import os
from dotenv import load_dotenv

# Load environment variables with UTF-8 encoding
try:
    load_dotenv(encoding='utf-8')
except (UnicodeDecodeError, Exception):
    try:
        load_dotenv()
    except Exception:
        pass

class Settings:
    KORU_LOGIN_URL = os.getenv("KORU_LOGIN_URL", "").strip()
    KORU_HOME_URL = os.getenv("KORU_HOME_URL", "").strip()
    KORU_USER = os.getenv("KORU_USER", "").strip()
    KORU_PASS = os.getenv("KORU_PASS", "").strip()
    KORU_TOTP_SECRET = os.getenv("KORU_TOTP_SECRET", "").strip()
    KORU_STORAGE = os.getenv("KORU_STORAGE", "state/koru_auth.json").strip()
    KORU_TIMEOUT_MS = int(os.getenv("KORU_TIMEOUT_MS", "45000"))
    HEADLESS = os.getenv("HEADLESS", "false").lower() == "true"

settings = Settings()
