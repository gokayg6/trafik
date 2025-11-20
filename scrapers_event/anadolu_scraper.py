import os
import json
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeoutError
import time
import random

class AnadoluScraper:
    def __init__(self):
        load_dotenv()
        self.login_url = os.getenv("ANADOLU_LOGIN_URL", "").strip()
        self.username  = os.getenv("ANADOLU_USER", "").strip()
        self.password  = os.getenv("ANADOLU_PASS", "").strip()
        self.headless  = os.getenv("HEADLESS", "false").lower() == "true"
        self.timeout   = int(os.getenv("ANADOLU_TIMEOUT_MS", "45000"))
        self.session_file = "anadolu_session.json"  # Tüm oturum verileri

        if not self.login_url:
            raise RuntimeError("ANADOLU_LOGIN_URL .env içinde tanımlı değil.")
        if not self.username or not self.password:
            raise RuntimeError("ANADOLU_USER ve ANADOLU_PASS .env içinde olmalı.")

        # Selector adayları
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
                time.sleep(random.uniform(2, 4))
            else:
                raise Exception("Giriş butonu bulunamadı!")
            
            # Giriş işleminin tamamlanmasını bekle
            page.wait_for_load_state("networkidle", timeout=self.timeout)
            print("[SUCCESS] Giriş işlemi tamamlandı!")
            
        except Exception as e:
            print(f"[ERROR] Giriş sırasında hata: {e}")
            raise

    def _save_session_data(self, page, context):
        """Tüm oturum verilerini kaydet (cookies, localStorage, sessionStorage)"""
        try:
            session_data = {
                'cookies': context.cookies(),
                'localStorage': {},
                'sessionStorage': {},
                'url': page.url,
                'timestamp': time.time()
            }
            
            # localStorage verilerini al
            try:
                local_storage = page.evaluate('() => Object.assign({}, window.localStorage)')
                session_data['localStorage'] = local_storage
                print(f"[INFO] localStorage: {len(local_storage)} kayıt bulundu")
            except Exception as e:
                print(f"[WARNING] localStorage okunamadı: {e}")
            
            # sessionStorage verilerini al
            try:
                session_storage = page.evaluate('() => Object.assign({}, window.sessionStorage)')
                session_data['sessionStorage'] = session_storage
                print(f"[INFO] sessionStorage: {len(session_storage)} kayıt bulundu")
            except Exception as e:
                print(f"[WARNING] sessionStorage okunamadı: {e}")
            
            # Dosyaya kaydet
            with open(self.session_file, 'w', encoding='utf-8') as f:
                json.dump(session_data, f, indent=2, ensure_ascii=False)
            
            print(f"[SUCCESS] Tüm oturum verileri kaydedildi: {self.session_file}")
            print(f"[INFO] - {len(session_data['cookies'])} cookie")
            print(f"[INFO] - {len(session_data['localStorage'])} localStorage item")
            print(f"[INFO] - {len(session_data['sessionStorage'])} sessionStorage item")
            
        except Exception as e:
            print(f"[ERROR] Oturum verileri kaydetme hatası: {e}")

    def _load_session_data(self, page, context):
        """Kaydedilmiş oturum verilerini yükle"""
        try:
            if not os.path.exists(self.session_file):
                print(f"[INFO] Oturum dosyası bulunamadı: {self.session_file}")
                return False
            
            with open(self.session_file, 'r', encoding='utf-8') as f:
                session_data = json.load(f)
            
            # Cookie'leri yükle
            if 'cookies' in session_data:
                context.add_cookies(session_data['cookies'])
                print(f"[INFO] {len(session_data['cookies'])} cookie yüklendi")
            
            # Önce sayfaya git (localStorage/sessionStorage için domain gerekli)
            print(f"[INFO] Sayfaya gidiliyor: {self.login_url}")
            page.goto(self.login_url, wait_until="domcontentloaded")
            
            # localStorage verilerini yükle
            if 'localStorage' in session_data and session_data['localStorage']:
                try:
                    for key, value in session_data['localStorage'].items():
                        page.evaluate(f'() => window.localStorage.setItem({json.dumps(key)}, {json.dumps(value)})')
                    print(f"[INFO] {len(session_data['localStorage'])} localStorage item yüklendi")
                except Exception as e:
                    print(f"[WARNING] localStorage yüklenemedi: {e}")
            
            # sessionStorage verilerini yükle
            if 'sessionStorage' in session_data and session_data['sessionStorage']:
                try:
                    for key, value in session_data['sessionStorage'].items():
                        page.evaluate(f'() => window.sessionStorage.setItem({json.dumps(key)}, {json.dumps(value)})')
                    print(f"[INFO] {len(session_data['sessionStorage'])} sessionStorage item yüklendi")
                except Exception as e:
                    print(f"[WARNING] sessionStorage yüklenemedi: {e}")
            
            # Sayfayı yenile
            print("[INFO] Sayfa yenileniyor...")
            page.reload(wait_until="networkidle")
            
            print(f"[SUCCESS] Oturum verileri yüklendi: {self.session_file}")
            return True
            
        except Exception as e:
            print(f"[ERROR] Oturum verileri yükleme hatası: {e}")
            return False

    def run(self):
        """Ana çalıştırma fonksiyonu - Oturum verileriyle dene, olmazsa login yap"""
        browser = None
        context = None
        page = None
        
        try:
            with sync_playwright() as p:
                print("[INFO] Browser başlatılıyor...")
                browser = p.chromium.launch(headless=self.headless)
                context = browser.new_context()
                page = context.new_page()
                page.set_default_timeout(self.timeout)
                
                # Önce oturum verileriyle dene
                print("\n" + "="*60)
                print("ADIM 1: OTURUM VERİLERİYLE GİRİŞ DENENİYOR...")
                print("="*60)
                
                session_success = self.run_with_cookies(context, page)
                
                if not session_success:
                    # Oturum başarısız, normal login yap
                    print("\n" + "="*60)
                    print("ADIM 2: NORMAL LOGIN İŞLEMİ YAPILIYOR...")
                    print("="*60)
                    
                    # Login sayfasına git
                    print(f"[INFO] Login sayfasına gidiliyor: {self.login_url}")
                    page.goto(self.login_url, wait_until="networkidle")
                    
                    # Normal login işlemi
                    self._login(page)
                    
                    # Mail doğrulama için bekle
                    print("\n" + "="*70)
                    print("MAİL DOĞRULAMA İÇİN BEKLENİYOR...")
                    print("Lütfen e-postanızı kontrol edin ve doğrulama işlemini tamamlayın.")
                    print("Doğrulama tamamlandıktan sonra ENTER'a basın.")
                    print("="*70)
                    input("Devam etmek için ENTER'a basın: ")
                    
                    # ✅ Mail doğrulaması tamamlandıktan sonra oturum kaydet
                    context = page.context
                    context.storage_state(path=self.session_file)
                    print(f"[SUCCESS] Mail doğrulaması sonrası oturum kaydedildi: {self.session_file}")
                    
                    # Ek olarak JSON cookie/localStorage da istiyorsan:
                    self._save_session_data(page, context)
                
                print("\n" + "="*60)
                print("GİRİŞ BAŞARILI - ARTIK İŞLEMLERE DEVAM EDEBİLİRSİNİZ")
                print("="*60)
                input("İşlemi sonlandırmak için ENTER'a basın: ")
                
                print("[SUCCESS] İşlem tamamlandı.")
                
        except PWTimeoutError as e:
            print(f"[ERROR] Zaman aşımı hatası: {e}")
        except Exception as e:
            print(f"[ERROR] Beklenmeyen hata: {e}")
        finally:
            print("[INFO] Browser kapatılıyor...")
            if page:
                page.close()
            if context:
                context.close()
            if browser:
                browser.close()
            print("[INFO] Browser kapatıldı.")

    def _check_login_success(self, page):
        """Login başarılı mı kontrol et"""
        try:
            time.sleep(3)  # Sayfanın yüklenmesi için bekle
            
            current_url = page.url
            print(f"[DEBUG] Mevcut URL: {current_url}")
            
            # 1. URL kontrolü - Login sayfasından ayrıldı mı?
            if "giris" in current_url.lower() or "login" in current_url.lower():
                print("[INFO] Hala login sayfasında - URL kontrolü başarısız")
                
                # 2. Login formu kontrolü
                username_exists = False
                for selector in self.USER_CANDS[:2]:
                    try:
                        element = page.query_selector(selector)
                        if element and element.is_visible():
                            username_exists = True
                            print(f"[INFO] Login formu bulundu: {selector}")
                            break
                    except:
                        continue
                
                if username_exists:
                    print("[INFO] Login formu görünür durumda - Cookie geçersiz")
                    return False
            
            # 3. Dashboard/Ana sayfa elementlerini kontrol et
            # Başarılı girişten sonra görünmesi gereken elementler
            success_indicators = [
                'a[href*="cikis"]',  # Çıkış linki
                'a[href*="logout"]',
                'button:has-text("Çıkış")',
                '.user-menu',
                '.dashboard',
                '[class*="nav"]',  # Navigation bar
                '[class*="menu"]'
            ]
            
            for selector in success_indicators:
                try:
                    element = page.query_selector(selector)
                    if element:
                        print(f"[SUCCESS] Başarılı giriş göstergesi bulundu: {selector}")
                        return True
                except:
                    continue
            
            # 4. Sayfa içeriğini kontrol et
            page_content = page.content().lower()
            
            # Başarılı giriş keyword'leri
            success_keywords = ['hoşgeldin', 'hosgeldin', 'dashboard', 'ana sayfa', 'çıkış', 'cikis', 'logout']
            login_keywords = ['giriş yap', 'giris yap', 'kullanıcı adı', 'kullanici adi', 'şifre', 'sifre']
            
            success_found = any(keyword in page_content for keyword in success_keywords)
            login_found = any(keyword in page_content for keyword in login_keywords)
            
            print(f"[DEBUG] Başarı keyword'leri bulundu: {success_found}")
            print(f"[DEBUG] Login keyword'leri bulundu: {login_found}")
            
            if success_found and not login_found:
                print("[INFO] İçerik analizi: Giriş başarılı görünüyor")
                return True
            
            print("[WARNING] Giriş başarısı doğrulanamadı - Manuel kontrol gerekebilir")
            
            # Son bir şans: Kullanıcıya sor
            print("\n" + "="*60)
            print("MANUEL KONTROL GEREKİYOR")
            print("Lütfen tarayıcıyı kontrol edin:")
            print("- Giriş başarılı mı?")
            print("- Ana sayfada mısınız?")
            print("="*60)
            response = input("Giriş başarılı mı? (e/h): ").strip().lower()
            
            return response == 'e' or response == 'evet'
            
        except Exception as e:
            print(f"[ERROR] Login kontrolünde hata: {e}")
            return False

    def run_with_cookies(self, context, page):
        """Kaydedilmiş oturum verileriyle giriş yap"""
        try:
            # Oturum verilerini yükle
            if not self._load_session_data(page, context):
                print("[WARNING] Oturum dosyası bulunamadı.")
                return False
            
            # Login başarılı mı kontrol et
            if self._check_login_success(page):
                print("[SUCCESS] Oturum verileriyle giriş başarılı!")
                return True
            else:
                print("[WARNING] Oturum verileriyle giriş başarısız. Normal login yapılacak.")
                return False
                
        except Exception as e:
            print(f"[ERROR] Oturum verileriyle giriş hatası: {e}")
            return False


if __name__ == "__main__":
    try:
        print("="*60)
        print("ANADOLU SCRAPER - AKILLI GİRİŞ SİSTEMİ")
        print("="*60)
        
        scraper = AnadoluScraper()
        scraper.run()
            
        print("\n" + "="*60)
        print("İŞLEM TAMAMLANDI")
        print("="*60)
        
    except RuntimeError as e:
        print(f"[FATAL] {e}")
    except Exception as e:
        print(f"[FATAL] Beklenmeyen hata: {e}")