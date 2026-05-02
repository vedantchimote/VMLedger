# Quick start script for VMLedger Docker deployment (PowerShell)

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "VMLedger Docker Quick Start" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

# Check if Docker is installed
try {
    $dockerVersion = docker --version
    Write-Host "✓ Docker is installed: $dockerVersion" -ForegroundColor Green
} catch {
    Write-Host "✗ Error: Docker is not installed." -ForegroundColor Red
    Write-Host "Please install Docker Desktop from https://www.docker.com/products/docker-desktop" -ForegroundColor Yellow
    exit 1
}

# Check if Docker Compose is installed
try {
    $composeVersion = docker-compose --version
    Write-Host "✓ Docker Compose is installed: $composeVersion" -ForegroundColor Green
} catch {
    Write-Host "✗ Error: Docker Compose is not installed." -ForegroundColor Red
    Write-Host "Please install Docker Compose from https://docs.docker.com/compose/install/" -ForegroundColor Yellow
    exit 1
}

Write-Host ""

# Check if .env file exists
if (-not (Test-Path .env)) {
    Write-Host "Creating .env file from .env.example..." -ForegroundColor Yellow
    Copy-Item .env.example .env
    Write-Host "✓ .env file created" -ForegroundColor Green
} else {
    Write-Host "✓ .env file already exists" -ForegroundColor Green
}

Write-Host ""
Write-Host "Starting Docker services..." -ForegroundColor Cyan
docker-compose up -d

if ($LASTEXITCODE -ne 0) {
    Write-Host "✗ Failed to start services" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "Waiting for services to be healthy..." -ForegroundColor Yellow
Start-Sleep -Seconds 10

# Check if services are running
$services = docker-compose ps
if ($services -match "Up") {
    Write-Host "✓ Services are running" -ForegroundColor Green
} else {
    Write-Host "✗ Services failed to start. Check logs with: docker-compose logs" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "Running database migrations..." -ForegroundColor Cyan
docker-compose exec -T api alembic upgrade head

if ($LASTEXITCODE -ne 0) {
    Write-Host "✗ Failed to run migrations" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "VMLedger is ready!" -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Access the application:" -ForegroundColor White
Write-Host "  - API: http://localhost:8000" -ForegroundColor Yellow
Write-Host "  - API Docs: http://localhost:8000/api/docs" -ForegroundColor Yellow
Write-Host "  - Health Check: http://localhost:8000/health" -ForegroundColor Yellow
Write-Host ""
Write-Host "Useful commands:" -ForegroundColor White
Write-Host "  - View logs: docker-compose logs -f" -ForegroundColor Yellow
Write-Host "  - Stop services: docker-compose down" -ForegroundColor Yellow
Write-Host "  - Restart services: docker-compose restart" -ForegroundColor Yellow
Write-Host ""
Write-Host "For more information, see DOCKER_DEPLOYMENT.md" -ForegroundColor Cyan
