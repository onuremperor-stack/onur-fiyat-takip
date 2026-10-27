from .config import Settings
from .models import MarketQuote, Product, ScanResult


def analyze_product(
    product: Product,
    query: str,
    quotes: list[MarketQuote],
    settings: Settings,
    source_errors: dict[str, str] | None = None,
) -> ScanResult:
    valid_quotes = [quote for quote in quotes if quote.price > 0]
    reference = min(valid_quotes, key=lambda quote: quote.price, default=None)
    result = ScanResult(
        product=product,
        query=query,
        quotes=valid_quotes,
        source_errors=source_errors or {},
        reference_quote=reference,
    )
    if reference is None:
        if result.source_errors:
            result.status = "Piyasa Erişimi Engellendi"
            result.recommendation = "Manuel arama bağlantılarından fiyatı kontrol edin"
        return result

    market_price = reference.price
    result.difference_tl = product.price - market_price
    result.difference_percent = (result.difference_tl / market_price) * 100

    if product.condition == "Yenilenmiş":
        if product.price > market_price * 1.05:
            result.status = "Yüksek (Piyasadan Pahalı)"
            result.recommendation = f"Fiyatı yaklaşık {market_price:,.0f} TL seviyesine çekin"
        elif product.price < market_price * 0.85:
            result.status = "Rekabetçi (Çok Avantajlı)"
            result.recommendation = "Marjı kontrol ederek fiyatı koruyun"
        else:
            result.status = "Rekabetçi (İyi)"
            result.recommendation = "Fiyat piyasa seviyesine uygun"
        return result

    if product.condition in {"Outlet", "Teşhir"}:
        discount = (
            settings.display_discount
            if product.condition == "Teşhir"
            else settings.outlet_discount
        )
        ceiling = market_price * (1 - discount)
        if product.price >= market_price:
            result.status = "Kritik Hata (Sıfırdan Pahalı)"
            result.recommendation = f"Acil indirim; hedef en fazla {ceiling:,.0f} TL"
        elif product.price > ceiling:
            result.status = "Yüksek (Yetersiz İndirim)"
            result.recommendation = f"Fiyatı {ceiling:,.0f} TL veya altına çekin"
        else:
            result.status = "Rekabetçi (İyi)"
            result.recommendation = "Fiyat kondisyon indirimine uygun"
        return result

    if result.difference_percent > 5:
        result.status = "Piyasadan Yüksek"
        result.recommendation = f"Fiyatı yaklaşık {market_price:,.0f} TL seviyesine çekin"
    elif result.difference_percent < -15:
        result.status = "Çok Ucuz (Marj Kontrolü)"
        result.recommendation = "Marjı kontrol edin; fiyat yükseltilebilir"
    else:
        result.status = "Dengeli"
        result.recommendation = "Fiyat piyasa ile uyumlu"
    return result
