# 🔐 Environment Variables Kurulum Kılavuzu

## Hızlı Başlangıç

### 1. Backend için .env Dosyası

Proje kök dizininde `.env` dosyası oluşturun:

```bash
# Windows PowerShell
Copy-Item .env.example .env

# Linux/Mac
cp .env.example .env
```

Ardından `.env` dosyasını düzenleyip gerçek değerlerinizi girin.

### 2. Frontend için .env.local Dosyası

Frontend klasöründe `.env.local` dosyası oluşturun:

```bash
cd "frontend2 newee/frontend"
Copy-Item .env.local.example .env.local  # Windows
# veya
cp .env.local.example .env.local  # Linux/Mac
```

## Gerekli Environment Variables

### Backend (.env)

#### Zorunlu Değişkenler:

```env
# Veritabanı
DATABASE_URL=mysql+pymysql://user:password@localhost:3306/sigorta_db

# Sigorta Şirketi Bilgileri (kullanılan şirketler için)
SOMPO_USER=BULUT1
SOMPO_PASS=EE28sigorta.
SOMPO_TOTP_SECRET=DD3JCJB7E7H25MB6BZ5IKXLKLJBZDQAO
SOMPO_LOGIN_URL=https://ejento.somposigorta.com.tr/dashboard/login

# Anadolu Sigorta
ANADOLU_USER=your_anadolu_username
ANADOLU_PASS=Amasya446
ANADOLU_TOTP_SECRET=LNPTT4LB6AI7TCKBQSFF2PPQ5U22JYB3
ANADOLU_LOGIN_URL=https://your-anadolu-login-url.com

# Referans Sigorta
REFERANS_USER=SAMA0328011
REFERANS_PASS=EEsigorta28.
REFERANS_TOTP_SECRET=your_referans_totp_secret

# Diğer şirketler için benzer şekilde:
# DOGA_USER, DOGA_PASS, DOGA_TOTP_SECRET, DOGA_LOGIN_URL
# KORU_USER, KORU_PASS, KORU_TOTP_SECRET, KORU_LOGIN_URL
# vb.
```

#### Opsiyonel Değişkenler:

```env
# Backend Port
BACKEND_PORT=8000

# Playwright Headless Modu
HEADLESS=false

# CORS Origins
CORS_ORIGINS=http://localhost:3000,https://app.loegs.com
```

### Frontend (.env.local)

```env
# Backend API URL
NEXT_PUBLIC_API_URL=http://localhost:8000

# Production için:
# NEXT_PUBLIC_API_URL=http://212.68.34.202:8000
```

## Güvenlik Notları

⚠️ **ÖNEMLİ:**
- `.env` ve `.env.local` dosyalarını **ASLA** Git'e commit etmeyin
- Bu dosyalar `.gitignore` içinde olmalı
- Production'da farklı bir `.env` dosyası kullanın
- TOTP secret'ları ve şifreleri güvenli bir şekilde saklayın

## VDS Üzerinde Kurulum

VDS sunucunuzda:

1. `.env` dosyasını oluşturun
2. Production değerlerini girin
3. Frontend için `.env.local` oluşturun ve production API URL'ini ayarlayın

```env
# VDS Backend .env
DATABASE_URL=mysql+pymysql://prod_user:prod_pass@localhost:3306/sigorta_db
NEXT_PUBLIC_API_URL=http://YOUR_VDS_IP:8000
HEADLESS=true
```

