"""add mfa_enabled and encrypt mfa_secret on admin_user

Revision ID: 90d9c9800d7d
Revises: b8ea577dc3c0
Create Date: 2026-03-07 22:04:44.677756

"""

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = "90d9c9800d7d"
down_revision = "b8ea577dc3c0"
branch_labels = None
depends_on = None


def upgrade():
    # Add mfa_enabled with server_default so existing rows get FALSE
    op.add_column(
        "admin_user",
        sa.Column(
            "mfa_enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
    )
    # Widen mfa_secret from VARCHAR(255) to VARCHAR(512) to hold encrypted ciphertext
    op.alter_column(
        "admin_user",
        "mfa_secret",
        existing_type=sa.VARCHAR(length=255),
        type_=sa.String(length=512),
        existing_nullable=True,
    )


def downgrade():
    op.alter_column(
        "admin_user",
        "mfa_secret",
        existing_type=sa.String(length=512),
        type_=sa.VARCHAR(length=255),
        existing_nullable=True,
    )
    op.drop_column("admin_user", "mfa_enabled")
