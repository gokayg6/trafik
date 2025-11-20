import os
import time
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

def main():
    load_dotenv()
    url = os.getenv("KORU_LOGIN_URL", "").strip()
    headless = os.getenv("HEADLESS", "false").lower() == "true"

    if not url:
        raise RuntimeError("KORU_LOGIN_URL .env dosyasında tanımlı değil.")

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=headless)
        context = browser.new_context(viewport={"width": 1366, "height": 900})
        page = context.new_page()

        page.goto(url, wait_until="domcontentloaded", timeout=45000)
        # Sayfa otursun diye hafif bekleme (dinamik scriptler için)
        time.sleep(3)

        # Görsel doğrulama için ekran görüntüsü
        page.screenshot(path="koru_login_page.png", full_page=True)
        print("[OK] Login sayfası açıldı. Screenshot: koru_login_page.png")

        browser.close()

if __name__ == "__main__":
    main()
