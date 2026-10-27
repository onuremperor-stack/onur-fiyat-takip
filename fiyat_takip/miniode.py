import re
import time
from typing import Any

import requests

from .models import Product


BASE_URL = "https://miniode.com"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Safari/537.36"
    )
}


class CatalogError(RuntimeError):
    """Miniöde kataloğu okunamadığında oluşur."""


def _get_json(session: requests.Session, url: str, timeout: int) -> dict[str, Any]:
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            response = session.get(url, headers=HEADERS, timeout=timeout)
            if response.status_code == 429:
                retry_after = response.headers.get("Retry-After")
                try:
                    wait_seconds = float(retry_after) if retry_after else 10 * (attempt + 1)
                except ValueError:
                    wait_seconds = 10 * (attempt + 1)
                if attempt < 2:
                    time.sleep(min(max(wait_seconds, 1), 60))
                    continue
            response.raise_for_status()
            return response.json()
        except (requests.RequestException, ValueError) as exc:
            last_error = exc
            if attempt < 2:
                time.sleep(1.5 * (attempt + 1))
    raise CatalogError(f"Miniöde yanıt vermedi: {last_error}") from last_error


def get_collections(timeout: int = 20) -> list[dict[str, str]]:
    collections: list[dict[str, str]] = []
    with requests.Session() as session:
        for page in range(1, 101):
            url = f"{BASE_URL}/collections.json?limit=250&page={page}"
            items = _get_json(session, url, timeout).get("collections", [])
            if not items:
                break
            collections.extend(
                {
                    "title": str(item.get("title", "")).strip(),
                    "handle": str(item.get("handle", "")).strip(),
                }
                for item in items
                if item.get("handle")
            )
    return collections


def get_catalog(
    collection_handle: str | None = None,
    timeout: int = 20,
    max_products: int | None = None,
) -> list[Product]:
    products: list[Product] = []
    with requests.Session() as session:
        for page in range(1, 1001):
            if collection_handle:
                url = (
                    f"{BASE_URL}/collections/{collection_handle}/products.json"
                    f"?limit=250&page={page}"
                )
            else:
                url = f"{BASE_URL}/products.json?limit=250&page={page}"

            items = _get_json(session, url, timeout).get("products", [])
            if not items:
                break

            for item in items:
                products.extend(_parse_product(item))
                if max_products and len(products) >= max_products:
                    return products[:max_products]
            time.sleep(1.0)
    return products


def _parse_product(item: dict[str, Any]) -> list[Product]:
    title = str(item.get("title", "")).strip()
    handle = str(item.get("handle", "")).strip()
    condition = detect_condition(title)
    parsed: list[Product] = []

    for variant in item.get("variants", []):
        variant_title = str(variant.get("title", "")).strip()
        name = title if variant_title in {"", "Default Title"} else f"{title} - {variant_title}"
        sku = str(variant.get("sku") or "").strip()
        barcode = str(variant.get("barcode") or "").strip()
        if not barcode:
            digits = re.sub(r"\D", "", sku)
            if len(digits) in {8, 11, 12, 13, 14}:
                barcode = digits

        try:
            price = float(variant.get("price") or 0)
        except (TypeError, ValueError):
            price = 0.0

        parsed.append(
            Product(
                product_id=str(item.get("id", "")),
                variant_id=str(variant.get("id", "")),
                name=name,
                condition=condition,
                barcode=barcode,
                sku=sku,
                price=price,
                available=bool(variant.get("available", False)),
                url=f"{BASE_URL}/products/{handle}",
            )
        )
    return parsed


def detect_condition(title: str) -> str:
    normalized = title.translate(str.maketrans({"İ": "i", "I": "ı"})).lower()
    if "outlet" in normalized:
        return "Outlet"
    if "teşhir" in normalized or "teshir" in normalized:
        return "Teşhir"
    if "yenilenmiş" in normalized or "yenilenmis" in normalized:
        return "Yenilenmiş"
    return "Sıfır"
