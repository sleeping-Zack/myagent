"""add project detail fields

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-12
"""
from alembic import op


revision = '0002'
down_revision = '0001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE projects
        ADD COLUMN IF NOT EXISTS duration VARCHAR(100),
        ADD COLUMN IF NOT EXISTS is_featured BOOLEAN NOT NULL DEFAULT FALSE,
        ADD COLUMN IF NOT EXISTS content_html TEXT,
        ADD COLUMN IF NOT EXISTS related_links JSONB DEFAULT '[]'
    """)


def downgrade() -> None:
    op.execute("""
        ALTER TABLE projects
        DROP COLUMN IF EXISTS related_links,
        DROP COLUMN IF EXISTS content_html,
        DROP COLUMN IF EXISTS is_featured,
        DROP COLUMN IF EXISTS duration
    """)
