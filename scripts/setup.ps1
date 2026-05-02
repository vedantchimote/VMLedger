# Setup script for VMLedger (Windows PowerShell)

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "VMLedger Setup Script" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan

# Check Python version
Write-Host "`nChecking Python version..." -ForegroundColor Yellow
try {
    $pythonVersion = python --version 2>&1 | Select-String -Pattern "Python (\d+\.\d+)" | ForEach-Object { $_.Matches.Groups[1].Value }
    $requiredVersion = [version]"3.11"
    $currentVersion = [version]$pythonVersion
    
    if ($currentVersion -lt $requiredVersion) {
        Write-Host "Error: Python 3.11 or higher is required. Found: $pythonVersion" -ForegroundColor Red
        exit 1
    }
    Write-Host "✓ Python $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "Error: Python not found. Please install Python 3.11 or higher." -ForegroundColor Red
    exit 1
}

# Create virtual environment
Write-Host "`nCreating virtual environment..." -ForegroundColor Yellow
if (Test-Path "venv") {
    Write-Host "Virtual environment already exists. Skipping..." -ForegroundColor Gray
} else {
    python -m venv venv
    Write-Host "✓ Virtual environment created" -ForegroundColor Green
}

# Activate virtual environment
Write-Host "`nActivating virtual environment..." -ForegroundColor Yellow
& "venv\Scripts\Activate.ps1"
Write-Host "✓ Virtual environment activated" -ForegroundColor Green

# Upgrade pip
Write-Host "`nUpgrading pip..." -ForegroundColor Yellow
python -m pip install --upgrade pip | Out-Null
Write-Host "✓ pip upgraded" -ForegroundColor Green

# Install dependencies
Write-Host "`nInstalling dependencies..." -ForegroundColor Yellow
pip install -r requirements.txt
Write-Host "✓ Dependencies installed" -ForegroundColor Green

# Create .env file if it doesn't exist
Write-Host ""
if (Test-Path ".env") {
    Write-Host ".env file already exists. Skipping..." -ForegroundColor Gray
} else {
    Write-Host "Creating .env file from template..." -ForegroundColor Yellow
    Copy-Item ".env.example" ".env"
    Write-Host "✓ .env file created" -ForegroundColor Green
    Write-Host ""
    Write-Host "⚠️  IMPORTANT: Edit .env file and set:" -ForegroundColor Yellow
    Write-Host "   - SECRET_KEY (generate with: python -c 'import secrets; print(secrets.token_hex(32))')" -ForegroundColor Yellow
    Write-Host "   - ENCRYPTION_MASTER_KEY (generate with: python -c 'import secrets; print(secrets.token_hex(32))')" -ForegroundColor Yellow
    Write-Host "   - DATABASE_URL (your PostgreSQL connection string)" -ForegroundColor Yellow
    Write-Host "   - REDIS_URL (your Redis connection string)" -ForegroundColor Yellow
}

# Create logs directory
Write-Host "`nCreating logs directory..." -ForegroundColor Yellow
if (-not (Test-Path "logs")) {
    New-Item -ItemType Directory -Path "logs" | Out-Null
}
Write-Host "✓ logs/ directory created" -ForegroundColor Green

# Run verification
Write-Host "`nRunning setup verification..." -ForegroundColor Yellow
python scripts/verify_setup.py

Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Setup Complete!" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "1. Edit .env file with your configuration" -ForegroundColor White
Write-Host "2. Set up PostgreSQL database" -ForegroundColor White
Write-Host "3. Set up Redis server" -ForegroundColor White
Write-Host "4. Run: uvicorn vmledger.main:app --reload" -ForegroundColor White
Write-Host ""
