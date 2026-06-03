"""initial_all_tables

Revision ID: 001
Revises: None
Create Date: 2026-06-03

All 15 tables: Phase 1 (users, collections, documents, ingest_jobs) +
Phase 2 (10 new tables) + full index suite.
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # pgvector extension
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # ── Phase 1 tables ──────────────────────────────────────────

    op.create_table(
        "users",
        sa.Column("id", sa.String(16), primary_key=True),
        sa.Column("username", sa.String(64), unique=True, index=True),
        sa.Column("email", sa.String(256), unique=True),
        sa.Column("password_hash", sa.String(256)),
        sa.Column("api_key_hash", sa.String(64), unique=True, nullable=True),
        sa.Column("role", sa.String(16), server_default="user"),
        sa.Column("is_active", sa.Boolean, server_default=sa.text("TRUE")),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), onupdate=sa.func.now(), nullable=True),
    )

    op.create_table(
        "collections",
        sa.Column("id", sa.String(16), primary_key=True),
        sa.Column("owner_id", sa.String(16), index=True),
        sa.Column("name", sa.String(256)),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("config", postgresql.JSONB, server_default=sa.text("'{}'::jsonb")),
        sa.Column("doc_count", sa.Integer, server_default="0"),
        sa.Column("chunk_count", sa.Integer, server_default="0"),
        sa.Column("status", sa.String(16), server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), onupdate=sa.func.now(), nullable=True),
    )

    op.create_table(
        "documents",
        sa.Column("id", sa.String(16), primary_key=True),
        sa.Column("collection_id", sa.String(16), index=True),
        sa.Column("title", sa.String(512)),
        sa.Column("source_type", sa.String(16)),
        sa.Column("source_path", sa.Text, nullable=True),
        sa.Column("mime_type", sa.String(128), nullable=True),
        sa.Column("file_size", sa.BigInteger, nullable=True),
        sa.Column("content_hash", sa.String(64), nullable=True),
        sa.Column("embedding_model", sa.String(128), nullable=True),
        sa.Column("language", sa.String(10), nullable=True),
        sa.Column("metadata", postgresql.JSONB, server_default=sa.text("'{}'::jsonb")),
        sa.Column("chunk_count", sa.Integer, server_default="0"),
        sa.Column("status", sa.String(16), server_default="pending"),
        sa.Column("path_status", postgresql.JSONB, server_default=sa.text("'{}'::jsonb")),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("ingested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), onupdate=sa.func.now(), nullable=True),
    )

    op.create_table(
        "ingest_jobs",
        sa.Column("id", sa.String(16), primary_key=True),
        sa.Column("collection_id", sa.String(16), index=True),
        sa.Column("user_id", sa.String(16)),
        sa.Column("source_type", sa.String(16)),
        sa.Column("config_snapshot", postgresql.JSONB, server_default=sa.text("'{}'::jsonb")),
        sa.Column("total_docs", sa.Integer, server_default="0"),
        sa.Column("completed_docs", sa.Integer, server_default="0"),
        sa.Column("failed_docs", sa.Integer, server_default="0"),
        sa.Column("errors", postgresql.JSONB, server_default=sa.text("'[]'::jsonb")),
        sa.Column("status", sa.String(16), server_default="pending"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True)),
    )

    # ── Phase 2 tables ──────────────────────────────────────────

    op.create_table(
        "sessions",
        sa.Column("id", sa.String(16), primary_key=True),
        sa.Column("user_id", sa.String(16), index=True),
        sa.Column("collection_id", sa.String(16), nullable=True),
        sa.Column("title", sa.String(256), nullable=True),
        sa.Column("summary", sa.String(1024), nullable=True),
        sa.Column("message_count", sa.Integer, server_default="0"),
        sa.Column("is_active", sa.Boolean, server_default=sa.text("TRUE")),
        sa.Column("last_activity_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), onupdate=sa.func.now(), nullable=True),
    )

    op.create_table(
        "messages",
        sa.Column("id", sa.String(16), primary_key=True),
        sa.Column("session_id", sa.String(16), index=True),
        sa.Column("trace_id", sa.String(64), nullable=True),
        sa.Column("role", sa.String(16)),
        sa.Column("content", sa.Text),
        sa.Column("citations", postgresql.JSONB, nullable=True),
        sa.Column("token_count", sa.Integer, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), onupdate=sa.func.now(), nullable=True),
    )

    op.create_table(
        "query_traces",
        sa.Column("id", sa.String(16), primary_key=True),
        sa.Column("session_id", sa.String(16), nullable=True),
        sa.Column("user_id", sa.String(16), index=True),
        sa.Column("collection_ids", postgresql.JSONB, server_default=sa.text("'{}'::jsonb")),
        sa.Column("query", sa.Text),
        sa.Column("answer", sa.Text, nullable=True),
        sa.Column("model_used", sa.String(64), nullable=True),
        sa.Column("total_tokens", sa.Integer, nullable=True),
        sa.Column("estimated_cost", sa.Float, nullable=True),
        sa.Column("citations", postgresql.JSONB, nullable=True),
        sa.Column("agent_graph", postgresql.JSONB, nullable=True),
        sa.Column("quality_score", sa.Float, nullable=True),
        sa.Column("iterations", sa.Integer, nullable=True),
        sa.Column("latency_ms", sa.Integer, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True)),
    )

    op.create_table(
        "feedbacks",
        sa.Column("id", sa.String(16), primary_key=True),
        sa.Column("trace_id", sa.String(64), index=True),
        sa.Column("user_id", sa.String(16), index=True),
        sa.Column("rating", sa.Integer, nullable=True),
        sa.Column("feedback_type", sa.String(16), nullable=True),
        sa.Column("comment", sa.Text, nullable=True),
        sa.Column("correction", sa.Text, nullable=True),
        sa.Column("resolved_status", sa.String(16), server_default="pending"),
        sa.Column("admin_notes", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), onupdate=sa.func.now(), nullable=True),
    )

    op.create_table(
        "long_term_memories",
        sa.Column("id", sa.String(16), primary_key=True),
        sa.Column("user_id", sa.String(16), index=True),
        sa.Column("type", sa.String(16)),
        sa.Column("entity", sa.String(256), nullable=True),
        sa.Column("content", postgresql.JSONB, server_default=sa.text("'{}'::jsonb")),
        sa.Column("embedding", postgresql.JSONB, nullable=True),
        sa.Column("confidence", sa.Float, server_default="1.0"),
        sa.Column("source_trace_id", sa.String(64), nullable=True),
        sa.Column("status", sa.String(16), server_default="active"),
        sa.Column("corrected_by", sa.String(16), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), onupdate=sa.func.now(), nullable=True),
    )

    op.create_table(
        "source_configs",
        sa.Column("id", sa.String(16), primary_key=True),
        sa.Column("user_id", sa.String(16), index=True),
        sa.Column("source_type", sa.String(16)),
        sa.Column("name", sa.String(256)),
        sa.Column("config", postgresql.JSONB, server_default=sa.text("'{}'::jsonb")),
        sa.Column("is_active", sa.Boolean, server_default=sa.text("TRUE")),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), onupdate=sa.func.now(), nullable=True),
    )

    op.create_table(
        "provider_configs",
        sa.Column("id", sa.String(16), primary_key=True),
        sa.Column("user_id", sa.String(16), index=True),
        sa.Column("provider_type", sa.String(16)),
        sa.Column("provider_name", sa.String(32)),
        sa.Column("config_encrypted", sa.LargeBinary, nullable=True),
        sa.Column("is_default", sa.Boolean, server_default=sa.text("FALSE")),
        sa.Column("is_active", sa.Boolean, server_default=sa.text("TRUE")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), onupdate=sa.func.now(), nullable=True),
    )

    op.create_table(
        "system_configs",
        sa.Column("id", sa.String(16), primary_key=True),
        sa.Column("key", sa.String(128), unique=True),
        sa.Column("value", postgresql.JSONB, server_default=sa.text("'{}'::jsonb")),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("updated_by", sa.String(16), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.String(16), primary_key=True),
        sa.Column("user_id", sa.String(16), nullable=True),
        sa.Column("action", sa.String(64)),
        sa.Column("resource_type", sa.String(32)),
        sa.Column("resource_id", sa.String(16), nullable=True),
        sa.Column("detail", postgresql.JSONB, nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("user_agent", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True)),
    )

    op.create_table(
        "user_quotas",
        sa.Column("id", sa.String(16), primary_key=True),
        sa.Column("user_id", sa.String(16), index=True),
        sa.Column("quota_type", sa.String(16)),
        sa.Column("limit_value", sa.Integer),
        sa.Column("used_value", sa.Integer, server_default="0"),
        sa.Column("period_start", sa.DateTime(timezone=True)),
        sa.Column("period_end", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), onupdate=sa.func.now(), nullable=True),
    )

    # ── Indexes ─────────────────────────────────────────────────

    op.create_index("idx_collections_owner", "collections", ["owner_id"])
    op.create_index("idx_documents_collection", "documents", ["collection_id", "status"])
    op.create_index("idx_sessions_user", "sessions", ["user_id", "is_active"])
    op.create_index("idx_messages_session", "messages", ["session_id", "created_at"])
    op.create_index("idx_query_traces_session", "query_traces", ["session_id", "created_at"])
    op.create_index("idx_query_traces_user", "query_traces", ["user_id", "created_at"])
    op.create_index("idx_feedbacks_trace", "feedbacks", ["trace_id"])
    op.create_index("idx_feedbacks_user", "feedbacks", ["user_id"])
    op.create_index("idx_memories_user_type", "long_term_memories", ["user_id", "type", "status"])
    op.create_index("idx_ingest_jobs_collection", "ingest_jobs", ["collection_id", "status"])
    op.create_index("idx_source_configs_user", "source_configs", ["user_id", "source_type"])
    op.create_index("idx_provider_configs_user", "provider_configs", ["user_id", "provider_type"])
    op.create_index("idx_audit_logs_user", "audit_logs", ["user_id", "created_at"])
    op.create_index("idx_user_quotas_user", "user_quotas", ["user_id", "quota_type"])

    # ivfflat index for memory embedding (cosine similarity search)
    op.execute(
        "CREATE INDEX idx_memories_embedding ON long_term_memories "
        "USING ivfflat (embedding vector_cosine_ops)"
    )


def downgrade() -> None:
    op.drop_index("idx_memories_embedding", table_name="long_term_memories")
    op.drop_index("idx_user_quotas_user", table_name="user_quotas")
    op.drop_index("idx_audit_logs_user", table_name="audit_logs")
    op.drop_index("idx_provider_configs_user", table_name="provider_configs")
    op.drop_index("idx_source_configs_user", table_name="source_configs")
    op.drop_index("idx_memories_user_type", table_name="long_term_memories")
    op.drop_index("idx_feedbacks_user", table_name="feedbacks")
    op.drop_index("idx_feedbacks_trace", table_name="feedbacks")
    op.drop_index("idx_query_traces_user", table_name="query_traces")
    op.drop_index("idx_query_traces_session", table_name="query_traces")
    op.drop_index("idx_messages_session", table_name="messages")
    op.drop_index("idx_sessions_user", table_name="sessions")
    op.drop_index("idx_documents_collection", table_name="documents")
    op.drop_index("idx_collections_owner", table_name="collections")

    op.drop_table("user_quotas")
    op.drop_table("audit_logs")
    op.drop_table("system_configs")
    op.drop_table("provider_configs")
    op.drop_table("source_configs")
    op.drop_table("long_term_memories")
    op.drop_table("feedbacks")
    op.drop_table("query_traces")
    op.drop_table("messages")
    op.drop_table("sessions")
    op.drop_table("ingest_jobs")
    op.drop_table("documents")
    op.drop_table("collections")
    op.drop_table("users")