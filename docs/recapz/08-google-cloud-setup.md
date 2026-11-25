# Google Cloud setup (T37, work item F-07)

Steps to create the Google Cloud project and OAuth client that Recapz needs for Google
sign-in (T10) and, later, Google Calendar (T18). This is done by hand in the Google Cloud
console with your own Google account; nothing here can be automated from the repository.
Console labels change from time to time; if a label differs, look for the closest match.

## 1. Create the project

1. Open https://console.cloud.google.com/ and sign in with the account that will own the
   project.
2. Project picker, then "New project". Name: `recapz-practice`. Create it and select it.

## 2. Configure the OAuth consent (Google Auth Platform)

1. Menu: "APIs and Services", then "OAuth consent screen" (it opens the Google Auth
   Platform pages: Branding, Audience, Clients, Data access).
2. Branding: app name `Recapz (practice)`, user support email, developer contact email.
   Leave logo and domains empty for local development.
3. Audience, user type:
   - **Internal** if the project belongs to the company Google Workspace and only company
     accounts will sign in. No test-user list is needed.
   - **External** otherwise. Keep the publishing status **Testing** and add every account
     that will sign in (yours and the test accounts) under "Test users".
4. Data access (scopes):
   - For sign-in (T10): `openid`, `.../auth/userinfo.email`, `.../auth/userinfo.profile`.
   - For the calendar (T18, later): `.../auth/calendar.readonly` and
     `.../auth/calendar.events.readonly`. Add them only when T18 starts; Recapz asks for
     calendar access separately from sign-in.

## 3. Create the OAuth client

1. Clients, then "Create client". Application type: **Web application**.
2. Name: `recapz-local`.
3. Authorized JavaScript origins: `http://localhost:5173`
4. Authorized redirect URIs: `http://localhost:8000/api/v1/auth/google/callback`
   (matches `GET /auth/google/callback` in `05-api-contract.md`). Add the staging URL
   later in T38.
5. Create, then copy the client ID and the client secret. Do not commit them.

## 4. Put the values in `.env`

Add to the local `.env` (never to `.env.example` with real values):

```
GOOGLE_CLIENT_ID=<client id>
GOOGLE_CLIENT_SECRET=<client secret>
GOOGLE_REDIRECT_URI=http://localhost:8000/api/v1/auth/google/callback
```

`.env.example` lists the same keys with empty values (added in T10).

## 5. Test accounts and meetings

- One owner account (yours) and at least one second account to test invitations and the
  "not invited" path.
- For T18 and T20 (later): a calendar with a few upcoming Google Meet events on the test
  account, and a meeting you can join from two accounts.

## 6. Check

- In the Clients page the redirect URI is exactly the one above (scheme, port, path).
- The account you will use is a test user (External) or in the company domain (Internal).
- The client secret is only in your local `.env` and your password manager.

## 7. Notes

- With an External app in Testing status, Google limits sign-in to the listed test users,
  and refresh tokens issued for it can expire after a short period; that is acceptable
  for local development. Publishing or verification is not needed for the practice.
- Calendar scopes are sensitive scopes; they work for test users without verification.
