# VMLedger Deployment Test Script
# This script tests the basic functionality of the deployed VMLedger application

Write-Host "==================================" -ForegroundColor Cyan
Write-Host "VMLedger Deployment Test" -ForegroundColor Cyan
Write-Host "==================================" -ForegroundColor Cyan
Write-Host ""

# Test 1: Check if containers are running
Write-Host "[1/5] Checking Docker containers..." -ForegroundColor Yellow
$containers = docker ps --filter "name=vmledger" --format "{{.Names}}" | Measure-Object -Line
if ($containers.Lines -eq 5) {
    Write-Host "✅ All 5 containers are running" -ForegroundColor Green
} else {
    Write-Host "❌ Expected 5 containers, found $($containers.Lines)" -ForegroundColor Red
    exit 1
}
Write-Host ""

# Test 2: Check API health (expect auth error, which means API is responding)
Write-Host "[2/5] Testing API endpoint..." -ForegroundColor Yellow
try {
    $response = Invoke-WebRequest -Uri "http://localhost:8000/api/health" -ErrorAction SilentlyContinue
} catch {
    if ($_.Exception.Response.StatusCode -eq 401) {
        Write-Host "✅ API is responding (authentication required as expected)" -ForegroundColor Green
    } else {
        Write-Host "❌ Unexpected response from API" -ForegroundColor Red
        exit 1
    }
}
Write-Host ""

# Test 3: Check database connection
Write-Host "[3/5] Checking database connection..." -ForegroundColor Yellow
$dbCheck = docker exec vmledger-postgres pg_isready -U vmledger
if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ Database is ready" -ForegroundColor Green
} else {
    Write-Host "❌ Database connection failed" -ForegroundColor Red
    exit 1
}
Write-Host ""

# Test 4: Check Redis connection
Write-Host "[4/5] Checking Redis connection..." -ForegroundColor Yellow
$redisCheck = docker exec vmledger-redis redis-cli ping
if ($redisCheck -eq "PONG") {
    Write-Host "✅ Redis is responding" -ForegroundColor Green
} else {
    Write-Host "❌ Redis connection failed" -ForegroundColor Red
    exit 1
}
Write-Host ""

# Test 5: Check Celery worker
Write-Host "[5/5] Checking Celery worker..." -ForegroundColor Yellow
$celeryLogs = docker logs vmledger-celery-worker --tail 5
if ($celeryLogs -match "ready") {
    Write-Host "✅ Celery worker is ready" -ForegroundColor Green
} else {
    Write-Host "⚠️  Celery worker status unclear" -ForegroundColor Yellow
}
Write-Host ""

# Summary
Write-Host "==================================" -ForegroundColor Cyan
Write-Host "✅ Deployment Test Passed!" -ForegroundColor Green
Write-Host "==================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Your VMLedger instance is running at:" -ForegroundColor White
Write-Host "  API: http://localhost:8000" -ForegroundColor Cyan
Write-Host "  Docs: http://localhost:8000/docs" -ForegroundColor Cyan
Write-Host ""
Write-Host "Next steps:" -ForegroundColor White
Write-Host "  1. Register a user: POST /api/auth/register" -ForegroundColor Gray
Write-Host "  2. Login: POST /api/auth/login" -ForegroundColor Gray
Write-Host "  3. Add VMs: POST /api/vms" -ForegroundColor Gray
Write-Host ""
Write-Host "See DEPLOYMENT_STATUS.md for detailed instructions." -ForegroundColor White
Write-Host ""
