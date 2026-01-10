import asyncio
import json
import os
from pathlib import Path
from datetime import datetime


from playwright.async_api import async_playwright
from telegram import Bot

# ================== НАЛАШТУВАННЯ ==================
BOT_TOKEN = os.getenv ("BOT_TOKEN")
CHAT_ID = int(os.getenv("CHAT_ID", "414989524"))

CHECK_INTERVAL = 60  # перевірка кожні 60 секунд
MAX_PAGES = 10       # скільки сторінок афіші перевіряємо

SNAPSHOT_FILE = Path("afisha_snapshot.json")
BASE_URL = "https://sales.ft.org.ua/events?page={page}"

# ================== АФІША ==================
async def get_afisha():
    afisha = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        for page_num in range(1, MAX_PAGES + 1):
            url = BASE_URL.format(page=page_num)
            await page.goto(url, timeout=60000)
            await page.wait_for_timeout(1500)

            events = await page.query_selector_all("div.event-card")
            if not events:
                break

            for e in events:
                title_el = await e.query_selector("h3")
                date_el = await e.query_selector(".event-date")
                time_el = await e.query_selector(".event-time")
                link_el = await e.query_selector("a")

                if not title_el or not date_el or not link_el:
                    continue

                afisha.append({
                    "title": (await title_el.inner_text()).strip(),
                    "date": (await date_el.inner_text()).strip(),
                    "time": (await time_el.inner_text()).strip() if time_el else "",
                    "url": await link_el.get_attribute("href"),
                })

        await browser.close()

    return afisha

# ================== SNAPSHOT ==================
def load_snapshot():
    if SNAPSHOT_FILE.exists():
        return json.loads(SNAPSHOT_FILE.read_text(encoding="utf-8"))
    return []

def save_snapshot(data):
    SNAPSHOT_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

# ================== МОНІТОРИНГ ==================
async def monitor(bot: Bot):
    old = load_snapshot()
    new = await get_afisha()

    if not old:
        save_snapshot(new)
        return

    added = [e for e in new if e not in old]
    removed = [e for e in old if e not in new]

    if not added and not removed:
        return

    text = "🎭 ЗМІНИ В АФІШІ:\n\n"

    for e in added:
        text += f"🆕 {e['title']} — {e['date']} {e['time']}\n{e['url']}\n\n"

    for e in removed:
        text += f"❌ ЗНИКЛА: {e['title']} — {e['date']} {e['time']}\n\n"

    await bot.send_message(chat_id=CHAT_ID, text=text)
    save_snapshot(new)

# ================== LOOP ==================
async def main():
    bot = Bot(token=BOT_TOKEN)

    while True:
        try:
            await monitor(bot)
        except Exception as e:
            print("ERROR:", e)

        await asyncio.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    asyncio.run(main())
