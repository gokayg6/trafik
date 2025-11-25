# koru_scraper.py
# Aşama-3: Koru login sayfasına giriş yap + 2FA (TOTP) doğrulaması + Trafik Sigortası Teklifi
# İyileştirilmiş versiyon

import os
import sys
import logging
import asyncio
from dotenv import load_dotenv
import pyotp
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeoutError
import time

# Windows için asyncio event loop policy ayarla (Playwright için)
# ProactorEventLoop subprocess desteği için gerekli
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

# Logging kurulumu
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class KoruScraper:
    def __init__(self):
        # Load environment variables with UTF-8 encoding
        try:
            load_dotenv(encoding='utf-8')
        except (UnicodeDecodeError, Exception):
            try:
                load_dotenv()
            except Exception:
                pass
        self.login_url = os.getenv("KORU_LOGIN_URL", "").strip()
        # Headless modu - varsayılan olarak False (görünür mod)
        self.headless = os.getenv("HEADLESS", "false").lower() == "true"
        # Debug için headless'i False yap
        if os.getenv("KORU_DEBUG", "false").lower() == "true":
            self.headless = False
        self.timeout_ms = int(os.getenv("KORU_TIMEOUT_MS", "45000"))
        self.username = os.getenv("KORU_USER", "").strip()
        self.password = os.getenv("KORU_PASS", "").strip()
        self.totp_secret = os.getenv("KORU_TOTP_SECRET", "").strip()

        # Gerekli parametreleri kontrol et
        if not all([self.login_url, self.username, self.password, self.totp_secret]):
            missing = []
            if not self.login_url:
                missing.append("KORU_LOGIN_URL")
            if not self.username:
                missing.append("KORU_USER")
            if not self.password:
                missing.append("KORU_PASS")
            if not self.totp_secret:
                missing.append("KORU_TOTP_SECRET")
            raise RuntimeError(f"Eksik .env bilgisi: {', '.join(missing)}")

        # Selector'lar
        self.sel_username = 'input#Username[name="Username"][type="text"]'
        self.sel_password = 'input#Password[name="Password"][type="password"]'
        self.sel_login_btn = 'button[name="button"][value="login"], button:has-text("Giriş Yap")'
        self.sel_totp_input = 'input#Code[name="Code"][type="text"]'
        self.sel_totp_button = 'button[name="button"][value="verify"], button:has-text("Doğrula")'

    def _validate_selectors(self, page):
        """Selector'ların sayfada mevcut olup olmadığını kontrol et"""
        try:
            if not page.locator(self.sel_username).is_visible(timeout=3000):
                logger.warning("Kullanıcı adı input alanı görünür değil")
                return False
            return True
        except Exception as e:
            logger.warning(f"Selector doğrulaması başarısız: {e}")
            return False

    def _fill_credentials(self, page):
        """Kullanıcı adı ve şifre alanlarını doldur"""
        try:
            username_field = page.locator(self.sel_username)
            password_field = page.locator(self.sel_password)

            username_field.wait_for(state="visible", timeout=self.timeout_ms)
            username_field.fill(self.username, timeout=self.timeout_ms)
            logger.info("Username entered")

            password_field.wait_for(state="visible", timeout=self.timeout_ms)
            password_field.fill(self.password, timeout=self.timeout_ms)
            logger.info("Password entered")

            return True
        except Exception as e:
            logger.error(f"Kimlik bilgileri girilirken hata: {e}")
            return False

    def _click_login_button(self, page):
        """Login butonuna tıkla"""
        try:
            login_btn = page.locator(self.sel_login_btn).first
            login_btn.wait_for(state="visible", timeout=self.timeout_ms)
            login_btn.click(timeout=8000)
            logger.info("Login button clicked")
            return True
        except Exception as e:
            logger.error(f"Giriş butonu tıklanamadı: {e}")
            return False

    def _close_popups(self, page):
        """jQuery UI dialog popup'larını kapat"""
        try:
            ok_buttons = page.locator('button:has-text("Tamam")')
            count = ok_buttons.count()
            logger.info(f"Bulunan 'Tamam' butonu sayısı: {count}")
            
            if count > 0:
                for i in range(count):
                    try:
                        btn = ok_buttons.nth(i)
                        btn.scroll_into_view_if_needed()
                        btn.click(timeout=3000, force=True)
                        logger.info(f"Popup #{i+1} 'Tamam' butonuyla kapatıldı (force)")
                        page.wait_for_timeout(500)
                    except Exception as e:
                        logger.debug(f"Tamam butonu tıklama başarısız: {e}")

            close_btns = page.locator('.ui-dialog-titlebar-close')
            close_count = close_btns.count()
            logger.info(f"Bulunan kapatma butonu sayısı: {close_count}")
            
            if close_count > 0:
                for i in range(close_count):
                    try:
                        btn = close_btns.nth(i)
                        btn.scroll_into_view_if_needed()
                        btn.click(timeout=3000, force=True)
                        logger.info(f"Popup #{i+1} X butonuyla kapatıldı (force)")
                        page.wait_for_timeout(500)
                    except Exception as e:
                        logger.debug(f"X butonu tıklama başarısız: {e}")

            # Overlay temizleme
            page.evaluate("""
                () => {
                    document.querySelectorAll('.ui-widget-overlay').forEach(el => el.remove());
                    document.querySelectorAll('.ui-dialog').forEach(el => el.style.display = 'none');
                }
            """)
            logger.info("Popup overlay'leri kaldırıldı")
        except Exception as e:
            logger.error(f"Popup kapatma hatası: {e}")

    def _handle_totp(self, page):
        """TOTP doğrulamasını işle"""
        try:
            totp_input = page.locator(self.sel_totp_input)
            totp_input.wait_for(state="visible", timeout=15000)
            logger.info("TOTP ekranı yüklendi")

            totp = pyotp.TOTP(self.totp_secret)
            code = totp.now()

            totp_input.fill(code, timeout=self.timeout_ms)
            logger.info(f"TOTP code entered: {code}")

            verify_btn = page.locator(self.sel_totp_button).first
            verify_btn.wait_for(state="visible", timeout=self.timeout_ms)
            verify_btn.click(timeout=8000)
            logger.info("Doğrulama butonuna tıklandı")

            return True
        except PWTimeoutError:
            logger.error("TOTP ekranı zaman aşımı: Login başarısız olabilir")
            return False
        except Exception as e:
            logger.error(f"TOTP doğrulaması başarısız: {e}")
            return False

    def create_trafik_sigortasi(self, page, teklif_data):
        """
        Trafik sigortası teklif formunu doldurur ve teklifi alır.
        """
        try:
            logger.info("Trafik sigortası form being filled...")

            # 🔹 1. Hızlı Trafik (Sepet) ikonuna tıklama
            trafik_icon = page.locator("table#police_hizli_trafik_sepet img#img_police_hizli_trafik_sepet")
            trafik_icon.wait_for(state="visible", timeout=10000)
            trafik_icon.click()
            logger.info("Trafik ikonuna tıklandı, sayfa yükleniyor...")
            page.wait_for_timeout(10000)

            # 🔹 2. Kimlik No doldur
            kimlik_input = page.locator("#kimlikNoInput")
            kimlik_input.wait_for(state="visible", timeout=15000)
            kimlik_input.fill(teklif_data["tc"])
            logger.info("TC kimlik no girildi")
            page.wait_for_timeout(3000)

            # 🔹 3. Doğum tarihi alanı boşsa doldur
            dogum_input = page.locator('#dogumTarihiInput input')
            dogum_degeri = dogum_input.input_value()
            if not dogum_degeri.strip():
                dogum_input.fill(teklif_data["dogum_tarihi"])
                logger.info("Doğum tarihi girildi")
                page.wait_for_timeout(3000)
            else:
                logger.info("Doğum tarihi zaten dolu, atlandı")

            # 🔹 4. Plaka İl ve Plaka No alanlarını kontrol et ve boşsa doldur
            plaka_il_input = page.locator("#plakaIlCodeuInput")
            plaka_no_input = page.locator("#plakaCodeuInput")

            plaka_il_value = plaka_il_input.input_value().strip()
            plaka_no_value = plaka_no_input.input_value().strip()

            if not plaka_il_value:
                plaka_il_input.fill(teklif_data["plaka_il"])
                logger.info("Plaka il kodu girildi")
                page.wait_for_timeout(3000)
            else:
                logger.info("Plaka il kodu zaten dolu, atlandı")

            if not plaka_no_value:
                plaka_no_input.fill(teklif_data["plaka_no"])
                logger.info("Plaka numarası girildi")
                page.wait_for_timeout(3000)
            else:
                logger.info("Plaka numarası zaten dolu, atlandı")

            # 🔹 6. Tescil no boşsa doldur
            tescil_no_input = page.locator("#tescilNoInput")
            if not tescil_no_input.input_value().strip():
                tescil_no_input.fill(teklif_data["tescil_no"])
                logger.info("Tescil numarası girildi")
                page.wait_for_timeout(3000)
            else:
                logger.info("Tescil numarası zaten dolu, atlandı")

            tescil_kod_input = page.locator("#tescilCodeInput")
            if not tescil_kod_input.input_value().strip():
                tescil_kod_input.fill(teklif_data["tescil_kod"])
                logger.info("Tescil kodu girildi")
                page.wait_for_timeout(3000)
            else:
                logger.info("Tescil kodu zaten dolu, atlandı")

            # 🔹 7. Teklif Al butonuna tıklama
            teklif_buton = page.locator('input[type="button"][value="Teklif Al"]')
            teklif_buton.wait_for(state="visible", timeout=10000)
            teklif_buton.click()
            logger.info("Teklif Al butonuna tıklandı, sonuç bekleniyor...")

            # 🔹 8. Tablo yüklenmesini beklemek için farklı stratejiler
            try:
                # Önce loading/processing göstergelerini kontrol et
                logger.info("Sayfa yüklenmesi bekleniyor...")

                # Alternatif 1: Tablonun görünür olmasını bekle
                page.wait_for_selector('#tblCaprazSatisTeklifTablosu', timeout=60000)
                logger.info("Teklif tablosu görünür oldu")

                # Alternatif 2: Tablo satırlarını bekle (daha uzun timeout)
                page.wait_for_selector('#tblCaprazSatisTeklifTablosu tbody tr', timeout=60000)
                logger.info("Tablo satırları yüklendi")

                # Alternatif 3: "TRAFIK" yazısının görünmesini bekle
                try:
                    page.wait_for_selector('td:has-text("TRAFIK")', timeout=30000)
                    logger.info("TRAFIK ürünü tabloda görüldü")
                except:
                    logger.warning("TRAFIK ürünü doğrudan bulunamadı, tabloyu tarıyoruz...")

                # Tabloyu al
                satirlar = page.locator('#tblCaprazSatisTeklifTablosu tbody tr')
                satir_sayisi = satirlar.count()
                logger.info(f"Toplam {satir_sayisi} quote rows found")

                trafik_teklifi = None

                for i in range(satir_sayisi):
                    try:
                        # Ürün adını al (3. sütun)
                        urun_adi = satirlar.nth(i).locator('td:nth-child(3)').inner_text(timeout=5000).strip()
                        logger.info(f"Satır {i+1} - Ürün Adı: '{urun_adi}'")

                        if urun_adi.upper() == "TRAFIK":
                            sigortali_ad = satirlar.nth(i).locator('td:nth-child(1)').inner_text(timeout=5000).strip()
                            teklif_no = satirlar.nth(i).locator('td:nth-child(2) a').inner_text(timeout=5000).strip()
                            prim = satirlar.nth(i).locator('td:nth-child(5)').inner_text(timeout=5000).strip()

                            trafik_teklifi = {
                                "sigortali_ad": sigortali_ad,
                                "teklif_no": teklif_no,
                                "urun_adi": urun_adi,
                                "prim": prim
                            }
                            logger.info(f"TRAFIK teklifi bulundu: {trafik_teklifi}")
                            break
                    except Exception as satir_hata:
                        logger.warning(f"Satır {i+1} okunamadı: {satir_hata}")
                        continue

                if not trafik_teklifi:
                    logger.warning("TRAFIK teklifi bulunamadı!")
                    # Hata ayıklama için tüm satırları logla
                    logger.info("Mevcut teklifler:")
                    for i in range(satir_sayisi):
                        try:
                            urun_adi = satirlar.nth(i).locator('td:nth-child(3)').inner_text(timeout=3000).strip()
                            prim = satirlar.nth(i).locator('td:nth-child(5)').inner_text(timeout=3000).strip()
                            logger.info(f"  - {urun_adi}: {prim}")
                        except:
                            logger.info(f"  - Satır {i+1}: Okunamadı")
                    return None

                return trafik_teklifi

            except Exception as e:
                logger.error(f"TRAFIK teklifini alırken hata oluştu: {e}")

                # Sayfa kaynağını hata ayıklama için kaydet
                try:
                    page_content = page.content()
                    with open("debug_page.html", "w", encoding="utf-8") as f:
                        f.write(page_content)
                    logger.info("Hata ayıklama için sayfa kaynağı 'debug_page.html' saved to file")
                except:
                    pass

                return None

        except Exception as e:
            logger.error(f"[HATA] Trafik sigortası teklifi oluşturulamadı: {e}")
            return False
        

    def create_kasko_sigortasi(self, page, teklif_data):
        """
        Kasko sigortası teklif formunu doldurur ve teklifi alır.
        teklif_data örneği:
        {
            "tc": "12345678901",
            "dogum_tarihi": "01.01.1990",
            "plaka_il": "34",
            "plaka_no": "ABC123",
            "tescil_kod": "AB",
            "tescil_no": "123456"
        }
        """
        try:
            logger.info("Kasko sigortası form being filled...")

            # 🔹 1. Hızlı Kasko (Sepet) ikonuna tıklama
            kasko_icon = page.locator("table#police_hizli_kasko_sepet img#img_police_hizli_kasko_sepet")
            kasko_icon.wait_for(state="visible", timeout=10000)
            kasko_icon.click()
            logger.info("Kasko ikonuna tıklandı, sayfa yükleniyor...")
            page.wait_for_timeout(10000)

            # 🔹 2. Kimlik No doldur
            kimlik_input = page.locator("#kimlikNoInput")
            kimlik_input.wait_for(state="visible", timeout=15000)
            kimlik_input.fill(teklif_data["tc"])
            logger.info("TC kimlik no girildi")
            page.wait_for_timeout(3000)

            # 🔹 3. Doğum tarihi alanı boşsa doldur
            dogum_input = page.locator('#dogumTarihiInput input')
            dogum_degeri = dogum_input.input_value()
            if not dogum_degeri.strip():
                dogum_input.fill(teklif_data["dogum_tarihi"])
                logger.info("Doğum tarihi girildi")
                page.wait_for_timeout(3000)
            else:
                logger.info("Doğum tarihi zaten dolu, atlandı")

            # 🔹 4. Plaka İl ve Plaka No alanlarını kontrol et ve boşsa doldur
            plaka_il_input = page.locator("#plakaIlCodeuInput")
            plaka_no_input = page.locator("#plakaCodeuInput")

            plaka_il_value = plaka_il_input.input_value().strip()
            plaka_no_value = plaka_no_input.input_value().strip()

            if not plaka_il_value:
                plaka_il_input.fill(teklif_data["plaka_il"])
                logger.info("Plaka il kodu girildi")
                page.wait_for_timeout(3000)
            else:
                logger.info("Plaka il kodu zaten dolu, atlandı")

            if not plaka_no_value:
                plaka_no_input.fill(teklif_data["plaka_no"])
                logger.info("Plaka numarası girildi")
                page.wait_for_timeout(3000)
            else:
                logger.info("Plaka numarası zaten dolu, atlandı")

            # 🔹 5. Tescil kodu boşsa doldur
            tescil_kod_input = page.locator("#tescilCodeInput")
            if not tescil_kod_input.input_value().strip():
                tescil_kod_input.fill(teklif_data["tescil_kod"])
                logger.info("Tescil kodu girildi")
                page.wait_for_timeout(3000)
            else:
                logger.info("Tescil kodu zaten dolu, atlandı")

            # 🔹 6. Tescil no boşsa doldur
            tescil_no_input = page.locator("#tescilNoInput")
            if not tescil_no_input.input_value().strip():
                tescil_no_input.fill(teklif_data["tescil_no"])
                logger.info("Tescil numarası girildi")
                page.wait_for_timeout(3000)
            else:
                logger.info("Tescil numarası zaten dolu, atlandı")

            # 🔹 7. Meslek seçimi - Otomatik "Diğer" seç
            meslek_select = page.locator("#sigortaliMeslek")
            meslek_select.select_option(value="3")  # 3 = Diğer
            page.wait_for_timeout(3000)

            # 🔹 8. Teklif Al butonuna tıklama
            teklif_buton = page.locator('input[type="button"][value="Teklif Al"]')
            teklif_buton.wait_for(state="visible", timeout=10000)
            teklif_buton.click()
            logger.info("Teklif Al butonuna tıklandı, sonuç bekleniyor...")

            # 🔹 9. Tablo yüklenmesini beklemek için farklı stratejiler
            try:
                logger.info("Sayfa yüklenmesi bekleniyor...")

                # Tablonun görünür olmasını bekle
                page.wait_for_selector('#tblCaprazSatisTeklifTablosu', timeout=60000)
                logger.info("Teklif tablosu görünür oldu")

                # Tablo satırlarını bekle
                page.wait_for_selector('#tblCaprazSatisTeklifTablosu tbody tr', timeout=60000)
                logger.info("Tablo satırları yüklendi")

                # Tabloyu al
                satirlar = page.locator('#tblCaprazSatisTeklifTablosu tbody tr')
                satir_sayisi = satirlar.count()
                logger.info(f"Toplam {satir_sayisi} quote rows found")

                kasko_teklifleri = []

                for i in range(satir_sayisi):
                    try:
                        # Ürün adını al (3. sütun)
                        urun_adi = satirlar.nth(i).locator('td:nth-child(3)').inner_text(timeout=2000).strip()
                        logger.info(f"Satır {i+1} - Ürün Adı: '{urun_adi}'")

                        # Kasko ürünlerini filtrele
                        if "KASKO" in urun_adi.upper():
                            sigortali_ad = satirlar.nth(i).locator('td:nth-child(1)').inner_text(timeout=2000).strip()
                            teklif_no = satirlar.nth(i).locator('td:nth-child(2) a').inner_text(timeout=2000).strip()
                            prim = satirlar.nth(i).locator('td:nth-child(5)').inner_text(timeout=2000).strip()

                            kasko_teklifi = {
                                "sigortali_ad": sigortali_ad,
                                "teklif_no": teklif_no,
                                "urun_adi": urun_adi,
                                "prim": prim
                            }
                            kasko_teklifleri.append(kasko_teklifi)
                            logger.info(f"Kasko teklifi bulundu: {kasko_teklifi}")

                    except Exception as satir_hata:
                        logger.debug(f"Satır {i+1} okunamadı: {satir_hata}")
                        continue

                if not kasko_teklifleri:
                    logger.warning("Kasko teklifi bulunamadı!")
                    # Hata ayıklama için tüm satırları logla
                    logger.info("Mevcut teklifler:")
                    for i in range(satir_sayisi):
                        try:
                            urun_adi = satirlar.nth(i).locator('td:nth-child(3)').inner_text(timeout=2000).strip()
                            prim = satirlar.nth(i).locator('td:nth-child(5)').inner_text(timeout=2000).strip()
                            logger.info(f"  - {urun_adi}: {prim}")
                        except:
                            logger.info(f"  - Satır {i+1}: Okunamadı")
                    return None

                # İlk kasko teklifini döndür
                return kasko_teklifleri[0] if kasko_teklifleri else None

            except Exception as e:
                logger.error(f"Kasko teklifini alırken hata oluştu: {e}")


                return None

        except Exception as e:
            logger.error(f"[HATA] Kasko sigortası teklifi oluşturulamadı: {e}")
            return False

    def run(self, trafik_data=None, kasko_data=None):
        """Ana çalıştırma fonksiyonu"""
        # Windows için event loop policy ayarla (her run'da)
        if sys.platform == "win32":
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
            # Mevcut event loop'u kapat ve yeni bir tane oluştur
            try:
                try:
                    loop = asyncio.get_event_loop()
                    if loop and not loop.is_closed():
                        loop.close()
                except RuntimeError:
                    pass
            except:
                pass
            # Yeni event loop oluştur
            asyncio.set_event_loop(asyncio.new_event_loop())
        
        browser = None
        try:
            with sync_playwright() as pw:
                browser = pw.chromium.launch(headless=self.headless)
                context = browser.new_context(viewport={"width": 1366, "height": 900})
                page = context.new_page()

                page.goto(self.login_url, wait_until="domcontentloaded", timeout=self.timeout_ms)
                logger.info(f"Login sayfası açıldı: {self.login_url}")

                if not self._validate_selectors(page):
                    logger.warning("Selector doğrulaması başarısız, continuing...")

                if not self._fill_credentials(page):
                    raise RuntimeError("Kimlik bilgileri girilemedi")

                if not self._click_login_button(page):
                    raise RuntimeError("Login butonu tıklanamadı")

                if not self._handle_totp(page):
                    raise RuntimeError("TOTP doğrulaması başarısız")

                page.wait_for_load_state("domcontentloaded", timeout=self.timeout_ms)
                logger.info(f"Login işlemi tamamlandı. URL: {page.url}")
                time.sleep(5)

                self._close_popups(page)

                result = {}
                
                # Trafik sigortası teklif işlemi
                if trafik_data:
                    trafik_teklifi = self.create_trafik_sigortasi(page, trafik_data)
                    logger.info(f"Trafik teklifi sonucu: {trafik_teklifi}")
                    result["trafik"] = trafik_teklifi
    
                # Kasko sigortası teklif işlemi
                if kasko_data:
                    kasko_teklifi = self.create_kasko_sigortasi(page, kasko_data)
                    logger.info(f"Kasko teklifi sonucu: {kasko_teklifi}")
                    result["kasko"] = kasko_teklifi
    
                if not self.headless:
                    input("\nTarayıcı açık. Kapatmak için Enter'a basın...")
    
                return result if result else False
    
        except Exception as e:
            logger.error(f"Ölümcül hata: {e}")
            return False
        # Finally bloğunu kaldırdık - sync_playwright() context manager browser'ı otomatik kapatır
    
    def run_trafik_with_data(self, teklif_data):
        """Trafik sigortası için scraper çalıştır"""
        return self.run(trafik_data=teklif_data)
    
    def run_kasko_with_data(self, teklif_data):
        """Kasko sigortası için scraper çalıştır"""
        return self.run(kasko_data=teklif_data)

if __name__ == "__main__":
    try:
        scraper = KoruScraper()
        success = scraper.run()
        sys.exit(0 if success else 1)
    except RuntimeError as e:
        logger.error(f"Yapılandırma hatası: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Beklenmeyen hata: {e}")
        sys.exit(1)
