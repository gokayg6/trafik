"""
Script to translate common Turkish phrases in scraper files to English
This helps prevent charmap encoding errors on Windows
"""

import re
import os

# Common Turkish to English translations
TRANSLATIONS = {
    # Print messages
    "Üretilen TOTP Kodu": "Generated TOTP Code",
    "TOTP kodu üretilemedi": "Failed to generate TOTP code",
    "klasörü oluşturuldu": "folder created",
    "Oturum durumu başarıyla": "Session state successfully",
    "dosyasına kaydedildi": "saved to file",
    "Oturum durumu kaydı başarısız oldu": "Failed to save session state",
    "Hata ekran görüntüsü alındı": "Error screenshot taken",
    "Sayfa yenileniyor": "Reloading page",
    "Sayfa yenileme başarısız": "Failed to reload page",
    "Tam giriş işlemi başlatılıyor": "Starting full login process",
    "Kullanıcı adı ve şifre girildi": "Username and password entered",
    "Giriş butonuna tıklandı": "Login button clicked",
    "formun TOTP moduna geçmesi bekleniyor": "waiting for form to switch to TOTP mode",
    "TOTP giriş moduna geçti": "switched to TOTP login mode",
    "TOTP Kodu": "TOTP Code",
    "şifre alanına giriliyor": "is being entered into password field",
    "Tam giriş başarılı": "Full login successful",
    "Bilgilendirme pop-up'ı kontrol ediliyor": "Checking for information popup",
    "Bilgilendirme pop-up'ı bulundu ve kapatıldı": "Information popup found and closed",
    "Bilgilendirme pop-up'ı bulunamadı": "Information popup not found",
    "devam ediliyor": "continuing",
    "Kasko Sigortası teklifi oluşturma işlemi başlatıldı": "Kasko insurance quote creation process started",
    "Ana sayfaya dönülüyor": "Returning to home page",
    "menü öğesine tıklanıyor": "menu item being clicked",
    "menüsü açıldı": "menu opened",
    "alt menü öğesine tıklanıyor": "submenu item being clicked",
    "Yeni sekme açıldı": "New tab opened",
    "ona geçiliyor": "switching to it",
    "Yeni sekmede açılan sayfa yükleniyor": "Page in new tab is loading",
    "Yeni sekme başarıyla yüklendi": "New tab successfully loaded",
    "Hata pop-up'ı kontrol ediliyor": "Checking for error popup",
    "hatası pop-up'ı bulundu": "error popup found",
    "Hata pop-up'ı 'Tamam' butonu ile kapatıldı": "Error popup closed with OK button",
    "Hata pop-up'ı bulunamadı": "Error popup not found",
    "Kullanıcı adı ve şifre ile giriş yapılıyor": "Logging in with username and password",
    "Kullanıcı adı girildi": "Username entered",
    "Şifre girildi": "Password entered",
    "Giriş butonu bulundu": "Login button found",
    "Giriş butonuna tıklandı": "Login button clicked",
    "Giriş butonu bulunamadı": "Login button not found",
    "Enter tuşu deneniyor": "trying Enter key",
    "Giriş işlemi tamamlandı": "Login process completed",
    "sayfa yüklenmesi bekleniyor": "waiting for page to load",
    "Google Authenticator pop-up'ı kontrol ediliyor": "Checking for Google Authenticator popup",
    "Google Authenticator pop-up'ı bulundu": "Google Authenticator popup found",
    "TOTP kodu girildi": "TOTP code entered",
    "Google Authenticator giriş butonuna tıklandı": "Google Authenticator login button clicked",
    "Google Authenticator pop-up'ı kapandı": "Google Authenticator popup closed",
    "Google Authenticator pop-up'ı bulunamadı": "Google Authenticator popup not found",
    "Son sayfa yüklenmesi bekleniyor": "Waiting for final page to load",
    "Son URL": "Final URL",
    "Tüm giriş işlemleri tamamlandı": "All login processes completed",
    "menüsüne ulaşılıyor": "accessing menu",
    "Arama kutusuna": "To search box",
    "yazıldı": "written",
    "menü filtreleniyor": "menu being filtered",
    "menüsü bekleniyor": "menu being waited for",
    "menüsüne tıklandı": "menu clicked",
    "linki bekleniyor": "link being waited for",
    "linkine tıklandı": "link clicked",
    "form sayfasının yüklenmesi bekleniyor": "waiting for form page to load",
    "formu URL": "form URL",
    "formuna ulaşıldı": "reached form",
    "Iframe'e geçiş yapılıyor": "Switching to iframe",
    "Iframe bulundu": "Iframe found",
    "Iframe'e geçiş yapıldı": "Switched to iframe",
    "formu dolduruluyor": "form being filled",
    "TC Kimlik No giriliyor": "TC Identity Number being entered",
    "TC Kimlik No girildi": "TC Identity Number entered",
    "Plaka giriliyor": "Plate being entered",
    "Plaka girildi": "Plate entered",
    "formu başarıyla dolduruldu": "form successfully filled",
    "Sorgula butonuna tıklanıyor": "Query button being clicked",
    "Sorgula butonuna tıklandı": "Query button clicked",
    "Müşteri aranıyor": "Searching for customer",
    "Müşteri arama trigger'ına tıklandı": "Customer search trigger clicked",
    "Ara butonuna tıklandı": "Search button clicked",
    "Müşteri tablosu kontrol ediliyor": "Checking customer table",
    "müşteri bulundu": "customers found",
    "İlk müşteri seçildi": "First customer selected",
    "Müşteri": "Customer",
    "Kod": "Code",
    "Müşteri bilgileri alınamadı": "Failed to get customer information",
    "Seç butonuna tıklandı": "Select button clicked",
    "Sonraki adım butonuna tıklanıyor": "Next step button being clicked",
    "Sonraki adım butonuna tıklandı": "Next step button clicked",
    "İkinci Sonraki adım butonuna tıklanıyor": "Second Next step button being clicked",
    "İkinci Sonraki adım butonuna tıklandı": "Second Next step button clicked",
    "Teklif sonuçları tablosu kontrol ediliyor": "Checking quote results table",
    "Doğru teklif tablosu bulundu": "Correct quote table found",
    "teklif satırı bulundu": "quote rows found",
    "Kasko teklif sonuçları başarıyla çekildi": "Kasko quote results successfully retrieved",
    "Kasko teklifi oluşturulurken bir hata oluştu": "An error occurred while creating Kasko quote",
    "Tamamlayıcı Sağlık Sigortası teklifi oluşturma işlemi başlatıldı": "Complementary Health Insurance quote creation process started",
    "linkine tıklanıyor": "link being clicked",
    "Yeni sayfanın yüklenmesi bekleniyor": "Waiting for new page to load",
    "iFrame bulunuyor": "Looking for iframe",
    "iFrame bulundu": "Iframe found",
    "içerik yükleniyor": "content loading",
    "TC Kimlik yazıldı": "TC Identity written",
    "E-posta girildi": "Email entered",
    "Şartlar checkbox'ının etiketine tıklanıyor": "Clicking on terms checkbox label",
    "Şartlar checkbox'ı etiket üzerinden başarıyla işaretlendi": "Terms checkbox successfully checked via label",
    "DEVAM butonunun aktif olması bekleniyor": "Waiting for CONTINUE button to become active",
    "Aktif DEVAM butonuna tıklandı": "Active CONTINUE button clicked",
    "Teklif sonuçları tablosunun yüklenmesi bekleniyor": "Waiting for quote results table to load",
    "Bu işlem uzun sürebilir": "This process may take a long time",
    "Teklif sonuç tablosu başarıyla yüklendi": "Quote results table successfully loaded",
    "Tablodaki veriler çekiliyor": "Retrieving data from table",
    "Veri çekme işlemi tamamlandı": "Data retrieval process completed",
    "İşlem zaman aşımına uğradı": "Process timed out",
    "Tablo yüklenmedi veya bir selector hatalı": "Table did not load or a selector is incorrect",
    "Tamamlayıcı Sağlık teklifi oluşturulurken bir hata oluştu": "An error occurred while creating Complementary Health quote",
    "Trafik Sigortası teklifi oluşturma işlemi başlatıldı": "Traffic Insurance quote creation process started",
    "Trafik formu dolduruluyor": "Traffic form being filled",
    "Trafik formu başarıyla dolduruldu": "Traffic form successfully filled",
    "Trafik teklif süreci tamamlandı": "Traffic quote process completed",
    "Trafik teklif alınırken hata": "Error while getting Traffic quote",
    "Trafik - Plaka bilgisi giriliyorum": "Traffic - Entering plate information",
    "Trafik - Plaka İl Kodu girildi": "Traffic - Plate City Code entered",
    "Trafik - Plaka İl Kodu alanı bulunamadı": "Traffic - Plate City Code field not found",
    "Trafik - Plaka No girildi": "Traffic - Plate Number entered",
    "Trafik - Plaka No alanı bulunamadı": "Traffic - Plate Number field not found",
    "Trafik elementi bulunamadı": "Traffic element not found",
    "Selector'ı kontrol edin": "Check the selector",
}

def translate_file(filepath):
    """Translate Turkish text in a file to English"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        original_content = content
        
        # Replace Turkish phrases
        for turkish, english in TRANSLATIONS.items():
            content = content.replace(turkish, english)
        
        # Only write if changes were made
        if content != original_content:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"Translated: {filepath}")
            return True
        else:
            print(f"No changes needed: {filepath}")
            return False
    except Exception as e:
        print(f"Error processing {filepath}: {e}")
        return False

if __name__ == "__main__":
    scraper_dir = "scrapers_event"
    files_to_translate = [
        "referans_event.py",
        "sompo_event.py",
        "anadolu_scraper.py",
        "doga_scraper.py",
        "seker_scraper.py",
        "koru_scraper.py",
        "atlas_scraper.py"
    ]
    
    for filename in files_to_translate:
        filepath = os.path.join(scraper_dir, filename)
        if os.path.exists(filepath):
            translate_file(filepath)
        else:
            print(f"File not found: {filepath}")

