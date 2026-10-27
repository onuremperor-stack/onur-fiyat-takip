from dataclasses import dataclass
import os
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _secret(name: str, default: str = "") -> str:
    value = os.getenv(name)
    if value:
        return value.strip()

    try:
        import streamlit as st

        value = st.secrets.get(name, default)
        return str(value).strip() if value is not None else default
    except Exception:
        return default


@dataclass(frozen=True, slots=True)
class Settings:
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    outlet_discount: float = 0.15
    display_discount: float = 0.20
    request_timeout: int = 20
    min_request_delay: float = 1.0
    chrome_helper_enabled: bool = True
    chrome_helper_port: int = 8765
    chrome_helper_connect_timeout: float = 6.0
    chrome_helper_job_timeout: float = 40.0
    data_dir: Path = PROJECT_ROOT / "data"
    report_dir: Path = PROJECT_ROOT / "reports"

    @classmethod
    def load(cls) -> "Settings":
        return cls(
            telegram_bot_token=_secret("TELEGRAM_BOT_TOKEN"),
            telegram_chat_id=_secret("TELEGRAM_CHAT_ID"),
            outlet_discount=float(os.getenv("OUTLET_DISCOUNT", "0.15")),
            display_discount=float(os.getenv("DISPLAY_DISCOUNT", "0.20")),
            request_timeout=int(os.getenv("REQUEST_TIMEOUT", "20")),
            min_request_delay=float(os.getenv("MIN_REQUEST_DELAY", "1.0")),
            chrome_helper_enabled=os.getenv("CHROME_HELPER_ENABLED", "1").lower()
            not in {"0", "false", "no"},
            chrome_helper_port=int(os.getenv("CHROME_HELPER_PORT", "8765")),
            chrome_helper_connect_timeout=float(
                os.getenv("CHROME_HELPER_CONNECT_TIMEOUT", "6")
            ),
            chrome_helper_job_timeout=float(
                os.getenv("CHROME_HELPER_JOB_TIMEOUT", "40")
            ),
        )

    @property
    def telegram_enabled(self) -> bool:
        return bool(self.telegram_bot_token and self.telegram_chat_id)

