# AI_OFFICE — Claude Code + Codex CLI dual-assistant workspace

Two assistants working on the same folder, each on the subscription you
already pay for:
- **Claude Code** — your Claude Pro/Max plan
- **Codex CLI** — your ChatGPT Plus/Pro plan (Codex is included; no
  separate API billing unless you choose to add API credits)

No API keys required for either side, no per-token billing.

## Setup

### Step 1 — Claude Code
Already installed if you're reading this through it. Otherwise:
```bash
npm install -g @anthropic-ai/claude-code
claude login
```

### Step 2 — Codex CLI, logged in with ChatGPT (not an API key)
```bash
npm install -g @openai/codex
codex
```
On first run it asks you to sign in -- choose **"Sign in with ChatGPT"**,
not "API key". This makes Codex use your ChatGPT Plus/Pro plan's included
usage instead of metered billing.

### Step 3 — Both point at this same folder
Clone this repo and `cd` into it before starting either tool:
```bash
git clone https://github.com/jckim5797-jc/260915.git
cd 260915
```
Then, in one terminal:
```bash
claude
```
and in a second terminal, in the same folder:
```bash
codex
```
Both tools read this folder's contents and automatically pick up their
role instructions from `CLAUDE.md` and `AGENTS.md` respectively (already
set up in this repo).

### Step 4 & 5 — Roles (already configured)
- `CLAUDE.md` — tells Claude Code it's the drafting/planning assistant and
  where to save drafts, how to ask Codex for review, and how to fold the
  review back in.
- `AGENTS.md` — tells Codex CLI it's the independent reviewer: what to
  check for, and where to write its findings.

Edit either file to change how strict the review should be, what
domain/perspective to check from (finance, security, legal, etc.), or add
project-specific context.

### Step 6 — Shared folders
```
01_INBOX/    raw material you drop in (notes, data, links)
02_WORKING/  Claude's scratch space
03_DRAFTS/   Claude's finished drafts, ready for review
04_REVIEW/   Codex's review output
05_FINAL/    Claude's revised version after applying valid feedback
```

### Step 7 — Let Claude call Codex automatically
Inside a Claude Code session, just ask normally, e.g.:
> "이 전략안 Codex한테 재무/논리 관점으로 검토시키고, 지적사항 반영해서 최종본 만들어줘"

Claude Code will (per `CLAUDE.md`) save a draft to `03_DRAFTS/`, run
`codex exec "..."` via its shell tool to get Codex's review written to
`04_REVIEW/`, read that back, revise, and save the final version to
`05_FINAL/`. You can also run `codex exec "..."` yourself directly any
time you want a one-off review without going through Claude.

## Flow at a glance

```
you
 -> Claude Code drafts           -> 03_DRAFTS/x.md
 -> Claude runs `codex exec ...` -> 04_REVIEW/x_review.md
 -> Claude reads the review, revises
 -> 05_FINAL/x.md
```

No API keys, no browser scraping -- just two CLIs reading/writing the same
folder, each billed to the subscription you're already paying for.

## A note on limits

"Included in your plan" still has a ceiling -- both Claude and ChatGPT
plans cap included usage over a rolling window. Heavy back-and-forth
review loops can hit that cap; if so, either wait for it to reset or (only
if you want to) add pay-as-you-go credits on the Codex side. That's a
separate, opt-in choice, not something this setup does automatically.
