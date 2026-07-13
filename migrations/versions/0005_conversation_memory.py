"""add visitor-owned conversation history and memory

Revision ID: 0005
Revises: 0004
Create Date: 2026-07-13
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "visitor_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("NOW()")),
        sa.Column("last_seen_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("NOW()")),
        sa.Column("expires_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.TIMESTAMP(timezone=True)),
    )

    op.add_column("conversations", sa.Column("visitor_id", postgresql.UUID(as_uuid=True)))
    op.add_column("conversations", sa.Column("title", sa.String(120)))
    op.add_column("conversations", sa.Column("summary", sa.Text()))
    op.add_column("conversations", sa.Column("summarized_through_sequence", sa.Integer(), server_default="0", nullable=False))
    op.add_column("conversations", sa.Column("message_count", sa.Integer(), server_default="0", nullable=False))
    op.add_column("conversations", sa.Column("status", sa.String(20), server_default="active", nullable=False))
    op.add_column("conversations", sa.Column("active_generation_id", postgresql.UUID(as_uuid=True)))
    op.add_column("conversations", sa.Column("generation_started_at", sa.TIMESTAMP(timezone=True)))
    op.add_column("conversations", sa.Column("last_message_at", sa.TIMESTAMP(timezone=True)))
    op.add_column("conversations", sa.Column("deleted_at", sa.TIMESTAMP(timezone=True)))
    op.create_foreign_key(
        "fk_conversations_visitor_id", "conversations", "visitor_sessions",
        ["visitor_id"], ["id"], ondelete="CASCADE"
    )
    op.create_index(
        "ix_conversations_visitor_last_message",
        "conversations", ["visitor_id", sa.text("last_message_at DESC")],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    op.add_column("messages", sa.Column("sequence_no", sa.Integer()))
    op.add_column("messages", sa.Column("client_message_id", postgresql.UUID(as_uuid=True)))
    op.add_column("messages", sa.Column("status", sa.String(20), server_default="completed", nullable=False))
    op.add_column("messages", sa.Column("regenerated_from_id", postgresql.UUID(as_uuid=True)))
    op.add_column("messages", sa.Column("citation_data", postgresql.JSONB(), server_default="[]", nullable=False))
    op.add_column("messages", sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("NOW()"), nullable=False))
    op.create_foreign_key(
        "fk_messages_regenerated_from", "messages", "messages",
        ["regenerated_from_id"], ["id"], ondelete="SET NULL"
    )
    op.execute("""
        WITH numbered AS (
            SELECT id, ROW_NUMBER() OVER (PARTITION BY conversation_id ORDER BY created_at, id) AS seq
            FROM messages
        )
        UPDATE messages SET sequence_no = numbered.seq
        FROM numbered WHERE messages.id = numbered.id
    """)
    op.alter_column("messages", "sequence_no", nullable=False)
    op.create_unique_constraint("uq_message_client_request", "messages", ["conversation_id", "client_message_id"])
    op.create_unique_constraint("uq_message_sequence", "messages", ["conversation_id", "sequence_no"])

    op.drop_constraint("messages_conversation_id_fkey", "messages", type_="foreignkey")
    op.create_foreign_key(
        "messages_conversation_id_fkey", "messages", "conversations",
        ["conversation_id"], ["id"], ondelete="CASCADE"
    )
    op.drop_constraint("question_feedback_message_id_fkey", "question_feedback", type_="foreignkey")
    op.create_foreign_key(
        "question_feedback_message_id_fkey", "question_feedback", "messages",
        ["message_id"], ["id"], ondelete="CASCADE"
    )


def downgrade() -> None:
    op.drop_constraint("question_feedback_message_id_fkey", "question_feedback", type_="foreignkey")
    op.create_foreign_key("question_feedback_message_id_fkey", "question_feedback", "messages", ["message_id"], ["id"])
    op.drop_constraint("messages_conversation_id_fkey", "messages", type_="foreignkey")
    op.create_foreign_key("messages_conversation_id_fkey", "messages", "conversations", ["conversation_id"], ["id"])
    op.drop_constraint("uq_message_sequence", "messages", type_="unique")
    op.drop_constraint("uq_message_client_request", "messages", type_="unique")
    op.drop_constraint("fk_messages_regenerated_from", "messages", type_="foreignkey")
    for column in ["updated_at", "citation_data", "regenerated_from_id", "status", "client_message_id", "sequence_no"]:
        op.drop_column("messages", column)
    op.drop_index("ix_conversations_visitor_last_message", table_name="conversations")
    op.drop_constraint("fk_conversations_visitor_id", "conversations", type_="foreignkey")
    for column in ["deleted_at", "last_message_at", "generation_started_at", "active_generation_id", "status", "message_count", "summarized_through_sequence", "summary", "title", "visitor_id"]:
        op.drop_column("conversations", column)
    op.drop_table("visitor_sessions")
