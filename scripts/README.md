# VMLedger Scripts

This directory contains utility scripts for VMLedger setup, database management, and deployment.

## Setup Scripts

### setup.sh / setup.ps1
Automated setup scripts for Linux/macOS and Windows respectively.

**Usage:**
```bash
# Linux/macOS
chmod +x scripts/setup.sh
./scripts/setup.sh

# Windows PowerShell
.\scripts\setup.ps1
```

**What it does:**
- Creates Python virtual environment
- Installs dependencies
- Creates .env file from template
- Generates secure keys
- Checks for PostgreSQL and Redis
- Runs database migrations

### verify_setup.py
Verifies that VMLedger is properly configured and all dependencies are available.

**Usage:**
```bash
python scripts/verify_setup.py
```

**Checks:**
- Python version
- Required packages
- Database connectivity
- Redis connectivity
- Configuration validity
- File permissions

## Database Scripts

### init_database.py
Initialize or reset the VMLedger database.

**Usage:**
```bash
# Initialize database (run migrations)
python scripts/init_database.py

# Reset database (WARNING: destroys all data)
python scripts/init_database.py --reset
```

**Features:**
- Checks database connectivity
- Runs Alembic migrations
- Verifies schema creation
- Creates initial data (if needed)
- Provides next steps guidance

**When to use:**
- First-time setup
- After cloning repository
- After major schema changes
- When database is corrupted (with --reset)

### backup_database.py
Create and manage PostgreSQL database backups.

**Usage:**
```bash
# Create backup with default settings
python scripts/backup_database.py

# Create backup in custom directory
python scripts/backup_database.py --output-dir /backups

# Create backup and clean up old backups
python scripts/backup_database.py --cleanup --retention 30

# List existing backups
python scripts/backup_database.py --list

# Create uncompressed plain SQL backup
python scripts/backup_database.py --no-compress --format plain
```

**Options:**
- `--output-dir DIR`: Backup directory (default: ./backups)
- `--retention DAYS`: Days to retain backups (default: 30)
- `--compress`: Compress with gzip (default: True)
- `--no-compress`: Skip compression
- `--format FORMAT`: Backup format (plain, custom, directory, tar)
- `--cleanup`: Remove old backups
- `--list`: List existing backups

**Backup Formats:**
- **custom** (default): Compressed, supports selective restore, best for production
- **plain**: Human-readable SQL, easy to inspect
- **directory**: One file per table, supports parallel restore
- **tar**: Compressed archive, portable

**Restore Instructions:**
The script provides detailed restore instructions after creating a backup.

**Automated Backups:**
```bash
# Linux/macOS cron (daily at 2 AM)
0 2 * * * cd /path/to/vmledger && python scripts/backup_database.py --cleanup --retention 30

# Windows Task Scheduler
# Create task to run: python scripts/backup_database.py --cleanup --retention 30
```

## Docker Scripts

### docker-quickstart.sh / docker-quickstart.ps1
Quick start scripts for Docker deployment.

**Usage:**
```bash
# Linux/macOS
chmod +x scripts/docker-quickstart.sh
./scripts/docker-quickstart.sh

# Windows PowerShell
.\scripts\docker-quickstart.ps1
```

**What it does:**
- Checks Docker installation
- Creates .env file if missing
- Starts Docker Compose services
- Runs database migrations
- Displays access URLs

## Common Workflows

### First-Time Setup

**Option 1: Native Python**
```bash
# 1. Run setup script
./scripts/setup.sh  # or setup.ps1 on Windows

# 2. Verify setup
python scripts/verify_setup.py

# 3. Initialize database
python scripts/init_database.py
```

**Option 2: Docker**
```bash
# 1. Run Docker quickstart
./scripts/docker-quickstart.sh  # or docker-quickstart.ps1 on Windows

# 2. Initialize database
docker-compose exec api python scripts/init_database.py
```

### Regular Backups

**Manual backup:**
```bash
python scripts/backup_database.py --cleanup --retention 30
```

**Automated backup (cron):**
```bash
# Add to crontab
0 2 * * * cd /path/to/vmledger && python scripts/backup_database.py --cleanup --retention 30 >> /var/log/vmledger-backup.log 2>&1
```

### Database Maintenance

**Check status:**
```bash
python scripts/verify_setup.py
```

**Reset database:**
```bash
python scripts/init_database.py --reset
```

**Restore from backup:**
```bash
# List available backups
python scripts/backup_database.py --list

# Restore (follow instructions from backup script)
pg_restore -h localhost -U vmledger -d vmledger -c backups/vmledger_backup_20240115_120000.dump
```

### Migration Management

**Check migration status:**
```bash
alembic current
alembic history
```

**Apply migrations:**
```bash
alembic upgrade head
```

**Create new migration:**
```bash
alembic revision --autogenerate -m "Description of changes"
```

## Requirements

### Python Scripts
- Python 3.11+
- Virtual environment activated
- Dependencies installed (`pip install -r requirements.txt`)
- .env file configured

### Database Scripts
- PostgreSQL client tools (pg_dump, pg_restore, psql)
- Database credentials in .env
- Network access to database

### Docker Scripts
- Docker Engine 20.10+
- Docker Compose 2.0+
- Sufficient disk space (10GB+)

## Troubleshooting

### Script Permission Denied
```bash
chmod +x scripts/*.sh
```

### Python Module Not Found
```bash
# Ensure virtual environment is activated
source venv/bin/activate  # Linux/macOS
venv\Scripts\activate     # Windows

# Reinstall dependencies
pip install -r requirements.txt
```

### Database Connection Failed
```bash
# Check database is running
pg_isready -h localhost -p 5432

# Check .env configuration
cat .env | grep DATABASE_URL

# Test connection
python -c "from vmledger.database import check_db_connection; print(check_db_connection())"
```

### pg_dump Not Found
```bash
# Ubuntu/Debian
sudo apt-get install postgresql-client

# macOS
brew install postgresql

# Windows
# Install from https://www.postgresql.org/download/windows/
```

### Backup Failed
```bash
# Check disk space
df -h

# Check permissions
ls -la backups/

# Check database connectivity
psql -h localhost -U vmledger -d vmledger -c "SELECT 1"
```

## Best Practices

1. **Always backup before migrations** in production
2. **Test scripts in development** before using in production
3. **Keep backups offsite** for disaster recovery
4. **Automate regular backups** using cron/scheduler
5. **Monitor script execution** and log outputs
6. **Document custom modifications** to scripts
7. **Review generated migrations** before applying
8. **Test restore procedures** regularly

## Contributing

When adding new scripts:
1. Add usage documentation to this README
2. Include help text in the script (`--help`)
3. Add error handling and logging
4. Test on multiple platforms if applicable
5. Update related documentation (INSTALLATION.md, DOCKER_DEPLOYMENT.md)
