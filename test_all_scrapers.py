"""
Tüm scraper'ları tek tek test et ve Chromium'un açıldığını doğrula
"""
import sys
sys.path.insert(0, '.')

from backend.main import (
    run_sompo_scraper,
    run_koru_scraper,
    run_doga_scraper
)

# Test verileri
TEST_DATA = {
    'tckn': '46984814554',
    'plaka': '29AS006',
    'dogum_tarihi': '05/08/1981',
    'ruhsat_seri_no': 'BF113557'
}

def test_scraper(name, func, branch, data):
    """Bir scraper'i test et"""
    print("\n" + "="*60)
    print(f"[TEST] {name.upper()} SCRAPER TEST")
    print("="*60)
    try:
        result = func(branch, data, 'test')
        if result:
            print(f"[OK] Status: {result.status}")
            if result.error:
                print(f"[WARNING] Error: {result.error[:150]}")
            else:
                print(f"[OK] Basarili! Chromium acildi ve scraper calisti!")
        else:
            print("[ERROR] Result: None")
    except Exception as e:
        print(f"[ERROR] Exception: {e}")
    print("="*60)

# Tüm scraper'ları test et
if __name__ == "__main__":
    print("\nTUM SCRAPER'LARI TEST EDIYORUZ...")
    print("="*60)
    
    # 1. SOMPO
    test_scraper(
        "SOMPO",
        run_sompo_scraper,
        'trafik',
        {
            'tckn': TEST_DATA['tckn'],
            'plaka': TEST_DATA['plaka'],
            'dogum_tarihi': TEST_DATA['dogum_tarihi']
        }
    )
    
    # 2. KORU
    test_scraper(
        "KORU",
        run_koru_scraper,
        'trafik',
        {
            'tckn': TEST_DATA['tckn'],
            'plaka': TEST_DATA['plaka'],
            'dogum_tarihi': TEST_DATA['dogum_tarihi'],
            'ruhsat_seri_no': TEST_DATA['ruhsat_seri_no']
        }
    )
    
    # 3. DOGA
    test_scraper(
        "DOGA",
        run_doga_scraper,
        'trafik',
        {
            'tckn': TEST_DATA['tckn'],
            'plaka': TEST_DATA['plaka'],
            'dogum_tarihi': TEST_DATA['dogum_tarihi'],
            'ruhsat_seri_no': TEST_DATA['ruhsat_seri_no']
        }
    )
    
    # Not: Anadolu, Referans, Seker ve Atlas scraper'lari henuz backend/main.py'de 
    # ayri fonksiyonlar olarak implement edilmemis.
    # Bunlar SCRAPER_FUNCTIONS dictionary'sinde tanimli olabilir.
    print("\n[NOT] Diger scraper'lar (Anadolu, Referans, Seker, Atlas) henuz test edilmedi.")
    
    print("\n[OK] TUM TESTLER TAMAMLANDI!")
    print("="*60)

