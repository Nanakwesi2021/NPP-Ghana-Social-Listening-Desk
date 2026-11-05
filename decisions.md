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

## 011 · Keep the demo sign-in away from real accounts and live deployments

**Status** Accepted · **Date** 2026-11-03 · **Owners** Engineering and security desk

**Context.** The Sample shift lets people sign in without a password by choosing a sample person. It opened any account in a desk group, so it could also open a real duty editor's account. It switched on whenever `DJANGO_DEBUG` was missing, so a server started without its `.env` file could have been opened by anyone. Staff passwords had also been written into `HANDOFF.md` in a public repository.

**Options considered.** Deleting the demo sign-in would remove the easiest way to show the desk. Relying on operators to set `DESK_SAMPLE_MODE=0` leaves one forgotten variable between the desk and an open door. Narrowing who the sign-in can open, and refusing sample mode when settings look live, keeps the demo and closes both gaps in code.

**Decision and rationale.**
- **Who it can open:** only usernames listed in `tests/fixtures/sample_shift/shift.json` that have no usable password (`desk.ingest.sample_people`).
- **When it runs:**
  - Sample mode defaults on only for a plain local demo.
  - It defaults off when debug is off, a `DATABASE_URL` is set, or `DJANGO_ALLOWED_HOSTS` names a public host.
  - Forcing it on in those settings stops the start-up with an explanation (`desk_site/safety.py`).
- **Secrets:** no passwords, tokens or chat IDs in the repository. `AGENTS.md` now states this as a rule.
- **Database ports:** Docker publishes PostgreSQL and Redis on loopback only, and PostgreSQL needs an explicit password.

**Consequences.** A real account can only be opened with its password. A misconfigured server falls back to normal sign-in instead of an open desk. The passwords that were published must still be changed, because git history keeps them.

**Revisit when** single sign-on or two-step sign-in replaces passwords. See `src/desk_site/safety.py` and `src/desk/tests/test_safety.py`.

## 012 · Sign-in lockout, health check and verified backups before going live

**Status** Accepted · **Date** 2026-11-03 · **Owners** Engineering and operations lead

**Context.** The desk is moving from laptops to a server reachable over the internet. Three things had to exist first:
- protection against password guessing
- a way for an outside monitor to see that the desk and its worker are alive
- backups that are known to restore

The Nginx configuration also forwarded the visitor's protocol and address in headers that Django was never told to trust. With `SECURE_SSL_REDIRECT` on, every request would have redirected forever.

**Options considered.**
- **Lockout:** a third-party package would add a dependency for one feature. Counting failures in the database works across all Gunicorn workers with no cache server.
- **Health:** a status page with counts and names would tell outsiders what the desk watches. A bare status with ages does not.
- **Backups:** copying the SQLite file while it is being written can corrupt the copy. SQLite's online backup API and `pg_dump` are designed for this.

**Decision and rationale.**
- **Lockout:**
  - 5 failures since the last successful sign-in lock a username for 15 minutes. 20 failures lock an address.
  - The check runs before the password is tested, on both `/login/` and `/admin/`.
  - Every attempt goes to a read-only `SignInEvent` log.
- **Health:** `/healthz/` reports the database and, on a live desk, the age of the latest trend calculation and poll. It answers 503 when stale.
- **Backups:**
  - `backup_desk` reads every backup back before keeping it: SQLite's integrity check, or `pg_restore --list`.
  - Files are readable by their owner only, and backups older than 14 days are pruned.
  - It gives up with an error rather than waiting forever on a busy database.
- **Proxy headers:** they are trusted only when `DESK_TRUST_PROXY_HEADERS=1`, because anyone can forge them on a server reachable without Nginx.

**Consequences.** Guessing a password online is slow and visible, and a stopped worker pages someone. Backups are tested when they are made. Backups on the same server still need copying off-site, which depends on the hosting choice.

**Revisit when** single sign-on or two-step sign-in is added, or when off-site backup storage is chosen. See `src/desk/signin.py`, `src/desk/health.py` and `src/desk/backups.py`.

## 013 · Two-step sign-in with an authenticator app

**Status** Accepted · **Date** 2026-11-03 · **Owners** Engineering and operations lead

**Context.** The desk will be reachable over the internet and holds the party's monitoring, case notes and escalations. A password alone can be phished, reused from another breached site or seen over a shoulder. The user chose passwords with two-step sign-in over Google Workspace single sign-on.

**Options considered.**
- **Codes by text message:** need a paid SMS provider, and a SIM swap defeats them.
- **Writing the code checks ourselves:** small, but replay protection, throttling and clock drift are easy to get subtly wrong.
- **django-otp:** a long-maintained library for authenticator-app codes and backup codes, with replay protection and throttling built in. segno draws the QR code as inline SVG, so set-up works without JavaScript.
- **Security keys or passkeys:** strongest, but every person needs a key or a compatible phone, and the pages need JavaScript.

**Decision and rationale.**
- Use django-otp with authenticator-app codes (6 digits, every 30 seconds) and 10 single-use backup codes.
- Require it for every account when sample mode is off (`DESK_TWO_STEP_REQUIRED`). An account that has set it up is asked for a code even where it is not required.
- A middleware sends anyone who has signed in but not entered a code to the code page, or to set-up if they have no phone yet. Only sign-in, sign-out, `/healthz/` and the two-step pages open before the code. The admin and password change do not.
- A password alone can never add a phone to an account that already has one. An administrator resets a lost phone with `provision_user --reset-two-step`.
- A used code is refused, and each wrong code doubles the wait before the next one is checked.

**Consequences.**
- Everyone needs a smartphone with an authenticator app, and a safe place for their backup codes.
- Between an account being created and its owner's first sign-in, the password alone lets someone set up a phone. Hand passwords over privately and have people sign in promptly. `provision_user --list` shows who has not set up.
- Someone who knows a password can make its owner wait by entering wrong codes. That means the password is known, so reset it.
- Two new dependencies: django-otp and segno.

**Revisit when** the party adopts Google Workspace or another identity provider, or staff can use passkeys. See `src/desk/twostep.py` and `src/desk/tests/test_two_step.py`.

## 014 · Automated cross-network spike detection, breakout alerts and unified scanning

**Status** Accepted · **Date** 2026-11-04 · **Owners** Research desk lead and engineering

**Context.** As social narratives and breaking stories evolve rapidly across Ghanaian portals and social media networks (News, YouTube broadcasts, X, Facebook, TikTok), the research desk and campaign War Room need early automated warning when a topic surges with high velocity or breaks out across multiple monitored networks simultaneously.

**Options considered.**
- **Manual analyst monitoring only:** relies on human observation in shift queues; risks missing early morning spikes or fast weekend breakouts.
- **Immediate alert on every individual post:** floods the War Room channel with noise and duplicate notifications.
- **Windowed cross-network breakout engine with hourly deduplication:** evaluates the desk's 60-minute window calculations against precise momentum and network diversity thresholds, deduplicating alerts by topic, hour, and surge tier.

**Decision and rationale.**
- Classify a topic as a **Key Trending Breakout** when:
  1. It meets the desk minimum mention threshold (`current_count >= 5`) and is rising (`change > 0`).
  2. And satisfies at least one breakout condition:
     - **Cross-Network Breakout:** observed on $\ge 2$ distinct monitored platforms (e.g., News + YouTube, or YouTube + X, or News + Facebook).
     - **High-Velocity Surge:** net change $\ge 5$ mentions compared to the previous 60-minute window.
- Persist breakouts in a dedicated `TrendAlert` model with channel, tier, momentum, and platform counts.
- Push formatted HTML notifications to the Telegram War Room with direct links to the desk trend view (`/trends/<slug>/`), platform distribution breakdown, and subject tags.
- Deduplicate on `trend:{topic.slug}:{YYYYMMDDHH}:{tier}`: alerts are sent once per hour window for a tier (`surge_med` for change $\ge 5$, `surge_high` for change $\ge 10$), allowing escalation when momentum accelerates while preventing alert spam.
- Implement a unified scanner `scan_networks` that unifies news feed collection, YouTube channel feeds, X search, 60-minute trend recomputation, and breakout alert dispatch in one command.
- Surface active breakouts prominently on the Desk Overview web UI (`overview.html`) using accessible `.banner--info` components and row-level `Breakout` chips.
- Add an in-browser analyst submission interface (`/sources/submit/`) allowing analysts to record observed Facebook, TikTok, WhatsApp, and X links directly with instantaneous auto-tagging and trend recomputation.

**Consequences.**
- The War Room receives timely, actionable alerts on surging cross-network topics without manual intervention.
- The 127 existing tests continue to pass; 8 new offline tests verify breakout classification, formatting, deduplication, command execution, and web submission.
- WhatsApp tips remain strictly excluded from trend calculations per Decision 002.
- Red styling remains strictly reserved for confirmed Critical · L4 cases per editorial guidelines; breakouts use brand blue tokens.

**Revisit when** alerting needs expand to SMS or additional chat channels, or when threshold tuning is requested by shift leads. See `src/desk/alerts.py`, `src/desk/models.py`, and `src/desk/tests/test_alerts.py`.

## 015 · Live commands refuse to run in sample mode

**Status** Accepted · **Date** 2026-11-05 · **Owners** Engineering and operations lead

**Context.** A plain local run uses the Sample shift database (`data/desk.sqlite3`) with sample mode on. Nothing stopped a live command from running there. On 3 November a live collection and a trend calculation did. Real YouTube items were stored beside the fictional ones, every fictional outlet showed as "collection delayed", and a calculation for 19:19 GMT became the newest, ahead of the 10:37 one that tells the tariff 4 → 12 story. `recompute_trends` and `scan_networks` also prune calculations more than 7 days older than the one they store, so a run a week later would have deleted the 10:37 calculation outright.

**Options considered.**
- **Rely on people setting the variables:** one forgotten `DESK_SAMPLE_MODE=0` is enough, and the handoff listed the live commands without the live settings.
- **Refuse when the database file is `data/desk.sqlite3`:** catches the same accident, but a server may keep a live desk at that default path with sample mode off.
- **Refuse when sample mode is on:** sample mode already means "this is the demo database", and it can never be on for a live deployment (decision 011).

**Decision and rationale.**
- One helper, `refuse_in_sample_mode` in `desk_site/safety.py`, raises a `CommandError` when `DESK_SAMPLE_MODE` is on. Each live command calls it first, before it reads a feed or writes to the database.
- It covers every command that reads a live source, stores live trend data or sends to the war room: `collect_news`, `collect_social`, `scan_networks`, `run_worker`, `recompute_trends` and `brief_shift --telegram`.
- The error names the database it protected and gives the two ways to run the command for real: `DESK_DATABASE=../data/live.sqlite3 DESK_SAMPLE_MODE=0`, or `DATABASE_URL` for PostgreSQL.
- `replay_sample` keeps working, and still recalculates the Sample shift's own trends at 10:37.
- `brief_shift` without `--telegram` keeps working, because the brief on screen only reads.
- `submit_social_link` is not covered: it reads no network and stores only what the person typed, just like the demo's web form.

**Consequences.**
- Real and fictional data can no longer mix through these commands.
- In sample mode, `recompute_trends --as-of` is refused too. `replay_sample` recalculates the sample's trends.
- Live servers are unaffected: sample mode is always off there, so the systemd units and crontab lines run as before.
- Tests that run these commands now turn sample mode off first.
- The Sample shift database damaged on 3 November is not repaired by this change. `replay_sample --wipe` restores it but discards demo decisions, so it is left to the owner.

**Revisit when** a live command needs a sample-mode variant, or the demo moves to its own deployment. See `src/desk_site/safety.py` and `src/desk/tests/test_sample_guard.py`.
