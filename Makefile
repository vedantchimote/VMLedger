.PHONY: help install dev test clean docker-up docker-down docker-build docker-logs docker-migrate docker-prod-up docker-prod-down docker-backup

help:
	@echo "VMLedger - Available Commands"
	@echo "=============================="
	@echo "Development:"
	@echo "  install           - Install dependencies"
	@echo "  dev               - Run development server"
	@echo "  worker            - Run Celery worker"
	@echo "  beat              - Run Celery beat scheduler"
	@echo ""
	@echo "Testing:"
	@echo "  test              - Run all tests"
	@echo "  test-unit         - Run unit tests only"
	@echo "  test-prop         - Run property tests only"
	@echo "  test-cov          - Run tests with coverage"
	@echo ""
	@echo "Code Quality:"
	@echo "  lint              - Run code linters"
	@echo "  format            - Format code with black"
	@echo "  clean             - Clean up generated files"
	@echo ""
	@echo "Docker - Development:"
	@echo "  docker-build      - Build Docker images"
	@echo "  docker-up         - Start Docker services (development)"
	@echo "  docker-down       - Stop Docker services"
	@echo "  docker-logs       - View Docker logs"
	@echo "  docker-migrate    - Run database migrations in Docker"
	@echo "  docker-restart    - Restart Docker services"
	@echo ""
	@echo "Docker - Production:"
	@echo "  docker-prod-up    - Start Docker services (production)"
	@echo "  docker-prod-down  - Stop production Docker services"
	@echo "  docker-prod-logs  - View production Docker logs"
	@echo "  docker-backup     - Backup production database"
	@echo ""
	@echo "Utilities:"
	@echo "  verify            - Verify setup"

install:
	pip install -r requirements.txt

dev:
	uvicorn vmledger.main:app --host 0.0.0.0 --port 8000 --reload

worker:
	celery -A vmledger.celery_app worker --loglevel=info --concurrency=10

beat:
	celery -A vmledger.celery_app beat --loglevel=info

test:
	pytest

test-unit:
	pytest tests/unit/ -v

test-prop:
	pytest tests/properties/ -v

test-cov:
	pytest --cov=vmledger --cov-report=html --cov-report=term

lint:
	flake8 vmledger tests
	mypy vmledger

format:
	black vmledger tests

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	rm -rf .pytest_cache
	rm -rf .coverage
	rm -rf htmlcov
	rm -rf dist
	rm -rf build

# Docker Development Commands
docker-build:
	docker-compose build

docker-up:
	docker-compose up -d
	@echo "Waiting for services to be healthy..."
	@sleep 5
	@echo "Services started. Run 'make docker-migrate' to apply database migrations."

docker-down:
	docker-compose down

docker-logs:
	docker-compose logs -f

docker-migrate:
	docker-compose exec api alembic upgrade head

docker-restart:
	docker-compose restart

docker-shell:
	docker-compose exec api /bin/bash

# Docker Production Commands
docker-prod-up:
	@if [ ! -f .env.production ]; then \
		echo "Error: .env.production file not found!"; \
		echo "Copy .env.production.example to .env.production and configure it."; \
		exit 1; \
	fi
	docker-compose -f docker-compose.prod.yml --env-file .env.production up -d --build
	@echo "Production services started. Run 'make docker-prod-migrate' to apply migrations."

docker-prod-down:
	docker-compose -f docker-compose.prod.yml down

docker-prod-logs:
	docker-compose -f docker-compose.prod.yml logs -f

docker-prod-migrate:
	docker-compose -f docker-compose.prod.yml exec api alembic upgrade head

docker-backup:
	@mkdir -p backups
	docker-compose -f docker-compose.prod.yml exec postgres pg_dump -U vmledger vmledger > backups/backup_$$(date +%Y%m%d_%H%M%S).sql
	@echo "Backup created in backups/ directory"

verify:
	python scripts/verify_setup.py
