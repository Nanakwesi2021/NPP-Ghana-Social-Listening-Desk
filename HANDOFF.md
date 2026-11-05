# Handoff · NPP Ghana Social Listening Desk

Updated on **4 November 2026**.

- **Code:** the latest commit, `9c779d1` (two-step sign-in), is on `main` on GitHub (`Nanakwesi2021/NPP-Ghana-Social-Listening-Desk`). Its automatic test run passed.
- **Tests:** all 127 offline tests pass in about 10 seconds.
- **Sources:** live news and 7 national broadcast channels are collected.

Rules for coding agents are in `AGENTS.md`. Read them before changing anything.

---

## 1. Resume work

**In Antigravity:** open the folder `/Users/barnabaseshun/Documents/NPP-Ghana-Social-Listening-Desk`. Ask the agent to read `AGENTS.md` and this file before it starts.

**In Claude Code:**

```sh
cd /Users/barnabaseshun/Documents/NPP-Ghana-Social-Listening-Desk
claude
```

Either way, confirm the test baseline before making changes:

```sh
cd src
../.venv/bin/python manage.py test desk
```

**Expected:** `Ran 127 tests … OK`. If a test fails before you start, stop and report it.

When new code adds packages, update each environment: run `../.venv/bin/python -m pip install -r ../requirements.lock`, then `../.venv/bin/python manage.py migrate` against each database you use.

---

## 2. Local services and ports

| Port | Backend Database | Mode | Description | Accounts |
| :--- | :--- | :--- | :--- | :--- |
| **8000** | `data/desk.sqlite3` | Sample shift (`DESK_SAMPLE_MODE=1`) | Offline tariff crisis demo with 1-click persona switcher | `ama` (Editor), `kwame` (Analyst) |
| **8001** | `data/live.sqlite3` | Live desk (`DESK_SAMPLE_MODE=0`) | Local file-based live listening desk with background worker | Staff accounts: see `provision_user --list` |
| **8002** | **PostgreSQL 16** (`npp_desk`) | Live desk (`DESK_SAMPLE_MODE=0`) | High-concurrency production PostgreSQL with GIN trigram search | Staff accounts: see `provision_user --list` |

**Restart the servers to apply new code.** A running server keeps the code it started with, so 8001 and 8002 do not ask for two-step codes until they are restarted.

- **SQLite (8000 and 8001):** both databases are already migrated.
- **PostgreSQL (8002):** run `migrate` first, with the real `DATABASE_URL` set. Do this in the Terminal app.

From `src/`:

```sh
# 8000 · Sample shift
../.venv/bin/python manage.py runserver 127.0.0.1:8000

# 8001 · local live desk, and its worker in a second terminal
DESK_DATABASE=../data/live.sqlite3 DESK_SAMPLE_MODE=0 ../.venv/bin/python manage.py runserver 127.0.0.1:8001
DESK_DATABASE=../data/live.sqlite3 DESK_SAMPLE_MODE=0 ../.venv/bin/python manage.py run_worker

# 8002 · PostgreSQL desk: set DATABASE_URL in that terminal first, never in a file in the repository
../.venv/bin/python manage.py migrate
../.venv/bin/python manage.py runserver 127.0.0.1:8002
```

**Passwords are never written in this repository.**

- Create or reset a password with `provision_user --random-password`, and hand it over privately.
- Each person then changes theirs at `/password-change/`.
- On a live desk, each person also sets up two-step sign-in with an authenticator app at their first sign-in.

---

## 3. What was built in the Antigravity sprint

1. **Test Suite Expansion:** Expanded offline test coverage from 34 to **70 passing tests** (127 now).
2. **Version Control:** Git repository initialized and pushed to GitHub:
   `https://github.com/Nanakwesi2021/NPP-Ghana-Social-Listening-Desk`
3. **Telegram Pilot for Critical · L4 Escalations:**
   - Dedicated `CaseNotification` model (`0003_casenotification.py`).
   - HTML notification formatting with case references, urgency rationale, and clickable links to case file & evidence.
   - Deduplication keyed by `<ref>:l4`.
   - Failure isolation: missing credentials or network errors do not block case decisions, and editors get a visible retry button.
4. **Social & Broadcaster Collectors:**
   - **X API v2:** Recent search collector in `src/desk/collectors/x.py`. Automatically detects HTTP 429 rate limits and pagination ceilings, recording `PollRun.Result.CAPPED` to mark platforms partial in trend windows (Decision 005) while preserving received posts. Waiting for an API key.
   - **Ghanaian Broadcast Channels:** Public Atom feed collector in `src/desk/collectors/youtube.py` monitoring 7 top national stations (JoyNews, Citi Tube, Peace FM / Despite Media, TV3 Ghana, UTV Ghana, Metro TV Ghana, Adom TV) with zero credentials.
   - **Analyst Submissions:** Management command `manage.py submit_social_link` for analysts to submit observed Facebook posts, TikTok clips, X posts, and WhatsApp field tips with automated language detection (English vs. Twi) and topic tagging. WhatsApp tips route into queue review but are strictly excluded from public trend momentum per Decision 002.
5. **Staff Provisioning & Self-Service Password Management:**
   - `manage.py provision_user`: role-gated command-line tool. Roles: `editor` (with the `desk.decide_case` permission), `analyst` (research) and `admin` (superuser). Options: `--random-password`, `--deactivate`, `--activate`, `--reset-two-step` and `--list` (which shows who has set up two-step sign-in).
   - `/password-change/` and `/password-change/done/` styled in desk design system with masthead user menu shortcuts.
6. **PostgreSQL 16+ Production Backend:**
   - Database `npp_desk` on PostgreSQL 16.15 with `pg_trgm` and `btree_gin` extensions (`0004_case_desk_case_claim_trgm_and_more.py`).
   - Native GIN indexes on `TrendRow.platform_counts`, `TrendRow.buckets`, `Item.excerpt`, and `Case.claim`.
   - Enhanced search using PostgreSQL native `SearchVector` and `TrigramSimilarity` fuzzy scoring for English and Twi terms.
   - Multi-container Docker Compose (`deploy/docker-compose.yml`) for PostgreSQL 16 and Redis 7.
   - Production systemd units and Nginx reverse proxy configuration in `deploy/`.
7. **Shift Intelligence Briefing:**
   - `manage.py brief_shift`: generates 05:45 GMT morning intelligence briefs and 21:30 GMT shift handovers.
   - Mobile-first rich Telegram HTML formatting with status badges and clickable desk links.
   - Systemd timers (`npp-desk-brief-morning.timer`, `npp-desk-brief-evening.timer`) and `deploy/crontab.txt`.

---

## 4. What was done after the sprint (Claude Code, 3 November)

Details are in `changelog.md` and decisions 011–013 in `decisions.md`.

1. **Phase 0 · security fixes before live use** (decision 011):
   - Staff passwords removed from this file. They remain in earlier git history, so they must be changed.
   - The passwordless demo sign-in opens only the fictional sample people.
   - Sample mode switches off when the settings look live, and the desk refuses to start if it is forced on there.
   - Docker services listen on loopback only.
   - The tests no longer reach YouTube or X.
   - A `DATABASE_URL` that is not PostgreSQL stops the desk.
2. **Phase 1 · hardening for a real server** (decision 012):
   - Sign-in lockout and a sign-in log.
   - `/healthz/` for uptime monitors.
   - `backup_desk`, with a check that each backup reads back.
   - A GitHub Actions workflow that runs the tests on every push.
3. **Two-step sign-in** (decision 013): a code from an authenticator app after the password, with 10 single-use backup codes. It is required on every live desk.

---

## 5. Key CLI Commands

All commands run from `src/`:

```sh
# Run full offline test suite (127 tests, about 10 seconds)
../.venv/bin/python manage.py test desk

# Live commands refuse to run in sample mode (decision 015). Run them against the live desk:
# with the settings below for data/live.sqlite3, or with DATABASE_URL set for PostgreSQL.

# Run live news collection pass
DESK_DATABASE=../data/live.sqlite3 DESK_SAMPLE_MODE=0 ../.venv/bin/python manage.py collect_news

# Run live social & broadcast collection pass
DESK_DATABASE=../data/live.sqlite3 DESK_SAMPLE_MODE=0 ../.venv/bin/python manage.py collect_social --sync-sources

# Recalculate 60-minute momentum trends
DESK_DATABASE=../data/live.sqlite3 DESK_SAMPLE_MODE=0 ../.venv/bin/python manage.py recompute_trends

# Continuous worker (poll feeds every 5m, recalculate trends every 60s)
DESK_DATABASE=../data/live.sqlite3 DESK_SAMPLE_MODE=0 ../.venv/bin/python manage.py run_worker

# Submit an analyst manual link or WhatsApp field tip
../.venv/bin/python manage.py submit_social_link --platform facebook --account "Kumasi Traders" --text "Protest over power outages"

# Generate shift intelligence brief
DESK_DATABASE=../data/live.sqlite3 DESK_SAMPLE_MODE=0 ../.venv/bin/python manage.py brief_shift --title "Morning Intelligence Brief" --telegram

# Provision or list staff accounts
../.venv/bin/python manage.py provision_user --list

# Back up the database (SQLite or PostgreSQL), check it reads back, keep 14 days
../.venv/bin/python manage.py backup_desk --keep-days 14

# Check an existing backup can be read back (the restore check)
../.venv/bin/python manage.py backup_desk --verify ../backups/<file>
```

**Running safely (Phase 1 hardening):**

- **Sign-in lockout:**
  - After 5 failed attempts since its last successful sign-in, a username is refused for 15 minutes.
  - After 20 failures, an address is refused.
  - Every sign-in, failure, refusal and sign-out is in the read-only **Sign-in events** log in `/admin/`.
  - To unlock someone early, wait out the window or reset their password with `provision_user`.
- **Two-step sign-in:**
  - On a live desk (sample mode off), everyone enters a 6-digit code from an authenticator app after their password, including in `/admin/`.
  - Each person sets up their phone at their first sign-in and gets 10 backup codes.
  - For a lost phone, run `provision_user --username NAME --reset-two-step`. If the phone was stolen, also give a new password with `--random-password`.
  - Codes are recorded in the **Sign-in events** log. See decision 013.
- **Health check:** `/healthz/` needs no sign-in and returns only a status. Point an uptime monitor at it. It answers 503 when:
  - the database is down;
  - on a live desk, trends are older than 5 minutes or collection is older than 20.
- **Backups:** `deploy/npp-desk-backup.timer` (or the crontab line) backs up daily at 02:15 GMT. Copy the backups folder off the server.
  - **Restore SQLite:** stop the services, then `gunzip` the backup over the database file.
  - **Restore PostgreSQL:** stop the services, then `pg_restore --clean --if-exists --no-owner -d npp_desk <file>.dump`.
- **Behind Nginx:** set `DESK_TRUST_PROXY_HEADERS=1` in the server's `.env`.
- **Automatic tests:** `.github/workflows/tests.yml` runs the checks and the test suite on every push to `main` and every pull request.

---

## 6. Plan from pilot to live war room

**Done:**

- **Phase 0:** complete.
- **Phase 1:** the code is done. What is left needs a hosting decision.

### Owner actions (not for a coding agent)

1. **Make the GitHub repository private.** It is still public: GitHub → Settings → Danger Zone → Change visibility.
2. **Change passwords that were ever written in the repository or in a chat.** This covers the staff accounts and the PostgreSQL accounts, on every copy of the desk and anywhere they were reused.
   - Run these commands in the Terminal app.
   - Never paste a password into an agent chat.
3. **Restart the desk servers** (section 2), after running `migrate` on PostgreSQL.
4. **Decide the hosting provider and monthly budget.** This unblocks the rest of Phase 1.
5. **Decide the remaining budgets and ownership:**
   - budget for X API access;
   - budget for a social-listening vendor;
   - who owns registration with Ghana's Data Protection Commission (Act 843) and the data retention policy.

### Phases

**Phase 1 · run it on a real server (what is left):**

- A hosted server and domain with HTTPS.
- Managed PostgreSQL, with off-site backups and a tested restore.
- Error and uptime alerts.
- A staging copy.

**Phase 2 · cover where Ghanaians talk:**

- **X:** paid API access.
- **YouTube:** search and comments, through YouTube's API.
- **Facebook, Instagram and TikTok:** realistically only through a licensed social-listening vendor.
- **Radio:** morning shows, with Twi speech-to-text that a person checks.
- **WhatsApp:** a consent-based tip line.
- **Analysts:** a web form for submitting links, replacing the command-line tool.
- **Peace FM:** a feed address from the outlet.

**Phase 3 · smarter triage:**

- Group the same story across outlets.
- Twi and Pidgin keyword packs, checked by native speakers.
- Spike alerts.
- Draft claim extraction and translation, always marked as drafts for a person to approve.

**Phase 4 · run it as a war room:**

- A staffed trial week, with a rota and on-call cover.
- Response-time targets and runbooks.
- A library of approved responses.
- Metrics: time to assign an owner and time to a finding.

**Throughout:**

- Public content only.
- No files on private individuals.
- No automated posting or bot amplification.
- The same treatment for criticism of the NPP and scrutiny of the government.

### Work an agent can start without new credentials or budget

1. **Web form for analyst submissions** (Phase 2): paste Facebook, TikTok, X and WhatsApp links in the browser instead of using `submit_social_link`. It must keep WhatsApp tips out of trend counts (decision 002) and work without JavaScript.
2. **Group the same story across outlets** (Phase 3).
3. **Spike alerts** (Phase 3), within the trend method in `architecture.md` and `decisions.md`.
4. **Figma:** add the three two-step screens (set-up, code entry, backup codes) to the prototype. The IDs are in `design/figma-ledger.json`.

### Needs the owner first

- **Live Telegram bot:**
  - Needs a bot token and war room chat ID in `.env`, entered by the owner. Ask before connecting it.
  - Never write either one into the repository.
- **X, Meta, TikTok, Telegram or any other source that needs credentials:** ask the owner before adding it (`AGENTS.md`).
- **Staffed shift trial:** needs people on shift. Follow it end to end:
  - an issue is created;
  - an analyst submits a finding;
  - the editor approves it;
  - the case escalates to L4 and the Telegram alert arrives.
