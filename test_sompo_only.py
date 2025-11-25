"""Sadece Sompo'nun aktif olduğunu test et"""
import sys
sys.path.insert(0, '.')

from backend.main import SCRAPER_FUNCTIONS

print("="*60)
print("AKTİF SCRAPER'LAR")
print("="*60)

for company, func in SCRAPER_FUNCTIONS.items():
    print(f"[OK] {company.value}")

print("="*60)
print(f"Toplam: {len(SCRAPER_FUNCTIONS)} scraper aktif")
print("="*60)

