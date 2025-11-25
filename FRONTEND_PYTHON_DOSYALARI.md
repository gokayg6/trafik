# 📁 Frontend'deki Python Dosyaları Analizi

## Konum
`frontend2 newee/frontend/quick/` klasörü

## Dosyalar

### 1. `app.py` - Flask Test Server
- **Amaç:** Eski test/development server
- **Durum:** Production'da kullanılmıyor
- **Öneri:** Arşivlenebilir veya silinebilir

### 2. `google_auth.py`
- **Amaç:** Google Authenticator test dosyası
- **Durum:** Production'da kullanılmıyor
- **Öneri:** Arşivlenebilir

### 3. `quick/sompo/` Klasörü
- `sompo_login.py` - Eski Sompo login test dosyası
- `yeni.py` - Test dosyası
- `sompo_cookies.json` - Test cookie dosyası
- **Durum:** Production'da kullanılmıyor
- **Öneri:** Arşivlenebilir

### 4. `quick/quickSigorta/` Klasörü
- `quicksigortaTrafik.py`
- `quicksigortaKasko.py`
- `quicksigortaSaglik.py`
- `quicksigortaSeyahatSaglik.py`
- `get_cookie.py`
- **Durum:** Eski Quick Sigorta test dosyaları
- **Öneri:** Arşivlenebilir

### 5. `sigortafrontend.html`
- **Amaç:** Eski HTML frontend (Next.js öncesi)
- **Durum:** Kullanılmıyor
- **Öneri:** Arşivlenebilir

## Öneri

Bu dosyalar production'da kullanılmıyor ve sadece test/development amaçlı. İki seçenek:

### Seçenek 1: Arşivle (Önerilen)
```bash
mkdir archive
mv "frontend2 newee/frontend/quick" archive/
```

### Seçenek 2: Sil
Eğer kesinlikle gerekmiyorsa:
```bash
rm -rf "frontend2 newee/frontend/quick"
```

## Not

Bu dosyalar frontend'in çalışmasını etkilemiyor. Next.js frontend'i (`src/` klasörü) bu dosyalardan bağımsız çalışıyor.

---

**Son Güncelleme:** 2025-01-XX

