"""Backfill project links for existing knowledge documents.

Revision ID: 0006
Revises: 0005
"""

from alembic import op


revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        UPDATE documents AS document
        SET project_id = project.id
        FROM projects AS project
        WHERE document.project_id IS NULL
          AND lower(document.source_id) IN (
              lower('knowledge/projects/' || project.slug || '.md'),
              lower('knowledge/projects/' || project.slug || 'README.md')
          )
    """)
    op.execute("""
        UPDATE document_chunks AS chunk
        SET project_id = document.project_id
        FROM documents AS document
        WHERE chunk.document_id = document.id
          AND chunk.project_id IS DISTINCT FROM document.project_id
          AND document.project_id IS NOT NULL
    """)


def downgrade() -> None:
    op.execute("""
        UPDATE document_chunks AS chunk
        SET project_id = NULL
        FROM documents AS document, projects AS project
        WHERE chunk.document_id = document.id
          AND document.project_id = project.id
          AND lower(document.source_id) IN (
              lower('knowledge/projects/' || project.slug || '.md'),
              lower('knowledge/projects/' || project.slug || 'README.md')
          )
    """)
    op.execute("""
        UPDATE documents AS document
        SET project_id = NULL
        FROM projects AS project
        WHERE document.project_id = project.id
          AND lower(document.source_id) IN (
              lower('knowledge/projects/' || project.slug || '.md'),
              lower('knowledge/projects/' || project.slug || 'README.md')
          )
    """)
