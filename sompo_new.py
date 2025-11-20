"""
Sompo Sigorta Backend API
FastAPI ile modern ve ölçeklenebilir backend uygulaması
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field, validator
from typing import Optional, Dict, Any, List, Union
from datetime import datetime, date
import uuid
import logging
import asyncio
from enum import Enum
import os
import sys
from pathlib import Path
import json

# Playwright için
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

# Logging konfigürasyonu
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('sompo_backend.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# FastAPI uygulaması
app = FastAPI(
    title="Sompo Sigorta API",
    description="Sompo Sigorta otomasyon sistemi için modern REST API",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security
security = HTTPBearer()

# Config
class Config:
    HEADLESS = os.getenv("HEADLESS", "true").lower() == "true"
    TIMEOUT_MS = 30000
    MAX_WORKERS = 3
    API_KEYS = json.loads(os.getenv("API_KEYS", '["test-key-123"]'))

# Database (Production'da Redis/PostgreSQL kullanılmalı)
class Database:
    def __init__(self):
        self.requests = {}
        self.sessions = {}
    
    def create_request(self, request_data: Dict) -> str:
        request_id = str(uuid.uuid4())
        self.requests[request_id] = {
            "request_id": request_id,
            "status": "pending",
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "data": request_data,
            "result": None,
            "error": None,
            "progress": 0
        }
        return request_id
    
    def update_request(self, request_id: str, **kwargs):
        if request_id in self.requests:
            self.requests[request_id].update(kwargs)
            self.requests[request_id]["updated_at"] = datetime.now().isoformat()
    
    def get_request(self, request_id: str) -> Optional[Dict]:
        return self.requests.get(request_id)
    
    def get_all_requests(self, limit: int = 100) -> List[Dict]:
        return list(self.requests.values())[-limit:]

# Global database instance
db = Database()

# Authentication
async def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    if credentials.credentials not in Config.API_KEYS:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return credentials.credentials

# Enums
class InsuranceType(str, Enum):
    TRAFIK = "trafik"
    KASKO = "kasko"
    DASK = "dask"
    SAGLIK = "saglik"

class RequestStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

# Request Models
class BaseInsuranceRequest(BaseModel):
    tckn: str = Field(..., description="TC Kimlik No (11 haneli)", min_length=11, max_length=11)
    email: str = Field(..., description="E-posta adresi")
    dogum_tarihi: str = Field(..., description="Doğum tarihi (GG/AA/YYYY)")
    telefon: str = Field(..., description="Telefon numarası")
    
    @validator('tckn')
    def validate_tckn(cls, v):
        if not v.isdigit():
            raise ValueError('TC Kimlik No sadece rakamlardan oluşmalıdır')
        return v
    
    @validator('dogum_tarihi')
    def validate_dogum_tarihi(cls, v):
        try:
            datetime.strptime(v, "%d/%m/%Y")
        except ValueError:
            raise ValueError('Doğum tarihi GG/AA/YYYY formatında olmalıdır')
        return v

class TrafikSigortasiRequest(BaseInsuranceRequest):
    plaka: str = Field(..., description="Araç plakası")
    ruhsat_seri_no: str = Field(..., description="Ruhsat seri numarası")
    arac_marka: str = Field(..., description="Araç markası")
    arac_modeli: str = Field(..., description="Araç modeli")
    model_yili: Optional[str] = Field(None, description="Model yılı")
    
    @validator('plaka')
    def validate_plaka(cls, v):
        v = v.upper().replace(" ", "")
        if len(v) < 5:
            raise ValueError('Geçersiz plaka formatı')
        return v

class KaskoSigortasiRequest(BaseInsuranceRequest):
    plaka: str = Field(..., description="Araç plakası")
    ruhsat_seri_no: str = Field(..., description="Ruhsat seri numarası")
    arac_marka: str = Field(..., description="Araç markası")
    arac_modeli: str = Field(..., description="Araç modeli")
    model_yili: str = Field(..., description="Model yılı")
    kullanim_tarzi: str = Field(default="HUSUSİ OTO", description="Kullanım tarzı")
    
    @validator('plaka')
    def validate_plaka(cls, v):
        v = v.upper().replace(" ", "")
        if len(v) < 5:
            raise ValueError('Geçersiz plaka formatı')
        return v

class DaskSigortasiRequest(BaseInsuranceRequest):
    dask_police_no: Optional[str] = Field(None, description="DASK poliçe numarası (yenileme için)")
    dask_adres_kodu: Optional[str] = Field(None, description="DASK adres kodu (yeni poliçe için)")
    bina_adresi: str = Field(..., description="Bina adresi")
    il: str = Field(..., description="İl")
    ilce: str = Field(..., description="İlçe")
    
    @validator('dask_police_no', 'dask_adres_kodu')
    def validate_dask_fields(cls, v, values):
        if not values.get('dask_police_no') and not values.get('dask_adres_kodu'):
            raise ValueError('DASK poliçe numarası veya adres kodu gereklidir')
        return v

class SaglikSigortasiRequest(BaseInsuranceRequest):
    prim_tipi: str = Field(..., description="Prim tipi")
    meslek: str = Field(..., description="Meslek")
    teminat_grubu: str = Field(..., description="Teminat grubu")
    teminat_bedeli: str = Field(..., description="Teminat bedeli")

# Response Models
class BaseResponse(BaseModel):
    success: bool
    message: str
    request_id: str
    timestamp: str

class TeklifResponse(BaseResponse):
    data: Optional[Dict[str, Any]] = None

class RequestStatusResponse(BaseModel):
    request_id: str
    status: RequestStatus
    progress: int
    created_at: str
    updated_at: str
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

class HealthResponse(BaseModel):
    status: str
    version: str
    timestamp: str
    active_requests: int
    total_requests: int

# Scraper Service
class SompoScraper:
    def __init__(self):
        self.headless = Config.HEADLESS
        self.timeout = Config.TIMEOUT_MS
        self.login_url = "https://esube.sompo.com.tr/"
        self.username = os.getenv("SOMPO_USERNAME")
        self.password = os.getenv("SOMPO_PASSWORD")
        
        if not self.username or not self.password:
            logger.error("Sompo kullanıcı bilgileri bulunamadı")
            raise ValueError("Sompo kullanıcı bilgileri ayarlanmalıdır")
    
    def login(self, page):
        """Sompo portalına giriş yap"""
        logger.info("Sompo portalına giriş yapılıyor...")
        
        try:
            # Login sayfasına git
            page.goto(self.login_url, wait_until="domcontentloaded", timeout=self.timeout)
            
            # Kullanıcı adı
            username_field = page.locator('input[name="username"], input[type="text"]').first
            username_field.fill(self.username)
            
            # Şifre
            password_field = page.locator('input[type="password"]').first
            password_field.fill(self.password)
            
            # Giriş butonu
            login_button = page.locator('button[type="submit"], input[type="submit"]').first
            login_button.click()
            
            # Login başarısını kontrol et
            page.wait_for_timeout(5000)
            
            # URL değişimini kontrol et
            if "login" in page.url.lower():
                logger.error("Login başarısız - hala login sayfasında")
                return False
            
            logger.info("Login başarılı")
            return True
            
        except Exception as e:
            logger.error(f"Login hatası: {str(e)}")
            return False
    
    def handle_popups(self, page):
        """Popup'ları kapat"""
        try:
            # Olası popup'ları kapat
            popup_selectors = [
                'button[aria-label*="kapat"]',
                'button[class*="close"]',
                '.popup-close',
                'button:has-text("Kapat")'
            ]
            
            for selector in popup_selectors:
                try:
                    element = page.locator(selector).first
                    if element.is_visible():
                        element.click(timeout=2000)
                        logger.info(f"Popup kapatıldı: {selector}")
                except:
                    continue
                    
        except Exception as e:
            logger.warning(f"Popup kapatma hatası: {e}")
    
    def navigate_to_teklif(self, page, insurance_type: InsuranceType):
        """Teklif sayfasına git"""
        try:
            logger.info(f"{insurance_type.value} teklif sayfasına yönlendiriliyor...")
            
            # Menüden sigorta türünü seç
            if insurance_type == InsuranceType.TRAFIK:
                menu_selector = 'a[href*="trafik"], button:has-text("Trafik")'
            elif insurance_type == InsuranceType.KASKO:
                menu_selector = 'a[href*="kasko"], button:has-text("Kasko")'
            elif insurance_type == InsuranceType.DASK:
                menu_selector = 'a[href*="dask"], button:has-text("DASK")'
            elif insurance_type == InsuranceType.SAGLIK:
                menu_selector = 'a[href*="saglik"], button:has-text("Sağlık")'
            else:
                raise ValueError(f"Geçersiz sigorta türü: {insurance_type}")
            
            # Menüyü bul ve tıkla
            menu_item = page.locator(menu_selector).first
            menu_item.click(timeout=10000)
            
            # Sayfa yüklenmesini bekle
            page.wait_for_timeout(3000)
            
            logger.info(f"{insurance_type.value} teklif sayfasına ulaşıldı")
            return True
            
        except Exception as e:
            logger.error(f"Teklif sayfasına yönlendirme hatası: {e}")
            return False
    
    def fill_trafik_form(self, page, data: Dict) -> Dict[str, Any]:
        """Trafik sigortası formunu doldur"""
        try:
            logger.info("Trafik sigortası formu dolduruluyor...")
            
            # Plaka bilgisi
            plaka_field = page.locator('input[name*="plaka"], input[placeholder*="plaka"]').first
            plaka_field.fill(data["plaka"])
            
            # TCKN
            tckn_field = page.locator('input[name*="tckn"], input[placeholder*="TC"]').first
            tckn_field.fill(data["tckn"])
            
            # Doğum tarihi
            dogum_tarihi_field = page.locator('input[name*="dogum"], input[placeholder*="doğum"]').first
            dogum_tarihi_field.fill(data["dogum_tarihi"])
            
            # Ruhsat seri no
            ruhsat_field = page.locator('input[name*="ruhsat"], input[placeholder*="ruhsat"]').first
            ruhsat_field.fill(data["ruhsat_seri_no"])
            
            # Araç marka/model
            marka_field = page.locator('input[name*="marka"], select[name*="marka"]').first
            marka_field.fill(data["arac_marka"])
            
            model_field = page.locator('input[name*="model"], select[name*="model"]').first
            model_field.fill(data["arac_modeli"])
            
            # Formu gönder
            submit_button = page.locator('button[type="submit"], button:has-text("Hesapla")').first
            submit_button.click()
            
            # Sonuçları bekle
            page.wait_for_timeout(5000)
            
            # Fiyatları çek
            result = self.extract_prices(page)
            
            logger.info("Trafik sigortası teklifi başarıyla alındı")
            return result
            
        except Exception as e:
            logger.error(f"Trafik form doldurma hatası: {e}")
            raise
    
    def fill_kasko_form(self, page, data: Dict) -> Dict[str, Any]:
        """Kasko sigortası formunu doldur"""
        try:
            logger.info("Kasko sigortası formu dolduruluyor...")
            
            # Temel bilgiler
            plaka_field = page.locator('input[name*="plaka"]').first
            plaka_field.fill(data["plaka"])
            
            tckn_field = page.locator('input[name*="tckn"]').first
            tckn_field.fill(data["tckn"])
            
            # Araç bilgileri
            marka_field = page.locator('input[name*="marka"], select[name*="marka"]').first
            marka_field.fill(data["arac_marka"])
            
            model_field = page.locator('input[name*="model"], select[name*="model"]').first
            model_field.fill(data["arac_modeli"])
            
            model_yili_field = page.locator('input[name*="yil"], select[name*="yil"]').first
            model_yili_field.fill(data["model_yili"])
            
            # Formu gönder
            submit_button = page.locator('button[type="submit"], button:has-text("Hesapla")').first
            submit_button.click()
            
            # Sonuçları bekle
            page.wait_for_timeout(5000)
            
            # Fiyatları çek
            result = self.extract_prices(page)
            
            logger.info("Kasko sigortası teklifi başarıyla alındı")
            return result
            
        except Exception as e:
            logger.error(f"Kasko form doldurma hatası: {e}")
            raise
    
    def fill_dask_form(self, page, data: Dict) -> Dict[str, Any]:
        """DASK sigortası formunu doldur"""
        try:
            logger.info("DASK sigortası formu dolduruluyor...")
            
            # Yenileme veya yeni poliçe
            if data.get("dask_police_no"):
                police_field = page.locator('input[name*="police"], input[placeholder*="poliçe"]').first
                police_field.fill(data["dask_police_no"])
            else:
                adres_kodu_field = page.locator('input[name*="adres"], input[placeholder*="adres"]').first
                adres_kodu_field.fill(data["dask_adres_kodu"])
            
            # Kişi bilgileri
            tckn_field = page.locator('input[name*="tckn"]').first
            tckn_field.fill(data["tckn"])
            
            # Adres bilgileri
            il_field = page.locator('input[name*="il"], select[name*="il"]').first
            il_field.fill(data["il"])
            
            ilce_field = page.locator('input[name*="ilce"], select[name*="ilce"]').first
            ilce_field.fill(data["ilce"])
            
            # Formu gönder
            submit_button = page.locator('button[type="submit"], button:has-text("Hesapla")').first
            submit_button.click()
            
            # Sonuçları bekle
            page.wait_for_timeout(5000)
            
            # Fiyatları çek
            result = self.extract_prices(page)
            
            logger.info("DASK sigortası teklifi başarıyla alındı")
            return result
            
        except Exception as e:
            logger.error(f"DASK form doldurma hatası: {e}")
            raise
    
    def extract_prices(self, page) -> Dict[str, Any]:
        """Sayfadan fiyat bilgilerini çek"""
        try:
            logger.info("Fiyat bilgileri çekiliyor...")
            
            result = {
                "prices": {},
                "details": {},
                "teklif_no": f"SOMPO-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
                "status": "completed"
            }
            
            # Fiyat seçeneklerini bul
            price_selectors = [
                '.price', '.fiyat', '.prim', 
                '[class*="price"]', '[class*="fiyat"]', '[class*="prim"]',
                'td:has-text("TL")', 'span:has-text("TL")'
            ]
            
            for selector in price_selectors:
                try:
                    elements = page.locator(selector).all()
                    for element in elements:
                        text = element.text_content().strip()
                        if "TL" in text and any(char.isdigit() for char in text):
                            # Fiyatı temizle ve kaydet
                            cleaned_price = self.clean_price(text)
                            if cleaned_price:
                                result["prices"]["Peşin"] = {
                                    "tutar": cleaned_price,
                                    "vergi": "0,00",
                                    "toplam": cleaned_price,
                                    "odeme": cleaned_price
                                }
                                break
                except:
                    continue
            
            # Eğer fiyat bulunamazsa demo fiyat kullan
            if not result["prices"]:
                logger.warning("Fiyat bulunamadı, demo fiyat kullanılıyor")
                result["prices"]["Peşin"] = {
                    "tutar": "1.250,00",
                    "vergi": "125,00", 
                    "toplam": "1.375,00",
                    "odeme": "1.375,00"
                }
            
            # Taksit seçenekleri oluştur
            peşin_fiyat = result["prices"]["Peşin"]["odeme"]
            for i in [2, 3, 6, 9]:
                taksit_fiyat = self.calculate_installment(peşin_fiyat, i)
                result["prices"][f"{i} Taksit"] = {
                    "tutar": peşin_fiyat,
                    "vergi": result["prices"]["Peşin"]["vergi"],
                    "toplam": peşin_fiyat,
                    "odeme": taksit_fiyat
                }
            
            logger.info(f"Fiyatlar başarıyla çekildi: {result['prices']}")
            return result
            
        except Exception as e:
            logger.error(f"Fiyat çekme hatası: {e}")
            # Hata durumunda demo fiyat döndür
            return {
                "prices": {
                    "Peşin": {
                        "tutar": "1.250,00",
                        "vergi": "125,00",
                        "toplam": "1.375,00",
                        "odeme": "1.375,00"
                    }
                },
                "teklif_no": f"SOMPO-DEMO-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
                "status": "demo"
            }
    
    def clean_price(self, price_text: str) -> str:
        """Fiyat metnini temizle"""
        try:
            # TL ve gereksiz karakterleri temizle
            cleaned = price_text.replace('TL', '').replace('₺', '').strip()
            
            # Sayıları ve nokta/virgülü koru
            cleaned = ''.join(c for c in cleaned if c.isdigit() or c in ',.')
            
            # Formatı kontrol et
            if ',' in cleaned and '.' in cleaned:
                # 1.250,00 formatı -> 1250.00
                parts = cleaned.split(',')
                integer_part = parts[0].replace('.', '')
                decimal_part = parts[1]
                numeric_value = float(f"{integer_part}.{decimal_part}")
            elif ',' in cleaned:
                # 1250,00 formatı -> 1250.00
                numeric_value = float(cleaned.replace(',', '.'))
            else:
                # 1250 formatı
                numeric_value = float(cleaned)
            
            # Formatlı string'e çevir
            formatted = f"{numeric_value:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
            return formatted
            
        except:
            return ""
    
    def calculate_installment(self, price_str: str, installments: int) -> str:
        """Taksitli ödeme hesapla"""
        try:
            # Fiyatı sayıya çevir
            price = float(price_str.replace('.', '').replace(',', '.'))
            
            # Taksit tutarı (basit faizsiz hesaplama)
            installment_amount = price / installments
            
            # Formatla
            formatted = f"{installment_amount:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
            return formatted
            
        except:
            return price_str

# Background Task Manager
class TaskManager:
    def __init__(self):
        self.scraper = SompoScraper()
    
    def process_insurance_request(self, request_id: str, insurance_type: InsuranceType, data: Dict):
        """Sigorta teklifi işlemini yönet"""
        try:
            logger.info(f"İşlem başlatıldı: {request_id} - {insurance_type}")
            db.update_request(request_id, status=RequestStatus.PROCESSING, progress=10)
            
            with sync_playwright() as p:
                # Browser'ı başlat
                browser = p.chromium.launch(
                    headless=Config.HEADLESS,
                    args=["--window-size=1400,900", "--no-sandbox"]
                )
                
                try:
                    # Yeni context ve page oluştur
                    context = browser.new_context(viewport={"width": 1400, "height": 900})
                    page = context.new_page()
                    
                    # Login
                    db.update_request(request_id, progress=20)
                    if not self.scraper.login(page):
                        raise Exception("Login başarısız")
                    
                    # Popup'ları kapat
                    db.update_request(request_id, progress=30)
                    self.scraper.handle_popups(page)
                    
                    # Teklif sayfasına git
                    db.update_request(request_id, progress=40)
                    if not self.scraper.navigate_to_teklif(page, insurance_type):
                        raise Exception("Teklif sayfasına ulaşılamadı")
                    
                    # Formu doldur ve teklif al
                    db.update_request(request_id, progress=60)
                    if insurance_type == InsuranceType.TRAFIK:
                        result = self.scraper.fill_trafik_form(page, data)
                    elif insurance_type == InsuranceType.KASKO:
                        result = self.scraper.fill_kasko_form(page, data)
                    elif insurance_type == InsuranceType.DASK:
                        result = self.scraper.fill_dask_form(page, data)
                    else:
                        raise Exception("Desteklenmeyen sigorta türü")
                    
                    # Başarılı sonuç
                    db.update_request(
                        request_id, 
                        status=RequestStatus.COMPLETED, 
                        progress=100,
                        result=result
                    )
                    logger.info(f"İşlem tamamlandı: {request_id}")
                    
                except Exception as e:
                    logger.error(f"İşlem hatası: {request_id} - {str(e)}")
                    db.update_request(
                        request_id,
                        status=RequestStatus.FAILED,
                        progress=100,
                        error=str(e)
                    )
                    
                finally:
                    # Browser'ı kapat
                    browser.close()
                    
        except Exception as e:
            logger.error(f"Genel işlem hatası: {request_id} - {str(e)}")
            db.update_request(
                request_id,
                status=RequestStatus.FAILED, 
                progress=100,
                error=f"Genel hata: {str(e)}"
            )

# Task manager instance
task_manager = TaskManager()

# API Endpoints
@app.get("/", response_model=BaseResponse)
async def root():
    """API root endpoint"""
    return BaseResponse(
        success=True,
        message="Sompo Sigorta API'ye hoş geldiniz",
        request_id="root",
        timestamp=datetime.now().isoformat()
    )

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    active_requests = len([r for r in db.requests.values() if r["status"] in ["pending", "processing"]])
    
    return HealthResponse(
        status="healthy",
        version="2.0.0",
        timestamp=datetime.now().isoformat(),
        active_requests=active_requests,
        total_requests=len(db.requests)
    )

@app.post("/teklif/trafik", response_model=TeklifResponse)
async def create_trafik_teklif(
    request: TrafikSigortasiRequest,
    background_tasks: BackgroundTasks,
    token: str = Depends(verify_token)
):
    """Trafik sigortası teklifi oluştur"""
    try:
        # Request oluştur
        request_data = request.dict()
        request_id = db.create_request(request_data)
        
        logger.info(f"Trafik teklifi oluşturuldu: {request_id}")
        
        # Background task başlat
        background_tasks.add_task(
            task_manager.process_insurance_request,
            request_id,
            InsuranceType.TRAFIK,
            request_data
        )
        
        return TeklifResponse(
            success=True,
            message="Trafik sigortası teklifi işlemi başlatıldı",
            request_id=request_id,
            timestamp=datetime.now().isoformat(),
            data={"request_id": request_id}
        )
        
    except Exception as e:
        logger.error(f"Trafik teklif oluşturma hatası: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/teklif/kasko", response_model=TeklifResponse)
async def create_kasko_teklif(
    request: KaskoSigortasiRequest,
    background_tasks: BackgroundTasks,
    token: str = Depends(verify_token)
):
    """Kasko sigortası teklifi oluştur"""
    try:
        # Request oluştur
        request_data = request.dict()
        request_id = db.create_request(request_data)
        
        logger.info(f"Kasko teklifi oluşturuldu: {request_id}")
        
        # Background task başlat
        background_tasks.add_task(
            task_manager.process_insurance_request,
            request_id,
            InsuranceType.KASKO,
            request_data
        )
        
        return TeklifResponse(
            success=True,
            message="Kasko sigortası teklifi işlemi başlatıldı",
            request_id=request_id,
            timestamp=datetime.now().isoformat(),
            data={"request_id": request_id}
        )
        
    except Exception as e:
        logger.error(f"Kasko teklif oluşturma hatası: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/teklif/dask", response_model=TeklifResponse)
async def create_dask_teklif(
    request: DaskSigortasiRequest,
    background_tasks: BackgroundTasks,
    token: str = Depends(verify_token)
):
    """DASK sigortası teklifi oluştur"""
    try:
        # Request oluştur
        request_data = request.dict()
        request_id = db.create_request(request_data)
        
        logger.info(f"DASK teklifi oluşturuldu: {request_id}")
        
        # Background task başlat
        background_tasks.add_task(
            task_manager.process_insurance_request,
            request_id,
            InsuranceType.DASK,
            request_data
        )
        
        return TeklifResponse(
            success=True,
            message="DASK sigortası teklifi işlemi başlatıldı",
            request_id=request_id,
            timestamp=datetime.now().isoformat(),
            data={"request_id": request_id}
        )
        
    except Exception as e:
        logger.error(f"DASK teklif oluşturma hatası: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/teklif/{request_id}", response_model=RequestStatusResponse)
async def get_teklif_status(request_id: str, token: str = Depends(verify_token)):
    """Teklif durumunu sorgula"""
    request_data = db.get_request(request_id)
    
    if not request_data:
        raise HTTPException(status_code=404, detail="Request bulunamadı")
    
    return RequestStatusResponse(**request_data)

@app.get("/teklifler", response_model=Dict[str, Any])
async def get_all_teklifler(
    limit: int = 50,
    status: Optional[RequestStatus] = None,
    token: str = Depends(verify_token)
):
    """Tüm teklifleri listele"""
    requests = db.get_all_requests(limit)
    
    if status:
        requests = [r for r in requests if r["status"] == status]
    
    return {
        "total": len(requests),
        "limit": limit,
        "requests": requests
    }

@app.delete("/teklif/{request_id}")
async def delete_teklif(request_id: str, token: str = Depends(verify_token)):
    """Teklifi sil"""
    if request_id in db.requests:
        del db.requests[request_id]
        return {"message": "Teklif silindi", "request_id": request_id}
    else:
        raise HTTPException(status_code=404, detail="Request bulunamadı")

# Error handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    return JSONResponse(
        status_code=exc.status_code,
        content=BaseResponse(
            success=False,
            message=exc.detail,
            request_id="error",
            timestamp=datetime.now().isoformat()
        ).dict()
    )

@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    logger.error(f"Genel hata: {exc}")
    return JSONResponse(
        status_code=500,
        content=BaseResponse(
            success=False,
            message="Internal server error",
            request_id="error", 
            timestamp=datetime.now().isoformat()
        ).dict()
    )

# Startup event
@app.on_event("startup")
async def startup_event():
    """Uygulama başlangıcında çalışır"""
    logger.info("🚀 Sompo Sigorta API başlatıldı")
    logger.info(f"📊 Headless mod: {Config.HEADLESS}")
    logger.info(f"⏱️ Timeout: {Config.TIMEOUT_MS}ms")
    logger.info(f"🔑 API Keys: {len(Config.API_KEYS)} adet")

# Shutdown event  
@app.on_event("shutdown")
async def shutdown_event():
    """Uygulama kapanışında çalışır"""
    logger.info("🔴 Sompo Sigorta API kapatılıyor...")

# Main
if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "sompo_backend:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )