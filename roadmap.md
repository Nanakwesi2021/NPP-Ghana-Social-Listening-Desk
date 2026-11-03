# Roadmap

Build the research desk’s core workflow first. A reviewer should be able to spot a topic gaining attention across sources, see the evidence, and assign a critical issue for follow-up. All milestones are proposed. The blueprint supplies a one-pass Python example.

## Now

**Goal.** Deliver one working desk dashboard, from offline source replay through incident review.

- [x] Prepare two clearly labelled sample streams, one news feed and one set of public social posts (`tests/fixtures/sample_shift/news.json` and `social.json`). Include timestamps, source links, repeated IDs, an electricity-tariff story discussed on both sources and unrelated headlines. Seed four distinct tariff items in the prior hour and twelve in the current hour. Add one post with 13 copies and two syndicated news copies, all excluded from those totals.
- [x] Store distinct items in SQLite. Group related items by topic. Rank rising topics by change in unique mentions between two equal time windows. Show both counts, contributing sources and the comparison period. Mark a first appearance as new.
- [x] Build a desk overview with ranked trends, a critical-issue queue and source status visible together. Include:
  - readable priority labels and GMT timestamps
  - filters for source and subject on the overview, and for platform, topic and subject on a trend
  - sample cases for criticism of the NPP and scrutiny of the government, judged against the same urgency criteria

  Selecting a trend opens the underlying headlines or excerpts and their original links.
- [x] Let a reviewer open an issue, see why it was flagged, take ownership, attach evidence, record a finding and have an editor approve, escalate, close or reopen it. Persist each decision with its author and timestamp.

**Definition of done.** In a credential-free demo, the reviewer:

1. Sees the electricity-tariff topic rise from four to twelve distinct items (+8) on News + X, with X marked partial.
2. Traces it to a news item and a social post.
3. Takes ownership of the post's claim and submits a finding that the editor approves.

Reloading the dashboard preserves the owner and decision. Replaying the same inputs after a restart leaves item counts, trend rankings and queue entries unchanged.

**Status.** Met on 3 November 2026 by the Sample shift desk in `src/`. `src/desk/tests/test_sample_shift.py` checks each condition. The test run is described in the [README](README.md#run-the-desk-locally-sample-shift).

## Next

**Goal.** Give the desk a measured near-real-time view of approved live sources.

| Pilot task | Evidence required |
| --- | --- |
| Connect independent sources | Check Citi Newsroom, Joy Online, Daily Graphic and Peace FM Online feeds individually. Enable X recent search when credentials and access have been verified. Record whether each input is live, simulated, awaiting access or unavailable. |
| Measure freshness and coverage | Record the last successful check, most recent item and expected polling interval per source. Show delays and rate limits on the dashboard. Test a healthy but quiet feed alongside a failed feed. |
| Validate critical-issue handling | Exercise L1 routine coverage, L2 emerging activity, L3 claims needing urgent verification and L4 reviewer-confirmed crisis escalation. Preserve evidence, reviewer decisions and ownership. Calibrate the blueprint’s 200 mentions per hour L2 example against observed coverage. |
| Pilot desk notifications | Enable Telegram only for a designated internal test chat. Confirm that a notification carries the correct priority and evidence link, duplicate input creates no second alert, and an unsuccessful delivery is visible to the operator. Trial the blueprint’s 30-minute L3 research target. |

**Progress (3 November 2026).** The news-feed collector, failure isolation, per-outlet freshness and live trend recalculation are built and tested; see [Run against live feeds](README.md#run-against-live-feeds). Citi Newsroom (via its WordPress posts API), Joy Online and Daily Graphic collect live. Peace FM Online has no public feed and needs one from the outlet. X, Telegram and the staffed-shift measurements have not started.

Before the shift, agree a freshness target for each source. For example, a feed that permits five-minute polling could have a ten-minute publication-to-screen target. Measure that end-to-end delay against the agreed target and mark late or unmeasurable sources explicitly.

**Definition of done.** Run at least one news feed and one authorized social source together for a staffed shift. At least 95% of new items must appear on the dashboard within one minute of collection. Report publication-to-collection delay separately for sources with trustworthy timestamps. Removing access to one source must flag its coverage gap while other sources continue updating. A reviewer can follow one pilot issue from first detection through a documented decision. Record the number of observations beside each percentage. A shift with no items cannot validate latency. These are acceptance targets for the pilot.

## Later

- **Extend platform coverage.** Prioritize public Facebook pages, Instagram, Threads, TikTok, YouTube and radio or television transcripts alongside RSS and X. For each candidate, document available access, covered content, refresh limits and cost. Enable an adapter only after a sample and a failed-connection test pass. Demonstrate one issue independently observed on two live social platforms before marking it as trending across social platforms. Assess voluntary WhatsApp submissions separately with consent, retention and access rules.
- **Use the dashboard for daily handovers.** Trial a 05:45 GMT overnight brief, 09:00–14:00 and 16:00–20:00 monitoring windows, and a 21:30 handover. The brief should identify rising topics, open critical issues, source gaps and the next reviewer.
- **Improve local language coverage.** Have fluent reviewers test Twi and Ghanaian Pidgin examples. Add validated patterns and track missed matches and ambiguous terms.

## Not planned

Automatic publication of rebuttals and access to private groups without authorization fall outside this build.

## Roadmap rules

Finish the offline desk workflow before starting the live pilot. Give each new milestone an observable acceptance check. Record significant design changes in [technical decisions](decisions.md), move verified changes to the [changelog](changelog.md), and update the roadmap when priorities change.
