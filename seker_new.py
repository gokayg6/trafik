from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
import uvicorn
import asyncio
import logging
from datetime import datetime
import uuid
from enum import Enum
from fastapi.middleware.cors import CORSMiddleware

# Scraper modülünü import et
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'scrapers_event'))
from scrapers_event.seker_scraper import run_seker_trafik_sigortasi, run_seker_kasko_sigortasi, run_seker_seyahat_saglik_sigortasi

# Logging konfigürasyonu
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Şeker Sigorta API",
    description="Şeker Sigorta otomasyon sistemi için REST API",
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

# Request modelleri - Sompo ile aynı format
class InsuranceType(str, Enum):
    TRAFIK = "trafik"
    KASKO = "kasko"
    SEYAHAT_SAGLIK = "seyahat_saglik"

class BaseInsuranceRequest(BaseModel):
    tckn: str = Field(..., description="TC Kimlik Numarası")
    email: Optional[str] = Field(None, description="E-posta adresi")
    dogum_tarihi: Optional[str] = Field(None, description="Doğum tarihi (GG.AA.YYYY)")
    telefon: Optional[str] = Field(None, description="Telefon numarası")

class TrafikSigortasiRequest(BaseInsuranceRequest):
    plaka: str = Field(..., description="Araç plakası")
    tescil: str = Field(..., description="Birleşik tescil numarası (örn: AB123456)")
    kullanim_tarzi: str = Field(..., description="Kullanım tarzı (örn: HUSUSİ OTO)")

class KaskoSigortasiRequest(BaseInsuranceRequest):
    plaka: str = Field(..., description="Araç plakası")
    tescil: str = Field(..., description="Birleşik tescil numarası (örn: AB123456)")
    kullanim_tarzi: str = Field(..., description="Kullanım tarzı (örn: HUSUSİ OTO)")

class SeyahatSaglikSigortasiRequest(BaseModel):
    tc_no: str = Field(..., description="TC Kimlik No veya Pasaport No")
    dogum_tarihi: str = Field(..., description="Doğum tarihi (GG.AA.YYYY)")
    teminat_bedeli: str = Field(..., description="Teminat bedeli (örn: 30.000 EUR)")
    police_suresi: str = Field(..., description="Poliçe süresi (örn: 1 Ay)")
    cografi_sinirlar: str = Field(..., description="Coğrafi sınırlar (örn: Tüm Dünya (Türkiye Hariç))")

# Response modelleri - Sompo ile aynı format
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

def run_sync_seker_scraper(insurance_type: InsuranceType, data: Dict[str, Any], request_id: str):
    """Şeker Sigorta senkron scraper fonksiyonlarını çalıştır"""
    try:
        logger.info(f"Şeker Sigorta scraper başlatılıyor: {insurance_type}, Request ID: {request_id}")
        
        update_session_status(request_id, "logging_in", 20)
        
        if insurance_type == InsuranceType.TRAFIK:
            result = run_seker_trafik_sigortasi(data)
        elif insurance_type == InsuranceType.KASKO:
            result = run_seker_kasko_sigortasi(data)
        elif insurance_type == InsuranceType.SEYAHAT_SAGLIK:
            result = run_seker_seyahat_saglik_sigortasi(data)
        else:
            update_session_status(request_id, "failed", 100, error="Geçersiz sigorta türü")
            return
        
        if result.get('basarili'):
            update_session_status(request_id, "completed", 100, result=result)
            logger.info(f"Şeker Sigorta scraper başarıyla tamamlandı: {request_id}")
        else:
            update_session_status(request_id, "failed", 100, error=result.get('hata', 'Bilinmeyen hata'))
            
    except Exception as e:
        error_msg = f"Şeker Sigorta scraper hatası: {str(e)}"
        logger.error(error_msg)
        update_session_status(request_id, "failed", 100, error=error_msg)

# API Endpoint'leri - Sompo ile aynı yapı
@app.get("/")
async def root():
    return {"message": "Şeker Sigorta API'ye hoş geldiniz", "status": "active"}

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
        run_sync_seker_scraper, 
        InsuranceType.TRAFIK, 
        data, 
        request_id
    )
    
    return ApiResponse(
        success=True,
        message="Şeker Sigorta trafik sigortası teklifi işlemi başlatıldı",
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
        run_sync_seker_scraper, 
        InsuranceType.KASKO, 
        data, 
        request_id
    )
    
    return ApiResponse(
        success=True,
        message="Şeker Sigorta kasko sigortası teklifi işlemi başlatıldı",
        request_id=request_id,
        timestamp=datetime.now().isoformat()
    )

@app.post("/teklif/seyahat-saglik", response_model=ApiResponse)
async def create_seyahat_saglik_teklif(request: SeyahatSaglikSigortasiRequest, background_tasks: BackgroundTasks):
    """Seyahat sağlık sigortası teklifi oluştur"""
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
        run_sync_seker_scraper, 
        InsuranceType.SEYAHAT_SAGLIK, 
        data, 
        request_id
    )
    
    return ApiResponse(
        success=True,
        message="Şeker Sigorta seyahat sağlık sigortası teklifi işlemi başlatıldı",
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
        "seker_new:app",
        host="0.0.0.0",
        port=8001,  # Sompo'dan farklı port
        reload=True,
        log_level="info"
    )