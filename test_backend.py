"""
Backend bağlantı test scripti
"""
import requests
import sys

def test_backend():
    """Backend'in çalışıp çalışmadığını test et"""
    base_url = "http://localhost:8000"
    
    print("🔍 Backend bağlantı testi başlatılıyor...")
    print(f"📍 URL: {base_url}\n")
    
    # Test 1: Health check
    try:
        print("1️⃣ Health check testi...")
        response = requests.get(f"{base_url}/health", timeout=5)
        if response.status_code == 200:
            print("   ✅ Backend çalışıyor!")
            print(f"   📊 Yanıt: {response.json()}")
        else:
            print(f"   ❌ Backend yanıt verdi ama hata kodu: {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print("   ❌ Backend'e bağlanılamadı!")
        print("   💡 Backend'i başlatmak için:")
        print("      uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload")
        return False
    except Exception as e:
        print(f"   ❌ Hata: {e}")
        return False
    
    # Test 2: Root endpoint
    try:
        print("\n2️⃣ Root endpoint testi...")
        response = requests.get(f"{base_url}/", timeout=5)
        if response.status_code == 200:
            print("   ✅ Root endpoint çalışıyor!")
            print(f"   📊 Yanıt: {response.json()}")
        else:
            print(f"   ⚠️ Root endpoint hata kodu: {response.status_code}")
    except Exception as e:
        print(f"   ⚠️ Root endpoint hatası: {e}")
    
    # Test 3: API docs
    try:
        print("\n3️⃣ API dokümantasyonu kontrolü...")
        response = requests.get(f"{base_url}/docs", timeout=5)
        if response.status_code == 200:
            print("   ✅ Swagger UI erişilebilir!")
            print(f"   🌐 Tarayıcıda aç: {base_url}/docs")
        else:
            print(f"   ⚠️ Docs endpoint hata kodu: {response.status_code}")
    except Exception as e:
        print(f"   ⚠️ Docs endpoint hatası: {e}")
    
    # Test 4: Companies endpoint
    try:
        print("\n4️⃣ Companies endpoint testi...")
        response = requests.get(f"{base_url}/api/v1/companies", timeout=5)
        if response.status_code == 200:
            print("   ✅ Companies endpoint çalışıyor!")
            data = response.json()
            print(f"   📊 Desteklenen şirketler: {data.get('companies', [])}")
            print(f"   📊 Scraper'lar: {data.get('scrapers_available', [])}")
        else:
            print(f"   ⚠️ Companies endpoint hata kodu: {response.status_code}")
    except Exception as e:
        print(f"   ⚠️ Companies endpoint hatası: {e}")
    
    print("\n" + "="*50)
    print("✅ Backend testi tamamlandı!")
    print("="*50)
    return True

if __name__ == "__main__":
    try:
        success = test_backend()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️ Test iptal edildi")
        sys.exit(1)

