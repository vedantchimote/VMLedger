"""Add DNS resolution tracking fields to VMs table.

Revision ID: 003
Revises: 002
Create Date: 2026-05-08
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add resolved_ip, dns_last_checked, and dns_mismatch columns."""
    op.add_column("vms", sa.Column("resolved_ip", sa.String(45), nullable=True))
    op.add_column(
        "vms",
        sa.Column("dns_last_checked", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "vms",
        sa.Column("dns_mismatch", sa.Boolean(), nullable=True, server_default="false"),
    )


def downgrade() -> None:
    """Remove DNS resolution tracking columns."""
    op.drop_column("vms", "dns_mismatch")
    op.drop_column("vms", "dns_last_checked")
    op.drop_column("vms", "resolved_ip")
