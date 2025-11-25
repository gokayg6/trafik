"""
Unified Backend API - Tüm sigorta şirketleri için tek API
"""
from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
import os
from dotenv import load_dotenv
import logging
from datetime import datetime
import uuid
import asyncio
import sys
from concurrent.futures import ThreadPoolExecutor

# Windows için asyncio event loop policy ayarla (Playwright için)
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# Local imports
from backend.database import get_db, init_db
from backend.schemas import (
    ScrapeRequest,
    ScrapeResponse,
    OfferResponse,
    OfferListResponse,
    ApiResponse,
    InsuranceCompany,
    InsuranceBranch,
    TrafikSigortasiRequest,
    KaskoSigortasiRequest,
    StandardOffer
)
from backend.models import (
    Offer, OfferStatus, InsuranceCompany as DBInsuranceCompany, InsuranceBranch as DBInsuranceBranch,
    CompanySettings, CompanyStatus, SystemLog, LogLevel, UserSettings
)

# Load environment variables with UTF-8 encoding
try:
    load_dotenv(encoding='utf-8')
except (UnicodeDecodeError, Exception):
    # Fallback if encoding fails
    try:
        load_dotenv()
    except Exception:
        # If that also fails, continue without .env file
        pass

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# FastAPI app
app = FastAPI(
    title="Sigorta Otomasyon API",
    description="Çoklu sigorta şirketi teklif otomasyon sistemi",
    version="2.0.0"
)

# CORS configuration
cors_origins = os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Thread pool for blocking scraper operations
thread_pool = ThreadPoolExecutor(max_workers=5)

# Global request tracking (in-memory, production'da Redis kullanılmalı)
active_requests: Dict[str, Dict[str, Any]] = {}


# ============================================
# SCRAPER MANAGERS
# ============================================

def run_sompo_scraper(branch: str, data: Dict[str, Any], request_id: str) -> Optional[StandardOffer]:
    """Sompo scraper'ı çalıştır"""
    import sys
    import os
    # Windows için asyncio event loop policy ve yeni loop oluştur (thread pool için)
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        # Thread'de yeni event loop oluştur
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
    try:
        sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'scrapers_event'))
        from sompo_event import (
            sync_playwright, login_and_save, handle_popups, 
            open_new_offer_page, process_trafik_sigortasi, process_kasko_sigortasi
        )
        
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=os.getenv("HEADLESS", "false").lower() == "true")
            context = browser.new_context()
            page = context.new_page()
            
            # Login
            if not login_and_save(page):
                browser.close()
                return StandardOffer(
                    company="Sompo",
                    branch=branch,
                    tckn=data.get('tckn', ''),
                    plate=data.get('plaka'),
                    status="failed",
                    error="Giriş başarısız"
                )
            
            handle_popups(page)
            new_page = open_new_offer_page(page)
            if not new_page:
                browser.close()
                return StandardOffer(
                    company="Sompo",
                    branch=branch,
                    tckn=data.get('tckn', ''),
                    plate=data.get('plaka'),
                    status="failed",
                    error="Yeni teklif sayfası açılamadı"
                )
            
            page = new_page
            
            # Process insurance
            if branch == "trafik":
                result = process_trafik_sigortasi(page, data)
            elif branch == "kasko":
                result = process_kasko_sigortasi(page, data)
            else:
                browser.close()
                return StandardOffer(
                    company="Sompo",
                    branch=branch,
                    tckn=data.get('tckn', ''),
                    plate=data.get('plaka'),
                    status="failed",
                    error=f"Desteklenmeyen branş: {branch}"
                )
            
            browser.close()
            
            if result and result.get('basarili'):
                return StandardOffer.from_sompo_result(result, data.get('tckn', ''), data.get('plaka'))
            else:
                return StandardOffer(
                    company="Sompo",
                    branch=branch,
                    tckn=data.get('tckn', ''),
                    plate=data.get('plaka'),
                    status="failed",
                    error=result.get('hata', 'Bilinmeyen hata') if result else 'Sonuç alınamadı'
                )
            
    except Exception as e:
        logger.error(f"Sompo scraper hatası: {e}", exc_info=True)
        return StandardOffer(
            company="Sompo",
            branch=branch,
            tckn=data.get('tckn', ''),
            plate=data.get('plaka'),
            status="failed",
            error=str(e)
        )


def run_koru_scraper(branch: str, data: Dict[str, Any], request_id: str) -> Optional[StandardOffer]:
    """Koru scraper'ı çalıştır"""
    import sys
    # Windows için asyncio event loop policy ve yeni loop oluştur (thread pool için)
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        # Thread'de yeni event loop oluştur
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
    try:
        from scrapers_event.koru_scraper import KoruScraper
        from scrapers_event.app.config import settings
        
        scraper = KoruScraper()
        
        # Koru için data formatını dönüştür
        koru_data = {
            "tc": data.get('tckn', ''),
            "dogum_tarihi": data.get('dogum_tarihi', '').replace('/', '.'),  # GG/AA/YYYY -> GG.AA.YYYY
            "plaka_il": data.get('plaka', '')[:2] if data.get('plaka') else '',
            "plaka_no": data.get('plaka', '')[2:] if data.get('plaka') and len(data.get('plaka', '')) > 2 else '',
            "tescil_kod": data.get('ruhsat_seri_no', '')[:2] if data.get('ruhsat_seri_no') else '',
            "tescil_no": data.get('ruhsat_seri_no', '')[2:] if data.get('ruhsat_seri_no') and len(data.get('ruhsat_seri_no', '')) > 2 else ''
        }
        
        # Scraper'ı çalıştır (thread pool içinde)
        if branch == "trafik":
            result = scraper.run_trafik_with_data(koru_data)
        elif branch == "kasko":
            result = scraper.run_kasko_with_data(koru_data)
        else:
            return StandardOffer(
                company="Koru",
                branch=branch,
                tckn=data.get('tckn', ''),
                plate=data.get('plaka'),
                status="failed",
                error=f"Desteklenmeyen branş: {branch}"
            )
        
        if result and isinstance(result, dict) and result.get('trafik'):
            return StandardOffer.from_koru_result(result, data.get('tckn', ''), data.get('plaka'))
        else:
            error_msg = "Koru teklif alınamadı"
            if result is False:
                error_msg = "Koru scraper çalıştırılamadı"
            elif isinstance(result, dict) and not result.get('trafik'):
                error_msg = "Koru trafik teklifi alınamadı"
            return StandardOffer(
                company="Koru",
                branch=branch,
                tckn=data.get('tckn', ''),
                plate=data.get('plaka'),
                status="failed",
                error=error_msg
            )
            
    except Exception as e:
        logger.error(f"Koru scraper hatası: {e}", exc_info=True)
        import traceback
        error_detail = str(e)
        if not error_detail:
            error_detail = f"Koru scraper exception: {type(e).__name__}"
        return StandardOffer(
            company="Koru",
            branch=branch,
            tckn=data.get('tckn', ''),
            plate=data.get('plaka'),
            status="failed",
            error=error_detail
        )


def run_doga_scraper(branch: str, data: Dict[str, Any], request_id: str) -> Optional[StandardOffer]:
    """Doğa scraper'ı çalıştır"""
    import sys
    # Windows için asyncio event loop policy ve yeni loop oluştur (thread pool için)
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        # Thread'de yeni event loop oluştur
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
    try:
        from scrapers_event.doga_scraper import DogaScraper
        
        scraper = DogaScraper()
        
        # Doğa için data formatını dönüştür
        doga_data = {
            "tc_no": data.get('tckn', ''),
            "birth_date": data.get('dogum_tarihi', '').replace('/', '-'),  # YYYY-MM-DD formatına çevir
            "plate_code": data.get('plaka', '')[:2] if data.get('plaka') else '',
            "plate_no": data.get('plaka', '')[2:] if data.get('plaka') and len(data.get('plaka', '')) > 2 else '',
            "tescil_seri_kod": data.get('ruhsat_seri_no', '')[:2] if data.get('ruhsat_seri_no') else '',
            "tescil_seri_no": data.get('ruhsat_seri_no', '')[2:] if data.get('ruhsat_seri_no') and len(data.get('ruhsat_seri_no', '')) > 2 else ''
        }
        
        # Scraper'ı çalıştır
        result = scraper.run_with_data(branch, doga_data)
        
        if result and result.get('premium_data'):
            return StandardOffer.from_doga_result(result, data.get('tckn', ''), data.get('plaka'))
        else:
            error_msg = "Doğa teklif alınamadı"
            if result is None:
                error_msg = "Doğa scraper sonuç döndürmedi"
            elif isinstance(result, dict) and not result.get('premium_data'):
                error_msg = "Doğa premium verisi alınamadı"
            return StandardOffer(
                company="Doğa",
                branch=branch,
                tckn=data.get('tckn', ''),
                plate=data.get('plaka'),
                status="failed",
                error=error_msg
            )
            
    except Exception as e:
        logger.error(f"Doğa scraper hatası: {e}", exc_info=True)
        import traceback
        error_detail = str(e)
        if not error_detail:
            error_detail = f"Doğa scraper exception: {type(e).__name__}"
        return StandardOffer(
            company="Doğa",
            branch=branch,
            tckn=data.get('tckn', ''),
            plate=data.get('plaka'),
            status="failed",
            error=error_detail
        )


# Scraper mapping
SCRAPER_FUNCTIONS = {
    InsuranceCompany.SOMPO: run_sompo_scraper,
    InsuranceCompany.KORU: run_koru_scraper,
    InsuranceCompany.DOGA: run_doga_scraper,
    # Diğer şirketler için de eklenebilir
}


# ============================================
# API ENDPOINTS
# ============================================

@app.on_event("startup")
async def startup_event():
    """Application startup"""
    logger.info("🚀 Sigorta Otomasyon API başlatılıyor...")
    try:
        init_db()
        logger.info("✅ Veritabanı bağlantısı başarılı")
    except Exception as e:
        logger.error(f"❌ Veritabanı bağlantı hatası: {e}")
    logger.info("✅ API hazır")


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Sigorta Otomasyon API",
        "version": "2.0.0",
        "status": "active"
    }


@app.get("/health")
async def health_check(db: Session = Depends(get_db)):
    """Health check endpoint"""
    try:
        # Database connection test
        db.execute("SELECT 1")
        return {
            "status": "healthy",
            "database": "connected",
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "database": "disconnected",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
        )


@app.post("/api/v1/scrape/run", response_model=ScrapeResponse)
async def run_scrape(
    request: ScrapeRequest,
    background_tasks: BackgroundTasks,
    db: Optional[Session] = Depends(get_db)
):
    """
    Unified scrape endpoint - Tüm şirketlerden teklif al
    
    Bu endpoint:
    - Belirtilen şirketlerden (veya tümünden) teklif alır
    - Sonuçları veritabanına kaydeder
    - Background task olarak çalışır
    """
    request_id = str(uuid.uuid4())
    timestamp = datetime.now().isoformat()
    
    # Request'i kaydet
    active_requests[request_id] = {
        "request_id": request_id,
        "status": "running",
        "branch": request.branch.value,
        "companies": [c.value for c in (request.companies or [])],
        "created_at": timestamp,
        "offers": [],
        "failed_companies": []
    }
    
    # Background task olarak scraper'ları çalıştır
    background_tasks.add_task(
        process_scrape_request,
        request_id,
        request,
        db
    )
    
    return ScrapeResponse(
        success=True,
        message="Teklif alma işlemi başlatıldı",
        request_id=request_id,
        timestamp=timestamp
    )


async def process_scrape_request(
    request_id: str,
    request: ScrapeRequest,
    db: Session
):
    """Scrape request'i işle ve log kaydet"""
    """Background task: Scraper'ları çalıştır ve sonuçları kaydet"""
    try:
        # Hangi şirketlerden teklif alınacak?
        companies_to_scrape = request.companies or list(InsuranceCompany)
        
        # Data hazırla
        if request.branch == InsuranceBranch.TRAFIK and request.trafik_data:
            data = request.trafik_data.dict()
        elif request.branch == InsuranceBranch.KASKO and request.kasko_data:
            data = request.kasko_data.dict()
        else:
            data = request.data or {}
        
        # Her şirket için scraper çalıştır
        offers = []
        failed_companies = []
        
        # Windows'ta thread pool yerine doğrudan çalıştırmak için loop'a ihtiyaç yok
        loop = None
        if sys.platform != "win32":
            loop = asyncio.get_event_loop()
        
        for company in companies_to_scrape:
            if company not in SCRAPER_FUNCTIONS:
                logger.warning(f"⚠️ {company.value} için scraper fonksiyonu bulunamadı")
                failed_companies.append(company.value)
                continue
            
            try:
                scraper_func = SCRAPER_FUNCTIONS[company]
                
                # Thread pool'da çalıştır (Windows'ta event loop sorunu nedeniyle doğrudan çalıştır)
                if sys.platform == "win32":
                    # Windows'ta thread pool yerine doğrudan çalıştır (blocking)
                    result = scraper_func(
                        request.branch.value,
                        data,
                        request_id
                    )
                else:
                    # Linux'ta thread pool kullan
                    result = await loop.run_in_executor(
                        thread_pool,
                        scraper_func,
                        request.branch.value,
                        data,
                        request_id
                    )
                
                if result and result.status == "completed":
                    # Veritabanına kaydet (eğer database mevcut ise)
                    try:
                        if db is not None:
                            offer = Offer(
                                company=DBInsuranceCompany[company.name],
                                branch=DBInsuranceBranch[request.branch.name],
                                tckn=data.get('tckn', ''),
                                plate=result.plate,
                                price=result.price,
                                currency=result.currency,
                                policy_no=result.policy_no,
                                status=OfferStatus.COMPLETED,
                                raw_data=result.raw_data
                            )
                            db.add(offer)
                            db.commit()
                            offers.append(offer)
                        else:
                            # Database yoksa, sadece in-memory olarak ekle
                            offers.append(result)
                    except Exception as db_error:
                        logger.warning(f"⚠️ Database kayıt hatası (in-memory devam ediyor): {db_error}")
                        offers.append(result)
                    
                    logger.info(f"✅ {company.value} teklifi başarılı: {result.price} {result.currency}")
                else:
                    # Hata kaydı
                    error_msg = result.error if result else "Bilinmeyen hata"
                    failed_companies.append(f"{company.value}: {error_msg}")
                    logger.error(f"❌ {company.value} teklifi başarısız: {error_msg}")
                    
            except Exception as e:
                logger.error(f"❌ {company.value} scraper hatası: {e}", exc_info=True)
                failed_companies.append(f"{company.value}: {str(e)}")
                
                # Log kaydı (eğer database mevcut ise)
                try:
                    if db is not None:
                        log = SystemLog(
                            level=LogLevel.ERROR,
                            message=f"{company.value} scraper error: {str(e)}",
                            user="system",
                            action="SCRAPER_ERROR",
                            log_metadata={"company": company.value, "branch": request.branch.value, "error": str(e), "request_id": request_id}
                        )
                        db.add(log)
                        db.commit()
                except Exception:
                    pass  # Database yoksa log kaydını atla
        
        # Request durumunu güncelle
        active_requests[request_id].update({
            "status": "completed",
            "offers": [o.to_dict() for o in offers],
            "failed_companies": failed_companies,
            "completed_at": datetime.now().isoformat()
        })
        
        # Başarı logu (eğer database mevcut ise)
        try:
            if db is not None:
                log = SystemLog(
                    level=LogLevel.SUCCESS,
                    message=f"Scrape request completed: {len(offers)} offers, {len(failed_companies)} failed",
                    user="system",
                    action="SCRAPE_COMPLETED",
                    log_metadata={"request_id": request_id, "offers_count": len(offers), "failed_count": len(failed_companies)}
                )
                db.add(log)
                db.commit()
        except Exception:
            pass  # Database yoksa log kaydını atla
        
    except Exception as e:
        logger.error(f"❌ Scrape request işleme hatası: {e}", exc_info=True)
        active_requests[request_id].update({
            "status": "failed",
            "error": str(e),
            "completed_at": datetime.now().isoformat()
        })
        
        # Hata logu (eğer database mevcut ise)
        try:
            if db is not None:
                log = SystemLog(
                    level=LogLevel.ERROR,
                    message=f"Scrape request failed: {str(e)}",
                    user="system",
                    action="SCRAPE_FAILED",
                    log_metadata={"request_id": request_id, "error": str(e)}
                )
                db.add(log)
                db.commit()
        except Exception:
            pass  # Database yoksa log kaydını atla


@app.get("/api/v1/offers", response_model=OfferListResponse)
async def get_offers(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    company: Optional[str] = None,
    branch: Optional[str] = None,
    tckn: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Teklif listesini getir"""
    query = db.query(Offer)
    
    # Filtreleme
    if company:
        query = query.filter(Offer.company == DBInsuranceCompany[company.upper()])
    if branch:
        query = query.filter(Offer.branch == DBInsuranceBranch[branch.upper()])
    if tckn:
        query = query.filter(Offer.tckn == tckn)
    
    # Sayfalama
    total = query.count()
    offers = query.order_by(Offer.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    
    return OfferListResponse(
        total=total,
        page=page,
        page_size=page_size,
        offers=[OfferResponse(**offer.to_dict()) for offer in offers]
    )


@app.get("/api/v1/scrape/{request_id}")
async def get_scrape_status(request_id: str):
    """Scrape işlemi durumunu sorgula"""
    if request_id not in active_requests:
        raise HTTPException(status_code=404, detail="Request ID bulunamadı")
    
    return active_requests[request_id]


@app.get("/api/v1/companies")
async def get_companies():
    """Desteklenen sigorta şirketlerini listele"""
    return {
        "companies": [c.value for c in InsuranceCompany],
        "scrapers_available": [c.value for c in SCRAPER_FUNCTIONS.keys()]
    }


# ============================================
# COMPANY SETTINGS ENDPOINTS
# ============================================

@app.get("/api/v1/companies/settings")
async def get_company_settings(db: Session = Depends(get_db)):
    """Tüm şirket ayarlarını getir"""
    settings = db.query(CompanySettings).all()
    
    # Eğer hiç ayar yoksa, varsayılan ayarları oluştur
    if not settings:
        default_companies = [c for c in DBInsuranceCompany]
        for company in default_companies:
            setting = CompanySettings(
                company=company,
                status=CompanyStatus.ACTIVE
            )
            db.add(setting)
        db.commit()
        settings = db.query(CompanySettings).all()
    
    return {
        "success": True,
        "companies": [s.to_dict() for s in settings]
    }


@app.post("/api/v1/companies/settings")
async def update_company_settings(
    company: str,
    status: str,
    db: Session = Depends(get_db)
):
    """Şirket durumunu güncelle"""
    try:
        company_enum = DBInsuranceCompany[company.upper()]
        status_enum = CompanyStatus[status.upper()]
    except KeyError:
        raise HTTPException(status_code=400, detail="Invalid company or status")
    
    setting = db.query(CompanySettings).filter(
        CompanySettings.company == company_enum
    ).first()
    
    if not setting:
        setting = CompanySettings(
            company=company_enum,
            status=status_enum
        )
        db.add(setting)
    else:
        setting.status = status_enum
    
    db.commit()
    db.refresh(setting)
    
    # Log kaydı
    log = SystemLog(
        level=LogLevel.INFO,
        message=f"Company {company} status changed to {status}",
        user="admin",
        action="UPDATE_COMPANY_STATUS",
        log_metadata={"company": company, "status": status}
    )
    db.add(log)
    db.commit()
    
    return {
        "success": True,
        "message": "Company status updated",
        "company": setting.to_dict()
    }


@app.post("/api/v1/companies/settings/bulk")
async def update_company_settings_bulk(
    updates: List[Dict[str, Any]],
    db: Session = Depends(get_db)
):
    """Birden fazla şirket durumunu toplu güncelle"""
    updated = []
    for update in updates:
        try:
            company_enum = DBInsuranceCompany[update["company"].upper()]
            status_enum = CompanyStatus[update["status"].upper()]
        except KeyError:
            continue
        
        setting = db.query(CompanySettings).filter(
            CompanySettings.company == company_enum
        ).first()
        
        if not setting:
            setting = CompanySettings(
                company=company_enum,
                status=status_enum
            )
            db.add(setting)
        else:
            setting.status = status_enum
        
        updated.append(setting)
    
    db.commit()
    
    # Log kaydı
    log = SystemLog(
        level=LogLevel.INFO,
        message=f"Bulk company status update: {len(updated)} companies",
        user="admin",
        action="BULK_UPDATE_COMPANY_STATUS",
        log_metadata={"updates": [{"company": u.company.value, "status": u.status.value} for u in updated]}
    )
    db.add(log)
    db.commit()
    
    return {
        "success": True,
        "message": f"{len(updated)} companies updated",
        "companies": [s.to_dict() for s in updated]
    }


# ============================================
# SYSTEM LOGS ENDPOINTS
# ============================================

@app.get("/api/v1/logs")
async def get_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    level: Optional[str] = None,
    user: Optional[str] = None,
    action: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Sistem loglarını getir"""
    query = db.query(SystemLog)
    
    # Filtreleme
    if level:
        try:
            level_enum = LogLevel[level.upper()]
            query = query.filter(SystemLog.level == level_enum)
        except KeyError:
            pass
    if user:
        query = query.filter(SystemLog.user == user)
    if action:
        query = query.filter(SystemLog.action == action)
    
    # Sayfalama
    total = query.count()
    logs = query.order_by(SystemLog.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    
    return {
        "success": True,
        "total": total,
        "page": page,
        "page_size": page_size,
        "logs": [log.to_dict() for log in logs]
    }


@app.post("/api/v1/logs")
async def create_log(
    level: str,
    message: str,
    user: Optional[str] = None,
    action: Optional[str] = None,
    log_metadata: Optional[Dict[str, Any]] = None,
    db: Session = Depends(get_db)
):
    """Yeni log kaydı oluştur"""
    try:
        level_enum = LogLevel[level.upper()]
    except KeyError:
        raise HTTPException(status_code=400, detail="Invalid log level")
    
    log = SystemLog(
        level=level_enum,
        message=message,
        user=user,
        action=action,
        log_metadata=log_metadata
    )
    db.add(log)
    db.commit()
    db.refresh(log)
    
    return {
        "success": True,
        "message": "Log created",
        "log": log.to_dict()
    }


# ============================================
# USER SETTINGS ENDPOINTS
# ============================================

@app.get("/api/v1/settings")
async def get_settings(
    user_id: Optional[int] = None,
    setting_key: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Kullanıcı ayarlarını getir"""
    query = db.query(UserSettings)
    
    if user_id is not None:
        query = query.filter(UserSettings.user_id == user_id)
    if setting_key:
        query = query.filter(UserSettings.setting_key == setting_key)
    
    settings = query.all()
    
    return {
        "success": True,
        "settings": [s.to_dict() for s in settings]
    }


@app.post("/api/v1/settings")
async def save_settings(
    setting_key: str,
    setting_value: Dict[str, Any],
    user_id: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """Kullanıcı ayarı kaydet"""
    # Mevcut ayarı kontrol et
    query = db.query(UserSettings).filter(UserSettings.setting_key == setting_key)
    if user_id is not None:
        query = query.filter(UserSettings.user_id == user_id)
    else:
        query = query.filter(UserSettings.user_id.is_(None))
    
    setting = query.first()
    
    if setting:
        setting.setting_value = setting_value
    else:
        setting = UserSettings(
            user_id=user_id,
            setting_key=setting_key,
            setting_value=setting_value
        )
        db.add(setting)
    
    db.commit()
    db.refresh(setting)
    
    return {
        "success": True,
        "message": "Setting saved",
        "setting": setting.to_dict()
    }


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("BACKEND_PORT", "8000"))
    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=port,
        reload=True,
        log_level="info"
    )

