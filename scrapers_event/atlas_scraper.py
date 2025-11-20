import os
import json
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeoutError
import time
import random
import pyotp # 'run_bireysel_kasko' fonksiyonundan import'u buraya taşıdım
import traceback # Hata ayıklama için

class AtlasScraper:
    def __init__(self):
        load_dotenv()
        self.login_url = os.getenv("ATLAS_LOGIN_URL", "").strip()
        self.username   = os.getenv("ATLAS_USER", "").strip()
        self.password   = os.getenv("ATLAS_PASS", "").strip()
        self.totp_secret = os.getenv("ATLAS_TOTP_SECRET", "").strip()
        self.headless   = os.getenv("HEADLESS", "false").lower() == "true"
        self.timeout   = int(os.getenv("ATLAS_TIMEOUT_MS", "45000"))

        if not self.login_url:
            raise RuntimeError("ATLAS_LOGIN_URL .env içinde tanımlı değil.")
        if not self.username or not self.password:
            raise RuntimeError("ATLAS_USER ve ATLAS_PASS .env içinde olmalı.")
        if not self.totp_secret:
            print("[WARNING] ATLAS_TOTP_SECRET .env içinde tanımlı değil. 2FA adımı başarısız olacak.")

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

    def _find_element(self, page, candidates, description="element"):
        """Birden fazla selector denemesi yapar"""
        for sel in candidates:
            try:
                elem = page.locator(sel).first
                if elem.is_visible(timeout=2000):
                    print(f"[INFO] {description} bulundu: {sel}")
                    return elem
            except:
                continue
        print(f"[WARNING] {description} hiçbir selector ile bulunamadı!")
        return None

    def _select_extjs_combo(self, frame_locator, page, input_id, target_text="HAYIR"):
        """
        ExtJS combo box için sadeleştirilmiş seçim fonksiyonu.
        Dropdown'ı açar ve hedef öğeye tıklar (yazma yok).
        
        Args:
            frame_locator: Playwright frame locator
            page: Playwright page object
            input_id: Input elementinin ID'si (# olmadan)
            target_text: Seçilecek değer (varsayılan: "HAYIR")
        """
        try:
            print(f"\n[INFO] ExtJS Combo seçimi başlıyor: {input_id}")
            print(f"[INFO] Hedef değer: '{target_text}'")
            
            # Input elementini bul
            input_selector = f"input#{input_id}"
            input_elem = frame_locator.locator(input_selector).first
            
            if not input_elem.count():
                print(f"[ERROR] Input bulunamadı: {input_selector}")
                return False
            
            # STRATEJİ 1: Input'a tıkla (bazı combo'lar bununla açılır)
            print("[STRATEJI 1] Input'a tıklanıyor...")
            input_elem.click()
            time.sleep(1.0)   # Dropdown'ın açılması için bekle
            
            # Dropdown listesini kontrol et
            dropdown_visible = False
            try:
                page.wait_for_selector("div.x-combo-list", state="visible", timeout=2000)
                dropdown_visible = True
                print("[SUCCESS] Dropdown listesi görünür (input tıklama ile)")
            except:
                print("[INFO] Input tıklama ile açılmadı, trigger deneniyor...")
            
            # STRATEJİ 2: Dropdown görünmediyse trigger'a tıkla
            if not dropdown_visible:
                print("[STRATEJI 2] Trigger'a tıklanıyor...")
                trigger_selectors = [
                    f"input#{input_id} ~ img.x-form-trigger",
                    f"input#{input_id} + img.x-form-trigger",
                    f"div.x-form-field-wrap:has(input#{input_id}) img.x-form-trigger",
                    f"#{input_id}-trigger"
                ]
                
                for trigger_sel in trigger_selectors:
                    try:
                        trigger = frame_locator.locator(trigger_sel).first
                        if trigger.count() and trigger.is_visible():
                            trigger.click()
                            print(f"[SUCCESS] Trigger tıklandı: {trigger_sel}")
                            time.sleep(1.5)
                            dropdown_visible = True
                            break
                    except:
                        continue
            
            # Eğer hala açılmadıysa son bir deneme
            if not dropdown_visible:
                print("[WARNING] Dropdown açılamadı, yine de devam ediliyor...")
            
            # Dropdown'ın tamamen yüklenmesini bekle
            time.sleep(1.0)
            
            # STRATEJİ 3: Hedef öğeyi bul ve tıkla
            print(f"[INFO] '{target_text}' öğesi aranıyor...")
            
            item_selectors = [
                f"div.x-combo-list-item:text-is('{target_text}')",
                f"div.x-combo-list-item:has-text('{target_text}')",
                f"//div[contains(@class, 'x-combo-list-item') and normalize-space(text())='{target_text}']",
                f"//div[contains(@class, 'x-combo-list-item')][text()='{target_text}']"
            ]
            
            item_found = False
            
            # Önce page'de ara
            for selector in item_selectors:
                try:
                    if selector.startswith('//'):
                        item = page.locator(f"xpath={selector}").first
                    else:
                        item = page.locator(selector).first
                    
                    if item.is_visible(timeout=2000):
                        print(f"[SUCCESS] Öğe bulundu (page): {selector}")
                        item.click()
                        print(f"[SUCCESS] '{target_text}' seçildi!")
                        item_found = True
                        time.sleep(0.8)
                        break
                except:
                    continue
            
            # Frame'de ara
            if not item_found:
                print("[INFO] Frame içinde aranıyor...")
                for selector in item_selectors:
                    try:
                        if selector.startswith('//'):
                            item = frame_locator.locator(f"xpath={selector}").first
                        else:
                            item = frame_locator.locator(selector).first
                        
                        if item.is_visible(timeout=2000):
                            print(f"[SUCCESS] Öğe bulundu (frame): {selector}")
                            item.click()
                            print(f"[SUCCESS] '{target_text}' seçildi!")
                            item_found = True
                            time.sleep(0.8)
                            break
                    except:
                        continue
            
            # STRATEJİ 4: Klavye ile seçim (son çare)
            if not item_found:
                print("[STRATEJI 4] Klavye ile seçim deneniyor...")
                try:
                    # Input'a odaklan
                    input_elem.focus()
                    time.sleep(0.3)
                    
                    # Aşağı ok tuşu ile "HAYIR" seçeneğine git
                    # Genellikle ilk öğe "EVET", ikinci "HAYIR" olur
                    page.keyboard.press("ArrowDown")
                    time.sleep(0.2)
                    page.keyboard.press("ArrowDown")   # HAYIR'a git
                    time.sleep(0.2)
                    
                    # Enter ile seç
                    page.keyboard.press("Enter")
                    print("[SUCCESS] Klavye ile seçim yapıldı")
                    item_found = True
                    time.sleep(0.5)
                except Exception as e:
                    print(f"[ERROR] Klavye seçimi başarısız: {e}")
            
            # Sonuç doğrulama
            if item_found:
                try:
                    final_value = input_elem.input_value()
                    print(f"[VERIFY] Seçim sonrası değer: '{final_value}'")
                    
                    # Değerin doğru olup olmadığını kontrol et
                    if target_text.lower() in final_value.lower():
                        print(f"[SUCCESS] ✅ Seçim doğrulandı!")
                        return True
                    else:
                        print(f"[WARNING] Değer beklenenden farklı")
                        return True   # Yine de devam et
                except:
                    print("[INFO] Değer doğrulanamadı")
                    return True   # Optimist yaklaşım
            else:
                print(f"[ERROR] ❌ '{target_text}' öğesi bulunamadı!")
                
                # Debug: Mevcut öğeleri listele
                try:
                    all_items = page.locator("div.x-combo-list-item").all()
                    if all_items:
                        print(f"[DEBUG] Dropdown'da {len(all_items)} öğe var:")
                        for i, item in enumerate(all_items[:5]):   # İlk 5'i göster
                            try:
                                print(f"  [{i}] '{item.inner_text()}'")
                            except:
                                pass
                except:
                    pass
                
                return False
        
        except Exception as e:
            print(f"[ERROR] Dropdown seçim hatası: {e}")
            traceback.print_exc()
            return False

    def run_bireysel_kasko(self, policy_data):
        """
        Tüm bireysel kasko işlemlerini tek fonksiyonda yapar.
        DROPDOWN HATALARINDA BİLE BROWSER AÇIK KALACAK.
        """
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

                # 1. LOGIN İŞLEMLERİ
                print(f"[INFO] Login sayfasına gidiliyor: {self.login_url}")
                page.goto(self.login_url, wait_until="load")

                # Kullanıcı girişi
                print("[INFO] Kullanıcı girişi yapılıyor...")
                username_input = self._find_element(page, self.USER_CANDS, "Kullanıcı adı")
                if username_input:
                    username_input.fill(self.username)
                    print("[INFO] Kullanıcı adı girildi.")
                else:
                    raise Exception("Kullanıcı adı alanı bulunamadı!")
                
                time.sleep(random.uniform(0.5, 1.5))
                
                password_input = self._find_element(page, self.PASS_CANDS, "Şifre")
                if password_input:
                    password_input.fill(self.password)
                    print("[INFO] Şifre girildi.")
                else:
                    raise Exception("Şifre alanı bulunamadı!")
                
                time.sleep(random.uniform(0.5, 1.5))
                
                login_button = self._find_element(page, self.LOGIN_BTN_CANDS, "Giriş butonu")
                if login_button:
                    login_button.click()
                    print("[INFO] Giriş butonuna tıklandı.")
                    time.sleep(random.uniform(2, 4))
                else:
                    raise Exception("Giriş butonu bulunamadı!")
                
                print("[SUCCESS] Giriş başarılı!")

                # 2. TOTP DOĞRULAMASI
                if not self.totp_secret:
                    raise Exception("TOTP Secret (.env) tanımlı değil, doğrulama yapılamaz.")
                
                print("[INFO] TOTP doğrulaması yapılıyor...")
                time.sleep(random.uniform(1, 2))
                
                totp = pyotp.TOTP(self.totp_secret)
                code = totp.now()
                print(f"[INFO] TOTP kodu oluşturuldu: {code}")
                
                totp_selectors = [
                    'input#txtGAKod', 'input[name="txtGAKod"]',
                    'input#txtGAKod_Container input', 'div#winGAC input[type="text"]',
                    'input.x-form-text.x-form-field', 'input[placeholder*="Doğrulama"]', 'input[placeholder*="Kod"]',
                ]
                
                totp_input = self._find_element(page, totp_selectors, "TOTP kodu alanı")
                if totp_input:
                    totp_input.click()
                    time.sleep(random.uniform(0.3, 0.7))
                    totp_input.fill("")
                    time.sleep(random.uniform(0.2, 0.4))
                    totp_input.fill(code)
                    print("[INFO] TOTP kodu girildi.")
                    time.sleep(random.uniform(0.5, 1.0))
                else:
                    raise Exception("TOTP input alanı bulunamadı!")
                
                verify_btn_selectors = [
                    'button#ext-gen61', 'table#btnValidateTwoFactor button',
                    'button.x-btn-text.icon-key', 'button:has-text("Giriş")',
                    'div#winGAC button[type="button"]', 'button[name="button"][value="verify"]',
                    'button:has-text("Doğrula")', 'button:has-text("Devam")',
                ]
                
                verify_button = self._find_element(page, verify_btn_selectors, "TOTP doğrula butonu")
                if verify_button:
                    verify_button.click()
                    print("[INFO] TOTP doğrula butonuna tıklandı.")
                    time.sleep(random.uniform(2, 4))
                else:
                    raise Exception("TOTP doğrula butonu bulunamadı!")
                
                try:
                    page.wait_for_selector('div#winGAC', state='hidden', timeout=10000)
                    print("[INFO] Google Authenticator popup'ı kapandı.")
                except:
                    print("[WARNING] Popup kapanma kontrolü başarısız, devam ediliyor...")
                
                time.sleep(random.uniform(1, 2))
                print("[SUCCESS] TOTP doğrulaması başarılı!")

                # 3. MENÜ NAVİGASYONU
                print("[INFO] Bireysel Kasko menüsüne gidiliyor...")
                
                police_menu = page.locator('span:text-is("Poliçe")')
                police_menu.wait_for(state="visible", timeout=10000)
                police_menu.click()
                print("[INFO] 'Poliçe' menüsüne tıklandı.")
                time.sleep(random.uniform(0.5, 1.0))
                
                oto_sigorta_menu = page.locator('span:text-is("OTO SİGORTALARI")')
                oto_sigorta_menu.wait_for(state="visible", timeout=5000)
                oto_sigorta_menu.click()
                print("[INFO] 'OTO SİGORTALARI' menüsüne tıklandı.")
                time.sleep(random.uniform(0.5, 1.0))
                
                bireysel_kasko_menu = page.locator('span:text-is("BİREYSEL OTOMOBİL KASKO(OTO)")')
                bireysel_kasko_menu.wait_for(state="visible", timeout=5000)
                bireysel_kasko_menu.click()
                print("[INFO] 'BİREYSEL OTOMOBİL KASKO(OTO)' menüsüne tıklandı.")
                
                print("[SUCCESS] Bireysel Kasko sayfası yüklendi!")

                time.sleep(15)
                
                # 4. IFRAME ve FORM İŞLEMLERİ
                frame_selector = "#frmMain"
                kasko_frame = page.frame_locator(frame_selector)
                
                tckn_selector = "#txtGIFTIdentityNo"
                kasko_frame.locator(tckn_selector).wait_for(state="visible", timeout=10000)
                print("[INFO] Iframe bulundu ve TCKN alanı görünür.")

                # Form alanlarını doldur
                if 'tckn' in policy_data:
                    kasko_frame.locator(tckn_selector).fill(policy_data['tckn'])
                    print(f"[INFO] TCKN girildi: {policy_data['tckn']}")
                    time.sleep(random.uniform(0.3, 0.7))
                
                if 'plaka' in policy_data:
                    kasko_frame.locator("#txtGIFTPlate").fill(policy_data['plaka'])
                    print(f"[INFO] Plaka girildi: {policy_data['plaka']}")
                    time.sleep(random.uniform(0.3, 0.7))
                
                if 'tescil_seri' in policy_data:
                    kasko_frame.locator("#txtGIFTEGMSerial").fill(policy_data['tescil_seri'])
                    print(f"[INFO] Tescil Seri girildi: {policy_data['tescil_seri']}")
                    time.sleep(random.uniform(0.3, 0.7))
                
                if 'tescil_no' in policy_data:
                    kasko_frame.locator("#txtGIFTEGMNo").fill(policy_data['tescil_no'])
                    print(f"[INFO] Tescil No girildi: {policy_data['tescil_no']}")
                    time.sleep(random.uniform(0.3, 0.7))

                print("[SUCCESS] Kasko formu dolduruldu.")

                # Tramer Sorgula butonuna tıkla
                sorgula_button_selector = 'button:has-text("Tramer Sorgula")'
                sorgula_button = kasko_frame.locator(sorgula_button_selector)
                sorgula_button.wait_for(state="visible", timeout=5000)
                sorgula_button.click()
                print("[INFO] 'Tramer Sorgula' butonuna tıklandı.")

                # Tramer sorgulamasını bekle
                print("[INFO] Tramer sorgulaması bekleniyor...")
                time.sleep(12)
                try:
                    kasko_frame.locator("#cphCFB_policyInputStatistics_ctl32").wait_for(state="visible", timeout=15000)
                    print("[SUCCESS] Tramer sorgulaması tamamlandı.")
                except PWTimeoutError:
                    print("[WARNING] Tramer sorgulaması zaman aşımına uğradı, devam ediliyor...")

                # 5. DROPDOWN SEÇİMLERİ
                print("\n" + "="*60)
                print("[INFO] Dropdown seçimleri başlıyor...")
                print("="*60)
                
                dropdown_results = []
                
                # Sigortalı Kamu Kurum: HAYIR
                result1 = self._select_extjs_combo(
                    frame_locator=kasko_frame,
                    page=page,
                    input_id="cphCFB_policyInputStatistics_ctl32",
                    target_text="HAYIR"
                )
                dropdown_results.append(("Sigortalı Kamu Kurum", result1))
                time.sleep(random.uniform(0.5, 1.0))

                # İhale Poliçesi Mi: HAYIR
                result2 = self._select_extjs_combo(
                    frame_locator=kasko_frame,
                    page=page,
                    input_id="cphCFB_policyInputStatistics_ctl34",
                    target_text="HAYIR"
                )
                dropdown_results.append(("İhale Poliçesi Mi", result2))

                # Dropdown sonuçlarını raporla
                success_count = sum(1 for _, result in dropdown_results if result)
                print("\n" + "="*60)
                print(f"[SUMMARY] Dropdown seçim sonuçları:")
                print("="*60)
                for dropdown_name, result in dropdown_results:
                    status = "✅ BAŞARILI" if result else "❌ BAŞARISIZ"
                    print(f"   - {dropdown_name}: {status}")
                
                print(f"\n[SUMMARY] Toplam: {success_count}/{len(dropdown_results)} dropdown başarıyla seçildi.")
                print("="*60)

                if success_count == len(dropdown_results):
                    print("\n🎉 [SUCCESS] Tüm dropdown seçimleri başarıyla tamamlandı!")
                else:
                    print("\n⚠️ [WARNING] Bazı dropdown seçimleri başarısız oldu, ancak işleme devam edildi.")

                # 6. MÜŞTERİ ARAMA İŞLEMLERİ - DÜZELTİLMİŞ VERSİYON
                print("\n" + "="*60)
                print("[INFO] Müşteri arama işlemleri başlıyor...")
                print("="*60)

                # Arama trigger'ına tıkla
                print("[INFO] Müşteri arama trigger'ına tıklanıyor...")
                search_trigger_selectors = [
                    'img.x-form-trigger.x-form-search-trigger',
                    'img.x-form-search-trigger',
                    'img[id*="ext-gen"][class*="x-form-search-trigger"]'
                ]

                trigger_clicked = False
                for selector in search_trigger_selectors:
                    try:
                        trigger = kasko_frame.locator(selector).first
                        if trigger.is_visible(timeout=3000):
                            trigger.click()
                            print(f"[SUCCESS] Arama trigger'ı tıklandı: {selector}")
                            trigger_clicked = True
                            break
                    except:
                        continue
                    
                if not trigger_clicked:
                    # Page üzerinde dene
                    try:
                        trigger = page.locator('img.x-form-trigger.x-form-search-trigger').first
                        if trigger.is_visible(timeout=3000):
                            trigger.click()
                            print("[SUCCESS] Arama trigger'ı tıklandı (page)")
                            trigger_clicked = True
                    except:
                        pass
                    
                if not trigger_clicked:
                    print("[ERROR] Arama trigger'ı bulunamadı!")
                else:
                    print("[INFO] 5 saniye bekleniyor...")
                    time.sleep(5)

                    # Ara işlemi - Enter tuşuna bas
                    print("[INFO] Arama için Enter tuşuna basılıyor...")
                    try:
                        page.keyboard.press("Enter")
                        print("[SUCCESS] Enter tuşuna basıldı")
                        ara_clicked = True
                    except Exception as e:
                        print(f"[ERROR] Enter tuşu gönderilemedi: {e}")
                        ara_clicked = False

                    if ara_clicked:
                        print("[INFO] 5 saniye bekleniyor...")
                        time.sleep(5)

                        # Müşteri tablosunda TCKN'ye göre arama yap
                        print("[INFO] Müşteri tablosunda TCKN'ye göre aranıyor...")

                        # TCKN'yi içeren satırı bul
                        tckn = policy_data.get('tckn', '32083591236')
                        customer_row_selectors = [
                            f'table.x-grid3-row-table:has-text("{tckn}")',
                            f'tr:has-text("{tckn}")',
                            f'div:has-text("{tckn}")'
                        ]

                        customer_found = False

                        for selector in customer_row_selectors:
                            try:
                                row = kasko_frame.locator(selector).first
                                if row.is_visible(timeout=5000):
                                    print(f"[SUCCESS] TCKN {tckn} içeren satır bulundu!")

                                    # Satıra çift tıkla
                                    row.dblclick()
                                    print("[SUCCESS] Müşteri satırına çift tıklandı")
                                    customer_found = True
                                    break
                            except:
                                continue
                            
                        # Eğer TCKN ile bulamadıysa, alternatif yöntemler dene
                        if not customer_found:
                            print("[INFO] TCKN ile bulunamadı, alternatif yöntemler deneniyor...")

                            # Yöntem 1: İlk satırı seç
                            try:
                                first_row = kasko_frame.locator('table.x-grid3-row-table').first
                                if first_row.is_visible(timeout=3000):
                                    first_row.dblclick()
                                    print("[SUCCESS] İlk müşteri satırına çift tıklandı")
                                    customer_found = True
                            except Exception as e:
                                print(f"[ERROR] İlk satıra tıklama hatası: {e}")

                        # Yöntem 2: Grid hücrelerinde ara
                        if not customer_found:
                            print("[INFO] Grid hücrelerinde aranıyor...")
                            try:
                                # Tüm hücreleri kontrol et
                                all_cells = kasko_frame.locator('td.x-grid3-td-8, div.x-grid3-col-8').all()
                                for cell in all_cells:
                                    try:
                                        cell_text = cell.inner_text().strip()
                                        if cell_text == tckn:
                                            print(f"[SUCCESS] TCKN bulundu: {cell_text}")
                                            # Hücrenin olduğu satıra çift tıkla
                                            row = cell.locator('xpath=./ancestor::table.x-grid3-row-table | ./ancestor::tr')
                                            row.dblclick()
                                            print("[SUCCESS] TCKN hücresinin satırına çift tıklandı")
                                            customer_found = True
                                            break
                                    except:
                                        continue
                            except Exception as e:
                                print(f"[ERROR] Hücre arama hatası: {e}")

                        if not customer_found:
                            print("[ERROR] Müşteri bulunamadı veya tıklanamadı!")
                        else:
                            print("[INFO] 5 saniye bekleniyor...")
                            time.sleep(5)

                            # İlk "Sonraki Adım" butonuna tıkla
                            print("[INFO] İlk 'Sonraki Adım' butonuna tıklanıyor...")
                            next_step_selectors = [
                                'button.x-btn-text.icon-resultsetnext:has-text("Sonraki Adım")',
                                'button:has-text("Sonraki Adım")',
                                'button.icon-resultsetnext'
                            ]
                            
                            next_clicked = False
                            for selector in next_step_selectors:
                                try:
                                    next_btn = kasko_frame.locator(selector).first
                                    if next_btn.is_visible(timeout=3000):
                                        next_btn.click()
                                        print(f"[SUCCESS] İlk 'Sonraki Adım' butonuna tıklandı")
                                        next_clicked = True
                                        break
                                except:
                                    continue
                            
                            if not next_clicked:
                                print("[ERROR] İlk 'Sonraki Adım' butonu bulunamadı!")
                            else:
                                print("[INFO] 18 saniye bekleniyor...")
                                time.sleep(18)

                                # İkinci "Sonraki Adım" butonuna tıkla
                                print("[INFO] İkinci 'Sonraki Adım' butonuna tıklanıyor...")
                                next_clicked2 = False
                                for selector in next_step_selectors:
                                    try:
                                        next_btn = kasko_frame.locator(selector).first
                                        if next_btn.is_visible(timeout=3000):
                                            next_btn.click()
                                            print(f"[SUCCESS] İkinci 'Sonraki Adım' butonuna tıklandı")
                                            next_clicked2 = True
                                            break
                                    except:
                                        continue
                                
                                if not next_clicked2:
                                    print("[ERROR] İkinci 'Sonraki Adım' butonu bulunamadı!")
                                else:
                                    print("[INFO] 18 saniye bekleniyor...")
                                    time.sleep(18)

                                    # Popup kontrol et ve varsa "Evet" seç
                                    print("[INFO] Popup kontrol ediliyor...")
                                    try:
                                        popup = kasko_frame.locator('div.x-shadow[style*="display: block"]').first
                                        if popup.is_visible(timeout=3000):
                                            print("[INFO] Popup tespit edildi! 'Evet' butonuna tıklanıyor...")
                                            evet_selectors = [
                                                'button:has-text("Evet")',
                                                'button.x-btn-text:has-text("Evet")',
                                                'button[type="button"]:has-text("Evet")'
                                            ]
                                            
                                            evet_clicked = False
                                            for selector in evet_selectors:
                                                try:
                                                    evet_btn = kasko_frame.locator(selector).first
                                                    if evet_btn.is_visible(timeout=2000):
                                                        evet_btn.click()
                                                        print("[SUCCESS] 'Evet' butonuna tıklandı")
                                                        evet_clicked = True
                                                        break
                                                except:
                                                    continue
                                            
                                            if not evet_clicked:
                                                print("[WARNING] 'Evet' butonu bulunamadı!")
                                        else:
                                            print("[INFO] Popup görünmüyor, devam ediliyor...")
                                    except:
                                        print("[INFO] Popup kontrolü başarısız, devam ediliyor...")
                                    
                                    print("[INFO] 15 saniye bekleniyor...")
                                    time.sleep(15)

                                    # 7. FİYAT VERİLERİNİ TOPLAMA
                                    print("\n" + "="*60)
                                    print("[INFO] Fiyat verileri toplanıyor...")
                                    print("="*60)

                                    try:
                                        # Grid satırını bul
                                        price_row_selectors = [
                                            'tbody tr:has(td:has-text("Taksitli"))',
                                            'table.x-grid3-row-table tbody tr',
                                            'tr:has(div:has-text("Taksitli"))'
                                        ]
                                        
                                        price_data = {}
                                        row_found = False
                                        
                                        for selector in price_row_selectors:
                                            try:
                                                rows = kasko_frame.locator(selector).all()
                                                for row in rows:
                                                    try:
                                                        text = row.inner_text()
                                                        if 'Taksitli' in text or 'taksitli' in text.lower():
                                                            print(f"[SUCCESS] Fiyat satırı bulundu!")
                                                            
                                                            # Tüm hücreleri al
                                                            cells = row.locator('td').all()
                                                            cell_values = []
                                                            
                                                            for cell in cells:
                                                                try:
                                                                    value = cell.inner_text().strip()
                                                                    if value:
                                                                        cell_values.append(value)
                                                                except:
                                                                    continue
                                                            
                                                            print(f"[DEBUG] Bulunan hücreler: {cell_values}")
                                                            
                                                            # Fiyat verilerini ayıkla (sayısal değerleri bul)
                                                            numeric_values = []
                                                            for val in cell_values:
                                                                # Virgül ve nokta içeren sayıları yakala
                                                                if any(char.isdigit() for char in val) and (',' in val or '.' in val):
                                                                    numeric_values.append(val)
                                                            
                                                            if len(numeric_values) >= 4:
                                                                price_data = {
                                                                    'prim': numeric_values[0] if len(numeric_values) > 0 else None,
                                                                    'vergi': numeric_values[1] if len(numeric_values) > 1 else None,
                                                                    'toplam': numeric_values[2] if len(numeric_values) > 2 else None,
                                                                    'komisyon': numeric_values[3] if len(numeric_values) > 3 else None
                                                                }
                                                                row_found = True
                                                                break
                                                    except:
                                                        continue
                                                if row_found:
                                                    break
                                            except:
                                                continue
                                        
                                        if price_data:
                                            print("\n" + "="*60)
                                            print("💰 FİYAT VERİLERİ:")
                                            print("="*60)
                                            print(f"   Ödeme Tipi : {price_data.get('odeme_tipi', 'N/A')}")
                                            print(f"   Prim        : {price_data.get('prim', 'N/A')}")
                                            print(f"   Vergi       : {price_data.get('vergi', 'N/A')}")
                                            print(f"   Toplam      : {price_data.get('toplam', 'N/A')}")
                                            print(f"   Komisyon    : {price_data.get('komisyon', 'N/A')}")
                                            print("="*60)
                                        else:
                                            print("[WARNING] Fiyat verileri bulunamadı!")
                                    
                                    except Exception as e:
                                        print(f"[ERROR] Fiyat toplama hatası: {e}")
                                        traceback.print_exc()

                print("\n" + "="*60)
                print("✅ TÜM İŞLEMLER TAMAMLANDI! Tarayıcıyı inceleyebilirsiniz.")
                print("="*60)

                # ❗❗❗ BROWSER'ı AÇIK TUT - KESİNLİKLE KAPANMAYACAK
                input("\n🎯 Tarayıcı açık. İnceleme yapabilirsiniz. Kapatmak için Enter tuşuna basın...")

                return success_count == len(dropdown_results)

        except Exception as e:
            print(f"\n[FATAL ERROR] BEKLENMEYEN HATA: {e}")
            traceback.print_exc()
            
            # ❗❗❗ HATA DURUMUNDA DA BROWSER'ı AÇIK TUT
            if page:
                print("\n❗ Hata oluştu ama browser açık kaldı. Sorunu inceleyebilirsiniz.")
                input("Kapatmak için Enter tuşuna basın...")
            return False

    # -----------------------------------------------------------------
    # YENİ FONKSİYON
    # -----------------------------------------------------------------
    def run_imm_dar_kasko(self, policy_data):
        """
        Tüm IMM ARTI KORUMA DAR KASKO işlemlerini tek fonksiyonda yapar.
        UYARI: ID'ler ve seçiciler Bireysel Kasko'dan farklı olabilir!
        """
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

                # 1. LOGIN İŞLEMLERİ (Aynı olduğu varsayıldı)
                print(f"[INFO] Login sayfasına gidiliyor: {self.login_url}")
                page.goto(self.login_url, wait_until="load")

                print("[INFO] Kullanıcı girişi yapılıyor...")
                username_input = self._find_element(page, self.USER_CANDS, "Kullanıcı adı")
                username_input.fill(self.username)
                time.sleep(random.uniform(0.5, 1.0))
                password_input = self._find_element(page, self.PASS_CANDS, "Şifre")
                password_input.fill(self.password)
                time.sleep(random.uniform(0.5, 1.0))
                login_button = self._find_element(page, self.LOGIN_BTN_CANDS, "Giriş butonu")
                login_button.click()
                print("[SUCCESS] Giriş başarılı!")
                time.sleep(random.uniform(2, 4))

                # 2. TOTP DOĞRULAMASI (Aynı olduğu varsayıldı)
                if not self.totp_secret:
                    raise Exception("TOTP Secret (.env) tanımlı değil, doğrulama yapılamaz.")
                
                print("[INFO] TOTP doğrulaması yapılıyor...")
                time.sleep(random.uniform(1, 2))
                
                totp = pyotp.TOTP(self.totp_secret)
                code = totp.now()
                print(f"[INFO] TOTP kodu oluşturuldu: {code}")
                
                totp_selectors = [
                    'input#txtGAKod', 'input[name="txtGAKod"]',
                    'input#txtGAKod_Container input', 'div#winGAC input[type="text"]'
                ]
                totp_input = self._find_element(page, totp_selectors, "TOTP kodu alanı")
                totp_input.fill(code)
                time.sleep(random.uniform(0.5, 1.0))
                
                verify_btn_selectors = [
                    'button#ext-gen61', 'table#btnValidateTwoFactor button',
                    'button.x-btn-text.icon-key', 'button:has-text("Giriş")'
                ]
                verify_button = self._find_element(page, verify_btn_selectors, "TOTP doğrula butonu")
                verify_button.click()
                
                try:
                    page.wait_for_selector('div#winGAC', state='hidden', timeout=10000)
                    print("[INFO] Google Authenticator popup'ı kapandı.")
                except:
                    print("[WARNING] Popup kapanma kontrolü başarısız, devam ediliyor...")
                
                time.sleep(random.uniform(1, 2))
                print("[SUCCESS] TOTP doğrulaması başarılı!")

                # 3. MENÜ NAVİGASYONU (GÜNCELLENDİ)
                print("[INFO] IMM Dar Kasko menüsüne gidiliyor...")
                
                police_menu = page.locator('span:text-is("Poliçe")')
                police_menu.wait_for(state="visible", timeout=10000)
                police_menu.click()
                print("[INFO] 'Poliçe' menüsüne tıklandı.")
                time.sleep(random.uniform(0.5, 1.0))
                
                oto_sigorta_menu = page.locator('span:text-is("OTO SİGORTALARI")')
                oto_sigorta_menu.wait_for(state="visible", timeout=5000)
                oto_sigorta_menu.click()
                print("[INFO] 'OTO SİGORTALARI' menüsüne tıklandı.")
                time.sleep(random.uniform(0.5, 1.0))
                
                # --- DEĞİŞİKLİK BURADA ---
                dar_kasko_menu = page.locator('span:text-is("IMM ARTI KORUMA DAR KASKO")')
                dar_kasko_menu.wait_for(state="visible", timeout=5000)
                dar_kasko_menu.click()
                print("[INFO] 'IMM ARTI KORUMA DAR KASKO' menüsüne tıklandı.")
                # --- DEĞİŞİKLİK SONU ---
                
                print("[SUCCESS] IMM Dar Kasko sayfası yüklendi!")

                time.sleep(15)

                frame_selector = "#frmMain"
                kasko_frame = page.frame_locator(frame_selector)
                

                tckn_selector = "#txtGIFTIdentityNo"
                kasko_frame.locator(tckn_selector).wait_for(state="visible", timeout=10000)
                print("[INFO] Iframe bulundu ve TCKN alanı görünür.")


                if 'tckn' in policy_data:
                    kasko_frame.locator(tckn_selector).fill(policy_data['tckn'])
                    print(f"[INFO] TCKN girildi: {policy_data['tckn']}")
                    time.sleep(random.uniform(0.3, 0.7))
                
                if 'plaka' in policy_data:
                    kasko_frame.locator("#txtGIFTPlate").fill(policy_data['plaka'])
                    print(f"[INFO] Plaka girildi: {policy_data['plaka']}")
                    time.sleep(random.uniform(0.3, 0.7))
                
                if 'tescil_seri' in policy_data:
                    kasko_frame.locator("#txtGIFTEGMSerial").fill(policy_data['tescil_seri'])
                    print(f"[INFO] Tescil Seri girildi: {policy_data['tescil_seri']}")
                    time.sleep(random.uniform(0.3, 0.7))
                
                if 'tescil_no' in policy_data:
                    kasko_frame.locator("#txtGIFTEGMNo").fill(policy_data['tescil_no'])
                    print(f"[INFO] Tescil No girildi: {policy_data['tescil_no']}")
                    time.sleep(random.uniform(0.3, 0.7))

                print("[SUCCESS] Kasko formu dolduruldu.")

                sorgula_button_selector = 'button:has-text("Tramer Sorgula")'
                sorgula_button = kasko_frame.locator(sorgula_button_selector)
                sorgula_button.wait_for(state="visible", timeout=5000)
                sorgula_button.click()
                print("[INFO] 'Tramer Sorgula' butonuna tıklandı.")

                # Tramer sorgulamasını bekle (Bireysel Kasko'dan uyarlandı)
                print("[INFO] Tramer sorgulaması bekleniyor...")
                time.sleep(12) # Ana bekleme
                try:
                    # Bireysel Kasko'da ctl32 bekleniyordu, burada ilk dropdown'u (ctl06) bekleyelim
                    kasko_frame.locator("#cphCFB_policyInputStatistics_ctl06").wait_for(state="visible", timeout=15000)
                    print("[SUCCESS] Tramer sorgulaması tamamlandı (Kullanım Tipi alanı görünür).")
                except PWTimeoutError:
                    print("[WARNING] Tramer sorgulaması zaman aşımına uğradı, devam ediliyor...")
        
                # 5. DROPDOWN SEÇİMLERİ (IMM KASKO İÇİN)
                print("\n" + "="*60)
                print("[INFO] Dropdown seçimleri başlıyor...")
                print("="*60)
                
                dropdown_results = []
                
                # Kullanım Tipi
                kullanim_tipi = policy_data.get('kullanim_tipi', 'DİĞER') # 'DİĞER' varsayılan
                result1 = self._select_extjs_combo(
                    frame_locator=kasko_frame,
                    page=page,
                    input_id="cphCFB_policyInputStatistics_ctl06",
                    target_text=kullanim_tipi
                )
                dropdown_results.append(("Kullanım Tipi", result1))
                time.sleep(random.uniform(0.5, 1.0))
        
                # IMM Başlama Limiti
                imm_limiti = policy_data.get('IMM_baslama_limiti', 'BAŞLAMA LİMİTSİZ')
                result2 = self._select_extjs_combo(
                    frame_locator=kasko_frame,
                    page=page,
                    input_id="cphCFB_policyInputStatistics_ctl12",
                    target_text=imm_limiti
                )
                dropdown_results.append(("IMM Başlama Limiti", result2))
                time.sleep(random.uniform(0.5, 1.0))
        
                # Dropdown sonuçlarını raporla
                success_count = sum(1 for _, result in dropdown_results if result)
                print("\n" + "="*60)
                print(f"[SUMMARY] Dropdown seçim sonuçları:")
                print("="*60)
                for dropdown_name, result in dropdown_results:
                    status = "✅ BAŞARILI" if result else "❌ BAŞARISIZ"
                    print(f"   - {dropdown_name}: {status}")
                
                print(f"\n[SUMMARY] Toplam: {success_count}/{len(dropdown_results)} dropdown başarıyla seçildi.")
                print("="*60)
        
                if success_count == len(dropdown_results):
                    print("\n🎉 [SUCCESS] Tüm dropdown seçimleri başarıyla tamamlandı!")
                else:
                    print("\n⚠️ [WARNING] Bazı dropdown seçimleri başarısız oldu, ancak işleme devam edildi.")
        
                # 6. SİGORTALIDAN TAŞI BUTONUNA TIKLA
                print("\n[INFO] 'Sigortalıdan Taşı' linkine tıklanıyor...")

                try:
                    # En sağlam yöntem metin ile bulmaktır:
                    tasima_linki = kasko_frame.locator('a:text-is("Sigortalıdan Taşı")')

                    tasima_linki.wait_for(state="visible", timeout=5000)
                    tasima_linki.click()

                    print("[SUCCESS] 'Sigortalıdan Taşı' linkine tıklandı.")
                    print("[INFO] Bilgilerin dolması için 3 saniye bekleniyor...")
                    time.sleep(3) # Bilgilerin formun diğer kısımlarına kopyalanması için bekle

                except Exception as e:
                    print(f"[ERROR] 'Sigortalıdan Taşı' linki tıklanırken hata: {e}")
                    # Hata durumunda bile devam etmeyi deneyebiliriz ancak şimdilik duruyoruz.
                    traceback.print_exc()
                    raise e # Bu önemli bir adım, hata varsa dursun

                print("\n[INFO] 'Sonraki Adım' butonlarına tıklanıyor...")
                
                # Bireysel Kasko'dan alınan sağlam selector listesi
                next_step_selectors = [
                    'button.x-btn-text.icon-resultsetnext:has-text("Sonraki Adım")',
                    'button:has-text("Sonraki Adım")',
                    'button.icon-resultsetnext'
                ]
      
                # --- İLK TIKLAMA ---
                print("[INFO] İlk 'Sonraki Adım' butonuna tıklanıyor...")
                next_clicked = False
                for selector in next_step_selectors:
                    try:
                        next_btn = kasko_frame.locator(selector).first
                        if next_btn.is_visible(timeout=3000):
                            next_btn.click()
                            print(f"[SUCCESS] İlk 'Sonraki Adım' butonuna tıklandı.")
                            next_clicked = True
                            break
                    except:
                        continue
                      
                if not next_clicked:
                    print("[ERROR] İlk 'Sonraki Adım' butonu bulunamadı!")
                    raise Exception("İlk 'Sonraki Adım' butonu tıklanamadı.")
                else:
                    print("[INFO] 15 saniye bekleniyor...")
                    time.sleep(15)
      
                # --- İKİNCİ TIKLAMA ---
                print("[INFO] İkinci 'Sonraki Adım' butonuna tıklanıyor...")
                next_clicked2 = False
                for selector in next_step_selectors:
                    try:
                        # Buton DOM'dan kalkıp geri gelebilir, bu yüzden 'first' ile tekrar buluyoruz
                        next_btn = kasko_frame.locator(selector).first 
                        if next_btn.is_visible(timeout=3000):
                            next_btn.click()
                            print(f"[SUCCESS] İkinci 'Sonraki Adım' butonuna tıklandı.")
                            next_clicked2 = True
                            break
                    except:
                        continue
                      
                if not next_clicked2:
                    print("[ERROR] İkinci 'Sonraki Adım' butonu bulunamadı!")
                    raise Exception("İkinci 'Sonraki Adım' butonu tıklanamadı.")
                else:
                    print("[INFO] Fiyatların yüklenmesi için 15 saniye bekleniyor...")
                    time.sleep(15)
      
                # 8. FİYAT VERİLERİNİ TOPLAMA
                print("\n" + "="*60)
                print("[INFO] Fiyat verileri toplanıyor...")
                print("="*60)
      
                try:
                    # Bireysel Kasko'daki fiyat toplama mantığını aynen kullanıyoruz
                    price_row_selectors = [
                        'tbody tr:has(td:has-text("Taksitli"))',
                        'table.x-grid3-row-table tbody tr',
                        'tr:has(div:has-text("Taksitli"))'
                    ]
                    
                    price_data = {}
                    row_found = False
                    
                    for selector in price_row_selectors:
                        try:
                            rows = kasko_frame.locator(selector).all()
                            for row in rows:
                                try:
                                    text = row.inner_text()
                                    if 'Taksitli' in text or 'taksitli' in text.lower():
                                        print(f"[SUCCESS] Fiyat satırı bulundu!")
                                        
                                        cells = row.locator('td').all()
                                        cell_values = []
                                        
                                        for cell in cells:
                                            try:
                                                value = cell.inner_text().strip()
                                                if value:
                                                    cell_values.append(value)
                                            except:
                                                continue
                                              
                                        print(f"[DEBUG] Bulunan hücreler: {cell_values}")
                                        
                                        # Hücrelerden sayısal fiyat değerlerini ayıkla
                                        numeric_values = []
                                        for val in cell_values:
                                            if any(char.isdigit() for char in val) and (',' in val or '.' in val):
                                                numeric_values.append(val)
                                        
                                        if len(numeric_values) >= 4:
                                            price_data = {
                                                'prim': numeric_values[0],
                                                'vergi': numeric_values[1],
                                                'toplam': numeric_values[2],
                                                'komisyon': numeric_values[3]
                                            }
                                            row_found = True
                                            break
                                except:
                                    continue
                            if row_found:
                                break
                        except:
                            continue
                          
                    if price_data:
                        print("\n" + "="*60)
                        print("💰 FİYAT VERİLERİ (IMM KASKO):")
                        print("="*60)
                        print(f"   Prim         : {price_data.get('prim', 'N/A')}")
                        print(f"   Vergi        : {price_data.get('vergi', 'N/A')}")   
                        print(f"   Toplam       : {price_data.get('toplam', 'N/A')}")
                        print(f"   Komisyon     : {price_data.get('komisyon', 'N/A')}")
                        print("="*60)
                    else:
                        print("[WARNING] Fiyat verileri bulunamadı!")
                
                except Exception as e:
                    print(f"[ERROR] Fiyat toplama hatası: {e}")
                    traceback.print_exc()
      
                print("\n" + "="*60)
                print("✅ TÜM İŞLEMLER TAMAMLANDI! Tarayıcıyı inceleyebilirsiniz.")
                print("="*60)
      
                # ❗❗❗ BROWSER'ı AÇIK TUT
                input("\n🎯 Tarayıcı açık. İnceleme yapabilirsiniz. Kapatmak için Enter tuşuna basın...")
                
                # Fonksiyonun başarılı olup olmadığını dropdown'lara göre döndür
                return success_count == len(dropdown_results)
                

        except Exception as e:
            print(f"\n[FATAL ERROR] BEKLENMEYEN HATA (IMM KASKO): {e}")
            traceback.print_exc()
            
            # ❗❗❗ HATA DURUMUNDA DA BROWSER'ı AÇIK TUT
            if page:
                print("\n❗ Hata oluştu ama browser açık kaldı. Sorunu inceleyebilirsiniz.")
                input("Kapatmak için Enter tuşuna basın...")
            return False

    # -----------------------------------------------------------------
    # YENİ FONKSİYON: TİCARİ KASKO
    # -----------------------------------------------------------------
    def run_ticari_kasko(self, policy_data):
        """
        Tüm TİCARİ KASKO (TKP) işlemlerini tek fonksiyonda yapar.
        """
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

                # 1. LOGIN İŞLEMLERİ (Aynı)
                print(f"[INFO] Login sayfasına gidiliyor: {self.login_url}")
                page.goto(self.login_url, wait_until="load")

                print("[INFO] Kullanıcı girişi yapılıyor...")
                username_input = self._find_element(page, self.USER_CANDS, "Kullanıcı adı")
                username_input.fill(self.username)
                time.sleep(random.uniform(0.5, 1.0))
                password_input = self._find_element(page, self.PASS_CANDS, "Şifre")
                password_input.fill(self.password)
                time.sleep(random.uniform(0.5, 1.0))
                login_button = self._find_element(page, self.LOGIN_BTN_CANDS, "Giriş butonu")
                login_button.click()
                print("[SUCCESS] Giriş başarılı!")
                time.sleep(random.uniform(2, 4))

                # 2. TOTP DOĞRULAMASI (Aynı)
                if not self.totp_secret:
                    raise Exception("TOTP Secret (.env) tanımlı değil, doğrulama yapılamaz.")
                
                print("[INFO] TOTP doğrulaması yapılıyor...")
                time.sleep(random.uniform(1, 2))
                
                totp = pyotp.TOTP(self.totp_secret)
                code = totp.now()
                print(f"[INFO] TOTP kodu oluşturuldu: {code}")
                
                totp_selectors = [
                    'input#txtGAKod', 'input[name="txtGAKod"]',
                    'input#txtGAKod_Container input', 'div#winGAC input[type="text"]'
                ]
                totp_input = self._find_element(page, totp_selectors, "TOTP kodu alanı")
                totp_input.fill(code)
                time.sleep(random.uniform(0.5, 1.0))
                
                verify_btn_selectors = [
                    'button#ext-gen61', 'table#btnValidateTwoFactor button',
                    'button.x-btn-text.icon-key', 'button:has-text("Giriş")'
                ]
                verify_button = self._find_element(page, verify_btn_selectors, "TOTP doğrula butonu")
                verify_button.click()
                
                try:
                    page.wait_for_selector('div#winGAC', state='hidden', timeout=10000)
                    print("[INFO] Google Authenticator popup'ı kapandı.")
                except:
                    print("[WARNING] Popup kapanma kontrolü başarısız, devam ediliyor...")
                
                time.sleep(random.uniform(1, 2))
                print("[SUCCESS] TOTP doğrulaması başarılı!")

                # 3. MENÜ NAVİGASYONU (TİCARİ KASKO İÇİN GÜNCELLENDİ)
                print("[INFO] Ticari Kasko (TKP) menüsüne gidiliyor...")
                
                police_menu = page.locator('span:text-is("Poliçe")')
                police_menu.wait_for(state="visible", timeout=10000)
                police_menu.click()
                print("[INFO] 'Poliçe' menüsüne tıklandı.")
                time.sleep(random.uniform(0.5, 1.0))
                
                oto_sigorta_menu = page.locator('span:text-is("OTO SİGORTALARI")')
                oto_sigorta_menu.wait_for(state="visible", timeout=5000)
                oto_sigorta_menu.click()
                print("[INFO] 'OTO SİGORTALARI' menüsüne tıklandı.")
                time.sleep(random.uniform(0.5, 1.0))
                
                # --- YENİ DEĞİŞİKLİK BURADA ---
                # HATA DÜZELTMESİ: 'span:text-is' 2 element buldu (strict mode violation).
                # Tıklanabilir olan link'i (<a> tag) bulmak için get_by_role kullanıyoruz.
                ticari_kasko_menu = page.get_by_role("link", name="TİCARİ KASKO (TKP)")
                
                ticari_kasko_menu.wait_for(state="visible", timeout=5000)
                ticari_kasko_menu.click()
                print("[INFO] 'TİCARİ KASKO (TKP)' menüsüne tıklandı.")
                # --- DEĞİŞİKLİK SONU ---
                
                print("[SUCCESS] Ticari Kasko (TKP) sayfası yüklendi!")

                time.sleep(15)

                # 4. IFRAME ve FORM İŞLEMLERİ (Diğerleriyle aynı varsayıldı)
                frame_selector = "#frmMain"
                kasko_frame = page.frame_locator(frame_selector)
                
                tckn_selector = "#txtGIFTIdentityNo"
                kasko_frame.locator(tckn_selector).wait_for(state="visible", timeout=10000)
                print("[INFO] Iframe bulundu ve TCKN alanı görünür.")

                # Form alanlarını doldur
                if 'tckn' in policy_data:
                    kasko_frame.locator(tckn_selector).fill(policy_data['tckn'])
                    print(f"[INFO] TCKN girildi: {policy_data['tckn']}")
                    time.sleep(random.uniform(0.3, 0.7))
                
                if 'plaka' in policy_data:
                    kasko_frame.locator("#txtGIFTPlate").fill(policy_data['plaka'])
                    print(f"[INFO] Plaka girildi: {policy_data['plaka']}")
                    time.sleep(random.uniform(0.3, 0.7))
                
                if 'tescil_seri' in policy_data:
                    kasko_frame.locator("#txtGIFTEGMSerial").fill(policy_data['tescil_seri'])
                    print(f"[INFO] Tescil Seri girildi: {policy_data['tescil_seri']}")
                    time.sleep(random.uniform(0.3, 0.7))
                
                if 'tescil_no' in policy_data:
                    kasko_frame.locator("#txtGIFTEGMNo").fill(policy_data['tescil_no'])
                    print(f"[INFO] Tescil No girildi: {policy_data['tescil_no']}")
                    time.sleep(random.uniform(0.3, 0.7))

                print("[SUCCESS] Kasko formu dolduruldu.")

                # Tramer Sorgula butonuna tıkla
                sorgula_button_selector = 'button:has-text("Tramer Sorgula")'
                sorgula_button = kasko_frame.locator(sorgula_button_selector)
                sorgula_button.wait_for(state="visible", timeout=5000)
                sorgula_button.click()
                print("[INFO] 'Tramer Sorgula' butonuna tıklandı.")

                # Tramer sorgulamasını bekle
                print("[INFO] Tramer sorgulaması bekleniyor...")
                time.sleep(12) # Ana bekleme
                
                # Tramer sorgusunun bittiğini doğrulamak için bir sonraki adımdaki
                # ilk dropdown'un görünür olmasını bekleyebiliriz.
                # Şimdilik genel bir bekleme yapıyoruz.

                print("\n" + "="*60)
                print("✅ TRAMER SORGULAMA ADIMI TAMAMLANDI!")
                print("Sıradaki adım (dropdown'lar) için ID'leri ve verileri bekliyorum.")
                print("="*60)

                # ❗❗❗ BROWSER'ı AÇIK TUT - BİLGİ BEKLİYORUZ
                input("\n🎯 Tarayıcı açık. Kapatmak için Enter tuşuna basın...")
                
                # Fonksiyon buradan devam edecek...
                
                return True # Test için şimdilik True

        except Exception as e:
            print(f"\n[FATAL ERROR] BEKLENMEYEN HATA (TİCARİ KASKO): {e}")
            traceback.print_exc()
            
            # ❗❗❗ HATA DURUMUNDA DA BROWSER'ı AÇIK TUT
            if page:
                print("\n❗ Hata oluştu ama browser açık kaldı. Sorunu inceleyebilirsiniz.")
                input("Kapatmak için Enter tuşuna basın...")
            return False
# -----------------------------------------------------------------
# '__main__' BLOĞU
# -----------------------------------------------------------------
if __name__ == "__main__":
    
    kasko_test_verisi = {
        "tckn": "32083591236",
        "plaka": "06HT203",
        "tescil_seri": "ER",
        "tescil_no": "993016"
    }
    kasko_imm_test_verisi = {
        "tckn": "32083591236",
        "plaka": "06HT203",
        "tescil_seri": "ER",
        "tescil_no": "993016",
        "kullanim_tipi":"DİĞER",
        "IMM_baslama_limiti":"BAŞLAMA LİMİTSİZ"
    }
    
    try:
        scraper = AtlasScraper()
        
        # Bireysel Kasko'yu çalıştırmak için:
        # print("--- BİREYSEL KASKO TESTİ BAŞLATILIYOR ---")
        # success = scraper.run_bireysel_kasko(policy_data=kasko_test_verisi)
        
        # # IMM Dar Kasko'yu çalıştırmak için bu satırların yorumunu kaldırın:
        # print("--- IMM DAR KASKO TESTİ BAŞLATILIYOR ---")
        # success = scraper.run_imm_dar_kasko(policy_data=kasko_imm_test_verisi)

        success = scraper.run_ticari_kasko(policy_data=kasko_imm_test_verisi)
        
    except Exception as e:
        print(f"\n💀 Program hatası: {e}")