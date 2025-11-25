# 📋 SİGORTA OTOMASYON PROJESİ - DETAYLI ANALİZ RAPORU

**Tarih:** 2025-01-XX  
**Proje:** FinalPy - Çoklu Sigorta Şirketi Teklif Otomasyonu

---

## 1. PROJE YAPISI ÖZETİ

### 1.1 Klasör Yapısı

```
FinalPy/
├── scrapers_event/          # Scraper modülleri
│   ├── sompo_event.py      # Sompo scraper (1900+ satır)
│   ├── doga_scraper.py     # Doğa scraper
│   ├── koru_scraper.py      # Koru scraper
│   ├── anadolu_scraper.py   # Anadolu scraper
│   ├── seker_scraper.py     # Şeker scraper
│   ├── atlas_scraper.py     # Atlas scraper
│   ├── referans_event.py    # Referans scraper
│   └── app/                 # Ortak config dosyaları
│       └── config.py
│
├── Backend Dosyaları (DAĞINIK YAPI!)
│   ├── sompo_backend.py     # Port 8000
│   ├── koru_backend.py      # Port 8003
│   ├── doga_backend.py      # Port 8000 (çakışma!)
│   ├── seker_backend.py      # Port 8004
│   ├── referans_backend.py   # Port belirtilmemiş
│   ├── sompo_new.py          # Yeni versiyon (kullanılmıyor?)
│   ├── koru_new.py           # Yeni versiyon (kullanılmıyor?)
│   └── seker_new.py          # Yeni versiyon (kullanılmıyor?)
│
├── frontend2 newee/frontend/ # Next.js frontend
│   ├── src/
│   │   ├── pages/           # Sayfalar (trafik, kasko, vb.)
│   │   ├── services/         # API servisleri
│   │   │   └── api.ts       # Frontend API client
│   │   └── components/      # UI bileşenleri
│   └── package.json
│
├── cookies/                  # Playwright storage state dosyaları
├── __pycache__/             # Python cache
└── README.md                 # Minimal dokümantasyon
```

### 1.2 Mevcut Durum

**✅ Çalışan Bileşenler:**
- Scraper'lar mevcut ve çalışır durumda (Sompo, Doğa, Koru, Şeker, Anadolu, Atlas, Referans)
- Frontend Next.js ile hazırlanmış, modern UI bileşenleri var
- Her sigorta şirketi için ayrı backend API mevcut

**❌ Eksik/Kopuk Bileşenler:**
- **Tek birleşik backend yok** - Her şirket için ayrı backend dosyası
- **Veritabanı entegrasyonu yok** - Sadece in-memory dictionary'ler kullanılıyor
- **Standart API endpoint'leri yok** - Her backend farklı endpoint yapısı kullanıyor
- **.env dosyası yok** - Örnek .env.example bile yok
- **requirements.txt yok** - Bağımlılıklar belirtilmemiş
- **Dokümantasyon eksik** - Çalıştırma talimatları yok

---

## 2. TESPİT EDİLEN KRİTİK SORUNLAR

### 2.1 🔴 KRİTİK - Çalışmayı Engelleme Potansiyeli Yüksek

#### Sorun 1: JSONResponse Import Eksikliği
**Dosya:** `sompo_backend.py:389`
```python
# HATA: JSONResponse import edilmemiş ama kullanılıyor
@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    return JSONResponse(...)  # ❌ NameError: name 'JSONResponse' is not defined
```
**Çözüm:** `from fastapi.responses import JSONResponse` eklenmeli.

#### Sorun 2: Port Çakışması
**Dosyalar:** `sompo_backend.py` ve `doga_backend.py`
- Her ikisi de port `8000` kullanıyor
- Aynı anda çalıştırılamaz

#### Sorun 3: Pydantic v2 Uyumsuzluğu
**Dosyalar:** `sompo_new.py`, `koru_new.py`
```python
# ❌ ESKİ YÖNTEM (Pydantic v1)
@validator('tckn')
def validate_tckn(cls, v):
    ...

# ✅ YENİ YÖNTEM (Pydantic v2)
@field_validator('tckn')
@classmethod
def validate_tckn(cls, v):
    ...
```
**Etki:** Pydantic v2 kullanıldığında deprecated uyarıları ve potansiyel hatalar.

#### Sorun 4: Encoding Sorunları
**Dosya:** `frontend2 newee/frontend/src/services/api.ts`
- Dosyada encoding sorunları var (emoji karakterleri bozuk)
- Örnek: `'Ys? Sompo Kasko teklifi isteYi:'` (satır 305)

#### Sorun 5: Hardcoded IP Adresleri
**Dosya:** `frontend2 newee/frontend/src/services/api.ts:4-6`
```typescript
const API_BASE_URL = 'http://212.68.34.202:8000';  // ❌ Hardcoded IP
const KORU_BASE_URL = 'http://212.68.34.202:8003';
const SEKER_BASE_URL = 'http://212.68.34.202:8004';
```
**Etki:** Lokal geliştirme ve farklı ortamlar için esnek değil.

### 2.2 🟡 ORTA - Mimari ve Standartlaştırma Sorunları

#### Sorun 6: Dağınık Backend Yapısı
- **7 farklı backend dosyası** var (sompo, koru, doga, seker, referans, anadolu, atlas)
- Her biri farklı endpoint yapısı kullanıyor
- Tek bir unified backend yok

**Örnek Endpoint Farklılıkları:**
- Sompo: `/teklif/trafik`, `/teklif/kasko`
- Koru: `/trafik-teklif`, `/kasko-teklif`
- Doğa: `/kasko-teklifi`, `/trafik-teklifi`
- Şeker: `/api/v1/teklif`

#### Sorun 7: Veritabanı Yok
- Tüm backend'ler **in-memory dictionary** kullanıyor
- Teklif kayıtları kalıcı değil
- SQLAlchemy modelleri yok
- Migration sistemi yok

#### Sorun 8: Standart Olmayan Scraper Çıktıları
Her scraper farklı format döndürüyor:

**Sompo:**
```python
{
    'basarili': True,
    'teklif_no': '...',
    'brut_prim': '...',
    'teklif_tipi': 'STANDART'
}
```

**Koru:**
```python
{
    'trafik': {
        'teklif_no': '...',
        'brut_prim': '...',
        'prim': '...'
    }
}
```

**Doğa:**
```python
{
    'premium_data': {
        'net_prim': '...',
        'ysv': '...',
        'gv': '...'
    }
}
```

**Çözüm:** Standart bir `Offer` modeli oluşturulmalı.

#### Sorun 9: CORS Güvenlik Riski
Tüm backend'lerde:
```python
allow_origins=["*"]  # ❌ Tüm origin'lere izin veriyor
```
**Çözüm:** Sadece frontend domain'lerine izin verilmeli.

#### Sorun 10: .env Dosyası Eksik
- `.env.example` yok
- Hangi environment variable'ların gerekli olduğu belirtilmemiş
- Hassas bilgiler (şifre, TOTP secret) kod içinde hardcoded olabilir

**Tespit Edilen Gerekli Env Variables:**
- `DOGA_LOGIN_URL`, `DOGA_USER`, `DOGA_PASS`, `DOGA_TOTP_SECRET`
- `KORU_LOGIN_URL`, `KORU_USER`, `KORU_PASS`, `KORU_TOTP_SECRET`
- `SOMPO_USER`, `SOMPO_PASS`, `SOMPO_TOTP_SECRET` (sompo_event.py'de hardcoded!)
- `ANADOLU_LOGIN_URL`, `ANADOLU_USER`, `ANADOLU_PASS`
- `HEADLESS` (true/false)
- `DATABASE_URL` (henüz kullanılmıyor)

### 2.3 🟢 DÜŞÜK - İyileştirme Önerileri

#### Sorun 11: Logging Tutarsızlığı
- Bazı dosyalarda `logging` kullanılıyor, bazılarında `print()`
- Log seviyeleri tutarsız

#### Sorun 12: Error Handling Eksik
- Scraper'larda try-except blokları var ama hata mesajları standart değil
- Backend'lerde hata yanıt formatları farklı

#### Sorun 13: Test Dosyaları Yok
- Unit test yok
- Integration test yok
- E2E test yok

#### Sorun 14: Dokümantasyon Eksik
- API dokümantasyonu yok (Swagger/OpenAPI var ama eksik)
- Çalıştırma talimatları yok
- Deployment guide yok

---

## 3. MİMARİ ÖNERİLER

### 3.1 Hedef Mimari

```
┌─────────────────────────────────────────────────────────┐
│                    FRONTEND (Next.js)                   │
│  - Teklif formu                                        │
│  - Sonuç gösterimi                                     │
│  - Admin panel                                         │
└────────────────────┬────────────────────────────────────┘
                     │ HTTP/REST
                     │
┌────────────────────▼────────────────────────────────────┐
│          UNIFIED BACKEND (FastAPI)                      │
│  - /api/v1/scrape/run                                   │
│  - /api/v1/offers                                       │
│  - /api/v1/health                                       │
│  - Authentication & Authorization                       │
└─────┬───────────────────────────────────────────────────┘
      │
      ├─────────────────┬─────────────────┬──────────────┐
      │                 │                 │              │
┌─────▼─────┐   ┌───────▼──────┐   ┌──────▼──────┐  ┌────▼─────┐
│  Scraper  │   │   Scraper    │   │  Scraper    │  │ Scraper │
│  Manager  │   │   Manager    │   │  Manager    │  │ Manager │
│ (Sompo)   │   │  (Koru)      │   │  (Doğa)     │  │ (Şeker) │
└───────────┘   └──────────────┘   └─────────────┘  └─────────┘
      │                 │                 │              │
      └─────────────────┴─────────────────┴──────────────┘
                        │
              ┌─────────▼─────────┐
              │   DATABASE        │
              │   (MySQL)         │
              │  - offers         │
              │  - users          │
              │  - logs           │
              └───────────────────┘
```

### 3.2 Standart Teklif Modeli

```python
class Offer(BaseModel):
    id: Optional[int] = None
    company: str  # "Sompo", "Koru", "Doğa", vb.
    branch: str   # "Trafik", "Kasko", "Sağlık"
    plate: str
    tckn: str
    price: float
    currency: str = "TRY"
    policy_no: Optional[str] = None
    valid_from: Optional[date] = None
    valid_to: Optional[date] = None
    raw_data: Optional[Dict[str, Any]] = None
    created_at: datetime
    status: str = "completed"  # "completed", "failed", "pending"
```

---

## 4. EKSİK DOSYALAR VE YAPILMASI GEREKENLER

### 4.1 Eksik Dosyalar

1. **`.env.example`** - Environment variable örnekleri
2. **`requirements.txt`** - Python bağımlılıkları
3. **`backend/main.py`** - Unified backend entry point
4. **`backend/models.py`** - SQLAlchemy modelleri
5. **`backend/database.py`** - DB connection ve session yönetimi
6. **`backend/schemas.py`** - Pydantic v2 şemaları
7. **`backend/scrapers/`** - Scraper manager'ları
8. **`backend/migrations/`** - Alembic migration dosyaları
9. **`docker-compose.yml`** - Development ortamı için
10. **`DEPLOYMENT.md`** - Deployment talimatları

### 4.2 Yapılması Gerekenler

1. ✅ Tüm backend'leri tek bir unified backend'e birleştir
2. ✅ SQLAlchemy ile veritabanı modelleri oluştur
3. ✅ Pydantic v2 migration yap
4. ✅ Standart scraper çıktı formatı belirle
5. ✅ Frontend'deki hardcoded IP'leri .env'e taşı
6. ✅ CORS ayarlarını güvenli hale getir
7. ✅ .env.example dosyası oluştur
8. ✅ requirements.txt oluştur
9. ✅ Dokümantasyon yaz
10. ✅ Çalıştırma talimatları hazırla

---

## 5. ÖNCELİK SIRASI

### Faz 1 - Kritik Düzeltmeler (Hemen)
1. JSONResponse import hatası düzelt
2. Port çakışması çöz
3. Hardcoded IP'leri .env'e taşı
4. .env.example oluştur

### Faz 2 - Mimari İyileştirmeler (Kısa Vadede)
1. Unified backend oluştur
2. Veritabanı entegrasyonu
3. Standart scraper çıktı formatı
4. Pydantic v2 migration

### Faz 3 - İyileştirmeler (Orta Vadede)
1. CORS güvenlik
2. Logging standardizasyonu
3. Error handling iyileştirme
4. Dokümantasyon

### Faz 4 - Ek Özellikler (Uzun Vadede)
1. Authentication/Authorization
2. Rate limiting
3. Caching
4. Monitoring & Alerting
5. Test coverage

---

## 6. SONUÇ VE ÖNERİLER

### Genel Durum
Proje **%60-70 tamamlanmış** durumda. Scraper'lar çalışıyor, frontend hazır, ancak backend entegrasyonu eksik ve dağınık.

### En Büyük Sorunlar
1. **Dağınık backend yapısı** - 7 ayrı backend dosyası
2. **Veritabanı yok** - Veriler kalıcı değil
3. **Standartlaştırma eksik** - Her şirket farklı format

### Önerilen Yaklaşım
1. Önce kritik hataları düzelt (JSONResponse, port çakışması)
2. Sonra unified backend oluştur
3. Veritabanı entegrasyonu yap
4. Frontend'i yeni backend'e bağla
5. Test et ve dokümante et

### Tahmini Süre
- **Faz 1 (Kritik Düzeltmeler):** 2-3 saat
- **Faz 2 (Mimari İyileştirmeler):** 1-2 gün
- **Faz 3 (İyileştirmeler):** 1 gün
- **Toplam:** 3-4 gün

---

**Rapor Hazırlayan:** AI Assistant  
**Son Güncelleme:** 2025-01-XX

