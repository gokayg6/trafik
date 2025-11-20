# Sigorta Backend Environment Setup Script
# Otomatik environment variables ayarlama

Write-Host "🚀 Sigorta Backend Environment Setup" -ForegroundColor Green
Write-Host "======================================" -ForegroundColor Green

# Backend Configuration
$HEADLESS = "true"
$TIMEOUT_MS = "45000"
$MAX_WORKERS = "3"

# API Keys (Frontend ile aynı olmalı)
$API_KEYS = '["test-api-key-123","frontend-key-456"]'

# Backend Portları
$SOMPO_PORT = "8000"
$KORU_PORT = "8003"
$SEKER_PORT = "8004"

# Kullanıcı bilgileri (Bunları kendi bilgilerinizle değiştirin)
$SOMPO_USERNAME = "your_sompo_username"
$SOMPO_PASSWORD = "your_sompo_password"

$KORU_USERNAME = "your_koru_username" 
$KORU_PASSWORD = "your_koru_password"
$KORU_TOTP_SECRET = "your_koru_totp_secret"  # Opsiyonel

$SEKER_USERNAME = "your_seker_username"
$SEKER_PASSWORD = "your_seker_password"

Write-Host "📝 Environment Variables ayarlanıyor..." -ForegroundColor Yellow

# Sompo Sigorta Environment Variables
[Environment]::SetEnvironmentVariable("SOMPO_USERNAME", $SOMPO_USERNAME, "User")
[Environment]::SetEnvironmentVariable("SOMPO_PASSWORD", $SOMPO_PASSWORD, "User")
[Environment]::SetEnvironmentVariable("SOMPO_PORT", $SOMPO_PORT, "User")

# Koru Sigorta Environment Variables  
[Environment]::SetEnvironmentVariable("KORU_USERNAME", $KORU_USERNAME, "User")
[Environment]::SetEnvironmentVariable("KORU_PASSWORD", $KORU_PASSWORD, "User")
[Environment]::SetEnvironmentVariable("KORU_TOTP_SECRET", $KORU_TOTP_SECRET, "User")
[Environment]::SetEnvironmentVariable("KORU_PORT", $KORU_PORT, "User")

# Şeker Sigorta Environment Variables
[Environment]::SetEnvironmentVariable("SEKER_USERNAME", $SEKER_USERNAME, "User")
[Environment]::SetEnvironmentVariable("SEKER_PASSWORD", $SEKER_PASSWORD, "User")
[Environment]::SetEnvironmentVariable("SEKER_PORT", $SEKER_PORT, "User")

# Ortak Environment Variables
[Environment]::SetEnvironmentVariable("HEADLESS", $HEADLESS, "User")
[Environment]::SetEnvironmentVariable("API_KEYS", $API_KEYS, "User")
[Environment]::SetEnvironmentVariable("TIMEOUT_MS", $TIMEOUT_MS, "User")
[Environment]::SetEnvironmentVariable("MAX_WORKERS", $MAX_WORKERS, "User")

Write-Host "✅ Tüm Environment Variables ayarlandı!" -ForegroundColor Green

# Kontrol ve bilgilendirme
Write-Host "`n📊 Ayarlanan Environment Variables:" -ForegroundColor Cyan
Write-Host "----------------------------------------" -ForegroundColor Cyan

Write-Host "🏢 Sompo Sigorta:" -ForegroundColor Yellow
Write-Host "   - SOMPO_USERNAME: $SOMPO_USERNAME" -ForegroundColor White
Write-Host "   - SOMPO_PASSWORD: ********" -ForegroundColor White  
Write-Host "   - SOMPO_PORT: $SOMPO_PORT" -ForegroundColor White

Write-Host "`n🛡️ Koru Sigorta:" -ForegroundColor Yellow
Write-Host "   - KORU_USERNAME: $KORU_USERNAME" -ForegroundColor White
Write-Host "   - KORU_PASSWORD: ********" -ForegroundColor White
Write-Host "   - KORU_TOTP_SECRET: $KORU_TOTP_SECRET" -ForegroundColor White
Write-Host "   - KORU_PORT: $KORU_PORT" -ForegroundColor White

Write-Host "`n🍬 Şeker Sigorta:" -ForegroundColor Yellow
Write-Host "   - SEKER_USERNAME: $SEKER_USERNAME" -ForegroundColor White
Write-Host "   - SEKER_PASSWORD: ********" -ForegroundColor White
Write-Host "   - SEKER_PORT: $SEKER_PORT" -ForegroundColor White

Write-Host "`n🌐 Ortak Ayarlar:" -ForegroundColor Yellow
Write-Host "   - HEADLESS: $HEADLESS" -ForegroundColor White
Write-Host "   - API_KEYS: $API_KEYS" -ForegroundColor White
Write-Host "   - TIMEOUT_MS: $TIMEOUT_MS" -ForegroundColor White
Write-Host "   - MAX_WORKERS: $MAX_WORKERS" -ForegroundColor White

Write-Host "`n🎯 Backend Başlatma Komutları:" -ForegroundColor Cyan
Write-Host "----------------------------------------" -ForegroundColor Cyan
Write-Host "Sompo Backend:    python sompo_backend.py" -ForegroundColor Green
Write-Host "Koru Backend:     python koru_backend.py" -ForegroundColor Green  
Write-Host "Şeker Backend:    python seker_backend.py" -ForegroundColor Green

Write-Host "`n📍 Port Bilgileri:" -ForegroundColor Cyan
Write-Host "----------------------------------------" -ForegroundColor Cyan
Write-Host "Sompo:   http://localhost:$SOMPO_PORT" -ForegroundColor White
Write-Host "Koru:    http://localhost:$KORU_PORT" -ForegroundColor White
Write-Host "Şeker:   http://localhost:$SEKER_PORT" -ForegroundColor White

Write-Host "`n📚 API Dokümantasyon:" -ForegroundColor Cyan
Write-Host "----------------------------------------" -ForegroundColor Cyan
Write-Host "Sompo:   http://localhost:$SOMPO_PORT/docs" -ForegroundColor White
Write-Host "Koru:    http://localhost:$KORU_PORT/docs" -ForegroundColor White
Write-Host "Şeker:   http://localhost:$SEKER_PORT/docs" -ForegroundColor White

Write-Host "`n✅ Kurulum tamamlandı! Backend'leri başlatabilirsiniz." -ForegroundColor Green

# Yeni PowerShell oturumunda environment variables'ların etkin olması için uyarı
Write-Host "`n⚠️  Not: Environment variables'ların etkin olması için yeni bir PowerShell penceresi açmanız gerekebilir." -ForegroundColor Yellow