"""add password_change_required column

Revision ID: 006
Revises: 005
Create Date: 2026-06-24
"""

from alembic import op
import sqlalchemy as sa

revision = "006"
down_revision = "005"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "users",
        sa.Column("password_change_required", sa.Boolean(), nullable=False, server_default="true"),
    )


def downgrade():
    op.drop_column("users", "password_change_required")
