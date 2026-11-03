# NPP Ghana Social Listening Desk

## What the team should see when it signs in

The New Patriotic Party’s social media team needs to know which public issues are gaining attention in Ghana, which claims need checking, and who is handling each one. The proposed desk brings those decisions into one workspace. The desk gives equal editorial priority to two beats, criticism of the NPP and scrutiny of Ghana’s government. Reviewers apply the same evidence and urgency criteria to both. Broader public issues can also appear on the trend board. Each issue records the subject of the claim separately from the account or outlet reporting it.

| Desk view | Decision it supports | What the operator sees |
| --- | --- | --- |
| Trending now | What changed in the last hour? | Ranked topics, unique mentions in this and the previous hour, change in volume, platforms observed, last update in GMT and links to representative items. |
| Needs attention | Which issue needs someone now, and why? | The precise claim, reason for urgency, evidence status, assigned reviewer, next action and review deadline. A duty editor can flag a consequential item before it trends. |
| Issue detail | What can we substantiate? | A timeline linking original posts, reports and primary evidence. The reviewer records corrections and the basis for escalating or closing the issue. |
| Source coverage | How much of the conversation can we actually see? | Each source’s scope, collection method, last successful check and status. A failed collector leaves a visible gap in the relevant trend window. |

**Example desk decision (illustrative).** Several accounts share an image claiming an electricity tariff takes effect today. The dashboard groups the copies and shows where discussion is growing. A reviewer opens the cited tariff notice, checks the effective date and records the finding with a link. If the claim is time-sensitive, the editor assigns it immediately, even when its mention count is low. The next shift sees the evidence, owner and any outstanding action.

## Coverage in Ghana

The product aims for near-real-time visibility across the sources the team can actually observe. The board labels every trend by its observed source set. An outlet quoting a TikTok video counts as observation of that outlet. Direct observation on TikTok requires its own record.

| Channel | Proposed first usable coverage | Condition for calling it live |
| --- | --- | --- |
| X | Ghana-relevant topics, public statements and recent posts | Approved access for the chosen queries, successful polling and measured delay. |
| YouTube and broadcast media | Selected Ghanaian public channels and political programmes, with links to original videos or published summaries | Verify each channel and retrieval interval. A video available in Ghana can originate elsewhere. [YouTube search reference](https://developers.google.com/youtube/data/reference/rest/v3/search/list) |
| Facebook, Instagram and Threads | Begin with named public sources the desk can lawfully review. Record analyst-submitted links separately. | Document the specific surfaces approved for automated collection on each platform and demonstrate a working collector. |
| TikTok | Analyst-submitted public links until a permitted collection route is established | Confirm access suitable for this organisation. TikTok’s Research Tools have eligibility and project-approval requirements. [TikTok eligibility](https://developers.tiktok.com/products/research-api/) |
| WhatsApp | Voluntarily submitted tips for verification | Mark a submission as a tip. Its presence says nothing about how many groups received it. |
| Ghanaian news and radio portals | Citi Newsroom, Joy Online, Daily Graphic and Peace FM Online feeds named in the blueprint | Check feed availability and record the most recent successful poll for each outlet. Show these as news sources. |

Use Ghana-relevant public sources, named places and issue terms such as *dumsor* and *galamsey* to establish local relevance. Keep original English, Twi/Akan or Ghanaian Pidgin wording alongside any analyst translation. Rank aggregate issue activity. A count from monitored sources cannot establish support among Ghanaian voters.

## Current status and first milestone

The supplied blueprint contains a one-pass Python example for RSS, optional X search and optional Telegram delivery. A local Django desk in `src/` now replays a fictional **Sample shift** from `tests/fixtures/sample_shift`. It covers the trend board, the issue queue, issue review and source coverage. It needs no live credentials. The design lives in the [Figma prototype](https://www.figma.com/design/V3AeKWDIKpfXyd5ET413US); see [design/figma-resume.md](design/figma-resume.md). The next milestone measures live coverage and delay before the desk relies on alerts. See the [roadmap](roadmap.md).

## Run the desk locally (Sample shift)

From the repository root, with Python 3.12 or later:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python src/manage.py migrate
.venv/bin/python src/manage.py replay_sample
.venv/bin/python src/manage.py runserver
```

Open http://127.0.0.1:8000/ and choose a sample person on the sign-in page. Ama Owusu is the duty editor and Kwame Mensah is an analyst. The sample accounts have no passwords and exist only while `DESK_SAMPLE_MODE` is on, which is the default when `DJANGO_DEBUG=1`.

The demo flow:

1. As Kwame, open **Electricity tariff increase**, which shows 12 distinct mentions, up from 4.
2. Open the @AccraVoices item and take ownership (`a`).
3. Add the sample notice, mark the translation reviewed and submit a finding.
4. Switch to Ama from the account menu and approve the finding.
5. Back on the overview, the queue shows the saved owner and decision.

The shift clock starts at 10:37 GMT when the sample is first replayed and then advances in real time. Two flags reset it:

- `replay_sample --reset-clock` restarts the clock and keeps decisions.
- `replay_sample --wipe` restores the original sample and discards decisions.

Replaying again without a flag changes nothing.

Run the tests with `.venv/bin/python src/manage.py test desk`. The tests use saved feeds and need no network.

## Run against live feeds

Live mode reads the news feeds named in `src/desk/collectors/live_config.json` and keeps its data in a separate database, so the Sample shift stays intact. Run these from `src/`:

```sh
export DESK_DATABASE=../data/live.sqlite3 DESK_SAMPLE_MODE=0
../.venv/bin/python manage.py migrate
../.venv/bin/python manage.py createsuperuser
../.venv/bin/python manage.py run_worker
```

In another terminal, with the same two variables set, run `../.venv/bin/python manage.py runserver`.

Sign in at `/admin/` with the account you created and add desk users. Put editors in the **Duty editor** group and analysts in **Analyst**.

`run_worker` reads every feed every 5 minutes and recalculates the trend windows every minute. Add `--once` for a single pass.

To schedule the steps yourself instead, run the two commands separately, for example from cron:

- `collect_news` every 5 minutes
- `recompute_trends` every minute

A failing feed is recorded on its own and never stops the others. The coverage page shows each outlet's last successful check, the reason for any failure, and the median delay between publication and collection. That delay counts only items published after collection began, so the backlog a feed already held is left out.

Topics and their keyword rules are seeded once from the same config file. After that, edit them under **Topics** in the admin, then run `collect_news --retag` to re-apply the rules to stored items. Items that match no rule stay untagged.

Outlet status, checked live on 3 November 2026:

| Outlet | Address used | Result |
|---|---|---|
| Citi Newsroom | WordPress posts API (`/wp-json/wp/v2/posts`) | Collecting. The site sends every RSS path (`/feed/`, `?feed=rss2`, category feeds) to its homepage, so RSS is off. The public posts API returns titles, GMT dates, links and excerpts, and `robots.txt` allows all crawlers. |
| Joy Online | `https://www.myjoyonline.com/feed/` | Collecting. The feed sometimes parses with warnings. |
| Daily Graphic | `https://www.graphic.com.gh/news?format=feed&type=rss` | Collecting. Summaries are only “Read More …”, so tagging relies on headlines. |
| Peace FM Online | None | Not collected. The blueprint feed returns HTTP 404. `/rss`, `/feed` and `/rss.xml` return web pages, and the homepage advertises no feed. Ask Peace FM for a feed or API, then set it in `live_config.json`. |

After changing an outlet in `live_config.json`, run `collect_news --sync-sources` to apply it to an existing database. Without the flag, edits made in the admin are kept. In this sandboxed setup pip needed `--use-deprecated=legacy-certs` to reach PyPI.

## Technical stack

| Layer | Proposed implementation |
| --- | --- |
| Team interface | An internal browser dashboard served by a Python application. |
| Collection | Python worker with a separate adapter for each source. The blueprint example uses feedparser and Tweepy. |
| Analysis and storage | Explainable topic rules, time-window counts and SQLite for the single-host pilot. |
| Operations | A scheduler runs collectors at source-specific intervals. Select a host and team authentication before a shared pilot. |
| Notifications | Internal Telegram alerts link back to the issue record once delivery and access are tested. |

## Run the blueprint example locally

For a one-pass RSS check, use a fresh directory with Python 3 installed. Copy the Python block headed **Complete Source Code** in section 5 of the blueprint into a file named `warroom_monitor.py` there. These commands run that example, which requests live feeds. The planned dashboard milestone has its own acceptance criteria in [the roadmap](roadmap.md).

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install tweepy feedparser python-dotenv requests
X_BEARER_TOKEN= TELEGRAM_BOT_TOKEN= TELEGRAM_CHAT_ID= python warroom_monitor.py
```

Read the progress and matched headlines in the terminal. Empty credentials select the RSS-only path and suppress delivery. Each run starts with an empty set of processed items. The sample provides no web address or background service.

## Environment variables

| Variable | When needed | Purpose |
| --- | --- | --- |
| `X_BEARER_TOKEN` | For X searches | Authenticates recent-search requests. |
| `TELEGRAM_BOT_TOKEN` | For internal delivery | Authenticates the bot that sends an alert. |
| `TELEGRAM_CHAT_ID` | For internal delivery | Selects the authorized destination chat. |

The sample reads these values from the environment or a local `.env` file. Keep credentials out of version control. The RSS-only command above overrides all three for that run.

## Proposed project structure

| Path | Purpose |
| --- | --- |
| `warroom_monitor.py` | Command-line entry point used by the blueprint example. |
| `src/` | Collection, topic ranking, issue review, dashboard and alert delivery. |
| `tests/fixtures/` | Saved feed examples for repeatable tests, including duplicates and items in local languages. |
| `data/` | Local SQLite database for development runs. |
| `docs/` | Future operator runbooks and review procedures. The five planning files belong together at the repository root. |

## Useful commands and project documents

From the activated environment, `python -m pip check` checks installed dependency compatibility. Run `deactivate` when finished.

For build order, see [the roadmap](roadmap.md). For the path from source item to reviewed alert, see [the architecture](architecture.md). Record changes to the plan in [the decision log](decisions.md) and delivered changes in [the changelog](changelog.md).
