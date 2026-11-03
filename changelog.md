# Changelog

## Unreleased

### Added

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

### Changed

- **3 November 2026** — Revised the brief around the NPP social media team’s shift workflow in Ghana. The first milestone now pairs a news feed fixture with social post fixtures and a dashboard that ranks rising issues. Reviewers can test the planned assignment and verification process before connecting live sources.
- Added platform-by-platform coverage requirements and pilot checks for freshness, collection failures and the time to review an urgent issue. The design distinguishes discussion of the NPP from claims about the governing party or a public institution.

### Release status

This revision updates the five planning documents. The supplied material identifies no deployed dashboard or versioned application release.

## Update rules

1. Record user-visible changes under Added, Changed, Fixed or Removed when the work lands. Describe the effect on an operator or analyst.
2. Link the issue or pull request when available. Keep planned work in the roadmap until its acceptance criteria pass.
3. At release time, move the entries under the published version and release date, then start a fresh Unreleased section.
4. Use Git history to recover exact revisions. Use this file to explain what changed between them.
