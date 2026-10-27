import asyncio
import os

from fiyat_takip.analysis import analyze_product
from fiyat_takip.config import Settings
from fiyat_takip.market import scan_products
from fiyat_takip.miniode import get_catalog
from fiyat_takip.reports import create_excel, save_excel
from fiyat_takip.storage import save_results
from fiyat_takip.telegram import send_report


def main() -> int:
    settings = Settings.load()
    minimum_price = float(os.getenv("MINIMUM_PRICE", "250"))
    maximum_products = int(os.getenv("MAXIMUM_PRODUCTS", "0"))

    catalog_limit = max(maximum_products * 10, 250) if maximum_products else None
    products = [
        product
        for product in get_catalog(
            timeout=settings.request_timeout,
            max_products=catalog_limit,
        )
        if product.available and product.price >= minimum_price
    ]
    if maximum_products:
        products = products[:maximum_products]
    if not products:
        print("Taranacak ürün bulunamadı.")
        return 1

    market_results = asyncio.run(scan_products(products, settings))
    results = [
        analyze_product(product, query, quotes, settings, source_errors)
        for product, query, quotes, source_errors in market_results
    ]
    report_bytes = create_excel(results)
    report_path = save_excel(settings.report_dir, report_bytes, "gece_fiyat_raporu")
    save_results(settings.data_dir / "price_history.db", results)
    print(f"Rapor oluşturuldu: {report_path}")

    if settings.telegram_enabled:
        sent, message = send_report(results, report_bytes, settings)
        print(message)
        return 0 if sent else 2
    print("Telegram ayarları bulunmadığı için bildirim gönderilmedi.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
