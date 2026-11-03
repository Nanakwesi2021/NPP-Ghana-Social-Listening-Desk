# Figma prototype · status

**File:** [NPP Ghana Social Listening Desk — Prototype](https://www.figma.com/design/V3AeKWDIKpfXyd5ET413US)
**Status:** complete as of 2026-11-03. Node IDs and component property keys are in `design/figma-ledger.json`.

## Pages

| Page | Contents |
|---|---|
| Design system | Variables, text and effect styles, 44 icons and the elephant mark. Component boards: Atoms, Controls, Shell, Patterns (including the compact mobile rows, the platform breakdown row and the annotation note). |
| Desktop · 1440 | Flow guide. Screens 01, 02, 03a, 03b, 03c and 01b, each with numbered notes above it. Below them: 04 Source coverage, the States board and the Build handoff board. |
| Mobile · 390 | Flow guide. M1 Overview (plus a full-length review copy), M2 Issue review (Original tab), M3 Issue review (Evidence tab), M4 Source coverage. |

## Clickable flows

- **Sample shift · desktop:** starts at 01. The tariff row opens 02. “Open for review” on @AccraVoices opens 03a. Take ownership leads to 03b, Submit finding to 03c, and Approve finding to 01b. The rail goes to Overview, Trends, Issues and Sources; the X-delayed banner and brief cell 3 open 04.
- **Sample shift · mobile:** starts at M1. ISS-0412 opens M2. The Evidence and Original tabs switch between M2 and M3. The back link returns to M1. The X notice and the Sources tab open M4.
- Hover variants are wired on trend rows, case items, buttons and rail items.

## Plan constraints to remember

- **Pages:** the file is limited to 3.
- **MCP calls:** the Figma tool-call allowance is limited and can run out mid-build.
- **Annotations:** Dev Mode annotations are blocked on a View seat, so notes are canvas frames instead.
- **Variable-bound paints:** use the variable's resolved colour as the base, or nested instance overrides render black.
- **Focus rings:** they need clip content to render.

## Possible next steps

- Add the editor's view of an escalation to L4 and the reopen path.
- Export the Figma variables to `static/desk/tokens.css` once the Django project exists.
