import json
from pathlib import Path


DEFAULT_MINIMUM_PRICE = 5_000


def _load_payload(path: Path) -> dict:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def load_minimum_price(path: Path) -> int:
    try:
        payload = _load_payload(path)
        value = int(payload.get("minimum_price", DEFAULT_MINIMUM_PRICE))
    except (ValueError, TypeError):
        return DEFAULT_MINIMUM_PRICE
    return max(value, 0)


def load_auto_scan(path: Path) -> bool:
    return _load_payload(path).get("auto_scan_enabled") is True


def save_preferences(path: Path, minimum_price: int, auto_scan_enabled: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_suffix(".tmp")
    temporary_path.write_text(
        json.dumps(
            {
                "minimum_price": max(int(minimum_price), 0),
                "auto_scan_enabled": bool(auto_scan_enabled),
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    temporary_path.replace(path)


def save_minimum_price(path: Path, value: int) -> None:
    save_preferences(path, value, load_auto_scan(path))


def save_auto_scan(path: Path, enabled: bool) -> None:
    save_preferences(
        path,
        load_minimum_price(path),
        enabled,
    )
