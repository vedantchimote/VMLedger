# Alembic Database Migrations

This directory contains Alembic database migration scripts for VMLedger.

## Overview

Alembic is a database migration tool for SQLAlchemy. It allows you to:
- Create and manage database schema changes
- Track database version history
- Upgrade and downgrade database schemas
- Generate migrations automatically from model changes

## Configuration

The Alembic configuration is stored in `alembic.ini` at the project root. The database URL is loaded from the `DATABASE_URL` environment variable via `vmledger.config.settings`.

## Usage

### Prerequisites

Ensure you have:
1. PostgreSQL running and accessible
2. Environment variables configured (see `.env.example`)
3. Dependencies installed: `pip install -r requirements.txt`

### Apply Migrations

To upgrade your database to the latest version:

```bash
# Using alembic directly
alembic upgrade head

# Or using python -m
python -m alembic upgrade head
```

### Rollback Migrations

To downgrade to a previous version:

```bash
# Downgrade one revision
alembic downgrade -1

# Downgrade to a specific revision
alembic downgrade <revision_id>

# Downgrade all the way
alembic downgrade base
```

### Check Current Version

To see the current database version:

```bash
alembic current
```

### View Migration History

To see all available migrations:

```bash
alembic history
```

### Create New Migrations

When you modify SQLAlchemy models, create a new migration:

```bash
# Auto-generate migration from model changes
alembic revision --autogenerate -m "Description of changes"

# Create empty migration (for manual changes)
alembic revision -m "Description of changes"
```

**Important:** Always review auto-generated migrations before applying them!

## Migration Files

Migration files are stored in `alembic/versions/` and follow this naming pattern:
- `<revision_id>_<description>.py`

Each migration file contains:
- `upgrade()`: Function to apply the migration
- `downgrade()`: Function to rollback the migration
- Revision identifiers for tracking

## Initial Migration

The initial migration (`001_initial_migration.py`) creates:

### Tables
1. **users** - User accounts with authentication data
2. **vms** - Virtual machine registry
3. **credentials** - Encrypted SSH credentials
4. **ping_results** - Health check history
5. **metrics** - Resource usage metrics
6. **alerts** - Alert notification history
7. **alert_configs** - Alert configuration per VM

### Indexes
- Standard B-tree indexes on foreign keys and frequently queried columns
- GIN indexes for full-text search (`search_vector`) and array fields (`tags`)
- Composite indexes for optimized queries

### Triggers
- **tsvector_update_trigger**: Automatically updates the `search_vector` column on VMs table when IP address, hostname, domain, tags, or deployment notes change

### Constraints
- Foreign key constraints with CASCADE delete
- Check constraints for data validation
- Unique constraints for data integrity

## Database Schema Features

### Full-Text Search

The VMs table includes a `search_vector` column (TSVECTOR type) that is automatically maintained by a trigger. This enables fast full-text search across:
- IP addresses (weight A - highest priority)
- Hostnames (weight A)
- Domains (weight B)
- Tags (weight B)
- Deployment notes (weight C - lowest priority)

The GIN index on `search_vector` provides efficient search performance.

### Array Support

The `tags` column uses PostgreSQL's ARRAY type with a GIN index for efficient querying of tag arrays.

### Cascade Deletion

All child tables use `ON DELETE CASCADE` to ensure data consistency when:
- A user is deleted → all their VMs and related data are deleted
- A VM is deleted → all credentials, ping results, metrics, alerts, and alert configs are deleted

## Troubleshooting

### Connection Errors

If you get database connection errors:
1. Ensure PostgreSQL is running
2. Check `DATABASE_URL` in your `.env` file
3. Verify database credentials
4. Check firewall/network settings

### Migration Conflicts

If you have migration conflicts:
1. Check current database version: `alembic current`
2. View migration history: `alembic history`
3. Resolve conflicts by creating a merge migration: `alembic merge -m "merge description" <rev1> <rev2>`

### Reset Database

To completely reset the database (⚠️ **DESTRUCTIVE** - all data will be lost):

```bash
# Downgrade to base
alembic downgrade base

# Upgrade to latest
alembic upgrade head
```

Or drop and recreate the database:

```sql
-- In PostgreSQL
DROP DATABASE vmledger;
CREATE DATABASE vmledger;
```

Then run migrations:

```bash
alembic upgrade head
```

## Best Practices

1. **Always review auto-generated migrations** - Alembic may not detect all changes correctly
2. **Test migrations on a copy of production data** before applying to production
3. **Never modify applied migrations** - Create a new migration instead
4. **Keep migrations small and focused** - One logical change per migration
5. **Write reversible migrations** - Always implement `downgrade()` function
6. **Backup before migrating** - Especially in production environments
7. **Use transactions** - Alembic wraps migrations in transactions by default

## Production Deployment

For production deployments:

1. **Backup the database** before running migrations
2. **Test migrations** on a staging environment first
3. **Plan for downtime** if the migration requires it
4. **Monitor the migration** - Some migrations can take time on large datasets
5. **Have a rollback plan** - Know how to downgrade if needed
6. **Document changes** - Keep track of what each migration does

### Zero-Downtime Migrations

For zero-downtime deployments:
1. Make schema changes backward-compatible
2. Deploy code that works with both old and new schema
3. Run migration
4. Deploy code that uses new schema
5. Remove old schema in a later migration

## Additional Resources

- [Alembic Documentation](https://alembic.sqlalchemy.org/)
- [SQLAlchemy Documentation](https://docs.sqlalchemy.org/)
- [PostgreSQL Documentation](https://www.postgresql.org/docs/)
