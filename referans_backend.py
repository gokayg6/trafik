# backend_referans.py

import sys
import os
import json
import time
import traceback
from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
import uvicorn
import asyncio
import logging
from datetime import datetime
import uuid
from enum import Enum

# Logging konfigürasyonu
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Scraper modülünü import et
sys.path.append(os.path.join(os.path.dirname(__file__), 'scrapers_event'))
from referans_event import *

app = FastAPI(
    title="Referans Sigorta API",
    description="Referans Sigorta otomasyon sistemi için REST API",
    version="1.0.0"
)

# Durum takibi için global değişken
active_sessions = {}

# Request modelleri
class InsuranceType(str, Enum):
    KASKO = "kasko"
    SAGLIK = "saglik"
    TRAFIK = "trafik"

class BaseInsuranceRequest(BaseModel):
    tc_kimlik: str = Field(..., description="TC Kimlik Numarası")
    email: str = Field(..., description="E-posta adresi")

class KaskoSigortasiRequest(BaseInsuranceRequest):
    plaka: str = Field(..., description="Araç plakası")
    telefon: str = Field(..., description="Telefon numarası")
    tescil_tarihi: str = Field(..., description="Tescil tarihi (YYYY-AA-GG)")
    asbis_no: str = Field(..., description="ASBİS numarası")
    kullanim_cinsi: str = Field(..., description="Kullanım cinsi")
    marka: str = Field(..., description="Araç markası")
    model_yili: str = Field(..., description="Model yılı")
    model: str = Field(..., description="Araç modeli")

class SaglikSigortasiRequest(BaseInsuranceRequest):
    pass  # Sağlık sigortası için ek alan yok

class TrafikSigortasiRequest(BaseInsuranceRequest):
    plaka: str = Field(..., description="Araç plakası")
    telefon: str = Field(..., description="Telefon numarası")
    tescil_tarihi: str = Field(..., description="Tescil tarihi (YYYY-AA-GG)")
    asbis_no: str = Field(..., description="ASBİS numarası")
    kullanim_cinsi: str = Field(..., description="Kullanım cinsi")
    marka: str = Field(..., description="Araç markası")
    model_yili: str = Field(..., description="Model yılı")
    model: str = Field(..., description="Araç modeli")

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
        logger.info(f"Referans scraper başlatılıyor: {insurance_type}, Request ID: {request_id}")
        
        # Playwright bağlamını oluştur
        p = sync_playwright().start()
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
            Object.defineProperty(navigator, 'webdriver', { get: () => false });
            Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
            Object.defineProperty(navigator, 'languages', { get: () => ['tr-TR', 'tr', 'en-US', 'en'] });
        """)
        
        page = context.new_page()
        
        try:
            # Giriş yap
            update_session_status(request_id, "logging_in", 20)
            full_login(page)
            
            # Pop-up'ları kapat
            update_session_status(request_id, "handling_popups", 30)
            handle_popup_if_exists(page)

            # Sigorta türüne göre işlem yap
            update_session_status(request_id, "processing_insurance", 60)
            
            if insurance_type == InsuranceType.KASKO:
                result = create_kasko_teklifi(page, data)
            elif insurance_type == InsuranceType.SAGLIK:
                result = create_tamamlayici_saglik_teklifi(page, data)
            elif insurance_type == InsuranceType.TRAFIK:
                result = create_trafik_teklifi(page, data)
            else:
                update_session_status(request_id, "failed", 100, error="Geçersiz sigorta türü")
                return
            
            # Sonuçları işle
            if result and result.get('durum') and 'başarıyla tamamlandı' in result.get('durum', ''):
                update_session_status(request_id, "completed", 100, result=result)
                logger.info(f"Referans scraper başarıyla tamamlandı: {request_id}")
            else:
                error_msg = result.get('hata', 'Teklif oluşturulamadı')
                update_session_status(request_id, "failed", 100, error=error_msg)
                logger.error(f"Referans scraper başarısız: {error_msg}")
            
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
    return {"message": "Referans Sigorta API'ye hoş geldiniz", "status": "active"}

@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

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
        "referans_backend:app",
        host="0.0.0.0",
        port=8001,
        reload=True,
        log_level="info"
    )