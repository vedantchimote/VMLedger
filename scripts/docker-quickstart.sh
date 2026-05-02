#!/bin/bash
# Quick start script for VMLedger Docker deployment

set -e

echo "=========================================="
echo "VMLedger Docker Quick Start"
echo "=========================================="
echo ""

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "Error: Docker is not installed."
    echo "Please install Docker from https://docs.docker.com/get-docker/"
    exit 1
fi

# Check if Docker Compose is installed
if ! command -v docker-compose &> /dev/null; then
    echo "Error: Docker Compose is not installed."
    echo "Please install Docker Compose from https://docs.docker.com/compose/install/"
    exit 1
fi

echo "✓ Docker and Docker Compose are installed"
echo ""

# Check if .env file exists
if [ ! -f .env ]; then
    echo "Creating .env file from .env.example..."
    cp .env.example .env
    echo "✓ .env file created"
else
    echo "✓ .env file already exists"
fi

echo ""
echo "Starting Docker services..."
docker-compose up -d

echo ""
echo "Waiting for services to be healthy..."
sleep 10

# Check if services are running
if docker-compose ps | grep -q "Up"; then
    echo "✓ Services are running"
else
    echo "✗ Services failed to start. Check logs with: docker-compose logs"
    exit 1
fi

echo ""
echo "Running database migrations..."
docker-compose exec -T api alembic upgrade head

echo ""
echo "=========================================="
echo "VMLedger is ready!"
echo "=========================================="
echo ""
echo "Access the application:"
echo "  - API: http://localhost:8000"
echo "  - API Docs: http://localhost:8000/api/docs"
echo "  - Health Check: http://localhost:8000/health"
echo ""
echo "Useful commands:"
echo "  - View logs: docker-compose logs -f"
echo "  - Stop services: docker-compose down"
echo "  - Restart services: docker-compose restart"
echo ""
echo "For more information, see DOCKER_DEPLOYMENT.md"
