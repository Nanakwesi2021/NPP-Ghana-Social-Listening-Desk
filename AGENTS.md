# Rules for coding agents · NPP Ghana Social Listening Desk

Read `HANDOFF.md` before starting work. These rules protect the current, working state of the project.

## Before and after every change

1. Run the test suite from `src/`: `../.venv/bin/python manage.py test desk`. On 3 November 2026 (after Phase 1 hardening), 107 tests passed in about 10 seconds. If a test fails before you start, stop and report it. Do not change code to make it pass.
2. Run the same command after your change. Every existing test must still pass.
3. If a change alters what the desk shows or calculates, say so explicitly in your summary.

## Do not change unless the user asks for it in so many words

- **Sample shift fixtures:** the data in `tests/fixtures/sample_shift/`. The demo depends on its exact numbers: the tariff at 4 → 12 (+8), buckets `[0,1,0,1,1,1,1,1,2,3,2,3]`, the ranking order, and the coverage counts 2/1/2/2/1.
- **Existing migrations:** never edit or delete `src/desk/migrations/0001_initial.py` or `0002_live_news_feeds.py`. Add a new migration instead.
- **The editorial rules** in `PRODUCT.md`:
  - Criticism of the NPP and scrutiny of the government get identical treatment.
  - Red means only a confirmed Critical · L4 case, always with an icon and a text label.
  - Urgency and verification stay separate fields.
  - Counts are distinct items, never public support.
  - Original Twi or Pidgin wording stays beside any translation.
- **The trend method** in `architecture.md` and `decisions.md`:
  - 60-minute windows with the end of each window excluded.
  - Copies grouped under their origin, and WhatsApp tips never counted.
  - Topics ranked by increase in count, with a 5-mention minimum.
  - Capped or failed polls mark a platform partial.
- **Design-token names** in `src/desk/static/desk/tokens.css`. They match the Figma variables' code syntax.
- **Role checks:** editor-only actions (approve, escalate, close, reopen, send back) are refused on the server for users without `desk.decide_case`. Never rely on the template alone.
- **Demo sign-in:** the passwordless sample sign-in (`sample_role`) may only open the fictional people in `tests/fixtures/sample_shift/shift.json` who have no usable password, and sample mode must never run on a live deployment (`desk_site/safety.py`). Never widen either.
- **No secrets in the repository:** never write passwords, tokens, API keys or chat IDs into docs, code, fixtures or commit messages. Put them in `.env` (ignored by git) or the server environment. Hand temporary passwords over privately.
- **Local databases:** never delete or reset `data/desk.sqlite3` or `data/live.sqlite3` unless the user asks. `replay_sample --wipe` discards demo decisions.

## How to work here

- **Stack:** Django templates plus three small JavaScript files (`refresh.js`, `keys.js`, `enhance.js`). Every page must still work without JavaScript. Do not add a front-end framework or build step without the user's agreement.
- **Shared names:**
  - Reuse the component classes in `desk.css` and the partials in `templates/desk/partials/`.
  - Every Figma component description names the partial it maps to.
- **Times:** show all times in GMT, with tabular numerals for counts and times.
- **Sources:**
  - Read only public feeds and APIs that the site's `robots.txt` allows.
  - Never disguise the user agent, scrape around a missing feed, or bypass bot protection.
  - Ask the user before adding any source that needs credentials (X, Meta, TikTok, Telegram).
  - Keep credentials in environment variables only.
- **Tests:** new behaviour gets a test that runs offline against saved fixtures. Tests must not need the network.
- **Docs:** user-visible changes get an entry in `changelog.md`. Design decisions get an entry in `decisions.md`, in the existing format.
- **Sample content:** all sample names, outlets, accounts, notices and claims are fictional; keep them that way.
- **When unsure:** ask the user rather than guess.
