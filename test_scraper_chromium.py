"""Scraper'larda Chromium'un açılıp açılmadığını test et - görünür mod"""
import sys
sys.path.insert(0, '.')

from backend.main import run_koru_scraper, run_doga_scraper
import time

print("="*60)
print("SCRAPER CHROMIUM TEST (GORUNUR MOD)")
print("="*60)

# Test verileri
test_data = {
    'tckn': '46984814554',
    'plaka': '29AS006',
    'dogum_tarihi': '05/08/1981',
    'ruhsat_seri_no': 'BF113557'
}

# KORU TEST
print("\n[TEST 1] KORU SCRAPER")
print("-"*60)
try:
    print("Chromium aciliyor (headless=False olmali)...")
    result = run_koru_scraper('trafik', test_data, 'test')
    print(f"Status: {result.status if result else 'None'}")
    if result and result.error:
        print(f"Error: {result.error[:100]}")
    print("Tarayici penceresi gorunur olmali!")
    time.sleep(3)
except Exception as e:
    print(f"Exception: {e}")

# DOGA TEST
print("\n[TEST 2] DOGA SCRAPER")
print("-"*60)
try:
    print("Chromium aciliyor (headless=False olmali)...")
    result = run_doga_scraper('trafik', test_data, 'test')
    print(f"Status: {result.status if result else 'None'}")
    if result and result.error:
        print(f"Error: {result.error[:100]}")
    print("Tarayici penceresi gorunur olmali!")
    time.sleep(3)
except Exception as e:
    print(f"Exception: {e}")

print("\n" + "="*60)
print("TEST TAMAMLANDI")
print("="*60)

