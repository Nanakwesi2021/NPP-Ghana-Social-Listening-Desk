# Handoff · NPP Ghana Social Listening Desk

Snapshot taken on 3 November 2026, when work moved from Claude Code to Antigravity. Everything below was working and verified at that point. The rules for coding agents are in `AGENTS.md`.

## 1. Open the project in Antigravity

1. In Antigravity, choose **Open Folder** and select `/Users/barnabaseshun/Documents/NPP-Ghana-Social-Listening-Desk`.
2. Antigravity loads `AGENTS.md` from the folder root as workspace rules. Keep that file.
3. Use the existing virtual environment at `.venv/` (Python 3.14.3). Select `.venv/bin/python` as the interpreter.
4. Confirm the baseline before changing anything:

```sh
cd src
../.venv/bin/python manage.py test desk
```

Expected: `Ran 34 tests … OK`.

If `.venv/` is missing (for example on another computer), recreate it with the exact versions:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.lock
```

The `.claude/` folder only holds Claude Code's preview settings, and Antigravity can ignore it.

## 2. What exists

| Part | Where | State |
|---|---|---|
| Product rules | `PRODUCT.md`, `README.md`, `architecture.md`, `decisions.md` (001–005), `roadmap.md` | Current |
| Figma prototype | [Figma file](https://www.figma.com/design/V3AeKWDIKpfXyd5ET413US) · status in `design/figma-resume.md`, node IDs in `design/figma-ledger.json` | Complete: design system, 7 desktop and 4 mobile screens, states board, notes, Django handoff board, two clickable flows |
| Django app | `src/` (project `desk_site`, app `desk`) | Working; 34 tests pass |
| Sample shift data | `tests/fixtures/sample_shift/` | The fictional demo shift: news and social streams, sources and polls, 6 cases |
| Collector fixtures | `tests/fixtures/rss/` | Offline feeds for tests |
| Live outlet config | `src/desk/collectors/live_config.json` | 4 outlets, 9 topics with keyword rules |
| Local databases | `data/desk.sqlite3` (sample), `data/live.sqlite3` (live) | Not in version control. Both can be rebuilt (section 4). |

The roadmap's **"Now"** milestone, the offline desk, is met. **"Next"** has started: live news collection works for three outlets.

## 3. Code map (`src/desk/`)

| File | Responsibility |
|---|---|
| `models.py` | Source, PollRun, Item, Topic (with `keywords`), TrendCalculation and TrendRow, Document, Case, Evidence, CaseEvent (append-only history), ShiftClock |
| `trends.py` | Window maths and ranking; persists one calculation per time |
| `coverage.py` | Source status (current, delayed, unavailable, manual, awaiting, tips), partial platforms, publication-to-collection delay |
| `workflow.py` | Case workflow: take ownership, evidence, translation review, finding, editor decisions. Every step writes a CaseEvent. |
| `ingest.py` | Idempotent Sample shift replay and the Duty editor and Analyst groups |
| `collectors/rss.py` | Live collector for RSS or Atom feeds and the WordPress posts API. One PollRun per outlet per pass; a failing feed stays isolated. |
| `tagging.py` | Keyword rules matched as whole words. Short all-caps acronyms are case-sensitive. |
| `views.py`, `urls.py` | Pages and POST actions. Editor checks run on the server. |
| `templates/desk/` | `base.html` (masthead, rail, mobile tab bar), overview, trend detail, issue detail, sources, search, partials |
| `static/desk/` | `tokens.css` (from Figma variables), `desk.css`, `js/refresh.js`, `js/keys.js`, `js/enhance.js` |
| `management/commands/` | `replay_sample`, `collect_news`, `recompute_trends`, `run_worker` |
| `tests/` | `test_trends.py`, `test_sample_shift.py`, `test_rss.py` |

## 4. Run it

All commands run from `src/`.

**Sample shift (demo)** uses `data/desk.sqlite3`:

```sh
../.venv/bin/python manage.py migrate
../.venv/bin/python manage.py replay_sample              # safe to repeat; changes nothing once loaded
../.venv/bin/python manage.py replay_sample --reset-clock # restart the demo clock at 10:37 GMT, keep decisions
../.venv/bin/python manage.py runserver
```

Open http://127.0.0.1:8000 and pick a sample person. Ama Owusu is the duty editor and Kwame Mensah is an analyst. In sample mode the accounts have no passwords.

**Live news** uses `data/live.sqlite3`:

```sh
export DESK_DATABASE=../data/live.sqlite3 DESK_SAMPLE_MODE=0
../.venv/bin/python manage.py migrate
../.venv/bin/python manage.py createsuperuser   # then add users to the "Duty editor" or "Analyst" group in /admin/
../.venv/bin/python manage.py run_worker        # collect every 5 min, recalculate every minute; add --once for one pass
../.venv/bin/python manage.py runserver         # in a second terminal with the same two variables
```

## 5. Live outlets (checked 3 November 2026)

| Outlet | Method | State |
|---|---|---|
| Citi Newsroom | WordPress posts API (its RSS is switched off) | Collecting |
| Joy Online | RSS | Collecting |
| Daily Graphic | RSS | Collecting. Summaries are “Read More …”, so tagging relies on headlines. |
| Peace FM Online | None | No public feed. Listed but not polled; needs a feed address from the outlet. |

After changing `live_config.json`, run `collect_news --sync-sources`.

## 6. Known gaps and open items

- **Peace FM Online:** needs a feed or API address from the outlet.
- **Twi sample line:** “Kanea ka no bɛkɔ soro ɛnnɛ anaa?” has not been checked by a fluent speaker.
- **Figma handoff board text:** it says `var(--color-bg-page)`, but the variables and `tokens.css` use `var(--bg-page)`. The code is right; only the board text is off.
- **X in the Sample shift:** modelled as capped since 09:40 (decision 005), so the app shows “11 capped polls” where the Figma screen says “2 missed polls”.
- **Live syndication:** copies of the same story across live outlets are not yet grouped. Only the sample data has grouped copies.
- **Old trend calculations:** live mode keeps one per minute, and pruning is not built yet.
- **No version control:** the folder is not a git repository. Create a baseline commit before you start, so every change can be seen and undone.

## 7. Next steps (roadmap “Next”)

1. Agree freshness targets per source, and run a staffed shift to measure collection delay against them.
2. Confirm the sign-in method, hosting, data retention and access owners before anyone outside the build team uses the desk.
3. Add X recent search, but only once API access and quotas are confirmed. Record query scope and capped pages.
4. Pilot Telegram alerts to one internal test chat. Duplicates must not re-alert, and failed deliveries must be visible.
5. Group syndicated copies across live outlets.
