# backend.py
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
import uvicorn
import asyncio
import logging
from datetime import datetime
import uuid
from enum import Enum
from fastapi.middleware.cors import CORSMiddleware


# Logging konfigürasyonu
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Scraper modülünü import et
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'scrapers_event'))
from sompo_event import *

app = FastAPI(
    title="Sompo Sigorta API",
    description="Sompo Sigorta otomasyon sistemi için REST API",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Durum takibi için global değişken
active_sessions = {}

# Request modelleri
class InsuranceType(str, Enum):
    TRAFIK = "trafik"
    KASKO = "kasko"
    SAGLIK = "saglik"
    DASK_YENILEME = "dask_yenileme"
    DASK_YENI = "dask_yeni"

class BaseInsuranceRequest(BaseModel):
    tckn: str = Field(..., description="TC Kimlik Numarası")
    email: str = Field(..., description="E-posta adresi")
    dogum_tarihi: Optional[str] = Field(None, description="Doğum tarihi (GG/AA/YYYY)")
    telefon: Optional[str] = Field(None, description="Telefon numarası")

class TrafikSigortasiRequest(BaseInsuranceRequest):
    plaka: str = Field(..., description="Araç plakası")
    ruhsat_seri_no: str = Field(..., description="Ruhsat seri numarası")
    arac_marka: str = Field(..., description="Araç markası")
    arac_modeli: str = Field(..., description="Araç modeli")

class KaskoSigortasiRequest(BaseInsuranceRequest):
    plaka: str = Field(..., description="Araç plakası")
    ruhsat_seri_no: str = Field(..., description="Ruhsat seri numarası")
    arac_marka: str = Field(..., description="Araç markası")
    arac_modeli: Optional[str] = Field(None, description="Araç modeli")
    meslek: str = Field(..., description="Meslek bilgisi")

class SaglikSigortasiRequest(BaseInsuranceRequest):
    prim_tipi: str = Field(..., description="Prim tipi (TAM SENLİK-YATARAK+AYAKTA TEDAVİ vb.)")
    meslek_saglik: str = Field(..., description="Meslek bilgisi")
    teminat_sayisi: int = Field(..., description="Teminat sayısı (3, 5, 7, 10, 12)")

class DaskYenilemeRequest(BaseInsuranceRequest):
    dask_police_no: str = Field(..., description="DASK poliçe numarası")

class DaskYeniRequest(BaseInsuranceRequest):
    dask_adres_kodu: str = Field(..., description="DASK adres kodu (UAVT)")

# Response modelleri
class ApiResponse(BaseModel):
    success: bool
    message: str
    request_id: str
    timestamp: str
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

class SessionStatus(BaseModel):
    request_id: str
    status: str
    progress: int
    start_time: str
    end_time: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

# Yardımcı fonksiyonlar
def generate_request_id():
    return str(uuid.uuid4())

def update_session_status(request_id: str, status: str, progress: int = 0, 
                         result: Dict[str, Any] = None, error: str = None):
    if request_id in active_sessions:
        active_sessions[request_id].update({
            'status': status,
            'progress': progress,
            'end_time': datetime.now().isoformat() if status in ['completed', 'failed'] else None,
            'result': result,
            'error': error
        })

def run_sync_scraper(insurance_type: InsuranceType, data: Dict[str, Any], request_id: str):
    """Senkron scraper fonksiyonlarını çalıştır"""
    try:
        logger.info(f"Scraper başlatılıyor: {insurance_type}, Request ID: {request_id}")
        
        # Playwright bağlamını oluştur
        p = sync_playwright().start()
        browser = p.chromium.launch(headless=False, args=["--window-size=1400,1000"])
        
        context = None
        page = None
        
        try:
            # Giriş yap
            update_session_status(request_id, "logging_in", 20)
            context = browser.new_context()
            page = context.new_page()
            success = login_and_save(page)
            
            if not success:
                update_session_status(request_id, "failed", 100, error="Giriş başarısız")
                return
            
            # Pop-up'ları kapat
            update_session_status(request_id, "handling_popups", 30)
            handle_popups(page)
            
            # Yeni teklif sayfasını aç
            update_session_status(request_id, "opening_offer_page", 40)
            new_page = open_new_offer_page(page)
            
            if not new_page:
                update_session_status(request_id, "failed", 100, error="Yeni teklif sayfası açılamadı")
                return
            
            page = new_page
            
            # Sigorta türüne göre işlem yap
            update_session_status(request_id, "processing_insurance", 60)
            
            if insurance_type == InsuranceType.TRAFIK:
                result = process_trafik_sigortasi(page, data)
            elif insurance_type == InsuranceType.KASKO:
                result = process_kasko_sigortasi(page, data)
            elif insurance_type == InsuranceType.SAGLIK:
                result = process_saglik_sigortasi(page, data)
            elif insurance_type == InsuranceType.DASK_YENILEME:
                result = process_dask_sigortasi(page, data)
            elif insurance_type == InsuranceType.DASK_YENI:
                result = process_dask_yeni_police(page, data)
            else:
                update_session_status(request_id, "failed", 100, error="Geçersiz sigorta türü")
                return
            
            # Sonuçları işle
            update_session_status(request_id, "completed", 100, result=result)
            logger.info(f"Scraper başarıyla tamamlandı: {request_id}")
            
        except Exception as e:
            error_msg = f"Scraper hatası: {str(e)}"
            logger.error(error_msg)
            update_session_status(request_id, "failed", 100, error=error_msg)
            
        finally:
            # Tarayıcıyı kapat
            if browser:
                browser.close()
            if p:
                p.stop()
                
    except Exception as e:
        error_msg = f"Scraper başlatma hatası: {str(e)}"
        logger.error(error_msg)
        update_session_status(request_id, "failed", 100, error=error_msg)

# API Endpoint'leri
@app.get("/")
async def root():
    return {"message": "Sompo Sigorta API'ye hoş geldiniz", "status": "active"}

@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

@app.post("/teklif/trafik", response_model=ApiResponse)
async def create_trafik_teklif(request: TrafikSigortasiRequest, background_tasks: BackgroundTasks):
    """Trafik sigortası teklifi oluştur"""
    request_id = generate_request_id()
    
    # Session'ı başlat
    active_sessions[request_id] = {
        'status': 'initialized',
        'progress': 0,
        'start_time': datetime.now().isoformat(),
        'end_time': None,
        'result': None,
        'error': None
    }
    
    # Background task olarak scraper'ı başlat
    data = request.dict()
    background_tasks.add_task(
        run_sync_scraper, 
        InsuranceType.TRAFIK, 
        data, 
        request_id
    )
    
    return ApiResponse(
        success=True,
        message="Trafik sigortası teklifi işlemi başlatıldı",
        request_id=request_id,
        timestamp=datetime.now().isoformat()
    )

@app.post("/teklif/kasko", response_model=ApiResponse)
async def create_kasko_teklif(request: KaskoSigortasiRequest, background_tasks: BackgroundTasks):
    """Kasko sigortası teklifi oluştur"""
    request_id = generate_request_id()
    
    # Session'ı başlat
    active_sessions[request_id] = {
        'status': 'initialized',
        'progress': 0,
        'start_time': datetime.now().isoformat(),
        'end_time': None,
        'result': None,
        'error': None
    }
    
    # Background task olarak scraper'ı başlat
    data = request.dict()
    background_tasks.add_task(
        run_sync_scraper, 
        InsuranceType.KASKO, 
        data, 
        request_id
    )
    
    return ApiResponse(
        success=True,
        message="Kasko sigortası teklifi işlemi başlatıldı",
        request_id=request_id,
        timestamp=datetime.now().isoformat()
    )

@app.post("/teklif/saglik", response_model=ApiResponse)
async def create_saglik_teklif(request: SaglikSigortasiRequest, background_tasks: BackgroundTasks):
    """Sağlık sigortası teklifi oluştur"""
    request_id = generate_request_id()
    
    # Session'ı başlat
    active_sessions[request_id] = {
        'status': 'initialized',
        'progress': 0,
        'start_time': datetime.now().isoformat(),
        'end_time': None,
        'result': None,
        'error': None
    }
    
    # Background task olarak scraper'ı başlat
    data = request.dict()
    background_tasks.add_task(
        run_sync_scraper, 
        InsuranceType.SAGLIK, 
        data, 
        request_id
    )
    
    return ApiResponse(
        success=True,
        message="Sağlık sigortası teklifi işlemi başlatıldı",
        request_id=request_id,
        timestamp=datetime.now().isoformat()
    )

@app.post("/teklif/dask/yenileme", response_model=ApiResponse)
async def create_dask_yenileme_teklif(request: DaskYenilemeRequest, background_tasks: BackgroundTasks):
    """DASK yenileme teklifi oluştur"""
    request_id = generate_request_id()
    
    # Session'ı başlat
    active_sessions[request_id] = {
        'status': 'initialized',
        'progress': 0,
        'start_time': datetime.now().isoformat(),
        'end_time': None,
        'result': None,
        'error': None
    }
    
    # Background task olarak scraper'ı başlat
    data = request.dict()
    background_tasks.add_task(
        run_sync_scraper, 
        InsuranceType.DASK_YENILEME, 
        data, 
        request_id
    )
    
    return ApiResponse(
        success=True,
        message="DASK yenileme teklifi işlemi başlatıldı",
        request_id=request_id,
        timestamp=datetime.now().isoformat()
    )

@app.post("/teklif/dask/yeni", response_model=ApiResponse)
async def create_dask_yeni_teklif(request: DaskYeniRequest, background_tasks: BackgroundTasks):
    """Yeni DASK teklifi oluştur"""
    request_id = generate_request_id()
    
    # Session'ı başlat
    active_sessions[request_id] = {
        'status': 'initialized',
        'progress': 0,
        'start_time': datetime.now().isoformat(),
        'end_time': None,
        'result': None,
        'error': None
    }
    
    # Background task olarak scraper'ı başlat
    data = request.dict()
    background_tasks.add_task(
        run_sync_scraper, 
        InsuranceType.DASK_YENI, 
        data, 
        request_id
    )
    
    return ApiResponse(
        success=True,
        message="Yeni DASK teklifi işlemi başlatıldı",
        request_id=request_id,
        timestamp=datetime.now().isoformat()
    )

@app.get("/durum/{request_id}", response_model=SessionStatus)
async def get_teklif_durumu(request_id: str):
    """Teklif oluşturma durumunu sorgula"""
    if request_id not in active_sessions:
        raise HTTPException(status_code=404, detail="Request ID bulunamadı")
    
    session_data = active_sessions[request_id]
    return SessionStatus(
        request_id=request_id,
        status=session_data['status'],
        progress=session_data['progress'],
        start_time=session_data['start_time'],
        end_time=session_data['end_time'],
        result=session_data['result'],
        error=session_data['error']
    )

@app.get("/aktif-istekler")
async def get_aktif_istekler():
    """Aktif tüm istekleri listele"""
    return {
        "active_requests": len([s for s in active_sessions.values() if s['status'] not in ['completed', 'failed']]),
        "total_requests": len(active_sessions),
        "requests": active_sessions
    }

@app.delete("/istek/{request_id}")
async def delete_istek(request_id: str):
    """İsteği sil"""
    if request_id in active_sessions:
        del active_sessions[request_id]
        return {"message": "İstek silindi", "request_id": request_id}
    else:
        raise HTTPException(status_code=404, detail="Request ID bulunamadı")

# Hata yönetimi
@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    return JSONResponse(
        status_code=exc.status_code, 
        content=ApiResponse(
            success=False,
            message="Hata oluştu",
            request_id="",
            timestamp=datetime.now().isoformat(),
            error=exc.detail
        ).dict()
    )

if __name__ == "__main__":
    uvicorn.run(
        "sompo_backend:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )