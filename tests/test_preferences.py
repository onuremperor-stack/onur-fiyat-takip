from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from fiyat_takip.preferences import (
    DEFAULT_MINIMUM_PRICE,
    load_minimum_price,
    save_minimum_price,
)


class PreferencesTests(unittest.TestCase):
    def test_default_minimum_price_is_five_thousand(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "preferences.json"
            self.assertEqual(load_minimum_price(path), DEFAULT_MINIMUM_PRICE)

    def test_last_minimum_price_is_saved(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "preferences.json"
            save_minimum_price(path, 7_500)
            self.assertEqual(load_minimum_price(path), 7_500)

    def test_invalid_preference_uses_default(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "preferences.json"
            path.write_text("not-json", encoding="utf-8")
            self.assertEqual(load_minimum_price(path), DEFAULT_MINIMUM_PRICE)


if __name__ == "__main__":
    unittest.main()
