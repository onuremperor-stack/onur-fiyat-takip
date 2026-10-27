from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from fiyat_takip.models import Product, ScanResult
from fiyat_takip.storage import load_history, save_results


class StorageTests(unittest.TestCase):
    def test_result_round_trip(self):
        item = Product("1", "2", "Örnek", "Sıfır", "", "SKU", 100, True, "url")
        result = ScanResult(product=item, query="örnek", status="Dengeli")

        with TemporaryDirectory() as directory:
            database = Path(directory) / "history.db"
            save_results(database, [result])
            history = load_history(database)

        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["Ürün"], "Örnek")


if __name__ == "__main__":
    unittest.main()

