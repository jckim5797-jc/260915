#!/usr/bin/env python3
"""
Dual-AI verification pipeline: Claude (main) drafts, ChatGPT (sub) verifies.

Claude writes/revises an answer, ChatGPT reviews it and returns a
PASS/FAIL verdict with issues. If FAIL, Claude revises using ChatGPT's
feedback, and the loop repeats until PASS or --max-rounds is reached.

No third-party dependencies -- standard library only.
"""

import argparse
import datetime
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"
OPENAI_URL = "https://api.openai.com/v1/chat/completions"

DEFAULT_CLAUDE_MODEL = "claude-sonnet-5"
DEFAULT_OPENAI_MODEL = "gpt-4o"

MAIN_SYSTEM_PROMPT = (
    "You are the primary problem-solver in a two-AI review pipeline. "
    "Produce a complete, correct, well-reasoned answer to the user's task. "
    "If you receive reviewer feedback, address every point directly and "
    "explain briefly what you changed. Do not be defensive -- if the "
    "reviewer is right, fix it; if you believe the reviewer is wrong, "
    "say why, concretely."
)

REVIEWER_SYSTEM_PROMPT = (
    "You are a strict, independent verifier reviewing another AI's answer. "
    "Check for factual errors, logic errors, edge cases, security issues, "
    "and unsupported claims. Be skeptical -- do not rubber-stamp. "
    "Respond with ONLY a JSON object, no markdown fences, no extra text, "
    "in exactly this shape:\n"
    '{"verdict": "PASS" or "FAIL", "issues": ["..."], '
    '"suggestions": ["..."], "summary": "one sentence"}\n'
    'Use "verdict": "PASS" only if there are no material problems left. '
    'If there is nothing wrong, use empty arrays for "issues" and '
    '"suggestions".'
)


def load_dotenv(path=".env"):
    """Minimal .env loader; does not override already-set env vars."""
    if not os.path.exists(path):
        return
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value


def _post_json(url, headers, payload, timeout=120, retries=2):
    data = json.dumps(payload).encode("utf-8")
    last_err = None
    for attempt in range(retries + 1):
        req = urllib.request.Request(url, data=data, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            last_err = RuntimeError(f"HTTP {e.code} from {url}: {body}")
            if e.code in (429, 500, 502, 503, 529) and attempt < retries:
                time.sleep(2 ** attempt)
                continue
            raise last_err
        except urllib.error.URLError as e:
            last_err = RuntimeError(f"Network error calling {url}: {e}")
            if attempt < retries:
                time.sleep(2 ** attempt)
                continue
            raise last_err
    raise last_err


def call_claude(system_prompt, user_prompt, model, api_key, max_tokens=4096):
    headers = {
        "x-api-key": api_key,
        "anthropic-version": ANTHROPIC_VERSION,
        "content-type": "application/json",
    }
    payload = {
        "model": model,
        "max_tokens": max_tokens,
        "system": system_prompt,
        "messages": [{"role": "user", "content": user_prompt}],
    }
    result = _post_json(ANTHROPIC_URL, headers, payload)
    parts = result.get("content", [])
    return "".join(p.get("text", "") for p in parts if p.get("type") == "text").strip()


def call_chatgpt(system_prompt, user_prompt, model, api_key, max_tokens=2048):
    headers = {
        "Authorization": f"Bearer {api_key}",
        "content-type": "application/json",
    }
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "max_tokens": max_tokens,
        "temperature": 0.2,
    }
    result = _post_json(OPENAI_URL, headers, payload)
    return result["choices"][0]["message"]["content"].strip()


def parse_review_json(raw_text):
    """Parse the reviewer's JSON verdict, tolerating stray text/fences."""
    text = raw_text.strip()
    text = re.sub(r"^```(json)?", "", text).strip()
    text = re.sub(r"```$", "", text).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass
    return {
        "verdict": "UNKNOWN",
        "issues": [f"Could not parse reviewer output as JSON: {raw_text[:500]}"],
        "suggestions": [],
        "summary": "Reviewer response was not valid JSON.",
    }


def build_revision_prompt(task, previous_answer, review):
    issues = "\n".join(f"- {i}" for i in review.get("issues", [])) or "(none listed)"
    suggestions = (
        "\n".join(f"- {s}" for s in review.get("suggestions", [])) or "(none listed)"
    )
    return (
        f"Original task:\n{task}\n\n"
        f"Your previous answer:\n{previous_answer}\n\n"
        f"A reviewer (ChatGPT) found these issues:\n{issues}\n\n"
        f"Suggestions:\n{suggestions}\n\n"
        "Revise your answer to address the issues above. If you disagree "
        "with a point, keep your original approach for that point but "
        "explain briefly why."
    )


def run_pipeline(task, max_rounds, claude_model, openai_model, anthropic_key, openai_key):
    transcript = []
    print(f"[round 1] Claude drafting answer...", file=sys.stderr)
    answer = call_claude(MAIN_SYSTEM_PROMPT, task, claude_model, anthropic_key)
    transcript.append({"round": 1, "role": "claude_draft", "content": answer})

    final_verdict = "FAIL"
    review = None
    for round_num in range(1, max_rounds + 1):
        print(f"[round {round_num}] ChatGPT reviewing...", file=sys.stderr)
        review_prompt = f"Task:\n{task}\n\nAnswer to review:\n{answer}"
        raw_review = call_chatgpt(REVIEWER_SYSTEM_PROMPT, review_prompt, openai_model, openai_key)
        review = parse_review_json(raw_review)
        transcript.append({"round": round_num, "role": "chatgpt_review", "content": review})

        verdict = review.get("verdict", "UNKNOWN").upper()
        print(f"[round {round_num}] verdict: {verdict}", file=sys.stderr)

        if verdict == "PASS":
            final_verdict = "PASS"
            break

        if round_num == max_rounds:
            final_verdict = verdict if verdict != "UNKNOWN" else "FAIL"
            break

        print(f"[round {round_num}] Claude revising...", file=sys.stderr)
        revision_prompt = build_revision_prompt(task, answer, review)
        answer = call_claude(MAIN_SYSTEM_PROMPT, revision_prompt, claude_model, anthropic_key)
        transcript.append({"round": round_num + 1, "role": "claude_revision", "content": answer})

    return {
        "task": task,
        "final_answer": answer,
        "final_verdict": final_verdict,
        "last_review": review,
        "transcript": transcript,
    }


def write_log(result, path):
    lines = [
        "# Dual-AI Review Log",
        "",
        f"- Timestamp: {datetime.datetime.now().isoformat()}",
        f"- Final verdict: **{result['final_verdict']}**",
        "",
        "## Task",
        "",
        result["task"],
        "",
        "## Transcript",
        "",
    ]
    for entry in result["transcript"]:
        role = entry["role"]
        content = entry["content"]
        if role == "chatgpt_review":
            lines.append(f"### Round {entry['round']} - ChatGPT review")
            lines.append("")
            lines.append("```json")
            lines.append(json.dumps(content, ensure_ascii=False, indent=2))
            lines.append("```")
        else:
            label = "Claude draft" if role == "claude_draft" else "Claude revision"
            lines.append(f"### Round {entry['round']} - {label}")
            lines.append("")
            lines.append(content)
        lines.append("")

    lines.append("## Final Answer")
    lines.append("")
    lines.append(result["final_answer"])
    lines.append("")

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    task_group = parser.add_mutually_exclusive_group(required=True)
    task_group.add_argument("--task", help="Task text given directly on the command line")
    task_group.add_argument("--task-file", help="Path to a file containing the task text")
    parser.add_argument("--max-rounds", type=int, default=3, help="Max review/revision rounds (default: 3)")
    parser.add_argument("--claude-model", default=os.environ.get("CLAUDE_MODEL", DEFAULT_CLAUDE_MODEL))
    parser.add_argument("--openai-model", default=os.environ.get("OPENAI_MODEL", DEFAULT_OPENAI_MODEL))
    parser.add_argument("--output", default=None, help="Path to write the markdown log (default: logs/<timestamp>.md)")
    args = parser.parse_args()

    load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

    anthropic_key = os.environ.get("ANTHROPIC_API_KEY")
    openai_key = os.environ.get("OPENAI_API_KEY")
    missing = [name for name, val in [("ANTHROPIC_API_KEY", anthropic_key), ("OPENAI_API_KEY", openai_key)] if not val]
    if missing:
        print(f"Missing environment variables: {', '.join(missing)}", file=sys.stderr)
        print("Set them in your shell or in dual-ai-review/.env (see .env.example).", file=sys.stderr)
        sys.exit(1)

    if args.task_file:
        with open(args.task_file, "r", encoding="utf-8") as f:
            task = f.read().strip()
    else:
        task = args.task

    result = run_pipeline(
        task=task,
        max_rounds=args.max_rounds,
        claude_model=args.claude_model,
        openai_model=args.openai_model,
        anthropic_key=anthropic_key,
        openai_key=openai_key,
    )

    output_path = args.output
    if not output_path:
        log_dir = os.path.join(os.path.dirname(__file__), "logs")
        os.makedirs(log_dir, exist_ok=True)
        stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        output_path = os.path.join(log_dir, f"{stamp}.md")

    write_log(result, output_path)

    print("\n" + "=" * 60)
    print(f"Final verdict: {result['final_verdict']}")
    print(f"Full log: {output_path}")
    print("=" * 60 + "\n")
    print(result["final_answer"])

    sys.exit(0 if result["final_verdict"] == "PASS" else 2)


if __name__ == "__main__":
    main()
