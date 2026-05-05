# VMLedger Installation Guide

This guide will walk you through setting up VMLedger for development and production use.

## Prerequisites

### Required Software

- **Python 3.11+**: [Download Python](https://www.python.org/downloads/)
- **PostgreSQL 15+**: [Download PostgreSQL](https://www.postgresql.org/download/)
- **Redis 7+**: [Download Redis](https://redis.io/download/)

### Optional Software

- **Docker & Docker Compose**: For containerized development
- **Git**: For version control

## Quick Start (Development)

### Option 1: Automated Setup (Recommended)

#### Windows (PowerShell)
```powershell
.\scripts\setup.ps1
```

#### Linux/macOS
```bash
chmod +x scripts/setup.sh
./scripts/setup.sh
```

### Option 2: Manual Setup

#### 1. Clone Repository
```bash
git clone <repository-url>
cd VMLedger
```

#### 2. Create Virtual Environment
```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Linux/macOS
python3 -m venv venv
source venv/bin/activate
```

#### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

#### 4. Configure Environment
```bash
# Copy example configuration
cp .env.example .env

# Generate secure keys
python -c "import secrets; print('SECRET_KEY=' + secrets.token_hex(32))"
python -c "import secrets; print('ENCRYPTION_MASTER_KEY=' + secrets.token_hex(32))"

# Edit .env and set the generated keys plus database/redis URLs
```

#### 5. Set Up Database

**Using Docker (Easiest):**
```bash
docker-compose up -d postgres redis
```

**Manual PostgreSQL Setup:**
```sql
-- Connect to PostgreSQL as superuser
CREATE DATABASE vmledger;
CREATE USER vmledger WITH PASSWORD 'your_secure_password';
GRANT ALL PRIVILEGES ON DATABASE vmledger TO vmledger;
```

Update `.env`:
```
DATABASE_URL=postgresql://vmledger:your_secure_password@localhost:5432/vmledger
```

**Manual Redis Setup:**
```bash
# Start Redis server
redis-server

# Or with password
redis-server --requirepass your_redis_password
```

Update `.env`:
```
REDIS_URL=redis://localhost:6379/0
# If using password:
REDIS_PASSWORD=your_redis_password
```

#### 6. Initialize Database
```bash
# Run migrations
alembic upgrade head

# Or use the initialization script (recommended)
python scripts/init_database.py
```

**Common Alembic commands:**
```bash
# Check current migration version
alembic current

# Show migration history
alembic history

# Upgrade to latest version
alembic upgrade head

# Downgrade one revision
alembic downgrade -1

# Downgrade to specific revision
alembic downgrade <revision_id>

# Create new migration (after model changes)
alembic revision --autogenerate -m "Description"
```

#### 7. Verify Setup
```bash
python scripts/verify_setup.py
```

## Running the Application

### Development Mode

You need to run three processes:

**Terminal 1 - API Server:**
```bash
uvicorn vmledger.main:app --host 0.0.0.0 --port 8000 --reload
```

**Terminal 2 - Celery Worker:**
```bash
celery -A vmledger.celery_app worker --loglevel=info --concurrency=10
```

**Terminal 3 - Celery Beat:**
```bash
celery -A vmledger.celery_app beat --loglevel=info
```

Or use the Makefile:
```bash
# Terminal 1
make dev

# Terminal 2
make worker

# Terminal 3
make beat
```

### Access the Application

- **API**: http://localhost:8000
- **API Docs**: http://localhost:8000/api/docs
- **Health Check**: http://localhost:8000/health

## Docker Deployment

### Development with Docker

```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

### Production Docker Setup

1. Create `docker-compose.prod.yml` (to be implemented in Task 20)
2. Set production environment variables
3. Use proper secrets management
4. Enable HTTPS with reverse proxy (Nginx)

## Configuration

### Required Environment Variables

```bash
# Security (REQUIRED - Generate unique values)
SECRET_KEY=<generate-with-secrets.token_hex(32)>
ENCRYPTION_MASTER_KEY=<generate-with-secrets.token_hex(32)>

# Database (REQUIRED)
DATABASE_URL=postgresql://user:password@host:5432/dbname

# Redis (REQUIRED)
REDIS_URL=redis://host:6379/0
```

### Optional Configuration

See `.env.example` for all available options including:
- Monitoring intervals
- SSH timeouts
- Data retention policies
- Email/SMTP settings
- CORS settings
- Logging configuration

## Testing

### Run All Tests
```bash
pytest
```

### Run Specific Test Types
```bash
# Unit tests
pytest tests/unit/

# Property-based tests
pytest tests/properties/

# Integration tests
pytest tests/integration/
```

### Run with Coverage
```bash
pytest --cov=vmledger --cov-report=html
# Open htmlcov/index.html in browser
```

## Database Management

### Migrations

VMLedger uses Alembic for database schema migrations.

**Check migration status:**
```bash
alembic current
alembic history
```

**Apply migrations:**
```bash
# Upgrade to latest
alembic upgrade head

# Upgrade to specific revision
alembic upgrade <revision_id>

# Downgrade one revision
alembic downgrade -1

# Downgrade to specific revision
alembic downgrade <revision_id>
```

**Create new migration:**
```bash
# Auto-generate from model changes
alembic revision --autogenerate -m "Add new column to users table"

# Create empty migration
alembic revision -m "Custom migration"
```

**Initialize database:**
```bash
# Using initialization script (recommended)
python scripts/init_database.py

# Reset database (WARNING: destroys all data)
python scripts/init_database.py --reset
```

### Backups

**Create backup:**
```bash
# Using backup script (recommended)
python scripts/backup_database.py

# Custom output directory
python scripts/backup_database.py --output-dir /path/to/backups

# With automatic cleanup of old backups
python scripts/backup_database.py --cleanup --retention 30
```

**List backups:**
```bash
python scripts/backup_database.py --list
```

**Backup formats:**
```bash
# Custom format (default, compressed, supports selective restore)
python scripts/backup_database.py --format custom

# Plain SQL (human-readable)
python scripts/backup_database.py --format plain

# Directory format (one file per table)
python scripts/backup_database.py --format directory

# Tar archive
python scripts/backup_database.py --format tar
```

**Manual backup using pg_dump:**
```bash
pg_dump -h localhost -U vmledger -d vmledger -F c -f backup.dump
```

**Restore from backup:**
```bash
# Custom format
pg_restore -h localhost -U vmledger -d vmledger -c backup.dump

# Plain SQL
psql -h localhost -U vmledger -d vmledger -f backup.sql

# Using script (shows restore instructions)
python scripts/backup_database.py --list
```

**Automated backups:**
```bash
# Linux/macOS cron (daily at 2 AM)
0 2 * * * cd /path/to/vmledger && python scripts/backup_database.py --cleanup --retention 30

# Windows Task Scheduler
# Create task to run: python scripts/backup_database.py --cleanup --retention 30
```

### Database Maintenance

**Check connection:**
```bash
python -c "from vmledger.database import check_db_connection; print('Connected' if check_db_connection() else 'Failed')"
```

**Check pool status:**
```bash
python -c "from vmledger.database import get_pool_status; import json; print(json.dumps(get_pool_status(), indent=2))"
```

**Vacuum database (PostgreSQL maintenance):**
```bash
psql -h localhost -U vmledger -d vmledger -c "VACUUM ANALYZE;"
```

**Check database size:**
```bash
psql -h localhost -U vmledger -d vmledger -c "SELECT pg_size_pretty(pg_database_size('vmledger'));"
```

## Troubleshooting

### Import Errors

**Problem**: `ModuleNotFoundError: No module named 'pydantic_settings'`

**Solution**: Ensure virtual environment is activated and dependencies are installed:
```bash
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -r requirements.txt
```

### Database Connection Errors

**Problem**: `could not connect to server: Connection refused`

**Solution**: 
1. Ensure PostgreSQL is running
2. Check DATABASE_URL in .env
3. Verify PostgreSQL is listening on correct port
4. Check firewall settings

### Redis Connection Errors

**Problem**: `Error connecting to Redis`

**Solution**:
1. Ensure Redis is running: `redis-cli ping` (should return PONG)
2. Check REDIS_URL in .env
3. If using password, ensure REDIS_PASSWORD is set

### Configuration Validation Errors

**Problem**: `Configuration validation failed: SECRET_KEY must be set`

**Solution**: Generate and set secure keys in .env:
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

### Port Already in Use

**Problem**: `Address already in use: 8000`

**Solution**: 
1. Find process using port: `lsof -i :8000` (Linux/macOS) or `netstat -ano | findstr :8000` (Windows)
2. Kill the process or use different port: `uvicorn vmledger.main:app --port 8001`

## Production Deployment

### Security Checklist

- [ ] Generate unique SECRET_KEY and ENCRYPTION_MASTER_KEY
- [ ] Use strong database passwords
- [ ] Enable Redis password authentication
- [ ] Set DEBUG=False
- [ ] Configure HTTPS/TLS
- [ ] Set up firewall rules
- [ ] Enable database connection encryption
- [ ] Configure proper CORS origins
- [ ] Set up log rotation
- [ ] Enable rate limiting
- [ ] Regular security updates

### Performance Tuning

- [ ] Adjust DATABASE_POOL_SIZE based on load
- [ ] Configure CONCURRENT_WORKERS for VM count
- [ ] Set up database read replicas
- [ ] Enable Redis persistence
- [ ] Configure Nginx reverse proxy
- [ ] Set up monitoring (Prometheus/Grafana)

### Monitoring

- [ ] Set up application monitoring
- [ ] Configure log aggregation
- [ ] Set up alerting for errors
- [ ] Monitor database performance
- [ ] Monitor Celery queue length
- [ ] Track API response times

## Next Steps

After installation:

1. **Create Admin User** (once implemented)
2. **Register First VM** (once implemented)
3. **Configure Alerts** (once implemented)
4. **Set Up Monitoring Dashboard** (once implemented)

## Getting Help

- Check logs in `logs/vmledger.log`
- Review API documentation at `/api/docs`
- Check database connection: `python -c "from vmledger.database import check_db_connection; print(check_db_connection())"`
- Verify configuration: `python scripts/verify_setup.py`

## Development Workflow

1. Create feature branch
2. Make changes
3. Run tests: `pytest`
4. Run linters: `make lint`
5. Format code: `make format`
6. Commit changes
7. Create pull request

## Uninstallation

```bash
# Stop services
docker-compose down -v  # If using Docker

# Remove virtual environment
rm -rf venv

# Remove database (if desired)
dropdb vmledger  # PostgreSQL

# Remove logs
rm -rf logs/
```
