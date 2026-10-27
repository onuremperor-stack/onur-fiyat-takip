import unittest

from fiyat_takip.analysis import analyze_product
from fiyat_takip.config import Settings
from fiyat_takip.models import MarketQuote, Product


def product(condition: str = "Sıfır", price: float = 10_000) -> Product:
    return Product(
        product_id="1",
        variant_id="2",
        name="Örnek Telefon 128 GB",
        condition=condition,
        barcode="1234567890123",
        sku="SKU-1",
        price=price,
        available=True,
        url="https://miniode.com/products/ornek",
    )


class AnalysisTests(unittest.TestCase):
    def setUp(self):
        self.settings = Settings()

    def test_uses_lowest_market_quote(self):
        result = analyze_product(
            product(),
            "örnek telefon 128 gb",
            [
                MarketQuote("Akakçe", 9_800, "https://akakce.example"),
                MarketQuote("Cimri", 9_500, "https://cimri.example"),
            ],
            self.settings,
        )
        self.assertEqual(result.reference_quote.source, "Cimri")
        self.assertEqual(result.reference_quote.price, 9_500)

    def test_outlet_more_expensive_than_new_is_critical(self):
        result = analyze_product(
            product("Outlet", 11_000),
            "örnek telefon",
            [MarketQuote("Akakçe", 10_000, "https://akakce.example")],
            self.settings,
        )
        self.assertIn("Kritik", result.status)

    def test_no_quote_is_reported(self):
        result = analyze_product(product(), "örnek telefon", [], self.settings)
        self.assertEqual(result.status, "Piyasa Bulunamadı")

    def test_blocked_source_is_not_reported_as_missing_product(self):
        result = analyze_product(
            product(),
            "örnek telefon",
            [],
            self.settings,
            {"Akakçe": "Akakçe erişimi engelledi (HTTP 403)"},
        )
        self.assertEqual(result.status, "Piyasa Erişimi Engellendi")
        self.assertIn("Manuel", result.recommendation)


if __name__ == "__main__":
    unittest.main()
