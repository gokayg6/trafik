import os
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeoutError
import time
import random

class DogaScraper:
    def __init__(self):
        load_dotenv()
        self.login_url = os.getenv("DOGA_LOGIN_URL", "").strip()
        self.username  = os.getenv("DOGA_USER", "").strip()
        self.password  = os.getenv("DOGA_PASS", "").strip()
        self.totp_secret = os.getenv("DOGA_TOTP_SECRET", "").strip()
        self.headless  = os.getenv("HEADLESS", "false").lower() == "true"
        self.timeout   = int(os.getenv("DOGA_TIMEOUT_MS", "45000"))

        if not self.login_url:
            raise RuntimeError("DOGA_LOGIN_URL .env içinde tanımlı değil.")
        if not self.username or not self.password:
            raise RuntimeError("DOGA_USER ve DOGA_PASS .env içinde olmalı.")
        if not self.totp_secret:
            raise RuntimeError("DOGA_TOTP_SECRET .env içinde olmalı.")

        # Yalın ve güvenli: önce net id/name; olmazsa genel fallback
        self.USER_CANDS = [
            'input#Username', 'input[name="Username"]',
            'input[placeholder*="Kullanıcı"]', 'input[placeholder*="Kullanici"]',
            'input[type="text"]'
        ]
        self.PASS_CANDS = [
            'input#Password', 'input[name="Password"]',
            'input[placeholder*="Şifre"]', 'input[placeholder*="Sifre"]',
            'input[type="password"]'
        ]
        self.LOGIN_BTN_CANDS = [
            'button[name="button"][value="login"]',
            'button:has-text("Giriş Yap")', 'button:has-text("Giriş")',
            'input[type="submit"]', 'button.btn.btn-primary'
        ]

    def run(self):
        """Ana çalıştırma fonksiyonu"""
        browser = None
        context = None
        page = None
        
        try:
            with sync_playwright() as p:
                # Browser başlat
                print("[INFO] Browser başlatılıyor...")
                browser = p.chromium.launch(headless=self.headless)
                context = browser.new_context()
                page = context.new_page()
                page.set_default_timeout(self.timeout)
                
                print(f"[INFO] Login sayfasına gidiliyor: {self.login_url}")
                page.goto(self.login_url, wait_until="networkidle")
                
                # Giriş yap
                self._login(page)
                
                # TOTP doğrulaması yap
                self._verify_totp(page)
                
                # -----------------------------------------------------------------
                # YENİ EKLENEN HATA AYIKLAMA SATIRI
                # -----------------------------------------------------------------
                # Eğer kod buraya kadar hatasız gelirse, bunu terminalde göreceğiz.
                print("\n[DEBUG] GİRİŞ VE TOTP BAŞARILI! MENÜ GÖSTERİLİYOR...\n")
                # -----------------------------------------------------------------

                # YENİ MENÜ SİSTEMİ BAŞLANGICI
                
                # Teklif verilerini burada tanımlayalım
                kasko_data = {
                    "tc_no": "32083591236",
                    "birth_date": "1965-03-10",
                    "plate_code": "06",
                    "plate_no": "HT203",
                    "tescil_seri_kod": "ER",
                    "tescil_seri_no": "993016"
                }
                
                trafik_data = {
                    "tc_no": "32083591236",
                    "birth_date": "1965-03-10",
                    "plate_code": "06",
                    "plate_no": "HT203",
                    "tescil_seri_kod": "ER",
                    "tescil_seri_no": "993016",
                }
                
                # Kullanıcıdan hangi işlemi yapmak istediğini sor
                while True:
                    print("\n" + "="*50)
                    print("İŞLEM SEÇİM MENÜSÜ")
                    print("="*50)
                    print("1: Kasko Teklifi Al")
                    print("2: Trafik Teklifi Al")
                    print("="*50)
                    
                    secim = input("Lütfen bir işlem seçin (1 veya 2): ").strip()
                    
                    if secim == '1':
                        print("\n[INFO] Kasko Teklifi başlatılıyor...")
                        self.get_kasko_quote(page, kasko_data)
                        break # Döngüden çık
                    
                    elif secim == '2':
                        print("\n[INFO] Trafik Teklifi başlatılıyor...")
                        self.get_trafik_quote(page, trafik_data)
                        break # Döngüden çık
                    
                    else:
                        print("\n[WARNING] Geçersiz seçim! Lütfen sadece '1' veya '2' girin.")
                        time.sleep(1)

                # -----------------------------------------------------------------
                # YENİ MENÜ SİSTEMİ BİTİŞİ
                # -----------------------------------------------------------------
                
                print("\n" + "="*50)
                print("ENTER'a BASMAK İÇİN BEKLENİYOR...")
                print("="*50)
                input("Devam etmek için ENTER'a basın: ")
                
                print("[SUCCESS] İşlem tamamlandı.")
                
        except PWTimeoutError as e:
            print(f"[ERROR] Zaman aşımı hatası: {e}")
        except Exception as e:
            print(f"[ERROR] Beklenmeyen hata: {e}")
            # Hatanın detayını görmek için bu satırı ekleyebilirsiniz:
            # import traceback
            # traceback.print_exc()
        finally:
            print("[INFO] 'finally' bloğuna girildi. Browser kapatılacak.")
            if page:
                page.close()
            if context:
                context.close()
            if browser:
                browser.close()
            print("[INFO] Browser kapatıldı.")

    def _login(self, page):
        """Kullanıcı girişi yap"""
        try:
            # Kullanıcı adı alanını bul ve doldur
            username_input = self._find_element(page, self.USER_CANDS, "Kullanıcı adı")
            if username_input:
                username_input.fill(self.username)
                print("[INFO] Kullanıcı adı girildi.")
            else:
                raise Exception("Kullanıcı adı alanı bulunamadı!")
            
            time.sleep(random.uniform(0.5, 1.5))
            
            # Şifre alanını bul ve doldur
            password_input = self._find_element(page, self.PASS_CANDS, "Şifre")
            if password_input:
                password_input.fill(self.password)
                print("[INFO] Şifre girildi.")
            else:
                raise Exception("Şifre alanı bulunamadı!")
            
            time.sleep(random.uniform(0.5, 1.5))
            
            # Giriş butonunu bul ve tıkla
            login_button = self._find_element(page, self.LOGIN_BTN_CANDS, "Giriş butonu")
            if login_button:
                login_button.click()
                print("[INFO] Giriş butonuna tıklandı.")
                time.sleep(random.uniform(2, 4))  # Giriş işleminin tamamlanmasını bekle
            else:
                raise Exception("Giriş butonu bulunamadı!")
            
            # Giriş başarılı mı kontrol et
            page.wait_for_load_state("networkidle", timeout=self.timeout)
            print("[SUCCESS] Giriş başarılı!")
            
        except Exception as e:
            print(f"[ERROR] Giriş sırasında hata: {e}")
            raise

    def get_trafik_quote(self, page, trafik_data):
        """Trafik sigortası için teklif al"""
        try:
            print("[INFO] TRAFİK sigortası sayfasına gidiliyor...")
            
            # -----------------------------------------------------------------

            trafik_element = page.query_selector('img#img_police_oto_kaza_310_trafik_policesi') # <<< TAHMİNİ SELECTOR!
            
            if trafik_element:
                print("[INFO] Trafik elementi bulundu.")
                trafik_element.click()
                print("[INFO] Trafik elementine tıklandı.")
                
                # Sayfanın yüklenmesini bekle
                print("[INFO] Sayfa yükleniyor...")
                page.wait_for_load_state("networkidle", timeout=self.timeout)
                print("[SUCCESS] Trafik  sayfası yüklendi.")
                
                # 10 saniye bekle
                print("[INFO] 10 saniye bekleniyor...")
                for i in range(10, 0, -1):
                    print(f"  [{i}s]", end="\r")
                    time.sleep(1)
                print("[SUCCESS] Bekleme tamamlandı.    ")
                
                # TC Kimlik No gir
                self._enter_tc_no(page, trafik_data["tc_no"])
                
                # Doğum Tarihi kontrolü
                self._check_birth_date_dialog(page, trafik_data["birth_date"])
                
                # Ürün Soruları'na tıkla
                self._click_product_questions(page)
                
                # 5 saniye bekle
                print("[INFO] 5 saniye bekleniyor...")
                for i in range(5, 0, -1):
                    print(f"  [{i}s]", end="\r")
                    time.sleep(1)
                print("[SUCCESS] Bekleme tamamlandı.    ")
                
                # Plaka gir
                self._enter_trafik_plate_info(page, trafik_data["plate_code"], trafik_data["plate_no"], 
                                      trafik_data["tescil_seri_kod"], trafik_data["tescil_seri_no"])
                
                print("[SUCCESS] Trafik  teklif süreci tamamlandı!")
                return True
            else:
                raise Exception("Trafik elementi bulunamadı! (Selector'ı kontrol edin)")
                
        except Exception as e:
            print(f"[ERROR] TRAFİK teklif alınırken hata: {e}")
            raise
    def _enter_trafik_plate_info(self, page, plate_code, plate_no, tescil_seri_kod, tescil_seri_no):
        """Trafik formu için Plaka bilgisi gir"""
        try:
            print("[INFO] Trafik - Plaka bilgisi giriliyorum...")
            
            # -----------------------------------------------------------------
            # !!! DEĞİŞTİR: Buradaki tüm selector'lar (ID'ler) TAHMİNİDİR.
            # Hepsini Trafik sayfasına göre güncellemelisiniz!
            # -----------------------------------------------------------------
            
            # Plaka İl Kodu gir
            plate_code_selector = 'input#trafikEkran_txtPlakaIlKodu' 
            plate_code_input = page.query_selector(plate_code_selector)
            if plate_code_input:
                page.evaluate(f'document.querySelector("{plate_code_selector}").scrollIntoView();')
                time.sleep(random.uniform(0.5, 1))
                plate_code_input.fill(plate_code)
                print(f"[SUCCESS] Trafik - Plaka İl Kodu girildi: {plate_code}")
                time.sleep(random.uniform(0.5, 1))
            else:
                raise Exception(f"Trafik - Plaka İl Kodu alanı bulunamadı! (Selector: {plate_code_selector})")
            
            # Plaka No gir
            plate_no_selector = 'input#trafikEkran_txtPlaka' # <<< TAHMİNİ SELECTOR!
            plate_no_input = page.query_selector(plate_no_selector)
            if plate_no_input:
                page.evaluate(f'document.querySelector("{plate_no_selector}").scrollIntoView();')
                time.sleep(random.uniform(0.5, 1))
                plate_no_input.fill(plate_no)
                print(f"[SUCCESS] Trafik - Plaka No girildi: {plate_no}")
                time.sleep(random.uniform(0.5, 1))
                
                page.click('body')
                print("[INFO] Boşluğa tıklandı, plaka sorgusu başlatıldı.")
                
                # Tescil Belge bilgilerini doldur (Trafik için yeni fonksiyon)
                self._enter_trafik_registration_info(page, tescil_seri_kod, tescil_seri_no)
                
                print("[SUCCESS] Trafik - Plaka bilgisi işlemi tamamlandı.")
                

                # Hesapla butonu (Ortak fonksiyonu yeniden kullanıyoruz)
                self._click_hesapla_button(page) 

                # Prim bilgilerini çek (Trafik için yeni fonksiyon)
                premium_data = self._extract_premium_values(page)
                
                # Primleri göster (Ortak fonksiyonu yeniden kullanıyoruz)
                self._display_premium_data(premium_data) 

            else:
                raise Exception(f"Trafik - Plaka No alanı bulunamadı! (Selector: {plate_no_selector})")
                
        except Exception as e:
            print(f"[ERROR] Trafik - Plaka bilgisi girilirken hata: {e}")
            raise    
    def _enter_trafik_registration_info(self, page, tescil_seri_kod, tescil_seri_no):
        """Trafik formu için Tescil Belge bilgilerini gir"""
        try:
            print("[INFO] Trafik - Tescil Belge bilgilerini giriliyorum...")
            
            # -----------------------------------------------------------------
            # !!! DEĞİŞTİR: ID'leri Trafik sayfasına göre güncelleyin.
            # -----------------------------------------------------------------

            # Tescil Belge Seri Kod gir
            seri_kod_selector = 'input#trafikEkran_txtTescilBelgeSeriKod' # <<< TAHMİNİ SELECTOR!
            seri_kod_input = page.query_selector(seri_kod_selector)
            if seri_kod_input:
                page.evaluate(f'document.querySelector("{seri_kod_selector}").scrollIntoView();')
                time.sleep(random.uniform(0.5, 1))
                seri_kod_input.fill(tescil_seri_kod)
                print(f"[SUCCESS] Trafik - Tescil Belge Seri Kod girildi: {tescil_seri_kod}")
                time.sleep(random.uniform(0.5, 1))
            else:
                print("[WARNING] Trafik - Tescil Belge Seri Kod alanı bulunamadı!")
            
            # Tescil Belge Seri No gir
            seri_no_selector = 'input#trafikEkran_txtTescilBelgeSeriNo' # <<< TAHMİNİ SELECTOR!
            seri_no_input = page.query_selector(seri_no_selector)
            if seri_no_input:
                page.evaluate(f'document.querySelector("{seri_no_selector}").scrollIntoView();')
                time.sleep(random.uniform(0.5, 1))
                seri_no_input.fill(tescil_seri_no)
                print(f"[SUCCESS] Trafik - Tescil Belge Seri No girildi: {tescil_seri_no}")
                time.sleep(random.uniform(0.5, 1))
            else:
                print("[WARNING] Trafik - Tescil Belge Seri No alanı bulunamadı!")
            
            # EGM Sorgula butonu (Ortak fonksiyonu yeniden kullanıyoruz)
            self._click_egm_button(page)
                
        except Exception as e:
            print(f"[ERROR] Trafik - Tescil Belge bilgilerini girilirken hata: {e}")
            raise    

    def get_kasko_quote(self, page, kasko_data):
        try:
            print("[INFO] KASKO sigortası sayfasına gidiliyor...")
            
            # KASKO elementini bul
            kasko_element = page.query_selector('img#img_police_oto_kaza_kasko_policesi')
            
            if kasko_element:
                print("[INFO] KASKO elementi bulundu.")
                kasko_element.click()
                print("[INFO] KASKO elementine tıklandı.")
                
                # Sayfanın yüklenmesini bekle
                print("[INFO] Sayfa yükleniyor...")
                page.wait_for_load_state("networkidle", timeout=self.timeout)
                print("[SUCCESS] KASKO sayfası yüklendi.")
                
                # 10 saniye bekle
                print("[INFO] 10 saniye bekleniyor...")
                for i in range(10, 0, -1):
                    print(f"  [{i}s]", end="\r")
                    time.sleep(1)
                print("[SUCCESS] Bekleme tamamlandı.    ")
                
                # TC Kimlik No gir
                self._enter_tc_no(page, kasko_data["tc_no"])
                
                # Doğum Tarihi kontrolü
                self._check_birth_date_dialog(page, kasko_data["birth_date"])
                
                # Ürün Soruları'na tıkla
                self._click_product_questions(page)
                
                # 5 saniye bekle
                print("[INFO] 5 saniye bekleniyor...")
                for i in range(5, 0, -1):
                    print(f"  [{i}s]", end="\r")
                    time.sleep(1)
                print("[SUCCESS] Bekleme tamamlandı.    ")
                
                # Plaka gir
                self._enter_plate_info(page, kasko_data["plate_code"], kasko_data["plate_no"], 
                                      kasko_data["tescil_seri_kod"], kasko_data["tescil_seri_no"])
                
                print("[SUCCESS] KASKO teklif süreci tamamlandı!")
                return True
            else:
                raise Exception("KASKO elementi bulunamadı!")
                
        except Exception as e:
            print(f"[ERROR] KASKO teklif alınırken hata: {e}")
            raise

    def _enter_tc_no(self, page, tc_no):
        """TC Kimlik No gir ve boşluğa tıkla"""
        try:
            print("[INFO] TC Kimlik No giriliyorum...")
            
            tc_input = page.query_selector('input#genelEkran_txtS_TcKimlikNo')
            if tc_input:
                # Elementi scroll ederek görünür hale getir
                page.evaluate('document.querySelector("input#genelEkran_txtS_TcKimlikNo").scrollIntoView();')
                time.sleep(random.uniform(0.5, 1))
                
                tc_input.fill(tc_no)
                print(f"[SUCCESS] TC Kimlik No girildi: {tc_no}")
                time.sleep(random.uniform(1, 2))
                
                # Boşluğa tıkla (sayfa üzerine tıkla)
                page.click('body')
                print("[INFO] Boşluğa tıklandı, doğum tarihi dialog'u açılmalı.")
                time.sleep(random.uniform(2, 3))
            else:
                raise Exception("TC Kimlik No alanı bulunamadı!")
                
        except Exception as e:
            print(f"[ERROR] TC Kimlik No girilirken hata: {e}")
            raise

    def _check_birth_date_dialog(self, page, birth_date):
        """Doğum Tarihi Dialog kontrol et ve gerekirse doldur"""
        try:
            # Dialog'un açılıp açılmadığını kontrol et (2 saniye bekle)
            try:
                page.wait_for_selector('div.ui-dialog', timeout=2000)
                print("[INFO] Doğum Tarihi dialog'u açılmış.")
                
                if not birth_date:
                    raise Exception("Doğum tarihi parametresi boş!")
                
                time.sleep(random.uniform(0.5, 1))
                
                # Doğum tarihi alanını bul ve doldur
                birth_date_input = page.query_selector('input#tcSorgusuDogumTarihi')
                if birth_date_input:
                    # Scroll ve focus et
                    page.evaluate('document.querySelector("input#tcSorgusuDogumTarihi").focus();')
                    time.sleep(random.uniform(0.3, 0.5))
                    
                    birth_date_input.fill(birth_date)
                    print(f"[SUCCESS] Doğum tarihi girildi: {birth_date}")
                    time.sleep(random.uniform(0.5, 1))
                    
                    # Tamam butonuna tıkla
                    ok_button = page.query_selector('div.ui-dialog-buttonpane button')
                    if ok_button:
                        ok_button.click()
                        print("[INFO] Tamam butonuna tıklandı.")
                        time.sleep(random.uniform(2, 3))
                    else:
                        raise Exception("Tamam butonu bulunamadı!")
                else:
                    raise Exception("Doğum tarihi input alanı bulunamadı!")
                    
            except PWTimeoutError:
                print("[INFO] Doğum Tarihi dialog'u açılmadı. Devam ediliyor...")
                
        except Exception as e:
            print(f"[ERROR] Doğum Tarihi kontrolü sırasında hata: {e}")
            raise

    def _click_product_questions(self, page):
        """Ürün Soruları linkine tıkla"""
        try:
            print("[INFO] Ürün Soruları linkini arıyorum...")
            
            # Ürün Soruları linkini bul
            product_questions_link = page.query_selector('a[title="Ürün Soruları"]')
            
            if product_questions_link:
                product_questions_link.click()
                print("[INFO] Ürün Soruları linkine tıklandı.")
                page.wait_for_load_state("networkidle", timeout=self.timeout)
                print("[SUCCESS] Ürün Soruları sayfası yüklendi.")
            else:
                raise Exception("Ürün Soruları linki bulunamadı!")
                
        except Exception as e:
            print(f"[ERROR] Ürün Soruları tıklanırken hata: {e}")
            raise

    def _enter_plate_info(self, page, plate_code, plate_no, tescil_seri_kod, tescil_seri_no):
        """Plaka bilgisi gir"""
        try:
            print("[INFO] Plaka bilgisi giriliyorum...")
            
            # Plaka İl Kodu gir
            plate_code_input = page.query_selector('input#kaskoEkran_txtPlakaIlKodu')
            if plate_code_input:
                # Scroll ederek görünür hale getir
                page.evaluate('document.querySelector("input#kaskoEkran_txtPlakaIlKodu").scrollIntoView();')
                time.sleep(random.uniform(0.5, 1))
                
                plate_code_input.fill(plate_code)
                print(f"[SUCCESS] Plaka İl Kodu girildi: {plate_code}")
                time.sleep(random.uniform(0.5, 1))
            else:
                raise Exception("Plaka İl Kodu alanı bulunamadı!")
            
            # Plaka No gir
            plate_no_input = page.query_selector('input#kaskoEkran_txtPlaka')
            if plate_no_input:
                # Scroll ederek görünür hale getir
                page.evaluate('document.querySelector("input#kaskoEkran_txtPlaka").scrollIntoView();')
                time.sleep(random.uniform(0.5, 1))
                
                plate_no_input.fill(plate_no)
                print(f"[SUCCESS] Plaka No girildi: {plate_no}")
                time.sleep(random.uniform(0.5, 1))
                
                # Boşluğa tıkla (sorgu başlasın)
                page.click('body')
                print("[INFO] Boşluğa tıklandı, plaka sorgusu başlatıldı.")
                
                # Popup'ı kontrol et ve handle et
                self._handle_warning_dialog(page)
                
                # Tescil Belge bilgilerini doldur
                self._enter_registration_info(page, tescil_seri_kod, tescil_seri_no)
                
                print("[SUCCESS] Plaka bilgisi işlemi tamamlandı.")
                self._handle_egm_success_dialog(page)

                self._click_hesapla_button(page)

                # Prim bilgilerini çek ve yazdır
                premium_data = self._extract_premium_values(page)
                self._display_premium_data(premium_data)

             
            else:
                raise Exception("Plaka No alanı bulunamadı!")
                
        except Exception as e:
            print(f"[ERROR] Plaka bilgisi girilirken hata: {e}")
            raise

    def _extract_premium_values(self, page):
        """Prim bilgilerini 'div#divPrimler' alanından çek"""
        try:
            print("[INFO] Prim bilgileri okunuyor...")

            # Önce divPrimler elementini bul ve scroll et
            prim_div = page.query_selector('div#divPrimler')
            if prim_div:
                print("[INFO] Prim div elementi bulundu, scroll ediliyor...")
                page.evaluate('document.querySelector("div#divPrimler").scrollIntoView();')
                time.sleep(2)
            else:
                print("[WARNING] div#divPrimler elementi bulunamadı!")

            # Daha geniş timeout ile bekle
            page.wait_for_selector("div#divPrimler", timeout=10000)
            print("[INFO] Prim div yüklendi, input'lar aranıyor...")

            # Tüm input alanlarını kontrol et
            all_inputs = page.query_selector_all('div#divPrimler input[type="text"]')
            print(f"[DEBUG] Toplam {len(all_inputs)} input elementi bulundu")

            for i, inp in enumerate(all_inputs):
                input_id = inp.get_attribute('id') or 'no-id'
                input_name = inp.get_attribute('name') or 'no-name'

                # input_value() metodunu kullan!
                try:
                    input_value = inp.input_value() or 'no-value'
                except:
                    input_value = 'error-reading-value'

                print(f"[DEBUG] Input {i}: id={input_id}, name={input_name}, value={input_value}")

            # Spesifik alanları çek - input_value() kullanarak
            fields = {
                "Net Prim": "#ctl20_txtNetPrim",
                "YSV": "#ctl20_txtYSV", 
                "G.V.": "#ctl20_txtGv",
                "GHP": "#ctl20_txtGhp",
                "THGF": "#ctl20_txtTHGF",
                "Brüt Prim": "#ctl20_txtBrutPrim",
                "Komisyon": "#ctl20_txtKomisyon",
                "Ek Komisyon": "#ctl20_txtEkKomisyon"
            }

            results = {}
            for label, selector in fields.items():
                try:
                    elem = page.query_selector(selector)
                    if elem:
                        # input_value() metodunu kullan!
                        val = elem.input_value()
                        results[label] = val
                        print(f"[DEBUG] {label}: '{val}'")
                    else:
                        results[label] = None
                        print(f"[DEBUG] {label}: ELEMENT BULUNAMADI")
                except Exception as e:
                    print(f"[DEBUG] {label} okunurken hata: {e}")
                    results[label] = None

            print("[SUCCESS] Prim bilgileri çekildi.")
            return results

        except Exception as e:
            print(f"[ERROR] Prim bilgileri okunurken hata: {e}")
            page.screenshot(path="error_screenshot.png")
            print("[INFO] Hata ekran görüntüsü kaydedildi: error_screenshot.png")
            raise

    def _display_premium_data(self, premium_data):
        """Prim bilgilerini güzel bir formatta ekrana yazdır"""
        print("\n" + "="*60)
        print("SİGORTA PRİM BİLGİLERİ")
        print("="*60)

        if not premium_data:
            print("Prim bilgileri alınamadı!")
            return

        for label, value in premium_data.items():
            if value and value.strip():
                # Değeri olduğu gibi göster, sadece TL ekle
                print(f"  {label:<15}: {value.strip()} TL")
            else:
                print(f"  {label:<15}: -")

        print("="*60)

    def _click_hesapla_button(self, page):
        """Sayfanın altındaki 'Hesapla' butonuna tıkla"""
        try:
            print("[INFO] 'Hesapla' butonu aranıyor...")
            hesapla_button = page.query_selector('input.btn.btn-info.marginli[value="Hesapla"]')
            if hesapla_button:
                # Prim alanına scroll et
                page.evaluate('document.querySelector("div#divPrimler").scrollIntoView();')
                time.sleep(1)
                
                hesapla_button.click()
                print("[INFO] 'Hesapla' butonuna tıklandı.")
                print("[INFO] Hesaplama tamamlanması için 10 saniye bekleniyor...")
                
                # Hesaplamanın tamamlanmasını bekle
                for i in range(10, 0, -1):
                    print(f"  [{i}s]", end="\r")
                    time.sleep(1)
                print("[SUCCESS] Hesaplama tamamlandı.    ")
            else:
                print("[WARNING] 'Hesapla' butonu bulunamadı!")
        except Exception as e:
            print(f"[ERROR] 'Hesapla' butonuna tıklanırken hata: {e}")
            raise

    def _handle_egm_success_dialog(self, page):
        """'EGM sorgusu başarılı' popup'unu kapat"""
        try:
            dialog_text = "EGM sorgusu başarılı"
            print("[INFO] 'EGM sorgusu başarılı' popup'u bekleniyor...")

            dialog_locator = page.locator(f'div.ui-dialog:has-text("{dialog_text}")')
            ok_button_locator = dialog_locator.get_by_role("button", name="Tamam")

            dialog_locator.wait_for(state="visible", timeout=8000)
            print("[INFO] Popup bulundu!")

            ok_button_locator.click()
            print("[INFO] 'Tamam' butonuna tıklandı.")

            dialog_locator.wait_for(state="hidden", timeout=5000)
            print("[SUCCESS] Popup başarıyla kapatıldı.")
        except Exception as e:
            print(f"[WARNING] 'EGM sorgusu başarılı' popup'u bulunamadı veya kapanamadı: {e}")

    def _handle_warning_dialog(self, page):
        """
        Spesifik "Hasar bulunmadığından..." uyarısını 
        içeren dialog'u bularak kapatır.
        """
        
        try:
            # 1. Dialog'u, içindeki spesifik uyarı metniyle bul.
            # Bu, sayfada başka 'ui-dialog' olsa bile DOĞRU olanı seçmemizi sağlar.
            dialog_text = "Hasar bulunmadığından kademe 1 arttırılıyor."
            dialog_locator = page.locator(f'div.ui-dialog:has-text("{dialog_text}")')
    
            # 2. Sadece bu dialog'un içindeki 'Tamam' butonunu bul.
            # get_by_role, HTML'deki gibi metin <span_> içinde olsa bile onu bulur.
            ok_button_locator = dialog_locator.get_by_role("button", name="Tamam")
    
            print(f"[INFO] '{dialog_text}' uyarısı bekleniyor (maks 5sn)...")
            
            # 3. Dialog'un GÖRÜNÜR olmasını bekle (time.sleep yerine).
            dialog_locator.wait_for(state='visible', timeout=5000)
            print("[INFO] Spesifik uyarı dialog'u bulundu!")
    
            # 4. 'Tamam' butonuna tıkla.
            # Playwright, tıklamadan önce butonun tıklanabilir olmasını bekler.
            ok_button_locator.click()
            print("[INFO] Uyarı dialog'u - 'Tamam' butonuna tıklandı.")
    
            # 5. Dialog'un KAPANMASINI (gizlenmesini) bekle (time.sleep yerine).
            dialog_locator.wait_for(state='hidden', timeout=5000)
            print("[SUCCESS] Dialog başarıyla kapatıldı.")
    
        except TimeoutError:
            # dialog_locator.wait_for('visible') zaman aşımına uğrarsa:
            print("[INFO] Spesifik uyarı dialog'u 5 saniye içinde açılmadı. Devam ediliyor...")
        
        except Exception as e:
            print(f"[ERROR] Spesifik uyarı dialog'u handle edilirken hata: {e}")

    def _enter_registration_info(self, page, tescil_seri_kod, tescil_seri_no):
        """Tescil Belge bilgilerini gir"""
        try:
            print("[INFO] Tescil Belge bilgilerini giriliyorum...")
            
            # Tescil Belge Seri Kod gir
            seri_kod_input = page.query_selector('input#kaskoEkran_txtTescilBelgeSeriKod')
            if seri_kod_input:
                # Scroll ederek görünür hale getir
                page.evaluate('document.querySelector("input#kaskoEkran_txtTescilBelgeSeriKod").scrollIntoView();')
                time.sleep(random.uniform(0.5, 1))
                
                seri_kod_input.fill(tescil_seri_kod)
                print(f"[SUCCESS] Tescil Belge Seri Kod girildi: {tescil_seri_kod}")
                time.sleep(random.uniform(0.5, 1))
            else:
                print("[WARNING] Tescil Belge Seri Kod alanı bulunamadı!")
            
            # Tescil Belge Seri No gir
            seri_no_input = page.query_selector('input#kaskoEkran_txtTescilBelgeSeriNo')
            if seri_no_input:
                # Scroll ederek görünür hale getir
                page.evaluate('document.querySelector("input#kaskoEkran_txtTescilBelgeSeriNo").scrollIntoView();')
                time.sleep(random.uniform(0.5, 1))
                
                seri_no_input.fill(tescil_seri_no)
                print(f"[SUCCESS] Tescil Belge Seri No girildi: {tescil_seri_no}")
                time.sleep(random.uniform(0.5, 1))
            else:
                print("[WARNING] Tescil Belge Seri No alanı bulunamadı!")
            
            # EGM Sorgula butonuna tıkla
            self._click_egm_button(page)
                
        except Exception as e:
            print(f"[ERROR] Tescil Belge bilgilerini girilirken hata: {e}")
            raise

    def _click_egm_button(self, page):
        """EGM Sorgula butonuna tıkla"""
        try:
            print("[INFO] EGM Sorgula butonunu arıyorum...")
            
            egm_button = page.query_selector('input#btnEGMSorgula')
            if egm_button:
                # Scroll ederek görünür hale getir
                page.evaluate('document.querySelector("input#btnEGMSorgula").scrollIntoView();')
                time.sleep(random.uniform(0.5, 1))
                
                egm_button.click()
                print("[INFO] EGM Sorgula butonuna tıklandı.")
                time.sleep(random.uniform(2, 3))
            else:
                print("[WARNING] EGM Sorgula butonu bulunamadı!")
                
        except Exception as e:
            print(f"[ERROR] EGM Sorgula butonuna tıklanırken hata: {e}")
            raise

    def _verify_totp(self, page):
        """TOTP 2FA doğrulaması yap"""
        try:
            import pyotp
            
            print("[INFO] TOTP doğrulaması yapılıyor...")
            
            # TOTP kodu oluştur
            totp = pyotp.TOTP(self.totp_secret)
            code = totp.now()
            print(f"[INFO] TOTP kodu oluşturuldu: {code}")
            
            # TOTP input alanını bul
            totp_selectors = [
                'input#OtpCode', 'input[name="OtpCode"]',
                'input[placeholder*="Doğrulama"]', 'input[placeholder*="Kod"]',
                'input[type="text"]'
            ]
            
            totp_input = self._find_element(page, totp_selectors, "TOTP kodu alanı")
            if totp_input:
                totp_input.fill(code)
                print("[INFO] TOTP kodu girildi.")
            else:
                raise Exception("TOTP input alanı bulunamadı!")
            
            time.sleep(random.uniform(0.5, 1.5))
            
            # TOTP doğrula butonunu bul ve tıkla
            verify_btn_selectors = [
                'button[name="button"][value="verify"]',
                'button:has-text("Doğrula")', 'button:has-text("Devam")',
                'input[type="submit"]'
            ]
            
            verify_button = self._find_element(page, verify_btn_selectors, "TOTP doğrula butonu")
            if verify_button:
                verify_button.click()
                print("[INFO] TOTP doğrula butonuna tıklandı.")
                time.sleep(random.uniform(2, 4))
            else:
                raise Exception("TOTP doğrula butonu bulunamadı!")
            
            # Doğrulama başarılı mı kontrol et
            page.wait_for_load_state("networkidle", timeout=self.timeout)
            print("[SUCCESS] TOTP doğrulaması başarılı!")
            
        except ImportError:
            print("[ERROR] pyotp kütüphanesi yüklü değil. Lütfen 'pip install pyotp' yapın.")
            raise
        except Exception as e:
            print(f"[ERROR] TOTP doğrulaması sırasında hata: {e}")
            raise

    def _find_element(self, page, selectors, element_name):
        """Verilen selector adaylarından ilkini bul"""
        for selector in selectors:
            try:
                element = page.query_selector(selector)
                if element:
                    print(f"[DEBUG] {element_name} bulundu: {selector}")
                    return element
            except Exception as e:
                print(f"[DEBUG] Selector başarısız ({selector}): {e}")
                continue
        
        print(f"[WARNING] {element_name} bulunamadı!")
        return None

    def _scrape_data(self, page):
        """Sayfadan veri çek (örnek)"""
        try:
            print("[INFO] Veri çekiliyor...")
            
            # Örnek: başlıkları çek
            titles = page.query_selector_all("h1, h2, h3")
            for title in titles:
                text = title.text_content()
                if text.strip():
                    print(f"  - {text.strip()}")
            
            print("[SUCCESS] Veri çekimi tamamlandı.")
            
        except Exception as e:
            print(f"[ERROR] Veri çekimi sırasında hata: {e}")

    def take_screenshot(self, page, filename="screenshot.png"):
        """Ekran görüntüsü al"""
        try:
            page.screenshot(path=filename)
            print(f"[INFO] Ekran görüntüsü kaydedildi: {filename}")
        except Exception as e:
            print(f"[ERROR] Ekran görüntüsü alınamadı: {e}")
    


# Kullanım örneği
if __name__ == "__main__":
    try:
        print("="*50)
        print("DOGA SCRAPER BAŞLATILIYOR")
        print("="*50)
        
        scraper = DogaScraper()
        scraper.run()
        
        print("="*50)
        print("İŞLEM BAŞARILA TAMAMLANDI")
        print("="*50)
        
    except RuntimeError as e:
        print(f"[FATAL] {e}")
    except Exception as e:
        print(f"[FATAL] Beklenmeyen hata: {e}")