"""public baseline: identity tables"""

from alembic import op

revision = "0001_public"
down_revision = None
branch_labels = None
depends_on = None

TS = "timestamptz NOT NULL DEFAULT now()"

STATEMENTS = [
    "CREATE EXTENSION IF NOT EXISTS pgcrypto",
    "CREATE EXTENSION IF NOT EXISTS citext",
    "CREATE EXTENSION IF NOT EXISTS vector",
    f"""CREATE TABLE public.organizations (
        id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
        name text NOT NULL,
        schema_name text NOT NULL UNIQUE,
        created_at {TS},
        updated_at {TS}
    )""",
    f"""CREATE TABLE public.users (
        id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
        email citext NOT NULL UNIQUE,
        name text NOT NULL,
        google_sub text UNIQUE,
        last_sign_in_at timestamptz,
        created_at {TS},
        updated_at {TS}
    )""",
    f"""CREATE TABLE public.memberships (
        organization_id uuid NOT NULL REFERENCES public.organizations (id),
        user_id uuid NOT NULL REFERENCES public.users (id),
        role text NOT NULL CONSTRAINT ck_memberships_role CHECK (role IN ('owner', 'member')),
        created_at {TS},
        updated_at {TS},
        PRIMARY KEY (organization_id, user_id)
    )""",
    f"""CREATE TABLE public.invites (
        id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
        organization_id uuid NOT NULL REFERENCES public.organizations (id),
        email citext NOT NULL,
        role text NOT NULL CONSTRAINT ck_invites_role CHECK (role IN ('owner', 'member')),
        invited_by uuid REFERENCES public.users (id),
        expires_at timestamptz NOT NULL,
        accepted_at timestamptz,
        revoked_at timestamptz,
        created_at {TS},
        updated_at {TS}
    )""",
    """CREATE UNIQUE INDEX uq_invites_open_email ON public.invites (organization_id, email)
        WHERE accepted_at IS NULL AND revoked_at IS NULL""",
    f"""CREATE TABLE public.sessions (
        id text PRIMARY KEY,
        user_id uuid NOT NULL REFERENCES public.users (id),
        organization_id uuid NOT NULL REFERENCES public.organizations (id),
        user_agent text,
        expires_at timestamptz NOT NULL,
        revoked_at timestamptz,
        created_at {TS},
        updated_at {TS}
    )""",
]


def upgrade() -> None:
    for stmt in STATEMENTS:
        op.execute(stmt)


def downgrade() -> None:
    for table in ("sessions", "invites", "memberships", "users", "organizations"):
        op.execute(f"DROP TABLE IF EXISTS public.{table}")
