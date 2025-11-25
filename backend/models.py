"""
SQLAlchemy Database Models
"""
from sqlalchemy import Column, Integer, String, Float, DateTime, Text, JSON, Enum as SQLEnum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
from datetime import datetime
import enum

Base = declarative_base()


class OfferStatus(str, enum.Enum):
    """Teklif durumu"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class InsuranceBranch(str, enum.Enum):
    """Sigorta branşı"""
    TRAFIK = "trafik"
    KASKO = "kasko"
    SAGLIK = "saglik"
    DASK = "dask"
    KONUT = "konut"
    SEYAHAT = "seyahat"


class InsuranceCompany(str, enum.Enum):
    """Sigorta şirketi"""
    SOMPO = "Sompo"
    KORU = "Koru"
    DOGA = "Doğa"
    SEKER = "Şeker"
    REFERANS = "Referans"
    ANADOLU = "Anadolu"
    ATLAS = "Atlas"


class Offer(Base):
    """
    Teklif kayıtları için standart model
    """
    __tablename__ = "offers"

    id = Column(Integer, primary_key=True, index=True)
    
    # Sigorta bilgileri
    company = Column(SQLEnum(InsuranceCompany), nullable=False, index=True)
    branch = Column(SQLEnum(InsuranceBranch), nullable=False, index=True)
    
    # Müşteri bilgileri
    tckn = Column(String(11), nullable=False, index=True)
    plate = Column(String(20), index=True)  # Plaka (trafik/kasko için)
    
    # Teklif bilgileri
    price = Column(Float, nullable=True)  # Prim tutarı
    currency = Column(String(3), default="TRY")
    policy_no = Column(String(50), nullable=True, index=True)  # Teklif/Poliçe numarası
    
    # Tarih bilgileri
    valid_from = Column(DateTime, nullable=True)
    valid_to = Column(DateTime, nullable=True)
    
    # Durum ve metadata
    status = Column(SQLEnum(OfferStatus), default=OfferStatus.PENDING, index=True)
    raw_data = Column(JSON, nullable=True)  # Scraper'dan gelen ham veri
    error_message = Column(Text, nullable=True)  # Hata mesajı (varsa)
    
    # Timestamps
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
    
    def to_dict(self):
        """Model'i dictionary'ye çevir"""
        return {
            "id": self.id,
            "company": self.company.value if self.company else None,
            "branch": self.branch.value if self.branch else None,
            "tckn": self.tckn,
            "plate": self.plate,
            "price": self.price,
            "currency": self.currency,
            "policy_no": self.policy_no,
            "valid_from": self.valid_from.isoformat() if self.valid_from else None,
            "valid_to": self.valid_to.isoformat() if self.valid_to else None,
            "status": self.status.value if self.status else None,
            "raw_data": self.raw_data,
            "error_message": self.error_message,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class User(Base):
    """
    Kullanıcı modeli (admin panel için)
    """
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(100), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    is_active = Column(String(10), default="true")
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)


class ScraperLog(Base):
    """
    Scraper işlem logları
    """
    __tablename__ = "scraper_logs"

    id = Column(Integer, primary_key=True, index=True)
    company = Column(SQLEnum(InsuranceCompany), nullable=False, index=True)
    branch = Column(SQLEnum(InsuranceBranch), nullable=False)
    request_id = Column(String(100), nullable=False, index=True)
    status = Column(SQLEnum(OfferStatus), nullable=False, index=True)
    message = Column(Text, nullable=True)
    error = Column(Text, nullable=True)
    execution_time = Column(Float, nullable=True)  # Saniye cinsinden
    created_at = Column(DateTime, server_default=func.now(), nullable=False)


class CompanyStatus(str, enum.Enum):
    """Şirket durumu"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    MAINTENANCE = "maintenance"


class CompanySettings(Base):
    """
    Şirket ayarları (aktif/pasif durumları)
    """
    __tablename__ = "company_settings"

    id = Column(Integer, primary_key=True, index=True)
    company = Column(SQLEnum(InsuranceCompany), unique=True, nullable=False, index=True)
    status = Column(SQLEnum(CompanyStatus), default=CompanyStatus.ACTIVE, nullable=False, index=True)
    last_query = Column(DateTime, nullable=True)
    success_rate = Column(Float, default=0.0)
    total_queries = Column(Integer, default=0)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    def to_dict(self):
        """Model'i dictionary'ye çevir"""
        return {
            "id": self.id,
            "company": self.company.value if self.company else None,
            "status": self.status.value if self.status else None,
            "last_query": self.last_query.isoformat() if self.last_query else None,
            "success_rate": self.success_rate,
            "total_queries": self.total_queries,
            "notes": self.notes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class LogLevel(str, enum.Enum):
    """Log seviyesi"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    SUCCESS = "success"


class SystemLog(Base):
    """
    Sistem logları (genel loglar)
    """
    __tablename__ = "system_logs"

    id = Column(Integer, primary_key=True, index=True)
    level = Column(SQLEnum(LogLevel), nullable=False, index=True)
    message = Column(Text, nullable=False)
    user = Column(String(100), nullable=True, index=True)
    action = Column(String(100), nullable=True, index=True)
    log_metadata = Column(JSON, nullable=True)  # Ek bilgiler (metadata SQLAlchemy'de rezerve isim)
    created_at = Column(DateTime, server_default=func.now(), nullable=False, index=True)

    def to_dict(self):
        """Model'i dictionary'ye çevir"""
        return {
            "id": self.id,
            "level": self.level.value if self.level else None,
            "message": self.message,
            "user": self.user,
            "action": self.action,
            "metadata": self.log_metadata,  # API response'da metadata olarak döner
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class UserSettings(Base):
    """
    Kullanıcı ayarları
    """
    __tablename__ = "user_settings"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=True, index=True)  # Kullanıcı ID (opsiyonel, global ayarlar için null)
    setting_key = Column(String(100), nullable=False, index=True)
    setting_value = Column(JSON, nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    def to_dict(self):
        """Model'i dictionary'ye çevir"""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "setting_key": self.setting_key,
            "setting_value": self.setting_value,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

