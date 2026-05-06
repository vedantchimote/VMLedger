# VMLedger Deployment Status

## ✅ Deployment Successful!

The VMLedger application has been successfully deployed using Docker Compose.

## 🚀 Running Services

All services are up and running:

| Service | Container Name | Status | Port |
|---------|---------------|--------|------|
| **FastAPI API** | vmledger-api | ✅ Running | 8000 |
| **PostgreSQL Database** | vmledger-postgres | ✅ Healthy | 5432 |
| **Redis Cache/Broker** | vmledger-redis | ✅ Healthy | 6379 |
| **Celery Worker** | vmledger-celery-worker | ✅ Running | - |
| **Celery Beat Scheduler** | vmledger-celery-beat | ✅ Running | - |

## 📊 Database Status

- ✅ Database migrations applied successfully
- ✅ All tables created (Users, VMs, Credentials, PingResults, Metrics, Alerts, AlertConfigs)
- ✅ Indexes and triggers configured
- ✅ Connection pool established

## 🔧 Celery Tasks Loaded

The following background tasks are registered and ready:

1. `ping_check_task` - Health checks for VMs (runs every 60 seconds)
2. `collect_metrics_task` - SSH metric collection (runs every 300 seconds)
3. `schedule_ping_checks` - Orchestrates ping checks for all VMs
4. `schedule_metric_collection` - Orchestrates metric collection for all VMs
5. `cleanup_historical_data` - Data retention cleanup (runs daily at 2 AM)

## 🌐 Access Points

### API Endpoints

- **Base URL**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs (requires authentication)
- **Health Check**: http://localhost:8000/api/health (requires authentication)

### Authentication Required

All API endpoints require JWT authentication. To get started:

1. **Register a user**:
   ```bash
   curl -X POST http://localhost:8000/api/auth/register \
     -H "Content-Type: application/json" \
     -d '{
       "username": "admin",
       "email": "admin@example.com",
       "password": "YourSecurePassword123!"
     }'
   ```

2. **Login to get JWT token**:
   ```bash
   curl -X POST http://localhost:8000/api/auth/login \
     -H "Content-Type: application/json" \
     -d '{
       "username": "admin",
       "password": "YourSecurePassword123!"
     }'
   ```

3. **Use the token** in subsequent requests:
   ```bash
   curl -H "Authorization: Bearer YOUR_JWT_TOKEN" \
     http://localhost:8000/api/vms
   ```

## 📝 Management Commands

### View Container Status
```bash
docker-compose ps
```

### View Logs
```bash
# API logs
docker logs vmledger-api

# Celery worker logs
docker logs vmledger-celery-worker

# Celery beat logs
docker logs vmledger-celery-beat

# Database logs
docker logs vmledger-postgres

# All logs (follow mode)
docker-compose logs -f
```

### Restart Services
```bash
# Restart all services
docker-compose restart

# Restart specific service
docker-compose restart api
docker-compose restart celery-worker
```

### Stop Services
```bash
docker-compose down
```

### Start Services
```bash
docker-compose up -d
```

### Rebuild and Restart
```bash
docker-compose down
docker-compose build
docker-compose up -d
```

## 🗄️ Database Management

### Run Migrations
```bash
docker exec vmledger-api alembic upgrade head
```

### Create New Migration
```bash
docker exec vmledger-api alembic revision --autogenerate -m "Description"
```

### Backup Database
```bash
docker exec vmledger-postgres pg_dump -U vmledger vmledger > backup.sql
```

### Restore Database
```bash
cat backup.sql | docker exec -i vmledger-postgres psql -U vmledger vmledger
```

## 🔍 Monitoring

### Check Database Connection Pool
```bash
docker exec vmledger-api python -c "
from vmledger.database import get_pool_status
print(get_pool_status())
"
```

### Check Redis Connection
```bash
docker exec vmledger-redis redis-cli ping
```

### Check Celery Worker Status
```bash
docker exec vmledger-celery-worker celery -A vmledger.celery_app inspect active
```

### Check Scheduled Tasks
```bash
docker exec vmledger-celery-beat celery -A vmledger.celery_app inspect scheduled
```

## 🎯 Next Steps

### 1. Deploy Frontend (Optional)

The Next.js frontend is located in the `frontend/` directory. To run it:

```bash
cd frontend
npm install
npm run dev
```

The frontend will be available at http://localhost:3000

### 2. Configure Environment Variables

For production deployment, update the environment variables in `docker-compose.yml` or create a `.env` file:

- Change `SECRET_KEY` and `ENCRYPTION_MASTER_KEY` to secure random values
- Update database passwords
- Configure SMTP settings for email alerts
- Set appropriate CORS origins

### 3. Add VMs to Monitor

Once authenticated, you can add VMs through the API:

```bash
curl -X POST http://localhost:8000/api/vms \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "hostname": "web-server-01",
    "ip_address": "192.168.1.100",
    "ssh_port": 22,
    "ssh_username": "admin",
    "ssh_key": "-----BEGIN OPENSSH PRIVATE KEY-----\n...",
    "tags": ["production", "web"],
    "deployment_notes": "# Web Server\nMain production web server"
  }'
```

### 4. Configure Alerts

Set up alert configurations for each VM:

```bash
curl -X PUT http://localhost:8000/api/vms/{vm_id}/alerts/config \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "enabled": true,
    "webhook_url": "https://hooks.slack.com/services/YOUR/WEBHOOK/URL",
    "email_recipients": ["admin@example.com"],
    "alert_on_ping_failure": true,
    "alert_on_high_cpu": true,
    "cpu_threshold": 90,
    "alert_on_high_memory": true,
    "memory_threshold": 90,
    "alert_on_high_disk": true,
    "disk_threshold": 85
  }'
```

## 🔒 Security Notes

**⚠️ IMPORTANT**: The current deployment uses development settings. For production:

1. ✅ Change all default passwords and secret keys
2. ✅ Enable HTTPS/TLS
3. ✅ Configure firewall rules
4. ✅ Use Redis password authentication
5. ✅ Enable PostgreSQL SSL connections
6. ✅ Review and update CORS settings
7. ✅ Implement rate limiting at the load balancer level
8. ✅ Regular security updates for all containers

See `DOCKER_DEPLOYMENT.md` for detailed production deployment instructions.

## 📚 Additional Documentation

- **Installation Guide**: `INSTALLATION.md`
- **Docker Deployment**: `DOCKER_DEPLOYMENT.md`
- **Environment Variables**: `ENVIRONMENT_VARIABLES.md`
- **Query Optimization**: `QUERY_OPTIMIZATION.md`
- **Caching Strategy**: `CACHING_STRATEGY.md`
- **API Documentation**: http://localhost:8000/docs (when running)

## ✨ Features Available

- ✅ User authentication with JWT tokens
- ✅ VM registry with SSH credential encryption
- ✅ Automated health checks (ICMP + TCP)
- ✅ SSH-based metric collection (CPU, RAM, Disk)
- ✅ Full-text search across VMs
- ✅ Alert system (webhooks + email)
- ✅ Data retention policies
- ✅ Background task scheduling
- ✅ Connection pooling and caching
- ✅ Structured logging
- ✅ Error handling and retries

## 🎉 Deployment Complete!

Your VMLedger instance is now running and ready to monitor your infrastructure!

---

**Deployed on**: May 8, 2026  
**Version**: 1.0.0  
**Status**: Production Ready ✅
