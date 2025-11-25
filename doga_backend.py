# backend.py
from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
import asyncio
import threading
from scrapers_event.doga_scraper import DogaScraper
import uuid
import time
from enum import Enum
import json

app = FastAPI(title="Doğa Sigorta Scraper API", version="1.0.0")

# Durum takibi için in-memory storage
class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"

jobs = {}

class JobResult(BaseModel):
    job_id: str
    status: JobStatus
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    created_at: float
    completed_at: Optional[float] = None
    premium_data: Optional[Dict[str, str]] = None

class KaskoRequest(BaseModel):
    tc_no: str = Field(..., description="TC Kimlik No")
    birth_date: str = Field(..., description="Doğum tarihi (YYYY-MM-DD)")
    plate_code: str = Field(..., description="Plaka il kodu (örn: '06')")
    plate_no: str = Field(..., description="Plaka no (örn: 'HT203')")
    tescil_seri_kod: str = Field(..., description="Tescil seri kod (örn: 'ER')")
    tescil_seri_no: str = Field(..., description="Tescil seri no (örn: '993016')")

class TrafikRequest(BaseModel):
    tc_no: str = Field(..., description="TC Kimlik No")
    birth_date: str = Field(..., description="Doğum tarihi (YYYY-MM-DD)")
    plate_code: str = Field(..., description="Plaka il kodu (örn: '06')")
    plate_no: str = Field(..., description="Plaka no (örn: 'HT203')")
    tescil_seri_kod: str = Field(..., description="Tescil seri kod (örn: 'ER')")
    tescil_seri_no: str = Field(..., description="Tescil seri no (örn: '993016')")

class PremiumData(BaseModel):
    net_prim: Optional[str] = None
    ysv: Optional[str] = None
    gv: Optional[str] = None
    ghp: Optional[str] = None
    thgf: Optional[str] = None
    brut_prim: Optional[str] = None
    komisyon: Optional[str] = None
    ek_komisyon: Optional[str] = None

def run_kasko_scraper(job_id: str, kasko_data: dict):
    """Kasko scraper'ını thread içinde çalıştır"""
    try:
        jobs[job_id].status = JobStatus.RUNNING
        
        scraper = DogaScraper()
        
        # Scraper'ı çalıştır ve premium verilerini al
        result = scraper.run_with_data("kasko", kasko_data)
        
        jobs[job_id].status = JobStatus.COMPLETED
        jobs[job_id].result = {"success": True, "message": "Kasko teklifi alındı"}
        jobs[job_id].premium_data = result.get("premium_data") if result else None
        jobs[job_id].completed_at = time.time()
        
    except Exception as e:
        jobs[job_id].status = JobStatus.FAILED
        jobs[job_id].error = str(e)
        jobs[job_id].completed_at = time.time()

def run_trafik_scraper(job_id: str, trafik_data: dict):
    """Trafik scraper'ını thread içinde çalıştır"""
    try:
        jobs[job_id].status = JobStatus.RUNNING
        
        scraper = DogaScraper()
        
        # Scraper'ı çalıştır ve premium verilerini al
        result = scraper.run_with_data("trafik", trafik_data)
        
        jobs[job_id].status = JobStatus.COMPLETED
        jobs[job_id].result = {"success": True, "message": "Trafik teklifi alındı"}
        jobs[job_id].premium_data = result.get("premium_data") if result else None
        jobs[job_id].completed_at = time.time()
        
    except Exception as e:
        jobs[job_id].status = JobStatus.FAILED
        jobs[job_id].error = str(e)
        jobs[job_id].completed_at = time.time()

# DogaScraper sınıfına yardımcı metod ekleme (patch gibi)
def setup_scraper_methods():
    """Scraper sınıfına gerekli metodları ekle"""
    original_run = DogaScraper.run
    
    def run_with_data(self, scraper_type, data):
        """Veri ile scraper çalıştır"""
        browser = None
        context = None
        page = None
        
        try:
            from playwright.sync_api import sync_playwright
            
            with sync_playwright() as p:
                # Browser başlat
                browser = p.chromium.launch(headless=self.headless)
                context = browser.new_context()
                page = context.new_page()
                page.set_default_timeout(self.timeout)
                
                # Login sayfasına git
                page.goto(self.login_url, wait_until="networkidle")
                
                # Giriş yap
                self._login(page)
                
                # TOTP doğrulaması yap
                self._verify_totp(page)
                
                # Scraper tipine göre işlem yap
                if scraper_type == "kasko":
                    premium_data = self.get_kasko_quote(page, data)
                elif scraper_type == "trafik":
                    premium_data = self.get_trafik_quote(page, data)
                else:
                    raise ValueError(f"Geçersiz scraper tipi: {scraper_type}")
                
                return {"premium_data": premium_data}
                
        except Exception as e:
            print(f"[ERROR] Scraper çalıştırılırken hata: {e}")
            raise
        finally:
            if page:
                page.close()
            if context:
                context.close()
            if browser:
                browser.close()
    
    # Metodu sınıfa ekle
    DogaScraper.run_with_data = run_with_data
    
    # Premium veri çekme metodunu da ekle/güncelle
    def _extract_premium_values_for_api(self, page):
        """API için premium verilerini çek"""
        try:
            premium_data = self._extract_premium_values(page)
            
            # Verileri standart formata dönüştür
            formatted_data = {}
            if premium_data:
                formatted_data = {
                    "net_prim": premium_data.get("Net Prim"),
                    "ysv": premium_data.get("YSV"),
                    "gv": premium_data.get("G.V."),
                    "ghp": premium_data.get("GHP"),
                    "thgf": premium_data.get("THGF"),
                    "brut_prim": premium_data.get("Brüt Prim"),
                    "komisyon": premium_data.get("Komisyon"),
                    "ek_komisyon": premium_data.get("Ek Komisyon")
                }
            
            return formatted_data
            
        except Exception as e:
            print(f"[ERROR] Premium verileri çekilirken hata: {e}")
            return {}
    
    DogaScraper._extract_premium_values_for_api = _extract_premium_values_for_api

# API başlatıldığında scraper metodlarını kur
setup_scraper_methods()

@app.get("/")
async def root():
    return {
        "message": "Doğa Sigorta Scraper API", 
        "status": "running",
        "version": "1.0.0"
    }

@app.post("/kasko-teklifi", response_model=dict)
async def kasko_teklifi_al(request: KaskoRequest, background_tasks: BackgroundTasks):
    """Kasko sigortası teklifi al"""
    job_id = str(uuid.uuid4())
    
    jobs[job_id] = JobResult(
        job_id=job_id,
        status=JobStatus.PENDING,
        created_at=time.time()
    )
    
    # Background task olarak scraper'ı başlat
    background_tasks.add_task(
        run_kasko_scraper,
        job_id,
        request.dict()
    )
    
    return {
        "job_id": job_id,
        "status": "started",
        "message": "Kasko sigortası teklifi alınıyor...",
        "data": request.dict()
    }

@app.post("/trafik-teklifi", response_model=dict)
async def trafik_teklifi_al(request: TrafikRequest, background_tasks: BackgroundTasks):
    """Trafik sigortası teklifi al"""
    job_id = str(uuid.uuid4())
    
    jobs[job_id] = JobResult(
        job_id=job_id,
        status=JobStatus.PENDING,
        created_at=time.time()
    )
    
    # Background task olarak scraper'ı başlat
    background_tasks.add_task(
        run_trafik_scraper,
        job_id,
        request.dict()
    )
    
    return {
        "job_id": job_id,
        "status": "started",
        "message": "Trafik sigortası teklifi alınıyor...",
        "data": request.dict()
    }

@app.get("/job/{job_id}", response_model=JobResult)
async def get_job_status(job_id: str):
    """İş durumunu sorgula"""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job bulunamadı")
    
    return jobs[job_id]

@app.get("/jobs")
async def list_jobs():
    """Tüm işleri listele"""
    return {
        "total_jobs": len(jobs),
        "jobs": {
            job_id: {
                "job_id": job.job_id,
                "status": job.status,
                "created_at": job.created_at,
                "completed_at": job.completed_at,
                "has_premium_data": job.premium_data is not None
            }
            for job_id, job in jobs.items()
        }
    }

@app.get("/job/{job_id}/premium")
async def get_job_premium_data(job_id: str):
    """İşin premium verilerini getir"""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job bulunamadı")
    
    job = jobs[job_id]
    
    if job.status != JobStatus.COMPLETED:
        raise HTTPException(status_code=400, detail="Job henüz tamamlanmadı")
    
    if not job.premium_data:
        raise HTTPException(status_code=404, detail="Premium veri bulunamadı")
    
    return {
        "job_id": job_id,
        "premium_data": job.premium_data
    }

@app.delete("/job/{job_id}")
async def delete_job(job_id: str):
    """İşi sil"""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job bulunamadı")
    
    del jobs[job_id]
    return {"message": "Job silindi"}

@app.delete("/jobs")
async def clear_all_jobs():
    """Tüm işleri temizle"""
    count = len(jobs)
    jobs.clear()
    return {"message": f"{count} job temizlendi"}

@app.get("/health")
async def health_check():
    """Sağlık kontrolü"""
    return {
        "status": "healthy", 
        "timestamp": time.time(),
        "active_jobs": len([j for j in jobs.values() if j.status == JobStatus.RUNNING])
    }

@app.get("/premium-fields")
async def get_premium_fields():
    """Premium veri alanlarını listele"""
    return {
        "premium_fields": [
            {"key": "net_prim", "label": "Net Prim", "description": "Net prim tutarı"},
            {"key": "ysv", "label": "YSV", "description": "Yangın Sigortaları Vergisi"},
            {"key": "gv", "label": "G.V.", "description": "Gider Vergisi"},
            {"key": "ghp", "label": "GHP", "description": "Gelir Hedefi Primi"},
            {"key": "thgf", "label": "THGF", "description": "Trafik Hesap Garanti Fonu"},
            {"key": "brut_prim", "label": "Brüt Prim", "description": "Brüt prim tutarı"},
            {"key": "komisyon", "label": "Komisyon", "description": "Komisyon tutarı"},
            {"key": "ek_komisyon", "label": "Ek Komisyon", "description": "Ek komisyon tutarı"}
        ]
    }

# Örnek veri endpoint'leri
@app.get("/example/kasko")
async def get_kasko_example():
    """Kasko için örnek veri"""
    return {
        "example": {
            "tc_no": "32083591236",
            "birth_date": "1965-03-10",
            "plate_code": "06",
            "plate_no": "HT203",
            "tescil_seri_kod": "ER",
            "tescil_seri_no": "993016"
        }
    }

@app.get("/example/trafik")
async def get_trafik_example():
    """Trafik için örnek veri"""
    return {
        "example": {
            "tc_no": "32083591236",
            "birth_date": "1965-03-10",
            "plate_code": "06",
            "plate_no": "HT203",
            "tescil_seri_kod": "ER",
            "tescil_seri_no": "993016"
        }
    }

if __name__ == "__main__":
    import uvicorn
    import os
    from dotenv import load_dotenv
    load_dotenv()
    port = int(os.getenv("DOGA_BACKEND_PORT", "8001"))
    uvicorn.run("doga_backend:app", host="0.0.0.0", port=port, reload=True)