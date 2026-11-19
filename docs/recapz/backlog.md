# Recapz practice backlog

Approved task list for the Recapz practice (reverse engineering Read AI from the
Recapz prototype). Each task becomes a parent issue; large ones are split into
sub-issues that each fit one reviewable pull request. Status is tracked in the issues,
not here.

## Phase 0: Planning and design

- **T01. Analyze the Recapz prototype and build a feature inventory.**
  Walk through every screen and list features, states and data entities.
  Done when: there is a feature inventory doc mapping screen to features to entities.
  Output: `docs/recapz/01-feature-inventory.md`.
- **T02. Requirements discovery and MVP scope with Claude.**
  Brainstorm with Read AI as the reference product, challenge assumptions, define user
  workflows, mark each feature MVP / Later / Out of scope.
  Done when: the MVP scope and main user flows are agreed and documented.
- **T03. Technical architecture and stack decision.**
  Backend, frontend, per-organization database, job processing, AI providers (STT,
  LLM, embeddings, TTS), with trade-offs including cost and deployment.
  Done when: there is an architecture doc with a diagram and the reasons.
- **T31. Data model and database schema design.**
  Organization, user, invite, meeting, recording, transcript segment, summary item,
  follow-up, folder, calendar event, conversation, document, audit log.
  Done when: the ERD is reviewed and the first migrations match it.
- **T32. API contract and error conventions.**
  REST and SSE endpoints, shapes, pagination, error format, OpenAPI spec in the repo.
  Done when: frontend and backend build against the same spec.
- **T04. Build Plan and Build Guide artifacts.**
  Phased Build Plan and a Build Guide (conventions, how to run, how to test); break the
  work down into issues.
  Done when: both artifacts are published and linked in the README.

## Phase 1: Foundation

- **T05. Repository skeleton and development conventions.**
  Done when: a new developer can clone and run the app with the README.
- **T06. Quality gates: CI, hooks and PR template.**
  Lint, format, type-check, tests in CI; pre-commit and pre-push hooks; PR template
  with a UI-parity checklist.
  Done when: CI runs on every PR and a failing check blocks the merge.
- **T07. Claude Code project setup (AI-native SDLC).**
  Subagents (reviewer, UI-parity checker), skills, hooks, plan mode per issue.
  Done when: agents and skills are committed and documented in CLAUDE.md.
- **T37. Google Cloud project and test accounts setup.**
  GCP project, OAuth consent screen, scopes (sign-in vs calendar), redirect URIs, test
  users and test meetings, documented in the Build Guide.
  Done when: OAuth and calendar sync work locally from the documented setup.
- **T08. Backend and database foundation.**
  API server, per-organization database isolation, migrations, background job runner.
  Done when: the health endpoint works, migrations run and a sample job is processed.
- **T09. Frontend shell matching the prototype.**
  Layout, sidebar, design tokens, empty state and toast components.
  Done when: the shell visually matches the prototype side by side.
- **T10. Google sign-in with invitation-only access.**
  OAuth sign-in, sessions, owner/member roles; non-invited emails are rejected and no
  account is created.
  Done when: invited users sign in, others see the error, role pages are protected.
- **T38. Deployment and environment configuration.**
  Container, secrets via env, staging deploy with migrations on release.
  Done when: the app runs on staging from one documented command or pipeline.
- **T39. Logging, observability and debugging aids.**
  Structured logs with request and meeting IDs, job view, error capture.
  Done when: any failed meeting can be traced end to end from the logs.
- **T40. Security and privacy baseline.**
  Token encryption at rest, org isolation tests, share-link permission checks, privacy
  note about third-party AI providers, deletion policy.
  Done when: isolation tests exist and the privacy doc is published.
- **T45. Testing strategy and test suites.**
  Unit, pipeline integration with sample audio, E2E for main flows; recorded fixtures
  instead of paid providers in CI.
  Done when: CI runs all suites without network calls to AI providers.

## Phase 2: Core pipeline, offline (MVP)

- **T34. AI provider abstraction layer.**
  Interfaces for STT (batch, streaming), LLM, embeddings, TTS; config-based selection,
  retries, timeouts, usage metering.
  Done when: switching a provider is a config change and usage is recorded per call.
- **T33. Recording storage, audio decoding and retention.**
  Done when: recordings play with seeking and expired ones are removed by a job.
- **T35. Background job reliability.**
  Job states, retries with backoff, idempotency, failure reasons in the UI, re-run a
  stage.
  Done when: a failed transcription can be retried without duplicate data.
- **T11. Meetings list and recording upload.**
  Upload, statuses Ready / Processing / Incomplete with stages Uploading, Transcribing,
  Summarizing, Filing; search and folder chips.
  Done when: an uploaded file goes from Processing to Ready or shows an error.
- **T12. Transcription for recorded files.**
  Batch STT behind the provider interface, speakers and timestamps.
  Done when: an upload produces a timestamped transcript with speakers.
- **T42. Per-meeting language settings and speaker labels.**
  Done when: transcripts use the chosen language and show named or labelled speakers.
- **T13. AI report generation.**
  Summary, follow-ups with owner and time, key points, chapters, highlights, questions.
  Done when: every item links to a valid timestamp in the transcript.
- **T14. Meeting report page.**
  Recap / Transcript / People tabs, player with chapters, click to seek, transcript
  search, summary editing, follow-up checkboxes.
  Done when: it matches the prototype and timestamps seek correctly.
- **T36. Embedding indexing pipeline.**
  Chunk transcripts and documents, embed, keep in sync on edit or delete, per org.
  Done when: a new meeting is searchable automatically after processing.
- **T15. Ask: Q&A over meetings with citations.**
  Per-meeting and cross-meeting, hybrid search, streaming, timestamp citations, chat
  history, "not found" when there is no evidence.
  Done when: every answer cites validated meetings and timestamps.
- **T43. Document management for Ask.**
  Done when: Ask can cite meetings and the documents the user is allowed to see.
- **T16. Follow-ups page.**
  To do (Mine / Everyone) and Suggested (Acknowledge / Ignore).
  Done when: states persist and the sidebar badge updates.
- **T17. Home dashboard.**
  Greeting, Ask bar, Up next with notetaker switch and agenda draft, Needs you, Recent
  meetings, first-time empty state.
  Done when: Home is correct for the empty and the populated case.

## Phase 3: Calendar and notetaker

- **T18. Google Calendar integration.**
  Separate consent, encrypted refresh token, connect/disconnect, sync, log Google's
  rejection reasons.
  Done when: upcoming events with Meet or Zoom links are synced and errors are clear.
- **T19. Calendar page and auto-join controls.**
  Done when: the switches decide which events are scheduled for the bot.
- **T20. Meeting bot: join Google Meet and capture audio (high risk).**
  Browser automation as "Recapz Notetaker", join notice, audio capture, leave
  conditions, page snapshots and logs at each step.
  Done when: the bot joins a real test meeting, records audible audio and the result
  goes through T12 and T13.
- **T21. Incomplete recordings handling.**
  Done when: a partial recording can be processed into a report.
- **T41. Live transcription and Live Ask during bot meetings.**
  Streaming STT, in-memory transcript over SSE, Live Ask, live meeting view, recording
  history.
  Done when: the transcript is live in a test meeting and Ask answers from it.
- **T44. Zoom/Teams link support for the notetaker.**
  Done when: each platform works or is clearly shown as unsupported.

## Phase 4: Organize and share

- **T22. Folders and smart filing.**
  Done when: new meetings get a filing suggestion that can be accepted or changed.
- **T23. Share and export.**
  Done when: share links respect permissions and exports open correctly.
- **T24. Connections: Slack, Notion, webhooks, MCP.**
  At least Slack and signed webhooks.
  Done when: a finished report can be pushed to the connected destinations.
- **T25. Your week.**
  Done when: the page is generated from real meetings of the last two weeks.

## Phase 5: Admin and operations

- **T26. Admin: people, organizations, devices, audit log.**
  Done when: members cannot open it and every admin action is in the audit log.
- **T27. AI provider settings and usage limits.**
  Done when: providers switch without code changes and usage is visible to admins.

## Phase 6: Stretch

- **T28. Live interpreter (English and Vietnamese).**
  Done when: the delay is measured and shown and nothing is posted into the meeting.
- **T29. Desktop recorder app.**
  Done when: a call in any app can be recorded and uploaded into the pipeline.

## Ongoing

- **T30. End-to-end testing, demo and documentation.**
  Done when: upload to report to Ask, and calendar to bot to report, pass and are
  documented.
