from datetime import datetime
from pathlib import Path
import sqlite3
from typing import Any

from .models import ScanResult


SCHEMA = """
CREATE TABLE IF NOT EXISTS observations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scanned_at TEXT NOT NULL,
    variant_id TEXT NOT NULL,
    sku TEXT,
    product_name TEXT NOT NULL,
    condition_name TEXT NOT NULL,
    miniode_price REAL NOT NULL,
    market_price REAL,
    source_name TEXT,
    status_name TEXT NOT NULL,
    product_url TEXT,
    market_url TEXT,
    market_title TEXT
);
CREATE INDEX IF NOT EXISTS idx_observations_scanned_at
ON observations(scanned_at DESC);
CREATE INDEX IF NOT EXISTS idx_observations_variant_id
ON observations(variant_id, scanned_at DESC);
"""


def _connect(database_path: Path) -> sqlite3.Connection:
    database_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    connection.executescript(SCHEMA)
    columns = {
        row[1] for row in connection.execute("PRAGMA table_info(observations)").fetchall()
    }
    if "market_title" not in columns:
        connection.execute("ALTER TABLE observations ADD COLUMN market_title TEXT")
    return connection


def save_results(database_path: Path, results: list[ScanResult]) -> str:
    scanned_at = datetime.now().astimezone().isoformat(timespec="seconds")
    rows = []
    for result in results:
        quote = result.reference_quote
        rows.append(
            (
                scanned_at,
                result.product.variant_id,
                result.product.sku,
                result.product.name,
                result.product.condition,
                result.product.price,
                quote.price if quote else None,
                quote.source if quote else None,
                result.status,
                result.product.url,
                quote.url if quote else None,
                quote.title if quote else None,
            )
        )

    connection = _connect(database_path)
    try:
        connection.executemany(
            """
            INSERT INTO observations (
                scanned_at, variant_id, sku, product_name, condition_name,
                miniode_price, market_price, source_name, status_name,
                product_url, market_url, market_title
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        connection.commit()
    finally:
        connection.close()
    return scanned_at


def load_history(database_path: Path, limit: int = 1_000) -> list[dict[str, Any]]:
    if not database_path.exists():
        return []
    connection = _connect(database_path)
    try:
        records = connection.execute(
            """
            SELECT
                scanned_at AS "Tarama Zamanı",
                product_name AS "Ürün",
                condition_name AS "Kondisyon",
                miniode_price AS "Miniöde Fiyatı",
                market_price AS "Piyasa Referansı",
                source_name AS "Kaynak",
                market_title AS "Eşleşen Ürün",
                status_name AS "Durum",
                sku AS "SKU"
            FROM observations
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    finally:
        connection.close()
    return [dict(record) for record in records]
