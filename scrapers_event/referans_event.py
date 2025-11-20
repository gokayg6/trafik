# -*- coding: utf-8 -*-
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
import pyotp
import time
import sys
import json 
import os 

# --- AYARLAR ---
COOKIE_DIR = "cookies"
STORAGE_STATE_FILE_PATH = os.path.join(COOKIE_DIR, "atlas_storage_state.json")

# GİRİŞ BİLGİLERİ 
YOUR_USERNAME = "SAMA0328011"
YOUR_PASSWORD = "EEsigorta28."

# 2FA (TOTP) BİLGİLERİ
SECRET_KEY = "GI4TCNJYL5KEERSMII"

LOGIN_URL = "https://portal.referanssigorta.net/sign-in"
DASHBOARD_URL = "https://portal.referanssigorta.net/" 

# Stealth modunda kullanılan userAgent
STEALTH_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

def generate_totp_code(secret_key):
    """Verilen secret key ile güncel TOTP kodunu üretir."""
    try:
        totp = pyotp.TOTP(secret_key)
        current_code = totp.now()
        print(f"[BİLGİ] Üretilen TOTP Kodu: {current_code}")
        return current_code
    except Exception as e:
        print(f"[HATA] TOTP kodu üretilemedi: {e}", file=sys.stderr)
        return None

def save_storage_state(context):
    """
    Oturum durumunu (çerezler ve depolama) JSON dosyasına kaydeder.
    Klasör yoksa oluşturur.
    """
    try:
        if not os.path.exists(COOKIE_DIR):
            os.makedirs(COOKIE_DIR)
            print(f"[BİLGİ] '{COOKIE_DIR}' klasörü oluşturuldu.")
            
        context.storage_state(path=STORAGE_STATE_FILE_PATH)
        print(f"\n[BİLGİ] Oturum durumu başarıyla '{STORAGE_STATE_FILE_PATH}' dosyasına kaydedildi.")
    except Exception as e:
        print(f"\n[HATA] Oturum durumu kaydı başarısız oldu: {e}", file=sys.stderr)

def hata_handler(page, hata_mesaji, fonksiyon_adi):
    """Hata durumunda sayfayı yenileyip ekran görüntüsü alır."""
    print(f"\n[HATA] {fonksiyon_adi} - {hata_mesaji}", file=sys.stderr)
    try:
        page.screenshot(path=f'hata_{fonksiyon_adi}_{int(time.time())}.png')
        print(f"[BİLGİ] Hata ekran görüntüsü alındı: hata_{fonksiyon_adi}_{int(time.time())}.png")
    except:
        pass
    print("[BİLGİ] Sayfa yenileniyor...")
    try:
        page.reload()
        time.sleep(3)
    except Exception as e:
        print(f"[UYARI] Sayfa yenileme başarısız: {e}")

def full_login(page):
    """Kullanıcı adı, şifre ve TOTP ile tam giriş işlemini yapar."""
    print("\n[BİLGİ] Tam giriş işlemi başlatılıyor (kullanıcı adı/şifre)...")
    
    page.goto(LOGIN_URL, wait_until="domcontentloaded")
    
    username_selector = '#login-username'
    password_selector = '#login-password'
    submit_button_selector = '#login-submit'

    page.locator(username_selector).fill(YOUR_USERNAME)
    page.locator(password_selector).fill(YOUR_PASSWORD)
    print("Kullanıcı adı ve şifre girildi.")
    
    page.locator(submit_button_selector).click()
    print("Giriş butonuna tıklandı, formun TOTP moduna geçmesi bekleniyor...")

    page.locator(username_selector).wait_for(state="hidden", timeout=15000)
    print("Form, TOTP giriş moduna geçti.")

    totp_code = generate_totp_code(SECRET_KEY)
    if not totp_code:
        raise Exception("TOTP kodu üretilemedi.")

    print(f"TOTP Kodu ({totp_code}) şifre alanına giriliyor...")
    page.locator(password_selector).fill(totp_code)

    page.locator(submit_button_selector).click()
    print("Giriş butonuna TOTP kodunu göndermek için tekrar tıklandı.")

    page.wait_for_url(lambda url: "sign-in" not in url, timeout=20000)
    print("Tam giriş başarılı!")

def handle_popup_if_exists(page):
    """
    Giriş sonrası çıkabilecek bilgilendirme pop-up'ını kontrol eder ve varsa kapatır.
    """
    print("\n[BİLGİ] Bilgilendirme pop-up'ı kontrol ediliyor...")
    
    popup_button_selector = '#first-open-ok'
    
    try:
        page.locator(popup_button_selector).wait_for(state='visible', timeout=5000)
        page.locator(popup_button_selector).click()
        print("[BİLGİ] Bilgilendirme pop-up'ı bulundu ve kapatıldı.")
        
    except PlaywrightTimeoutError:
        print("[BİLGİ] Bilgilendirme pop-up'ı bulunamadı, devam ediliyor.")

def create_kasko_teklifi(page, teklif_data):
    """
    Verilen bilgilerle Kasko Sigortası teklifi oluşturur.
    Yeni Teklif > Diğer menüsünü kullanır. Hata durumunda sayfayı yenileyip devam eder.
    """
    try:
        print("\n[BİLGİ] Kasko Sigortası teklifi oluşturma işlemi başlatıldı...")
        
        # --- 1. ADIM: ANA SAYFAYA DÖN ---
        print("[BİLGİ] Ana sayfaya dönülüyor...")
        page.goto("https://portal.referanssigorta.net/", wait_until="domcontentloaded")
        page.wait_for_load_state('networkidle', timeout=30000)
        time.sleep(5)

        handle_popup_if_exists(page)
        
        # --- 2. ADIM: "YENİ TEKLİF" MENÜSÜNE TIKLA ---
        print("[BİLGİ] 'Yeni Teklif' menü öğesine tıklanıyor...")
        yeni_teklif_selector = 'a[href="javascript:;"] span.menu-item-text:has-text("Yeni Teklif")'
        page.locator(yeni_teklif_selector).click()
        print("[BİLGİ] 'Yeni Teklif' menüsü açıldı.")
        time.sleep(2)
        
        # --- 3. ADIM: "DİĞER" ALT MENÜSÜNE TIKLA ---
        print("[BİLGİ] 'Diğer' alt menü öğesine tıklanıyor...")
        diger_selector = 'li a[target="_blank"] span.menu-item-text:has-text("Diğer")'
        
        with page.context.expect_page() as new_page_info:
            page.locator(diger_selector).click()
        
        new_page = new_page_info.value
        print("[BİLGİ] Yeni sekme açıldı, ona geçiliyor...")
        page = new_page
        
        print("[BİLGİ] Yeni sekmede açılan sayfa yükleniyor...")
        page.wait_for_load_state('networkidle', timeout=30000)
        print(f"[BİLGİ] Yeni sekme başarıyla yüklendi: {page.url}")
        time.sleep(5)

        # --- 4. ADIM: HATA POP-UP'INI KONTROL ET VE KAPAT ---
        print("\n[BİLGİ] Hata pop-up'ı kontrol ediliyor...")
        try:
            popup_selector = '.x-window:has-text("Hata")'
            page.locator(popup_selector).wait_for(state='visible', timeout=10000)
            print("[BİLGİ] 'İkili kimlik doğrulama' hatası pop-up'ı bulundu.")
            tamam_btn_selector = '#ext-gen124'
            page.locator(tamam_btn_selector).click()
            print("[BİLGİ] Hata pop-up'ı 'Tamam' butonu ile kapatıldı.")
            time.sleep(3)
        except PlaywrightTimeoutError:
            print("[BİLGİ] Hata pop-up'ı bulunamadı, devam ediliyor...")

        # --- 5. ADIM: KULLANICI ADI VE ŞİFRE İLE GİRİŞ YAP ---
        print("\n[BİLGİ] Kullanıcı adı ve şifre ile giriş yapılıyor...")
        
        username_selector = '#txtUsername'
        try:
            username_field = page.locator(username_selector)
            username_field.wait_for(state='visible', timeout=15000)
            username_field.fill(YOUR_USERNAME)
            print(f"[BİLGİ] Kullanıcı adı girildi: {YOUR_USERNAME}")
            time.sleep(1)
        except Exception as e:
            hata_handler(page, str(e), "kasko_username")
            raise

        password_selector = '#txtPassword'
        try:
            password_field = page.locator(password_selector)
            password_field.wait_for(state='visible', timeout=15000)
            password_field.fill(YOUR_PASSWORD)
            print("[BİLGİ] Şifre girildi.")
            time.sleep(1)
        except Exception as e:
            hata_handler(page, str(e), "kasko_password")
            raise

        login_btn_selectors = [
            'button:has-text("Giriş")',
            'input[type="submit"]',
            '.x-btn:has-text("Giriş")',
            'button.x-btn-text',
            'input[value="Giriş"]'
        ]
        
        login_successful = False
        for selector in login_btn_selectors:
            if page.locator(selector).count() > 0:
                print(f"[BİLGİ] Giriş butonu bulundu: {selector}")
                page.locator(selector).first.click()
                print("[BİLGİ] Giriş butonuna tıklandı.")
                login_successful = True
                break
        
        if not login_successful:
            print("[UYARI] Giriş butonu bulunamadı, Enter tuşu deneniyor...")
            page.keyboard.press('Enter')

        print("[BİLGİ] Giriş işlemi tamamlandı, sayfa yüklenmesi bekleniyor...")
        page.wait_for_load_state('networkidle', timeout=30000)
        time.sleep(5)

        # --- 6. ADIM: GOOGLE AUTHENTICATOR KODUNU GİR ---
        print("\n[BİLGİ] Google Authenticator pop-up'ı kontrol ediliyor...")
        try:
            ga_popup_selector = '#winGAC'
            page.locator(ga_popup_selector).wait_for(state='visible', timeout=15000)
            print("[BİLGİ] Google Authenticator pop-up'ı bulundu.")
            
            totp_code = generate_totp_code(SECRET_KEY)
            if not totp_code:
                raise Exception("TOTP kodu üretilemedi.")
            
            ga_code_selector = '#txtGAKod'
            page.locator(ga_code_selector).wait_for(state='visible', timeout=10000)
            page.locator(ga_code_selector).fill(totp_code)
            print(f"[BİLGİ] TOTP kodu girildi: {totp_code}")
            time.sleep(1)
            
            ga_login_selector = '#btnValidateTwoFactor'
            page.locator(ga_login_selector).click()
            print("[BİLGİ] Google Authenticator giriş butonuna tıklandı.")
            
            page.locator(ga_popup_selector).wait_for(state='hidden', timeout=15000)
            print("[BİLGİ] Google Authenticator pop-up'ı kapandı.")
        except PlaywrightTimeoutError:
            print("[BİLGİ] Google Authenticator pop-up'ı bulunamadı, devam ediliyor...")
        
        print("[BİLGİ] Son sayfa yüklenmesi bekleniyor...")
        page.wait_for_load_state('networkidle', timeout=30000)
        time.sleep(5)
        
        print(f"[BİLGİ] Son URL: {page.url}")
        print("[BAŞARILI] Tüm giriş işlemleri tamamlandı!")

        # --- 7. ADIM: KASKO MENÜSÜNE ULAŞ ---
        print("\n[BİLGİ] Kasko menüsüne ulaşılıyor...")
        
        try:
            print("[BİLGİ] Arama kutosuna 'kasko' yazılıyor...")
            search_input_selector = '#TriggerField1'
            page.locator(search_input_selector).wait_for(state='visible', timeout=15000)
            page.locator(search_input_selector).fill('kasko')
            print("[BİLGİ] 'kasko' yazıldı, menü filtreleniyor...")
            time.sleep(3)
        except Exception as e:
            hata_handler(page, str(e), "kasko_search")
            raise

        try:
            print("[BİLGİ] 'Poliçe' menüsü bekleniyor...")
            police_selector = 'a.x-tree-node-anchor:has-text("Poliçe")'
            page.locator(police_selector).wait_for(state='visible', timeout=10000)
            page.locator(police_selector).click()
            print("[BİLGİ] 'Poliçe' menüsüne tıklandı.")
            time.sleep(3)
        except Exception as e:
            hata_handler(page, str(e), "kasko_police")
            raise
        
        try:
            print("[BİLGİ] 'Kasko' menüsü bekleniyor...")
            kasko_selector = 'span:has-text("Kasko")'
            page.locator(kasko_selector).wait_for(state='visible', timeout=10000)
            page.locator(kasko_selector).click()
            print("[BİLGİ] 'Kasko' menüsüne tıklandı.")
            time.sleep(3)
        except Exception as e:
            hata_handler(page, str(e), "kasko_menu")
            raise
        
        try:
            print("[BİLGİ] 'Referans Kasko (MD2)' linki bekleniyor...")
            referans_kasko_selector = 'a.x-tree-node-anchor[href*="/NonLife/Policy/SavePolicy.aspx?APP_MP=MD2"]:has-text("Referans Kasko (MD2)")'
            page.locator(referans_kasko_selector).wait_for(state='visible', timeout=10000)
            page.locator(referans_kasko_selector).click()
            print("[BİLGİ] 'Referans Kasko (MD2)' linkine tıklandı.")
        except Exception as e:
            hata_handler(page, str(e), "kasko_referans")
            raise
        
        print("[BİLGİ] Kasko form sayfasının yüklenmesi bekleniyor...")
        page.wait_for_load_state('networkidle', timeout=30000)
        time.sleep(5)
        print(f"[BİLGİ] Kasko formu URL: {page.url}")
        print("[BAŞARILI] Kasko formuna ulaşıldı!")

        # --- 8. ADIM: IFRAME'E GEÇİŞ YAP ---
        print("\n[BİLGİ] Iframe'e geçiş yapılıyor...")
        
        try:
            iframe_selector = '#frmMain'
            page.locator(iframe_selector).wait_for(state='visible', timeout=15000)
            print("[BİLGİ] Iframe bulundu.")
        except Exception as e:
            hata_handler(page, str(e), "kasko_iframe")
            raise
        
        frame = page.frame_locator(iframe_selector)
        print("[BİLGİ] Iframe'e geçiş yapıldı.")
        time.sleep(3)

        # --- 9. ADIM: KASKO FORMUNU DOLDUR ---
        print("\n[BİLGİ] Kasko formu dolduruluyor...")
        
        try:
            print(f"[BİLGİ] TC Kimlik No giriliyor: {teklif_data['tc_kimlik']}")
            tc_selector = '#txtGIFTIdentityNo'
            frame.locator(tc_selector).wait_for(state='visible', timeout=15000)
            frame.locator(tc_selector).fill(teklif_data['tc_kimlik'])
            print(f"[BİLGİ] TC Kimlik No girildi: {teklif_data['tc_kimlik']}")
            time.sleep(2)
        except Exception as e:
            hata_handler(page, str(e), "kasko_tc")
            raise
        
        try:
            print(f"[BİLGİ] Plaka giriliyor: {teklif_data['plaka']}")
            plaka_selector = '#txtGIFTPlate'
            frame.locator(plaka_selector).fill(teklif_data['plaka'])
            print(f"[BİLGİ] Plaka girildi: {teklif_data['plaka']}")
            time.sleep(2)
        except Exception as e:
            hata_handler(page, str(e), "kasko_plaka")
            raise

        print("[BAŞARILI] Kasko formu başarıyla dolduruldu!")

        # --- 10. ADIM: SORGULA BUTONUNA TIKLA ---
        print("\n[BİLGİ] Sorgula butonuna tıklanıyor...")
        try:
            sorgula_selector = 'button.x-btn-text.icon-find:has-text("Sorgula")'
            frame.locator(sorgula_selector).click()
            print("[BİLGİ] Sorgula butonuna tıklandı.")
            time.sleep(8)
        except Exception as e:
            hata_handler(page, str(e), "kasko_sorgula")
            raise

        # --- 12. ADIM: MÜŞTERİ ARAMA ---
        print("\n[BİLGİ] Müşteri aranıyor...")
        time.sleep(8)
        
        try:
            musteri_arama_trigger = frame.locator('#ext-gen233')
            musteri_arama_trigger.click()
            print("[BİLGİ] Müşteri arama trigger'ına tıklandı.")
            time.sleep(8)
        except Exception as e:
            hata_handler(page, str(e), "kasko_musteri_trigger")
            raise
        
        try:
            ara_buton_selector = '#ext-gen2033'
            frame.locator(ara_buton_selector).click()
            print("[BİLGİ] Ara butonuna tıklandı.")
            time.sleep(8)
        except Exception as e:
            hata_handler(page, str(e), "kasko_ara_buton")
            raise
        
        # --- 13. ADIM: MÜŞTERİ TABLOSUNU KONTROL ET VE SEÇ ---
        print("\n[BİLGİ] Müşteri tablosu kontrol ediliyor...")
        
        tablo_selector = 'div.x-grid3-body table.x-grid3-row-table'
        tablo_elementleri = frame.locator(tablo_selector)
        
        if tablo_elementleri.count() > 0:
            print(f"[BİLGİ] {tablo_elementleri.count()} müşteri bulundu.")
            
            ilk_musteri = tablo_elementleri.first
            ilk_musteri.click()
            print("[BİLGİ] İlk müşteri seçildi.")
            time.sleep(2)
            
            try:
                musteri_kodu = frame.locator('td.x-grid3-td-MustKod div.x-grid3-cell-inner').first.inner_text()
                musteri_adi = frame.locator('td.x-grid3-td-1 div.x-grid3-cell-inner').first.inner_text()
                print(f"[BİLGİ] Müşteri: {musteri_adi} (Kod: {musteri_kodu})")
            except Exception as e:
                print(f"[UYARI] Müşteri bilgileri alınamadı: {e}")
                musteri_kodu = ""
                musteri_adi = ""
            
            try:
                sec_buton_selector = '#ext-gen2041'
                frame.locator(sec_buton_selector).click()
                print("[BİLGİ] Seç butonuna tıklandı.")
                time.sleep(8)
            except Exception as e:
                hata_handler(page, str(e), "kasko_sec_buton")
                raise

            # --- 14. ADIM: SONRAKI ADIM BUTONUNA TIKLA ---
            print("\n[BİLGİ] Sonraki adım butonuna tıklanıyor...")
        
            try:
                sonraki_adim_selector = 'button.x-btn-text.icon-resultsetnext:has-text("Sonraki Adım")'
                frame.locator(sonraki_adim_selector).wait_for(state='visible', timeout=15000)
                frame.locator(sonraki_adim_selector).click()
                print("[BİLGİ] Sonraki adım butonuna tıklandı.")
                time.sleep(15)
            except Exception as e:
                hata_handler(page, str(e), "kasko_sonraki_1")
                raise
                
            # --- 15. ADIM: İKİNCİ SONRAKI ADIM BUTONUNA TIKLA ---
            print("\n[BİLGİ] İkinci Sonraki adım butonuna tıklanıyor...")
            
            try:
                sonraki_adim_selector = '#ext-gen56'
                frame.locator(sonraki_adim_selector).wait_for(state='visible', timeout=15000)
                frame.locator(sonraki_adim_selector).click()
                print("[BİLGİ] İkinci Sonraki adım butonuna tıklandı.")
                time.sleep(20)
            except Exception as e:
                hata_handler(page, str(e), "kasko_sonraki_2")
                raise
            
           # --- 16. ADIM: TEKLIF SONUÇLARINI ÇEK ---
            print("\n[BİLGİ] Teklif sonuçları tablosu kontrol ediliyor...")
            
            try:
                # 1️⃣ Sadece içinde 'Peşin' yazan tabloyu seç
                teklif_tablo_body = frame.locator("div.x-grid3-body", has_text="Peşin")
                teklif_tablo_body.wait_for(state='visible', timeout=20000)
                print("[BİLGİ] Doğru teklif tablosu bulundu.")
            except Exception as e:
                hata_handler(page, str(e), "kasko_tablo_body")
                raise
            
            try:
                # 2️⃣ Satırları al
                tablo_satirlari = teklif_tablo_body.locator("table.x-grid3-row-table")
                satir_sayisi = tablo_satirlari.count()
                print(f"[BİLGİ] {satir_sayisi} teklif satırı bulundu.")
            
                def oku_satir(satir):
                    td_liste = satir.locator("td:not([style*='display:none']) div.x-grid3-cell-inner")
                    hucreler = []
                    for j in range(td_liste.count()):
                        cell = td_liste.nth(j)
                        text = cell.inner_text().strip()
                        if not text:
                            text = cell.inner_html().strip()
                        hucreler.append(text)
                    return hucreler
            
                def yazdir_satir(baslik, hucreler):
                    alanlar = ["P/T", "Net Prim", "Vergi", "Brüt Prim", "Komisyon"]
                    print(f"\n[BİLGİ] {baslik}:")
                    for i, alan in enumerate(alanlar):
                        print(f"  {alan}: {hucreler[i] if i < len(hucreler) else '(bulunamadı)'}")
            
                # 3️⃣ Peşin ve Taksitli satırlarını al
                pesin_hucreler = oku_satir(tablo_satirlari.nth(0))
                yazdir_satir("Peşin Teklifi", pesin_hucreler)
            
                taksitli_hucreler = []
                if satir_sayisi > 1:
                    taksitli_hucreler = oku_satir(tablo_satirlari.nth(1))
                    yazdir_satir("Taksitli Teklifi", taksitli_hucreler)
            
                teklif_sonuclari = {
                    "pesin": {
                        "pt": pesin_hucreler[0] if len(pesin_hucreler) > 0 else "",
                        "net_prim": pesin_hucreler[1] if len(pesin_hucreler) > 1 else "",
                        "vergi": pesin_hucreler[2] if len(pesin_hucreler) > 2 else "",
                        "brut_prim": pesin_hucreler[3] if len(pesin_hucreler) > 3 else "",
                        "komisyon": pesin_hucreler[4] if len(pesin_hucreler) > 4 else "",
                    },
                    "taksitli": {
                        "pt": taksitli_hucreler[0] if len(taksitli_hucreler) > 0 else "",
                        "net_prim": taksitli_hucreler[1] if len(taksitli_hucreler) > 1 else "",
                        "vergi": taksitli_hucreler[2] if len(taksitli_hucreler) > 2 else "",
                        "brut_prim": taksitli_hucreler[3] if len(taksitli_hucreler) > 3 else "",
                        "komisyon": taksitli_hucreler[4] if len(taksitli_hucreler) > 4 else "",
                    }
                }
            
                print("\n[BAŞARILI] Kasko teklif sonuçları başarıyla çekildi!")
            
            except Exception as e:
                hata_handler(page, str(e), "kasko_veri_cekme")
                raise

        
    except Exception as e:
        print(f"\n[HATA] Kasko teklifi oluşturulurken bir hata oluştu: {e}", file=sys.stderr)
        hata_handler(page, str(e), "kasko_genel_hata")
        return {"durum": "Hata oluştu", "hata": str(e)}

def create_tamamlayici_saglik_teklifi(page, teklif_data):
    """
    Verilen bilgilerle Tamamlayıcı Sağlık Sigortası teklifi oluşturur ve sonuçları çeker.
    """
    try:
        print("\n[BİLGİ] Tamamlayıcı Sağlık Sigortası teklifi oluşturma işlemi başlatıldı...")

        print("Ana sayfadaki 'Tamamlayıcı Sağlık' linkine tıklanıyor...")
        page.locator('a.btn-home[href*="/sales-funnels/supplemental-health"]').click()
        
        print("Yeni sayfanın yüklenmesi bekleniyor...")
        page.wait_for_load_state('networkidle', timeout=30000)

        # iFrame'e erişim
        print("[BİLGİ] iFrame bulunuyor...")
        iframe = page.locator('#salesFunnel')
        iframe.wait_for(state='visible', timeout=30000)
        print("[BİLGİ] iFrame bulundu, içerik yükleniyor...")
        time.sleep(3)
        
        frame = page.frame_locator('#salesFunnel')
        
        print("Formu dolduruluyor...")
        tc_field = frame.locator('#Insureds-0-IdentityNumber')
        tc_field.wait_for(state='visible', timeout=20000)
        tc_field.fill(teklif_data['tc_kimlik'])
        print(f"[BİLGİ] TC Kimlik yazıldı: {teklif_data['tc_kimlik']}")
        time.sleep(3)
        
        frame.locator('#Insureds-0-Email').fill('example@gmail.com')
        print("E-posta girildi.")
        
        print("[BİLGİ] Şartlar checkbox'ının etiketine tıklanıyor...")
        checkbox_label_selector = 'label[for="TermsApproved"]'
        frame.locator(checkbox_label_selector).click()
        print("[BİLGİ] Şartlar checkbox'ı etiket üzerinden başarıyla işaretlendi.")
        
        print("[BİLGİ] DEVAM butonunun aktif olması bekleniyor...")
        enabled_continue_button_selector = 'input.btn-success.continue-btn:not([disabled])'
        frame.locator(enabled_continue_button_selector).click(timeout=15000)
        print("[BİLGİ] Aktif DEVAM butonuna tıklandı.")
        
        print("\n[BİLGİ] Teklif sonuçları tablosunun yüklenmesi bekleniyor... (Bu işlem uzun sürebilir)")
        results_table_selector = 'table.quotation-table'
        results_table = frame.locator(results_table_selector)
        results_table.wait_for(state='visible', timeout=90000)
        print("[BAŞARILI] Teklif sonuç tablosu başarıyla yüklendi!")
        
        print("[BİLGİ] Tablodaki veriler çekiliyor...")
        time.sleep(2)
        
        first_row = results_table.locator('tbody tr').first
        
        sigortali_adi = first_row.locator('td').nth(0).inner_text()
        yatarak_tedavi_prim = first_row.locator('td').nth(1).inner_text()
        ayakta_tedavi_prim = first_row.locator('td').nth(2).inner_text()
        toplam_prim = first_row.locator('td').nth(4).inner_text()
        
        sonuclar = {
            "sigortali_adi": sigortali_adi.strip(),
            "yatarak_tedavi_prim": yatarak_tedavi_prim.strip(),
            "ayakta_tedavi_prim": ayakta_tedavi_prim.strip(),
            "toplam_prim": toplam_prim.strip()
        }
        
        print("[BAŞARILI] Veri çekme işlemi tamamlandı.")
        return sonuclar
        
    except PlaywrightTimeoutError as e:
        print(f"\n[HATA] İşlem zaman aşımına uğradı. Tablo yüklenmedi veya bir selector hatalı.", file=sys.stderr)
        hata_handler(page, str(e), "saglik_timeout")
        return None
    except Exception as e:
        print(f"\n[HATA] Tamamlayıcı Sağlık teklifi oluşturulurken bir hata oluştu: {e}", file=sys.stderr)
        hata_handler(page, str(e), "saglik_genel_hata")
        return None

def create_trafik_teklifi(page, teklif_data):
    """
    Verilen bilgilerle Trafik Sigortası teklifi oluşturur.
    Yeni Teklif > Diğer menüsünü kullanır. Hata durumunda sayfayı yenileyip devam eder.
    """
    try:
        print("\n[BİLGİ] Trafik Sigortası teklifi oluşturma işlemi başlatıldı...")
        
        # --- 1. ADIM: ANA SAYFAYA DÖN ---
        print("[BİLGİ] Ana sayfaya dönülüyor...")
        page.goto("https://portal.referanssigorta.net/", wait_until="domcontentloaded")
        page.wait_for_load_state('networkidle', timeout=30000)
        time.sleep(5)

        handle_popup_if_exists(page)
        
        # --- 2. ADIM: "YENİ TEKLİF" MENÜSÜNE TIKLA ---
        print("[BİLGİ] 'Yeni Teklif' menü öğesine tıklanıyor...")
        yeni_teklif_selector = 'a[href="javascript:;"] span.menu-item-text:has-text("Yeni Teklif")'
        page.locator(yeni_teklif_selector).click()
        print("[BİLGİ] 'Yeni Teklif' menüsü açıldı.")
        time.sleep(2)
        
        # --- 3. ADIM: "DİĞER" ALT MENÜSÜNE TIKLA ---
        print("[BİLGİ] 'Diğer' alt menü öğesine tıklanıyor...")
        diger_selector = 'li a[target="_blank"] span.menu-item-text:has-text("Diğer")'
        
        with page.context.expect_page() as new_page_info:
            page.locator(diger_selector).click()
        
        new_page = new_page_info.value
        print("[BİLGİ] Yeni sekme açıldı, ona geçiliyor...")
        page = new_page
        
        print("[BİLGİ] Yeni sekmede açılan sayfa yükleniyor...")
        page.wait_for_load_state('networkidle', timeout=30000)
        print(f"[BİLGİ] Yeni sekme başarıyla yüklendi: {page.url}")
        time.sleep(5)

        # --- 4. ADIM: HATA POP-UP'INI KONTROL ET VE KAPAT ---
        print("\n[BİLGİ] Hata pop-up'ı kontrol ediliyor...")
        try:
            popup_selector = '.x-window:has-text("Hata")'
            page.locator(popup_selector).wait_for(state='visible', timeout=10000)
            print("[BİLGİ] 'İkili kimlik doğrulama' hatası pop-up'ı bulundu.")
            tamam_btn_selector = '#ext-gen124'
            page.locator(tamam_btn_selector).click()
            print("[BİLGİ] Hata pop-up'ı 'Tamam' butonu ile kapatıldı.")
            time.sleep(3)
        except PlaywrightTimeoutError:
            print("[BİLGİ] Hata pop-up'ı bulunamadı, devam ediliyor...")

        # --- 5. ADIM: KULLANICI ADI VE ŞİFRE İLE GİRİŞ YAP ---
        print("\n[BİLGİ] Kullanıcı adı ve şifre ile giriş yapılıyor...")
        
        username_selector = '#txtUsername'
        try:
            username_field = page.locator(username_selector)
            username_field.wait_for(state='visible', timeout=15000)
            username_field.fill(YOUR_USERNAME)
            print(f"[BİLGİ] Kullanıcı adı girildi: {YOUR_USERNAME}")
            time.sleep(1)
        except Exception as e:
            hata_handler(page, str(e), "trafik_username")
            raise

        password_selector = '#txtPassword'
        try:
            password_field = page.locator(password_selector)
            password_field.wait_for(state='visible', timeout=15000)
            password_field.fill(YOUR_PASSWORD)
            print("[BİLGİ] Şifre girildi.")
            time.sleep(1)
        except Exception as e:
            hata_handler(page, str(e), "trafik_password")
            raise

        login_btn_selectors = [
            'button:has-text("Giriş")',
            'input[type="submit"]',
            '.x-btn:has-text("Giriş")',
            'button.x-btn-text',
            'input[value="Giriş"]'
        ]
        
        login_successful = False
        for selector in login_btn_selectors:
            if page.locator(selector).count() > 0:
                print(f"[BİLGİ] Giriş butonu bulundu: {selector}")
                page.locator(selector).first.click()
                print("[BİLGİ] Giriş butonuna tıklandı.")
                login_successful = True
                break
        
        if not login_successful:
            print("[UYARI] Giriş butonu bulunamadı, Enter tuşu deneniyor...")
            page.keyboard.press('Enter')

        print("[BİLGİ] Giriş işlemi tamamlandı, sayfa yüklenmesi bekleniyor...")
        page.wait_for_load_state('networkidle', timeout=30000)
        time.sleep(5)

        # --- 6. ADIM: GOOGLE AUTHENTICATOR KODUNU GİR ---
        print("\n[BİLGİ] Google Authenticator pop-up'ı kontrol ediliyor...")
        try:
            ga_popup_selector = '#winGAC'
            page.locator(ga_popup_selector).wait_for(state='visible', timeout=15000)
            print("[BİLGİ] Google Authenticator pop-up'ı bulundu.")
            
            totp_code = generate_totp_code(SECRET_KEY)
            if not totp_code:
                raise Exception("TOTP kodu üretilemedi.")
            
            ga_code_selector = '#txtGAKod'
            page.locator(ga_code_selector).wait_for(state='visible', timeout=10000)
            page.locator(ga_code_selector).fill(totp_code)
            print(f"[BİLGİ] TOTP kodu girildi: {totp_code}")
            time.sleep(1)
            
            ga_login_selector = '#btnValidateTwoFactor'
            page.locator(ga_login_selector).click()
            print("[BİLGİ] Google Authenticator giriş butonuna tıklandı.")
            
            page.locator(ga_popup_selector).wait_for(state='hidden', timeout=15000)
            print("[BİLGİ] Google Authenticator pop-up'ı kapandı.")
        except PlaywrightTimeoutError:
            print("[BİLGİ] Google Authenticator pop-up'ı bulunamadı, devam ediliyor...")
        
        print("[BİLGİ] Son sayfa yüklenmesi bekleniyor...")
        page.wait_for_load_state('networkidle', timeout=30000)
        time.sleep(5)
        
        print(f"[BİLGİ] Son URL: {page.url}")
        print("[BAŞARILI] Tüm giriş işlemleri tamamlandı!")

        # --- 7. ADIM: TRAFIK MENÜSÜNE ULAŞ ---
        print("\n[BİLGİ] Trafik menüsüne ulaşılıyor...")
        
        try:
            print("[BİLGİ] Arama kutusuna 'trafik' yazılıyor...")
            search_input_selector = '#TriggerField1'
            page.locator(search_input_selector).wait_for(state='visible', timeout=15000)
            page.locator(search_input_selector).fill('trafik')
            print("[BİLGİ] 'trafik' yazıldı, menü filtreleniyor...")
            time.sleep(3)
        except Exception as e:
            hata_handler(page, str(e), "trafik_search")
            raise

        try:
            print("[BİLGİ] 'Poliçe' menüsü bekleniyor...")
            police_selector = 'a.x-tree-node-anchor:has-text("Poliçe")'
            page.locator(police_selector).wait_for(state='visible', timeout=10000)
            page.locator(police_selector).click()
            print("[BİLGİ] 'Poliçe' menüsüne tıklandı.")
            time.sleep(3)
        except Exception as e:
            hata_handler(page, str(e), "trafik_police")
            raise
        
        try:
            print("[BİLGİ] 'Trafik' menüsü bekleniyor...")
            trafik_selector = 'span:has-text("Trafik")'
            page.locator(trafik_selector).wait_for(state='visible', timeout=10000)
            page.locator(trafik_selector).click()
            print("[BİLGİ] 'Trafik' menüsüne tıklandı.")
            time.sleep(3)
        except Exception as e:
            hata_handler(page, str(e), "trafik_menu")
            raise
        
        try:
            print("[BİLGİ] 'Prestij Trafik Sigortası (TR2)' linki bekleniyor...")
            prestij_trafik_selector = 'a.x-tree-node-anchor[href*="/NonLife/Policy/SavePolicy.aspx?APP_MP=TR2"]:has-text("Prestij Trafik Sigortası (TR2)")'
            page.locator(prestij_trafik_selector).wait_for(state='visible', timeout=10000)
            page.locator(prestij_trafik_selector).click()
            print("[BİLGİ] 'Prestij Trafik Sigortası (TR2)' linkine tıklandı.")
        except Exception as e:
            hata_handler(page, str(e), "trafik_prestij")
            raise
        
        print("[BİLGİ] Trafik form sayfasının yüklenmesi bekleniyor...")
        page.wait_for_load_state('networkidle', timeout=30000)
        time.sleep(5)
        print(f"[BİLGİ] Trafik formu URL: {page.url}")
        print("[BAŞARILI] Trafik formuna ulaşıldı!")

        # --- 8. ADIM: IFRAME'E GEÇİŞ YAP ---
        print("\n[BİLGİ] Iframe'e geçiş yapılıyor...")
        
        try:
            iframe_selector = '#frmMain'
            page.locator(iframe_selector).wait_for(state='visible', timeout=15000)
            print("[BİLGİ] Iframe bulundu.")
        except Exception as e:
            hata_handler(page, str(e), "trafik_iframe")
            raise
        
        frame = page.frame_locator(iframe_selector)
        print("[BİLGİ] Iframe'e geçiş yapıldı.")
        time.sleep(3)

        # --- 9. ADIM: TRAFIK FORMUNU DOLDUR ---
        print("\n[BİLGİ] Trafik formu dolduruluyor...")
        
        try:
            print(f"[BİLGİ] TC Kimlik No giriliyor: {teklif_data['tc_kimlik']}")
            tc_selector = '#txtGIFTIdentityNo'
            frame.locator(tc_selector).wait_for(state='visible', timeout=15000)
            frame.locator(tc_selector).fill(teklif_data['tc_kimlik'])
            print(f"[BİLGİ] TC Kimlik No girildi: {teklif_data['tc_kimlik']}")
            time.sleep(2)
        except Exception as e:
            hata_handler(page, str(e), "trafik_tc")
            raise
        
        try:
            print(f"[BİLGİ] Plaka giriliyor: {teklif_data['plaka']}")
            plaka_selector = '#txtGIFTPlate'
            frame.locator(plaka_selector).fill(teklif_data['plaka'])
            print(f"[BİLGİ] Plaka girildi: {teklif_data['plaka']}")
            time.sleep(2)
        except Exception as e:
            hata_handler(page, str(e), "trafik_plaka")
            raise
        
        try:
            print(f"[BİLGİ] ASBİS No giriliyor: {teklif_data['asbis_no']}")
            asbis_seri_selector = '#txtGIFTEGMSerial'
            frame.locator(asbis_seri_selector).fill(teklif_data['asbis_no'][:2])
            print(f"[BİLGİ] ASBİS Seri girildi: {teklif_data['asbis_no'][:2]}")
            time.sleep(1)
            
            asbis_no_selector = '#txtGIFTEGMNo'
            frame.locator(asbis_no_selector).fill(teklif_data['asbis_no'][2:])
            print(f"[BİLGİ] ASBİS No girildi: {teklif_data['asbis_no'][2:]}")
            time.sleep(2)
        except Exception as e:
            hata_handler(page, str(e), "trafik_asbis")
            raise

        print("[BAŞARILI] Trafik formu başarıyla dolduruldu!")

        # --- 10. ADIM: SORGULA BUTONUNA TIKLA ---
        print("\n[BİLGİ] Sorgula butonuna tıklanıyor...")
        try:
            sorgula_selector = 'button.x-btn-text.icon-find:has-text("Sorgula")'
            frame.locator(sorgula_selector).click()
            print("[BİLGİ] Sorgula butonuna tıklandı.")
            time.sleep(8)
        except Exception as e:
            hata_handler(page, str(e), "trafik_sorgula")
            raise

        # --- 11. ADIM: POPUP UYARIYA "HAYIR" DE ---
        print("\n[BİLGİ] Popup uyarı kontrol ediliyor...")
        try:
            popup_selector = '#ext-gen2219'
            frame.locator(popup_selector).wait_for(state='visible', timeout=10000)
            print("[BİLGİ] Popup uyarı bulundu: 'Kimlik bilgilerinden bilgi bulunamadı'")
            
            hayir_btn_selector = '#ext-gen2189'
            frame.locator(hayir_btn_selector).click()
            print("[BİLGİ] Popup'a 'Hayır' ile cevap verildi.")
            time.sleep(3)
        except PlaywrightTimeoutError:
            print("[BİLGİ] Popup uyarı bulunamadı, devam ediliyor...")
        
        print("[BAŞARILI] Sorgulama işlemi tamamlandı!")
        print("\n[BİLGİ] Araç Bilgileri bölümü dolduruluyor...")
        time.sleep(2)
        
        # Kullanım Cinsi seç
        try:
            print(f"[BİLGİ] Kullanım Cinsi seçiliyor: {teklif_data['kullanim_cinsi']}")
            kullanim_cinsi_trigger = frame.locator('#ext-gen504')
            kullanim_cinsi_trigger.click()
            print("[BİLGİ] Kullanım Cinsi combobox'ı açıldı.")
            time.sleep(2)
            
            kullanim_cinsi_option = frame.locator(f'div.x-combo-list-item:has-text("{teklif_data["kullanim_cinsi"]}")').first
            kullanim_cinsi_option.click()
            print(f"[BİLGİ] Kullanım Cinsi seçildi: {teklif_data['kullanim_cinsi']}")
            time.sleep(2)
        except Exception as e:
            hata_handler(page, str(e), "trafik_kullanim_cinsi")
            raise
        
        # Marka seç
        try:
            print(f"[BİLGİ] Marka seçiliyor: {teklif_data['marka']}")
            marka_trigger = frame.locator('#ext-gen518')
            marka_trigger.click()
            print("[BİLGİ] Marka combobox'ı açıldı.")
            time.sleep(2)
            
            marka_option = frame.locator(f'div.x-combo-list-item:has-text("{teklif_data["marka"]}")').first
            marka_option.click()
            print(f"[BİLGİ] Marka seçildi: {teklif_data['marka']}")
            time.sleep(2)
        except Exception as e:
            hata_handler(page, str(e), "trafik_marka")
            raise
        
        # Model Yılı seç
        try:
            print(f"[BİLGİ] Model Yılı seçiliyor: {teklif_data['model_yili']}")
            model_yili_trigger = frame.locator('#ext-gen532')
            model_yili_trigger.click()
            print("[BİLGİ] Model Yılı combobox'ı açıldı.")
            time.sleep(2)
            
            model_yili_option = frame.locator(f'div.x-combo-list-item:has-text("{teklif_data["model_yili"]}")').first
            model_yili_option.click()
            print(f"[BİLGİ] Model Yılı seçildi: {teklif_data['model_yili']}")
            time.sleep(2)
        except Exception as e:
            hata_handler(page, str(e), "trafik_model_yili")
            raise
        
        # Model seç
        try:
            print(f"[BİLGİ] Model seçiliyor: {teklif_data['model']}")
            model_trigger = frame.locator('#ext-gen546')
            model_trigger.click()
            print("[BİLGİ] Model combobox'ı açıldı.")
            time.sleep(2)
            
            model_option = frame.locator(f'div.x-combo-list-item:has-text("{teklif_data["model"]}")').first
            model_option.click()
            print(f"[BİLGİ] Model seçildi: {teklif_data['model']}")
            time.sleep(2)
        except Exception as e:
            hata_handler(page, str(e), "trafik_model")
            raise
        
        print("[BAŞARILI] Araç Bilgileri başarıyla dolduruldu!")

        # Müşteri arama
        try:
            print("\n[BİLGİ] Müşteri arama penceresini açmak için trigger'a tıklanıyor...")
            musteri_arama_trigger = frame.locator('#ext-gen233')
            musteri_arama_trigger.click()
            print("[BİLGİ] Müşteri arama trigger'ına tıklandı.")
            time.sleep(8)
        except Exception as e:
            hata_handler(page, str(e), "trafik_musteri_trigger")
            raise
        
        try:
            print("\n[BİLGİ] Ara butonuna tıklanıyor...")
            ara_btn_selector = '#ext-gen2332'
            frame.locator(ara_btn_selector).click()
            print("[BİLGİ] Ara butonuna tıklandı.")
            time.sleep(8)
        except Exception as e:
            hata_handler(page, str(e), "trafik_ara_buton")
            raise
        
        # Müşteri tablosundan seç
        try:
            print("\n[BİLGİ] Müşteri tablosu kontrol ediliyor...")
            tablo_selector = 'table.x-grid3-row-table'
            tablo = frame.locator(tablo_selector).first
            tablo.wait_for(state='visible', timeout=15000)
            print("[BİLGİ] Müşteri tablosu bulundu.")
            
            musteri_satiri = tablo.locator('tbody tr').first
            musteri_satiri.click()
            print("[BİLGİ] İlk müşteri satırına tıklandı.")
            time.sleep(2)
            
            try:
                musteri_kodu = musteri_satiri.locator('td.x-grid3-td-MustKod div').inner_text()
                musteri_adi = musteri_satiri.locator('td.x-grid3-td-1 div').inner_text()
                print(f"[BİLGİ] Müşteri seçildi - Kod: {musteri_kodu}, Adı: {musteri_adi}")
            except Exception as e:
                print(f"[UYARI] Müşteri bilgileri alınamadı: {e}")
                musteri_kodu = ""
                musteri_adi = ""
        except Exception as e:
            hata_handler(page, str(e), "trafik_musteri_tablosu")
            raise
        
        try:
            print("\n[BİLGİ] Seç butonuna tıklanıyor...")
            sec_btn_selector = '#ext-gen2340'
            frame.locator(sec_btn_selector).click()
            print("[BİLGİ] Seç butonuna tıklandı.")
            time.sleep(8)
        except Exception as e:
            hata_handler(page, str(e), "trafik_sec_buton")
            raise

        try:
            print("[BİLGİ] Sonraki Adım Butonuna tıklanıyor...")
            sonraki_adim_btn_selector = '#ext-gen56'
            frame.locator(sonraki_adim_btn_selector).click()
            print("[BİLGİ] Sonraki Adım Butonuna tıklandı.")
            time.sleep(8)
        except Exception as e:
            hata_handler(page, str(e), "trafik_sonraki_1")
            raise

        try:
            print("[BİLGİ] Evet butonuna tıklanıyor...")
            evet_btn_selector = '#ext-gen2173'
            frame.locator(evet_btn_selector).click()
            print("[BİLGİ] Evet butonuna tıklandı.")
            time.sleep(10)
        except Exception as e:
            hata_handler(page, str(e), "trafik_evet_buton")
            raise

        try:
            print("[BİLGİ] Tekrar Sonraki Adım Butonuna tıklanıyor...")
            sonraki_adim_btn_selector = '#ext-gen56'
            frame.locator(sonraki_adim_btn_selector).click()
            print("[BİLGİ] Tekrar Sonraki Adım Butonuna tıklandı.")
            time.sleep(15)
        except Exception as e:
            hata_handler(page, str(e), "trafik_sonraki_2")
            raise
        
        try:
            print("\n[BİLGİ] Teklif sonuç tablosu kontrol ediliyor...")
            sonuc_tablo_selector = 'table.x-grid3-row-table'
            sonuc_tablolar = frame.locator(sonuc_tablo_selector)
            sonuc_tablolar.first.wait_for(state='visible', timeout=15000)
            print(f"[BİLGİ] {sonuc_tablolar.count()} teklif satırı bulundu.")
            
            # İlk satırı (Peşin) al
            pesini_satiri = sonuc_tablolar.nth(0)
            pesini_pt = pesini_satiri.locator('td').nth(1).inner_text().strip()
            pesini_net_prim = pesini_satiri.locator('td').nth(2).inner_text().strip()
            pesini_vergi = pesini_satiri.locator('td').nth(3).inner_text().strip()
            pesini_brut_prim = pesini_satiri.locator('td').nth(4).inner_text().strip()
            pesini_komisyon = pesini_satiri.locator('td').nth(5).inner_text().strip()
            
            print(f"[BİLGİ] Peşin Teklifi:")
            print(f"  P/T: {pesini_pt}")
            print(f"  Net Prim: {pesini_net_prim}")
            print(f"  Vergi: {pesini_vergi}")
            print(f"  Brüt Prim: {pesini_brut_prim}")
            print(f"  Komisyon: {pesini_komisyon}")
            
            # İkinci satırı (Taksitli) al
            taksitli_satiri = sonuc_tablolar.nth(1)
            taksitli_pt = taksitli_satiri.locator('td').nth(1).inner_text().strip()
            taksitli_net_prim = taksitli_satiri.locator('td').nth(2).inner_text().strip()
            taksitli_vergi = taksitli_satiri.locator('td').nth(3).inner_text().strip()
            taksitli_brut_prim = taksitli_satiri.locator('td').nth(4).inner_text().strip()
            taksitli_komisyon = taksitli_satiri.locator('td').nth(5).inner_text().strip()
            
            print(f"[BİLGİ] Taksitli Teklifi:")
            print(f"  P/T: {taksitli_pt}")
            print(f"  Net Prim: {taksitli_net_prim}")
            print(f"  Vergi: {taksitli_vergi}")
            print(f"  Brüt Prim: {taksitli_brut_prim}")
            print(f"  Komisyon: {taksitli_komisyon}")
            
            teklif_sonuclari = {
                "pesini": {
                    "pt": pesini_pt,
                    "net_prim": pesini_net_prim,
                    "vergi": pesini_vergi,
                    "brut_prim": pesini_brut_prim,
                    "komisyon": pesini_komisyon
                },
                "taksitli": {
                    "pt": taksitli_pt,
                    "net_prim": taksitli_net_prim,
                    "vergi": taksitli_vergi,
                    "brut_prim": taksitli_brut_prim,
                    "komisyon": taksitli_komisyon
                }
            }
            
            print("[BAŞARILI] Trafik Teklif sonuçları başarıyla çekildi!")
            
            return {
                "durum": "Trafik teklifi başarıyla tamamlandı",
                "asama": "teklif_sonuclari",
                "url": page.url,
                "tc_kimlik": teklif_data.get('tc_kimlik', ''),
                "plaka": teklif_data.get('plaka', ''),
                "asbis_no": teklif_data.get('asbis_no', ''),
                "kullanim_cinsi": teklif_data.get('kullanim_cinsi', ''),
                "marka": teklif_data.get('marka', ''),
                "model_yili": teklif_data.get('model_yili', ''),
                "model": teklif_data.get('model', ''),
                "musteri_kodu": musteri_kodu,
                "musteri_adi": musteri_adi,
                "teklif_sonuclari": teklif_sonuclari
            }
        except Exception as e:
            hata_handler(page, str(e), "trafik_teklif_sonuclari")
            raise

    except Exception as e:
        print(f"\n[HATA] Trafik teklifi oluşturulurken bir hata oluştu: {e}", file=sys.stderr)
        hata_handler(page, str(e), "trafik_genel_hata")
        return {"durum": "Hata oluştu", "hata": str(e)}

def main():
    with sync_playwright() as p:
        # Stealth mode ayarları
        browser = p.chromium.launch(
            headless=False,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-web-resources',
                '--disable-client-side-phishing-detection',
            ]
        )
        
        context = browser.new_context(
            user_agent=STEALTH_USER_AGENT,
            viewport={"width": 1400, "height": 1000},
            ignore_https_errors=True,
        )
        
        # Stealth mode için JavaScript injection
        context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => false,
            });
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5],
            });
            Object.defineProperty(navigator, 'languages', {
                get: () => ['tr-TR', 'tr', 'en-US', 'en'],
            });
        """)
        
        page = context.new_page()
        
        try:
            # 1. ORTAK ADIM: GİRİŞ YAPMA
            full_login(page)
            print("\n[BAŞARILI] Tam giriş işlemi tamamlandı!")

            # 2. ORTAK ADIM: POP-UP'I KAPATMA
            handle_popup_if_exists(page)

            # 3. MENÜ GÖSTERME VE SEÇİM ALMA
            print("\n" + "="*25)
            print("--- İŞLEM MENÜSÜ ---")
            print("1: Tamamlayıcı Sağlık Sigortası Teklifi")
            print("2: Kasko Sigortası Teklifi")
            print("3: Trafik Sigortası Teklifi")
            print("="*25)
            secim = input("Lütfen yapmak istediğiniz işlemi seçin (1, 2 veya 3): ")

            # 4. SEÇİME GÖRE İLGİLİ FONKSİYONU ÇAĞIRMA
            if secim == '1':
                print("\n[BİLGİ] Tamamlayıcı Sağlık Sigortası işlemi seçildi.")
                teklif_icin_tc = "48274206902" 
                teklif_sonuclari = create_tamamlayici_saglik_teklifi(
                    page, 
                    {'tc_kimlik': teklif_icin_tc}
                )
                
                if teklif_sonuclari:
                    print("\n--- ÇEKİLEN SAĞLIK TEKLİF BİLGİLERİ ---")
                    print(f"  Sigortalı Adı:         {teklif_sonuclari['sigortali_adi']}")
                    print(f"  Yatarak Tedavi Prim:   {teklif_sonuclari['yatarak_tedavi_prim']}")
                    print(f"  Ayakta Tedavi Prim:    {teklif_sonuclari['ayakta_tedavi_prim']}")
                    print(f"  Toplam Prim:           {teklif_sonuclari['toplam_prim']}")
                    print("------------------------------------------")
                else:
                    print("\n[UYARI] Sağlık teklif bilgileri çekilemedi.")

            elif secim == '2':
                print("\n[BİLGİ] Kasko Sigortası işlemi seçildi.")
                
                kasko_teklif_data = {
                    'plaka': '52DS543',
                    'tc_kimlik': '22238537226',
                    'telefon': '5551234567',
                    'email': 'test@ornekmail.com',
                    'tescil_tarihi': '2023-05-15',
                    'asbis_no': 'FC504573',
                    'kullanim_cinsi': '01 / HUSUSİ OTOMOBİL',
                    'marka': 'VOLKSWAGEN',
                    'model_yili': '2017',
                    'model': 'TRANSIT KAMYONET DIZEL (05 KAMYONET) | 053513'
                }
                teklif_sonuclari = create_kasko_teklifi(
                    page, 
                    kasko_teklif_data
                )

                if teklif_sonuclari and teklif_sonuclari.get('durum') == 'Kasko teklifi başarıyla tamamlandı':
                    print("\n[BAŞARILI] Kasko formu işlemi tamamlandı.")
                    print(f"  Müşteri: {teklif_sonuclari.get('musteri_adi', 'N/A')}")
                    print(f"  Peşin Brüt Prim: {teklif_sonuclari['teklif_sonuclari']['pesini']['brut_prim']}")
                    print(f"  Taksitli Brüt Prim: {teklif_sonuclari['teklif_sonuclari']['taksitli']['brut_prim']}")
                else:
                    print("\n[UYARI] Kasko teklif işlemi başarısız oldu.")
                    
            elif secim == '3':
                print("\n[BİLGİ] Trafik Sigortası işlemi seçildi.")
                
                trafik_teklif_data = {
                    'plaka': '28ACV635',
                    'tc_kimlik': '38281378662',
                    'telefon': '5551234567',
                    'email': 'test@ornekmail.com',
                    'tescil_tarihi': '2023-05-15',
                    'asbis_no': 'GR714361',
                    'kullanim_cinsi': 'ÖZEL OTOMOBİL',
                    'marka': 'TOFAS-FIAT',
                    'model_yili': '1986',
                    'model': 'SAHIN1.4 | 100281'
                }
                teklif_sonuclari = create_trafik_teklifi(
                    page, 
                    trafik_teklif_data
                )

                if teklif_sonuclari and teklif_sonuclari.get('durum') == 'Trafik teklifi başarıyla tamamlandı':
                    print("\n[BAŞARILI] Trafik formu işlemi tamamlandı.")
                    print(f"  Müşteri: {teklif_sonuclari.get('musteri_adi', 'N/A')}")
                    print(f"  Peşin Brüt Prim: {teklif_sonuclari['teklif_sonuclari']['pesini']['brut_prim']}")
                    print(f"  Taksitli Brüt Prim: {teklif_sonuclari['teklif_sonuclari']['taksitli']['brut_prim']}")
                else:
                    print("\n[UYARI] Trafik teklif işlemi başarısız oldu.")
            else:
                print("\n[HATA] Geçersiz seçim. Lütfen 1, 2 veya 3 giriniz.")

            # 5. İŞLEM SONU BEKLEME
            print("\n################################################################")
            print("İŞLEM TAMAMLANDI. TARAYICI İNCELEME İÇİN AÇIK BIRAKILDI.")
            print("################################################################")
            input("Tarayıcıyı kapatmak için ENTER tuşuna basın...")

        except Exception as e:
            print(f"\n[HATA] Ana işlem sırasında bir hata oluştu: {e}", file=sys.stderr)
            input("Hata oluştu. Tarayıcıyı kapatmak için ENTER tuşuna basın...")
            
        finally:
            context.close()
            browser.close()
            print("Tarayıcı kapatıldı.")

if __name__ == "__main__":
    main()