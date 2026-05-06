# Docker Deployment Guide

This guide covers deploying VMLedger using Docker and Docker Compose for both development and production environments.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Architecture](#architecture)
- [Development Deployment](#development-deployment)
- [Production Deployment](#production-deployment)
- [Container Management](#container-management)
- [Troubleshooting](#troubleshooting)

## Prerequisites

- Docker Engine 20.10+ installed
- Docker Compose 2.0+ installed
- At least 4GB RAM available
- At least 10GB disk space

### Install Docker

**Linux:**
```bash
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER
```

**macOS/Windows:**
Install Docker Desktop from https://www.docker.com/products/docker-desktop

## Architecture

The VMLedger Docker deployment consists of 5 containers:

1. **postgres** - PostgreSQL 15 database
2. **redis** - Redis 7 cache and message broker
3. **api** - FastAPI application server
4. **celery-worker** - Background task workers
5. **celery-beat** - Periodic task scheduler

```
┌─────────────┐
│   Browser   │
└──────┬──────┘
       │
       ▼
┌─────────────┐     ┌──────────────┐
│  FastAPI    │────▶│  PostgreSQL  │
│  (Port 8000)│     │  (Port 5432) │
└──────┬──────┘     └──────────────┘
       │
       │            ┌──────────────┐
       └───────────▶│    Redis     │
                    │  (Port 6379) │
                    └──────┬───────┘
                           │
       ┌───────────────────┴───────────────────┐
       │                                       │
       ▼                                       ▼
┌─────────────┐                        ┌─────────────┐
│   Celery    │                        │   Celery    │
│   Worker    │                        │    Beat     │
└─────────────┘                        └─────────────┘
```

## Development Deployment

### Quick Start

1. **Clone the repository:**
   ```bash
   git clone <repository-url>
   cd vmledger
   ```

2. **Start all services:**
   ```bash
   docker-compose up -d
   ```

3. **Run database migrations:**
   ```bash
   docker-compose exec api alembic upgrade head
   ```
   
   **Alternative: Use the initialization script:**
   ```bash
   docker-compose exec api python scripts/init_database.py
   ```

4. **Access the application:**
   - API: http://localhost:8000
   - API Docs: http://localhost:8000/api/docs
   - Health Check: http://localhost:8000/health

### Development Features

- **Hot Reload**: Code changes automatically reload the API
- **Volume Mounts**: Source code is mounted for live editing
- **Debug Mode**: Detailed error messages and API documentation enabled
- **Exposed Ports**: All services accessible on localhost

### Viewing Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f api
docker-compose logs -f celery-worker
docker-compose logs -f celery-beat
```

### Stopping Services

```bash
# Stop all services
docker-compose down

# Stop and remove volumes (WARNING: deletes all data)
docker-compose down -v
```

## Production Deployment

### Initial Setup

1. **Create production environment file:**
   ```bash
   cp .env.production.example .env.production
   ```

2. **Edit `.env.production` and set secure values:**
   ```bash
   # Generate strong keys
   python -c "import secrets; print('SECRET_KEY=' + secrets.token_urlsafe(32))"
   python -c "import secrets; print('ENCRYPTION_MASTER_KEY=' + secrets.token_urlsafe(32))"
   python -c "import secrets; print('POSTGRES_PASSWORD=' + secrets.token_urlsafe(32))"
   python -c "import secrets; print('REDIS_PASSWORD=' + secrets.token_urlsafe(32))"
   ```

3. **Update CORS origins:**
   ```bash
   # In .env.production
   CORS_ORIGINS=https://your-domain.com,https://www.your-domain.com
   ```

### Deploy to Production

1. **Build and start services:**
   ```bash
   docker-compose -f docker-compose.prod.yml --env-file .env.production up -d --build
   ```

2. **Run database migrations:**
   ```bash
   docker-compose -f docker-compose.prod.yml exec api alembic upgrade head
   ```
   
   **Alternative: Use the initialization script:**
   ```bash
   docker-compose -f docker-compose.prod.yml exec api python scripts/init_database.py
   ```

3. **Verify deployment:**
   ```bash
   docker-compose -f docker-compose.prod.yml ps
   curl http://localhost:8000/health
   ```

### Production Features

- **No Hot Reload**: Stable production builds
- **No Volume Mounts**: Code baked into image
- **Production Mode**: Debug disabled, optimized logging
- **Resource Limits**: CPU and memory constraints
- **Health Checks**: Automatic container restart on failure
- **Password Protection**: Redis requires authentication

### SSL/TLS Configuration

For production, use a reverse proxy (Nginx/Traefik) for SSL termination:

**Example Nginx configuration:**
```nginx
server {
    listen 443 ssl http2;
    server_name your-domain.com;

    ssl_certificate /etc/ssl/certs/your-cert.pem;
    ssl_certificate_key /etc/ssl/private/your-key.pem;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

## Container Management

### Database Migrations

VMLedger uses Alembic for database schema migrations. This section covers common migration operations.

#### Running Migrations

**Upgrade to latest version:**
```bash
# Development
docker-compose exec api alembic upgrade head

# Production
docker-compose -f docker-compose.prod.yml exec api alembic upgrade head
```

**Upgrade to specific revision:**
```bash
docker-compose exec api alembic upgrade <revision_id>
```

**Downgrade to previous revision:**
```bash
docker-compose exec api alembic downgrade -1
```

**Downgrade to specific revision:**
```bash
docker-compose exec api alembic downgrade <revision_id>
```

**Downgrade to base (remove all migrations):**
```bash
# WARNING: This will drop all tables
docker-compose exec api alembic downgrade base
```

#### Checking Migration Status

**Show current revision:**
```bash
docker-compose exec api alembic current
```

**Show migration history:**
```bash
docker-compose exec api alembic history
```

**Show pending migrations:**
```bash
docker-compose exec api alembic heads
```

#### Creating New Migrations

**Auto-generate migration from model changes:**
```bash
docker-compose exec api alembic revision --autogenerate -m "Description of changes"
```

**Create empty migration:**
```bash
docker-compose exec api alembic revision -m "Description of changes"
```

#### Database Initialization

**Initialize database with all tables:**
```bash
# Development
docker-compose exec api python scripts/init_database.py

# Production
docker-compose -f docker-compose.prod.yml exec api python scripts/init_database.py
```

**Reset database (WARNING: destroys all data):**
```bash
docker-compose exec api python scripts/init_database.py --reset
```

#### Migration Best Practices

1. **Always backup before migrations** in production
2. **Test migrations** in development/staging first
3. **Review auto-generated migrations** before applying
4. **Never edit applied migrations** - create new ones instead
5. **Keep migrations small** and focused on single changes
6. **Document breaking changes** in migration messages

### Scaling Workers

Increase Celery worker concurrency:

```bash
# Development
docker-compose up -d --scale celery-worker=3

# Production
docker-compose -f docker-compose.prod.yml up -d --scale celery-worker=3
```

Or adjust `CONCURRENT_WORKERS` in environment file.

### Database Backups

#### Creating Backups

**Using the backup script (recommended):**
```bash
# Development
docker-compose exec api python scripts/backup_database.py

# Production
docker-compose -f docker-compose.prod.yml exec api python scripts/backup_database.py --output-dir /backups
```

**Backup with cleanup (remove backups older than 7 days):**
```bash
docker-compose exec api python scripts/backup_database.py --cleanup --retention 7
```

**List existing backups:**
```bash
docker-compose exec api python scripts/backup_database.py --list
```

**Manual backup using pg_dump:**
```bash
docker-compose exec postgres pg_dump -U vmledger vmledger > backup_$(date +%Y%m%d_%H%M%S).sql
```

**Restore backup:**
```bash
cat backup_20240115_120000.sql | docker-compose exec -T postgres psql -U vmledger vmledger
```

**Production backup with docker-compose.prod.yml:**
```bash
docker-compose -f docker-compose.prod.yml exec postgres pg_dump -U vmledger vmledger > /backups/backup_$(date +%Y%m%d_%H%M%S).sql
```

#### Backup Formats

The backup script supports multiple formats:

**Custom format (default, recommended):**
```bash
docker-compose exec api python scripts/backup_database.py --format custom
```
- Compressed by default
- Supports selective restore
- Best for production

**Plain SQL format:**
```bash
docker-compose exec api python scripts/backup_database.py --format plain
```
- Human-readable SQL
- Easy to inspect and edit
- Good for development

**Directory format:**
```bash
docker-compose exec api python scripts/backup_database.py --format directory
```
- One file per table
- Supports parallel restore
- Good for large databases

**Tar format:**
```bash
docker-compose exec api python scripts/backup_database.py --format tar
```
- Compressed archive
- Portable format

#### Restoring from Backup

**Restore from custom format:**
```bash
# Stop services first
docker-compose down

# Start only database
docker-compose up -d postgres

# Restore
docker-compose exec -T postgres pg_restore -U vmledger -d vmledger -c backup.dump

# Start all services
docker-compose up -d
```

**Restore from plain SQL:**
```bash
docker-compose exec -T postgres psql -U vmledger -d vmledger -f backup.sql
```

**Restore from compressed backup:**
```bash
gunzip backup.dump.gz
docker-compose exec -T postgres pg_restore -U vmledger -d vmledger -c backup.dump
```

#### Automated Backup Schedule

**Set up cron job for daily backups (Linux/macOS):**
```bash
# Edit crontab
crontab -e

# Add daily backup at 2 AM with 30-day retention
0 2 * * * cd /path/to/vmledger && docker-compose exec -T api python scripts/backup_database.py --cleanup --retention 30 >> /var/log/vmledger-backup.log 2>&1
```

**Windows Task Scheduler:**
```powershell
# Create scheduled task for daily backup
$action = New-ScheduledTaskAction -Execute "docker-compose" -Argument "exec -T api python scripts/backup_database.py --cleanup --retention 30"
$trigger = New-ScheduledTaskTrigger -Daily -At 2am
Register-ScheduledTask -Action $action -Trigger $trigger -TaskName "VMLedger Backup" -Description "Daily VMLedger database backup"
```

#### Backup Best Practices

1. **Backup before migrations** - Always create backup before schema changes
2. **Test restores regularly** - Verify backups can be restored successfully
3. **Store offsite** - Keep backups in different location from database
4. **Encrypt sensitive backups** - Use encryption for production backups
5. **Monitor backup size** - Track backup growth over time
6. **Automate backups** - Use cron/scheduler for regular backups
7. **Document restore procedures** - Keep restore instructions accessible
8. **Retain multiple versions** - Keep at least 30 days of backups

### Monitoring Container Health

```bash
# Check container status
docker-compose ps

# Check resource usage
docker stats

# Check health status
docker inspect --format='{{.State.Health.Status}}' vmledger-api
```

### Updating Application

**Development:**
```bash
docker-compose down
git pull
docker-compose up -d --build
docker-compose exec api alembic upgrade head
```

**Production:**
```bash
docker-compose -f docker-compose.prod.yml down
git pull
docker-compose -f docker-compose.prod.yml up -d --build
docker-compose -f docker-compose.prod.yml exec api alembic upgrade head
```

## Troubleshooting

### Container Won't Start

**Check logs:**
```bash
docker-compose logs <service-name>
```

**Common issues:**
- Database not ready: Wait for health check to pass
- Port already in use: Change port in docker-compose.yml
- Permission denied: Check file permissions and user

### Database Connection Failed

**Verify PostgreSQL is running:**
```bash
docker-compose ps postgres
docker-compose exec postgres pg_isready -U vmledger
```

**Check connection string:**
```bash
docker-compose exec api env | grep DATABASE_URL
```

### Redis Connection Failed

**Verify Redis is running:**
```bash
docker-compose ps redis
docker-compose exec redis redis-cli ping
```

**Production (with password):**
```bash
docker-compose -f docker-compose.prod.yml exec redis redis-cli -a $REDIS_PASSWORD ping
```

### Celery Tasks Not Running

**Check worker status:**
```bash
docker-compose exec celery-worker celery -A vmledger.celery_app inspect active
docker-compose exec celery-worker celery -A vmledger.celery_app inspect stats
```

**Check beat scheduler:**
```bash
docker-compose logs celery-beat | grep "Scheduler:"
```

### High Memory Usage

**Check container stats:**
```bash
docker stats
```

**Adjust resource limits in docker-compose.prod.yml:**
```yaml
deploy:
  resources:
    limits:
      memory: 1G
```

### Logs Not Appearing

**Check volume mount:**
```bash
docker-compose exec api ls -la /app/logs
```

**Check log file permissions:**
```bash
ls -la logs/
```

### Network Issues Between Containers

**Verify network:**
```bash
docker network ls
docker network inspect vmledger_vmledger-network
```

**Test connectivity:**
```bash
docker-compose exec api ping postgres
docker-compose exec api ping redis
```

## Security Best Practices

1. **Never commit `.env.production` to version control**
2. **Use strong, unique passwords for all services**
3. **Regularly update Docker images**: `docker-compose pull`
4. **Enable firewall rules** to restrict access to ports
5. **Use SSL/TLS** with a reverse proxy in production
6. **Regularly backup database** and store offsite
7. **Monitor logs** for suspicious activity
8. **Keep Docker and Docker Compose updated**

## Performance Tuning

### Database Optimization

```yaml
# In docker-compose.prod.yml, add to postgres environment:
POSTGRES_SHARED_BUFFERS: 256MB
POSTGRES_EFFECTIVE_CACHE_SIZE: 1GB
POSTGRES_WORK_MEM: 16MB
```

### Redis Optimization

```yaml
# In docker-compose.prod.yml, add to redis command:
command: redis-server --maxmemory 512mb --maxmemory-policy allkeys-lru
```

### API Workers

Adjust based on CPU cores:
```bash
# In .env.production
API_WORKERS=4  # Typically (2 x CPU cores) + 1
```

## Additional Resources

- [Docker Documentation](https://docs.docker.com/)
- [Docker Compose Documentation](https://docs.docker.com/compose/)
- [FastAPI Deployment](https://fastapi.tiangolo.com/deployment/)
- [Celery Production Guide](https://docs.celeryproject.org/en/stable/userguide/deployment.html)
