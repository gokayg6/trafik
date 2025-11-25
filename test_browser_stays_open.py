"""Browser'ın açık kalıp kalmadığını test et - geçerli URL ile"""
import sys
import asyncio
sys.path.insert(0, '.')

from scrapers_event.koru_scraper import KoruScraper
from playwright.sync_api import sync_playwright
import time

# Windows için event loop policy ayarla
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    try:
        try:
            loop = asyncio.get_event_loop()
            if loop and not loop.is_closed():
                loop.close()
        except RuntimeError:
            pass
    except:
        pass
    asyncio.set_event_loop(asyncio.new_event_loop())

print("="*60)
print("BROWSER ACILMA VE ACIK KALMA TESTI")
print("="*60)

try:
    print("[1] sync_playwright() baslatiliyor...")
    with sync_playwright() as pw:
        print("[2] Chromium launch ediliyor (headless=False)...")
        browser = pw.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        
        print("[3] Google.com'a gidiliyor (gecerli URL)...")
        page.goto("https://www.google.com", wait_until="domcontentloaded", timeout=30000)
        print("[4] Sayfa yuklendi! Browser acik kalacak...")
        print("    (Tarayici penceresi 10 saniye acik kalacak)")
        
        # 10 saniye bekle - browser açık kalmalı
        time.sleep(10)
        
        print("[5] Browser kapatiliyor...")
        page.close()
        context.close()
        browser.close()
        print("[6] Browser kapatildi!")
    
    print("[OK] TEST BASARILI - Browser acildi ve 10 saniye acik kaldi!")
    
except Exception as e:
    print(f"[ERROR] TEST BASARISIZ: {e}")
    import traceback
    traceback.print_exc()

print("="*60)

