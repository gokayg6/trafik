"""Chromium'un açılıp açılmadığını test et"""
import asyncio
import sys
import time
from playwright.sync_api import sync_playwright

# Windows için event loop policy ayarla
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    # Mevcut event loop'u kapat ve yeni bir tane oluştur
    try:
        try:
            loop = asyncio.get_event_loop()
            if loop and not loop.is_closed():
                loop.close()
        except RuntimeError:
            pass
    except:
        pass
    # Yeni event loop oluştur
    asyncio.set_event_loop(asyncio.new_event_loop())

print("="*60)
print("CHROMIUM ACILMA TESTI")
print("="*60)

try:
    print("[1] sync_playwright() baslatiliyor...")
    with sync_playwright() as p:
        print("[2] Chromium launch ediliyor (headless=False)...")
        browser = p.chromium.launch(headless=False)
        print("[3] Chromium ACILDI! 10 saniye bekleniyor...")
        print("    (Tarayici penceresi gorunur olmali)")
        time.sleep(10)
        print("[4] Chromium kapatiliyor...")
        browser.close()
        print("[5] Chromium kapatildi!")
    print("[OK] TEST BASARILI - Chromium acildi ve calisti!")
except Exception as e:
    print(f"[ERROR] TEST BASARISIZ: {e}")
    import traceback
    traceback.print_exc()

print("="*60)

