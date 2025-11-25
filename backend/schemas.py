"""
Pydantic v2 Schemas for request/response validation
"""
from pydantic import BaseModel, Field, field_validator
from typing import Optional, Dict, Any, List
from datetime import datetime, date
from enum import Enum


class InsuranceBranch(str, Enum):
    """Sigorta branşı"""
    TRAFIK = "trafik"
    KASKO = "kasko"
    SAGLIK = "saglik"
    DASK = "dask"
    KONUT = "konut"
    SEYAHAT = "seyahat"


class InsuranceCompany(str, Enum):
    """Sigorta şirketi"""
    SOMPO = "Sompo"
    KORU = "Koru"
    DOGA = "Doğa"
    SEKER = "Şeker"
    REFERANS = "Referans"
    ANADOLU = "Anadolu"
    ATLAS = "Atlas"


class OfferStatus(str, Enum):
    """Teklif durumu"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


# ============================================
# REQUEST SCHEMAS
# ============================================

class BaseInsuranceRequest(BaseModel):
    """Temel sigorta isteği"""
    tckn: str = Field(..., description="TC Kimlik Numarası", min_length=11, max_length=11)
    email: Optional[str] = Field(None, description="E-posta adresi")
    telefon: Optional[str] = Field(None, description="Telefon numarası")
    dogum_tarihi: Optional[str] = Field(None, description="Doğum tarihi (GG/AA/YYYY veya YYYY-MM-DD)")

    @field_validator('tckn')
    @classmethod
    def validate_tckn(cls, v: str) -> str:
        """TCKN validasyonu"""
        if not v.isdigit():
            raise ValueError("TCKN sadece rakamlardan oluşmalıdır")
        if len(v) != 11:
            raise ValueError("TCKN 11 haneli olmalıdır")
        return v


class TrafikSigortasiRequest(BaseInsuranceRequest):
    """Trafik sigortası teklif isteği"""
    plaka: str = Field(..., description="Araç plakası (örn: 34ABC123)")
    ruhsat_seri_no: str = Field(..., description="Ruhsat seri numarası (örn: FC993016)")
    arac_marka: str = Field(..., description="Araç markası")
    arac_modeli: Optional[str] = Field(None, description="Araç modeli")

    @field_validator('plaka')
    @classmethod
    def validate_plaka(cls, v: str) -> str:
        """Plaka validasyonu"""
        v = v.upper().strip()
        if len(v) < 5:
            raise ValueError("Geçersiz plaka formatı")
        return v


class KaskoSigortasiRequest(BaseInsuranceRequest):
    """Kasko sigortası teklif isteği"""
    plaka: str = Field(..., description="Araç plakası")
    ruhsat_seri_no: str = Field(..., description="Ruhsat seri numarası")
    arac_marka: str = Field(..., description="Araç markası")
    arac_modeli: Optional[str] = Field(None, description="Araç modeli")
    meslek: Optional[str] = Field(None, description="Meslek bilgisi")


class ScrapeRequest(BaseModel):
    """Unified scrape request - tüm şirketler için"""
    branch: InsuranceBranch = Field(..., description="Sigorta branşı")
    companies: Optional[List[InsuranceCompany]] = Field(
        None,
        description="Hangi şirketlerden teklif alınacak (boşsa tümü)"
    )
    # Trafik/Kasko için
    trafik_data: Optional[TrafikSigortasiRequest] = None
    kasko_data: Optional[KaskoSigortasiRequest] = None
    # Diğer branşlar için genel data
    data: Optional[Dict[str, Any]] = None

    @field_validator('companies')
    @classmethod
    def validate_companies(cls, v: Optional[List[InsuranceCompany]]) -> Optional[List[InsuranceCompany]]:
        """Şirket listesi validasyonu"""
        if v is not None and len(v) == 0:
            raise ValueError("Şirket listesi boş olamaz")
        return v


# ============================================
# RESPONSE SCHEMAS
# ============================================

class OfferResponse(BaseModel):
    """Teklif yanıt modeli"""
    id: Optional[int] = None
    company: str
    branch: str
    tckn: str
    plate: Optional[str] = None
    price: Optional[float] = None
    currency: str = "TRY"
    policy_no: Optional[str] = None
    valid_from: Optional[str] = None
    valid_to: Optional[str] = None
    status: str
    raw_data: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    created_at: str
    updated_at: Optional[str] = None

    class Config:
        from_attributes = True


class ApiResponse(BaseModel):
    """Standart API yanıt modeli"""
    success: bool
    message: str
    request_id: Optional[str] = None
    timestamp: str
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class ScrapeResponse(ApiResponse):
    """Scrape işlemi yanıtı"""
    offers: Optional[List[OfferResponse]] = None
    failed_companies: Optional[List[str]] = None


class OfferListResponse(BaseModel):
    """Teklif listesi yanıtı"""
    total: int
    page: int = 1
    page_size: int = 50
    offers: List[OfferResponse]


# ============================================
# INTERNAL SCHEMAS (Scraper output normalization)
# ============================================

class StandardOffer(BaseModel):
    """
    Scraper'lardan gelen çıktıları standart formata çevirmek için
    """
    company: str
    branch: str
    plate: Optional[str] = None
    tckn: str
    price: Optional[float] = None
    currency: str = "TRY"
    policy_no: Optional[str] = None
    valid_from: Optional[str] = None
    valid_to: Optional[str] = None
    raw_data: Optional[Dict[str, Any]] = None
    status: str = "completed"
    error: Optional[str] = None

    @classmethod
    def from_sompo_result(cls, result: Dict[str, Any], tckn: str, plate: Optional[str] = None) -> "StandardOffer":
        """Sompo scraper çıktısını standart formata çevir"""
        if not result.get('basarili'):
            return cls(
                company="Sompo",
                branch="trafik",  # veya kasko
                tckn=tckn,
                plate=plate,
                status="failed",
                error=result.get('hata', 'Bilinmeyen hata')
            )
        
        # Prim değerini parse et
        price = None
        brut_prim = result.get('brut_prim', '')
        if brut_prim:
            try:
                # "1.234,56 TL" formatından float'a çevir
                price_str = brut_prim.replace('TL', '').replace('.', '').replace(',', '.').strip()
                price = float(price_str)
            except:
                pass
        
        return cls(
            company="Sompo",
            branch="trafik",  # veya kasko
            tckn=tckn,
            plate=plate,
            price=price,
            policy_no=result.get('teklif_no'),
            raw_data=result,
            status="completed"
        )

    @classmethod
    def from_koru_result(cls, result: Dict[str, Any], tckn: str, plate: Optional[str] = None) -> "StandardOffer":
        """Koru scraper çıktısını standart formata çevir"""
        trafik_data = result.get('trafik') or result
        if not trafik_data:
            return cls(
                company="Koru",
                branch="trafik",
                tckn=tckn,
                plate=plate,
                status="failed",
                error="Koru teklif verisi bulunamadı"
            )
        
        price = None
        brut_prim = trafik_data.get('brut_prim') or trafik_data.get('prim')
        if brut_prim:
            try:
                price_str = str(brut_prim).replace('TL', '').replace('.', '').replace(',', '.').strip()
                price = float(price_str)
            except:
                pass
        
        return cls(
            company="Koru",
            branch="trafik",
            tckn=tckn,
            plate=plate,
            price=price,
            policy_no=trafik_data.get('teklif_no'),
            raw_data=result,
            status="completed"
        )

    @classmethod
    def from_doga_result(cls, result: Dict[str, Any], tckn: str, plate: Optional[str] = None) -> "StandardOffer":
        """Doğa scraper çıktısını standart formata çevir"""
        premium_data = result.get('premium_data', {})
        if not premium_data:
            return cls(
                company="Doğa",
                branch="trafik",
                tckn=tckn,
                plate=plate,
                status="failed",
                error="Doğa premium verisi bulunamadı"
            )
        
        # Brüt Prim'i al
        price = None
        brut_prim = premium_data.get('Brüt Prim')
        if brut_prim:
            try:
                price_str = str(brut_prim).replace('TL', '').replace('.', '').replace(',', '.').strip()
                price = float(price_str)
            except:
                pass
        
        return cls(
            company="Doğa",
            branch="trafik",
            tckn=tckn,
            plate=plate,
            price=price,
            raw_data=result,
            status="completed"
        )

