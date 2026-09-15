# Dual-AI Review Pipeline (API-based, headless)

**If you just want Claude and ChatGPT reviewing each other's work using
subscriptions you already pay for, use the setup at the repo root
(`../README.md`, `../CLAUDE.md`, `../AGENTS.md` -- Claude Code + Codex CLI
sharing a folder) instead of this.** That's simpler, has no per-token
billing, and is what most people want.

This folder is for a different, narrower case: a **fully unattended,
headless** review loop -- e.g. running in CI, on a server with no
interactive terminal, or as a one-shot scripted check -- where you're
fine paying per-token API rates on both accounts in exchange for not
needing an interactive Claude Code / Codex CLI session at all.

Claude drafts an answer, ChatGPT verifies it and returns a PASS/FAIL
verdict with concrete issues, and Claude revises until ChatGPT passes it
or the round limit is hit. Pure Python standard library -- nothing to
`pip install`.

## Setup

1. Get API keys:
   - Anthropic: https://console.anthropic.com/settings/keys
   - OpenAI: https://platform.openai.com/api-keys
2. Copy `.env.example` to `.env` and fill in both keys:
   ```
   cp dual-ai-review/.env.example dual-ai-review/.env
   ```
3. Requires Python 3.8+. No other dependencies (standard library only).

## Usage

```bash
python3 dual-ai-review/orchestrator.py --task "피보나치 수열을 구하는 파이썬 함수를 작성해줘"
```

Or with a longer task from a file (e.g. a spec, a code diff to review, a
design doc):

```bash
python3 dual-ai-review/orchestrator.py --task-file my_task.txt --max-rounds 4
```

Options:
- `--max-rounds N` -- max review/revision cycles (default 3)
- `--claude-model` / `--openai-model` -- override models (or set
  `CLAUDE_MODEL` / `OPENAI_MODEL` in `.env`)
- `--output path.md` -- where to write the full transcript (default:
  `dual-ai-review/logs/<timestamp>.md`)

The script exits with code `0` if ChatGPT's final verdict is PASS, and `2`
otherwise, so you can use it in scripts/CI (`&& echo ok || echo needs work`).

## How it works

1. Claude gets the task and produces a full answer.
2. ChatGPT is prompted as a strict, independent verifier and must respond
   with structured JSON: `{"verdict": "PASS"|"FAIL", "issues": [...],
   "suggestions": [...], "summary": "..."}`.
3. If FAIL, Claude gets the task + its previous answer + ChatGPT's issues
   and suggestions, and produces a revision.
4. Repeat until PASS or `--max-rounds` is reached.
5. Every round is written to a markdown log under `logs/`.

## Notes

- Each run costs API credits on both accounts -- roughly `rounds x 2` API
  calls.
- The reviewer prompt asks for JSON only; if a model still wraps it in
  prose, the script falls back to extracting the first `{...}` block. If
  that also fails, the verdict is marked `UNKNOWN` so you don't silently
  treat a broken review as a pass.
