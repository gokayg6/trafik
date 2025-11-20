# backend.py
from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
import asyncio
import threading
from scrapers_event.seker_scraper import SekerScraper
import uuid
import time
from enum import Enum

app = FastAPI(title="Şeker Sigorta Scraper API", version="1.0.0")

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

class TrafikSigortasiRequest(BaseModel):
    plaka: str = Field(..., description="Araç plakası")
    tckn: str = Field(..., description="TC Kimlik No")
    tescil: str = Field(..., description="Birleşik tescil numarası")
    kullanim_tarzi: str = Field(..., description="Kullanım tarzı (örn: 'HUSUSİ OTO')")

class KaskoSigortasiRequest(BaseModel):
    plaka: str = Field(..., description="Araç plakası")
    tckn: str = Field(..., description="TC Kimlik No")
    tescil: str = Field(..., description="Birleşik tescil numarası")
    kullanim_tarzi: str = Field(..., description="Kullanım tarzı (örn: 'HUSUSİ OTO')")

class SeyahatSaglikRequest(BaseModel):
    dogum_tarihi: str = Field(..., description="Doğum tarihi (GG.AA.YYYY)")
    tc_no: str = Field(..., description="TC Kimlik No veya Pasaport numarası")
    teminat_bedeli: str = Field(..., description="Teminat bedeli (örn: '30.000 EUR')")
    police_suresi: str = Field(..., description="Poliçe süresi (örn: '1 Ay')")
    cografi_sinirlar: str = Field(..., description="Coğrafi sınırlar (örn: 'Tüm Dünya (Türkiye Hariç)')")

def run_scraper_in_thread(job_id: str, scraper_type: str, **kwargs):
    """Scraper'ı thread içinde çalıştır"""
    try:
        jobs[job_id].status = JobStatus.RUNNING
        
        scraper = SekerScraper()
        
        if scraper_type == "trafik":
            result = scraper.run(trafik_args=kwargs)
        elif scraper_type == "kasko":
            result = scraper.run(kasko_args=kwargs)
        elif scraper_type == "seyahat":
            result = scraper.run(seyahat_args=kwargs)
        else:
            raise ValueError(f"Geçersiz scraper tipi: {scraper_type}")
        
        jobs[job_id].status = JobStatus.COMPLETED
        jobs[job_id].result = result
        jobs[job_id].completed_at = time.time()
        
    except Exception as e:
        jobs[job_id].status = JobStatus.FAILED
        jobs[job_id].error = str(e)
        jobs[job_id].completed_at = time.time()

@app.get("/")
async def root():
    return {"message": "Şeker Sigorta Scraper API", "status": "running"}

@app.post("/trafik-sigortasi", response_model=dict)
async def trafik_sigortasi_teklifi(request: TrafikSigortasiRequest, background_tasks: BackgroundTasks):
    """Trafik sigortası teklifi al"""
    job_id = str(uuid.uuid4())
    
    jobs[job_id] = JobResult(
        job_id=job_id,
        status=JobStatus.PENDING,
        created_at=time.time()
    )
    
    # Background task olarak scraper'ı başlat
    background_tasks.add_task(
        run_scraper_in_thread,
        job_id,
        "trafik",
        **request.dict()
    )
    
    return {
        "job_id": job_id,
        "status": "started",
        "message": "Trafik sigortası teklifi alınıyor..."
    }

@app.post("/kasko-sigortasi", response_model=dict)
async def kasko_sigortasi_teklifi(request: KaskoSigortasiRequest, background_tasks: BackgroundTasks):
    """Kasko sigortası teklifi al"""
    job_id = str(uuid.uuid4())
    
    jobs[job_id] = JobResult(
        job_id=job_id,
        status=JobStatus.PENDING,
        created_at=time.time()
    )
    
    # Background task olarak scraper'ı başlat
    background_tasks.add_task(
        run_scraper_in_thread,
        job_id,
        "kasko",
        **request.dict()
    )
    
    return {
        "job_id": job_id,
        "status": "started",
        "message": "Kasko sigortası teklifi alınıyor..."
    }

@app.post("/seyahat-saglik-sigortasi", response_model=dict)
async def seyahat_saglik_sigortasi_teklifi(request: SeyahatSaglikRequest, background_tasks: BackgroundTasks):
    """Seyahat sağlık sigortası teklifi al"""
    job_id = str(uuid.uuid4())
    
    jobs[job_id] = JobResult(
        job_id=job_id,
        status=JobStatus.PENDING,
        created_at=time.time()
    )
    
    # Background task olarak scraper'ı başlat
    background_tasks.add_task(
        run_scraper_in_thread,
        job_id,
        "seyahat",
        **request.dict()
    )
    
    return {
        "job_id": job_id,
        "status": "started",
        "message": "Seyahat sağlık sigortası teklifi alınıyor..."
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
        "jobs": {
            job_id: job.dict() for job_id, job in jobs.items()
        }
    }

@app.delete("/job/{job_id}")
async def delete_job(job_id: str):
    """İşi sil"""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job bulunamadı")
    
    del jobs[job_id]
    return {"message": "Job silindi"}

@app.get("/health")
async def health_check():
    """Sağlık kontrolü"""
    return {"status": "healthy", "timestamp": time.time()}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend:app", host="0.0.0.0", port=8000, reload=True)