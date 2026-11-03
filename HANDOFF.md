# Handoff · NPP Ghana Social Listening Desk

Updated on **3 November 2026** following the Antigravity sprint. All 70 offline unit tests pass, the repository is tracked and pushed to GitHub (`Nanakwesi2021/NPP-Ghana-Social-Listening-Desk`), PostgreSQL 16 is provisioned with trigram fuzzy search and native JSONB indexing, and live news and 7 national broadcast channels are actively monitored.

Rules for coding agents remain in `AGENTS.md`.

---

## 1. Resume Work in Claude Code

From your terminal, navigate to the project directory and start Claude:

```sh
cd /Users/barnabaseshun/Documents/NPP-Ghana-Social-Listening-Desk
claude
```

Confirm the current test baseline before making changes:

```sh
cd src
../.venv/bin/python manage.py test desk
```
**Expected:** `Ran 107 tests … OK`.

---

## 2. Active Local Services & Ports

Three environments are currently active and listening on localhost:

| Port | Backend Database | Mode | Description | Accounts |
| :--- | :--- | :--- | :--- | :--- |
| **8000** | `data/desk.sqlite3` | Sample shift (`DESK_SAMPLE_MODE=1`) | Offline tariff crisis demo with 1-click persona switcher | `ama` (Editor), `kwame` (Analyst) |
| **8001** | `data/live.sqlite3` | Live desk (`DESK_SAMPLE_MODE=0`) | Local file-based live listening desk with background worker | Staff accounts: see `provision_user --list` |
| **8002** | **PostgreSQL 16** (`npp_desk`) | Live desk (`DESK_SAMPLE_MODE=0`) | High-concurrency production PostgreSQL with GIN trigram search | Staff accounts: see `provision_user --list` |

Passwords are never written in this repository. Create or reset them with `provision_user --random-password` and hand them over privately. Each person then changes theirs at `/password-change/`.

---

## 3. What Was Implemented (Antigravity Sprint)

1. **Test Suite Expansion:** Expanded offline test coverage from 34 to **70 passing tests**.
2. **Version Control:** Git repository initialized and pushed to GitHub:
   `https://github.com/Nanakwesi2021/NPP-Ghana-Social-Listening-Desk`
3. **Telegram Pilot for Critical · L4 Escalations:**
   - Dedicated `CaseNotification` model (`0003_casenotification.py`).
   - HTML notification formatting with case references, urgency rationale, and clickable links to case file & evidence.
   - Deduplication keyed by `<ref>:l4`.
   - Failure isolation: missing credentials or network errors do not block case decisions, and visible retry button is provided to editors.
4. **Social & Broadcaster Collectors:**
   - **X API v2:** Recent search collector in `src/desk/collectors/x.py`. Automatically detects HTTP 429 rate limits and pagination ceilings, recording `PollRun.Result.CAPPED` to mark platforms partial in trend windows (Decision 005) while preserving received posts.
   - **Ghanaian Broadcast Channels:** Public Atom feed collector in `src/desk/collectors/youtube.py` monitoring 7 top national stations (JoyNews, Citi Tube, Peace FM / Despite Media, TV3 Ghana, UTV Ghana, Metro TV Ghana, Adom TV) with zero credentials.
   - **Analyst Submissions:** Management command `manage.py submit_social_link` for analysts to submit observed Facebook posts, TikTok clips, X posts, and WhatsApp field tips with automated language detection (English vs. Twi) and topic tagging. WhatsApp tips route into queue review but are strictly excluded from public trend momentum per Decision 002.
5. **Staff Provisioning & Self-Service Password Management:**
   - `manage.py provision_user`: role-gated CLI (`editor` with `desk.decide_case` permission, `analyst` for research, `admin` for superuser) with `--random-password`, `--deactivate`, `--activate`, and `--list`.
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

## 4. Key CLI Commands

All commands run from `src/`:

```sh
# Run full offline test suite (107 tests, about 10 seconds)
../.venv/bin/python manage.py test desk

# Run live news collection pass
../.venv/bin/python manage.py collect_news

# Run live social & broadcast collection pass
../.venv/bin/python manage.py collect_social --sync-sources

# Recalculate 60-minute momentum trends
../.venv/bin/python manage.py recompute_trends

# Continuous worker (poll feeds every 5m, recalculate trends every 60s)
../.venv/bin/python manage.py run_worker

# Submit an analyst manual link or WhatsApp field tip
../.venv/bin/python manage.py submit_social_link --platform facebook --account "Kumasi Traders" --text "Protest over power outages"

# Generate shift intelligence brief
../.venv/bin/python manage.py brief_shift --title "Morning Intelligence Brief" --telegram

# Provision or list staff accounts
../.venv/bin/python manage.py provision_user --list

# Back up the database (SQLite or PostgreSQL), check it reads back, keep 14 days
../.venv/bin/python manage.py backup_desk --keep-days 14

# Check an existing backup can be read back (the restore check)
../.venv/bin/python manage.py backup_desk --verify ../backups/<file>
```

**Running safely (Phase 1 hardening):**

- **Sign-in lockout:** a username is refused for 15 minutes after 5 failed attempts since its last successful sign-in. An address is refused after 20 failures. Every sign-in, failure, refusal and sign-out is in the read-only **Sign-in events** log in `/admin/`. To unlock someone early, wait out the window or reset their password with `provision_user`.
- **Health check:** `/healthz/` needs no sign-in and returns only a status. It answers 503 when the database is down or, on a live desk, when trends are older than 5 minutes or collection is older than 20. Point an uptime monitor at it.
- **Backups:** `deploy/npp-desk-backup.timer` (or the crontab line) backs up daily at 02:15 GMT. Copy the backups folder off the server.
  - **Restore SQLite:** stop the services, then `gunzip` the backup over the database file.
  - **Restore PostgreSQL:** stop the services, then `pg_restore --clean --if-exists --no-owner -d npp_desk <file>.dump`.
- **Behind Nginx:** set `DESK_TRUST_PROXY_HEADERS=1` in the server's `.env`.
- **Automatic tests:** `.github/workflows/tests.yml` runs the checks and the test suite on every push to `main` and every pull request.

---

## 5. Next Steps for Claude Code

1. **Staffed Shift Trial:** Run an end-to-end staffed shift cycle verifying issue creation, analyst finding submission, editor approval, and L4 Telegram escalation.
2. **Web-Based Link Submission:** Build an in-browser quick-submission modal for analysts on shift to paste Facebook/TikTok/WhatsApp links without CLI access.
3. **Live Telegram Bot:** Connect live `@BotFather` bot token and war room chat ID in `.env` to verify real mobile alert delivery.
