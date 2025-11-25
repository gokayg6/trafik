# TEST İÇİN SADECE SOMPO AKTİF

## Yapılan Değişiklikler

### Backend (`backend/main.py`)
- `SCRAPER_FUNCTIONS` dictionary'sinde sadece Sompo aktif
- Varsayılan şirket ayarları sadece Sompo için oluşturuluyor

### Frontend
- `dashboard.tsx`: Sadece Sompo şirketi gösteriliyor
- `admin/companies.tsx`: Sadece Sompo şirketi gösteriliyor

## Test Etme

1. Backend'i başlat:
```bash
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

2. Frontend'i başlat:
```bash
cd frontend/frontend
npm run dev
```

3. Tarayıcıda aç:
- Dashboard: Sadece Sompo şirketi görünmeli
- Admin/Companies: Sadece Sompo şirketi görünmeli
- Teklif alma: Sadece Sompo'dan teklif alınmalı

## Geri Alma

Değişiklikleri geri almak için:
1. `backend/main.py` - `SCRAPER_FUNCTIONS` dictionary'sine diğer şirketleri ekle
2. `frontend/frontend/src/pages/dashboard.tsx` - Filtreleme satırını kaldır
3. `frontend/frontend/src/pages/admin/companies.tsx` - Filtreleme satırını kaldır
4. `backend/main.py` - `get_company_settings` fonksiyonunda tüm şirketleri ekle

