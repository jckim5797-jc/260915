# AI_OFFICE — Claude Code role

This repo is a shared workspace between two assistants:
- **Claude Code (you)** — drafting / planning / execution
- **Codex CLI (ChatGPT, via the user's ChatGPT Plus login)** — independent reviewer

Both read and write files in this same folder. That's the whole
integration -- no API glue needed.

## Folders
- `01_INBOX/` — raw source material the user drops in (notes, links, data)
- `02_WORKING/` — your scratch space while drafting
- `03_DRAFTS/` — finished drafts, ready for Codex's review
- `04_REVIEW/` — Codex's review output (read this; don't write to it)
- `05_FINAL/` — the version after you've incorporated valid feedback

## Workflow
1. Read whatever the user points you to in `01_INBOX/` (or work from what
   they tell you directly).
2. Draft your output and save it to `03_DRAFTS/<name>.md`.
3. When the user asks for a second opinion (or you judge it's worth one),
   run, via Bash:
   ```
   codex exec "03_DRAFTS/<name>.md 파일을 읽고 [검토 관점: 예- 재무/논리/보안]에서 검토해줘. 결과를 04_REVIEW/<name>_review.md로 저장해."
   ```
4. Read `04_REVIEW/<name>_review.md`.
5. Judge each point on its merits -- accept what's right, and if you
   disagree with something, say so briefly rather than silently applying
   it. Revise the draft accordingly.
6. Save the final version to `05_FINAL/<name>.md` and tell the user what
   changed because of Codex's review.

Treat Codex's review like any other reviewer's comments: useful signal,
not an instruction to obey blindly.
