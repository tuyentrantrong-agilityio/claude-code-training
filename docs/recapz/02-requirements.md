# Recapz requirements and MVP scope (T02)

Input: `01-feature-inventory.md` and the Recapz prototype. Read AI is the reference
product. Items marked **Decided** were confirmed by the owner of this practice on
2026-11-19; items marked **Proposal** still need review.

## 1. Decisions so far

| Topic | Decision | Status |
|---|---|---|
| MVP scope | Offline first: sign-in, upload, transcript, recap, report page, Ask, follow-ups, Home. Calendar and bot come after the MVP; interpreter and desktop app are stretch. | Decided |
| Stack | Python FastAPI backend, React frontend, PostgreSQL | Decided |
| AI providers | Compared in `03-architecture.md`, chosen after that review | Open |
| Notetaker platforms | Google Meet first; Zoom and Teams are shown as unsupported in the UI | Decided |

## 2. Users and roles

- **Owner**: manages the organization (people, invites, providers, devices, audit log)
  and uses every product feature.
- **Member**: records, reads and asks about meetings they can access.
- **Attendee without an account**: receives a shared recap link or email; cannot sign in
  unless invited.

## 3. Scope by release

| Area | Feature | Release |
|---|---|---|
| Access | Google sign-in, invitation only, owner/member roles | MVP |
| Access | Admin: invites, people, roles | MVP (minimal: invite and role) |
| Access | Admin: organizations, devices, audit log | Later |
| Meetings | Upload audio or video, processing stages, Ready/Processing/Incomplete tabs, search | MVP |
| Meetings | Batch transcription with speakers and timestamps, meeting language EN/VI | MVP |
| Meetings | Recap: summary, follow-ups, key points, chapters, highlights, questions | MVP |
| Meetings | Report page: tabs, player, click to seek, transcript search, edit summary | MVP |
| Meetings | Download transcript and recap | MVP |
| Meetings | Share link with permissions, email recap | Later |
| Ask | Per-meeting and cross-meeting Q&A, streaming, timestamp citations, chat history | MVP |
| Ask | Reference documents in Ask | Later |
| Follow-ups | To do (Mine/Everyone), done toggle | MVP |
| Follow-ups | Suggested follow-ups (Acknowledge/Ignore) | Later |
| Home | Ask bar, Needs you, Recent meetings, first-time empty state | MVP |
| Home | Up next and agenda draft | Later (needs calendar) |
| Calendar | Google Calendar connect and sync, per-event notetaker switch, auto-join | Later |
| Notetaker | Bot joins Google Meet, records, leaves, incomplete handling | Later |
| Notetaker | Live transcript and Live Ask during a bot meeting | Later |
| Organize | Folders and smart filing | Later |
| Organize | Your week (summary, topics, missed, daily read) | Later |
| Integrations | Slack, webhooks | Later |
| Integrations | Notion, Confluence, MCP server | Stretch |
| Admin | Provider settings, usage tracking, monthly limits | Later |
| Stretch | Live interpreter EN/VI | Stretch |
| Stretch | Desktop recorder app | Stretch |

## 4. MVP user flows

### F1. First sign-in
1. An owner exists from the seed or setup script and invites a member by email.
2. The member opens Recapz, chooses "Continue with Google".
3. If the Google email is invited, a session starts and Home shows the empty state.
   Otherwise the page shows "This account is not invited" and no account is created.

### F2. Upload to report
1. The user uploads an audio or video file from Meetings (or the Home empty state) and
   picks the meeting language.
2. The meeting appears in Processing with the current stage.
3. Stages: Uploading, Transcribing, Summarizing, Filing (Filing is a no-op until folders
   exist).
4. When done, the meeting moves to Ready; on failure it moves to Incomplete with the
   reason and a retry action.
5. The user opens the report, plays the audio, clicks timestamps, edits the summary,
   ticks follow-ups and downloads the transcript or recap.

### F3. Ask
1. From Home, the Ask page or the report side panel, the user asks a question.
2. The answer streams in and ends with citations (meeting title and timestamp).
3. A citation opens the report at that moment.
4. If nothing relevant is found, the answer says so instead of guessing.

### F4. Follow-ups
1. Follow-ups extracted by the recap appear in Follow-ups and in Home "Needs you".
2. The user filters Mine or Everyone and marks items done; counts update.

## 5. Functional rules

- A user only sees meetings of their organization. In the MVP every member of an
  organization can see every meeting of that organization (folder-level permissions come
  with folders).
- Every generated item (follow-up, key point, chapter, highlight, citation) carries a
  timestamp that exists in the transcript.
- Follow-up owner is a free-text name from the transcript; it is linked to a user when
  the name or email matches a member.
- Ask never answers from outside the organization's meetings and never invents a
  citation.
- A failed stage can be retried without duplicating transcripts or recap items.
- Deleting a meeting deletes its recording, transcript, recap items and search index
  entries.

## 6. Non-functional requirements (Proposal)

- **Privacy**: recordings and transcripts may be sent to third-party AI providers; the
  UI states this and admins choose providers. Secrets only in the server environment.
- **Isolation**: data of one organization is never readable from another; covered by
  tests.
- **Reliability**: processing runs in background jobs with retries; the UI never blocks
  on a long call.
- **Supported input**: common audio and video formats (mp3, m4a, wav, mp4, webm).
  Size and duration limits to be set in T03 after the provider choice.
- **Languages**: English and Vietnamese meetings; UI in English.
- **Cost control**: usage of each AI call is recorded from the start, even before
  limits exist.
- **Testability**: CI never calls paid AI providers; tests use recorded fixtures.

## 7. Out of scope for the practice

- Billing and paid plans.
- Mobile apps.
- Real-time collaboration on recaps.

## 8. Open questions

1. Which AI providers (decided after the comparison in `03-architecture.md`).
2. Maximum upload size and meeting length.
3. Retention period for recordings and transcripts.
4. Where the practice runs beyond local development (staging host).
5. Should members see all meetings of the organization, or only meetings they own or
   attended? (MVP proposal: all, see section 5.)
