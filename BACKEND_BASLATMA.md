# 🚀 Backend Başlatma Kılavuzu

## Hızlı Başlangıç

### 1. Backend'in Çalıştığından Emin Olun

Backend çalışmıyorsa, frontend "fetch failed" hatası verir.

**Backend'i başlatmak için:**

```bash
# Proje kök dizininde
cd FinalPy

# Python sanal ortamını aktifleştir
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# Backend'i başlat
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

Backend başarıyla başladığında şu mesajı göreceksiniz:
```
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
INFO:     Started reloader process
INFO:     Started server process
INFO:     Waiting for application startup.
INFO:     🚀 Sigorta Otomasyon API başlatılıyor...
INFO:     ✅ Veritabanı bağlantısı başarılı
INFO:     ✅ API hazır
INFO:     Application startup complete.
```

### 2. Backend'in Çalıştığını Test Edin

Tarayıcıda şu adresi açın:
```
http://localhost:8000/docs
```

Swagger UI açılırsa backend çalışıyor demektir.

Veya terminal'de:
```bash
curl http://localhost:8000/health
```

Yanıt:
```json
{
  "status": "healthy",
  "database": "connected",
  "timestamp": "2025-01-XX..."
}
```

### 3. Frontend'i Başlatın

**Yeni terminal penceresi açın:**

```bash
cd "frontend2 newee/frontend"
npm run dev
```

Frontend şu adreste çalışacak: `http://localhost:3000`

### 4. Environment Variables Kontrolü

**Backend için `.env` dosyası:**
```env
DATABASE_URL=mysql+pymysql://user:password@localhost:3306/sigorta_db
BACKEND_PORT=8000
HEADLESS=false
CORS_ORIGINS=http://localhost:3000
```

**Frontend için `.env.local` dosyası:**
```env
NEXT_PUBLIC_API_URL=http://localhost:8000
```

## Sorun Giderme

### ❌ "fetch failed" Hatası

**Neden:**
- Backend çalışmıyor
- Backend farklı port'ta çalışıyor
- CORS hatası

**Çözüm:**
1. Backend'in çalıştığından emin olun (yukarıdaki adımları takip edin)
2. Port kontrolü:
   ```bash
   # Windows
   netstat -ano | findstr :8000
   
   # Linux/Mac
   lsof -i :8000
   ```
3. `.env.local` dosyasında `NEXT_PUBLIC_API_URL` doğru mu kontrol edin

### ❌ "Database connection error"

**Neden:**
- MySQL çalışmıyor
- `.env` dosyasındaki `DATABASE_URL` yanlış
- Veritabanı oluşturulmamış

**Çözüm:**
1. MySQL servisini başlatın:
   ```bash
   # Windows (Services)
   # MySQL servisini başlat
   
   # Linux
   sudo systemctl start mysql
   ```

2. Veritabanını oluşturun:
   ```sql
   CREATE DATABASE sigorta_db;
   ```

3. `.env` dosyasındaki `DATABASE_URL` kontrol edin

### ❌ "CORS error"

**Neden:**
- Backend'deki `CORS_ORIGINS` frontend URL'ini içermiyor

**Çözüm:**
Backend `.env` dosyasında:
```env
CORS_ORIGINS=http://localhost:3000,http://localhost:3001
```

## Production (VDS) İçin

VDS'te backend'i systemd service olarak çalıştırın:

```bash
sudo systemctl start sigorta-backend
sudo systemctl status sigorta-backend
```

Detaylı bilgi için [DEPLOYMENT.md](DEPLOYMENT.md) dosyasına bakın.

---

**Önemli:** Backend çalışmadan frontend çalışmaz! Her zaman önce backend'i başlatın.

