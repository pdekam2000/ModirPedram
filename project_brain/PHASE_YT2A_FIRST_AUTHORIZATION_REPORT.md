# PHASE YT-2A — First YouTube OAuth Authorization Report

**Phase:** `YT-2A`  
**Date:** 2026-06-27  
**Scope:** First-time Google OAuth for YouTube upload — credential discovery, browser login, token persistence, refresh verification.

---

## Goal

Perform first-time authorization using Google Cloud Desktop OAuth credentials and persist refresh token for automatic future uploads.

---

## Credential location

The runtime discovers OAuth client JSON in this order:

1. `channel_profile.json` → `youtube_oauth_client_path` (if set)
2. `project_brain/local_credentials/youtube_client_secret.json`
3. `project_brain/local_credentials/client_secret.json`
4. `project_brain/local_credentials/credentials.local.json`
5. **`secrets/client_secret*.json`** ← current project credentials

**Discovered path:**

```
secrets/client_secret_358365273494-cfdkn8lppt8bd2h6f3i6t062ajvu1qbm.apps.googleusercontent.com.json
```

**Client ID loaded:** `358365273494-cfdkn8lppt8bd2h6f3i6t062ajvu1qbm.apps.googleusercontent.com`

---

## Delivered

### New module

`content_brain/upload/youtube_first_authorization.py`

| Function | Purpose |
|----------|---------|
| `discover_oauth_credentials()` | Locate Desktop JSON; expose path + client_id |
| `run_first_youtube_authorization()` | Browser OAuth → save tokens → channel info → refresh verify |
| `write_youtube_auth_result()` / `load_youtube_auth_result()` | Persist/read `youtube_auth_result.json` |
| `get_youtube_oauth_readiness()` | OAuth status, connected channel, upload ready |

### CLI

```bash
python project_brain/run_youtube_first_authorization.py
```

Options:

- `--discover-only` — verify credential path without opening browser
- `--port 8080` — local OAuth callback port
- `--no-browser` — print auth URL only (manual fallback)

### API endpoints

| Endpoint | Purpose |
|----------|---------|
| `POST /upload/youtube/auth/first` | Run first authorization (opens browser on server machine) |
| `GET /upload/youtube/auth/result` | Read `youtube_auth_result.json` + readiness |
| `GET /upload/youtube/auth/readiness` | OAuth status / upload ready snapshot |

Existing YT-2 endpoints still work: `/upload/youtube/auth/start`, `/exchange`, `/status`.

### Persisted artifacts

```
project_brain/upload/
  youtube_oauth_token.json    ← access + refresh tokens
  youtube_account.json        ← channel_id, channel_name, youtube_account_id
  youtube_auth_result.json    ← first-auth summary (YT-2A)
```

**`youtube_auth_result.json` schema:**

```json
{
  "authorized": true,
  "channel_name": "",
  "channel_id": "",
  "token_refresh_verified": true,
  "oauth_client_path": "secrets/client_secret_....json",
  "refresh_token_present": true,
  "oauth_method": "google_auth_oauthlib_local_server"
}
```

### Results page

New **YouTube OAuth** panel (always visible):

- OAuth status (Authorized / Credentials ready / Not configured)
- Connected channel name + ID
- Credentials configured
- Token refresh verified
- Upload ready

### Dependencies added

```
google-auth-oauthlib==1.2.1
google-auth==2.40.3
```

---

## Authorization flow

1. Locate `secrets/client_secret*.json`
2. Register path in channel profile (`youtube_credentials_configured: true`)
3. Open browser → Google login → approve YouTube upload + readonly scopes
4. Localhost callback captures auth code (port 8080)
5. Exchange code → save `youtube_oauth_token.json`
6. Fetch channel → save `youtube_account.json`
7. Refresh access token once to verify no re-login needed
8. Enable `youtube_upload_enabled` in channel profile
9. Write `youtube_auth_result.json`

---

## Validation

**Script:** `project_brain/validate_youtube_first_authorization.py`

| Test | Result |
|------|--------|
| OAuth credential path located | PASS |
| client_id loaded | PASS |
| First authorization persists | PASS |
| youtube_auth_result.json written | PASS |
| Auth result schema | PASS |
| OAuth readiness after auth | PASS |
| Token refresh without login | PASS |
| Results page OAuth fields | PASS |
| Upload service first-auth hook | PASS |
| Project credentials discoverable | PASS |
| No metadata generator modified | PASS |

**Total: 11/11 PASS**

---

## Run first authorization (interactive)

Complete this once on your machine:

```bash
pip install google-auth-oauthlib google-auth
python project_brain/run_youtube_first_authorization.py
```

When the browser opens:

1. Sign in with your Google account
2. Select the YouTube channel to upload to
3. Approve **YouTube upload** permissions
4. Wait for “YouTube authorization complete” in the browser

Verify:

```bash
python project_brain/run_youtube_first_authorization.py --discover-only
type project_brain\upload\youtube_auth_result.json
```

Expected: `"authorized": true`, `"token_refresh_verified": true`, channel name/id populated.

---

## Upload ready criteria

Upload is ready when all are true:

- OAuth credentials JSON found
- Refresh token stored
- Channel ID + name stored
- `youtube_upload_enabled: true` (set automatically on first auth)

Check on Results page **YouTube OAuth** panel or:

```
GET /upload/youtube/auth/readiness
```

---

## Next phase

**PHASE ANALYTICS-FEEDBACK-LOOP** — views, CTR, retention, watch time, likes, comments, subscriber conversion, prompt optimization feedback.
