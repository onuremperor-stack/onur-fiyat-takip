from collections.abc import Callable

from .analysis import analyze_product
from .config import Settings
from .market import scan_products
from .models import Product, ScanResult


async def run_scan(
    products: list[Product],
    settings: Settings,
    progress_callback: Callable[[int, int], None] | None = None,
) -> list[ScanResult]:
    market_results = await scan_products(products, settings, progress_callback)
    return [
        analyze_product(product, query, quotes, settings, source_errors)
        for product, query, quotes, source_errors in market_results
    ]
