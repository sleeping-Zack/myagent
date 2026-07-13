"""name heuristic token counts explicitly

Revision ID: 0004
Revises: 0003
Create Date: 2026-07-13
"""
from alembic import op


revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("messages", "input_tokens", new_column_name="estimated_input_tokens")
    op.alter_column("messages", "output_tokens", new_column_name="estimated_output_tokens")


def downgrade() -> None:
    op.alter_column("messages", "estimated_input_tokens", new_column_name="input_tokens")
    op.alter_column("messages", "estimated_output_tokens", new_column_name="output_tokens")
