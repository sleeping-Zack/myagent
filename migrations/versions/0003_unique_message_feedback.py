"""allow one feedback row per message

Revision ID: 0003
Revises: 0002
Create Date: 2026-07-13
"""
from alembic import op


revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        DELETE FROM question_feedback
        WHERE id IN (
            SELECT id
            FROM (
                SELECT id,
                       ROW_NUMBER() OVER (
                           PARTITION BY message_id
                           ORDER BY created_at DESC, id::text DESC
                       ) AS row_number
                FROM question_feedback
                WHERE message_id IS NOT NULL
            ) duplicates
            WHERE row_number > 1
        )
    """)
    op.create_unique_constraint(
        "uq_question_feedback_message_id",
        "question_feedback",
        ["message_id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_question_feedback_message_id",
        "question_feedback",
        type_="unique",
    )
