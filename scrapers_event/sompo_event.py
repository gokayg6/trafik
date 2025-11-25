# -*- coding: utf-8 -*-
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
import pyotp
import time
import sys
import json
import os
import traceback
import asyncio

# Windows için asyncio event loop policy ayarla (Playwright için)
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# --- AYARLAR ---
COOKIE_DIR = "cookies"
STORAGE_STATE_FILE_PATH = os.path.join(COOKIE_DIR, "sompo_storage_state.json")

# GİRİŞ BİLGİLERİ - .env'den oku
import os
from dotenv import load_dotenv
# Load environment variables with UTF-8 encoding
try:
    load_dotenv(encoding='utf-8')
except (UnicodeDecodeError, Exception):
    try:
        load_dotenv()
    except Exception:
        pass

YOUR_USERNAME = os.getenv("SOMPO_USER", "").strip()
YOUR_PASSWORD = os.getenv("SOMPO_PASS", "EE28sigorta.").strip()  # Default: EE28sigorta.

# 2FA (TOTP) BİLGİLERİ
SECRET_KEY = os.getenv("SOMPO_TOTP_SECRET", "").strip()

# Validasyon
if not YOUR_USERNAME or not YOUR_PASSWORD or not SECRET_KEY:
    raise RuntimeError("SOMPO_USER, SOMPO_PASS ve SOMPO_TOTP_SECRET .env dosyasında tanımlı olmalıdır!")
LOGIN_BUTTON_SELECTOR = 'button[type="submit"]'
TOTP_CONTAINER_SELECTOR = 'div.p-inputotp'

LOGIN_URL = "https://ejento.somposigorta.com.tr/dashboard/login"
DASHBOARD_URL = "https://ejento.somposigorta.com.tr/dashboard"

# --- İŞLEM SELECTOR'LARI ---
NEW_OFFER_BUTTON_SELECTOR = 'button:has-text("YENİ İŞ TEKLİFİ")'
POPUP_NOTIF_HAYIR = '#ppialog-popover-cancel-button:has-text("HAYIR")'
POPUP_SHEPHERD_CLOSE = 'button.shepherd-cancel-icon'
GET_OFFER_BUTTON_SELECTOR = 'button:has-text("TEKLİF AL")'

# --- SİGORTA TÜRLERİ ---
INSURANCE_TYPES = {
    "TRAFIK": "Trafik Sigortası",
    "KASKO": "Kasko Sigortası",
    "SAGLIK": "Tamamlayıcı Sağlık Sigortası",
    "DASK": "DASK (Zorunlu Deprem Sigortası)"
}


def generate_totp_code(secret_key):
    """Verilen secret key ile güncel TOTP kodunu üretir."""
    try:
        totp = pyotp.TOTP(secret_key)
        current_code = totp.now()
        print(f"[BİLGİ] Generated TOTP Code: {current_code}")
        return current_code
    except Exception as e:
        print(f"[HATA] Failed to generate TOTP code: {e}", file=sys.stderr)
        return None

def save_storage_state(page):
    """Oturum durumunu JSON dosyasına kaydeder."""
    try:
        if not os.path.exists(COOKIE_DIR):
            os.makedirs(COOKIE_DIR)
        page.context.storage_state(path=STORAGE_STATE_FILE_PATH)
        print(f"\n[BİLGİ] Session state successfully '{STORAGE_STATE_FILE_PATH}' saved to file.")
    except Exception as e:
        print(f"\n[HATA] Failed to save session state: {e}", file=sys.stderr)

def login_and_save(page):
    """Kullanıcı adı/şifre ve TOTP ile giriş yapar ve oturumu kaydeder."""
    page.goto(LOGIN_URL, wait_until="domcontentloaded")
    print("Sayfa açıldı:", page.title())
    username_selector = 'form input:nth-of-type(1)'
    password_selector = 'input[type="password"]'
    page.fill(username_selector, YOUR_USERNAME)
    page.fill(password_selector, YOUR_PASSWORD)
    print("Username and password entered.")
    page.click(LOGIN_BUTTON_SELECTOR)
    print("Giriş butonu tıklandı, TOTP ekranı bekleniyor...")
    totp_code = generate_totp_code(SECRET_KEY)
    if not totp_code or len(totp_code) != 6:
        print("[HATA] Geçersiz TOTP kodu uzunluğu.", file=sys.stderr)
        return False
    page.wait_for_selector(TOTP_CONTAINER_SELECTOR, timeout=15000)
    totp_container = page.locator(TOTP_CONTAINER_SELECTOR)
    input_fields = totp_container.locator('input[type="text"]')
    for i in range(6):
        digit = totp_code[i]
        input_fields.nth(i).fill(digit)
    print(f"TOTP Code ({totp_code}) hanelere ayrılarak girildi.")
    time.sleep(0.5)
    print("TOTP code entered. Otomatik doğrulama ve Dashboard bekleniyor...")
    page.wait_for_url(lambda url: url != LOGIN_URL, timeout=15000)
    print("Giriş başarılı! Dashboard sayfasına geçildi.")
    save_storage_state(page)
    return True

def handle_popups(page):
    """Tanıtım ve Bildirim pop-up'larını kapatır (Varsa)."""
    print("\n[İŞLEM] Pop-up kontrol ediliyor...")
    time.sleep(2)
    print("[BİLGİ] Pop-up yüklenmesi için 2 saniye beklendi.")

    popup_buttons = [
        (POPUP_NOTIF_HAYIR, "'HAYIR' Bildirim pop-up'ı"),
        (POPUP_SHEPHERD_CLOSE, "Shepherd Turu Kapatma (X)"),
    ]

    for selector, name in popup_buttons:
        try:
            button = page.locator(selector)

            if button.is_visible(timeout=2000):
                button.click()
                print(f"[BİLGİ] {name} tıklandı ve kapatıldı.")
                time.sleep(0.5)
        except PlaywrightTimeoutError:
            continue
        except Exception as e:
            print(f"[HATA] {name} kapatılırken beklenmedik hata: {e}", file=sys.stderr)

    print("[BİLGİ] Pop-up kontrol adımı tamamlandı.")


def fill_tckn_field(page, tckn_value):
    """TCKN alanını bulur ve doldurur. Başarı durumunu döndürür."""
    print(f"\n[İŞLEM] TCKN girişi yapılıyor: {tckn_value}")

    # Alternatif selector'lar
    tckn_selectors = [
        "#txtIdentityOrTaxNo",
        "input[id='txtIdentityOrTaxNo']",
        "input[name*='Identity']",
        "input[name*='TaxNo']",
        "input[placeholder*='TC']",
        "input[placeholder*='Kimlik']",
    ]

    for selector in tckn_selectors:
        try:
            print(f"[BİLGİ] TCKN alanı deneniyor: {selector}")

            page.wait_for_selector(selector, state="visible", timeout=5000)
            input_box = page.locator(selector).first
            input_box.wait_for(state="visible", timeout=5000)

            # Alanı temizle ve doldur
            input_box.click()
            time.sleep(0.3)
            page.keyboard.press("Control+A")
            page.keyboard.press("Backspace")
            time.sleep(0.2)
            input_box.fill(tckn_value)
            time.sleep(0.5)

            # Doğrulama
            current_value = input_box.input_value()
            if current_value == tckn_value:
                print(f"[BAŞARILI] TCKN '{tckn_value}' başarıyla written.")
                page.keyboard.press("Tab")
                time.sleep(0.5)
                return True
            else:
                print(f"[UYARI] TCKN written ama doğrulanamadı. Beklenen: {tckn_value}, Bulunan: {current_value}")

        except PlaywrightTimeoutError:
            continue
        except Exception as e:
            print(f"[HATA] {selector} ile hata: {e}")
            continue

    print("[HATA] TCKN alanı hiçbir selector ile bulunamadı!", file=sys.stderr)
    return False


def open_new_offer_page(page):
    """Yeni İş Teklifi sayfasını açar ve yeni sekmeyi döndürür."""
    print(f"\n[İŞLEM] 'YENİ İŞ TEKLİFİ' butonuna tıklanıyor...")

    page.wait_for_url(lambda url: "login" not in url.lower(), timeout=15000)
    page.wait_for_selector(NEW_OFFER_BUTTON_SELECTOR, timeout=10000)
    page.click(NEW_OFFER_BUTTON_SELECTOR)
    print("[BAŞARILI] 'YENİ İŞ TEKLİFİ' butonuna tıklandı.")

    time.sleep(3)

    # 'TEKLİF AL' butonuna tıkla ve yeni sekmeyi yakala
    print("[İŞLEM] 'TEKLİF AL' butonuna tıklanıyor ve yeni sekme bekleniyor...")
    try:
        page.wait_for_selector(GET_OFFER_BUTTON_SELECTOR, timeout=10000)

        with page.context.expect_page() as new_page_info:
            page.click(GET_OFFER_BUTTON_SELECTOR)

        new_page = new_page_info.value
        print("[BAŞARILI] Yeni sekme yakalandı!")

        new_page.wait_for_load_state("domcontentloaded")
        print(f"[BİLGİ] Yeni sekme URL: {new_page.url}")

        time.sleep(5)  # Form yüklenmesini bekle
        return new_page

    except PlaywrightTimeoutError:
        print("[UYARI] 'TEKLİF AL' butonu bulunamadı veya yeni sekme açılmadı.", file=sys.stderr)
        return None


# ==================== SİGORTA TÜRÜ FONKSİYONLARI ====================

def process_trafik_sigortasi(page, data):
    """
    Trafik Sigortası için teklif sürecini tamamlar.
    """
    print("\n" + "="*60)
    print("TRAFİK SİGORTASI İŞLEMİ BAŞLATILIYOR")
    print("="*60)
    
    try:
        # 1️⃣ TCKN girişi
        if not fill_tckn_field(page, data['tckn']):
            return False
        
        time.sleep(1)
        
        # 2️⃣ Kasko checkbox'ını kaldır, Trafik checkbox'ını işaretle
        print("\n[İŞLEM] Sigorta türü seçiliyor (Trafik)...")
        
        # Kasko checkbox'ının işaretini kaldır
        casco_checkbox = page.locator("#chkCasco")
        if casco_checkbox.is_checked():
            casco_checkbox.uncheck()
            print("[BİLGİ] Kasko seçimi kaldırıldı.")
        
        time.sleep(0.3)
        
        # Trafik checkbox'ını işaretle
        traffic_checkbox = page.locator("#chkTraffic")
        if not traffic_checkbox.is_checked():
            traffic_checkbox.check()
            print("[BİLGİ] Trafik sigortası seçildi.")
        
        time.sleep(0.5)
        
        # 3️⃣ Plaka girişi
        print(f"\n[İŞLEM] Plaka bilgisi giriliyor: {data['plaka']}")
        
        # Plakayı parçala: "34ABC123" -> "34" ve "ABC123"
        plaka = data['plaka'].upper().strip()
        
        il_kodu = ""
        kalan_plaka = ""
        
        for i, char in enumerate(plaka):
            if char.isdigit():
                il_kodu += char
            else:
                kalan_plaka = plaka[i:]
                break
        
        if not il_kodu or not kalan_plaka:
            print(f"[HATA] Geçersiz plaka formatı: {data['plaka']}", file=sys.stderr)
            return False
        
        print(f"[BİLGİ] Plaka parçalandı -> İl: {il_kodu}, Kalan: {kalan_plaka}")
        
        # İl kodunu gir
        plate_city_input = page.locator("#txtPlateNoCityNo")
        plate_city_input.click()
        plate_city_input.fill(il_kodu)
        time.sleep(0.3)
        print(f"[BAŞARILI] İl kodu girildi: {il_kodu}")
        
        # Kalan plakayı gir
        plate_input = page.locator("#txtPlateNo")
        plate_input.click()
        plate_input.fill(kalan_plaka)
        time.sleep(0.3)
        print(f"[BAŞARILI] Plate entered: {kalan_plaka}")
        
        # 4️⃣ Ruhsat Seri No girişi
        print(f"\n[İŞLEM] Ruhsat seri no giriliyor: {data['ruhsat_seri_no']}")
        
        ruhsat = data['ruhsat_seri_no'].upper().strip()
        
        ruhsat_code = ""
        ruhsat_number = ""
        
        for i, char in enumerate(ruhsat):
            if char.isalpha():
                ruhsat_code += char
            else:
                ruhsat_number = ruhsat[i:]
                break
        
        if not ruhsat_code or not ruhsat_number:
            print(f"[HATA] Geçersiz ruhsat seri no formatı: {data['ruhsat_seri_no']}", file=sys.stderr)
            return False
        
        print(f"[BİLGİ] Ruhsat parçalandı -> Seri: {ruhsat_code}, No: {ruhsat_number}")
        
        # Ruhsat seri kodunu gir
        egm_code_input = page.locator("#txtEGMNoCode")
        egm_code_input.click()
        egm_code_input.fill(ruhsat_code)
        time.sleep(0.3)
        print(f"[BAŞARILI] Ruhsat seri kodu girildi: {ruhsat_code}")
        
        # Ruhsat numarasını gir
        egm_number_input = page.locator("#txtEGMNoNumber")
        egm_number_input.click()
        egm_number_input.fill(ruhsat_number)
        time.sleep(0.3)
        print(f"[BAŞARILI] Ruhsat numarası girildi: {ruhsat_number}")
        
        # 5️⃣ EGM Sorgula butonuna tıkla
        print("\n[İŞLEM] EGM sorgusu yapılıyor...")
        egm_search_button = page.locator("#btnSearchEgm")
        egm_search_button.click()
        print("[BAŞARILI] EGM Query button clicked.")
        
        print("[BİLGİ] EGM sorgu sonucu bekleniyor (5 saniye)...")
        time.sleep(10)

        """
        arac_marka = "Volkswagen" # DÜZENLENECEK ARAÇ MARKA
        data['arac_marka'] = arac_marka if arac_marka else "Bilinmiyor"
        """

        print(f"\n[İŞLEM] Araç markası seçiliyor: {data['arac_marka']}")
        
        try:
            vehicle_brand_dropdown = page.locator("#ddlVehicleBrandNewCasco")
            vehicle_brand_dropdown.wait_for(state="visible", timeout=5000)
            
            print(f"[BİLGİ] Marka dropdown'ı bulundu. Seçim yapılıyor: {data['arac_marka']}")
            
            # Dropdown'dan markaları listele ve eşleş
            options = vehicle_brand_dropdown.locator("option")
            option_found = False
            
            for i in range(options.count()):
                option_text = options.nth(i).text_content().strip()
                if option_text.upper() == data['arac_marka'].upper():
                    option_value = options.nth(i).get_attribute("value")
                    vehicle_brand_dropdown.select_option(value=option_value)
                    print(f"[BAŞARILI] Araç markası seçildi: {option_text}")
                    option_found = True
                    break
            
            if not option_found:
                print(f"[UYARI] Marka bulunamadı: {data['arac_marka']}, listedeki seçenekler aranıyor...")
                # Tam eşleşme yoksa, kısmi eşleşme ara
                for i in range(options.count()):
                    option_text = options.nth(i).text_content().strip()
                    if data['arac_marka'].upper() in option_text.upper():
                        option_value = options.nth(i).get_attribute("value")
                        vehicle_brand_dropdown.select_option(value=option_value)
                        print(f"[BAŞARILI] Benzer marka seçildi: {option_text}")
                        option_found = True
                        break
            
            if not option_found:
                print(f"[HATA] Araç markası seçilenemedi: {data['arac_marka']}")
                return False
            
            time.sleep(1)
            
        except PlaywrightTimeoutError:
            print("[HATA] Araç markası dropdown'ı bulunamadı!")
            return False
        except Exception as e:
            print(f"[HATA] Araç markası seçiminde hata: {e}", file=sys.stderr)
            return False
        time.sleep(3)
        # 6️⃣ Araç Modeli girişi
        print(f"\n[İŞLEM] Araç modeli alanı kontrol ediliyor...")
        
        vehicle_model_input = page.locator("#txtVehicleModels")
        
        try:
            vehicle_model_input.wait_for(state="visible", timeout=3000)
            
            print(f"[BİLGİ] Araç modeli alanı bulundu. Dolduruluyor: {data['arac_modeli']}")
            
            vehicle_model_input.click()
            time.sleep(0.5)
            
            page.keyboard.press("Control+A")
            page.keyboard.press("Backspace")
            time.sleep(0.2)
            
            vehicle_model_input.type(data['arac_modeli'], delay=100)
            print(f"[BAŞARILI] Araç modeli written: {data['arac_modeli']}")
            
            time.sleep(2)
            print("[BİLGİ] Autocomplete listesi bekleniyor...")
            
            try:
                autocomplete_item = page.locator("ul.ui-autocomplete li.ui-menu-item").first
                if autocomplete_item.is_visible(timeout=3000):
                    autocomplete_item.click()
                    print("[BAŞARILI] Autocomplete listesinden ilk seçenek seçildi.")
                else:
                    page.keyboard.press("Enter")
                    print("[BİLGİ] Enter tuşuna basıldı.")
            except:
                page.keyboard.press("Enter")
                print("[BİLGİ] Enter tuşuna basıldı (autocomplete bulunamadı).")
        
        except PlaywrightTimeoutError:
            print("[UYARI] Araç modeli giriş alanı bulunamadı veya zorunlu değil. Adım atlanıyor.")
            pass
        except Exception as e:
            print(f"[HATA] Araç modeli girişinde beklenmedik hata: {e}", file=sys.stderr)
            pass
        
        time.sleep(1)
        
        # 7️⃣ E-posta iletişim türünü seç
        print("\n[İŞLEM] E-posta iletişim türü seçiliyor...")
        
        email_radio = page.locator("#rblInsuredContactType_1")
        email_radio.check()
        print("[BAŞARILI] E-posta iletişim türü seçildi.")
        
        time.sleep(0.5)
        
        # 8️⃣ E-posta adresi gir
        print(f"\n[İŞLEM] E-posta adresi giriliyor: {data['email']}")
        
        email_input = page.locator("#txtInsuredEmailAddress")
        email_input.wait_for(state="visible", timeout=5000)
        email_input.click()
        email_input.fill(data['email'])
        print(f"[BAŞARILI] E-posta adresi girildi: {data['email']}")
        
        time.sleep(0.5)
        
        # 9️⃣ Teklif Oluştur butonuna tıkla
        print("\n[İŞLEM] 'Teklif Oluştur' butonuna tıklanıyor...")
        
        proposal_button = page.locator("#btnProposalCreate")
        proposal_button.wait_for(state="visible", timeout=5000)
        proposal_button.click()
        print("[BAŞARILI] 'Teklif Oluştur' butonuna tıklandı.")
        
        print("[BİLGİ] Teklif oluşturma işlemi bekleniyor (7 saniye)...")
        time.sleep(7)
        
        # 🔟 Teklif bilgilerini al
        print("\n[İŞLEM] Teklif bilgileri alınıyor...")
        
        try:
            print("[BİLGİ] Sayfa aşağı kaydırılıyor...")
            page.evaluate("window.scrollBy(0, 500)")
            time.sleep(2)
            page.evaluate("window.scrollBy(0, 500)")
            time.sleep(2)
            
            teklif_tipi = None
            brut_prim = None
            teklif_no = None
            
            print("[BİLGİ] Standart Trafik Teklifi kontrol ediliyor...")
            try:
                standart_brut_prim_element = page.locator("#lblTrafficProposalGrossPremium")
                
                if standart_brut_prim_element.count() > 0:
                    is_visible = page.evaluate("""
                        () => {
                            const element = document.querySelector('#lblTrafficProposalGrossPremium');
                            if (!element) return false;
                            const style = window.getComputedStyle(element);
                            const text = element.textContent.trim();
                            return style.display !== 'none' && text.length > 0;
                        }
                    """)
                    
                    if is_visible:
                        brut_prim = standart_brut_prim_element.text_content().strip()
                        teklif_tipi = "STANDART"
                        
                        try:
                            teklif_no_element = page.locator("#lblTrafficProposalStartEndDateOrProposalNo")
                            teklif_no = teklif_no_element.text_content().strip()
                        except:
                            teklif_no = "Bulunamadı"
                        
                        print(f"[BAŞARILI] Standart Trafik Teklifi bulundu!")
            except Exception as e:
                print(f"[BİLGİ] Standart teklif bulunamadı: {e}")
            
            if not brut_prim:
                print("[BİLGİ] Ek Teminatlı Trafik Teklifi kontrol ediliyor...")
                try:
                    page.evaluate("window.scrollBy(0, 300)")
                    time.sleep(1)
                    
                    ek_teminatli_brut_prim_element = page.locator("#lblTrafficProposalGrossPremiumAlternative")
                    
                    ek_teminatli_brut_prim_element.wait_for(state="visible", timeout=15000)
                    brut_prim = ek_teminatli_brut_prim_element.text_content().strip()
                    teklif_tipi = "EK_TEMİNATLI"
                    
                    try:
                        teklif_no_element = page.locator("#lblTrafficProposalStartEndDateOrProposalNoAlternative")
                        teklif_no = teklif_no_element.text_content().strip()
                    except:
                        teklif_no = "Bulunamadı"
                    
                    print(f"[BAŞARILI] Ek Teminatlı Trafik Teklifi bulundu!")
                except Exception as e:
                    print(f"[BİLGİ] Ek Teminatlı teklif bulunamadı: {e}")
            
            if not brut_prim:
                print("[HATA] Hiçbir teklif bulunamadı!", file=sys.stderr)
                
                print("\n[DEBUG] Sayfa içeriği kontrol ediliyor...")
                page_content = page.content()
                
                if "lblTrafficProposalGrossPremium" in page_content:
                    print("[DEBUG] Standart teklif elementi HTML'de var!")
                if "lblTrafficProposalGrossPremiumAlternative" in page_content:
                    print("[DEBUG] Ek Teminatlı teklif elementi HTML'de var!")
                
                return {'basarili': False, 'hata': 'Teklif bilgileri bulunamadı'}
            
            print("\n" + "="*60)
            print(f"✅ TRAFİK SİGORTASI TEKLİFİ BAŞARIYLA OLUŞTURULDU!")
            print(f"📋 Teklif Tipi: {teklif_tipi}")
            print("="*60)
            print(f"📄 Teklif No: {teklif_no}")
            print(f"💰 Brüt Prim: {brut_prim}")
            print("="*60)
            
            return {
                'basarili': True,
                'teklif_tipi': teklif_tipi,
                'teklif_no': teklif_no,
                'brut_prim': brut_prim
            }
            
        except PlaywrightTimeoutError:
            print("[HATA] Teklif bilgileri yüklenemedi (timeout)!", file=sys.stderr)
            return {'basarili': False, 'hata': 'Timeout - Teklif bilgileri bulunamadı'}
        except Exception as e:
            print(f"[HATA] Teklif bilgileri alınırken hata oluştu: {e}", file=sys.stderr)
            traceback.print_exc()
            return {'basarili': False, 'hata': str(e)}
        
    except Exception as e:
        print(f"\n[HATA] Trafik sigortası işlemi sırasında hata oluştu: {e}", file=sys.stderr)
        traceback.print_exc()
        return False

def process_kasko_sigortasi(page, data):
    """
    Kasko Sigortası için teklif sürecini tamamlar.
    """
    print("\n" + "="*60)
    print("KASKO SİGORTASI İŞLEMİ BAŞLATILIYOR")
    print("="*60)
    
    try:
        # 1️⃣ TCKN girişi
        if not fill_tckn_field(page, data['tckn']):
            return False
        
        time.sleep(1)
        
        # 2️⃣ Kasko checkbox'ını işaretle, Trafik checkbox'ını kaldır
        print("\n[İŞLEM] Sigorta türü seçiliyor (Kasko)...")
        
        casco_checkbox = page.locator("#chkCasco")
        if not casco_checkbox.is_checked():
            casco_checkbox.check()
            print("[BİLGİ] Kasko sigortası seçildi.")
        
        time.sleep(0.3)
        
        traffic_checkbox = page.locator("#chkTraffic")
        if traffic_checkbox.is_checked():
            traffic_checkbox.uncheck()
            print("[BİLGİ] Trafik sigortası seçimi kaldırıldı.")
        
        time.sleep(0.5)
        
        # 3️⃣ Plaka girişi
        print(f"\n[İŞLEM] Plaka bilgisi giriliyor: {data['plaka']}")
        
        plaka = data['plaka'].upper().strip()
        
        il_kodu = ""
        kalan_plaka = ""
        
        for i, char in enumerate(plaka):
            if char.isdigit():
                il_kodu += char
            else:
                kalan_plaka = plaka[i:]
                break
        
        if not il_kodu or not kalan_plaka:
            print(f"[HATA] Geçersiz plaka formatı: {data['plaka']}", file=sys.stderr)
            return False
        
        print(f"[BİLGİ] Plaka parçalandı -> İl: {il_kodu}, Kalan: {kalan_plaka}")
        
        plate_city_input = page.locator("#txtPlateNoCityNo")
        plate_city_input.click()
        plate_city_input.fill(il_kodu)
        time.sleep(0.3)
        print(f"[BAŞARILI] İl kodu girildi: {il_kodu}")
        
        plate_input = page.locator("#txtPlateNo")
        plate_input.click()
        plate_input.fill(kalan_plaka)
        time.sleep(0.3)
        print(f"[BAŞARILI] Plate entered: {kalan_plaka}")
        
        # 4️⃣ Ruhsat Seri No girişi
        print(f"\n[İŞLEM] Ruhsat seri no giriliyor: {data['ruhsat_seri_no']}")
        
        ruhsat = data['ruhsat_seri_no'].upper().strip()
        
        ruhsat_code = ""
        ruhsat_number = ""
        
        for i, char in enumerate(ruhsat):
            if char.isalpha():
                ruhsat_code += char
            else:
                ruhsat_number = ruhsat[i:]
                break
        
        if not ruhsat_code or not ruhsat_number:
            print(f"[HATA] Geçersiz ruhsat seri no formatı: {data['ruhsat_seri_no']}", file=sys.stderr)
            return False
        
        print(f"[BİLGİ] Ruhsat parçalandı -> Seri: {ruhsat_code}, No: {ruhsat_number}")
        
        egm_code_input = page.locator("#txtEGMNoCode")
        egm_code_input.click()
        egm_code_input.fill(ruhsat_code)
        time.sleep(0.3)
        print(f"[BAŞARILI] Ruhsat seri kodu girildi: {ruhsat_code}")
        
        egm_number_input = page.locator("#txtEGMNoNumber")
        egm_number_input.click()
        egm_number_input.fill(ruhsat_number)
        time.sleep(0.3)
        print(f"[BAŞARILI] Ruhsat numarası girildi: {ruhsat_number}")
        
        # 5️⃣ EGM Sorgula butonuna tıkla
        print("\n[İŞLEM] EGM sorgusu yapılıyor...")
        egm_search_button = page.locator("#btnSearchEgm")
        egm_search_button.click()
        print("[BAŞARILI] EGM Query button clicked.")
        
        print("[BİLGİ] EGM sorgu sonucu bekleniyor (5 saniye)...")
        time.sleep(5)
        
        # 6️⃣ Araç Modeli girişi
        if 'arac_modeli' in data and data['arac_modeli']:
            print(f"\n[İŞLEM] Araç modeli alanı kontrol ediliyor...")
            
            vehicle_model_input = page.locator("#txtVehicleModels")
            
            try:
                vehicle_model_input.wait_for(state="visible", timeout=3000)
                
                print(f"[BİLGİ] Araç modeli alanı bulundu. Dolduruluyor: {data['arac_modeli']}")
                
                vehicle_model_input.click()
                time.sleep(0.5)
                
                page.keyboard.press("Control+A")
                page.keyboard.press("Backspace")
                time.sleep(0.2)
                
                vehicle_model_input.type(data['arac_modeli'], delay=100)
                print(f"[BAŞARILI] Araç modeli written: {data['arac_modeli']}")
                
                time.sleep(2)
                print("[BİLGİ] Autocomplete listesi bekleniyor...")
                
                try:
                    autocomplete_item = page.locator("ul.ui-autocomplete li.ui-menu-item").first
                    if autocomplete_item.is_visible(timeout=3000):
                        autocomplete_item.click()
                        print("[BAŞARILI] Autocomplete listesinden ilk seçenek seçildi.")
                    else:
                        page.keyboard.press("Enter")
                        print("[BİLGİ] Enter tuşuna basıldı.")
                except:
                    page.keyboard.press("Enter")
                    print("[BİLGİ] Enter tuşuna basıldı (autocomplete bulunamadı).")
            
            except PlaywrightTimeoutError:
                print("[UYARI] Araç modeli giriş alanı bulunamadı veya zorunlu değil. Adım atlanıyor.")
            except Exception as e:
                print(f"[HATA] Araç modeli girişinde beklenmedik hata: {e}", file=sys.stderr)
        
        time.sleep(1)
        
        # 7️⃣ MESLEK SEÇİMİ - GÜNCELLENMİŞ VERSİYON
        if 'meslek' in data and data['meslek']:
            print(f"\n[İŞLEM] Meslek bilgisi giriliyor: {data['meslek']}")
            
            try:
                job_input = page.locator("#txtCascoNewEntranceJobCode")
                job_input.wait_for(state="visible", timeout=5000)
                
                job_input.click()
                time.sleep(0.5)
                
                page.keyboard.press("Control+A")
                page.keyboard.press("Backspace")
                time.sleep(0.2)
                
                job_input.type(data['meslek'], delay=100)
                print(f"[BAŞARILI] Meslek written: {data['meslek']}")
                
                time.sleep(2)
                print("[BİLGİ] Meslek autocomplete listesi bekleniyor...")
                
                try:
                    autocomplete_items = page.locator("ul.ui-autocomplete li.ui-menu-item")
                    
                    if autocomplete_items.count() > 0:
                        exact_match_found = False
                        for i in range(autocomplete_items.count()):
                            item_text = autocomplete_items.nth(i).text_content().strip()
                            if item_text.upper() == data['meslek'].upper():
                                autocomplete_items.nth(i).click()
                                print(f"[BAŞARILI] Meslek seçildi: {item_text}")
                                exact_match_found = True
                                break
                        
                        if not exact_match_found:
                            autocomplete_items.first.click()
                            first_item_text = autocomplete_items.first.text_content().strip()
                            print(f"[UYARI] Tam eşleşme bulunamadı, ilk meslek seçildi: {first_item_text}")
                    else:
                        page.keyboard.press("Enter")
                        print("[BİLGİ] Enter tuşuna basıldı (autocomplete bulunamadı).")
                        
                except Exception as e:
                    print(f"[HATA] Meslek autocomplete seçiminde hata: {e}")
                    page.keyboard.press("Enter")
                    print("[BİLGİ] Enter tuşuna basıldı (hata durumunda).")
                    
            except PlaywrightTimeoutError:
                print("[HATA] Meslek input alanı bulunamadı!", file=sys.stderr)
                return {'basarili': False, 'hata': 'Meslek alanı bulunamadı'}
            except Exception as e:
                print(f"[HATA] Meslek girişinde beklenmedik hata: {e}", file=sys.stderr)
                return {'basarili': False, 'hata': f'Meslek giriş hatası: {e}'}
        
        time.sleep(1)
        
        # 8️⃣ E-posta iletişim türünü seç
        print("\n[İŞLEM] E-posta iletişim türü seçiliyor...")
        
        email_radio = page.locator("#rblInsuredContactType_1")
        email_radio.check()
        print("[BAŞARILI] E-posta iletişim türü seçildi.")
        
        time.sleep(0.5)
        
        # 9️⃣ E-posta adresi gir
        print(f"\n[İŞLEM] E-posta adresi giriliyor: {data['email']}")
        
        email_input = page.locator("#txtInsuredEmailAddress")
        email_input.wait_for(state="visible", timeout=5000)
        email_input.click()
        email_input.fill(data['email'])
        print(f"[BAŞARILI] E-posta adresi girildi: {data['email']}")
        
        time.sleep(0.5)
        
        # 🔟 Teklif Oluştur butonuna tıkla
        print("\n[İŞLEM] 'Teklif Oluştur' butonuna tıklanıyor...")
        
        proposal_button = page.locator("#btnProposalCreate")
        proposal_button.wait_for(state="visible", timeout=5000)
        proposal_button.click()
        print("[BAŞARILI] 'Teklif Oluştur' butonuna tıklandı.")
        
        print("[BİLGİ] İlk teklif sonucu bekleniyor (3 saniye)...")
        time.sleep(3)
        
        # --- VADE BOŞLUĞU POP-UP'INI ELE ALMA ---
        
        VADE_BOSLUGU_POPUP_TITLE = 'h3:has-text("Teklifte vade boşluğu bulunmaktadır.")'
        ILK_BEYAN_RADIO_SELECTOR = '#rbVehicleDamaged_1'
        TAMAM_BUTTON_SELECTOR = 'button:has-text("Tamam")'

        print("\n[İŞLEM] Vade boşluğu pop-up'ı kontrol ediliyor...")
        
        try:
            page.wait_for_selector(VADE_BOSLUGU_POPUP_TITLE, timeout=5000, state='visible')
            print("[UYARI] Vade boşluğu beyan pop-up'ı yakalandı!")
            
            radio_button = page.locator(ILK_BEYAN_RADIO_SELECTOR)
            radio_button.check()
            print("[BAŞARILI] İlk beyan seçeneği işaretlendi.")
            time.sleep(0.5)
            
            print("[BİLGİ] Tamam butonu aranıyor...")
            
            tamam_button = page.locator(TAMAM_BUTTON_SELECTOR)
            
            if tamam_button.count() > 0:
                for i in range(tamam_button.count()):
                    if tamam_button.nth(i).is_visible():
                        tamam_button.nth(i).click()
                        print("[BAŞARILI] Pop-up 'Tamam' butonuna tıklandı.")
                        break
                else:
                    print("[HATA] Görünür 'Tamam' butonu bulunamadı!")
                    return {'basarili': False, 'hata': 'Vade boşluğu Tamam butonu görünür değil'}
            else:
                print("[HATA] 'Tamam' butonu bulunamadı!")
                return {'basarili': False, 'hata': 'Vade boşluğu Tamam butonu bulunamadı'}

            print("[BİLGİ] Teklifin tamamlanması bekleniyor (5 saniye)...")
            time.sleep(5)

        except PlaywrightTimeoutError:
            print("[BİLGİ] Vade boşluğu pop-up'ı görünmedi, normal akış devam ediyor.")
        except Exception as e:
            print(f"[HATA] Vade boşluğu pop-up'ı işlenirken beklenmedik hata: {e}", file=sys.stderr)
            traceback.print_exc()
            return {'basarili': False, 'hata': f'Vade boşluğu pop-up hatası: {e}'}
        
        # --- TEKLİF BİLGİLERİNİ ALMA ADIMI ---

        print("\n[İŞLEM] Teklif bilgileri alınıyor...")
        
        try:
            print("[BİLGİ] Sayfa aşağı kaydırılıyor...")
            page.evaluate("window.scrollBy(0, 700)")
            time.sleep(2)
            
            teklif_bilgileri = {}
            
            print("\n[İŞLEM] Standart Kasko Teklifi bilgileri alınıyor...")
            try:
                standart_teklif_no_element = page.locator("#lblCascoProposal2TransactionNo")
                if standart_teklif_no_element.count() > 0 and standart_teklif_no_element.is_visible():
                    standart_teklif_no = standart_teklif_no_element.text_content().strip()
                    teklif_bilgileri['standart_teklif_no'] = standart_teklif_no
                    print(f"[BAŞARILI] Standart Teklif No: {standart_teklif_no}")
                else:
                    teklif_bilgileri['standart_teklif_no'] = "Bulunamadı"
                    print("[UYARI] Standart Teklif No bulunamadı")
                
                standart_brut_prim_element = page.locator("#lblCascoProposal2GrossPremium")
                if standart_brut_prim_element.count() > 0 and standart_brut_prim_element.is_visible():
                    standart_brut_prim = standart_brut_prim_element.text_content().strip()
                    teklif_bilgileri['standart_brut_prim'] = standart_brut_prim
                    print(f"[BAŞARILI] Standart Brüt Prim: {standart_brut_prim}")
                else:
                    teklif_bilgileri['standart_brut_prim'] = "Bulunamadı"
                    print("[UYARI] Standart Brüt Prim bulunamadı")
                    
            except Exception as e:
                print(f"[HATA] Standart kasko teklifi bilgileri alınırken hata: {e}")
                teklif_bilgileri['standart_teklif_no'] = "Hata"
                teklif_bilgileri['standart_brut_prim'] = "Hata"
            
            print("\n[İŞLEM] Bütçe Dostu Kasko Teklifi bilgileri alınıyor...")
            try:
                butce_teklif_no_element = page.locator("#lblReasonablePriceCascoProposalTransactionNo")
                if butce_teklif_no_element.count() > 0 and butce_teklif_no_element.is_visible():
                    butce_teklif_no = butce_teklif_no_element.text_content().strip()
                    teklif_bilgileri['butce_dostu_teklif_no'] = butce_teklif_no
                    print(f"[BAŞARILI] Bütçe Dostu Teklif No: {butce_teklif_no}")
                else:
                    teklif_bilgileri['butce_dostu_teklif_no'] = "Bulunamadı"
                    print("[UYARI] Bütçe Dostu Teklif No bulunamadı")
                
                butce_brut_prim_element = page.locator("#lblReasonablePriceCascoProposalGrossPremium")
                if butce_brut_prim_element.count() > 0 and butce_brut_prim_element.is_visible():
                    butce_brut_prim = butce_brut_prim_element.text_content().strip()
                    teklif_bilgileri['butce_dostu_brut_prim'] = butce_brut_prim
                    print(f"[BAŞARILI] Bütçe Dostu Brüt Prim: {butce_brut_prim}")
                else:
                    teklif_bilgileri['butce_dostu_brut_prim'] = "Bulunamadı"
                    print("[UYARI] Bütçe Dostu Brüt Prim bulunamadı")
                    
            except Exception as e:
                print(f"[HATA] Bütçe dostu kasko teklifi bilgileri alınırken hata: {e}")
                teklif_bilgileri['butce_dostu_teklif_no'] = "Hata"
                teklif_bilgileri['butce_dostu_brut_prim'] = "Hata"
            
            print("\n[İŞLEM] Teklifler karşılaştırılıyor...")
            
            def temizle_prim_degeri(prim_str):
                if prim_str == "Bulunamadı" or prim_str == "Hata":
                    return float('inf')
                try:
                    temizlenmis = prim_str.replace('TL', '').replace('.', '').replace(',', '.').strip()
                    return float(temizlenmis)
                except:
                    return float('inf')
            
            standart_prim = temizle_prim_degeri(teklif_bilgileri.get('standart_brut_prim', 'Bulunamadı'))
            butce_prim = temizle_prim_degeri(teklif_bilgileri.get('butce_dostu_brut_prim', 'Bulunamadı'))
            
            if standart_prim <= butce_prim and standart_prim != float('inf'):
                en_uygun_teklif = "STANDART_KASKO"
                en_uygun_prim = teklif_bilgileri['standart_brut_prim']
                en_uygun_teklif_no = teklif_bilgileri['standart_teklif_no']
            elif butce_prim != float('inf'):
                en_uygun_teklif = "BÜTÇE_DOSTU_KASKO"
                en_uygun_prim = teklif_bilgileri['butce_dostu_brut_prim']
                en_uygun_teklif_no = teklif_bilgileri['butce_dostu_teklif_no']
            else:
                en_uygun_teklif = "TEKLİF_BULUNAMADI"
                en_uygun_prim = "Bulunamadı"
                en_uygun_teklif_no = "Bulunamadı"
            
            teklif_bilgileri['en_uygun_teklif'] = en_uygun_teklif
            teklif_bilgileri['en_uygun_prim'] = en_uygun_prim
            teklif_bilgileri['en_uygun_teklif_no'] = en_uygun_teklif_no
            
            print("\n" + "="*60)
            print(f"✅ KASKO SİGORTASI TEKLİFLERİ BAŞARIYLA OLUŞTURULDU!")
            print("="*60)
            print(f"📋 Standart Kasko:")
            print(f"  📄 Teklif No: {teklif_bilgileri.get('standart_teklif_no', 'Bulunamadı')}")
            print(f"  💰 Brüt Prim: {teklif_bilgileri.get('standart_brut_prim', 'Bulunamadı')}")
            print(f"\n📋 Bütçe Dostu Kasko:")
            print(f"  📄 Teklif No: {teklif_bilgileri.get('butce_dostu_teklif_no', 'Bulunamadı')}")
            print(f"  💰 Brüt Prim: {teklif_bilgileri.get('butce_dostu_brut_prim', 'Bulunamadı')}")
            print(f"\n🏆 En Uygun Teklif: {en_uygun_teklif}")
            print(f"  📄 Teklif No: {en_uygun_teklif_no}")
            print(f"  💰 Brüt Prim: {en_uygun_prim}")
            print("="*60)
            
            return {
                'basarili': True,
                'teklif_bilgileri': teklif_bilgileri,
                'standart_teklif_no': teklif_bilgileri.get('standart_teklif_no'),
                'standart_brut_prim': teklif_bilgileri.get('standart_brut_prim'),
                'butce_dostu_teklif_no': teklif_bilgileri.get('butce_dostu_teklif_no'),
                'butce_dostu_brut_prim': teklif_bilgileri.get('butce_dostu_brut_prim'),
                'en_uygun_teklif': en_uygun_teklif,
                'en_uygun_prim': en_uygun_prim,
                'en_uygun_teklif_no': en_uygun_teklif_no
            }

        except PlaywrightTimeoutError:
            print("[HATA] Kasko teklif sonuçları yüklenemedi (timeout)!", file=sys.stderr)
            return {'basarili': False, 'hata': 'Timeout - Teklif bilgileri bulunamadı'}
        except Exception as e:
            print(f"[HATA] Kasko teklif bilgileri alınırken hata oluştu: {e}", file=sys.stderr)
            traceback.print_exc()
            return {'basarili': False, 'hata': str(e)}
        
    except Exception as e:
        print(f"\n[HATA] Kasko sigortası işlemi sırasında hata oluştu: {e}", file=sys.stderr)
        traceback.print_exc()
        return {'basarili': False, 'hata': str(e)}

def process_saglik_sigortasi(page, data):
    """
    Tamamlayıcı Sağlık Sigortası için teklif sürecini tamamlar.
    """
    print("\n" + "="*60)
    print("TAMAMLAYICI SAĞLIK SİGORTASI İŞLEMİ BAŞLATILIYOR")
    print("="*60)
    
    try:
        # 1️⃣ SAĞLIK MENÜSÜNE TIKLA
        print("\n[İŞLEM] Sağlık menüsüne tıklanıyor...")
        
        saglik_menu = page.locator('a.genel.aMenu:has-text("Sağlık")')
        saglik_menu.wait_for(state="visible", timeout=10000)
        saglik_menu.click()
        print("[BAŞARILI] Sağlık menu clicked.")
        
        time.sleep(2)
        
        # 2️⃣ TAMAMLAYICI SAĞLIK SEKMESİNE TIKLA
        print("\n[İŞLEM] Tamamlayıcı Sağlık sekmesine tıklanıyor...")
        
        tamamlayici_saglik_tab = page.locator('#btnSupplementaryHealthInputTab')
        tamamlayici_saglik_tab.wait_for(state="visible", timeout=10000)
        tamamlayici_saglik_tab.click()
        print("[BAŞARILI] Tamamlayıcı Sağlık sekmesine tıklandı.")
        
        print("[BİLGİ] Tamamlayıcı Sağlık formu yükleniyor...")
        time.sleep(5)
        
        # 3️⃣ TCKN GİRİŞİ
        if not fill_tckn_field(page, data['tckn']):
            return {'basarili': False, 'hata': 'TCKN girişi başarısız'}
        
        time.sleep(2)
        
        # 4️⃣ DOĞUM TARİHİ GİRİŞİ - FORMAT DÜZELTMESİ (GG/AA/YYYY)
        if 'dogum_tarihi' in data and data['dogum_tarihi']:
            print(f"\n[İŞLEM] Doğum tarihi kontrol ediliyor: {data['dogum_tarihi']}")
            
            try:
                dogum_tarihi_input = page.locator("#txtAllProductsBirthDate")
                if dogum_tarihi_input.count() > 0:
                    current_value = dogum_tarihi_input.input_value()
                    
                    dogum_tarihi_formatted = data['dogum_tarihi']
                    if '.' in dogum_tarihi_formatted:
                        dogum_tarihi_formatted = dogum_tarihi_formatted.replace('.', '/')
                    elif '-' in dogum_tarihi_formatted:
                        dogum_tarihi_formatted = dogum_tarihi_formatted.replace('-', '/')
                    
                    print(f"[BİLGİ] Doğum tarihi formatı: {dogum_tarihi_formatted}")
                    
                    if not current_value.strip() or current_value.strip() == '01/01/0001':
                        dogum_tarihi_input.fill(dogum_tarihi_formatted)
                        print(f"[BAŞARILI] Doğum tarihi girildi: {dogum_tarihi_formatted}")
                    else:
                        print(f"[BİLGİ] Doğum tarihi zaten dolu: {current_value}, değiştirilmiyor.")
                else:
                    print("[UYARI] Doğum tarihi alanı bulunamadı")
                    
            except Exception as e:
                print(f"[UYARI] Doğum tarihi girişinde hata: {e}")
        
        time.sleep(1)
        
        print("\n[İŞLEM] Poliçe tipi kontrol ediliyor: Yeni İş")
        
        try:
            yeni_is_radio = page.locator("#divSupplementaryHealthHospitalPolicyType #rblPolicyType_0")
            
            if yeni_is_radio.count() > 0:
                is_checked = yeni_is_radio.is_checked()
                
                if not is_checked:
                    yeni_is_label = page.locator('#divSupplementaryHealthHospitalPolicyType label[for="rblPolicyType_0"]')
                    if yeni_is_label.count() > 0:
                        yeni_is_label.click()
                        print("[BAŞARILI] 'Yeni İş' poliçe tipi seçildi.")
                    else:
                        print("[UYARI] 'Yeni İş' label'ı bulunamadı")
                else:
                    print("[BİLGİ] 'Yeni İş' zaten seçili")
            else:
                print("[UYARI] Tamamlayıcı Sağlık için poliçe tipi radio butonu bulunamadı")
                
        except Exception as e:
            print(f"[UYARI] Poliçe tipi seçiminde hata: {e}")
        
        time.sleep(1)
        
        # 6️⃣ PRİM TİPİ SEÇİMİ
        if 'prim_tipi' in data and data['prim_tipi']:
            print(f"\n[İŞLEM] Prim tipi seçiliyor: {data['prim_tipi']}")
            
            try:
                prim_tipi_select = page.locator("#ddlSupplementaryHealthPrimTypes")
                if prim_tipi_select.count() > 0:
                    current_value = prim_tipi_select.input_value()
                    if current_value == "-1":
                        prim_tipi_select.select_option(label=data['prim_tipi'])
                        print(f"[BAŞARILI] Prim tipi seçildi: {data['prim_tipi']}")
                    else:
                        print(f"[BİLGİ] Prim tipi zaten seçili: {current_value}")
                else:
                    print("[UYARI] Prim tipi dropdown'ı bulunamadı")
                    
            except Exception as e:
                print(f"[HATA] Prim tipi seçilemedi: {e}")
                return {'basarili': False, 'hata': f'Prim tipi seçilemedi: {e}'}
        
        time.sleep(1)
        
        # 7️⃣ TEMİNAT SAYISI SEÇİMİ
        if 'teminat_sayisi' in data and data['teminat_sayisi']:
            print(f"\n[İŞLEM] Teminat sayısı seçiliyor: {data['teminat_sayisi']}")
            
            try:
                teminat_sayisi_select = page.locator("#ddlSupplementaryHealthCoverNumbers")
                if teminat_sayisi_select.count() > 0:
                    teminat_sayisi = str(data['teminat_sayisi'])
                    
                    teminat_sayisi_select.select_option(value=teminat_sayisi)
                    print(f"[BAŞARILI] Teminat sayısı seçildi: {data['teminat_sayisi']}")
                else:
                    print("[UYARI] Teminat sayısı dropdown'ı bulunamadı")
                    
            except Exception as e:
                print(f"[HATA] Teminat sayısı seçilemedi: {e}")
                return {'basarili': False, 'hata': f'Teminat sayısı seçilemedi: {e}'}
        
        time.sleep(1)
        
        # 8️⃣ MESLEK SEÇİMİ
        if 'meslek_saglik' in data and data['meslek_saglik']:
            print(f"\n[İŞLEM] Meslek seçiliyor: {data['meslek_saglik']}")
            
            try:
                meslek_select = page.locator("#ddlSupplementaryHealthProfession")
                if meslek_select.count() > 0:
                    meslek_select.wait_for(state="visible", timeout=5000)
                    
                    options = meslek_select.locator("option")
                    option_found = False
                    
                    for i in range(options.count()):
                        option_text = options.nth(i).text_content().strip()
                        if option_text == data['meslek_saglik']:
                            option_value = options.nth(i).get_attribute("value")
                            meslek_select.select_option(value=option_value)
                            print(f"[BAŞARILI] Meslek seçildi: {data['meslek_saglik']} (değer: {option_value})")
                            option_found = True
                            break
                    
                    if not option_found:
                        print(f"[HATA] Meslek seçeneği bulunamadı: {data['meslek_saglik']}")
                        return {'basarili': False, 'hata': f'Meslek seçeneği bulunamadı: {data["meslek_saglik"]}'}
                        
                else:
                    print("[UYARI] Meslek dropdown'ı bulunamadı")
                    return {'basarili': False, 'hata': 'Meslek dropdown bulunamadı'}
                    
            except Exception as e:
                print(f"[HATA] Meslek seçilemedi: {e}")
                return {'basarili': False, 'hata': f'Meslek seçilemedi: {e}'}
        
        time.sleep(1)
        
        # 9️⃣ TEKLİF OLUŞTUR BUTONUNA TIKLA
        print("\n[İŞLEM] 'Teklif Oluştur' butonuna tıklanıyor...")
        
        try:
            proposal_button = page.locator("#btnProposalCreate")
            proposal_button.wait_for(state="visible", timeout=5000)
            proposal_button.click()
            print("[BAŞARILI] 'Teklif Oluştur' butonuna tıklandı.")
        except Exception as e:
            print(f"[HATA] Teklif oluştur butonuna tıklanamadı: {e}")
            return {'basarili': False, 'hata': f'Teklif oluştur butonuna tıklanamadı: {e}'}
        
        print("[BİLGİ] Bilgilendirme pop-up'ı bekleniyor...")
        time.sleep(5)
        
        # 🔟 BİLGİLENDİRME POP-UP'INDA DEVAM BUTONUNA TIKLA
        print("\n[İŞLEM] Bilgilendirme pop-up'ında 'Devam' butonuna tıklanıyor...")
        
        try:
            devam_selectors = [
                '#btnInfoPopup',
                'button:has-text("Devam")',
                '.ui-dialog-buttonset button:has-text("Devam")'
            ]
            
            devam_clicked = False
            for selector in devam_selectors:
                try:
                    devam_button = page.locator(selector)
                    if devam_button.count() > 0 and devam_button.is_visible():
                        devam_button.click()
                        print("[BAŞARILI] 'Devam' butonuna tıklandı.")
                        devam_clicked = True
                        break
                except:
                    continue
            
            if not devam_clicked:
                print("[BİLGİ] Devam butonu bulunamadı, normal akışa continuing...")
                
        except Exception as e:
            print(f"[UYARI] Devam butonu işlenirken hata: {e}")
        
        print("[BİLGİ] Teklif oluşturma işlemi bekleniyor (10 saniye)...")
        time.sleep(10)
        
        # 1️⃣1️⃣ TEKLİF BİLGİLERİNİ AL
        print("\n[İŞLEM] Teklif bilgileri alınıyor...")
        
        teklif_bilgileri = {}
        
        try:
            teklif_no_element = page.locator('b:has-text("Teklif No :")')
            if teklif_no_element.count() > 0:
                teklif_no_text = teklif_no_element.text_content().strip()
                teklif_no = teklif_no_text.replace("Teklif No :", "").strip()
                teklif_bilgileri['teklif_no'] = teklif_no
                print(f"[BAŞARILI] Teklif No: {teklif_no}")
            else:
                teklif_bilgileri['teklif_no'] = "Bulunamadı"
                print("[UYARI] Teklif numarası bulunamadı")
            
            toplam_prim_element = page.locator('#tdMainProposalPrimOnly804, label[id*="tdMainProposalPrimOnly"]')
            if toplam_prim_element.count() > 0:
                toplam_prim = toplam_prim_element.text_content().strip()
                teklif_bilgileri['toplam_prim'] = toplam_prim
                print(f"[BAŞARILI] Toplam Prim: {toplam_prim}")
            else:
                teklif_bilgileri['toplam_prim'] = "Bulunamadı"
                print("[UYARI] Toplam prim bulunamadı")
            
            komisyon_element = page.locator('#komisyonHd, td[id="komisyonHd"]')
            if komisyon_element.count() > 0:
                komisyon = komisyon_element.text_content().strip()
                teklif_bilgileri['komisyon'] = komisyon
                print(f"[BAŞARILI] Komisyon: {komisyon}")
            else:
                teklif_bilgileri['komisyon'] = "Bulunamadı"
                print("[UYARI] Komisyon bulunamadı")
            
            durum_element = page.locator('#supplementaryHealthProposalStatusName, b[id="supplementaryHealthProposalStatusName"]')
            if durum_element.count() > 0:
                durum = durum_element.text_content().strip()
                teklif_bilgileri['durum'] = durum
                print(f"[BAŞARILI] Durum: {durum}")
            else:
                teklif_bilgileri['durum'] = "Bulunamadı"
                print("[UYARI] Durum bulunamadı")
                
        except Exception as e:
            print(f"[UYARI] Teklif bilgileri alınırken hata: {e}")
        
        print("\n" + "="*60)
        print(f"✅ TAMAMLAYICI SAĞLIK SİGORTASI TEKLİFİ BAŞARIYLA OLUŞTURULDU!")
        print("="*60)
        if teklif_bilgileri.get('teklif_no') != "Bulunamadı":
            print(f"📄 Teklif No: {teklif_bilgileri.get('teklif_no')}")
        if teklif_bilgileri.get('toplam_prim') != "Bulunamadı":
            print(f"💰 Toplam Prim: {teklif_bilgileri.get('toplam_prim')}")
        if teklif_bilgileri.get('komisyon') != "Bulunamadı":
            print(f"📊 Komisyon: {teklif_bilgileri.get('komisyon')}")
        if teklif_bilgileri.get('durum') != "Bulunamadı":
            print(f"📈 Durum: {teklif_bilgileri.get('durum')}")
        print("="*60)
        
        return {
            'basarili': True,
            'mesaj': 'Tamamlayıcı Sağlık sigortası teklifi oluşturuldu',
            'teklif_bilgileri': teklif_bilgileri
        }
        
    except Exception as e:
        print(f"\n[HATA] Tamamlayıcı Sağlık sigortası işlemi sırasında hata oluştu: {e}", file=sys.stderr)
        traceback.print_exc()
        return {'basarili': False, 'hata': str(e)}

def process_dask_sigortasi(page, data):
    """
    DASK (Zorunlu Deprem Sigortası) için YENİLEME sürecini tamamlar.
    """
    print("\n" + "="*60)
    print("DASK SİGORTASI (YENİLEME) İŞLEMİ BAŞLATILIYOR")
    print("="*60)
    
    try:
        # 1️⃣ BİREYSEL SEKMEYE TIKLA
        print("\n[İŞLEM] 'Bireysel' sekmesine tıklanıyor...")
        
        bireysel_tab = page.locator('em.neoSansMedium:has-text("Bireysel")')
        bireysel_tab.wait_for(state="visible", timeout=10000)
        bireysel_tab.click()
        print("[BAŞARILI] 'Bireysel' sekmesine tıklandı.")
        
        print("[BİLGİ] Bireysel menü yükleniyor (2 saniye)...")
        time.sleep(2)
        
        # 2️⃣ DASK SEKMESINE TIKLA
        print("\n[İŞLEM] 'Dask' sekmesine tıklanıyor...")
        
        dask_tab = page.locator('a.tabDask#btnDaskInputTab')
        dask_tab.wait_for(state="visible", timeout=10000)
        dask_tab.click()
        print("[BAŞARILI] 'Dask' sekmesine tıklandı.")
        
        print("[BİLGİ] Menü kapatılıyor...")
        time.sleep(1)
        
        try:
            open_menu = page.locator("ul.open_tab")
            if open_menu.count() > 0:
                print("[BİLGİ] Açık menü bulundu, dışarıya tıklanarak kapatılıyor...")
                page.click("body", position={"x": 50, "y": 100})
                time.sleep(1)
        except:
            pass
        
        print("[BİLGİ] DASK formu yükleniyor...")
        time.sleep(2)
        
        # 3️⃣ DASK POLİÇE NUMARASI GİRİŞİ
        print(f"\n[İŞLEM] DASK poliçe numarası giriliyor: {data['dask_police_no']}")
        
        try:
            dask_police_input = page.locator("#txtDaskOldPolicyNumber")
            dask_police_input.wait_for(state="visible", timeout=5000)
            
            dask_police_input.scroll_into_view_if_needed()
            time.sleep(0.5)
            
            dask_police_input.click()
            time.sleep(0.3)
            dask_police_input.fill(data['dask_police_no'])
            print(f"[BAŞARILI] DASK poliçe numarası girildi: {data['dask_police_no']}")
        except Exception as e:
            print(f"[HATA] DASK poliçe numarası girişinde hata: {e}")
            return {'basarili': False, 'hata': f'DASK poliçe numarası: {e}'}
        
        time.sleep(0.5)
        
        # 4️⃣ TCKN GİRİŞİ
        print(f"\n[İŞLEM] TCKN giriliyor: {data['tckn']}")
        try:
            tckn_element = page.locator("#txtIdentityOrTaxNo")
            tckn_element.wait_for(state="visible", timeout=5000)
            
            tckn_element.scroll_into_view_if_needed()
            time.sleep(0.3)
            
            tckn_element.click()
            time.sleep(0.3)
            
            page.keyboard.press("Control+A")
            time.sleep(0.1)
            page.keyboard.press("Delete")
            time.sleep(0.2)
            
            tckn_element.type(data['tckn'], delay=50)
            time.sleep(0.5)
            
            current_value = tckn_element.input_value()
            if current_value == data['tckn']:
                print(f"[BAŞARILI] TCKN başarıyla girildi: {data['tckn']}")
                page.click("body", position={"x": 50, "y": 100})
            else:
                print(f"[UYARI] TCKN değeri eşleşmiyor. Beklenen: {data['tckn']}, Bulunan: {current_value}")
                
        except Exception as e:
            print(f"[HATA] TCKN girişinde hata: {e}", file=sys.stderr)
            return {'basarili': False, 'hata': f'TCKN girişi başarısız: {e}'}
        
        time.sleep(1)
        
        # 5️⃣ DOĞUM TARİHİ KONTROLÜ VE GİRİŞİ
        print("\n[İŞLEM] Doğum tarihi kontrol ediliyor...")
        
        try:
            birth_date_input = page.locator("#txtDaskBirthDate")
            
            if birth_date_input.count() > 0:
                birth_date_input.wait_for(state="visible", timeout=3000)
                
                current_birth_date = birth_date_input.input_value()
                
                print(f"[BİLGİ] Doğum tarihi alanında var olan değer: '{current_birth_date}'")
                
                if not current_birth_date or current_birth_date.strip() == "" or current_birth_date.strip() == "01/01/0001":
                    if 'dogum_tarihi' in data and data['dogum_tarihi']:
                        print(f"[İŞLEM] Doğum tarihi boş, giriliyor: {data['dogum_tarihi']}")
                        
                        birth_date_input.scroll_into_view_if_needed()
                        birth_date_input.click()
                        time.sleep(0.2)
                        birth_date_input.type(data['dogum_tarihi'], delay=50)
                        print(f"[BAŞARILI] Doğum tarihi girildi: {data['dogum_tarihi']}")
                    else:
                        print("[UYARI] Doğum tarihi alanı boş ama veri sağlanmadı")
                else:
                    print(f"[BİLGİ] Doğum tarihi zaten dolu '{current_birth_date}', girişi atlanıyor")
                    
        except Exception as e:
            print(f"[UYARI] Doğum tarihi kontrolünde hata: {e}")
        
        time.sleep(3)
        
        # 6️⃣ TEKLİF OLUŞTUR BUTONUNA TIKLA
        print("\n[İŞLEM] 'Teklif Oluştur' butonuna tıklanıyor...")
        
        try:
            proposal_button = page.locator("#btnProposalCreate")
            proposal_button.wait_for(state="visible", timeout=5000)
            proposal_button.scroll_into_view_if_needed()
            
            is_disabled = proposal_button.get_attribute("disabled")
            
            if is_disabled:
                print("[BİLGİ] Buton henüz aktif değil, 3 saniye bekleniyor...")
                time.sleep(3)
            
            proposal_button.click()
            print("[BAŞARILI] 'Teklif Oluştur' butonuna tıklandı.")
            
        except Exception as e:
            print(f"[HATA] Teklif oluştur butonuna tıklanamadı: {e}")
            return {'basarili': False, 'hata': f'Teklif oluştur butonuna tıklanamadı: {e}'}
        
        # 7️⃣ TELEFON POPUP'I KONTROLÜ VE İŞLEMİ
        print("\n[İŞLEM] Telefon popup'ı kontrol ediliyor...")
        time.sleep(2)
        
        try:
            mobile_popup = page.locator("#divMobilePopup")
            
            if mobile_popup.count() > 0:
                mobile_popup.wait_for(state="visible", timeout=5000)
                print("[BİLGİ] Telefon popup'ı bulundu!")
                
                phone_input = page.locator("#txtMobilePhoneInPopup")
                phone_input.wait_for(state="visible", timeout=3000)
                
                current_phone = phone_input.input_value()
                print(f"[BİLGİ] Telefon alanında mevcut değer: '{current_phone}'")
                
                if not current_phone or current_phone.strip() == "" or current_phone.strip() == "905":
                    if 'telefon' in data and data['telefon']:
                        print(f"[İŞLEM] Telefon numarası giriliyor: {data['telefon']}")
                        
                        phone_input.click()
                        time.sleep(0.2)
                        phone_input.triple_click()
                        time.sleep(0.1)
                        phone_input.type(data['telefon'], delay=50)
                        print(f"[BAŞARILI] Telefon numarası girildi: {data['telefon']}")
                        
                        time.sleep(0.5)
                    else:
                        print("[UYARI] Telefon numarası alanı boş ama veri sağlanmadı")
                        print("[BİLGİ] Popup TAMAM butonuna tıklanacak (boş şekilde)")
                else:
                    print(f"[BİLGİ] Telefon numarası zaten dolu: {current_phone}")
                
                print("[İŞLEM] TAMAM butonuna tıklanıyor...")
                
                dialog_buttons = page.locator(".ui-dialog-buttonset button")
                
                if dialog_buttons.count() >= 2:
                    dialog_buttons.nth(1).click()
                    print("[BAŞARILI] TAMAM butonuna tıklandı.")
                else:
                    print("[UYARI] TAMAM butonu bulunamadı, başka yöntem deneniyor...")
                    tamam_button = page.locator('button:has-text("Tamam")')
                    if tamam_button.count() > 0:
                        tamam_button.click()
                        print("[BAŞARILI] TAMAM butonuna tıklandı (alternatif).")
                
                time.sleep(2)
                
            else:
                print("[BİLGİ] Telefon popup'ı görünmedi, continuing...")
                
        except PlaywrightTimeoutError:
            print("[UYARI] Telefon popup'ı timeout (görünmedi), continuing...")
        except Exception as e:
            print(f"[UYARI] Telefon popup'ı işlenirken hata: {e}")
        
        print("[BİLGİ] Teklif oluşturma işlemi bekleniyor (10 saniye)...")
        time.sleep(10)
        
        # 8️⃣ TEKLİF BİLGİLERİNİ AL
        print("\n[İŞLEM] DASK teklif bilgileri alınıyor...")
        
        teklif_bilgileri = {}
        
        try:
            teklif_no_element = page.locator("#lblDaskProposalTransactionNo")
            if teklif_no_element.count() > 0:
                teklif_no = teklif_no_element.text_content().strip()
                teklif_bilgileri['teklif_no'] = teklif_no
                print(f"[BAŞARILI] Teklif No: {teklif_no}")
            else:
                teklif_bilgileri['teklif_no'] = "Bulunamadı"
                print("[UYARI] Teklif numarası bulunamadı")
            
            brut_prim_element = page.locator("#lblDaskProposalGrossPremium")
            if brut_prim_element.count() > 0:
                brut_prim = brut_prim_element.text_content().strip()
                teklif_bilgileri['brut_prim'] = brut_prim
                print(f"[BAŞARILI] Brüt Prim: {brut_prim}")
            else:
                teklif_bilgileri['brut_prim'] = "Bulunamadı"
                print("[UYARI] Brüt prim bulunamadı")
            
            teklif_bilgileri['dask_police_no'] = data.get('dask_police_no', 'Bilinmiyor')
            print(f"[BİLGİ] DASK Poliçe No: {teklif_bilgileri['dask_police_no']}")
            
            teklif_bilgileri['tckn'] = data.get('tckn', 'Bilinmiyor')
            print(f"[BİLGİ] TC Kimlik No: {teklif_bilgileri['tckn']}")
            
        except Exception as e:
            print(f"[UYARI] Teklif bilgileri alınırken hata: {e}")
        
        print("\n" + "="*60)
        print("📋 TEKLIF BİLGİLERİ ÖZETI:")
        print("="*60)
        print(f"📄 Teklif No: {teklif_bilgileri.get('teklif_no', 'Bulunamadı')}")
        print(f"💰 Brüt Prim: {teklif_bilgileri.get('brut_prim', 'Bulunamadı')}")
        print(f"🆔 DASK Poliçe No: {teklif_bilgileri.get('dask_police_no', 'Bilinmiyor')}")
        print(f"👤 TC No: {teklif_bilgileri.get('tckn', 'Bilinmiyor')}")
        print("="*60)
        
        return {
            'basarili': True,
            'mesaj': 'DASK teklifi başarıyla oluşturuldu',
            'teklif_no': teklif_bilgileri.get('teklif_no'),
            'brut_prim': teklif_bilgileri.get('brut_prim'),
            'dask_police_no': teklif_bilgileri.get('dask_police_no'),
            'tckn': teklif_bilgileri.get('tckn'),
            'teklif_bilgileri': teklif_bilgileri
        }
        
    except Exception as e:
        print(f"\n[HATA] DASK sigortası işlemi sırasında hata oluştu: {e}", file=sys.stderr)
        traceback.print_exc()
        return {'basarili': False, 'hata': str(e)}


# ====================================================================
# YENİ EKLENEN FONKSİYON
# ====================================================================
def process_dask_yeni_police(page, data):
    """
    DASK (Zorunlu Deprem Sigortası) için YENİ POLİÇE sürecini tamamlar.
    Bu fonksiyon DASK Adres Codeu (UAVT) kullanır.
    """
    print("\n" + "="*60)
    print("DASK SİGORTASI (YENİ POLİÇE) İŞLEMİ BAŞLATILIYOR")
    print("="*60)
    
    try:
        # 1️⃣ BİREYSEL SEKMEYE TIKLA
        print("\n[İŞLEM] 'Bireysel' sekmesine tıklanıyor...")
        
        bireysel_tab = page.locator('em.neoSansMedium:has-text("Bireysel")')
        bireysel_tab.wait_for(state="visible", timeout=10000)
        bireysel_tab.click()
        print("[BAŞARILI] 'Bireysel' sekmesine tıklandı.")
        
        print("[BİLGİ] Bireysel menü yükleniyor (2 saniye)...")
        time.sleep(2)
        
        # 2️⃣ DASK SEKMESINE TIKLA
        print("\n[İŞLEM] 'Dask' sekmesine tıklanıyor...")
        
        dask_tab = page.locator('a.tabDask#btnDaskInputTab')
        dask_tab.wait_for(state="visible", timeout=10000)
        dask_tab.click()
        print("[BAŞARILI] 'Dask' sekmesine tıklandı.")
        
        print("[BİLGİ] Menü kapatılıyor...")
        time.sleep(1)
        
        try:
            open_menu = page.locator("ul.open_tab")
            if open_menu.count() > 0:
                print("[BİLGİ] Açık menü bulundu, dışarıya tıklanarak kapatılıyor...")
                page.click("body", position={"x": 50, "y": 100})
                time.sleep(1)
        except:
            pass
        
        print("[BİLGİ] DASK formu yükleniyor...")
        time.sleep(2)
        
        # 3️⃣ POLİÇE TİPİNİ 'YENİ İŞ' OLARAK SEÇ
        print("\n[İŞLEM] Poliçe tipi 'Yeni İş' olarak seçiliyor...")
        try:
            # 'Yeni İş' radio butonunu (genellikle ilki) seç
            yeni_is_radio = page.locator("#rblDaskNewOrRenewal_1")
            yeni_is_radio.check()
            print("[BAŞARILI] 'Yeni İş' poliçe tipi seçildi.")
        except Exception as e:
            print(f"[HATA] 'Yeni İş' poliçe tipi seçilemedi: {e}", file=sys.stderr)
            return {'basarili': False, 'hata': f'Yeni İş seçilemedi: {e}'}

        time.sleep(3)

        # 4️⃣ DASK ADRES KODU (UAVT) GİRİŞİ
        print(f"\n[İŞLEM] DASK Adres Codeu (UAVT) giriliyor: {data['dask_adres_kodu']}")
        
        try:
            adres_kodu_input = page.locator("#txtUAVTAddressNo")
            adres_kodu_input.wait_for(state="visible", timeout=5000)
            
            adres_kodu_input.scroll_into_view_if_needed()
            time.sleep(0.5)
            
            adres_kodu_input.click()
            time.sleep(0.3)
            adres_kodu_input.fill(data['dask_adres_kodu'])
            print(f"[BAŞARILI] DASK Adres Codeu girildi: {data['dask_adres_kodu']}")
        except Exception as e:
            print(f"[HATA] DASK Adres Codeu girişinde hata: {e}")
            return {'basarili': False, 'hata': f'DASK Adres Codeu: {e}'}
        
        time.sleep(0.5)

        # 5️⃣ ADRES SORGULA BUTONUNA TIKLA
        print("\n[İŞLEM] Adres sorgula butonuna tıklanıyor...")
        try:
            adres_sorgula_button = page.locator("#btnSearchWithUAVTAddressNo")
            adres_sorgula_button.click()
            print("[BAŞARILI] Adres sorgulama başlatıldı. 5 saniye bekleniyor...")
            time.sleep(5)
        except Exception as e:
            print(f"[HATA] Adres sorgula butonuna tıklanamadı: {e}", file=sys.stderr)
            return {'basarili': False, 'hata': f'Adres sorgulanamadı: {e}'}


        # 6️⃣ TCKN GİRİŞİ (Adres sorgulandıktan sonra)
        # Bu kısım yenileme ile aynı olduğu için mevcut fill_tckn_field fonksiyonu kullanılabilir.
        if not fill_tckn_field(page, data['tckn']):
             return {'basarili': False, 'hata': 'TCKN girişi başarısız'}

        time.sleep(1)
        
        # ... (Diğer adımlar yenileme ile aynı) ...
        # Doğum tarihi, Teklif Oluştur, Telefon Pop-up'ı ve Sonuç Alma adımları aynıdır.

        # 7️⃣ DOĞUM TARİHİ KONTROLÜ VE GİRİŞİ
        print("\n[İŞLEM] Doğum tarihi kontrol ediliyor...")
        
        try:
            birth_date_input = page.locator("#txtDaskBirthDate")
            
            if birth_date_input.count() > 0:
                birth_date_input.wait_for(state="visible", timeout=3000)
                
                current_birth_date = birth_date_input.input_value()
                
                print(f"[BİLGİ] Doğum tarihi alanında var olan değer: '{current_birth_date}'")
                
                if not current_birth_date or current_birth_date.strip() == "" or current_birth_date.strip() == "01/01/0001":
                    if 'dogum_tarihi' in data and data['dogum_tarihi']:
                        print(f"[İŞLEM] Doğum tarihi boş, giriliyor: {data['dogum_tarihi']}")
                        
                        birth_date_input.scroll_into_view_if_needed()
                        birth_date_input.click()
                        time.sleep(0.2)
                        birth_date_input.type(data['dogum_tarihi'], delay=50)
                        print(f"[BAŞARILI] Doğum tarihi girildi: {data['dogum_tarihi']}")
                    else:
                        print("[UYARI] Doğum tarihi alanı boş ama veri sağlanmadı")
                else:
                    print(f"[BİLGİ] Doğum tarihi zaten dolu '{current_birth_date}', girişi atlanıyor")
                    
        except Exception as e:
            print(f"[UYARI] Doğum tarihi kontrolünde hata: {e}")
        
        time.sleep(3)
        
        # 8️⃣ TEKLİF OLUŞTUR BUTONUNA TIKLA
        print("\n[İŞLEM] 'Teklif Oluştur' butonuna tıklanıyor...")
        
        try:
            proposal_button = page.locator("#btnProposalCreate")
            proposal_button.wait_for(state="visible", timeout=5000)
            proposal_button.scroll_into_view_if_needed()
            
            is_disabled = proposal_button.get_attribute("disabled")
            
            if is_disabled:
                print("[BİLGİ] Buton henüz aktif değil, 3 saniye bekleniyor...")
                time.sleep(3)
            
            proposal_button.click()
            print("[BAŞARILI] 'Teklif Oluştur' butonuna tıklandı.")
            
        except Exception as e:
            print(f"[HATA] Teklif oluştur butonuna tıklanamadı: {e}")
            return {'basarili': False, 'hata': f'Teklif oluştur butonuna tıklanamadı: {e}'}
        
        # 9️⃣ TELEFON POPUP'I KONTROLÜ VE İŞLEMİ
        print("\n[İŞLEM] Telefon popup'ı kontrol ediliyor...")
        time.sleep(2)
        
        try:
            mobile_popup = page.locator("#divMobilePopup")
            
            if mobile_popup.count() > 0:
                mobile_popup.wait_for(state="visible", timeout=5000)
                print("[BİLGİ] Telefon popup'ı bulundu!")
                
                phone_input = page.locator("#txtMobilePhoneInPopup")
                phone_input.wait_for(state="visible", timeout=3000)
                
                current_phone = phone_input.input_value()
                print(f"[BİLGİ] Telefon alanında mevcut değer: '{current_phone}'")
                
                if not current_phone or current_phone.strip() == "" or current_phone.strip() == "905":
                    if 'telefon' in data and data['telefon']:
                        print(f"[İŞLEM] Telefon numarası giriliyor: {data['telefon']}")
                        
                        phone_input.click()
                        time.sleep(0.2)
                        phone_input.triple_click()
                        time.sleep(0.1)
                        phone_input.type(data['telefon'], delay=50)
                        print(f"[BAŞARILI] Telefon numarası girildi: {data['telefon']}")
                        
                        time.sleep(0.5)
                    else:
                        print("[UYARI] Telefon numarası alanı boş ama veri sağlanmadı")
                        print("[BİLGİ] Popup TAMAM butonuna tıklanacak (boş şekilde)")
                else:
                    print(f"[BİLGİ] Telefon numarası zaten dolu: {current_phone}")
                
                print("[İŞLEM] TAMAM butonuna tıklanıyor...")
                
                dialog_buttons = page.locator(".ui-dialog-buttonset button")
                
                if dialog_buttons.count() >= 2:
                    dialog_buttons.nth(1).click()
                    print("[BAŞARILI] TAMAM butonuna tıklandı.")
                else:
                    print("[UYARI] TAMAM butonu bulunamadı, başka yöntem deneniyor...")
                    tamam_button = page.locator('button:has-text("Tamam")')
                    if tamam_button.count() > 0:
                        tamam_button.click()
                        print("[BAŞARILI] TAMAM butonuna tıklandı (alternatif).")
                
                time.sleep(2)
                
            else:
                print("[BİLGİ] Telefon popup'ı görünmedi, continuing...")
                
        except PlaywrightTimeoutError:
            print("[UYARI] Telefon popup'ı timeout (görünmedi), continuing...")
        except Exception as e:
            print(f"[UYARI] Telefon popup'ı işlenirken hata: {e}")
        
        print("[BİLGİ] Teklif oluşturma işlemi bekleniyor (10 saniye)...")
        time.sleep(10)
        
        # 1️⃣0️⃣ TEKLİF BİLGİLERİNİ AL
        print("\n[İŞLEM] DASK teklif bilgileri alınıyor...")
        
        teklif_bilgileri = {}
        
        try:
            teklif_no_element = page.locator("#lblDaskProposalTransactionNo")
            if teklif_no_element.count() > 0:
                teklif_no = teklif_no_element.text_content().strip()
                teklif_bilgileri['teklif_no'] = teklif_no
                print(f"[BAŞARILI] Teklif No: {teklif_no}")
            else:
                teklif_bilgileri['teklif_no'] = "Bulunamadı"
                print("[UYARI] Teklif numarası bulunamadı")
            
            brut_prim_element = page.locator("#lblDaskProposalGrossPremium")
            if brut_prim_element.count() > 0:
                brut_prim = brut_prim_element.text_content().strip()
                teklif_bilgileri['brut_prim'] = brut_prim
                print(f"[BAŞARILI] Brüt Prim: {brut_prim}")
            else:
                teklif_bilgileri['brut_prim'] = "Bulunamadı"
                print("[UYARI] Brüt prim bulunamadı")
            
            teklif_bilgileri['dask_adres_kodu'] = data.get('dask_adres_kodu', 'Bilinmiyor')
            print(f"[BİLGİ] DASK Adres Codeu: {teklif_bilgileri['dask_adres_kodu']}")
            
            teklif_bilgileri['tckn'] = data.get('tckn', 'Bilinmiyor')
            print(f"[BİLGİ] TC Kimlik No: {teklif_bilgileri['tckn']}")
            
        except Exception as e:
            print(f"[UYARI] Teklif bilgileri alınırken hata: {e}")
        
        print("\n" + "="*60)
        print("📋 TEKLIF BİLGİLERİ ÖZETI:")
        print("="*60)
        print(f"📄 Teklif No: {teklif_bilgileri.get('teklif_no', 'Bulunamadı')}")
        print(f"💰 Brüt Prim: {teklif_bilgileri.get('brut_prim', 'Bulunamadı')}")
        print(f"📍 DASK Adres Codeu: {teklif_bilgileri.get('dask_adres_kodu', 'Bilinmiyor')}")
        print(f"👤 TC No: {teklif_bilgileri.get('tckn', 'Bilinmiyor')}")
        print("="*60)
        
        return {
            'basarili': True,
            'mesaj': 'Yeni DASK teklifi başarıyla oluşturuldu',
            'teklif_no': teklif_bilgileri.get('teklif_no'),
            'brut_prim': teklif_bilgileri.get('brut_prim'),
            'dask_adres_kodu': teklif_bilgileri.get('dask_adres_kodu'),
            'tckn': teklif_bilgileri.get('tckn'),
            'teklif_bilgileri': teklif_bilgileri
        }
        
    except Exception as e:
        print(f"\n[HATA] Yeni DASK sigortası işlemi sırasında hata oluştu: {e}", file=sys.stderr)
        traceback.print_exc()
        return {'basarili': False, 'hata': str(e)}

# ==================== ANA FONKSİYON ====================

def main():
    p = sync_playwright().start()
    browser = p.chromium.launch(headless=False, args=["--window-size=1400,1000"])
    
    context = None
    page = None

    print("[BİLGİ] Otomatik çerezle giriş pasif. Her çalıştırmada tam giriş yapılacak.")
    
    # 1. Giriş yap
    try:
        context = browser.new_context()
        page = context.new_page()
        success = login_and_save(page)
        if not success:
            return

    except PlaywrightTimeoutError as e:
        print(f"\n[HATA] Giriş sırasında zaman aşımı: {e}", file=sys.stderr)
        return
    except Exception as e:
        print(f"\n[HATA] Giriş işlemi sırasında beklenmedik hata: {e}", file=sys.stderr)
        return

    # 2. İşlemleri çalıştır
    try:
        if page:
            # Pop-up'ları kapat
            handle_popups(page)
            
            # Yeni teklif sayfasını aç
            new_page = open_new_offer_page(page)
            
            if new_page:
                page = new_page
                print("[BİLGİ] Artık yeni sekme ile çalışılıyor.")
                
                # ÖRNEK KULLANIM - İstediğiniz sigorta türünü seçin
                
                sample_data = {
                    'tckn': '40840299196',
                    'plaka': '59ADH604',
                    'ruhsat_seri_no': 'GB783183',
                    'arac_marka':"RENAULT",
                    'arac_modeli': 'Megane',
                    'meslek': 'A.Ş. SAHİBİ VE ÇALIŞANI',  # Kasko için
                    'email': 'ornek@mail.com',
                    # Sağlık sigortası için ek bilgiler
                    'dogum_tarihi': '01/01/2002',
                    'prim_tipi': 'TAM SENLİK-YATARAK+AYAKTA TEDAVİ',
                    'meslek_saglik': 'ÖZEL SEKTÖR ÇALIŞANI',
                    'teminat_sayisi': 3 , # 3, 5, 7, 10, veya 12
                    # DASK YENİLEME için
                    'dask_police_no': '56699188',
                    # YENİ DASK için
                    'dask_adres_kodu': '1016854321', # Örnek bir adres kodu
                    'telefon': '5551234567'
                }
                
                # Hangi sigorta türünü işlemek istiyorsunuz?
                print("\n" + "="*60)
                print("HANGİ SİGORTA TÜRÜNÜ İŞLEMEK İSTİYORSUNUZ?")
                print("="*60)
                print("1. Trafik Sigortası")
                print("2. Kasko Sigortası")
                print("3. Tamamlayıcı Sağlık Sigortası")
                print("4. DASK (Poliçe Yenileme)")
                print("5. DASK (Yeni Poliçe)") # YENİ SEÇENEK
                
                choice = input("\nSeçiminiz (1-5): ").strip()
                
                if choice == "1":
                    result = process_trafik_sigortasi(page, sample_data)
                    if result and result.get('basarili'):
                        print("\n✅ Teklif başarıyla oluşturuldu!")
                        print(f"📋 Detaylar: {result}")
                    else:
                        print("\n❌ Teklif oluşturulamadı!")
                elif choice == "2":
                    result = process_kasko_sigortasi(page, sample_data)
                    if result and result.get('basarili'):
                        print("\n✅ Kasko teklifi başarıyla oluşturuldu!")
                    else:
                        print("\n❌ Kasko teklifi oluşturulamadı!")
                elif choice == "3":
                    result = process_saglik_sigortasi(page, sample_data)
                    if result and result.get('basarili'):
                        print("\n✅ Sağlık sigortası teklifi başarıyla oluşturuldu!")
                    else:
                        print("\n❌ Sağlık sigortası teklifi oluşturulamadı!")
                elif choice == "4":
                    result = process_dask_sigortasi(page, sample_data)
                    if result and result.get('basarili'):
                        print("\n✅ DASK (Yenileme) teklifi başarıyla oluşturuldu!")
                    else:
                        print("\n❌ DASK (Yenileme) teklifi oluşturulamadı!")
                elif choice == "5":
                    # YENİ FONKSİYON ÇAĞRISI
                    result = process_dask_yeni_police(page, sample_data)
                    if result and result.get('basarili'):
                        print("\n✅ DASK (Yeni Poliçe) teklifi başarıyla oluşturuldu!")
                    else:
                        print("\n❌ DASK (Yeni Poliçe) teklifi oluşturulamadı!")
                else:
                    print("[UYARI] Geçersiz seçim!")
            else:
                print("[UYARI] Yeni sekme alınamadı.")
    
    except Exception as e:
        print(f"[HATA] İşlem sırasında hata oluştu: {e}", file=sys.stderr)
        
    finally:
        input("\n[BİLGİ] Tarayıcıyı kapatmak için ENTER tuşuna basın...")
        
        if browser:
            browser.close()
        p.stop()
        print("Program sonlandırıldı.")


if __name__ == "__main__":
    main()