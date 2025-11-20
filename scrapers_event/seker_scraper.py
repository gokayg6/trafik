# seker_scraper.py
# Aşama: Şeker login sayfasını aç + username/şifre doldur + girişe bas.
# Not: TOTP/Doğrula YOK. Sen manuel girip tıklıyorsun.

import os
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeoutError
import time
import random

class SekerScraper:
    def __init__(self):
        load_dotenv()
        self.login_url = os.getenv("SEKER_LOGIN_URL", "").strip()
        self.username  = os.getenv("SEKER_USER", "").strip()
        self.password  = os.getenv("SEKER_PASS", "").strip()
        self.headless  = os.getenv("HEADLESS", "false").lower() == "true"
        self.timeout   = int(os.getenv("SEKER_TIMEOUT_MS", "45000"))

        if not self.login_url:
            raise RuntimeError("SEKER_LOGIN_URL .env içinde tanımlı değil.")
        if not self.username or not self.password:
            raise RuntimeError("SEKER_USER ve SEKER_PASS .env içinde olmalı.")

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

    def _first_visible(self, page, selectors):
        for sel in selectors:
            try:
                loc = page.locator(sel).first
                if loc.count() and loc.is_visible():
                    return loc
            except Exception:
                pass
        return None

    def _take_screenshot(self, page, name):
        """Hata durumunda ekran görüntüsü al"""
        screenshot_path = f"screenshot_{name}_{int(time.time())}.png"
        try:
            page.screenshot(path=screenshot_path, full_page=True)
            print(f"[INFO] Ekran görüntüsü kaydedildi: {screenshot_path}")
        except Exception as e:
            print(f"[WARN] Ekran görüntüsü alınamadı: {e}")

    def _ayristir_tescil_no(self, tescil_birlestirilmis):
        """
        Birleşik tescil numarasını seri ve no olarak ayırır
        Örnek: "AB1234567890" -> ("AB", "1234567890")
        """
        if not tescil_birlestirilmis:
            return None, None
        
        # İlk 2 karakter seri, geri kalanı no
        if len(tescil_birlestirilmis) >= 2:
            tescil_seri = tescil_birlestirilmis[:2]  # İlk 2 karakter
            tescil_no = tescil_birlestirilmis[2:]    # Geri kalan karakterler
            return tescil_seri, tescil_no
        else:
            print(f"[WARN] Tescil numarası çok kısa: {tescil_birlestirilmis}")
            return None, None

    def _iframe_gecis(self, page):
        """Ana iframe'e geçiş yap"""
        print("\n--- IFRAME'E GEÇİŞ YAPILIYOR ---")
        
        try:
            # Iframe'i bekle
            page.wait_for_selector('iframe#frmMain', timeout=10000)
            
            # Iframe frame elementini al
            frame_element = page.frame('frmMain')
            if not frame_element:
                # Alternatif iframe seçici
                frame_element = page.frame(url='NonLife/Policy/ViewPolicy.aspx')
            
            if frame_element:
                print("[OK] Iframe'e geçiş yapıldı")
                return frame_element
            else:
                print("[ERROR] Iframe bulunamadı")
                self._take_screenshot(page, "iframe_not_found")
                return None
                
        except Exception as e:
            print(f"[ERROR] Iframe geçiş hatası: {e}")
            self._take_screenshot(page, "iframe_error")
            return None

    def _fiyat_tablosundan_veri_al(self, frame):
        """
        Fiyat tablosundan verileri çıkar
        
        Returns:
            dict: Fiyat verileri
                {
                    'pesin': {
                        'tutar': 'X.XXX,XX',
                        'vergi': 'X.XXX,XX',
                        'toplam': 'X.XXX,XX',
                        'odeme': 'X.XXX,XX'
                    },
                    ...
                }
        """
        try:
            fiyat_verileri = {}
            
            # Tablo satırlarını al
            satir_locators = frame.locator('table.x-grid3-row-table tbody tr').all()
            
            print(f"[INFO] {len(satir_locators)} satır bulundu")
            
            for satir in satir_locators:
                # Hücreler
                hucreler = satir.locator('td.x-grid3-cell').all()
                
                if len(hucreler) >= 5:
                    # İlk hücre: Ödeme Planı Adı
                    odeme_plani_text = hucreler[1].inner_text().strip()
                    
                    # Diğer hücreler: Fiyatlar
                    tutar = hucreler[2].inner_text().strip()
                    vergi = hucreler[3].inner_text().strip()
                    toplam = hucreler[4].inner_text().strip()
                    odeme = hucreler[5].inner_text().strip() if len(hucreler) > 5 else "N/A"
                    
                    fiyat_verileri[odeme_plani_text] = {
                        'tutar': tutar,
                        'vergi': vergi,
                        'toplam': toplam,
                        'odeme': odeme
                    }
                    
                    print(f"[INFO] {odeme_plani_text} - Tutar: {tutar}, Vergi: {vergi}, Toplam: {toplam}")
            
            return fiyat_verileri if fiyat_verileri else None
            
        except Exception as e:
            print(f"[ERROR] Fiyat tablosu verisi alınırken hata: {e}")
            self._take_screenshot(frame.page, "fiyat_tablosu_error")
            return None

    def _secim_dropdown_ac_ve_sec(self, frame, dropdown_input_id, deger):
        """
        Dropdown açar ve belirtilen değeri seçer (Extjs Combo Box)
        
        Args:
            frame: Playwright frame object
            dropdown_input_id: Dropdown input element ID
            deger: Seçilecek değer/metin
        """
        try:
            print(f"[INFO] Dropdown açılıyor: {dropdown_input_id}")
            print(f"[INFO] Aranacak değer: {deger}")
            
            # Input elementini bul
            input_elem = frame.locator(f'input#{dropdown_input_id}').first
            
            if not input_elem.count():
                print(f"[ERROR] Input element bulunamadı: {dropdown_input_id}")
                return False
            
            # Input'u temizle
            input_elem.fill("")
            time.sleep(0.5)
            
            # Input'a focus ver
            input_elem.focus()
            time.sleep(1)
            
            # Değeri yazarak dropdown'u aç (Combo box yazarak arama)
            print(f"[INFO] Dropdown açmak için ilk karakterler yazılıyor...")
            input_elem.type(deger[:3], delay=200)
            time.sleep(2)
            
            # Dropdown listesi açılıncaya kadar bekle
            try:
                frame.wait_for_selector('div.x-combo-list-item', timeout=5000)
                print("[OK] Dropdown listesi açıldı")
            except:
                print("[WARN] Dropdown listesi açılmadı, sayfaya tıklayarak tekrar deniyoruz...")
                # Trigger image'ine tıkla
                trigger_img = frame.locator(f'input#{dropdown_input_id}').first.locator('~ img.x-form-trigger').first
                if trigger_img.count():
                    trigger_img.click()
                    time.sleep(2)
                else:
                    # Parent div içindeki img'i ara
                    input_parent = frame.locator(f'input#{dropdown_input_id}').first
                    trigger_img = input_parent.locator('xpath=../img.x-form-trigger').first
                    if trigger_img.count():
                        trigger_img.click()
                        time.sleep(2)
            
            time.sleep(1.5)
            
            # Dropdown listesinde değeri ara
            liste_items = frame.locator('div.x-combo-list-item').all()
            
            print(f"[INFO] {len(liste_items)} kombo item bulundu")
            
            seçildi = False
            for idx, item in enumerate(liste_items):
                item_text = item.inner_text().strip()
                print(f"[DEBUG] [{idx}] Item: '{item_text}'")
                
                # Tam eşleşme veya kısmi eşleşme kontrolü
                if item_text.upper() == deger.upper():
                    print(f"[OK] Tam eşleşme bulundu: {item_text}")
                    item.click()
                    seçildi = True
                    time.sleep(2)
                    break
                elif deger.upper() in item_text.upper():
                    print(f"[OK] Kısmi eşleşme bulundu: {item_text}")
                    item.click()
                    seçildi = True
                    time.sleep(2)
                    break
            
            if seçildi:
                print(f"[OK] Değer başarıyla seçildi: {deger}")
                
                # Seçim sonrası değerleri kontrol et
                time.sleep(1)
                input_value = input_elem.input_value()
                hidden_value_field = frame.locator(f'input#{dropdown_input_id}_Value').first
                hidden_index_field = frame.locator(f'input#{dropdown_input_id}_SelIndex').first
                
                print(f"[INFO] Input value: {input_value}")
                if hidden_value_field.count():
                    print(f"[INFO] Hidden value: {hidden_value_field.get_attribute('value')}")
                if hidden_index_field.count():
                    print(f"[INFO] Hidden index: {hidden_index_field.get_attribute('value')}")
                
                return True
            else:
                print(f"[ERROR] '{deger}' değeri dropdown'da bulunamadı")
                print(f"[INFO] Mevcut liste öğeleri:")
                for idx, item in enumerate(liste_items[:10]):  # İlk 10 öğeyi yazdır
                    print(f"  [{idx}] {item.inner_text().strip()}")
                
                # Dropdown'u kapat (Escape tuşu)
                input_elem.press("Escape")
                time.sleep(1)
                
                self._take_screenshot(frame.page, "dropdown_value_not_found")
                return False
                
        except Exception as e:
            print(f"[ERROR] Dropdown seçim hatası: {e}")
            import traceback
            traceback.print_exc()
            self._take_screenshot(frame.page, "dropdown_select_error")
            return False

    def kasko_sigortasi_islemleri(self, page, kasko_args=None):
        """
        Kasko sigortası işlemlerini gerçekleştir

        Args:
            page: Playwright page object
            kasko_args: Kasko sigortası argümanları (dict)
                - plaka: Araç plakası
                - tckn: TC Kimlik No
                - tescil: Birleşik tescil numarası
                - kullanim_tarzi: Kullanım tarzı (örn: "HUSUSİ OTO")
        """
        print("\n" + "="*60)
        print("KASKO SİGORTASI İŞLEMLERİ BAŞLATILIYOR")
        print("="*60)

        # Argümanları dict'ten al
        plaka = kasko_args.get('plaka') if kasko_args else None
        tckn = kasko_args.get('tckn') if kasko_args else None
        tescil_birlestirilmis = kasko_args.get('tescil') if kasko_args else None
        kullanim_tarzi = kasko_args.get('kullanim_tarzi') if kasko_args else None
        
        # Birleşik tescil numarasını ayır
        tescil_seri, tescil_no = self._ayristir_tescil_no(tescil_birlestirilmis)
        
        print(f"[INFO] Plaka: {plaka}")
        print(f"[INFO] TCKN: {tckn}")
        print(f"[INFO] Tescil (Birleşik): {tescil_birlestirilmis}")
        print(f"[INFO] Tescil Seri (Ayrılmış): {tescil_seri}")
        print(f"[INFO] Tescil No (Ayrılmış): {tescil_no}")
        print(f"[INFO] Kullanım Tarzı: {kullanim_tarzi}")

        try:

            # 1. ADIM: "Teklif/Poliçe" menüsüne tıkla (iframe içinde)
            print("\n--- 1. ADIM: Teklif/Poliçe menüsüne tıklanıyor ---")
            teklif_police_selectors = [
                'a.x-tree-node-anchor:has-text("Teklif/Poliçe")',
                'a:has-text("Teklif/Poliçe")',
                'span:has-text("Teklif/Poliçe")'
            ]

            teklif_police_link = self._first_visible(page, teklif_police_selectors)
            if teklif_police_link:
                teklif_police_link.click()
                print("[OK] Teklif/Poliçe menüsüne tıklandı")
                time.sleep(5)
            else:
                print("[ERROR] Teklif/Poliçe menüsü bulunamadı")
                self._take_screenshot(page, "kasko_teklif_police_not_found")
                return False

            # 2. ADIM: "Kasko" menüsüne tıkla (iframe içinde)
            print("\n--- 2. ADIM: Kasko menüsüne tıklanıyor ---")
            kasko_selectors = [
                'a.x-tree-node-anchor:has-text("Kasko")',
                'a:has-text("Kasko")',
                'span:has-text("Kasko")'
            ]

            kasko_link = self._first_visible(page, kasko_selectors)
            if kasko_link:
                kasko_link.click()
                print("[OK] Kasko menüsüne tıklandı")
                time.sleep(5)
            else:
                print("[ERROR] Kasko menüsü bulunamadı")
                self._take_screenshot(page, "kasko_menu_not_found")
                return False

            # 3. ADIM: Kasko ürün linkine tıkla
            print("\n--- 3. ADIM: Kasko ürün linkine tıklanıyor ---")
            kasko_urun_selectors = [
                'a.x-tree-node-anchor[href*="SavePolicy"]',
                'a:has-text("Kasko")',
                'a[href*="/NonLife/Policy/SavePolicy.aspx?APP_MP=320"]'
            ]

            kasko_urun_link = self._first_visible(page, kasko_urun_selectors)
            if kasko_urun_link:
                kasko_urun_link.click()
                print("[OK] Kasko ürün linkine tıklandı")

                # 4. ADIM: 10 saniye bekle (yeni iframe içeriği yüklenmesi için)
                print("[INFO] Sayfanın yüklenmesi için 10 saniye bekleniyor...")
                time.sleep(15)

                # Yeni iframe içeriği yüklendi, tekrar frame alalım
                frame = self._iframe_gecis(page)
                if not frame:
                    return False

                print(f"[OK] Kasko sigortası form sayfasına yönlendirildi")

            else:
                print("[ERROR] Kasko ürün linki bulunamadı")
                self._take_screenshot(page, "kasko_urun_not_found")
                return False

            # 5. ADIM: FORM ALANLARINI DOLDUR (iframe içinde)
            print("\n--- 4. ADIM: Form Alanları Dolduruluyor ---")
            
            # TC Kimlik No alanını doldur
            print("[INFO] TC Kimlik No yazılıyor...")
            tc_selectors = [
                'input#txtIdentityNo',
                'input[name="txtIdentityNo"]',
                'input[id*="IdentityNo"]',
                '#txtGIFTIdentityNo'
            ]
            
            tc_input = self._first_visible(frame, tc_selectors)
            if tc_input:
                if tckn:
                    tc_input.fill(tckn)
                    print(f"[OK] TC Kimlik No yazıldı: {tckn}")
                else:
                    print("[WARN] TCKN bilgisi verilmedi, manuel giriş gerekebilir")
            else:
                print("[ERROR] TC Kimlik No inputu bulunamadı")
                self._take_screenshot(page, "kasko_tc_input_not_found")
                return False

            # Plaka alanını doldur
            print("[INFO] Plaka yazılıyor...")
            plaka_selectors = [
                'input#txtPlate',
                'input[name="txtPlate"]',
                'input#txtCarPlate',
                'input[name="txtCarPlate"]',
                '#txtGIFTPlate'
            ]
            
            plaka_input = self._first_visible(frame, plaka_selectors)
            if plaka_input:
                if plaka:
                    plaka_input.fill(plaka)
                    print(f"[OK] Plaka yazıldı: {plaka}")
                else:
                    print("[WARN] Plaka bilgisi verilmedi, manuel giriş gerekebilir")
            else:
                print("[ERROR] Plaka inputu bulunamadı")
                self._take_screenshot(page, "kasko_plaka_input_not_found")
                return False


            # 6. ADIM: Sorgula butonuna tıkla
            print("\n--- 5. ADIM: Sorgula Butonuna Tıklanıyor ---")
            sorgula_selectors = [
                'input[type="submit"]',
                'button[type="submit"]',
                'input[value*="Sorgula"]',
                'button:has-text("Sorgula")',
                'input[id*="btnSorgula"]',
                '#ext-gen3451'
            ]
            
            sorgula_btn = self._first_visible(frame, sorgula_selectors)
            if sorgula_btn:
                sorgula_btn.click()
                print("[OK] Sorgula butonuna tıklandı")
                print("[INFO] Sorgu sonucu bekleniyor... (10 saniye)")
                time.sleep(15)
            else:
                print("[ERROR] Sorgula butonu bulunamadı")
                self._take_screenshot(page, "kasko_sorgula_button_not_found")
                return False

            # 7. ADIM: Kullanım Tarzı dropdown'dan seç
            print("\n--- 6. ADIM: Kullanım Tarzı Dropdown'dan Seçiliyor ---")
            
            if kullanim_tarzi:
                success = self._secim_dropdown_ac_ve_sec(
                    frame,
                    'cphCFB_policyInputStatistics_ctl00',
                    kullanim_tarzi
                )
                if not success:
                    print("[WARN] Kullanım Tarzı dropdown seçimi başarısız, devam ediliyor...")
                    self._take_screenshot(page, "kasko_kullanim_tarzi_dropdown_fail")
            else:
                print("[WARN] Kullanım Tarzı bilgisi verilmedi, manuel giriş gerekebilir")

            print("\nbaşlangıç tarihi seçiliyor ")
            tarih_selectors = [
                    '#ext-gen445'
            ]
            
            tarih_btn = self._first_visible(frame, tarih_selectors)
            if tarih_btn:
                tarih_btn.click()

            else:
                print("[ERROR] Sonraki Adım butonu bulunamadı")
                self._take_screenshot(page, "kasko_tarih_btn_not_found")
                return False
            time.sleep(3)
            tarih_selectors2 = [
                    '#ext-gen3690'
            ]
            
            tarih_btn2 = self._first_visible(frame, tarih_selectors2)
            if tarih_btn2:
                tarih_btn2.click()

            else:
                print("[ERROR] Sonraki Adım butonu bulunamadı")
                self._take_screenshot(page, "kasko_tarih_btn2_not_found")
                return False
            time.sleep(3)
            # 8. ADIM: "Sonraki Adım" butonuna tıkla
            print("\n--- 7. ADIM: Sonraki Adım Butonuna Tıklanıyor ---")
            sonraki_adim_selectors = [
                'button#ext-gen66',
                'button.x-btn-text.icon-resultsetnext',
                'button:has-text("Sonraki Adım")',
                'button[type="button"].icon-resultsetnext'
            ]
            
            sonraki_adim_btn = self._first_visible(frame, sonraki_adim_selectors)
            if sonraki_adim_btn:
                sonraki_adim_btn.click()
                print("[OK] Sonraki Adım butonuna tıklandı")
                print("[INFO] Sonraki sayfanın yüklenmesi için 8 saniye bekleniyor...")
                time.sleep(18)
            else:
                print("[ERROR] Sonraki Adım butonu bulunamadı")
                self._take_screenshot(page, "kasko_sonraki_adim_button_not_found")
                return False

            # 9. ADIM: Telefon numarası alanını kontrol et ve doldur
            print("\n--- 8. ADIM: Telefon Numarası Kontrol ve Girişi ---")
            telefon_selectors = [
                '#cphCFB_policyInputInformations_rptrInformations_numInformation_16'
            ]
            
            telefon_input = self._first_visible(frame, telefon_selectors)
            if telefon_input:
                telefon_degeri = telefon_input.input_value()
                
                if not telefon_degeri or telefon_degeri.strip() == "":
                    random_telefon = str(random.randint(5000000000, 5999999999))
                    
                    telefon_input.focus()
                    time.sleep(1)
                    
                    telefon_input.type(random_telefon, delay=400)
                    print(f"[OK] Telefon numarası yazıldı: {random_telefon}")
                    
                    telefon_input.blur()
                    time.sleep(2)
                    

                else:
                    print(f"[OK] Telefon numarası zaten dolu: {telefon_degeri}")
            else:
                print("[ERROR] Telefon numarası inputu bulunamadı")
                self._take_screenshot(page, "kasko_telefon_input_not_found")
                return False
            print("\ntescil tarihi seçiliyor ")
            tarih_selectors3 = [
                    '#ext-gen3867'
            ]
            
            tarih_btn3 = self._first_visible(frame, tarih_selectors3)
            if tarih_btn3:
                tarih_btn3.click()

            else:
                print("[ERROR] Sonraki Adım butonu bulunamadı")
                self._take_screenshot(page, "kasko_tarih_btn_not_found")
                return False
            time.sleep(2)
            tarih_selectors4 = [
                    '#ext-gen4467'
            ]
            
            tarih_btn4 = self._first_visible(frame, tarih_selectors4)
            if tarih_btn4:
                tarih_btn4.click()

            else:
                print("[ERROR] tarih4 butonu bulunamadı")
                self._take_screenshot(page, "kasko_tarih_btn2_not_found")
                return False
            time.sleep(3)
            # 10. ADIM: Tekrar "Sonraki Adım" butonuna tıkla
            print("\n--- 9. ADIM: Tekrar Sonraki Adım Butonuna Tıklanıyor ---")
            sonraki_adim_btn2 = self._first_visible(frame, sonraki_adim_selectors)
            if sonraki_adim_btn2:
                sonraki_adim_btn2.click()
                print("[OK] Sonraki Adım butonuna tıklandı")
                time.sleep(25)
            else:
                print("[ERROR] Sonraki Adım butonu bulunamadı")
                self._take_screenshot(page, "kasko_sonraki_adim_button_not_found_2")
                return False

            # 11. ADIM: Uyarı dialog kontrolü
            print("\n--- 10. ADIM: Uyarı Dialog Kontrolü ---")
            
            dialog_check = frame.locator('div.x-window.x-window-plain.x-window-dlg').first
            if dialog_check.is_visible():
                print("[INFO] Uyarı dialog bulundu!")
                time.sleep(2)
                
                evet_btn_selectors = [
                    'button.x-btn-text:has-text("Evet")',
                    'button:has-text("Evet")',
                    'button[type="button"]'
                ]
                
                evet_btn = self._first_visible(frame, evet_btn_selectors)
                if evet_btn:
                    evet_btn.click()
                    print("[OK] Uyarı dialog'da 'Evet' tıklandı")
                    time.sleep(10)
                else:
                    print("[ERROR] Evet butonu bulunamadı")
                    self._take_screenshot(page, "kasko_evet_button_not_found")
            else:
                print("[INFO] Uyarı dialog bulunamadı, devam ediliyor...")
                time.sleep(3)

            # 12. ADIM: Fiyat tablosundan verileri al
            print("\n--- 11. ADIM: Fiyat Tablosu Verilerini Alma ---")
            time.sleep(3)
            fiyat_verileri = self._fiyat_tablosundan_veri_al(frame)
            
            if fiyat_verileri:
                print("[OK] Fiyat verileri başarıyla alındı:")
                for tip, fiyatlar in fiyat_verileri.items():
                    print(f"  {tip}:")
                    print(f"    - Tutar: {fiyatlar.get('tutar', 'N/A')}")
                    print(f"    - Vergi: {fiyatlar.get('vergi', 'N/A')}")
                    print(f"    - Toplam: {fiyatlar.get('toplam', 'N/A')}")
                    print(f"    - Ödeme: {fiyatlar.get('odeme', 'N/A')}")
            else:
                print("[WARN] Fiyat tablosu verisi alınamadı")

            print("\n[SUCCESS] Kasko sigortası formu başarıyla tamamlandı!")
            return fiyat_verileri

        except Exception as e:
            print(f"[ERROR] Kasko sigortası işlemlerinde hata: {e}")
            self._take_screenshot(page, "kasko_sigortasi_error")
            return False

    def trafik_sigortasi_islemleri(self, page, trafik_args=None):
        """
        Trafik sigortası işlemlerini gerçekleştir

        Args:
            page: Playwright page object
            trafik_args: Trafik sigortası argümanları (dict)
                - plaka: Araç plakası
                - tckn: TC Kimlik No
                - tescil: Birleşik tescil numarası
                - kullanim_tarzi: Kullanım tarzı (örn: "HUSUSİ OTO")
        """
        print("\n" + "="*60)
        print("TRAFİK SİGORTASI İŞLEMLERİ BAŞLATILIYOR")
        print("="*60)

        # Argümanları dict'ten al
        plaka = trafik_args.get('plaka') if trafik_args else None
        tckn = trafik_args.get('tckn') if trafik_args else None
        tescil_birlestirilmis = trafik_args.get('tescil') if trafik_args else None
        kullanim_tarzi = trafik_args.get('kullanim_tarzi') if trafik_args else None
        
        # Birleşik tescil numarasını ayır
        tescil_seri, tescil_no = self._ayristir_tescil_no(tescil_birlestirilmis)
        
        print(f"[INFO] Plaka: {plaka}")
        print(f"[INFO] TCKN: {tckn}")
        print(f"[INFO] Tescil (Birleşik): {tescil_birlestirilmis}")
        print(f"[INFO] Tescil Seri (Ayrılmış): {tescil_seri}")
        print(f"[INFO] Tescil No (Ayrılmış): {tescil_no}")
        print(f"[INFO] Kullanım Tarzı: {kullanim_tarzi}")

        try:

            # 1. ADIM: "Teklif/Poliçe" menüsüne tıkla (iframe içinde)
            print("\n--- 1. ADIM: Teklif/Poliçe menüsüne tıklanıyor ---")
            teklif_police_selectors = [
                'a.x-tree-node-anchor:has-text("Teklif/Poliçe")',
                'a:has-text("Teklif/Poliçe")',
                'span:has-text("Teklif/Poliçe")'
            ]

            teklif_police_link = self._first_visible(page, teklif_police_selectors)
            if teklif_police_link:
                teklif_police_link.click()
                print("[OK] Teklif/Poliçe menüsüne tıklandı")
                time.sleep(5)
            else:
                print("[ERROR] Teklif/Poliçe menüsü bulunamadı")
                self._take_screenshot(page, "teklif_police_not_found")
                return False

            # 2. ADIM: "Trafik" menüsüne tıkla (iframe içinde)
            print("\n--- 2. ADIM: Trafik menüsüne tıklanıyor ---")
            trafik_selectors = [
                'a.x-tree-node-anchor:has-text("Trafik")',
                'a:has-text("Trafik")',
                'span:has-text("Trafik")'
            ]

            trafik_link = self._first_visible(page, trafik_selectors)
            if trafik_link:
                trafik_link.click()
                print("[OK] Trafik menüsüne tıklandı")
                time.sleep(5)
            else:
                print("[ERROR] Trafik menüsü bulunamadı")
                self._take_screenshot(page, "trafik_not_found")
                return False

            # 3. ADIM: "310 TRAFİK" linkine tıkla (iframe içinde)
            print("\n--- 3. ADIM: 310 TRAFİK linkine tıklanıyor ---")
            trafik_310_selectors = [
                'a.x-tree-node-anchor[href*="/NonLife/Policy/SavePolicy.aspx?APP_MP=310"]',
                'a:has-text("310 TRAFİK")',
                'a[href*="/NonLife/Policy/SavePolicy.aspx?APP_MP=310"]'
            ]

            trafik_310_link = self._first_visible(page, trafik_310_selectors)
            if trafik_310_link:
                trafik_310_link.click()
                print("[OK] 310 TRAFİK linkine tıklandı")

                # 4. ADIM: 10 saniye bekle (yeni iframe içeriği yüklenmesi için)
                print("[INFO] Sayfanın yüklenmesi için 10 saniye bekleniyor...")
                time.sleep(10)

                # Yeni iframe içeriği yüklendi, tekrar frame alalım
                frame = self._iframe_gecis(page)
                if not frame:
                    return False

                print(f"[OK] Trafik sigortası form sayfasına yönlendirildi")

            else:
                print("[ERROR] 310 TRAFİK linki bulunamadı")
                self._take_screenshot(page, "310_trafik_not_found")
                return False

            # 5. ADIM: FORM ALANLARINI DOLDUR (iframe içinde)
            print("\n--- 4. ADIM: Form Alanları Dolduruluyor ---")
            
            # TC Kimlik No alanını doldur
            print("[INFO] TC Kimlik No yazılıyor...")
            tc_selectors = [
                'input#txtGIFTIdentityNo',
                'input[name="txtGIFTIdentityNo"]',
                'input[id*="GIFTIdentityNo"]'
            ]
            
            tc_input = self._first_visible(frame, tc_selectors)
            if tc_input:
                if tckn:
                    tc_input.fill(tckn)
                    print(f"[OK] TC Kimlik No yazıldı: {tckn}")
                else:
                    print("[WARN] TCKN bilgisi verilmedi, manuel giriş gerekebilir")
            else:
                print("[ERROR] TC Kimlik No inputu bulunamadı")
                self._take_screenshot(page, "tc_input_not_found")
                return False

            # Plaka alanını doldur
            print("[INFO] Plaka yazılıyor...")
            plaka_selectors = [
                'input#txtGIFTPlate',
                'input[name="txtGIFTPlate"]',
                'input[id*="GIFTPlate"]'
            ]
            
            plaka_input = self._first_visible(frame, plaka_selectors)
            if plaka_input:
                if plaka:
                    plaka_input.fill(plaka)
                    print(f"[OK] Plaka yazıldı: {plaka}")
                else:
                    print("[WARN] Plaka bilgisi verilmedi, manuel giriş gerekebilir")
            else:
                print("[ERROR] Plaka inputu bulunamadı")
                self._take_screenshot(page, "plaka_input_not_found")
                return False

            # Tescil Seri alanını doldur (EGM Seri)
            print("[INFO] Tescil Seri yazılıyor...")
            tescil_seri_selectors = [
                'input#txtGIFTEGMSerial',
                'input[name="txtGIFTEGMSerial"]',
                'input[id*="GIFTEGMSerial"]'
            ]
            
            tescil_seri_input = self._first_visible(frame, tescil_seri_selectors)
            if tescil_seri_input:
                if tescil_seri:
                    tescil_seri_input.fill(tescil_seri)
                    print(f"[OK] Tescil Seri yazıldı: {tescil_seri}")
                else:
                    print("[WARN] Tescil Seri bilgisi bulunamadı, manuel giriş gerekebilir")
            else:
                print("[ERROR] Tescil Seri inputu bulunamadı")
                self._take_screenshot(page, "tescil_seri_input_not_found")
                return False

            # Tescil No alanını doldur (EGM No)
            print("[INFO] Tescil No yazılıyor...")
            tescil_no_selectors = [
                'input#txtGIFTEGMNo',
                'input[name="txtGIFTEGMNo"]',
                'input[id*="GIFTEGMNo"]'
            ]
            
            tescil_no_input = self._first_visible(frame, tescil_no_selectors)
            if tescil_no_input:
                if tescil_no:
                    tescil_no_input.fill(tescil_no)
                    print(f"[OK] Tescil No yazıldı: {tescil_no}")
                else:
                    print("[WARN] Tescil No bilgisi bulunamadı, manuel giriş gerekebilir")
            else:
                print("[ERROR] Tescil No inputu bulunamadı")
                self._take_screenshot(page, "tescil_no_input_not_found")
                return False

            # 6. ADIM: Sorgula butonuna tıkla (iframe içinde)
            print("\n--- 5. ADIM: Sorgula Butonuna Tıklanıyor ---")
            sorgula_selectors = [
                'input[type="submit"]',
                'button[type="submit"]',
                'input[value*="Sorgula"]',
                'button:has-text("Sorgula")',
                'input[id*="btnSorgula"]',
                'button[id*="btnSorgula"]'
            ]
            
            sorgula_btn = self._first_visible(frame, sorgula_selectors)
            if sorgula_btn:
                sorgula_btn.click()
                print("[OK] Sorgula butonuna tıklandı")
                
                # 7. ADIM: Sorgu sonucunun gelmesi için 10 sn bekle
                print("[INFO] Sorgu sonucu bekleniyor... (10 saniye)")
                time.sleep(16)
                
            else:
                print("[ERROR] Sorgula butonu bulunamadı")
                self._take_screenshot(page, "sorgula_button_not_found")
                return False

            # 8. ADIM: Kullanım Tarzı dropdown'dan seç
            print("\n--- 6. ADIM: Kullanım Tarzı Dropdown'dan Seçiliyor ---")
            
            if kullanim_tarzi:
                success = self._secim_dropdown_ac_ve_sec(
                    frame,
                    'cphCFB_policyInputStatistics_ctl00',
                    kullanim_tarzi
                )
                if not success:
                    print("[WARN] Kullanım Tarzı dropdown seçimi başarısız, devam ediliyor...")
                    self._take_screenshot(page, "kullanim_tarzi_dropdown_fail")
            else:
                print("[WARN] Kullanım Tarzı bilgisi verilmedi, manuel giriş gerekebilir")

            # 9. ADIM: "Sonraki Adım" butonuna tıkla
            print("\n--- 7. ADIM: Sonraki Adım Butonuna Tıklanıyor ---")
            sonraki_adim_selectors = [
                'button#ext-gen66',
                'button.x-btn-text.icon-resultsetnext',
                'button:has-text("Sonraki Adım")',
                'button[type="button"].icon-resultsetnext'
            ]
            
            sonraki_adim_btn = self._first_visible(frame, sonraki_adim_selectors)
            if sonraki_adim_btn:
                sonraki_adim_btn.click()
                print("[OK] Sonraki Adım butonuna tıklandı")
                
                # 10. ADIM: Sonraki sayfanın yüklenmesi için 8 sn bekle
                print("[INFO] Sonraki sayfanın yüklenmesi için 8 saniye bekleniyor...")
                time.sleep(15)
                
            else:
                print("[ERROR] Sonraki Adım butonu bulunamadı")
                self._take_screenshot(page, "sonraki_adim_button_not_found")
                return False

            # 11. ADIM: Telefon numarası alanını kontrol et ve doldur (veri yoksa random no gir)
            print("\n--- 8. ADIM: Telefon Numarası Kontrol ve Girişi ---")
            telefon_selectors = [
                'input#cphCFB_policyInputInformations_rptrInformations_numInformation_19',
                'input[name="cphCFB_policyInputInformations_rptrInformations_numInformation_19"]',
                'input[id*="numInformation_19"]'
            ]
            
            telefon_input = self._first_visible(frame, telefon_selectors)
            if telefon_input:
                telefon_degeri = telefon_input.input_value()
                
                if not telefon_degeri or telefon_degeri.strip() == "":
                    # Veri yok, random telefon no gir (başında 0 olmadan)
                    random_telefon = str(random.randint(5000000000, 5999999999))
                    
                    # Focus et
                    telefon_input.focus()
                    time.sleep(1)
                    
                    # Yavaş yazma
                    telefon_input.type(random_telefon, delay=400)
                    print(f"[OK] Telefon numarası yazıldı: {random_telefon}")
                    
                    # Blur event tetikle (form validation için)
                    telefon_input.blur()
                    time.sleep(2)
                    
                    # Dispatch change event
                    frame.evaluate("document.getElementById('cphCFB_policyInputInformations_rptrInformations_numInformation_19').dispatchEvent(new Event('change', { bubbles: true }))")
                    time.sleep(2)
                else:
                    print(f"[OK] Telefon numarası zaten dolu: {telefon_degeri}")
            else:
                print("[ERROR] Telefon numarası inputu bulunamadı")
                self._take_screenshot(page, "telefon_input_not_found")
                return False

            # 12. ADIM: Tekrar "Sonraki Adım" butonuna tıkla
            print("\n--- 9. ADIM: Tekrar Sonraki Adım Butonuna Tıklanıyor ---")
            sonraki_adim_btn2 = self._first_visible(frame, sonraki_adim_selectors)
            if sonraki_adim_btn2:
                sonraki_adim_btn2.click()
                print("[OK] Sonraki Adım butonuna tıklandı")
                time.sleep(15)
            else:
                print("[ERROR] Sonraki Adım butonu bulunamadı")
                self._take_screenshot(page, "sonraki_adim_button_not_found_2")
                return False

            # 13. ADIM: Uyarı dialog kontrolü (Evet/Hayır seçeneği)
            print("\n--- 10. ADIM: Uyarı Dialog Kontrolü ---")
            uyari_dialog_selectors = [
                'div.x-window.x-window-plain.x-window-dlg',
                'div#ext-comp-1054',
                'span:has-text("Uyarı")'
            ]
            
            # Dialog visible mi kontrol et
            dialog_check = frame.locator('div.x-window.x-window-plain.x-window-dlg').first
            if dialog_check.is_visible():
                print("[INFO] Uyarı dialog bulundu!")
                time.sleep(2)
                
                # Evet butonu tıkla
                evet_btn_selectors = [
                    'button.x-btn-text:has-text("Evet")',
                    'button:has-text("Evet")',
                    'button[type="button"]'
                ]
                
                evet_btn = self._first_visible(frame, evet_btn_selectors)
                if evet_btn:
                    evet_btn.click()
                    print("[OK] Uyarı dialog'da 'Evet' tıklandı")
                    time.sleep(6)
                else:
                    print("[ERROR] Evet butonu bulunamadı")
                    self._take_screenshot(page, "evet_button_not_found")
            else:
                print("[INFO] Uyarı dialog bulunamadı, devam ediliyor...")
                time.sleep(3)

            # 14. ADIM: Fiyat tablosundan verileri al
            print("\n--- 11. ADIM: Fiyat Tablosu Verilerini Alma ---")
            time.sleep(3)
            fiyat_verileri = self._fiyat_tablosundan_veri_al(frame)
            
            if fiyat_verileri:
                print("[OK] Fiyat verileri başarıyla alındı:")
                for tip, fiyatlar in fiyat_verileri.items():
                    print(f"  {tip}:")
                    print(f"    - Tutar: {fiyatlar.get('tutar', 'N/A')}")
                    print(f"    - Vergi: {fiyatlar.get('vergi', 'N/A')}")
                    print(f"    - Toplam: {fiyatlar.get('toplam', 'N/A')}")
                    print(f"    - Ödeme: {fiyatlar.get('odeme', 'N/A')}")
            else:
                print("[WARN] Fiyat tablosu verisi alınamadı")

            print("\n[SUCCESS] Trafik sigortası formu başarıyla tamamlandı!")
            return fiyat_verileri

        except Exception as e:
            print(f"[ERROR] Trafik sigortası işlemlerinde hata: {e}")
            self._take_screenshot(page, "trafik_sigortasi_error")
            return False
    def _secim_dropdown_ac_ve_sec_fixed(self, frame, dropdown_input_id, deger):
        """
        ExtJS Combo Box seçim - DÜZELTİLMİŞ

        Sorun: Dropdown açılıyor ama input'a yazı yazılmıyor diye kapanıyor.
        Çözüm: Trigger'ı tıklamak yerine input'a yazı yaz, bu dropdown'u açık tutar.
        """
        try:
            print(f"\n[INFO] Dropdown açılıyor: {dropdown_input_id}")
            print(f"[INFO] Aranacak değer: '{deger}'")

            # Input elementini bul
            input_elem = frame.locator(f'input#{dropdown_input_id}').first

            if not input_elem.count():
                print(f"[ERROR] Input element bulunamadı: {dropdown_input_id}")
                return False

            # Input'u temizle
            input_elem.fill("")
            time.sleep(0.5)

            # Input'a focus ver
            input_elem.focus()
            time.sleep(0.5)

            # *** ÖNEMLİ: İlk karakteri yaz (bu dropdown'u açık tutacak) ***
            print(f"[INFO] İlk karakter yazılıyor: '{deger[0]}'")
            input_elem.type(deger[0], delay=150)
            time.sleep(1.5)

            # Dropdown listesi bekleniyor
            print("[INFO] Dropdown listesi bekleniyor...")
            try:
                frame.wait_for_selector('div.x-combo-list-item', timeout=6000)
                print("[OK] Dropdown listesi açıldı ve görünüyor")
                time.sleep(1)
            except:
                print("[WARN] Dropdown listesi beklenenden sonra da görünmüyor")
                time.sleep(1)

            # Dropdown listesindeki tüm item'ları al
            liste_items = frame.locator('div.x-combo-list-item').all()
            print(f"[INFO] Toplam {len(liste_items)} item bulundu")

            if len(liste_items) == 0:
                print("[ERROR] Dropdown listesinde hiç item yok!")
                input_elem.press("Escape")
                time.sleep(0.5)
                self._take_screenshot(frame.page, f"dropdown_{dropdown_input_id}_no_items")
                return False

            # Tüm item'ları yazdır (debug için)
            print("[DEBUG] Dropdown içeriği:")
            for idx, item in enumerate(liste_items):
                item_text = item.inner_text().strip()
                print(f"  [{idx}] '{item_text}'")

            seçildi = False

            # 1. Tam eşleşme ara
            print(f"\n[INFO] Tam eşleşme aranıyor: '{deger}'")
            for idx, item in enumerate(liste_items):
                item_text = item.inner_text().strip()

                if item_text == deger or item_text.upper() == deger.upper():
                    print(f"[OK] TAM EŞLEŞME BULUNDU: '{item_text}'")
                    # Scroll et
                    frame.evaluate(f"document.querySelectorAll('div.x-combo-list-item')[{idx}].scrollIntoView(true)")
                    time.sleep(0.3)
                    # Tıkla
                    item.click()
                    time.sleep(2)
                    seçildi = True
                    break
                
            # 2. Eğer tam eşleşme yoksa, başında aynı olan ara
            if not seçildi:
                print(f"\n[INFO] Başında aynı olan aranıyor...")
                for idx, item in enumerate(liste_items):
                    item_text = item.inner_text().strip()

                    if item_text.upper().startswith(deger.upper()[:3]):
                        print(f"[OK] KISMI EŞLEŞME BULUNDU: '{item_text}'")
                        frame.evaluate(f"document.querySelectorAll('div.x-combo-list-item')[{idx}].scrollIntoView(true)")
                        time.sleep(0.3)
                        item.click()
                        time.sleep(2)
                        seçildi = True
                        break
                    
            # 3. Eğer hala yoksa, contains arama yap
            if not seçildi:
                print(f"\n[INFO] İçinde olan aranıyor...")
                for idx, item in enumerate(liste_items):
                    item_text = item.inner_text().strip()

                    if deger.upper() in item_text.upper():
                        print(f"[OK] İÇİNDE ARAMA İLE BULUNDU: '{item_text}'")
                        frame.evaluate(f"document.querySelectorAll('div.x-combo-list-item')[{idx}].scrollIntoView(true)")
                        time.sleep(0.3)
                        item.click()
                        time.sleep(2)
                        seçildi = True
                        break
                    
            if seçildi:
                print(f"[SUCCESS] Değer seçildi: {deger}")

                # Seçim sonrası kontrol
                time.sleep(1)
                input_value = input_elem.input_value()
                print(f"[INFO] Input value: '{input_value}'")

                return True
            else:
                print(f"[ERROR] '{deger}' değeri bulunamadı!")
                print(f"[INFO] Mevcut değerler:")
                for idx, item in enumerate(liste_items):
                    print(f"  - {item.inner_text().strip()}")

                # Dropdown'u kapat
                input_elem.press("Escape")
                time.sleep(0.5)

                self._take_screenshot(frame.page, f"dropdown_{dropdown_input_id}_not_found")
                return False

        except Exception as e:
            print(f"[ERROR] Dropdown seçim hatası: {e}")
            import traceback
            traceback.print_exc()
            try:
                self._take_screenshot(frame.page, f"dropdown_{dropdown_input_id}_error")
            except:
                pass
            return False

    def seyahat_saglik_sigortasi_islemleri(self, page, seyahat_args=None):
        """
        Seyahat sağlık sigortası işlemlerini gerçekleştir

        Args:
            page: Playwright page object
            seyahat_args: Seyahat sigortası argümanları (dict)
                - dogum_tarihi: Doğum tarihi (GG.AA.YYYY) bu formatta olmalıdır
                - tc_no: TC Kimlik No veya Pasaport numarası
                - teminat_bedeli: (30.000 EUR) veya (50.000 EUR) seçilmeli
                - police_suresi: ("8 Gün,15 Gün,1 Ay,2 Ay,3 Ay,6 Ay veya 1 Yıl ") seçilmelidir format bu şekilde olmalıdır.
                - cografi_sinirlar: ("Tüm Dünya (Türkiye Hariç),Tüm Avrupa Ülkeleri (Schengen Ülkeleri Dahil),Schengen Ülkeleri") seçilmelidir format bu şekilde olmalıdır.
        """
        print("\n" + "="*60)
        print("SEYAHAT SAĞLIK SİGORTASI İŞLEMLERİ BAŞLATILIYOR")
        print("="*60)
        
        # Argümanları dict'ten al
        dogum_tarihi = seyahat_args.get('dogum_tarihi') if seyahat_args else None
        tc_no = seyahat_args.get('tc_no') if seyahat_args else None
        teminat_bedeli = seyahat_args.get('teminat_bedeli') if seyahat_args else None
        police_suresi = seyahat_args.get('police_suresi') if seyahat_args else None
        cografi_sinirlar = seyahat_args.get('cografi_sinirlar') if seyahat_args else None
        
        print(f"[INFO] TC No / Pasaport No: {tc_no}")
        print(f"[INFO] Doğum Tarihi: {dogum_tarihi}")
        print(f"[INFO] Teminat Bedeli: {teminat_bedeli}")
        print(f"[INFO] Poliçe Süresi: {police_suresi}")
        print(f"[INFO] Coğrafi Sınırlar: {cografi_sinirlar}")

        try:
            # 1. ADIM: "Teklif/Poliçe" menüsüne tıkla (iframe içinde)
            print("\n--- 1. ADIM: Teklif/Poliçe menüsüne tıklanıyor ---")
            teklif_police_selectors = [
                'a.x-tree-node-anchor:has-text("Teklif/Poliçe")',
                'a:has-text("Teklif/Poliçe")',
                'span:has-text("Teklif/Poliçe")'
            ]

            teklif_police_link = self._first_visible(page, teklif_police_selectors)
            if teklif_police_link:
                teklif_police_link.click()
                print("[OK] Teklif/Poliçe menüsüne tıklandı")
                time.sleep(5)
            else:
                print("[ERROR] Teklif/Poliçe menüsü bulunamadı")
                self._take_screenshot(page, "seyahat_teklif_police_not_found")
                return False

            # 2. ADIM: "Sağlık" menüsüne tıkla
            print("\n--- 2. ADIM: Sağlık menüsüne tıklanıyor ---")
            saglik_selectors = [
                'a.x-tree-node-anchor:has-text("Sağlık")',
                'a:has-text("Sağlık")',
                'span:has-text("Sağlık")'
            ]

            saglik_link = self._first_visible(page, saglik_selectors)
            if saglik_link:
                saglik_link.click()
                print("[OK] Sağlık menüsüne tıklandı")
                time.sleep(5)
            else:
                print("[ERROR] Sağlık menüsü bulunamadı")
                self._take_screenshot(page, "seyahat_saglik_menu_not_found")
                return False
                
            # 3. ADIM: "Seyahat Sağlık" ürün linkine tıkla (Örn: "340 SEYAHAT SAĞLIK")
            print("\n--- 3. ADIM: Seyahat Sağlık ürün linkine tıklanıyor ---")
            seyahat_urun_selectors = [
                'a[href="/NonLife/Policy/SavePolicy.aspx?APP_MP=298"]',
                'a:has-text("298 SEYAHAT SAĞLIK")',
                '//a[contains(@href, "APP_MP=298")]'

            ]

            seyahat_urun_link = self._first_visible(page, seyahat_urun_selectors)
            if seyahat_urun_link:
                seyahat_urun_link.click()
                print("[OK] Seyahat Sağlık ürün linkine tıklandı")

                # 4. ADIM: 10 saniye bekle (yeni iframe içeriği yüklenmesi için)
                print("[INFO] Sayfanın yüklenmesi için 10 saniye bekleniyor...")
                time.sleep(10)

                # Yeni iframe içeriği yüklendi, tekrar frame alalım
                frame = self._iframe_gecis(page)
                if not frame:
                    return False

                print(f"[OK] Seyahat sağlık sigortası form sayfasına yönlendirildi")

            else:
                print("[ERROR] Seyahat Sağlık ürün linki bulunamadı")
                self._take_screenshot(page, "seyahat_urun_not_found")
                return False

            print("\n--- 5. ADIM: Dropdown Seçimleri (Teminat, Süre, Coğrafi) ---")
            
            # Teminat Bedeli
            if teminat_bedeli:
                print(f"\n>>> Teminat Bedeli: {teminat_bedeli}")
                success = self._secim_dropdown_ac_ve_sec_fixed(
                    frame,
                    'cphCFB_policyInputStatistics_ctl00',
                    teminat_bedeli
                )
                if success:
                    print("[OK] Teminat Bedeli seçildi")
                    time.sleep(2)
                else:
                    print("[WARN] Teminat Bedeli seçilemedi, devam ediliyor...")
                    time.sleep(2)
            
            # Poliçe Süresi
            if police_suresi:
                print(f"\n>>> Poliçe Süresi: {police_suresi}")
                success = self._secim_dropdown_ac_ve_sec_fixed(
                    frame,
                    'cphCFB_policyInputStatistics_ctl02',
                    police_suresi
                )
                if success:
                    print("[OK] Poliçe Süresi seçildi")
                    time.sleep(2)
                else:
                    print("[WARN] Poliçe Süresi seçilemedi, devam ediliyor...")
                    time.sleep(2)
            
            # Coğrafi Sınırlar (SON)
            if cografi_sinirlar:
                print(f"\n>>> Coğrafi Sınırlar: {cografi_sinirlar}")
                success = self._secim_dropdown_ac_ve_sec_fixed(
                    frame,
                    'cphCFB_policyInputStatistics_ctl04',
                    cografi_sinirlar
                )
                if success:
                    print("[OK] Coğrafi Sınırlar seçildi")
                    time.sleep(2)
                else:
                    print("[WARN] Coğrafi Sınırlar seçilemedi, devam ediliyor...")
                    time.sleep(2)
            
            print("\n[OK] Tüm dropdown seçimleri tamamlandı")
            time.sleep(3)
            # --- YENİ MÜŞTERİ ARAMA SEKANSI (Sizin isteğiniz) ---
            print("\n--- 5. ADIM: Müşteri Arama Başlatılıyor ---")

            # 5.1: Arama Trigger'ına tıkla
            print("[INFO] Müşteri arama trigger'ına tıklanıyor...")
            # Sizin HTML'inizdeki ID (ext-gen260) dinamik olabilir, class'ı kullanmak daha güvenli
            arama_trigger_selectors = [
                '#ext-gen260' 
            ]
            arama_trigger_btn = self._first_visible(frame, arama_trigger_selectors)
            
            if arama_trigger_btn:
                arama_trigger_btn.click()
                print("[OK] Arama trigger'ına tıklandı.")
                print("[INFO] Arama penceresinin açılması için 5 saniye bekleniyor...")
                time.sleep(7)
            else:
                print("[ERROR] Müşteri arama trigger'ı bulunamadı")
                self._take_screenshot(page, "seyahat_arama_trigger_not_found")
                return False

            # 5.2: TC No gir (Açılan pencerede/bölümde)
            print("[INFO] TC No (arama) yazılıyor...")
            tc_arama_selectors = [
                'input#cphCFB_policyInputHeader_customerSearch_txtTCK', # Sizin verdiğiniz ID
                'input[name="cphCFB_policyInputHeader_customerSearch_txtTCK"]'
            ]
            tc_arama_input = self._first_visible(frame, tc_arama_selectors)
            if tc_arama_input:
                if tc_no:
                    tc_arama_input.fill(tc_no)
                    print(f"[OK] TC No (arama) yazıldı: {tc_no}")
                else:
                    print("[WARN] TC No bilgisi verilmedi.")
            else:
                print("[ERROR] TC No (arama) inputu bulunamadı")
                self._take_screenshot(page, "seyahat_tc_arama_input_not_found")
                return False

            # 5.3: Doğum Tarihi gir (Açılan pencerede/bölümde)
            print("[INFO] Doğum Tarihi (arama) yazılıyor...")
            tarih_arama_selectors = [
                'input#cphCFB_policyInputHeader_customerSearch_txtBirthDate', # Sizin verdiğiniz ID
                'input[name="cphCFB_policyInputHeader_customerSearch_txtBirthDate"]'
            ]
            tarih_arama_input = self._first_visible(frame, tarih_arama_selectors)
            if tarih_arama_input:
                if dogum_tarihi:
                    tarih_arama_input.fill(dogum_tarihi)
                    print(f"[OK] Doğum Tarihi (arama) yazıldı: {dogum_tarihi}")
                else:
                    print("[WARN] Doğum Tarihi bilgisi verilmedi.")
            else:
                print("[ERROR] Doğum Tarihi (arama) inputu bulunamadı")
                self._take_screenshot(page, "seyahat_tarih_arama_input_not_found")
                return False

            print("\n--- 5.4 ADIM: Doğum Tarihi Sonrası ENTER'a Basılıyor ---")
            
            if tarih_arama_input:
                # ENTER'a bas (form submit veya arama tetiklenir)
                tarih_arama_input.press("Enter")
                print("[OK] ENTER'a basıldı")
                print("[INFO] Arama sonucu bekleniyor... (5 saniye)")
                time.sleep(10)
            else:
                print("[ERROR] Doğum tarihi inputu bulunamadı, Ara butonu bulunmaya çalışılıyor...")
                
                # Fallback: Ara butonunu bul
                ara_btn_selectors = [
                    'button.x-btn-text.icon-find',
                    'button:has-text("Ara")',
                    '#ext-gen3169',
                    '#ext-gen3168'
                ]
                ara_btn = self._first_visible(frame, ara_btn_selectors)
                if ara_btn:
                    ara_btn.click()
                    print("[OK] Ara butonuna tıklandı (fallback)")
                    time.sleep(5)
                else:
                    print("[WARN] Ara butonu da bulunamadı, devam ediliyor...")
                    time.sleep(3)
            # --- YENİ SEKANSI BURADA BİTİR ---

            print("\n--- 5.5 ADIM: Arama Sonucunda Müşteriye Çift Tıklanıyor ---")
            
            # Grid'deki satır'ı bul
            grid_row_selectors = [
                'div.x-grid3-row.x-grid3-row-first.x-grid3-row-last',
                'div.x-grid3-row',
                'table.x-grid3-row-table'
            ]
            
            grid_row = self._first_visible(frame, grid_row_selectors)
            if grid_row:
                print("[OK] Grid satırı bulundu")
                print("[INFO] Müşteriye çift tıklanıyor...")
                grid_row.dblclick()
                print("[OK] Çift tıklama yapıldı")
                time.sleep(10)
            else:
                print("[ERROR] Grid satırı bulunamadı")
                self._take_screenshot(frame.page, "seyahat_grid_row_not_found")
                return False

            print("\n--- 5.6 ADIM: Sonraki Adım Butonuna Tıklanıyor ---")
            sonraki_adim_selectors = [
                'button.x-btn-text.icon-resultsetnext',
                'button#ext-gen64',
                'button:has-text("Sonraki Adım")',
                'button[type="button"].icon-resultsetnext'
            ]
            
            sonraki_adim_btn = self._first_visible(frame, sonraki_adim_selectors)
            if sonraki_adim_btn:
                sonraki_adim_btn.click()
                print("[OK] Sonraki Adım butonuna tıklandı")
                print("[INFO] Sonraki sayfanın yüklenmesi için 10 saniye bekleniyor...")
                time.sleep(15)
            else:
                print("[ERROR] Sonraki Adım butonu bulunamadı")
                self._take_screenshot(frame.page, "seyahat_sonraki_adim_button_not_found")
                return False
            print("\n--- 5.7 ADIM: Uyarı Dialog Kontrolü ---")
            
            try:
                # Dialog'un açılmasını bekle
                frame.wait_for_selector('div.x-window-dlg', timeout=5000)
                print("[OK] Uyarı dialog açıldı")
                time.sleep(1)
            except:
                print("[WARN] Uyarı dialog beklenen zamanda açılmadı, yine de devam ediliyor...")
            
            # "Evet" butonunu bul ve tıkla
            evet_btn_selectors = [
                'button.x-btn-text:has-text("Evet")',
                'button#ext-gen3498',
                'button:has-text("Evet")'
            ]
            
            evet_btn = self._first_visible(frame, evet_btn_selectors)
            if evet_btn:
                print("[OK] Uyarı dialog'da 'Evet' butonu bulundu")
                evet_btn.click()
                print("[OK] 'Evet' butonuna tıklandı")
                print("[INFO] 10 saniye bekleniyor...")
                time.sleep(10)
            else:
                print("[WARN] 'Evet' butonu bulunamadı")
                self._take_screenshot(frame.page, "seyahat_uyari_evet_not_found")
                time.sleep(10)

            # 9. ADIM: Tekrar "Sonraki Adım" butonuna tıkla
            print("\n--- 9. ADIM: Tekrar Sonraki Adım Butonuna Tıklanıyor ---")
            sonraki_adim_btn2 = self._first_visible(frame, sonraki_adim_selectors)
            if sonraki_adim_btn2:
                sonraki_adim_btn2.click()
                print("[OK] Sonraki Adım butonuna tıklandı")
                time.sleep(12)
            else:
                print("[ERROR] Sonraki Adım butonu bulunamadı")
                self._take_screenshot(page, "seyahat_sonraki_adim_button_not_found_2")
                return False

            print("\n--- 5.8 ADIM: Fiyat Tablosu Verilerini Alma ---")
            time.sleep(2)
            
            fiyat_verileri = {}
            
            try:
                # Grid satırlarını bul
                grid_rows = frame.locator('div.x-grid3-row').all()
                print(f"[INFO] {len(grid_rows)} fiyat satırı bulundu")
                
                for satir_idx, satir in enumerate(grid_rows):
                    try:
                        # Hücreler
                        hucreler = satir.locator('td.x-grid3-cell').all()
                        
                        if len(hucreler) >= 6:
                            # Hücre içindeki text'i al
                            odeme_plani = hucreler[1].inner_text().strip()  # Peşin, Taksit vs
                            tutar = hucreler[2].inner_text().strip()        # 30.83
                            vergi = hucreler[3].inner_text().strip()        # 0.00
                            toplam = hucreler[4].inner_text().strip()       # 30.83
                            odeme = hucreler[5].inner_text().strip()        # 15.42
                            
                            fiyat_verileri[odeme_plani] = {
                                'tutar': tutar,
                                'vergi': vergi,
                                'toplam': toplam,
                                'odeme': odeme
                            }
                            
                            print(f"[INFO] {odeme_plani}:")
                            print(f"       - Tutar: {tutar}")
                            print(f"       - Vergi: {vergi}")
                            print(f"       - Toplam: {toplam}")
                            print(f"       - Ödeme: {odeme}")
                    except Exception as e:
                        print(f"[WARN] Satır {satir_idx} işlenirken hata: {e}")
                        continue
                
                if fiyat_verileri:
                    print(f"\n[OK] {len(fiyat_verileri)} fiyat seçeneği bulundu")
                else:
                    print("[WARN] Fiyat tablosu verisi alınamadı")
                    
            except Exception as e:
                print(f"[ERROR] Fiyat tablosu okuma hatası: {e}")
                import traceback
                traceback.print_exc()
            
            time.sleep(2)

            print("\n[SUCCESS] Seyahat sağlık sigortası formu başarıyla tamamlandı!")
            return True

        except Exception as e:
            print(f"[ERROR] Seyahat sağlık sigortası işlemlerinde hata: {e}")
            import traceback
            traceback.print_exc()
            self._take_screenshot(page, "seyahat_sigortasi_error")
            return False

    def run(self, trafik_args=None, kasko_args=None, seyahat_args=None):
        """
        Ana çalıştırma fonksiyonu
        
        Args:
            trafik_args: Trafik sigortası için argümanlar (dict)
            kasko_args: Kasko sigortası için argümanlar (dict)
            seyahat_args: Seyahat sağlık sigortası için argümanlar (dict)
        """
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=self.headless)
            context = browser.new_context(viewport={"width": 1366, "height": 900})
            page = context.new_page()

            try:
                page.goto(self.login_url, wait_until="domcontentloaded", timeout=self.timeout)
                page.bring_to_front()
                print("[OK] Login sayfası açıldı:", self.login_url)
            except PWTimeoutError:
                browser.close()
                raise RuntimeError("Sayfaya bağlanırken zaman aşımı.")
            
            # Kullanıcı adı
            u = self._first_visible(page, self.USER_CANDS)
            if not u: 
                browser.close(); raise RuntimeError("Kullanıcı adı inputu bulunamadı.")
            u.fill(self.username, timeout=self.timeout)
            print("[OK] Kullanıcı adı yazıldı.")

            # Şifre
            p = self._first_visible(page, self.PASS_CANDS)
            if not p:
                browser.close(); raise RuntimeError("Şifre inputu bulunamadı.")
            p.fill(self.password, timeout=self.timeout)
            print("[OK] Şifre yazıldı.")

            # Giriş
            btn = self._first_visible(page, self.LOGIN_BTN_CANDS)
            if not btn:
                browser.close(); raise RuntimeError("Giriş butonu bulunamadı.")
            btn.click(timeout=8000)
            print("[OK] Giriş butonuna tıklandı.")

            # Buradan sonrası MANUEL: TOTP kodunu ve Doğrula'yı sen gir/klikle.
            time.sleep(5)
            print("[OK] Manuel TOTP tamamlandıysa oturum açılmış olmalı. Mevcut URL:", page.url)

            # --- İnteraktif Menü ---
            while True:
                print("\n" + "="*60)
                print("Lütfen yapmak istediğiniz işlemi seçin:")
                print("  1: Trafik Sigortası Teklifi")
                print("  2: Kasko Sigortası Teklifi")
                print("  3: Seyahat Sağlık Sigortası Teklifi")
                print("  0: Çıkış")
                print("="*60)
                
                secim = input("Seçiminiz (1, 2, 3 veya 0): ").strip()

                if secim == '1':
                    if trafik_args:
                        print("\n[INFO] Trafik Sigortası işlemi başlatılıyor...")
                        fiyat_sonucu = self.trafik_sigortasi_islemleri(page, trafik_args)
                        
                        if fiyat_sonucu and isinstance(fiyat_sonucu, dict):
                            print("\n" + "="*60)
                            print("TRAFİK SİGORTASI - FİYAT SONUÇLARI")
                            print("="*60)
                            for odeme_plani, fiyatlar in fiyat_sonucu.items():
                                if odeme_plani.strip():  # Boş anahtarları atla
                                    print(f"\n{odeme_plani}:")
                                    print(f"  Tutar: {fiyatlar.get('tutar', 'N/A')}")
                                    print(f"  Vergi: {fiyatlar.get('vergi', 'N/A')}")
                                    print(f"  Toplam: {fiyatlar.get('toplam', 'N/A')}")
                                    print(f"  Ödeme: {fiyatlar.get('odeme', 'N/A')}")
                            print("="*60)



                elif secim == '2':
                    if kasko_args:
                        print("\n[INFO] Kasko Sigortası işlemi başlatılıyor...")
                        fiyat_sonucu = self.kasko_sigortasi_islemleri(page, kasko_args)
                        
                        if fiyat_sonucu and isinstance(fiyat_sonucu, dict):
                            print("\n" + "="*60)
                            print("KASKO SİGORTASI - FİYAT SONUÇLARI")
                            print("="*60)
                            for odeme_plani, fiyatlar in fiyat_sonucu.items():
                                if odeme_plani.strip():  # Boş anahtarları atla
                                    print(f"\n{odeme_plani}:")
                                    print(f"  Tutar: {fiyatlar.get('tutar', 'N/A')}")
                                    print(f"  Vergi: {fiyatlar.get('vergi', 'N/A')}")
                                    print(f"  Toplam: {fiyatlar.get('toplam', 'N/A')}")
                                    print(f"  Ödeme: {fiyatlar.get('odeme', 'N/A')}")
                            print("="*60)



                elif secim == '3':
                    if seyahat_args:
                        print("\n[INFO] Seyahat Sağlık Sigortası işlemi başlatılıyor...")
                        fiyat_sonucu = self.seyahat_saglik_sigortasi_islemleri(page, seyahat_args)
                        
                        if fiyat_sonucu and isinstance(fiyat_sonucu, dict):
                            print("\n" + "="*60)
                            print("SEYAHAT SAĞLIK SİGORTASI - FİYAT SONUÇLARI")
                            print("="*60)
                            for odeme_plani, fiyatlar in fiyat_sonucu.items():
                                if odeme_plani.strip():  # Boş olanları atla
                                    print(f"\n{odeme_plani}:")
                                    print(f"  Tutar: {fiyatlar.get('tutar', 'N/A')} EUR")
                                    print(f"  Vergi: {fiyatlar.get('vergi', 'N/A')} EUR")
                                    print(f"  Toplam: {fiyatlar.get('toplam', 'N/A')} EUR")
                                    print(f"  Ödeme: {fiyatlar.get('odeme', 'N/A')} EUR")
                            print("="*60)
                        else:
                            print("[WARN] Seyahat sağlık sigortası işleminde hata oluştu")
                        
                        print("\n[INFO] Browser kapatılıyor...")
                        browser.close()
                        print("[OK] Browser kapatıldı. Program sonlandırılıyor...")
                        break
                elif secim == '0':
                    print("\n[INFO] Çıkış yapılıyor...")
                    break
                
                else:
                    print("\n[ERROR] Geçersiz seçim. Lütfen 1, 2, 3 veya 0 girin.")
                
                time.sleep(2)

            # --- Döngü bitti ---
            print("\n" + "="*60)
            print("TÜM İŞLEMLER TAMAMLANDI.")
            input("Tarayıcıyı kapatmak için Enter'a bas…")
            browser.close()


if __name__ == "__main__":
    trafik_args = {
        'plaka': '06HT203',
        'tckn': '32083591236',
        'tescil': 'ER993016',
        'kullanim_tarzi': 'HUSUSİ OTO'
    }

    kasko_args = {
        'plaka': '06HT203',
        'tckn': '32083591236',
        'tescil': 'ER993016',
        'kullanim_tarzi': 'HUSUSİ OTO'
    }
    
    seyahat_args = {
        'dogum_tarihi': '01.01.2002',
        'tc_no': '48274206902',
        'teminat_bedeli': '30.000 EUR',
        'police_suresi': '1 Ay',
        'cografi_sinirlar': 'Tüm Dünya (Türkiye Hariç)',
    }

    # --- Scraper'ı Başlat ---
    SekerScraper().run(
        trafik_args=trafik_args, 
        kasko_args=kasko_args, 
        seyahat_args=seyahat_args
    )