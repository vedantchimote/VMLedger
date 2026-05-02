#!/usr/bin/env python3
"""
Database backup script for VMLedger.

This script:
1. Creates PostgreSQL database backups using pg_dump
2. Supports custom backup directory and retention policies
3. Compresses backups to save disk space
4. Provides restore instructions

Usage:
    python scripts/backup_database.py [options]

Options:
    --output-dir DIR    Backup directory (default: ./backups)
    --retention DAYS    Number of days to retain backups (default: 30)
    --compress          Compress backup with gzip (default: True)
    --no-compress       Do not compress backup
    --format FORMAT     Backup format: plain, custom, directory, tar (default: custom)
    --cleanup           Remove old backups based on retention policy

Requirements:
    - pg_dump must be installed and in PATH
    - Database credentials must be configured in .env
"""

import sys
import os
import argparse
import logging
import subprocess
from pathlib import Path
from datetime import datetime, timedelta
from urllib.parse import urlparse
import gzip
import shutil

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from vmledger.config import settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def parse_database_url(database_url: str) -> dict:
    """
    Parse PostgreSQL database URL into components.
    
    Args:
        database_url: PostgreSQL connection URL
    
    Returns:
        Dictionary with connection parameters
    """
    parsed = urlparse(database_url)
    
    return {
        'host': parsed.hostname or 'localhost',
        'port': parsed.port or 5432,
        'database': parsed.path.lstrip('/') if parsed.path else 'vmledger',
        'username': parsed.username or 'vmledger',
        'password': parsed.password or ''
    }


def check_pg_dump_available() -> bool:
    """
    Check if pg_dump is available in PATH.
    
    Returns:
        True if pg_dump is available, False otherwise
    """
    try:
        result = subprocess.run(
            ['pg_dump', '--version'],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            version = result.stdout.strip()
            logger.info(f"Found {version}")
            return True
        return False
    except FileNotFoundError:
        logger.error("pg_dump not found in PATH")
        return False
    except Exception as e:
        logger.error(f"Error checking pg_dump: {e}")
        return False


def create_backup(
    output_dir: Path,
    compress: bool = True,
    backup_format: str = 'custom'
) -> tuple[bool, str]:
    """
    Create database backup using pg_dump.
    
    Args:
        output_dir: Directory to store backup
        compress: Whether to compress the backup
        backup_format: Backup format (plain, custom, directory, tar)
    
    Returns:
        Tuple of (success, backup_file_path)
    """
    logger.info("Creating database backup...")
    
    # Parse database URL
    db_params = parse_database_url(settings.database_url)
    
    # Create output directory if it doesn't exist
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate backup filename with timestamp
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # Determine file extension based on format
    format_extensions = {
        'plain': '.sql',
        'custom': '.dump',
        'directory': '',  # Directory format creates a folder
        'tar': '.tar'
    }
    extension = format_extensions.get(backup_format, '.dump')
    
    backup_filename = f"vmledger_backup_{timestamp}{extension}"
    backup_path = output_dir / backup_filename
    
    # Build pg_dump command
    pg_dump_cmd = [
        'pg_dump',
        '-h', db_params['host'],
        '-p', str(db_params['port']),
        '-U', db_params['username'],
        '-d', db_params['database'],
        '-F', backup_format[0],  # First letter: p, c, d, t
        '-f', str(backup_path),
        '--verbose'
    ]
    
    # Set password environment variable
    env = os.environ.copy()
    if db_params['password']:
        env['PGPASSWORD'] = db_params['password']
    
    try:
        logger.info(f"Running pg_dump to {backup_path}...")
        logger.info(f"  Host: {db_params['host']}:{db_params['port']}")
        logger.info(f"  Database: {db_params['database']}")
        logger.info(f"  Format: {backup_format}")
        
        result = subprocess.run(
            pg_dump_cmd,
            env=env,
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout
        )
        
        if result.returncode != 0:
            logger.error(f"pg_dump failed with exit code {result.returncode}")
            logger.error(f"Error output: {result.stderr}")
            return False, ""
        
        # Check if backup file was created
        if backup_format == 'directory':
            if not backup_path.is_dir():
                logger.error(f"Backup directory not created: {backup_path}")
                return False, ""
        else:
            if not backup_path.exists():
                logger.error(f"Backup file not created: {backup_path}")
                return False, ""
        
        # Get backup size
        if backup_format == 'directory':
            backup_size = sum(f.stat().st_size for f in backup_path.rglob('*') if f.is_file())
        else:
            backup_size = backup_path.stat().st_size
        
        logger.info(f"✓ Backup created: {backup_path}")
        logger.info(f"  Size: {backup_size / (1024*1024):.2f} MB")
        
        # Compress if requested and format is plain or custom
        if compress and backup_format in ['plain', 'custom']:
            logger.info("Compressing backup...")
            compressed_path = Path(str(backup_path) + '.gz')
            
            try:
                with open(backup_path, 'rb') as f_in:
                    with gzip.open(compressed_path, 'wb') as f_out:
                        shutil.copyfileobj(f_in, f_out)
                
                # Remove uncompressed file
                backup_path.unlink()
                
                compressed_size = compressed_path.stat().st_size
                compression_ratio = (1 - compressed_size / backup_size) * 100
                
                logger.info(f"✓ Backup compressed: {compressed_path}")
                logger.info(f"  Compressed size: {compressed_size / (1024*1024):.2f} MB")
                logger.info(f"  Compression ratio: {compression_ratio:.1f}%")
                
                return True, str(compressed_path)
            except Exception as e:
                logger.error(f"Compression failed: {e}")
                logger.info(f"Keeping uncompressed backup: {backup_path}")
                return True, str(backup_path)
        
        return True, str(backup_path)
        
    except subprocess.TimeoutExpired:
        logger.error("pg_dump timed out after 5 minutes")
        return False, ""
    except Exception as e:
        logger.error(f"Backup failed: {e}")
        return False, ""


def cleanup_old_backups(output_dir: Path, retention_days: int) -> int:
    """
    Remove backups older than retention period.
    
    Args:
        output_dir: Directory containing backups
        retention_days: Number of days to retain backups
    
    Returns:
        Number of backups removed
    """
    logger.info(f"Cleaning up backups older than {retention_days} days...")
    
    if not output_dir.exists():
        logger.info("  Backup directory does not exist, nothing to clean")
        return 0
    
    cutoff_date = datetime.now() - timedelta(days=retention_days)
    removed_count = 0
    
    # Find all backup files
    backup_patterns = ['vmledger_backup_*.sql', 'vmledger_backup_*.dump', 
                      'vmledger_backup_*.tar', 'vmledger_backup_*.gz']
    
    for pattern in backup_patterns:
        for backup_file in output_dir.glob(pattern):
            try:
                # Get file modification time
                file_mtime = datetime.fromtimestamp(backup_file.stat().st_mtime)
                
                if file_mtime < cutoff_date:
                    logger.info(f"  Removing old backup: {backup_file.name}")
                    backup_file.unlink()
                    removed_count += 1
            except Exception as e:
                logger.error(f"  Error removing {backup_file.name}: {e}")
    
    # Also check for directory format backups
    for backup_dir in output_dir.glob('vmledger_backup_*'):
        if backup_dir.is_dir():
            try:
                dir_mtime = datetime.fromtimestamp(backup_dir.stat().st_mtime)
                if dir_mtime < cutoff_date:
                    logger.info(f"  Removing old backup directory: {backup_dir.name}")
                    shutil.rmtree(backup_dir)
                    removed_count += 1
            except Exception as e:
                logger.error(f"  Error removing {backup_dir.name}: {e}")
    
    if removed_count > 0:
        logger.info(f"✓ Removed {removed_count} old backup(s)")
    else:
        logger.info("  No old backups to remove")
    
    return removed_count


def list_backups(output_dir: Path):
    """
    List all available backups.
    
    Args:
        output_dir: Directory containing backups
    """
    logger.info(f"Available backups in {output_dir}:")
    
    if not output_dir.exists():
        logger.info("  No backups found (directory does not exist)")
        return
    
    # Find all backup files
    backup_patterns = ['vmledger_backup_*.sql', 'vmledger_backup_*.dump', 
                      'vmledger_backup_*.tar', 'vmledger_backup_*.gz']
    
    backups = []
    for pattern in backup_patterns:
        backups.extend(output_dir.glob(pattern))
    
    # Also check for directory format backups
    for backup_dir in output_dir.glob('vmledger_backup_*'):
        if backup_dir.is_dir():
            backups.append(backup_dir)
    
    if not backups:
        logger.info("  No backups found")
        return
    
    # Sort by modification time (newest first)
    backups.sort(key=lambda x: x.stat().st_mtime, reverse=True)
    
    for backup in backups:
        mtime = datetime.fromtimestamp(backup.stat().st_mtime)
        if backup.is_dir():
            size = sum(f.stat().st_size for f in backup.rglob('*') if f.is_file())
        else:
            size = backup.stat().st_size
        
        logger.info(f"  {backup.name}")
        logger.info(f"    Created: {mtime.strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"    Size: {size / (1024*1024):.2f} MB")


def print_restore_instructions(backup_file: str):
    """
    Print instructions for restoring from backup.
    
    Args:
        backup_file: Path to backup file
    """
    db_params = parse_database_url(settings.database_url)
    backup_path = Path(backup_file)
    
    logger.info("\n" + "=" * 60)
    logger.info("RESTORE INSTRUCTIONS")
    logger.info("=" * 60)
    
    if backup_path.suffix == '.gz':
        logger.info("\n1. Decompress the backup:")
        logger.info(f"   gunzip {backup_file}")
        decompressed = str(backup_path).replace('.gz', '')
        logger.info(f"   This will create: {decompressed}")
        backup_file = decompressed
        backup_path = Path(backup_file)
    
    if backup_path.suffix == '.sql':
        logger.info("\n2. Restore using psql:")
        logger.info(f"   psql -h {db_params['host']} -p {db_params['port']} \\")
        logger.info(f"        -U {db_params['username']} -d {db_params['database']} \\")
        logger.info(f"        -f {backup_file}")
    elif backup_path.suffix == '.dump':
        logger.info("\n2. Restore using pg_restore:")
        logger.info(f"   pg_restore -h {db_params['host']} -p {db_params['port']} \\")
        logger.info(f"             -U {db_params['username']} -d {db_params['database']} \\")
        logger.info(f"             -c {backup_file}")
    elif backup_path.suffix == '.tar':
        logger.info("\n2. Restore using pg_restore:")
        logger.info(f"   pg_restore -h {db_params['host']} -p {db_params['port']} \\")
        logger.info(f"             -U {db_params['username']} -d {db_params['database']} \\")
        logger.info(f"             -F t -c {backup_file}")
    elif backup_path.is_dir():
        logger.info("\n2. Restore using pg_restore:")
        logger.info(f"   pg_restore -h {db_params['host']} -p {db_params['port']} \\")
        logger.info(f"             -U {db_params['username']} -d {db_params['database']} \\")
        logger.info(f"             -F d -c {backup_file}")
    
    logger.info("\nOptions:")
    logger.info("  -c : Clean (drop) database objects before recreating")
    logger.info("  -d : Specify database name")
    logger.info("  -h : Database host")
    logger.info("  -p : Database port")
    logger.info("  -U : Database user")
    
    logger.info("\n⚠ WARNING:")
    logger.info("  Restoring will overwrite existing data in the database!")
    logger.info("  Make sure to stop all VMLedger services before restoring.")
    logger.info("=" * 60)


def main():
    """Main backup function."""
    parser = argparse.ArgumentParser(
        description='Backup VMLedger PostgreSQL database',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Create compressed backup in default location
  python scripts/backup_database.py
  
  # Create backup in custom directory
  python scripts/backup_database.py --output-dir /backups
  
  # Create backup and clean up old backups
  python scripts/backup_database.py --cleanup --retention 7
  
  # Create uncompressed plain SQL backup
  python scripts/backup_database.py --no-compress --format plain
  
  # List existing backups
  python scripts/backup_database.py --list
        """
    )
    parser.add_argument(
        '--output-dir',
        type=Path,
        default=Path('./backups'),
        help='Backup directory (default: ./backups)'
    )
    parser.add_argument(
        '--retention',
        type=int,
        default=30,
        help='Number of days to retain backups (default: 30)'
    )
    parser.add_argument(
        '--compress',
        action='store_true',
        default=True,
        help='Compress backup with gzip (default: True)'
    )
    parser.add_argument(
        '--no-compress',
        action='store_false',
        dest='compress',
        help='Do not compress backup'
    )
    parser.add_argument(
        '--format',
        choices=['plain', 'custom', 'directory', 'tar'],
        default='custom',
        help='Backup format (default: custom)'
    )
    parser.add_argument(
        '--cleanup',
        action='store_true',
        help='Remove old backups based on retention policy'
    )
    parser.add_argument(
        '--list',
        action='store_true',
        help='List existing backups and exit'
    )
    
    args = parser.parse_args()
    
    logger.info("=" * 60)
    logger.info("VMLedger Database Backup")
    logger.info("=" * 60)
    
    # List backups if requested
    if args.list:
        list_backups(args.output_dir)
        sys.exit(0)
    
    # Check if pg_dump is available
    if not check_pg_dump_available():
        logger.error("\nBackup failed: pg_dump not found")
        logger.error("Please install PostgreSQL client tools")
        logger.error("  Ubuntu/Debian: sudo apt-get install postgresql-client")
        logger.error("  macOS: brew install postgresql")
        logger.error("  Windows: Install from https://www.postgresql.org/download/windows/")
        sys.exit(1)
    
    # Create backup
    success, backup_file = create_backup(
        args.output_dir,
        compress=args.compress,
        backup_format=args.format
    )
    
    if not success:
        logger.error("\nBackup failed")
        sys.exit(1)
    
    # Cleanup old backups if requested
    if args.cleanup:
        cleanup_old_backups(args.output_dir, args.retention)
    
    # Print restore instructions
    print_restore_instructions(backup_file)
    
    logger.info("\n✓ Backup completed successfully")
    sys.exit(0)


if __name__ == "__main__":
    main()
