"""Initial migration with all tables and indexes

Revision ID: 001
Revises: 
Create Date: 2024-01-15 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create all tables, indexes, and triggers."""
    
    # Create users table
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('username', sa.String(length=50), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('password_hash', sa.String(length=255), nullable=False),
        sa.Column('encryption_salt', sa.String(length=64), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('failed_login_attempts', sa.Integer(), nullable=False, server_default=sa.text('0')),
        sa.Column('locked_until', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_users_username', 'users', ['username'], unique=False)
    op.create_index('idx_users_email', 'users', ['email'], unique=False)
    op.create_index(op.f('ix_users_id'), 'users', ['id'], unique=False)
    op.create_index(op.f('ix_users_username'), 'users', ['username'], unique=True)
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)
    
    # Create vms table
    op.create_table(
        'vms',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('ip_address', sa.String(length=45), nullable=False),
        sa.Column('hostname', sa.String(length=255), nullable=False),
        sa.Column('domain', sa.String(length=255), nullable=True),
        sa.Column('ssh_port', sa.Integer(), nullable=False, server_default=sa.text('22')),
        sa.Column('tags', postgresql.ARRAY(sa.Text()), nullable=True),
        sa.Column('deployment_notes', sa.Text(), nullable=True),
        sa.Column('search_vector', postgresql.TSVECTOR(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('last_seen', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_reachable', sa.Boolean(), nullable=True),
        sa.CheckConstraint('ssh_port >= 1 AND ssh_port <= 65535', name='valid_ssh_port'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'ip_address', 'ssh_port', name='unique_vm_per_user')
    )
    op.create_index(op.f('ix_vms_id'), 'vms', ['id'], unique=False)
    op.create_index(op.f('ix_vms_user_id'), 'vms', ['user_id'], unique=False)
    op.create_index(op.f('ix_vms_ip_address'), 'vms', ['ip_address'], unique=False)
    op.create_index(op.f('ix_vms_hostname'), 'vms', ['hostname'], unique=False)
    
    # Create GIN indexes for full-text search and array fields
    op.create_index('idx_vms_search', 'vms', ['search_vector'], unique=False, postgresql_using='gin')
    op.create_index('idx_vms_tags', 'vms', ['tags'], unique=False, postgresql_using='gin')
    
    # Create trigger function for tsvector auto-update
    op.execute("""
        CREATE FUNCTION vms_search_vector_update() RETURNS trigger AS $$
        BEGIN
            NEW.search_vector :=
                setweight(to_tsvector('pg_catalog.english', COALESCE(NEW.ip_address, '')), 'A') ||
                setweight(to_tsvector('pg_catalog.english', COALESCE(NEW.hostname, '')), 'A') ||
                setweight(to_tsvector('pg_catalog.english', COALESCE(NEW.domain, '')), 'B') ||
                setweight(to_tsvector('pg_catalog.english', COALESCE(array_to_string(NEW.tags, ' '), '')), 'B') ||
                setweight(to_tsvector('pg_catalog.english', COALESCE(NEW.deployment_notes, '')), 'C');
            RETURN NEW;
        END
        $$ LANGUAGE plpgsql;
    """)
    
    # Create trigger for tsvector auto-update on VMs table
    op.execute("""
        CREATE TRIGGER tsvector_update_trigger
        BEFORE INSERT OR UPDATE ON vms
        FOR EACH ROW
        EXECUTE FUNCTION vms_search_vector_update();
    """)
    
    # Create credentials table
    op.create_table(
        'credentials',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('vm_id', sa.Integer(), nullable=False),
        sa.Column('auth_type', sa.String(length=20), nullable=False),
        sa.Column('encrypted_credential', sa.Text(), nullable=False),
        sa.Column('ssh_username', sa.String(length=100), nullable=False, server_default=sa.text("'root'")),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint("auth_type IN ('ssh_key', 'password')", name='valid_auth_type'),
        sa.ForeignKeyConstraint(['vm_id'], ['vms.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('vm_id')
    )
    op.create_index(op.f('ix_credentials_id'), 'credentials', ['id'], unique=False)
    op.create_index(op.f('ix_credentials_vm_id'), 'credentials', ['vm_id'], unique=True)
    
    # Create ping_results table
    op.create_table(
        'ping_results',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('vm_id', sa.Integer(), nullable=False),
        sa.Column('timestamp', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('success', sa.Boolean(), nullable=False),
        sa.Column('response_time_ms', sa.Float(), nullable=True),
        sa.Column('error_type', sa.String(length=50), nullable=True),
        sa.Column('icmp_success', sa.Boolean(), nullable=True),
        sa.Column('tcp_success', sa.Boolean(), nullable=True),
        sa.ForeignKeyConstraint(['vm_id'], ['vms.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_ping_results_id'), 'ping_results', ['id'], unique=False)
    op.create_index(op.f('ix_ping_results_vm_id'), 'ping_results', ['vm_id'], unique=False)
    op.create_index('idx_ping_results_timestamp', 'ping_results', [sa.text('timestamp DESC')], unique=False)
    
    # Create metrics table
    op.create_table(
        'metrics',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('vm_id', sa.Integer(), nullable=False),
        sa.Column('timestamp', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('cpu_usage_percent', sa.Float(), nullable=True),
        sa.Column('ram_used_mb', sa.Integer(), nullable=True),
        sa.Column('ram_total_mb', sa.Integer(), nullable=True),
        sa.Column('disk_used_gb', sa.Float(), nullable=True),
        sa.Column('disk_total_gb', sa.Float(), nullable=True),
        sa.Column('disk_usage_percent', sa.Float(), nullable=True),
        sa.Column('collection_success', sa.Boolean(), nullable=False),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['vm_id'], ['vms.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_metrics_id'), 'metrics', ['id'], unique=False)
    op.create_index(op.f('ix_metrics_vm_id'), 'metrics', ['vm_id'], unique=False)
    op.create_index('idx_metrics_timestamp', 'metrics', [sa.text('timestamp DESC')], unique=False)
    op.create_index('idx_metrics_vm_timestamp', 'metrics', ['vm_id', sa.text('timestamp DESC')], unique=False)
    
    # Create alerts table
    op.create_table(
        'alerts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('vm_id', sa.Integer(), nullable=False),
        sa.Column('alert_type', sa.String(length=50), nullable=False),
        sa.Column('sent_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('notification_method', sa.String(length=20), nullable=True),
        sa.Column('success', sa.Boolean(), nullable=False),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['vm_id'], ['vms.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_alerts_id'), 'alerts', ['id'], unique=False)
    op.create_index(op.f('ix_alerts_vm_id'), 'alerts', ['vm_id'], unique=False)
    op.create_index('idx_alerts_sent_at', 'alerts', [sa.text('sent_at DESC')], unique=False)
    
    # Create alert_configs table
    op.create_table(
        'alert_configs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('vm_id', sa.Integer(), nullable=False),
        sa.Column('enabled', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('webhook_url', sa.Text(), nullable=True),
        sa.Column('email_recipient', sa.String(length=255), nullable=True),
        sa.Column('cooldown_minutes', sa.Integer(), nullable=False, server_default=sa.text('15')),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint('webhook_url IS NOT NULL OR email_recipient IS NOT NULL', name='at_least_one_method'),
        sa.ForeignKeyConstraint(['vm_id'], ['vms.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_alert_configs_id'), 'alert_configs', ['id'], unique=False)
    op.create_index(op.f('ix_alert_configs_vm_id'), 'alert_configs', ['vm_id'], unique=False)


def downgrade() -> None:
    """Drop all tables, indexes, and triggers."""
    
    # Drop tables in reverse order (respecting foreign key constraints)
    op.drop_table('alert_configs')
    op.drop_table('alerts')
    op.drop_table('metrics')
    op.drop_table('ping_results')
    op.drop_table('credentials')
    
    # Drop trigger and function for VMs table
    op.execute('DROP TRIGGER IF EXISTS tsvector_update_trigger ON vms;')
    op.execute('DROP FUNCTION IF EXISTS vms_search_vector_update();')
    
    op.drop_table('vms')
    op.drop_table('users')
