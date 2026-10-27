from dataclasses import asdict, dataclass, field
from typing import Any
from urllib.parse import quote_plus


@dataclass(slots=True)
class Product:
    product_id: str
    variant_id: str
    name: str
    condition: str
    barcode: str
    sku: str
    price: float
    available: bool
    url: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class MarketQuote:
    source: str
    price: float
    url: str
    title: str = ""

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ScanResult:
    product: Product
    query: str
    quotes: list[MarketQuote] = field(default_factory=list)
    source_errors: dict[str, str] = field(default_factory=dict)
    reference_quote: MarketQuote | None = None
    difference_tl: float = 0.0
    difference_percent: float = 0.0
    status: str = "Piyasa Bulunamadı"
    recommendation: str = "Barkod veya ürün adını doğrulayın"

    def as_row(self) -> dict[str, Any]:
        quote = self.reference_quote
        return {
            "Ürün": self.product.name,
            "Kondisyon": self.product.condition,
            "Miniöde Fiyatı": self.product.price,
            "Piyasa Referansı": quote.price if quote else None,
            "Referans Kaynak": quote.source if quote else "Bulunamadı",
            "Eşleşen Ürün": quote.title if quote else "",
            "Akakçe Fiyatı": self._source_price("Akakçe"),
            "Cimri Fiyatı": self._source_price("Cimri"),
            "Akakçe Durumu": self._source_status("Akakçe"),
            "Cimri Durumu": self._source_status("Cimri"),
            "Fark TL": self.difference_tl,
            "Fark %": self.difference_percent,
            "Durum": self.status,
            "Öneri": self.recommendation,
            "SKU": self.product.sku,
            "Barkod": self.product.barcode,
            "Ürün URL": self.product.url,
            "Piyasa URL": quote.url if quote else "",
            "Akakçe Arama": (
                f"https://www.akakce.com/arama/?q={quote_plus(self.query)}"
            ),
            "Cimri Arama": (
                f"https://www.cimri.com/arama?q={quote_plus(self.query)}"
            ),
            "Arama Sorgusu": self.query,
        }

    def _source_price(self, source: str) -> float | None:
        quote = next((q for q in self.quotes if q.source == source), None)
        return quote.price if quote else None

    def _source_status(self, source: str) -> str:
        if self._source_price(source) is not None:
            return "Fiyat bulundu"
        return self.source_errors.get(source, "Ürün bulunamadı")
