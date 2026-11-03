# Architecture

## System overview

The NPP research and social media teams in Ghana share a private desk for two questions. **What topics are gaining attention across the sources we cover?** **What claim or event needs someone’s attention now?** The trend board answers the first from time-stamped observations. The critical issue queue answers the second from evidence, urgency and an assigned reviewer. A credible safety incident can enter the queue on its first report. A much-discussed football result can appear on the board without opening a case.

The supplied `warroom_monitor.py` checks four news feeds and optionally searches X and sends Telegram messages. It exits after one pass and keeps seen IDs in memory. The dashboard, persistent stores, trend calculations and team workflows below are proposed.

## Components

| Component | Proposed location | Responsibility |
| --- | --- | --- |
| Private dashboard | `src/` web views | Show ranked topics, source coverage and an assigned issue queue. Topic detail shows its time series, platform breakdown, sample links and the reason it rose. Case detail shows the claim, evidence, owner, deadline, status and decision history. |
| Application layer | `src/` | Serve dashboard reads and authenticated case actions. Apply role checks on the server for each read, edit, escalation and export. Record who changed what and when. |
| Collection worker | `warroom_monitor.py` and `src/` | Run one pass from a scheduler or terminal, with a cursor and status per source. Record errors, quotas, truncation and gaps. A failed source leaves the others running. |
| Analysis | `src/` | Normalize items, resolve duplicates, group related stories, tag issues and subjects, and compute trend windows. Keep original Twi, English or Ghanaian Pidgin text alongside any reviewed translation. |
| Data access | `src/` with `data/` for local SQLite | Persist sources and poll runs, items, topic memberships, trend windows, cases, evidence, review events and pending deliveries. The worker and web application use the same data layer. |
| Internal delivery | `src/` | When enabled, send authorized notifications linking back to the case. Record acknowledgement, retryable failure or uncertain delivery. |
| Verification | `tests/fixtures/` | Replay two periods of timestamped observations, cross-posts, a disconnected source, a breaking report and a disputed claim. |

## From observation to trend

1. Record platform, outlet or channel, external ID or canonical URL, source link, excerpt, published time if known, and collection time. Deduplicate repeated polls with a unique key on source and external ID or canonical URL. Link syndicated copies to a common origin where identifiable. Retain each platform appearance as evidence of distribution.
2. Tag the *subject* separately from the *issue*. A report about an electricity tariff may concern the governing administration, the NPP, both, or another institution. Multiple subjects and an unassigned subject are valid. Keep broader Ghanaian events eligible for the trend board even when no party name matches.
3. As a pilot rule, recalculate each minute. At 10:37 GMT, for example, compare 09:37–10:37 with 08:37–09:37, excluding the endpoint of each window to avoid double counting. Use the same sources with usable coverage in both windows. Count distinct observed items per topic in each window, grouping known syndicated copies under one origin. Use publication time where available and identify collection-time fallbacks. Persist both window bounds, counts, source set and calculation time.
4. As a proposed starting point, rank rising topics with a positive increase and at least five distinct observations in the current window by the **increase in count**. Break ties using the number of represented platforms, then current count. Show the raw counts and label a zero baseline as **new in this window**. Display a cross-platform label only when evidence links exist on at least two platforms. Keep single-platform trends visible with their actual coverage.
5. Display the latest completed poll and window on the board in Ghana time. Classify each configured source as current, delayed, unavailable or disabled. As an initial rule, mark a source delayed after two missed poll intervals. Mark a window partial when a requested source was excluded or a provider capped the sample. Distinguish observed silence from missing coverage.

For example, a topic rising from 4 to 12 distinct reports has an increase of 8. If all 12 appeared on news websites, its platform coverage remains news only. If X access failed during that period, the card discloses the gap. It cannot establish how widely the topic trended on X.

## Critical issues and fact-checking

A desk member can open a case from one source item or a trend. The case stores the exact claim or event, affected subject, priority rationale, source links and next review time. The blueprint’s L1–L4 scale maps to routine monitoring, emerging issue, urgent review and confirmed crisis. An analyst proposes an escalation and an editor confirms L4. Volume alone establishes neither truth nor urgency.

The workflow is **new → assigned → in review → reviewed → closed**. An analyst gathers primary records and corroboration, records contrary evidence and recommends a finding. An editor records the disposition, including “insufficient evidence” when appropriate. New evidence can reopen a case while preserving the prior finding. A social desk reader can consult approved briefs and flag items for research. Administrators manage membership, credentials and source settings. Require sign-in for all desk roles and keep provider secrets on the server.

## Source rollout and operation

- **First slice.** Use fixtures to exercise the full desk workflow. For the first live pilot, verify the Citi Newsroom, Joy Online, Daily Graphic and Peace FM Online feeds individually. Multiple outlets increase news coverage.
- **First social comparison.** Add X recent search once access and quotas are verified. Record query scope, language filters and capped pages. Label a topic observed in both news and X as “news + X.” Reserve “across social platforms” for evidence observed directly on two or more social networks.
- **Further coverage.** Evaluate public Meta, TikTok, YouTube and radio transcripts separately. Show planned connectors as unconnected until a fetch succeeds. Voluntarily submitted WhatsApp media would require a separate intake and retention decision.
- **Delivery.** Introduce Telegram only after case routing is tested. Save each alert intent with its case event in one transaction. A provider timeout after acceptance is ambiguous and needs reconciliation. A case remains reviewable during an outage.

Before a shared pilot, confirm the identity provider, access owners, approved live sources, retention period, operator coverage and hosting. Calibrate trend windows, stale-source thresholds and crisis response targets against observed coverage. See the [decision records](decisions.md) and [roadmap](roadmap.md).
