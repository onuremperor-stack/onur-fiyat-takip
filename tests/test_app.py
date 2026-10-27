from pathlib import Path
import unittest
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from fiyat_takip.models import Product, ScanResult


PROJECT_ROOT = Path(__file__).resolve().parent.parent


class AppSmokeTests(unittest.TestCase):
    @patch("fiyat_takip.miniode.get_collections", return_value=[])
    def test_app_opens_without_exception(self, get_collections):
        app = AppTest.from_file(PROJECT_ROOT / "app.py", default_timeout=10).run()

        self.assertFalse(app.exception)
        self.assertTrue(app.title)
        self.assertTrue(app.selectbox)
        self.assertTrue(app.button)

    @patch("fiyat_takip.miniode.get_collections", return_value=[])
    def test_blocked_sources_are_visible_in_results(self, get_collections):
        product = Product(
            "1",
            "1",
            "Behringer Xenyx QX1222USB",
            "Outlet",
            "40336530131230",
            "40336530131230",
            13_900,
            True,
            "https://miniode.com",
        )
        result = ScanResult(
            product=product,
            query="behringer xenyx qx1222usb",
            source_errors={
                "Akakçe": "Akakçe erişimi engelledi (HTTP 403)",
                "Cimri": "Cimri erişimi engelledi (HTTP 403)",
            },
            status="Piyasa Erişimi Engellendi",
            recommendation="Manuel arama bağlantılarından fiyatı kontrol edin",
        )
        app = AppTest.from_file(PROJECT_ROOT / "app.py", default_timeout=10)
        app.session_state["results"] = [result]
        app.session_state["report_bytes"] = b"test"
        app.session_state["report_name"] = "test.xlsx"
        app.run()

        self.assertFalse(app.exception)
        table = app.dataframe[0].value
        self.assertEqual(table.iloc[0]["Durum"], "Piyasa Erişimi Engellendi")
        self.assertIn("HTTP 403", table.iloc[0]["Akakçe Durumu"])


if __name__ == "__main__":
    unittest.main()
