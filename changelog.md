# Changelog

## Unreleased

### Added

- **4 November 2026** — Cross-network spike detection, automated trending breakouts and unified scanning:
  - **Spike & Breakout Detection Engine:** `src/desk/alerts.py` evaluates 60-minute window momentum to detect cross-network breakouts (observed on $\ge 2$ distinct platforms) and high-velocity surges (net change $\ge 5$ mentions).
  - **Telegram War Room Push:** automated HTML alerts dispatched to the Telegram War Room with topic context, momentum indicators, network breakdowns, and direct links to the desk trend view. Deduplicated per topic, hour, and surge tier (`surge_med` vs `surge_high`) to eliminate alert fatigue.
  - **TrendAlert Model & Migration:** `TrendAlert` model (`0007_trendalert.py`) tracks alert records, delivery status (`sent`, `failed`, `disabled`), deduplication keys, and timestamps.
  - **Unified Network Scanner:** `scan_networks` management command unifies news collection (Citi Newsroom, Joy Online, Daily Graphic), YouTube video broadcasts, X search, trend momentum recomputation, and breakout dispatch in a single call.
  - **Continuous Background Worker:** `run_worker` updated to trigger breakout detection and dispatch automatically on every cycle.
  - **Desk Overview Breakout Banner:** high-visibility `.banner--info` banner and `Breakout` chips on `overview.html` highlighting surging topics and linking directly to trend details.
  - **Analyst Observation Submission:** web-based submission form at `/sources/submit/` allowing analysts to submit observed posts from Facebook, TikTok, WhatsApp tips, and X with auto-tagging and immediate trend recomputation without terminal access.
  - **Offline Test Suite:** 8 new offline tests in `test_alerts.py` covering breakout classification, notification formatting, deduplication, command execution, and web submission (135 total tests passing).

- **3 November 2026** — Two-step sign-in:
  - **Codes:** after the password, the desk asks for a 6-digit code from an authenticator app on the person's phone. Every account needs it whenever sample mode is off, so every live desk asks for codes. `/admin/` and password changes need the code too.
  - **Set-up:** at their first sign-in, each person scans a QR code (or types a key) and confirms it with a code. They then get 10 single-use backup codes, shown once.
  - **Safety:** a used code is refused, each wrong code doubles the wait before the next try, and a password alone can never add a phone to an account that already has one. Accepted and refused codes, set-ups and resets go in the sign-in log.
  - **Lost phone:** `provision_user --username NAME --reset-two-step` removes the phone and backup codes, and the person sets up again at their next sign-in. `provision_user --list` shows who has not set up.
  - **Account menu:** **Two-step sign-in** shows how many backup codes are left, makes new ones and sets up a new phone.

- **3 November 2026** — Phase 1 hardening for running the desk on a real server:
  - **Sign-in lockout:** 5 failed attempts lock a username for 15 minutes, and 20 failures lock an address. The lockout also covers `/admin/`. A read-only sign-in log records every sign-in, failure, refusal and sign-out.
  - **Health check:** `/healthz/` lets uptime monitors check the database and, on a live desk, that trends and collection are fresh. It needs no sign-in and reveals no desk content.
  - **Backups:** `backup_desk` backs up SQLite or PostgreSQL, reads each backup back before keeping it, writes files readable by their owner only, and prunes old backups. A daily systemd timer and a crontab line run it.
  - **Automatic tests:** a GitHub Actions workflow runs the checks and the full suite on every push and pull request.
  - **Faster tests:** the suite runs in about 10 seconds instead of about a minute, using a fast password hasher in tests only.

- **3 November 2026** — Prepared the initial project documentation from the NPP war room blueprint. The [README](README.md) identifies what the embedded Python example does and how to run one RSS pass locally.
- Defined the first implementation milestone and acceptance criteria in the [roadmap](roadmap.md). The initial test uses a saved feed so a developer can check topic matching and duplicate handling without live credentials.
- Documented the proposed data flow and implementation choices in the [architecture](architecture.md) and [decision log](decisions.md).

- **3 November 2026** — Added a high-fidelity [Figma prototype](https://www.figma.com/design/V3AeKWDIKpfXyd5ET413US). It includes the design system, seven desktop screens, four mobile screens, a states board and two clickable Sample shift flows.
- **3 November 2026** — Added a local Django desk (`src/`) that replays the fictional Sample shift with no credentials:
  - **Trends:** an editor sees the electricity-tariff topic rise from 4 to 12 distinct mentions on News + X, with X marked partial.
  - **Queue:** a single-source safety report stays in the queue without trending.
  - **Review:** an analyst takes ownership, compares the post with a dated notice and submits a finding; the duty editor approves it.
  - **Record:** every step is saved with its author, role and GMT time.
  - **Restarts:** replaying the inputs after a restart leaves counts, rankings and the queue unchanged.
  - **Source coverage:** shows quiet and delayed sources differently.

- **3 November 2026** — Added live news collection with `collect_news`, `recompute_trends` and `run_worker`:
  - **Collection:** each outlet's feed is read every 5 minutes into a separate live database. Items are stored once per guid, with publication and collection times.
  - **Failures:** a failing feed is recorded with its reason and does not stop the others. A feed that returns a web page says so.
  - **Topics:** starting topics come with keyword rules that editors can change in the admin. Items that match no rule stay untagged.
  - **Freshness:** the coverage page shows each outlet's median publication-to-collection delay.
  - **Live outlets:** Citi Newsroom, Joy Online and Daily Graphic collect. Citi uses its public WordPress posts API because its RSS is switched off. Peace FM Online publishes no usable feed, so it is listed but not polled.

- **3 November 2026** — Added internal Telegram alert pilot for confirmed Critical · L4 escalations:
  - **Dispatch:** when a duty editor escalates a case to Critical · L4, a structured alert is dispatched to the designated internal Telegram chat with case details, editor urgency rationale, direct links to the case file and primary evidence.
  - **Deduplication:** keyed by `<ref>:l4`; duplicate escalations or re-triggers never send a second message.
  - **Resilience:** network timeouts or missing bot credentials do not block or rollback the case escalation. The failure is recorded and displayed prominently on the case detail page with an editor-only retry option.
  - **Offline tests:** six new offline tests verify alert formatting, successful dispatch, deduplication, failure tolerance, disabled state, and editor retry.

- **3 November 2026** — Added social media adapter architecture and rate-limit governance for X and YouTube:
  - **X Recent Search Adapter:** polls X API v2 using server-side `X_BEARER_TOKEN`. Detects rate limits (HTTP 429 and `x-rate-limit-remaining`) and pagination ceilings, recording `PollRun.Result.CAPPED` to mark platform coverage as partial in trend windows (Decision 005) while preserving received posts.
  - **YouTube Public Channels Adapter:** ingests public broadcast Atom feeds for Ghanaian news channels (JoyNews, Citi Tube) without credential requirements.
  - **Management Command:** added `collect_social` with `--sync-sources` to run collection passes or gracefully report awaiting credentials.
  - **Offline Tests:** added six offline unit tests covering complete ingestion, rate-limit capping, HTTP 429 handling, and channel feed parsing.

- **3 November 2026** — Added production deployment configuration, environment specifications, and shift briefing:
  - **Environment & Configuration:** added `.env.example` and native `.env` loading in `settings.py`. Added PostgreSQL `DATABASE_URL` support with connection pooling, and configured production security headers (HSTS, SSL redirect, nosniff, frame denial).
  - **Live Broadcast Channels:** verified and connected real live YouTube Atom feeds for JoyNews (`UChd1DEecCRlxaa0-hvPACCw`), ChannelOne TV / Citi Tube (`UCUTeE-as508hixQrNVHO7vQ`), and Peace FM / Despite Media (`UC5tDLzkXRDGSc98L2gTg1gQ`).
  - **Deployment Files:** generated `gunicorn.conf.py`, `npp-desk-web.service`, `npp-desk-worker.service`, and `nginx.conf` in `deploy/`.
  - **Shift Intelligence Briefing:** added `brief_shift` management command for 05:45 GMT morning briefs and 21:30 handovers with optional Telegram dispatch.

- **3 November 2026** — Added PostgreSQL 16+ integration, native JSONB indexing, and full-text/trigram search:
  - **Driver & Driver Lock:** installed `psycopg` (v3.3.7) with binary wheels, updated `requirements.lock`, and enabled `django.contrib.postgres`.
  - **Native JSONB & GIN Indexes:** added `0004_case_desk_case_claim_trgm_and_more.py` migration enabling `TrigramExtension`, `BtreeGinExtension`, and GIN indexes on `TrendRow.platform_counts`, `TrendRow.buckets`, `Item.excerpt`, and `Case.claim`.
  - **Intelligent Search Engine:** updated `views.search` to use PostgreSQL native `SearchVector` full-text search and `TrigramSimilarity` fuzzy matching for English and Twi terms, with automated fallback to `__icontains` on SQLite.
  - **Docker Compose:** provided `deploy/docker-compose.yml` for PostgreSQL 16 and Redis.
  - **Offline Tests:** four new unit tests in `test_postgres_backend.py` covering settings parsing, GIN index definitions, and search routing.

- **3 November 2026** — Added staff user provisioning CLI, role lifecycle governance, and self-service password management:
  - **Provisioning Tooling:** added `provision_user` management command to create, configure, list, and toggle real staff accounts for `Duty Editor` (with `desk.decide_case`), `Analyst`, and `Hub Admin`. Supports random high-entropy temporary passwords and terminal account overviews.
  - **Self-Service Password Rotation:** added authenticated `/password-change/` and `/password-change/done/` views styled in the desk design system.
  - **User Masthead Navigation:** integrated direct shortcuts to "Change password" and "Administration" within the account menu.
  - **Offline Unit Tests:** ten new offline unit tests in `test_provisioning.py` verifying group membership, decision permissions, password rotation, and account deactivation/reactivation.

- **3 November 2026** — Expanded live social media feeds, broadcast monitoring, and analyst submission workflows (Path B):
  - **Expanded Broadcast Coverage:** connected seven verified Ghanaian broadcast TV and radio channels (JoyNews, Citi Tube / ChannelOne TV, Peace FM / Despite Media, TV3 Ghana, UTV Ghana, Metro TV Ghana, Adom TV) via public Atom feeds with zero credentials.
  - **Analyst Submission Tooling:** added `submit_social_link` management command for analysts to submit public Facebook posts, TikTok videos, X posts, and WhatsApp field tips with automated language detection (English vs Twi) and topic tagging.
  - **Editorial Governance Compliance:** WhatsApp tips trigger manual case reviews while remaining strictly excluded from trend momentum calculation per Decision 002.
  - **Comprehensive Source Sync:** updated `collect_social --sync-sources` to provision the full platform spectrum (News, X, YouTube, Facebook, TikTok, Instagram, Threads, WhatsApp tips) on the live sources dashboard.
  - **Offline Tests:** added four new unit tests in `test_social_collectors.py` verifying custom X queries, Facebook submissions, WhatsApp tips handling, and social source syncing (bringing test suite to 65 passing tests).

- **3 November 2026** — Live PostgreSQL 16 database provisioning, schema migration, and verification (Path C):
  - **Database & Extensions:** provisioned `npp_desk` on PostgreSQL 16.15 with native extensions `pg_trgm` and `btree_gin`. Applied all migrations including GIN indexes on `TrendRow.platform_counts`, `TrendRow.buckets`, `Item.excerpt`, and `Case.claim`.
  - **Staff Seeding & Role Gates:** provisioned initial administrative and editorial staff (`admin`, `ama.editor`, `kwaku.analyst`) on the PostgreSQL database with proper group mapping.
  - **Live Ingestion & Search:** ran real-time multi-channel news and broadcast collection directly into PostgreSQL 16 (79 broadcast items, 125 news articles), and verified fuzzy trigram similarity search scores across ingested articles.
  - **Live Service Deployment:** launched authenticated live desk server backed by PostgreSQL 16 at `http://127.0.0.1:8002/`.

- **3 November 2026** — Automated shift intelligence briefings and Telegram War Room dispatch (Path D):
  - **Structured War Room Briefings:** upgraded `brief_shift` command with rich Telegram HTML formatting (`format_telegram_brief`), status badges, and direct clickable links to desk trends and cases.
  - **Scheduling Automation:** provided production `crontab.txt` and systemd timers (`npp-desk-brief-morning.timer` for 05:45 GMT, `npp-desk-brief-evening.timer` for 21:30 GMT) for automated briefing generation.
  - **Offline Tests:** five new unit tests in `test_brief_shift.py` covering text summary generation, custom titles, Telegram HTML formatting, mocked API delivery, and unconfigured credential safety (bringing total test suite to 70 passing tests).

### Fixed

- **5 November 2026** — The top bar no longer overlaps on laptop and tablet screens. Before, between 768 and about 1,400 px wide, the desk time ran into "Evidence as of". As the window narrows, the bar now drops extras in steps:
  - **Below 1,420 px:** the date and "· fictional data".
  - **Below 1,220 px:** the person's name beside their initials; the brand and search box get smaller.
  - **Below 1,000 px:** the desk time.

  "Evidence as of", search and the account menu stay until the phone layout. On phones, the brand block is narrower, so "Sample shift" no longer touches the account initials.
- **5 November 2026** — Live commands can no longer write into the Sample shift:
  - **What happened:** on 3 November a live collection and trend calculation ran against the Sample shift database (`data/desk.sqlite3`) while sample mode was on. Real YouTube items went in, every fictional outlet showed as "collection delayed", and the tariff 4 → 12 story dropped off the overview.
  - **The guard:** with sample mode on, `collect_news`, `collect_social`, `scan_networks`, `run_worker`, `recompute_trends` and `brief_shift --telegram` now stop before touching the network or the database. The error says to run them with `DESK_DATABASE=../data/live.sqlite3 DESK_SAMPLE_MODE=0`, or with `DATABASE_URL` set to the PostgreSQL desk.
  - **Unchanged:** with sample mode off, the commands run exactly as before. In sample mode, `replay_sample` and `brief_shift` without `--telegram` still work.
  - **Repaired:** on 5 November, at the owner's request, `replay_sample --wipe --reset-clock` restored the Sample shift database. That removed the items from the live run and discarded the demo decisions.
  - **Offline tests:** 7 new tests in `test_sample_guard.py`. Five existing tests that ran these commands now turn sample mode off first.
- **3 November 2026** — Security fixes before live use (Phase 0):
  - **Demo sign-in:** the passwordless Sample shift sign-in now opens only the five fictional sample people listed in the fixture, and only accounts with no password. Before, it could open any staff account, including duty editors.
  - **Live settings:** sample mode now switches off by default when the settings look like a live deployment (debug off, a `DATABASE_URL`, or a public host). The desk refuses to start if sample mode is explicitly switched on there.
  - **Credentials removed:** staff passwords are removed from `HANDOFF.md`. They remain in earlier git history, so they must be changed.
  - **Docker Compose:** PostgreSQL and Redis now listen on loopback only, and PostgreSQL has no default password (`POSTGRES_PASSWORD` is required).
  - **Offline tests:** the social-collector test no longer reaches YouTube or X during the test run.
  - **HTTPS behind Nginx:** with `DESK_TRUST_PROXY_HEADERS=1`, Django trusts Nginx's `X-Forwarded-Proto`. Before, `SECURE_SSL_REDIRECT` would have redirected every request forever on the deployed server.
  - **PostgreSQL driver:** `requirements.txt` now includes it; before, only `requirements.lock` did.
  - **Fresh clones:** `data/` is now kept in the repository with a placeholder file. Without the folder, Django's start-up checks could not open the SQLite database, and the first GitHub test run failed.
  - **Database address:** a `DATABASE_URL` that is set but is not a `postgresql://` address now stops the desk with a clear error. Before, a placeholder or typo was ignored, and commands meant for PostgreSQL ran against the SQLite demo database.

### Changed

- **5 November 2026** — The desk is now called **War Room** wherever people see its name:
  - **On screen:** the masthead, browser tabs, sign-in, two-step and password pages, and `/admin/`.
  - **Telegram:** briefs start with `NPP WAR ROOM ·`.
  - **Authenticator apps:** new set-ups are labelled War Room. Phones already set up keep the old Listening Desk label, and their codes still work.
  - **Unchanged:** code names, web addresses, commands and design-token names.
- **3 November 2026** — Revised the brief around the NPP social media team’s shift workflow in Ghana. The first milestone now pairs a news feed fixture with social post fixtures and a dashboard that ranks rising issues. Reviewers can test the planned assignment and verification process before connecting live sources.
- Added platform-by-platform coverage requirements and pilot checks for freshness, collection failures and the time to review an urgent issue. The design distinguishes discussion of the NPP from claims about the governing party or a public institution.

### Release status

This revision updates the five planning documents. The supplied material identifies no deployed dashboard or versioned application release.

## Update rules

1. Record user-visible changes under Added, Changed, Fixed or Removed when the work lands. Describe the effect on an operator or analyst.
2. Link the issue or pull request when available. Keep planned work in the roadmap until its acceptance criteria pass.
3. At release time, move the entries under the published version and release date, then start a fresh Unreleased section.
4. Use Git history to recover exact revisions. Use this file to explain what changed between them.
