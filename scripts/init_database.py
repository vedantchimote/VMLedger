#!/usr/bin/env python3
"""
Database initialization script for VMLedger.

This script:
1. Checks database connectivity
2. Runs Alembic migrations to create/update schema
3. Optionally creates initial data (if needed)
4. Verifies database setup

Usage:
    python scripts/init_database.py [--reset]

Options:
    --reset     Drop all tables and reinitialize (WARNING: destroys all data)
"""

import sys
import os
import argparse
import logging
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import text, inspect
from alembic import command
from alembic.config import Config
from vmledger.database import engine, check_db_connection, Base
from vmledger.config import settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def check_database_connection() -> bool:
    """
    Check if database is accessible.
    
    Returns:
        True if connection successful, False otherwise
    """
    logger.info("Checking database connection...")
    try:
        if check_db_connection():
            logger.info("✓ Database connection successful")
            return True
        else:
            logger.error("✗ Database connection failed")
            return False
    except Exception as e:
        logger.error(f"✗ Database connection error: {e}")
        return False


def get_alembic_config() -> Config:
    """
    Get Alembic configuration.
    
    Returns:
        Alembic Config object
    """
    alembic_ini_path = project_root / "alembic.ini"
    if not alembic_ini_path.exists():
        raise FileNotFoundError(f"alembic.ini not found at {alembic_ini_path}")
    
    alembic_cfg = Config(str(alembic_ini_path))
    alembic_cfg.set_main_option("sqlalchemy.url", settings.database_url)
    return alembic_cfg


def check_migration_status() -> dict:
    """
    Check current migration status.
    
    Returns:
        Dictionary with migration status information
    """
    logger.info("Checking migration status...")
    
    try:
        with engine.connect() as conn:
            # Check if alembic_version table exists
            inspector = inspect(engine)
            tables = inspector.get_table_names()
            
            if 'alembic_version' not in tables:
                logger.info("  No migrations applied yet (alembic_version table not found)")
                return {
                    'initialized': False,
                    'current_revision': None,
                    'tables_exist': len(tables) > 0,
                    'table_count': len(tables)
                }
            
            # Get current revision
            result = conn.execute(text("SELECT version_num FROM alembic_version"))
            row = result.fetchone()
            current_revision = row[0] if row else None
            
            logger.info(f"  Current migration revision: {current_revision}")
            logger.info(f"  Existing tables: {len(tables)}")
            
            return {
                'initialized': True,
                'current_revision': current_revision,
                'tables_exist': len(tables) > 0,
                'table_count': len(tables)
            }
    except Exception as e:
        logger.error(f"  Error checking migration status: {e}")
        return {
            'initialized': False,
            'current_revision': None,
            'tables_exist': False,
            'table_count': 0,
            'error': str(e)
        }


def run_migrations() -> bool:
    """
    Run Alembic migrations to upgrade database to latest version.
    
    Returns:
        True if successful, False otherwise
    """
    logger.info("Running database migrations...")
    
    try:
        alembic_cfg = get_alembic_config()
        command.upgrade(alembic_cfg, "head")
        logger.info("✓ Migrations completed successfully")
        return True
    except Exception as e:
        logger.error(f"✗ Migration failed: {e}")
        return False


def reset_database() -> bool:
    """
    Drop all tables and reset database (WARNING: destroys all data).
    
    Returns:
        True if successful, False otherwise
    """
    logger.warning("⚠ RESETTING DATABASE - ALL DATA WILL BE LOST")
    
    try:
        # Drop all tables
        logger.info("Dropping all tables...")
        Base.metadata.drop_all(bind=engine)
        
        # Drop alembic_version table if it exists
        with engine.connect() as conn:
            conn.execute(text("DROP TABLE IF EXISTS alembic_version CASCADE"))
            conn.commit()
        
        logger.info("✓ Database reset complete")
        return True
    except Exception as e:
        logger.error(f"✗ Database reset failed: {e}")
        return False


def verify_database_schema() -> bool:
    """
    Verify that all expected tables exist.
    
    Returns:
        True if all tables exist, False otherwise
    """
    logger.info("Verifying database schema...")
    
    expected_tables = [
        'users',
        'vms',
        'credentials',
        'ping_results',
        'metrics',
        'alerts',
        'alert_configs',
        'alembic_version'
    ]
    
    try:
        inspector = inspect(engine)
        existing_tables = inspector.get_table_names()
        
        missing_tables = [table for table in expected_tables if table not in existing_tables]
        
        if missing_tables:
            logger.error(f"✗ Missing tables: {', '.join(missing_tables)}")
            return False
        
        logger.info(f"✓ All {len(expected_tables)} expected tables exist")
        
        # Verify indexes on key tables
        logger.info("Verifying indexes...")
        vms_indexes = [idx['name'] for idx in inspector.get_indexes('vms')]
        logger.info(f"  VMs table has {len(vms_indexes)} indexes")
        
        return True
    except Exception as e:
        logger.error(f"✗ Schema verification failed: {e}")
        return False


def create_initial_data() -> bool:
    """
    Create initial data if needed (currently no initial data required).
    
    Returns:
        True if successful, False otherwise
    """
    logger.info("Checking for initial data requirements...")
    
    # Currently no initial data is required for VMLedger
    # Users register their own accounts and VMs
    # This function is a placeholder for future requirements
    
    logger.info("  No initial data required")
    return True


def main():
    """Main initialization function."""
    parser = argparse.ArgumentParser(
        description='Initialize VMLedger database',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Initialize database (run migrations)
  python scripts/init_database.py
  
  # Reset database and reinitialize (WARNING: destroys all data)
  python scripts/init_database.py --reset
        """
    )
    parser.add_argument(
        '--reset',
        action='store_true',
        help='Drop all tables and reinitialize (WARNING: destroys all data)'
    )
    
    args = parser.parse_args()
    
    logger.info("=" * 60)
    logger.info("VMLedger Database Initialization")
    logger.info("=" * 60)
    
    # Step 1: Check database connection
    if not check_database_connection():
        logger.error("\nDatabase initialization failed: Cannot connect to database")
        logger.error("Please check your DATABASE_URL configuration")
        sys.exit(1)
    
    # Step 2: Check current migration status
    status = check_migration_status()
    logger.info(f"\nDatabase status:")
    logger.info(f"  Initialized: {status['initialized']}")
    logger.info(f"  Current revision: {status.get('current_revision', 'None')}")
    logger.info(f"  Tables exist: {status['table_count']}")
    
    # Step 3: Reset database if requested
    if args.reset:
        logger.warning("\n⚠ RESET REQUESTED - ALL DATA WILL BE LOST")
        response = input("Are you sure you want to reset the database? Type 'yes' to confirm: ")
        if response.lower() != 'yes':
            logger.info("Reset cancelled")
            sys.exit(0)
        
        if not reset_database():
            logger.error("\nDatabase initialization failed: Reset failed")
            sys.exit(1)
    
    # Step 4: Run migrations
    logger.info("\nRunning migrations...")
    if not run_migrations():
        logger.error("\nDatabase initialization failed: Migration failed")
        sys.exit(1)
    
    # Step 5: Verify schema
    logger.info("\nVerifying schema...")
    if not verify_database_schema():
        logger.error("\nDatabase initialization failed: Schema verification failed")
        sys.exit(1)
    
    # Step 6: Create initial data (if needed)
    logger.info("\nCreating initial data...")
    if not create_initial_data():
        logger.error("\nDatabase initialization failed: Initial data creation failed")
        sys.exit(1)
    
    # Success
    logger.info("\n" + "=" * 60)
    logger.info("✓ Database initialization completed successfully")
    logger.info("=" * 60)
    logger.info("\nNext steps:")
    logger.info("  1. Start the API server: uvicorn vmledger.main:app --reload")
    logger.info("  2. Start Celery worker: celery -A vmledger.celery_app worker")
    logger.info("  3. Start Celery beat: celery -A vmledger.celery_app beat")
    logger.info("  4. Register a user account via the API")
    logger.info("  5. Register your first VM")
    
    sys.exit(0)


if __name__ == "__main__":
    main()
