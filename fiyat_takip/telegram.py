from html import escape
from io import BytesIO

import requests

from .config import Settings
from .models import ScanResult


def send_report(
    results: list[ScanResult],
    excel_content: bytes,
    settings: Settings,
) -> tuple[bool, str]:
    if not settings.telegram_enabled:
        return False, "Telegram token veya Chat ID tanımlı değil."

    actionable = [
        result
        for result in results
        if any(word in result.status for word in ("Kritik", "Yüksek", "Pahalı"))
    ]
    lines = [
        "🚨 <b>Fiyat Takip Raporu</b>",
        f"📊 Taranan ürün: <b>{len(results)}</b>",
        f"⚠️ Müdahale gereken: <b>{len(actionable)}</b>",
        "",
    ]
    for index, result in enumerate(actionable[:6], start=1):
        quote = result.reference_quote
        lines.extend(
            [
                f"<b>{index}. {escape(result.product.name[:45])}</b>",
                f"Miniöde: <b>{result.product.price:,.2f} TL</b>",
                f"Piyasa: <b>{quote.price:,.2f} TL</b> ({escape(quote.source)})",
                f"Durum: {escape(result.status)}",
                "",
            ]
        )
    if len(actionable) > 6:
        lines.append(f"<i>...ve {len(actionable) - 6} ürün daha.</i>")
    if not actionable:
        lines.append("✅ Müdahale gerektiren fiyat bulunmadı.")

    base_url = f"https://api.telegram.org/bot{settings.telegram_bot_token}"
    try:
        message_response = requests.post(
            f"{base_url}/sendMessage",
            json={
                "chat_id": settings.telegram_chat_id,
                "text": "\n".join(lines),
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            },
            timeout=15,
        )
        message_response.raise_for_status()

        document_response = requests.post(
            f"{base_url}/sendDocument",
            data={"chat_id": settings.telegram_chat_id},
            files={
                "document": (
                    "miniode_fiyat_raporu.xlsx",
                    BytesIO(excel_content),
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
            },
            timeout=45,
        )
        document_response.raise_for_status()
        return True, "Telegram bildirimi ve Excel raporu gönderildi."
    except requests.RequestException as exc:
        return False, f"Telegram gönderimi başarısız: {exc}"

