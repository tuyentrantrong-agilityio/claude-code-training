"""org baseline: meeting data tables (schema comes from search_path)"""

from alembic import op

revision = "0001_org"
down_revision = None
branch_labels = None
depends_on = None

TS = "timestamptz NOT NULL DEFAULT now()"
PK = "id uuid PRIMARY KEY DEFAULT gen_random_uuid()"
MEETING = "meeting_id uuid NOT NULL REFERENCES meetings (id) ON DELETE CASCADE"

STATEMENTS = [
    f"""CREATE TABLE meetings (
        {PK},
        title text NOT NULL,
        source text NOT NULL CONSTRAINT ck_meetings_source
            CHECK (source IN ('upload', 'bot', 'desktop')),
        platform text NOT NULL CONSTRAINT ck_meetings_platform
            CHECK (platform IN ('file', 'meet', 'zoom', 'teams', 'desktop')),
        language text NOT NULL CONSTRAINT ck_meetings_language CHECK (language IN ('en', 'vi')),
        status text NOT NULL CONSTRAINT ck_meetings_status
            CHECK (status IN ('processing', 'ready', 'incomplete')),
        stage text CONSTRAINT ck_meetings_stage
            CHECK (stage IN ('uploading', 'transcribing', 'summarizing', 'filing')),
        error text,
        started_at timestamptz,
        duration_ms integer,
        owner_id uuid,
        summary text,
        summary_edited_at timestamptz,
        deleted_at timestamptz,
        created_at {TS},
        updated_at {TS}
    )""",
    "CREATE INDEX ix_meetings_status_started_at ON meetings (status, started_at DESC)",
    f"""CREATE TABLE recordings (
        {PK},
        {MEETING} UNIQUE,
        original_path text,
        audio_path text,
        mime_type text,
        size_bytes bigint,
        expires_at timestamptz,
        created_at {TS},
        updated_at {TS}
    )""",
    f"""CREATE TABLE meeting_participants (
        {PK},
        {MEETING},
        speaker_label text,
        display_name text,
        user_id uuid,
        created_at {TS},
        updated_at {TS}
    )""",
    f"""CREATE TABLE transcript_segments (
        {PK},
        {MEETING},
        seq integer NOT NULL,
        start_ms integer NOT NULL,
        end_ms integer NOT NULL,
        participant_id uuid REFERENCES meeting_participants (id),
        text text NOT NULL,
        created_at {TS},
        updated_at {TS},
        CONSTRAINT uq_transcript_segments_meeting_id UNIQUE (meeting_id, seq),
        CONSTRAINT ck_transcript_segments_time_range CHECK (start_ms <= end_ms AND start_ms >= 0)
    )""",
    """CREATE INDEX ix_transcript_segments_meeting_id_start_ms
        ON transcript_segments (meeting_id, start_ms)""",
    f"""CREATE TABLE recap_items (
        {PK},
        {MEETING},
        kind text NOT NULL CONSTRAINT ck_recap_items_kind
            CHECK (kind IN ('key_point', 'chapter', 'highlight', 'question')),
        seq integer NOT NULL,
        at_ms integer CONSTRAINT ck_recap_items_at_ms CHECK (at_ms >= 0),
        title text,
        text text,
        created_at {TS},
        updated_at {TS},
        CONSTRAINT uq_recap_items_meeting_id UNIQUE (meeting_id, kind, seq)
    )""",
    f"""CREATE TABLE follow_ups (
        {PK},
        {MEETING},
        text text NOT NULL,
        owner_name text,
        owner_user_id uuid,
        at_ms integer,
        state text NOT NULL DEFAULT 'open' CONSTRAINT ck_follow_ups_state
            CHECK (state IN ('open', 'done')),
        origin text NOT NULL DEFAULT 'recap' CONSTRAINT ck_follow_ups_origin
            CHECK (origin IN ('recap', 'suggested')),
        done_at timestamptz,
        created_at {TS},
        updated_at {TS}
    )""",
    "CREATE INDEX ix_follow_ups_owner_user_id_state ON follow_ups (owner_user_id, state)",
    f"""CREATE TABLE jobs (
        {PK},
        meeting_id uuid REFERENCES meetings (id) ON DELETE CASCADE,
        kind text NOT NULL CONSTRAINT ck_jobs_kind
            CHECK (kind IN ('decode', 'transcribe', 'recap', 'index', 'cleanup')),
        state text NOT NULL DEFAULT 'queued' CONSTRAINT ck_jobs_state
            CHECK (state IN ('queued', 'running', 'succeeded', 'failed')),
        attempts integer NOT NULL DEFAULT 0,
        run_after timestamptz NOT NULL DEFAULT now(),
        last_error text,
        locked_by text,
        locked_at timestamptz,
        created_at {TS},
        updated_at {TS}
    )""",
    "CREATE INDEX ix_jobs_state_run_after ON jobs (state, run_after)",
    """CREATE UNIQUE INDEX uq_jobs_active_meeting_kind ON jobs (meeting_id, kind)
        WHERE state IN ('queued', 'running')""",
    f"""CREATE TABLE usage_events (
        {PK},
        meeting_id uuid,
        function text,
        provider text,
        units numeric,
        unit_kind text,
        created_at {TS},
        updated_at {TS}
    )""",
]

TABLES = [
    "usage_events",
    "jobs",
    "follow_ups",
    "recap_items",
    "transcript_segments",
    "meeting_participants",
    "recordings",
    "meetings",
]


def upgrade() -> None:
    for stmt in STATEMENTS:
        op.execute(stmt)


def downgrade() -> None:
    for table in TABLES:
        op.execute(f"DROP TABLE IF EXISTS {table}")
