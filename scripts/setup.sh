#!/bin/bash
# Setup script for VMLedger (Linux/macOS)

set -e

echo "=========================================="
echo "VMLedger Setup Script"
echo "=========================================="

# Check Python version
echo "Checking Python version..."
python_version=$(python3 --version 2>&1 | awk '{print $2}')
required_version="3.11"

if [ "$(printf '%s\n' "$required_version" "$python_version" | sort -V | head -n1)" != "$required_version" ]; then
    echo "Error: Python 3.11 or higher is required. Found: $python_version"
    exit 1
fi
echo "✓ Python $python_version"

# Create virtual environment
echo ""
echo "Creating virtual environment..."
if [ -d "venv" ]; then
    echo "Virtual environment already exists. Skipping..."
else
    python3 -m venv venv
    echo "✓ Virtual environment created"
fi

# Activate virtual environment
echo ""
echo "Activating virtual environment..."
source venv/bin/activate
echo "✓ Virtual environment activated"

# Upgrade pip
echo ""
echo "Upgrading pip..."
pip install --upgrade pip
echo "✓ pip upgraded"

# Install dependencies
echo ""
echo "Installing dependencies..."
pip install -r requirements.txt
echo "✓ Dependencies installed"

# Create .env file if it doesn't exist
echo ""
if [ -f ".env" ]; then
    echo ".env file already exists. Skipping..."
else
    echo "Creating .env file from template..."
    cp .env.example .env
    echo "✓ .env file created"
    echo ""
    echo "⚠️  IMPORTANT: Edit .env file and set:"
    echo "   - SECRET_KEY (generate with: openssl rand -hex 32)"
    echo "   - ENCRYPTION_MASTER_KEY (generate with: openssl rand -hex 32)"
    echo "   - DATABASE_URL (your PostgreSQL connection string)"
    echo "   - REDIS_URL (your Redis connection string)"
fi

# Create logs directory
echo ""
echo "Creating logs directory..."
mkdir -p logs
echo "✓ logs/ directory created"

# Run verification
echo ""
echo "Running setup verification..."
python scripts/verify_setup.py

echo ""
echo "=========================================="
echo "Setup Complete!"
echo "=========================================="
echo ""
echo "Next steps:"
echo "1. Edit .env file with your configuration"
echo "2. Set up PostgreSQL database"
echo "3. Set up Redis server"
echo "4. Run: uvicorn vmledger.main:app --reload"
echo ""
