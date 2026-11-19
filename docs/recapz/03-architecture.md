# Recapz architecture and stack (T03)

Status: **Proposal**, except the stack line marked Decided. Scope: the MVP from
`02-requirements.md`, with room for the calendar, the notetaker and live features.

## 1. Stack

| Layer | Choice | Status |
|---|---|---|
| Backend | Python, FastAPI, Pydantic, SQLAlchemy 2, Alembic | Decided (FastAPI); libraries proposed |
| Frontend | React, Vite, TypeScript, Tailwind CSS, TanStack Query | Decided (React); libraries proposed |
| Database | PostgreSQL with `pgvector` | Decided (PostgreSQL); pgvector proposed |
| Jobs | Worker process reading a jobs table in PostgreSQL (`SELECT ... FOR UPDATE SKIP LOCKED`) | Proposal |
| Files | Local disk in development, S3-compatible storage later, behind one storage interface | Proposal |
| Streaming to browser | Server-Sent Events (Ask answers, processing status, later live transcript) | Proposal |
| Notetaker (later) | Playwright with Chromium, run by the worker | Proposal |
| Tooling | uv, ruff, mypy, pytest; eslint, prettier, vitest, Playwright for E2E | Proposal |

Why these: the team already knows Python and PostgreSQL, FastAPI gives async I/O and an
OpenAPI spec for free, and PostgreSQL can hold the jobs, the full-text index and the
vectors, so the MVP needs no extra infrastructure (no Redis, no separate vector store).

## 2. Components

```
+-------------------+        HTTPS / SSE        +----------------------+
|  React web app    | <-----------------------> |  FastAPI API server  |
+-------------------+                           +----------+-----------+
                                                           |
                       +-----------------------------------+-------------+
                       |                    |                            |
               +-------v-------+   +--------v---------+        +---------v--------+
               |  PostgreSQL   |   |  File storage    |        |  Worker process  |
               |  public +     |   |  recordings      |        |  jobs: decode,   |
               |  org schemas  |   |  (disk / S3)     |        |  transcribe,     |
               |  + pgvector   |   +------------------+        |  recap, index    |
               +---------------+                               +---------+--------+
                                                                         |
                                                       +-----------------v-----------+
                                                       |  AI provider adapters        |
                                                       |  STT batch / STT stream /    |
                                                       |  LLM / embeddings / TTS      |
                                                       +------------------------------+
```

- The API server handles auth, CRUD, uploads and Ask. Long work is queued as jobs.
- The worker runs the pipeline stages and, later, the notetaker browser sessions.
- Provider adapters hide each vendor behind one interface per function (T34).

## 3. Multi-organization isolation

The prototype keeps "each organization in its own database file". With PostgreSQL the
proposed equivalent is **one schema per organization**:

- `public` schema: organizations, users, memberships, invites, sessions (identity only).
- `org_<id>` schema per organization: meetings, transcripts, recap items, follow-ups,
  conversations, embeddings, jobs, usage, audit log.
- Each request resolves the organization from the session and sets `search_path` for
  that transaction; the worker does the same per job.
- Alembic runs org migrations for every schema.

| Option | Pros | Cons |
|---|---|---|
| Schema per org (proposed) | Strong separation like the prototype, easy export or delete of one org, no `org_id` on every query | Migrations loop over schemas, more care with connection state |
| Shared tables + `org_id` + row-level security | One migration, simple queries across orgs for admins | A missed filter or policy leaks data; needs RLS tests everywhere |
| Database per org | Closest to the prototype | Too heavy for a practice (connections, backups) |

## 4. Processing pipeline (MVP)

```
upload -> decode -> transcribe -> recap -> index -> ready
             \           \          \        \
              +-----------+----------+--------+--> incomplete (reason, retry stage)
```

1. **upload**: store the file, create the meeting (status processing, stage Uploading).
2. **decode**: ffmpeg to a normalized audio file (mono, fixed sample rate) and duration.
3. **transcribe**: batch STT with diarization and the meeting language; store segments
   (start, end, speaker, text).
4. **recap**: LLM produces summary, follow-ups, key points, chapters, highlights and
   questions as JSON; every timestamp is validated against the segments before saving.
5. **index**: chunk segments, embed, store vectors and full-text data.
6. **ready**: status ready. Any failure stores the stage and reason; retry restarts from
   that stage and replaces its own output (idempotent).

## 5. Ask (hybrid search with citations)

1. Retrieve candidates with PostgreSQL full-text search and pgvector similarity, merge
   the two rankings (reciprocal rank fusion).
2. Send the top chunks, each with meeting id and timestamps, to the LLM with an
   instruction to answer only from them and cite chunk ids.
3. Map cited chunk ids back to meeting and timestamp; drop citations that do not exist.
4. Stream tokens over SSE, then send the final citations event.
5. No relevant chunks: return the "not found" answer without calling the LLM.

## 6. AI provider comparison (to decide)

The choice is open. Criteria, in order: Vietnamese and English quality, speaker labels,
streaming support (needed later for live), cost per hour of audio or per token, data
retention terms, ease of local testing. Facts below are what to verify on each vendor's
current documentation and pricing page before deciding; no figures are assumed here.

| Function | Candidates | Check before choosing |
|---|---|---|
| STT batch | Deepgram, AssemblyAI, ElevenLabs Scribe, OpenAI transcription API, self-hosted faster-whisper | Vietnamese accuracy on our own sample recordings, diarization for Vietnamese, price per hour, max file size |
| STT streaming (later) | Deepgram, AssemblyAI, ElevenLabs, Blaze (from the prototype) | Vietnamese streaming support, latency, websocket API |
| LLM (recap, Ask) | Claude, DeepSeek, OpenAI | JSON output reliability, Vietnamese quality, price, context size, data use policy |
| Embeddings | OpenAI, Voyage, a local multilingual model (for example bge-m3) | Vietnamese retrieval quality, vector size, cost |
| TTS (later) | ElevenLabs, Blaze, OpenAI | Vietnamese voices, latency |

Proposed way to decide: record two short sample meetings (one English, one Vietnamese),
run them through two or three STT candidates and two LLMs behind the T34 adapters, and
compare transcripts and recaps side by side. Self-hosted Whisper is kept only as a
fallback: it needs a GPU for reasonable speed, which makes deployment harder.

## 7. Security baseline

- Google OAuth with the `openid email profile` scopes for sign-in; calendar scope asked
  separately later.
- Server-side sessions in PostgreSQL, HTTP-only secure cookies, CSRF protection for
  state-changing requests.
- Provider keys and OAuth secrets only in environment variables.
- Refresh tokens (calendar, later) encrypted at rest.
- Org isolation tests: a user of org A gets 404 for every resource of org B.

## 8. Local development (proposal)

- `docker compose` with PostgreSQL (pgvector image); API, worker and web run locally.
- Seed script: one organization, one owner, one member invite, two sample meetings.
- `.env.example` lists every variable; real keys stay out of git.

## 9. Open points

1. Provider choice (section 6).
2. Upload limits and retention (depend on the provider).
3. Staging host for T38.
