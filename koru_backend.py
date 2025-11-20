# koru_backend.py
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
import logging
import asyncio
import uuid
from datetime import datetime
import os
import sys
import time  # time modülünü import et
from concurrent.futures import ThreadPoolExecutor

# Playwright import'u ekle
from playwright.sync_api import sync_playwright

sys.path.append(os.path.join(os.path.dirname(__file__), 'scrapers_event'))
from scrapers_event.koru_scraper import KoruScraper


# Logging kurulumu
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# FastAPI uygulaması
app = FastAPI(
    title="Koru Sigorta API",
    description="Koru sigorta portalı için otomatik teklif alma API'sı",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Thread pool for blocking operations
thread_pool = ThreadPoolExecutor(max_workers=3)

# Data Modelleri
class TeklifData(BaseModel):
    tc: str = Field(..., description="TC Kimlik No")
    dogum_tarihi: str = Field(..., description="Doğum Tarihi (GG.AA.YYYY)")
    plaka_il: str = Field(..., description="Plaka İl Kodu (örn: 34)")
    plaka_no: str = Field(..., description="Plaka No")
    tescil_kod: str = Field(..., description="Tescil Kod")
    tescil_no: str = Field(..., description="Tescil No")

class TrafikTeklifIstek(BaseModel):
    teklif_data: TeklifData

class KaskoTeklifIstek(BaseModel):
    teklif_data: TeklifData

class TrafikKaskoTeklifIstek(BaseModel):
    teklif_data: TeklifData

class TeklifSonuc(BaseModel):
    sigortali_ad: Optional[str] = None
    teklif_no: Optional[str] = None
    urun_adi: Optional[str] = None
    prim: Optional[str] = None

class ApiResponse(BaseModel):
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None
    request_id: Optional[str] = None
    timestamp: str

class ScraperTask(BaseModel):
    task_id: str
    status: str  # "pending", "running", "completed", "failed"
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    created_at: str
    completed_at: Optional[str] = None

# Global değişkenler
tasks: Dict[str, ScraperTask] = {}

# Yardımcı fonksiyonlar
def get_current_timestamp():
    return datetime.now().isoformat()

def create_task() -> str:
    task_id = str(uuid.uuid4())
    tasks[task_id] = ScraperTask(
        task_id=task_id,
        status="pending",
        created_at=get_current_timestamp()
    )
    return task_id

def update_task_status(task_id: str, status: str, result: Dict = None, error: str = None):
    if task_id in tasks:
        tasks[task_id].status = status
        if result:
            tasks[task_id].result = result
        if error:
            tasks[task_id].error = error
        if status in ["completed", "failed"]:
            tasks[task_id].completed_at = get_current_timestamp()

class HeadlessKoruScraper(KoruScraper):
    """Headless modda çalışacak şekilde override edilmiş scraper"""
    
    def __init__(self):
        super().__init__()
        # HEADLESS modunu environment variable'dan al, yoksa True yap
        self.headless = os.getenv("HEADLESS", "true").lower() == "true"
        logger.info(f"Scraper headless mod: {self.headless}")
    
    def run_trafik_with_data(self, teklif_data: Dict):
        """Trafik sigortası teklifi al"""
        browser = None
        try:
            with sync_playwright() as pw:
                browser = pw.chromium.launch(headless=self.headless)
                context = browser.new_context(viewport={"width": 1366, "height": 900})
                page = context.new_page()

                # Login işlemleri
                page.goto(self.login_url, wait_until="domcontentloaded", timeout=self.timeout_ms)
                
                if not self._validate_selectors(page):
                    logger.warning("Selector doğrulaması başarısız, devam ediliyor...")

                if not self._fill_credentials(page):
                    raise RuntimeError("Kimlik bilgileri girilemedi")

                if not self._click_login_button(page):
                    raise RuntimeError("Login butonu tıklanamadı")

                if not self._handle_totp(page):
                    raise RuntimeError("TOTP doğrulaması başarısız")

                page.wait_for_load_state("domcontentloaded", timeout=self.timeout_ms)
                time.sleep(5)  # Artık time modülü import edildi
                self._close_popups(page)

                # Trafik sigortası teklifi al
                trafik_teklifi = self.create_trafik_sigortasi(page, teklif_data)
                logger.info(f"Trafik teklifi sonucu: {trafik_teklifi}")

                # Tarayıcıyı otomatik kapat
                if browser:
                    browser.close()
                    logger.info("Tarayıcı otomatik kapatıldı")

                return {
                    "trafik": trafik_teklifi
                }
                
        except Exception as e:
            logger.error(f"Trafik sigortası çalıştırma hatası: {e}")
            if browser:
                browser.close()
            return None
    
    def run_kasko_with_data(self, teklif_data: Dict):
        """Kasko sigortası teklifi al"""
        browser = None
        try:
            with sync_playwright() as pw:
                browser = pw.chromium.launch(headless=self.headless)
                context = browser.new_context(viewport={"width": 1366, "height": 900})
                page = context.new_page()

                # Login işlemleri
                page.goto(self.login_url, wait_until="domcontentloaded", timeout=self.timeout_ms)
                
                if not self._validate_selectors(page):
                    logger.warning("Selector doğrulaması başarısız, devam ediliyor...")

                if not self._fill_credentials(page):
                    raise RuntimeError("Kimlik bilgileri girilemedi")

                if not self._click_login_button(page):
                    raise RuntimeError("Login butonu tıklanamadı")

                if not self._handle_totp(page):
                    raise RuntimeError("TOTP doğrulaması başarısız")

                page.wait_for_load_state("domcontentloaded", timeout=self.timeout_ms)
                time.sleep(5)  # Artık time modülü import edildi
                self._close_popups(page)

                # Kasko sigortası teklifi al
                kasko_teklifi = self.create_kasko_sigortasi(page, teklif_data)
                logger.info(f"Kasko teklifi sonucu: {kasko_teklifi}")

                # Tarayıcıyı otomatik kapat
                if browser:
                    browser.close()
                    logger.info("Tarayıcı otomatik kapatıldı")

                return {
                    "kasko": kasko_teklifi
                }
                
        except Exception as e:
            logger.error(f"Kasko sigortası çalıştırma hatası: {e}")
            if browser:
                browser.close()
            return None

    def run_trafik_kasko_with_data(self, teklif_data: Dict):
        """Hem trafik hem kasko sigortası teklifi al"""
        browser = None
        try:
            with sync_playwright() as pw:
                browser = pw.chromium.launch(headless=self.headless)
                context = browser.new_context(viewport={"width": 1366, "height": 900})
                page = context.new_page()

                # Login işlemleri
                page.goto(self.login_url, wait_until="domcontentloaded", timeout=self.timeout_ms)
                
                if not self._validate_selectors(page):
                    logger.warning("Selector doğrulaması başarısız, devam ediliyor...")

                if not self._fill_credentials(page):
                    raise RuntimeError("Kimlik bilgileri girilemedi")

                if not self._click_login_button(page):
                    raise RuntimeError("Login butonu tıklanamadı")

                if not self._handle_totp(page):
                    raise RuntimeError("TOTP doğrulaması başarısız")

                page.wait_for_load_state("domcontentloaded", timeout=self.timeout_ms)
                time.sleep(5)  # Artık time modülü import edildi
                self._close_popups(page)

                # Önce trafik sigortası teklifi al
                trafik_teklifi = self.create_trafik_sigortasi(page, teklif_data)
                logger.info(f"Trafik teklifi sonucu: {trafik_teklifi}")

                # Sonra kasko sigortası teklifi al
                kasko_teklifi = self.create_kasko_sigortasi(page, teklif_data)
                logger.info(f"Kasko teklifi sonucu: {kasko_teklifi}")

                # Tarayıcıyı otomatik kapat
                if browser:
                    browser.close()
                    logger.info("Tarayıcı otomatik kapatıldı")

                return {
                    "trafik": trafik_teklifi,
                    "kasko": kasko_teklifi
                }
                
        except Exception as e:
            logger.error(f"Trafik ve Kasko sigortası çalıştırma hatası: {e}")
            if browser:
                browser.close()
            return None

def run_scraper_with_data(scraper_type: str, teklif_data: Dict, task_id: str) -> Dict[str, Any]:
    """Scraper'ı thread pool'da çalıştır"""
    try:
        logger.info(f"Task {task_id}: {scraper_type} scraper başlatılıyor")
        update_task_status(task_id, "running")
        
        # Headless scraper kullan
        scraper = HeadlessKoruScraper()
        
        if scraper_type == "trafik":
            result = scraper.run_trafik_with_data(teklif_data)
            if result and result.get("trafik"):
                logger.info(f"Task {task_id}: Trafik sigortası başarılı")
                update_task_status(task_id, "completed", result)
                return {"success": True, **result}
            else:
                error_msg = "Trafik sigortası teklifi alınamadı"
                logger.error(f"Task {task_id}: {error_msg}")
                update_task_status(task_id, "failed", error=error_msg)
                return {"success": False, "error": error_msg}
                
        elif scraper_type == "kasko":
            result = scraper.run_kasko_with_data(teklif_data)
            if result and result.get("kasko"):
                logger.info(f"Task {task_id}: Kasko sigortası başarılı")
                update_task_status(task_id, "completed", result)
                return {"success": True, **result}
            else:
                error_msg = "Kasko sigortası teklifi alınamadı"
                logger.error(f"Task {task_id}: {error_msg}")
                update_task_status(task_id, "failed", error=error_msg)
                return {"success": False, "error": error_msg}
                
        elif scraper_type == "trafik_kasko":
            result = scraper.run_trafik_kasko_with_data(teklif_data)
            if result and (result.get("trafik") or result.get("kasko")):
                logger.info(f"Task {task_id}: Trafik ve Kasko sigortası başarılı")
                update_task_status(task_id, "completed", result)
                return {"success": True, **result}
            else:
                error_msg = "Trafik ve Kasko sigortası teklifleri alınamadı"
                logger.error(f"Task {task_id}: {error_msg}")
                update_task_status(task_id, "failed", error=error_msg)
                return {"success": False, "error": error_msg}
            
    except Exception as e:
        error_msg = f"{scraper_type} sigortası hatası: {str(e)}"
        logger.error(f"Task {task_id}: {error_msg}")
        update_task_status(task_id, "failed", error=error_msg)
        return {"success": False, "error": error_msg}

async def run_scraper_in_thread(scraper_type: str, teklif_data: Dict, task_id: str):
    """Scraper'ı thread pool'da çalıştır"""
    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            thread_pool, 
            run_scraper_with_data, 
            scraper_type, teklif_data, task_id
        )
        return result
    except Exception as e:
        logger.error(f"Thread pool hatası: {e}")
        update_task_status(task_id, "failed", error=str(e))
        return {"success": False, "error": str(e)}

# API Endpoint'leri (aynı kaldı)
@app.get("/")
async def root():
    return ApiResponse(
        success=True,
        message="Koru Sigorta API çalışıyor",
        timestamp=get_current_timestamp()
    )

@app.get("/health")
async def health_check():
    return ApiResponse(
        success=True,
        message="API sağlıklı",
        timestamp=get_current_timestamp()
    )

@app.post("/trafik-teklif", response_model=ApiResponse)
async def trafik_teklif_al(istek: TrafikTeklifIstek, background_tasks: BackgroundTasks):
    """Trafik sigortası teklifi al"""
    try:
        task_id = create_task()
        
        # Background task olarak çalıştır - thread pool kullan
        background_tasks.add_task(
            run_scraper_in_thread,
            "trafik",
            istek.teklif_data.dict(),
            task_id
        )
        
        return ApiResponse(
            success=True,
            message="Trafik sigortası teklif işlemi başlatıldı",
            data={"task_id": task_id},
            request_id=task_id,
            timestamp=get_current_timestamp()
        )
        
    except Exception as e:
        logger.error(f"Trafik teklif endpoint hatası: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/kasko-teklif", response_model=ApiResponse)
async def kasko_teklif_al(istek: KaskoTeklifIstek, background_tasks: BackgroundTasks):
    """Kasko sigortası teklifi al"""
    try:
        task_id = create_task()
        
        # Background task olarak çalıştır - thread pool kullan
        background_tasks.add_task(
            run_scraper_in_thread,
            "kasko", 
            istek.teklif_data.dict(),
            task_id
        )
        
        return ApiResponse(
            success=True,
            message="Kasko sigortası teklif işlemi başlatıldı",
            data={"task_id": task_id},
            request_id=task_id,
            timestamp=get_current_timestamp()
        )
        
    except Exception as e:
        logger.error(f"Kasko teklif endpoint hatası: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/trafik-kasko-teklif", response_model=ApiResponse)
async def trafik_kasko_teklif_al(istek: TrafikKaskoTeklifIstek, background_tasks: BackgroundTasks):
    """Hem trafik hem kasko sigortası teklifi al"""
    try:
        task_id = create_task()
        
        # Background task olarak çalıştır - thread pool kullan
        background_tasks.add_task(
            run_scraper_in_thread,
            "trafik_kasko",
            istek.teklif_data.dict(),
            task_id
        )
        
        return ApiResponse(
            success=True,
            message="Trafik ve Kasko sigortası teklif işlemi başlatıldı",
            data={"task_id": task_id},
            request_id=task_id,
            timestamp=get_current_timestamp()
        )
        
    except Exception as e:
        logger.error(f"Trafik-Kasko teklif endpoint hatası: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/task/{task_id}")
async def get_task_status(task_id: str):
    """Task durumunu sorgula"""
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="Task bulunamadı")
    
    task = tasks[task_id]
    
    # Başarı durumunu kontrol et
    success = task.status == "completed" and task.result is not None
    
    return ApiResponse(
        success=success,
        message=f"Task durumu: {task.status}",
        data=task.dict(),
        request_id=task_id,
        timestamp=get_current_timestamp()
    )

@app.get("/tasks")
async def get_all_tasks():
    """Tüm task'ları listele"""
    return ApiResponse(
        success=True,
        message="Tüm task'lar listelendi",
        data={"tasks": {task_id: task.dict() for task_id, task in tasks.items()}},
        timestamp=get_current_timestamp()
    )

@app.delete("/task/{task_id}")
async def delete_task(task_id: str):
    """Task'ı sil"""
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="Task bulunamadı")
    
    del tasks[task_id]
    return ApiResponse(
        success=True,
        message="Task silindi",
        request_id=task_id,
        timestamp=get_current_timestamp()
    )

@app.get("/scraper-info")
async def get_scraper_info():
    """Scraper bilgilerini göster (debug için)"""
    try:
        scraper = HeadlessKoruScraper()
        return ApiResponse(
            success=True,
            message="Scraper bilgileri",
            data={
                "login_url": scraper.login_url,
                "username": scraper.username,
                "headless": scraper.headless,
                "timeout_ms": scraper.timeout_ms,
                "has_totp": bool(scraper.totp_secret)
            },
            timestamp=get_current_timestamp()
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Scraper bilgileri alınamadı: {e}")

# Test endpoint'leri
@app.post("/test-trafik")
async def test_trafik(background_tasks: BackgroundTasks):
    """Test için trafik teklifi al"""
    try:
        task_id = create_task()
        
        test_data = {
            "tc": "32083591236",
            "dogum_tarihi": "10.03.1965",
            "plaka_il": "06",
            "plaka_no": "HT203",
            "tescil_kod": "FC",
            "tescil_no": "993016"
        }
        
        # Background task olarak çalıştır
        background_tasks.add_task(
            run_scraper_in_thread,
            "trafik",
            test_data,
            task_id
        )
        
        return ApiResponse(
            success=True,
            message="Test trafik teklif işlemi başlatıldı",
            data={"task_id": task_id},
            request_id=task_id,
            timestamp=get_current_timestamp()
        )
        
    except Exception as e:
        logger.error(f"Test trafik hatası: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/test-kasko")
async def test_kasko(background_tasks: BackgroundTasks):
    """Test için kasko teklifi al"""
    try:
        task_id = create_task()
        
        test_data = {
            "tc": "32083591236",
            "dogum_tarihi": "10.03.1965",
            "plaka_il": "06",
            "plaka_no": "HT203",
            "tescil_kod": "ER",
            "tescil_no": "993016"
        }
        
        # Background task olarak çalıştır
        background_tasks.add_task(
            run_scraper_in_thread,
            "kasko",
            test_data,
            task_id
        )
        
        return ApiResponse(
            success=True,
            message="Test kasko teklif işlemi başlatıldı",
            data={"task_id": task_id},
            request_id=task_id,
            timestamp=get_current_timestamp()
        )
        
    except Exception as e:
        logger.error(f"Test kasko hatası: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/test-trafik-kasko")
async def test_trafik_kasko(background_tasks: BackgroundTasks):
    """Test için hem trafik hem kasko teklifi al"""
    try:
        task_id = create_task()
        
        test_data = {
            "tc": "32083591236",
            "dogum_tarihi": "10.03.1965",
            "plaka_il": "06",
            "plaka_no": "HT203",
            "tescil_kod": "ER",
            "tescil_no": "993016"
        }
        
        # Background task olarak çalıştır
        background_tasks.add_task(
            run_scraper_in_thread,
            "trafik_kasko",
            test_data,
            task_id
        )
        
        return ApiResponse(
            success=True,
            message="Test trafik-kasko teklif işlemi başlatıldı",
            data={"task_id": task_id},
            request_id=task_id,
            timestamp=get_current_timestamp()
        )
        
    except Exception as e:
        logger.error(f"Test trafik-kasko hatası: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "koru_backend:app",
        host="0.0.0.0",
        port=8003,
        reload=True,
        log_level="info"
    )