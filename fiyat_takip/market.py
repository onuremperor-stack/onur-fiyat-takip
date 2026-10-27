import asyncio
import re
import unicodedata
from collections.abc import Callable
from urllib.parse import quote_plus, urljoin

from .chrome_bridge import ChromeBridge
from .config import Settings
from .models import MarketQuote, Product


STOP_WORDS = {
    "outlet",
    "teşhir",
    "teshir",
    "yenilenmiş",
    "yenilenmis",
    "sıfır",
    "sifir",
    "ve",
    "ile",
    "için",
    "icin",
    "renk",
}

ACCESSORY_WORDS = {
    "adaptor",
    "adaptör",
    "aski",
    "askı",
    "canta",
    "çanta",
    "flash",
    "kablo",
    "kapak",
    "kayis",
    "kayış",
    "kilif",
    "kılıf",
    "kordon",
    "koruyucu",
    "sarj",
    "şarj",
    "stand",
    "uyumlu",
}

CONDITION_WORDS = {"outlet", "teshir", "vitrin", "yenilenmis"}
EXCLUSIVE_VARIANT_GROUPS = (
    {"cellular", "lte"},
    {"classic"},
    {"ultra"},
    {"pro"},
    {"max"},
    {"plus"},
    {"mini"},
    {"lite"},
    {"se"},
    {"active"},
    {"neo"},
)
VARIANT_ATTRIBUTE_WORDS = {
    "altin",
    "aluminyum",
    "bej",
    "beyaz",
    "bronz",
    "celik",
    "gri",
    "gumus",
    "kahverengi",
    "kirmizi",
    "lacivert",
    "mavi",
    "mor",
    "pembe",
    "sari",
    "siyah",
    "titanyum",
    "turuncu",
    "yesil",
}
ACCESSORY_URL_MARKERS = (
    "aksesuar",
    "ekran-koruyucu",
    "kablo",
    "kayis",
    "kilif",
    "kordon",
    "sarj",
)
NUMERIC_DESCRIPTOR_WORDS = {"adet", "kanal", "parca"}


class SourceAccessError(RuntimeError):
    def __init__(self, source: str, status_code: int):
        self.source = source
        self.status_code = status_code
        super().__init__(f"{source} erişimi engelledi (HTTP {status_code})")


class ChromeHelperError(RuntimeError):
    pass


def normalize_text(value: str) -> str:
    value = value.translate(str.maketrans({"İ": "i", "I": "i", "ı": "i"})).lower()
    value = unicodedata.normalize("NFKD", value)
    value = "".join(char for char in value if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9]+", " ", value).strip()


def build_query(product: Product) -> str:
    normalized = normalize_text(product.name)
    tokens = [
        token
        for token in normalized.split()
        if token not in STOP_WORDS and (len(token) > 1 or token.isdigit())
    ]
    if product.condition == "Yenilenmiş":
        return " ".join([*tokens[:12], "yenilenmis"])
    return " ".join(tokens[:12])


def title_matches(query: str, title: str, url: str = "") -> bool:
    if not title:
        return False

    query_tokens = normalize_text(query).split()
    title_tokens = set(normalize_text(title).split())
    if not query_tokens:
        return False

    query_token_set = set(query_tokens)
    if (title_tokens & ACCESSORY_WORDS) - query_token_set:
        return False
    normalized_url = url.lower()
    if not (query_token_set & ACCESSORY_WORDS) and any(
        marker in normalized_url for marker in ACCESSORY_URL_MARKERS
    ):
        return False
    if (title_tokens & CONDITION_WORDS) - query_token_set:
        return False

    for group in EXCLUSIVE_VARIANT_GROUPS:
        if bool(query_token_set & group) != bool(title_tokens & group):
            return False

    required_attributes = query_token_set & VARIANT_ATTRIBUTE_WORDS
    if required_attributes and not required_attributes.issubset(title_tokens):
        return False

    alpha_numeric_models = [
        token
        for token in query_tokens
        if any(char.isdigit() for char in token)
        and any(char.isalpha() for char in token)
    ]
    numeric_models = [
        token
        for index, token in enumerate(query_tokens)
        if token.isdigit()
        and (
            index + 1 >= len(query_tokens)
            or query_tokens[index + 1] not in NUMERIC_DESCRIPTOR_WORDS
        )
    ]
    required_models = [*alpha_numeric_models, *numeric_models]
    if required_models and not all(token in title_tokens for token in required_models):
        return False

    matched = sum(token in title_tokens for token in query_tokens)
    return matched / len(query_tokens) >= 0.65


def parse_price(raw_text: str | None) -> float | None:
    if not raw_text:
        return None
    text = raw_text.lower()
    if any(word in text for word in ("taksit", "yorum", "satıcı", "satici")):
        return None

    candidates = re.findall(r"\d{1,3}(?:\.\d{3})*(?:,\d{1,2})?|\d+(?:,\d{1,2})?", text)
    values: list[float] = []
    for candidate in candidates:
        try:
            value = float(candidate.replace(".", "").replace(",", "."))
        except ValueError:
            continue
        if value >= 50:
            values.append(value)
    return min(values, default=None)


async def _first_text(locator) -> str:
    if await locator.count() == 0:
        return ""
    try:
        return (await locator.first.inner_text()).strip()
    except Exception:
        return ""


async def _scan_akakce(
    page,
    query: str,
    minimum_price: float,
    match_query: str | None = None,
) -> MarketQuote | None:
    search_url = f"https://www.akakce.com/arama/?q={quote_plus(query)}"
    match_query = match_query or query
    response = await page.goto(search_url, wait_until="domcontentloaded", timeout=25_000)
    if response and response.status in {403, 429}:
        raise SourceAccessError("Akakçe", response.status)

    cards = page.locator("#APL > li, ul.pl_v8 > li, li.w")
    for index in range(min(await cards.count(), 20)):
        card = cards.nth(index)
        title = await _first_text(card.locator(".pn_v8, h3, a"))
        href = await card.locator("a").first.get_attribute("href")
        result_url = urljoin("https://www.akakce.com", href or search_url)
        if not title_matches(match_query, title, result_url):
            continue
        price = parse_price(await _first_text(card.locator("span.pt_v8, span.pr_v8, em.v_v8, .p-price")))
        if price is None or price <= minimum_price:
            continue
        return MarketQuote("Akakçe", price, result_url, title)

    heading = await _first_text(page.locator("h1"))
    if title_matches(match_query, heading, page.url):
        price = parse_price(await _first_text(page.locator("span.pt_v8, span.pr_v8, .p-price")))
        if price and price > minimum_price:
            return MarketQuote("Akakçe", price, page.url, heading)
    return None


async def _scan_cimri(
    page,
    query: str,
    minimum_price: float,
    match_query: str | None = None,
) -> MarketQuote | None:
    search_url = f"https://www.cimri.com/arama?q={quote_plus(query)}"
    match_query = match_query or query
    response = await page.goto(search_url, wait_until="domcontentloaded", timeout=25_000)
    if response and response.status in {403, 429}:
        raise SourceAccessError("Cimri", response.status)

    selector = (
        "article, [data-test-id='product-card'], [class*='ProductCard'], "
        "[class*='productCard'], li[class*='product']"
    )
    cards = page.locator(selector)
    for index in range(min(await cards.count(), 20)):
        card = cards.nth(index)
        text = await _first_text(card)
        href = await card.locator("a").first.get_attribute("href")
        result_url = urljoin("https://www.cimri.com", href or search_url)
        if not title_matches(match_query, text, result_url):
            continue
        price = parse_price(
            await _first_text(
                card.locator("[data-test-id='price'], .price, [class*='price']")
            )
        )
        if price is None or price <= minimum_price:
            continue
        return MarketQuote("Cimri", price, result_url, text[:200])
    return None


def _quote_from_helper_payload(
    source: str,
    query: str,
    minimum_price: float,
    payload: dict,
) -> MarketQuote | None:
    if payload.get("error"):
        raise ChromeHelperError(f"{source} Chrome yardımcısı: {payload['error']}")
    if payload.get("blocked"):
        raise ChromeHelperError(f"{source} güvenlik doğrulaması gösterdi")

    quotes: list[MarketQuote] = []
    for card in payload.get("cards", []):
        result_url = str(card.get("href") or payload.get("url") or "")
        titles = [str(value).strip() for value in card.get("titles", []) if value]
        text = str(card.get("text", "")).strip()
        matching_title = next(
            (title for title in titles if title_matches(query, title, result_url)),
            "",
        )
        if not matching_title and title_matches(query, text, result_url):
            matching_title = text[:200]
        if not matching_title:
            continue

        raw_prices = [str(value) for value in card.get("prices", []) if value]
        if not raw_prices and text:
            raw_prices = [text]
        prices = [price for raw in raw_prices if (price := parse_price(raw)) is not None]
        valid_prices = [price for price in prices if price > minimum_price]
        if not valid_prices:
            continue
        quotes.append(
            MarketQuote(
                source,
                valid_prices[0],
                result_url,
                matching_title,
            )
        )
    return min(quotes, key=lambda quote: quote.price, default=None)


async def _scan_with_helper(
    bridge: ChromeBridge,
    source: str,
    query: str,
    minimum_price: float,
    timeout: float,
    match_query: str | None = None,
) -> MarketQuote | None:
    base_url = (
        "https://www.akakce.com/arama/?q="
        if source == "Akakçe"
        else "https://www.cimri.com/arama?q="
    )
    payload = await bridge.request(
        source,
        f"{base_url}{quote_plus(query)}",
        timeout,
    )
    return _quote_from_helper_payload(
        source,
        match_query or query,
        minimum_price,
        payload,
    )


async def _scan_products_with_helper(
    products: list[Product],
    settings: Settings,
    bridge: ChromeBridge,
    progress_callback: Callable[[int, int], None] | None,
) -> list[tuple[Product, str, list[MarketQuote], dict[str, str]]]:
    results: list[tuple[Product, str, list[MarketQuote], dict[str, str]]] = []
    for index, product in enumerate(products, start=1):
        query = build_query(product)
        minimum_price = product.price * 0.20 if product.price > 2_000 else 0
        quotes: list[MarketQuote] = []
        source_errors: dict[str, str] = {}

        for source in ("Akakçe", "Cimri"):
            try:
                quote = await _scan_with_helper(
                    bridge,
                    source,
                    query,
                    minimum_price,
                    settings.chrome_helper_job_timeout,
                )
            except (ChromeHelperError, TimeoutError) as exc:
                source_errors[source] = str(exc)
                quote = None
            if quote:
                quotes.append(quote)

        if not quotes and product.barcode:
            for source in ("Akakçe", "Cimri"):
                try:
                    quote = await _scan_with_helper(
                        bridge,
                        source,
                        product.barcode,
                        minimum_price,
                        settings.chrome_helper_job_timeout,
                        match_query=query,
                    )
                except (ChromeHelperError, TimeoutError) as exc:
                    source_errors[source] = str(exc)
                    quote = None
                if quote:
                    quotes.append(quote)
            if quotes:
                query = f"{query} [Barkod: {product.barcode}]"

        results.append((product, query, quotes, source_errors))
        if progress_callback:
            progress_callback(index, len(products))
    return results


async def scan_products(
    products: list[Product],
    settings: Settings,
    progress_callback: Callable[[int, int], None] | None = None,
) -> list[tuple[Product, str, list[MarketQuote], dict[str, str]]]:
    if settings.chrome_helper_enabled:
        bridge = ChromeBridge(settings.chrome_helper_port)
        try:
            bridge.start()
            if await bridge.wait_for_client(settings.chrome_helper_connect_timeout):
                return await _scan_products_with_helper(
                    products,
                    settings,
                    bridge,
                    progress_callback,
                )
        except OSError as exc:
            print(f"Chrome yardımcısı köprüsü başlatılamadı: {exc}")
        finally:
            bridge.stop()

    try:
        from playwright.async_api import async_playwright
    except ImportError as exc:
        raise RuntimeError(
            "Playwright kurulu değil. Kurulum dosyasını çalıştırın."
        ) from exc

    results: list[tuple[Product, str, list[MarketQuote], dict[str, str]]] = []
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        context = await browser.new_context(
            locale="tr-TR",
            timezone_id="Europe/Istanbul",
            viewport={"width": 1440, "height": 1000},
        )
        page = await context.new_page()

        for index, product in enumerate(products, start=1):
            query = build_query(product)
            minimum_price = product.price * 0.20 if product.price > 2_000 else 0
            quotes: list[MarketQuote] = []
            source_errors: dict[str, str] = {}

            for source, scanner in (("Akakçe", _scan_akakce), ("Cimri", _scan_cimri)):
                try:
                    quote = await scanner(page, query, minimum_price)
                except SourceAccessError as exc:
                    source_errors[source] = str(exc)
                    quote = None
                except Exception as exc:
                    source_errors[source] = f"Tarama hatası: {type(exc).__name__}"
                    print(f"{scanner.__name__} hatası ({product.sku}): {exc}")
                    quote = None
                if quote:
                    quotes.append(quote)
                await asyncio.sleep(settings.min_request_delay)

            if not quotes and product.barcode:
                for source, scanner in (("Akakçe", _scan_akakce), ("Cimri", _scan_cimri)):
                    try:
                        quote = await scanner(
                            page,
                            product.barcode,
                            minimum_price,
                            match_query=query,
                        )
                    except SourceAccessError as exc:
                        source_errors[source] = str(exc)
                        quote = None
                    except Exception as exc:
                        source_errors[source] = f"Tarama hatası: {type(exc).__name__}"
                        print(f"Barkod arama hatası ({product.sku}): {exc}")
                        quote = None
                    if quote:
                        quotes.append(quote)
                    await asyncio.sleep(settings.min_request_delay)
                if quotes:
                    query = f"{query} [Barkod: {product.barcode}]"

            results.append((product, query, quotes, source_errors))
            if progress_callback:
                progress_callback(index, len(products))

        await context.close()
        await browser.close()
    return results
