import json
from pathlib import Path


DEFAULT_MINIMUM_PRICE = 5_000


def load_minimum_price(path: Path) -> int:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        value = int(payload.get("minimum_price", DEFAULT_MINIMUM_PRICE))
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return DEFAULT_MINIMUM_PRICE
    return max(value, 0)


def save_minimum_price(path: Path, value: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_suffix(".tmp")
    temporary_path.write_text(
        json.dumps({"minimum_price": max(int(value), 0)}, ensure_ascii=False),
        encoding="utf-8",
    )
    temporary_path.replace(path)
