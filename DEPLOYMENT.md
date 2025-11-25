# 🚀 Sigorta Otomasyon Sistemi - Deployment Kılavuzu

## 📋 İçindekiler

1. [Lokal Geliştirme Ortamı](#lokal-geliştirme-ortamı)
2. [VDS Üzerinde Production Kurulumu](#vds-üzerinde-production-kurulumu)
3. [Veritabanı Kurulumu](#veritabanı-kurulumu)
4. [Backend Çalıştırma](#backend-çalıştırma)
5. [Frontend Çalıştırma](#frontend-çalıştırma)
6. [Sorun Giderme](#sorun-giderme)

---

## 🖥️ Lokal Geliştirme Ortamı

### Gereksinimler

- Python 3.10+ veya 3.11+
- Node.js 18+ ve npm
- MySQL/MariaDB 8.0+
- Git

### Adım 1: Projeyi İndirin

```bash
git clone <repository-url>
cd FinalPy
```

### Adım 2: Python Sanal Ortamı Oluşturun

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Linux/Mac
python3 -m venv venv
source venv/bin/activate
```

### Adım 3: Python Bağımlılıklarını Yükleyin

```bash
pip install -r requirements.txt
playwright install chromium
```

### Adım 4: Environment Variables Ayarlayın

```bash
# Backend için
cp ENV_SETUP.md .env
# .env dosyasını düzenleyin ve gerçek değerlerinizi girin

# Frontend için
cd "frontend2 newee/frontend"
cp .env.local.example .env.local
# .env.local dosyasını düzenleyin
```

### Adım 5: Veritabanını Oluşturun

```sql
CREATE DATABASE sigorta_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'sigorta_user'@'localhost' IDENTIFIED BY 'sigorta_pass';
GRANT ALL PRIVILEGES ON sigorta_db.* TO 'sigorta_user'@'localhost';
FLUSH PRIVILEGES;
```

### Adım 6: Backend'i Başlatın

```bash
# Proje kök dizininde
python -m backend.main
# veya
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

Backend şu adreste çalışacak: `http://localhost:8000`

API dokümantasyonu: `http://localhost:8000/docs`

### Adım 7: Frontend'i Başlatın

```bash
cd "frontend2 newee/frontend"
npm install
npm run dev
```

Frontend şu adreste çalışacak: `http://localhost:3000`

---

## 🌐 VDS Üzerinde Production Kurulumu

### Adım 1: VDS'e Bağlanın

```bash
ssh user@your-vds-ip
```

### Adım 2: Gerekli Yazılımları Kurun

```bash
# Ubuntu/Debian için
sudo apt update
sudo apt install -y python3 python3-pip python3-venv nodejs npm mysql-server git

# MySQL kurulumu
sudo mysql_secure_installation
```

### Adım 3: Projeyi VDS'e Yükleyin

```bash
# Git ile
git clone <repository-url>
cd FinalPy

# veya SCP ile
# Lokal bilgisayarınızdan:
scp -r FinalPy user@your-vds-ip:/home/user/
```

### Adım 4: Python Ortamını Kurun

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
playwright install chromium
```

### Adım 5: Veritabanını Kurun

```bash
sudo mysql -u root -p
```

```sql
CREATE DATABASE sigorta_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'sigorta_user'@'localhost' IDENTIFIED BY 'güçlü_şifre_buraya';
GRANT ALL PRIVILEGES ON sigorta_db.* TO 'sigorta_user'@'localhost';
FLUSH PRIVILEGES;
EXIT;
```

### Adım 6: Environment Variables Ayarlayın

```bash
nano .env
```

Production değerlerini girin:

```env
DATABASE_URL=mysql+pymysql://sigorta_user:güçlü_şifre_buraya@localhost:3306/sigorta_db
BACKEND_PORT=8000
HEADLESS=true
CORS_ORIGINS=https://app.loegs.com,https://www.loegs.com

# Sigorta şirketi bilgileri
SOMPO_USER=your_username
SOMPO_PASS=your_password
SOMPO_TOTP_SECRET=your_secret
# ... diğer şirketler
```

### Adım 7: Backend'i Systemd Service Olarak Kurun

```bash
sudo nano /etc/systemd/system/sigorta-backend.service
```

İçeriği:

```ini
[Unit]
Description=Sigorta Otomasyon Backend
After=network.target mysql.service

[Service]
Type=simple
User=your-user
WorkingDirectory=/home/your-user/FinalPy
Environment="PATH=/home/your-user/FinalPy/venv/bin"
ExecStart=/home/your-user/FinalPy/venv/bin/uvicorn backend.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Servisi başlatın:

```bash
sudo systemctl daemon-reload
sudo systemctl enable sigorta-backend
sudo systemctl start sigorta-backend
sudo systemctl status sigorta-backend
```

### Adım 8: Frontend'i Build Edin ve Çalıştırın

```bash
cd "frontend2 newee/frontend"
npm install
npm run build

# Production modunda çalıştır
npm start
# veya PM2 ile
pm2 start npm --name "sigorta-frontend" -- start
```

### Adım 9: Nginx Reverse Proxy (Opsiyonel)

```bash
sudo apt install nginx
sudo nano /etc/nginx/sites-available/sigorta
```

Nginx config:

```nginx
server {
    listen 80;
    server_name your-domain.com;

    # Backend
    location /api {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    # Frontend
    location / {
        proxy_pass http://localhost:3000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/sigorta /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

---

## 🗄️ Veritabanı Kurulumu

### Tabloları Oluşturma

Backend ilk çalıştırıldığında otomatik olarak tablolar oluşturulur. Manuel oluşturmak için:

```bash
python
```

```python
from backend.database import init_db
init_db()
```

### Migration (Gelecekte Alembic kullanılabilir)

Şu an için tablolar otomatik oluşturuluyor. Production'da Alembic kullanılması önerilir.

---

## 🔧 Backend Çalıştırma

### Development Modu

```bash
# Otomatik reload ile
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

### Production Modu

```bash
# Systemd service olarak (önerilen)
sudo systemctl start sigorta-backend

# veya manuel
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --workers 4
```

### Log Kontrolü

```bash
# Systemd log
sudo journalctl -u sigorta-backend -f

# Manuel log
tail -f logs/app.log
```

---

## 🎨 Frontend Çalıştırma

### Development Modu

```bash
cd "frontend2 newee/frontend"
npm run dev
```

### Production Build

```bash
npm run build
npm start
```

### PM2 ile (Önerilen)

```bash
pm2 start npm --name "sigorta-frontend" -- start
pm2 save
pm2 startup
```

---

## 🐛 Sorun Giderme

### Backend Başlamıyor

1. **Port kullanımda:**
   ```bash
   lsof -i :8000  # Linux/Mac
   netstat -ano | findstr :8000  # Windows
   ```

2. **Veritabanı bağlantı hatası:**
   - `.env` dosyasındaki `DATABASE_URL` kontrol edin
   - MySQL servisinin çalıştığından emin olun: `sudo systemctl status mysql`

3. **Playwright hatası:**
   ```bash
   playwright install chromium
   ```

### Frontend Backend'e Bağlanamıyor

1. **CORS hatası:**
   - Backend `.env` dosyasında `CORS_ORIGINS` kontrol edin
   - Frontend `.env.local` dosyasında `NEXT_PUBLIC_API_URL` kontrol edin

2. **Network hatası:**
   - Backend'in çalıştığından emin olun
   - Firewall ayarlarını kontrol edin

### Scraper Çalışmıyor

1. **Login hatası:**
   - `.env` dosyasındaki kullanıcı adı/şifre/TOTP secret kontrol edin
   - Sigorta şirketi web sitesine manuel giriş yapılabildiğini kontrol edin

2. **Timeout hatası:**
   - VDS'in IP'sinin sigorta şirketleri tarafından izin verildiğinden emin olun
   - `HEADLESS=true` ile çalıştırmayı deneyin

---

## 📞 Destek

Sorun yaşarsanız:
1. Log dosyalarını kontrol edin
2. `PROJE_ANALIZ_RAPORU.md` dosyasını inceleyin
3. GitHub Issues'a sorun bildirin

---

**Son Güncelleme:** 2025-01-XX

