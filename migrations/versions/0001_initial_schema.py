"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-07-11
"""
from alembic import op
import sqlalchemy as sa

revision = '0001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')
    op.execute('CREATE EXTENSION IF NOT EXISTS vector')

    op.execute("""
        CREATE TABLE projects (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            slug VARCHAR(100) UNIQUE NOT NULL,
            title VARCHAR(200) NOT NULL,
            one_liner TEXT,
            project_type VARCHAR(50),
            role_summary TEXT,
            tech_stack JSONB DEFAULT '[]',
            status VARCHAR(30),
            visibility VARCHAR(20) DEFAULT 'public',
            start_date DATE,
            end_date DATE,
            cover_image TEXT,
            sort_order INTEGER DEFAULT 0,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)

    op.execute("""
        CREATE TABLE documents (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            source_id VARCHAR(200) UNIQUE NOT NULL,
            title VARCHAR(300) NOT NULL,
            document_type VARCHAR(50) NOT NULL,
            project_id UUID REFERENCES projects(id),
            source_path TEXT NOT NULL,
            content_hash VARCHAR(64) NOT NULL,
            visibility VARCHAR(20) DEFAULT 'private',
            confidence VARCHAR(20) DEFAULT 'unverified',
            tags JSONB DEFAULT '[]',
            updated_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)

    op.execute("""
        CREATE TABLE document_chunks (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
            project_id UUID REFERENCES projects(id),
            chunk_index INTEGER NOT NULL,
            title TEXT NOT NULL,
            section TEXT,
            content TEXT NOT NULL,
            embedding VECTOR(1024),
            visibility VARCHAR(20) NOT NULL DEFAULT 'private',
            confidence VARCHAR(20) NOT NULL,
            tags JSONB DEFAULT '[]',
            token_count INTEGER,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)

    op.execute("""
        CREATE TABLE conversations (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            session_id VARCHAR(100) UNIQUE NOT NULL,
            visitor_type VARCHAR(30) DEFAULT 'anonymous',
            created_at TIMESTAMPTZ DEFAULT NOW(),
            last_active_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)

    op.execute("""
        CREATE TABLE messages (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            conversation_id UUID NOT NULL REFERENCES conversations(id),
            role VARCHAR(20) NOT NULL,
            content TEXT NOT NULL,
            citation_ids JSONB DEFAULT '[]',
            model_name VARCHAR(100),
            input_tokens INTEGER,
            output_tokens INTEGER,
            latency_ms INTEGER,
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)

    op.execute("""
        CREATE TABLE question_feedback (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            message_id UUID REFERENCES messages(id),
            rating SMALLINT,
            reason VARCHAR(100),
            comment TEXT,
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS question_feedback")
    op.execute("DROP TABLE IF EXISTS messages")
    op.execute("DROP TABLE IF EXISTS conversations")
    op.execute("DROP TABLE IF EXISTS document_chunks")
    op.execute("DROP TABLE IF EXISTS documents")
    op.execute("DROP TABLE IF EXISTS projects")
    op.execute('DROP EXTENSION IF EXISTS vector')
    op.execute('DROP EXTENSION IF EXISTS "uuid-ossp"')
