# Design prompt · NPP Ghana Social Listening Desk

Design a high-fidelity, clickable prototype for the **NPP Ghana Social Listening Desk**, a private workspace for researchers, social media officers and duty editors. At the start of a shift, an editor should be able to answer three questions in ten seconds. What is gaining attention in Ghana? Which claim needs a decision now? How fresh is the evidence? Give criticism of the NPP and scrutiny of the government equal treatment.

## Visual direction

Use the attached elephant poster as the visual reference. Translate its bold typography, blue field and angled white frame into a restrained newsroom identity. Use a deep-blue navigation rail, a white reading surface and one angled detail at the edge of the masthead. Keep tables, charts and text aligned on a straight grid. A small elephant silhouette can identify the desk in the masthead. Keep the poster slogans and oversized illustration out of the working screens.

| Color | Use |
|---|---|
| Royal blue `#014EA6` | Primary actions, links and the current-period trend line |
| Deep blue `#00387F` | Navigation and masthead, with white text |
| Sky blue `#7FBCFF` | Selected items on dark blue and chart fills |
| Signal red `#E60000` | Confirmed critical priority, paired with an icon and text |
| White `#FFFFFF` | Tables, evidence panels and reading surfaces |

Add neutral ink and light grey for body text, dividers and the page background. Use a bold grotesk heading face and a legible sans serif for reading. Use tabular numerals for counts and times. Keep red independent of the party being discussed. Give keyboard focus, selected rows and severity badges distinct, accessible treatments.

## Screens and interactions

1. **Desk overview.** At 1440 px, give the left two-thirds to *Trending Now* and the right third to *Needs Attention*. Lead with the ranked topics and open decisions. Each trend row shows topic, distinct mentions this hour and last hour, numeric change, a small chart, observed sources and last update in GMT. Each issue shows the exact claim, urgency reason, verification status, owner and deadline. Give an urgent low-volume case a visible place in the queue.
2. **Trend detail.** Clicking a topic opens the two-hour timeline, the comparison windows, platform breakdown and source-linked examples. Let the analyst filter by platform, topic and subject. Distinguish a quiet source from a disconnected one. Use “New this hour” when the previous count was zero. Provide an “Open for review” action on an individual item.
3. **Issue review.** Put the exact claim and next action at the top. Show the original item, primary evidence, any contrary evidence and a timestamped decision history. Keep English, Twi or Ghanaian Pidgin excerpts beside any reviewed translation. An analyst can take ownership and submit a finding. An editor can approve, escalate, close or reopen the case. Show priority and verification as separate fields.
4. **Source coverage.** List news/RSS, X, Facebook, Instagram, Threads, TikTok, YouTube and voluntary WhatsApp tips. Show collection method, scope, last successful check and delay. Clearly distinguish a connected feed, an analyst-submitted link and a source awaiting access. A forwarded tip provides no estimate of audience reach.

## Prototype scenario and handoff

Use a clearly labelled **Sample shift**. A fictional electricity-tariff story rises from 4 to 12 distinct mentions across monitored news and X. Separately, a single post claims the tariff begins today. Let the reviewer open the original item, assign the claim, compare it with a sample dated notice, and submit a finding for editor review. Show the saved owner and decision on returning to the queue. Include a delayed-source state and an empty queue state. Keep all example allegations and attributions fictional.

Deliver desktop and 390 px mobile layouts, a clickable review flow, and reusable components for trend rows, case cards, source status, evidence entries and filters. On mobile, place urgent cases above trends and preserve one-tap access to source evidence. Annotate which actions require editor permission. Keep the components practical to implement with Django templates and lightweight JavaScript.
