import unittest

from fiyat_takip.market import (
    ChromeHelperError,
    _quote_from_helper_payload,
    build_query,
    parse_price,
    title_matches,
)
from fiyat_takip.models import Product


class MarketHelpersTests(unittest.TestCase):
    def test_turkish_price_is_parsed(self):
        self.assertEqual(parse_price("12.499,90 TL"), 12_499.90)

    def test_model_number_must_match(self):
        self.assertTrue(title_matches("iphone 15 pro 128 gb", "Apple iPhone 15 Pro 128 GB"))
        self.assertFalse(title_matches("iphone 15 pro 128 gb", "Apple iPhone 14 Pro 128 GB"))

    def test_descriptor_number_can_be_omitted_when_model_matches(self):
        self.assertTrue(
            title_matches(
                "behringer xenyx qx1222usb 12 kanal mikser",
                "Behringer Xenyx QX1222USB Deck Mikser",
            )
        )

    def test_barcode_does_not_match_an_unrelated_title(self):
        self.assertFalse(title_matches("8806090089886", "Samsung saat kordonu"))

    def test_accessory_does_not_match_main_product(self):
        self.assertFalse(
            title_matches(
                "iphone 15 pro 128 gb",
                "iPhone 15 Pro Uyumlu 128 GB Flash Bellek",
            )
        )

    def test_accessory_category_url_does_not_match_main_product(self):
        self.assertFalse(
            title_matches(
                "haylou ls02 akilli saat",
                "Haylou LS02 Siyah Akıllı Saat",
                "https://www.cimri.com/akilli-saat-aksesuari/ekran-koruyucu",
            )
        )

    def test_used_listing_does_not_match_new_market_query(self):
        self.assertFalse(
            title_matches(
                "apple watch se 2 2023 gps 40mm gece yarisi aluminyum kasa",
                "Apple Watch SE 2 2023 GPS 40mm Gece Yarısı Alüminyum Kasa Teşhir Vitrin",
            )
        )

    def test_material_and_color_must_match(self):
        self.assertFalse(
            title_matches(
                "apple watch series 10 gps cellular 42mm altin titanyum kasa",
                "Apple Watch Series 10 GPS Cellular 42mm Siyah Alüminyum Kasa",
            )
        )

    def test_query_removes_condition(self):
        item = Product(
            product_id="1",
            variant_id="2",
            name="Teşhir Apple iPhone 15 Pro 128 GB",
            condition="Teşhir",
            barcode="",
            sku="",
            price=1,
            available=True,
            url="",
        )
        self.assertNotIn("teshir", build_query(item))

    def test_refurbished_query_keeps_condition(self):
        item = Product(
            product_id="1",
            variant_id="2",
            name="Yenilenmiş Apple iPhone 15 Pro 128 GB",
            condition="Yenilenmiş",
            barcode="",
            sku="",
            price=1,
            available=True,
            url="",
        )
        self.assertIn("yenilenmis", build_query(item))

    def test_chrome_helper_payload_returns_lowest_matching_quote(self):
        quote = _quote_from_helper_payload(
            "Akakçe",
            "iphone 15 pro 128 gb",
            1_000,
            {
                "url": "https://www.akakce.com/arama/",
                "cards": [
                    {
                        "titles": ["Apple iPhone 14 Pro 128 GB"],
                        "prices": ["38.000 TL"],
                        "href": "https://example.com/wrong",
                    },
                    {
                        "titles": ["Apple iPhone 15 Pro 128 GB"],
                        "prices": ["49.999,90 TL", "48.750 TL"],
                        "href": "https://example.com/right",
                    },
                ],
            },
        )
        self.assertIsNotNone(quote)
        self.assertEqual(quote.price, 49_999.90)
        self.assertEqual(quote.url, "https://example.com/right")

    def test_chrome_helper_reports_block_page(self):
        with self.assertRaises(ChromeHelperError):
            _quote_from_helper_payload(
                "Cimri",
                "iphone 15",
                0,
                {"blocked": True, "cards": []},
            )


if __name__ == "__main__":
    unittest.main()
