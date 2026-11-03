# Product context · Social Listening Desk

Inferred from `UI-UX-Design-Prompt.md`, `README.md`, `architecture.md` and `decisions.md` on 2026-11-03. Assumptions are marked.

## Who uses it

| Role | What they do on the desk |
|---|---|
| Duty editor | Opens the shift, decides which issue needs a decision, approves, escalates, closes or reopens cases. Confirms L4 (critical). |
| Analyst / researcher | Takes ownership of a claim, gathers primary evidence, records a reviewed translation and submits a finding. |
| Social media officer | Reads trends and approved briefs, flags items for research. |

## The ten-second test

At the start of a shift the editor answers three questions without scrolling:

1. What is gaining attention in Ghana?
2. Which issue needs a decision now?
3. How fresh is the evidence?

## Editorial rules the interface must hold

- Criticism of the NPP and scrutiny of the government get identical visual treatment. Party and subject names are always neutral ink.
- Colour signals operational state only. Signal red means a **confirmed critical** case and always appears with an icon and a text label.
- Urgency and verification are separate fields. A case can be Urgent and Unverified.
- Counts are distinct observations from monitored sources. They never stand in for public support.
- Every count carries its window and its source set. A delayed source is disclosed where the count is shown.
- Original English, Twi/Akan or Ghanaian Pidgin wording stays beside any reviewed translation.

## Surface

Operate mode: a private, authenticated work tool. Scanability, consistency and honest data age outrank expression. Brand lives in the masthead (deep blue, one angled cut, a small elephant mark) and in Archivo headings.

## Build target

Django templates with lightweight JavaScript. Every component in the Figma file maps to a template partial; interactions are links, forms and small progressive enhancements (filters as query parameters, a one-minute partial refresh).

## Assumptions

- The reference poster was not available. The elephant mark and angled frame are drawn from the written brief and the sampled hex values.
- All names, outlets, accounts, notices and claims in the Sample shift are fictional.
