"""Optimize database queries with additional indexes

Revision ID: 002
Revises: 001
Create Date: 2024-01-20 10:00:00.000000

This migration adds additional indexes to optimize common query patterns:
- Composite index on metrics(vm_id, timestamp DESC) for efficient latest metric lookup
- Composite index on ping_results(vm_id, timestamp DESC) for efficient latest ping lookup
- Index on vms(user_id, is_reachable) for dashboard filtering
- Index on alerts(vm_id, sent_at DESC) for alert history queries

These indexes support:
- Dashboard queries that fetch latest metrics and ping results per VM
- VM list filtering by reachability status
- Alert history queries

Requirements: 13.1-13.5 (API Performance)
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '002'
down_revision = '001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add performance optimization indexes."""
    
    # The composite index on metrics(vm_id, timestamp DESC) already exists as idx_metrics_vm_timestamp
    # from the initial migration, so we don't need to add it again
    
    # Add composite index on vms(user_id, is_reachable) for dashboard filtering
    # This helps when filtering VMs by reachability status for a specific user
    op.create_index(
        'idx_vms_user_reachable',
        'vms',
        ['user_id', 'is_reachable'],
        unique=False
    )
    
    # Add index on vms(user_id, updated_at DESC) for sorting by last update
    op.create_index(
        'idx_vms_user_updated',
        'vms',
        ['user_id', sa.text('updated_at DESC')],
        unique=False
    )
    
    # Add index on alerts(vm_id, sent_at DESC, alert_type) for alert history queries
    # This is a covering index that includes alert_type for filtering
    op.create_index(
        'idx_alerts_vm_sent_type',
        'alerts',
        ['vm_id', sa.text('sent_at DESC'), 'alert_type'],
        unique=False
    )
    
    # Add index on credentials(vm_id, auth_type) for credential lookup optimization
    # This helps when we need to filter by authentication type
    op.create_index(
        'idx_credentials_vm_auth',
        'credentials',
        ['vm_id', 'auth_type'],
        unique=False
    )


def downgrade() -> None:
    """Remove performance optimization indexes."""
    
    op.drop_index('idx_credentials_vm_auth', table_name='credentials')
    op.drop_index('idx_alerts_vm_sent_type', table_name='alerts')
    op.drop_index('idx_vms_user_updated', table_name='vms')
    op.drop_index('idx_vms_user_reachable', table_name='vms')
