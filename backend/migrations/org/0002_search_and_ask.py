"""search index and Ask: search_chunks, conversations, messages, citations

The embedding column is a plain `vector` with no fixed dimension, because the real
embedding provider is not chosen yet. Search uses an exact cosine scan. An HNSW index
needs a fixed dimension: once the provider is chosen, add a migration that alters the
column to vector(n) and creates the index.
"""

from alembic import op

revision = "0002_search_and_ask"
down_revision = "0001_org"
branch_labels = None
depends_on = None

TS = "timestamptz NOT NULL DEFAULT now()"
PK = "id uuid PRIMARY KEY DEFAULT gen_random_uuid()"
MEETING = "meeting_id uuid NOT NULL REFERENCES meetings (id) ON DELETE CASCADE"

STATEMENTS = [
    f"""CREATE TABLE search_chunks (
        {PK},
        {MEETING},
        seq integer NOT NULL,
        start_ms integer NOT NULL,
        end_ms integer NOT NULL,
        text text NOT NULL,
        tsv tsvector GENERATED ALWAYS AS (to_tsvector('simple', text)) STORED,
        embedding vector,
        created_at {TS},
        updated_at {TS},
        CONSTRAINT uq_search_chunks_meeting_id UNIQUE (meeting_id, seq)
    )""",
    "CREATE INDEX ix_search_chunks_tsv ON search_chunks USING gin (tsv)",
    "CREATE INDEX ix_search_chunks_meeting_id ON search_chunks (meeting_id)",
    f"""CREATE TABLE conversations (
        {PK},
        user_id uuid NOT NULL,
        scope_meeting_id uuid REFERENCES meetings (id) ON DELETE SET NULL,
        title text,
        created_at {TS},
        updated_at {TS}
    )""",
    "CREATE INDEX ix_conversations_user_id_updated_at ON conversations (user_id, updated_at DESC)",
    f"""CREATE TABLE messages (
        {PK},
        conversation_id uuid NOT NULL REFERENCES conversations (id) ON DELETE CASCADE,
        role text NOT NULL CONSTRAINT ck_messages_role CHECK (role IN ('user', 'assistant')),
        text text NOT NULL DEFAULT '',
        status text NOT NULL DEFAULT 'done' CONSTRAINT ck_messages_status
            CHECK (status IN ('streaming', 'done', 'failed')),
        created_at {TS},
        updated_at {TS}
    )""",
    "CREATE INDEX ix_messages_conversation_id_created_at ON messages (conversation_id, created_at)",
    f"""CREATE TABLE citations (
        {PK},
        message_id uuid NOT NULL REFERENCES messages (id) ON DELETE CASCADE,
        {MEETING},
        chunk_id uuid REFERENCES search_chunks (id) ON DELETE SET NULL,
        at_ms integer,
        seq integer NOT NULL,
        created_at {TS},
        updated_at {TS}
    )""",
    "CREATE INDEX ix_citations_message_id ON citations (message_id)",
    "CREATE INDEX ix_citations_meeting_id ON citations (meeting_id)",
]

TABLES = ["citations", "messages", "conversations", "search_chunks"]


def upgrade() -> None:
    for stmt in STATEMENTS:
        op.execute(stmt)


def downgrade() -> None:
    for table in TABLES:
        op.execute(f"DROP TABLE IF EXISTS {table}")
