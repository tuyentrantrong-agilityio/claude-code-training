# Recapz feature inventory (T01)

Source: the Recapz design prototype, https://claude.ai/artifact/5dS2kuzsPwZsnydb4Aj2Ji
(version 1794368866-ade1). The prototype runs on invented data, nothing is saved and
every AI or Google call is simulated. This document lists what each screen does, the
states it must handle and the data it needs, so later tasks can be checked against it.

## 1. Product in one paragraph

Recapz is a meeting notetaker for a small organization. It records meetings (a bot that
joins Meet or Zoom, a desktop recorder, or an uploaded file), turns them into a
transcript and a recap (summary, follow-ups, key points, chapters), and lets people ask
questions across all their meetings with answers that cite the exact moment. It also
offers a live English to Vietnamese interpreter. Sign-in is by invitation only and each
organization has its own database file.

## 2. Navigation

Sidebar (left rail), top to bottom:

| Group | Item | Route | Notes |
|---|---|---|---|
| Main | Home | `#/home` | Default route |
| Main | Meetings | `#/meetings`, `#/meeting/<id>?t=<sec>` | Report page opens at a timestamp |
| Main | Ask | `#/ask?q=<text>` | Can be opened with a question |
| Main | Interpreter | `#/live?e=<eventId>` | Shows a "Live" badge while a session runs |
| Main | Follow-ups | `#/followups` | Badge: open items for me + new suggestions |
| Main | Your week | `#/week` | |
| Workspace | Folders | `#/folders` | |
| Workspace | Calendar | `#/calendar` | |
| Workspace | Connections | `#/connections` | |
| Bottom | Desktop app | `#/desktop` | |
| Bottom | Admin | `#/admin?tab=<tab>` | Visible to owners only |

Account menu (top of the rail): organization name and role, "Preview as member/owner",
Sign out. Footer of the rail: current user name and email.

Shared UI pieces: avatar with initials and a stable color, avatar stack (max 4, then
"+N"), timestamp button that jumps to `#/meeting/<id>?t=<sec>`, switch, dropdown menu,
modal, page header, empty state, toast.

## 3. Screens

### 3.1 Sign in
- "Continue with Google" with the account email.
- Only invited emails (members or pending invites) can sign in.
- States: signed in (redirect to Home), "This account is not invited" (no account is
  created).

### 3.2 Home
- Greeting by time of day and first name, today's date.
- Ask bar: Enter or "Ask" opens `#/ask?q=...`.
- Up next: next 3 calendar events from today, with time, platform, duration, notetaker
  status, buttons "Interpret" and "Agenda", and a notetaker switch per event.
- Agenda draft: suggested 5-point agenda that includes the number of follow-ups waiting
  on me, with Copy.
- Needs you: up to 4 open follow-ups owned by me, checkbox to mark done, timestamp
  link, "See all follow-ups".
- Recent meetings: 3 latest ready meetings (date, duration, "You missed this" tag,
  title, summary, attendees, folder or "Unfiled").
- Banner "Your week at a glance" linking to Your week.
- Empty state (no meetings and no events): three start cards, Connect your calendar,
  Install the desktop app, Upload a recording.

### 3.3 Meetings
- Header button Upload.
- Search by title, folder filter chips (All + each folder).
- Tabs with counts: Ready, Processing, Incomplete.
- Row: date, title, then summary (ready) / "Working on it: <stage>" (processing) /
  error text (incomplete); attendees and folder pill.
- Upload modal: drop an audio or video file, Start processing.
- Processing pipeline stages: Uploading, Transcribing, Summarizing, Filing.
- Empty state: "No meetings yet" with Upload.

### 3.4 Meeting report
- Breadcrumb, title, attendees, date, time, platform, duration.
- Folder select (Unfiled or a folder).
- More menu: Download transcript (.txt), Download recap (.md), Push to Slack, Push to
  Notion, Send to webhook.
- Share modal: share link, who can open it (only people I invite / anyone in the
  organization), email the recap to all attendees.
- Tabs:
  - Recap: summary (edit, save, cancel, copy), follow-ups (text, owner, done checkbox,
    timestamp), key points (title, text, timestamp), highlights (quote, timestamp),
    questions raised (each opens Ask with that question).
  - Transcript: lines with time, speaker and text; search with highlight; the current
    line follows the player; click a line to seek. Interpreted meetings also show the
    Vietnamese text under each line.
  - People: talk share per person in percent.
- Side panel: player (current speaker avatar, play/pause, -15s, seek bar with chapter
  marks, time, speed), chapters list (click to seek and play), Ask about this meeting
  (suggested prompts: Summarize this meeting, What are the follow-ups?, Who owns the
  next steps?).
- Processing state: progress and "This page fills in when the report is ready".
- Incomplete state: error message (for example the notetaker lost its connection
  after 03:12 and the audio up to that point was saved), buttons "Process what was
  saved" and Delete.
- Not found state: "Meeting not found" with a link back.

### 3.5 Ask
- Ask across all meetings; every answer points to the moment it came from.
- Left: New chat and the list of past chats (title = first question).
- Starter questions when the chat is empty.
- Answers stream in ("Thinking..." first), then show citations as meeting title plus
  timestamp.
- Behaviours seen in the prototype answer logic: list open follow-ups, give a recap,
  draft an agenda, otherwise quote the most relevant transcript lines. When nothing is
  found it says so and suggests other words. With no meetings it says there is nothing
  to search yet.

### 3.6 Follow-ups
- Tab To do: filter Mine / Everyone, checkbox done, owner, meeting title, timestamp.
- Tab Suggested (with count): suggestion text, meeting and timestamp, Acknowledge
  (adds to my list) or Ignore.
- Empty states: "Nothing to do", "All reviewed".

### 3.7 Your week
- Period: the last two weeks and the number of meetings.
- What happened: short narrative summary.
- Daily read: a one-minute spoken briefing (AI voice) with play/pause and progress,
  and the script text.
- Topics: topic name, number of meetings, share bar.
- What you missed: meetings I did not attend, with summary and Open recap.
- Empty state when there are no ready meetings.

### 3.8 Folders
- Kinds: smart (files meetings by its description), shared (with the organization),
  personal.
- Suggested filing: unfiled meetings with a suggested folder and a confidence percent,
  Accept.
- Folder cards: name, kind pill, description, meeting count, show/hide the list.
- New folder modal: name, kind, description.

### 3.9 Calendar
- "Join every meeting automatically" (Meet, Zoom or Teams links).
- Paste a meeting link to add the notetaker to a meeting happening now (detects Meet,
  Zoom or Teams from the link, rejects others).
- Event list: time, title, platform, duration, invited count, bot status pill,
  Interpret, notetaker switch.
- Bot statuses: off, scheduled, joining, waiting for host, in call, ended.
- Note shown to users: the notetaker is named "Recapz Notetaker", posts a notice in the
  meeting chat when it joins, and hosts can remove it.
- Empty state: "No upcoming meetings" with Connect calendar.

### 3.10 Connections
- Cards with Connected / Not connected and Connect / Disconnect:
  - Google Calendar: reads the calendar so the notetaker can join; asked separately
    from sign-in.
  - Slack: post recaps and follow-ups to a channel.
  - Notion: save meeting notes as pages.
  - Confluence: save reports to a space.
  - Webhooks: send a signed JSON event when a report is ready; Send test.
  - MCP server: let other AI tools search your meetings; shows the client config with a
    bearer token.

### 3.11 Desktop app (simulated in the prototype)
- The app watches for calls and shows "Meeting detected" with Start recording / Not now.
- Recording view: REC/PAUSED, timer, audio level bars, Pause/Resume, Stop.
- Records the microphone and the computer audio; on Stop the file is uploaded and goes
  through the processing pipeline, with a notification when the report is ready.
- Settings: start with the computer, show meeting notifications, microphone choice,
  local copy folder. Updates install by themselves and are signature checked.

### 3.12 Live interpreter
- Setup:
  - How to listen: on this computer (desktop app, computer audio and/or microphone) or
    send the notetaker (Meet or Zoom; choose a calendar event or paste a link).
  - Languages: they speak English, you read Vietnamese, you answer in English.
  - Options: read the translation aloud, save a recap when finished.
  - Shows the current providers for speech, translation and voice; owners get a link to
    change them.
- Joining (bot mode): joining, waiting for host, in call; Cancel.
- Running:
  - Header: Listening/Paused, elapsed time, source, measured delay (about 1.4 s in the
    prototype), Pause, Pop out captions, End session.
  - What they say: speaker, time, Vietnamese translation ("Translating..." first) with
    the English beneath; lines addressed to me are marked "Asked you"; large text and
    read aloud switches.
  - Your answer: type or speak Vietnamese, Translate to English, Play in English, Copy,
    Clear; quick suggestions. Recapz never speaks or types in the meeting.
  - Lost the thread?: Catch me up gives a short Vietnamese summary so far.
  - Floating captions pop-out with the last two lines.
- End: if there are at least two lines and "save recap" is on, a normal meeting report
  is created with the English transcript and the Vietnamese beneath it.

### 3.13 Admin (owners only)
- People: invite by email with role (member/owner), invites expire, revoke; members
  table with role change, session count, Remove (ends their sessions).
- Organizations: list with member count and database file; create a new one. Each
  organization is its own database file.
- Providers: choose per function, with a Test button that reports latency:
  - Live speech to text: Blaze or ElevenLabs.
  - Translation, recaps and chat (LLM): DeepSeek (production) or Claude (development).
  - Spoken voice: Blaze or ElevenLabs.
  - Finished recordings (batch speech to text): ElevenLabs Scribe or Blaze.
  - Keys live only in the server environment file; a confidentiality warning is shown.
- Devices: signed-in devices with last seen, Revoke.
- Audit log: time, who, what (invites, role changes, removals, org creation, device
  revokes).
- A member who opens Admin sees "Only owners can open this page".

## 4. Data entities seen in the prototype

| Entity | Main fields |
|---|---|
| User / member | name, email, role (owner, member), session count |
| Invite | email, role, expiry |
| Organization | name, member count, database file |
| Device | label, last seen |
| Meeting | title, type, platform (Meet, Zoom, Teams, Desktop, File), source (bot, desktop, upload), start, duration, status (ready, processing, incomplete), stage, error, attended, owner, folder, people |
| Transcript line | time, speaker, text, optional Vietnamese text |
| Summary | text (editable) |
| Follow-up (action) | text, owner, time, state (new, done) |
| Key point | time, title, text |
| Chapter | time, title |
| Highlight | time, text |
| Question raised | text |
| Suggested follow-up | meeting, time, text, state (new, ack, ignored) |
| Folder | name, kind (smart, shared, personal), description |
| Calendar event | title, start, duration, platform, people, notetaker on/off, bot status |
| Ask conversation | title, messages (role, text, citations: meeting, time) |
| Integration | name, description, connected, config |
| Provider settings | stt, llm, tts, batch |
| Live session | mode (device, bot), status, elapsed, lines (who, en, vi, asked me), paused, voice |
| Desktop settings | autostart, notifications, microphone, local folder |
| Audit entry | time, who, what |

## 5. External services implied

- Google OAuth (sign-in) and Google Calendar (separate consent).
- Meeting platforms for the bot: Google Meet, Zoom (Teams appears in the calendar but
  not in the interpreter list).
- Speech to text (streaming and batch), LLM, text to speech: Blaze, ElevenLabs,
  DeepSeek, Claude as listed in Admin.
- Slack, Notion, Confluence, webhooks, an MCP server, email for sharing recaps.

## 6. Open questions for T02 (requirements discovery)

1. Which features are MVP? Proposed: sign-in, upload, transcript, recap, report page,
   Ask, follow-ups, Home; calendar and bot next; interpreter and desktop app later.
2. Bot platforms: Meet only first, or Meet and Zoom? Teams is shown in the calendar but
   not supported in the interpreter.
3. AI providers: use the ones in the prototype (Blaze, ElevenLabs, DeepSeek, Claude) or
   pick others? Which ones support Vietnamese well enough?
4. How is "attended" decided (calendar response, presence in the call)?
5. How are smart folder suggestions computed (LLM classification or embeddings), and
   what confidence is enough to file automatically?
6. Retention: how long are recordings and transcripts kept?
7. Integrations: which of Slack, Notion, Confluence, webhooks, MCP are needed first?
8. Where will it run (local only for the practice, or a staging server)?
