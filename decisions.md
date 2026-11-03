# Technical decisions

These proposals were recorded on 2026-11-03. Owners are suggested roles. The blueprint supplies a one-pass monitoring example. Each decision below governs the proposed shared hub.

## 001 · Give trends and critical issues separate views

**Status** Proposed · **Date** 2026-11-03 · **Owners** Research editor and social desk lead

**Context.** A quiet but credible report about the governing administration may require review before an unrelated, fast-moving Ghanaian trend. The team needs to see both.

**Options considered.** A single ranked feed is simple but buries low-volume critical reports. Chat alerts are fast but make ownership and case history hard to recover. A private dashboard can show a trend board and a case queue linked by shared sources.

**Decision and rationale.** Build the two dashboard views. Keep topic, subject, observed momentum, editorial priority and verification finding as separate fields. Allow a reviewer to open a case from a single item.

**Consequences.** Users can see why a story is popular and why a different case needs action. The team must maintain a topic taxonomy and staff the queue.

**Revisit when** desk trials show the same cases are repeatedly missed or users cannot find the evidence behind a ranking. See [architecture](architecture.md#critical-issues-and-fact-checking).

## 002 · Compare time windows with documented coverage

**Status** Proposed · **Date** 2026-11-03 · **Owners** Research desk and engineering

**Context.** Engagement totals, a short set of headlines and provider rankings each describe different slices of public activity. A burst of repeated polling or a new connection can look like a sudden surge.

**Options considered.** Summed engagement favors platforms that expose richer metrics. Provider rankings give a useful view of one service and use different methods. Counts of distinct observations in comparable windows have a visible denominator and can be reproduced.

**Decision and rationale.** Pilot equal 60-minute windows, a five-observation minimum and ranking by absolute growth using comparable sources. Show links, window counts, available platforms, data age and collection gaps. A cross-platform label requires observations on two or more platforms.

**Consequences.** Reviewers can recalculate a ranking from a fixture. Sparse topics may miss the display threshold, and restricted searches may miss real trends. Manual case creation stays available for a credible first report.

**Revisit when** coverage expands, source cadence changes, or analyst review shows repeated misses. See [trend calculation](architecture.md#from-observation-to-trend).

## 003 · Stage collection and retain the evidence locally in the pilot

**Status** Proposed · **Date** 2026-11-03 · **Owner** Engineering

**Context.** The sample resets its in-memory seen set on restart. Platform permissions and polling capacity are unconfirmed.

**Options considered.** A short-lived set suits the example. SQLite supports unique keys, transactions and historical comparisons on one host. A managed database better serves multiple hosts and adds operational setup.

**Decision and rationale.** Verify the interface with replayable fixtures and SQLite. Validate live RSS, then X independently. Evaluate additional providers according to access and usable coverage. Couple case events and pending notifications in one transaction so delivery can resume after interruption.

**Consequences.** Repeat runs preserve evidence and case history. The pilot needs backups and checks for write contention. Each integration needs its own coverage test.

**Revisit when** hosting requires separate worker and application hosts, measured concurrency exceeds SQLite’s capacity, or retention demands change. See the [roadmap](roadmap.md).

## 004 · Require human review for findings and crisis escalation

**Status** Proposed · **Date** 2026-11-03 · **Owners** Research editor and hub administrator

**Context.** A keyword match may surface a claim, a quotation of that claim or a correction. The sample’s severity scorer has no evidence-review step.

**Options considered.** Automatic findings are immediate but conflate a match with verification. Manual review of every item consumes desk time. Rule-based discovery plus an assigned reviewer and editor focuses review on cases that need a decision.

**Decision and rationale.** Analysts assemble evidence and recommend findings. Editors approve dispositions and L4 escalation. Social desk users can flag items and read approved briefs. Administrators control access and sources. Preserve revisions, contrary evidence and unresolved findings in the case record.

**Consequences.** Staff can trace each finding to sources and an approver. Review times depend on desk coverage. The blueprint’s 30-minute L3 target needs a staffed pilot before adoption.

**Revisit when** queue age exceeds agreed targets or a permissions review identifies a gap. See [the review workflow](architecture.md#critical-issues-and-fact-checking).

## 005 · Treat capped polls as missing coverage

**Status** Proposed · **Date** 2026-11-03 · **Owners** Research desk and engineering

**Context.** A provider can keep answering while returning only its first page under a rate limit. Items still arrive, so a source can look healthy while most of its matches are missing.

**Options considered.** Counting any successful response as current hides the gap. Treating a capped response as a failure discards items the desk did receive. Recording the poll result as complete, capped or failed keeps the items and the gap.

**Decision and rationale.** Store each poll's result. Mark a source delayed after two poll intervals without a complete poll, even if capped polls are still returning items. Mark every trend window that contains a capped or failed poll as partial for that platform. Show “X partial” beside the affected counts. The offline desk applies this rule to the Sample shift: X has been capped since 09:40, yet its posts still appear.

**Consequences.** Counts stay usable, and editors see where they may be low. A long-capped source keeps showing as delayed until a complete poll succeeds.

**Revisit when** a provider reports exact truncation counts that would let the desk estimate the gap. See `src/desk/coverage.py`.

## 006 · Telegram alert dispatch for confirmed Critical · L4 cases

**Status** Proposed · **Date** 2026-11-03 · **Owners** Research desk, social desk lead and engineering

**Context.** When a duty editor confirms a case is Critical · L4, leadership and the war room require instant notification. However, external chat integrations must not block case decisions if the network fails or times out, must prevent duplicate alerts if re-triggered, and must link back directly to the case file and primary evidence on the desk.

**Options considered.** Direct synchronous call during escalation that raises errors blocks the editor if Telegram is unreachable. An asynchronous queue requires additional infrastructure (Redis/Celery) that complicates the lightweight single-host architecture. Transactionally recording a notification model coupled with safe dispatch handles failure gracefully without extra external daemons.

**Decision and rationale.** Persist each alert intent as a `CaseNotification` in the database with a unique deduplication key (`<ref>:l4`). Dispatch the alert via Telegram Bot API using structured HTML styling, including the case reference, subject, topic, verification state, editor urgency rationale, direct desk URL, and links to primary evidence. If delivery fails or credentials are unset, record the error status on the notification and show a visible warning to the operator with a retry action, keeping the case fully active and reviewable.

**Consequences.** The war room receives instant alerts with full evidence context. Duplicate alerts are prevented. Outages or credential issues do not interrupt desk operations.

**Revisit when** notification channels expand beyond Telegram (e.g. SMS, WhatsApp) or when multi-tier notification retry workers are required. See `src/desk/notifications.py`.

## 007 · Social media adapter design and rate-limit governance for X and YouTube

**Status** Proposed · **Date** 2026-11-03 · **Owners** Research desk, social desk lead and engineering

**Context.** Moving beyond news feeds requires ingesting public social discourse from X (Twitter) and broadcast YouTube channels. However, third-party social APIs enforce strict rate limits (HTTP 429) and monthly tweet caps. Adding credentials must adhere to strict server-side environment variable rules and robots.txt policies, without scraping around missing access or disguising user agents.

**Options considered.** Automated headless browser scraping of social feeds violates platform terms and is fragile against bot protections. Uncredentialed fallback modes combined with official API specifications allow safe deployment while awaiting provider approval.

**Decision and rationale.**
1. **Credentials & Environment:** Keep API secrets strictly in environment variables (`X_BEARER_TOKEN`, `YOUTUBE_API_KEY`). If a token is unset, the adapter leaves the source in an `awaiting` state without polling or failing other sources.
2. **Rate Limit & Truncation (Decision 005):** For X API v2 recent search (`GET /2/tweets/search/recent`), when an HTTP 429 occurs or response headers indicate `x-rate-limit-remaining: 0` or single-page result capping (`next_token`), the adapter records `PollRun.Result.CAPPED`. This keeps all collected items while marking the platform as partial in trend momentum windows.
3. **Public YouTube Broadcasts:** Prefer public Atom channel feeds (`/feeds/videos.xml?channel_id=...`) for Ghanaian news broadcasters (JoyNews, Citi Tube) which need zero credentials and respect public robots.txt rules.
4. **Offline Testing:** All social collector adapters support dependency-injected fetchers, enabling comprehensive offline unit testing without external network dependencies.

**Consequences.** The desk can run in uncredentialed, partial, or fully credentialed environments. Platform caps are visible to analysts, and trend momentum rankings reflect data gaps accurately.

**Revisit when** Meta/Facebook Graph API access is approved for campaign pages or when commercial data firehoses are connected. See `src/desk/collectors/x.py` and `src/desk/collectors/youtube.py`.

## 008 · Production backend architecture, deployment layout, and shift briefing

**Status** Proposed · **Date** 2026-11-03 · **Owners** Operations lead and engineering

**Context.** Operating a 24/7 political listening desk during active election cycles requires high concurrency between background collectors and multiple concurrent analysts and editors. SQLite file locks trigger write contention (`OperationalError: database is locked`) under multi-process loads. The desk also requires structured shift briefings (05:45 GMT morning brief and 21:30 handover).

**Options considered.** Continuing with SQLite file locking requires aggressive transaction timeouts and risks intermittent collector failures. Managed PostgreSQL provides row-level locking (MVCC), native JSONB for sparkline calculations, and connection pooling.

**Decision and rationale.**
1. **Database Support & Driver:** Installed modern `psycopg` (v3) and added dynamic `DATABASE_URL` parsing to support PostgreSQL 16+ in production with persistent connection pooling (`CONN_MAX_AGE=600`), while maintaining zero-config SQLite fallback for local demo and offline tests (`timeout: 20`).
2. **Native JSONB & GIN Indexing:** Configured native PostgreSQL JSONB indexing (`GinIndex`) on `TrendRow.platform_counts` and `TrendRow.buckets` for instantaneous sparkline bucket retrieval, as well as `btree_gin` and `pg_trgm` extensions.
3. **Full-Text & Trigram Search:** Enhanced the desk search endpoint to automatically detect PostgreSQL and use native `tsvector` (`SearchVector`) and trigram fuzzy matching (`TrigramSimilarity` on `pg_trgm`) across claims, excerpts, and Twi/English terms.
4. **Deployment Artifacts:** Provide production systemd unit definitions for Gunicorn (`npp-desk-web.service`) and the continuous worker (`npp-desk-worker.service`), alongside Nginx reverse proxy configuration with TLS/HSTS and static caching, plus a `docker-compose.yml` for PostgreSQL 16 and Redis.
5. **Shift Intelligence Briefing:** Add the `brief_shift` command to automatically generate morning and handover reports summarizing top momentum trends, critical queue cases, and source health.

**Consequences.** The platform is ready for immediate deployment on Linux cloud servers with PostgreSQL and continuous background ingestion.

**Revisit when** horizontal multi-node scaling requires Celery/Redis task clustering. See `src/desk_site/settings.py` and `deploy/`.

## 009 · Staff provisioning, account lifecycle, and self-service password management

**Status** Proposed · **Date** 2026-11-03 · **Owners** Operations lead, security desk and research editor

**Context.** Moving to live operations requires onboarding analysts and duty editors with strict role enforcement. Editorial rules require that only users with `desk.decide_case` can approve, escalate, close, or reopen cases. Relying solely on demo users (`ama`, `kwame`) or granting blanket superuser access compromises auditability and operational security. Staff also need self-service password rotation without administrative intervention.

**Options considered.** Relying purely on the Django `/admin/` portal requires granting all users `is_staff` and exposes underlying database tables to operational analysts. A dedicated provisioning command (`provision_user`) combined with authenticated self-service password management provides tight group mapping and streamlined onboarding.

**Decision and rationale.**
1. **Provisioning CLI (`manage.py provision_user`):** Implemented an administrative CLI tool supporting:
   - `--role editor`: assigns user to `Duty editor` group with explicit `desk.decide_case` permissions.
   - `--role analyst`: assigns user to `Analyst` group without decision authority.
   - `--role admin`: grants staff and superuser privileges.
   - `--random-password`: generates cryptographically secure 16-character temporary passwords.
   - `--activate` and `--deactivate`: handles staff offboarding or shift suspensions immediately.
   - `--list`: presents formatted terminal overview of usernames, roles, groups, and active status.
2. **Self-Service Password Management:** Integrated Django auth views (`/password-change/` and `/password-change/done/`) rendered using the desk's design system tokens, typography, and SVG icons.
3. **Masthead User Menu:** Added direct "Change password" and "Administration" shortcuts inside the masthead user dropdown in `base.html`.
4. **Offline Test Coverage:** Added 10 offline unit tests in `src/desk/tests/test_provisioning.py` verifying group membership, decision permission gates, password rotation, activation toggles, and view routing.

**Consequences.** The desk supports multi-user shifts with proper audit logs (attributing case events, reviews, and Telegram alerts to specific named personnel). Security hygiene is maintained via password rotation.

**Revisit when** single sign-on (SSO) via Google Workspace, SAML, or enterprise identity providers is required. See `src/desk/management/commands/provision_user.py`.

## 010 · Shift intelligence briefing schedules and Telegram War Room format

**Status** Proposed · **Date** 2026-11-03 · **Owners** Operations lead, research editor, communications director

**Context.** In addition to real-time Critical · L4 alert dispatches, leadership and duty editors require structured morning intelligence briefs (05:45 GMT, ahead of morning radio programmes such as Peace FM Kokrokoo and Joy Super Morning Show) and evening handover briefs (21:30 GMT). Fixed-width monospace text is difficult to read on mobile devices, and unlinked case references force recipients to manually search the desk.

**Options considered.** Sending unformatted plaintext requires horizontal scrolling on mobile. Email newsletters are too slow for fast-moving campaign war rooms. Structured Telegram HTML messages with status indicators, clickable desk hyperlinks, and concise sectioning deliver immediate situational awareness on mobile devices.

**Decision and rationale.**
1. **Command Line & Automation (`brief_shift`):** Management command compiles top momentum trends, open critical queue cases, and source coverage health.
2. **Rich Telegram HTML Formatting:** Formats briefs with mobile-optimized HTML, emoji status indicators (🟢, 🟡, 🔴, 🔵, 💬), and direct clickable hyperlinks to desk trends (`/trends/<slug>/`) and case files (`/issues/<ref>/`).
3. **Automated Timers:** Provided systemd timer units (`npp-desk-brief-morning.timer`, `npp-desk-brief-evening.timer`) and `crontab.txt` scheduled for 05:45 GMT and 21:30 GMT.
4. **Resilience & Testing:** Missing credentials or network issues skip dispatch without failing or blocking operations; covered by offline tests in `test_brief_shift.py`.

**Consequences.** War room leadership receives actionable briefings before key broadcast cycles with direct links to primary evidence.

**Revisit when** email or PDF briefing export is requested. See `src/desk/management/commands/brief_shift.py`.
