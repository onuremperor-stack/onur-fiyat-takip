import asyncio
import sys
from urllib.parse import quote_plus

from playwright.async_api import async_playwright


async def main(query: str) -> None:
    targets = {
        "Akakçe": f"https://www.akakce.com/arama/?q={quote_plus(query)}",
        "Cimri": f"https://www.cimri.com/arama?q={quote_plus(query)}",
    }
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        page = await browser.new_page(locale="tr-TR")
        for source, url in targets.items():
            response = await page.goto(url, wait_until="domcontentloaded", timeout=30_000)
            await page.wait_for_timeout(2_000)
            body = (await page.locator("body").inner_text())[:1_500]
            print(f"\n--- {source} ---")
            print("status:", response.status if response else None)
            print("url:", page.url)
            print("title:", await page.title())
            print("body:", body.replace("\n", " | "))
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main(" ".join(sys.argv[1:])))
