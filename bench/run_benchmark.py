"""
Backend/model benchmark harness for query/ask.py.

Runs the same eval questions against whichever generation backends are current
and reports mechanical/structural properties of each answer — the same things
that were being checked by eye in query/comparison_results.md, turned into a
repeatable script. See bench/README.md and the spec for the full rationale.

No changes to query/ask.py: this reuses its seams directly —
retrieve() -> build_prompt() -> generate_answer() / parse_cited_indices(). It
does NOT call ask.ask(), because that strips the CITED: line out of the answer
before returning and the structural checks need the raw model output.

Cost: a default run never calls Claude. --include-claude adds a Claude Sonnet 5
column, gated by a hard cumulative spend cap (bench/spend_tracker.json) computed
from the real usage field on every response. The cap can only track this tool's
own spend — Anthropic's API does not expose account credit balance. Check that
independently at platform.claude.com/settings/billing.

Run from the repo root:
    python3 -m bench.run_benchmark
    python3 -m bench.run_benchmark --include-claude
    python3 -m bench.run_benchmark --questions near-miss-1,cross-essay-1 -k 8
    python3 -m bench.run_benchmark --reset-spend
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

BENCH_DIR = Path(__file__).resolve().parent
REPO_ROOT = BENCH_DIR.parent
RESULTS_DIR = BENCH_DIR / "results"
QUESTIONS_FILE = BENCH_DIR / "eval_questions.json"
SPEND_FILE = BENCH_DIR / "spend_tracker.json"

# query/ask.py expects to be imported with query/ on sys.path (it does its own
# sys.path insert for ingest/ at import time).
sys.path.insert(0, str(REPO_ROOT / "query"))
import ask  # noqa: E402

# --- Cost / spend config -----------------------------------------------------

SPEND_CAP_USD = 0.50
CLAUDE_MODEL = "claude-sonnet-5"
CLAUDE_MAX_TOKENS = 2048
# Published rates, USD per 1M tokens: (input, output). Verified against the
# claude-api reference 2026-08-29.
CLAUDE_PRICING = {"claude-sonnet-5": (2.0, 10.0)}

# --- Backend matrix --------------------------------------------------------—-

DEFAULT_BACKENDS = [
    ("ollama", "llama3.1"),
    ("huggingface", "openai/gpt-oss-20b"),
    ("extractive", None),
]
EXTRACTIVE_TOP_N = 2  # how many retrieved excerpts extractive mode returns verbatim

# --- Report legend ---------------------------------------------------------—-
# Written once, reused verbatim in every generated report so the wording stays
# stable across runs. Do not regenerate this per run.

REPORT_LEGEND = """\
Each check looks at the shape of the answer, not whether it's true. The answer
is printed next to its verdicts so you can check them yourself.

- **latency_s** — how many seconds the model took to answer.

- **errored** — the backend was unavailable (rate limit, out of credits, model
  not served, timeout). The message is kept as-is. That's a useful result, not
  a failed test, so the other checks are skipped for that answer.

- **cited_line_present** — the answer ended with a `CITED:` line. Without it the
  app can't tell the answer from its source list.

- **prose_before_cited** — the model wrote at least one sentence before the
  `CITED:` line. A `CITED:` line on its own shows up as a blank answer in the app.

- **citation_format_valid** — the `CITED:` line could be read: either
  `CITED: none` or a list of numbers.

- **citations_in_range** — the numbers the model cited point at excerpts it was
  actually shown, not made-up ones.

- **citation_count** — how many different essays the answer drew from, out of
  how many different essays were in the excerpts it got. Citing 1 of 3 on a
  question that spans essays suggests a thinner answer than citing 3 of 3. The
  second number matters: retrieval often returns several excerpts from the same
  essay, so a low count can just mean there wasn't much to cite. This counts
  citations, it doesn't judge them.

- **looks_truncated** — the answer stopped mid-sentence with no `CITED:` line,
  usually because the model ran out of room. A cut-off answer loses its
  citation line too.

- **decline_correct** — only for questions the archive shouldn't be able to
  answer. True when the model said so and cited nothing, rather than inventing
  a connection. Marked n/a for questions that should get a real answer.

- **extractive** — not a model. It just returns the top excerpts as the answer,
  as a floor to compare against: did a model's answer stay close to what
  retrieval actually found, or did it go further? It has no `CITED:` line, so
  the citation and decline checks don't apply to it.

What this does not check: whether a model quietly twisted what an excerpt said
while still citing it. Catching that needs a second model to grade, or a person
reading closely. Put that reading in the Notes section at the end.
"""

# --- Spend tracker ---------------------------------------------------------—-


def load_spend():
    if SPEND_FILE.exists():
        with open(SPEND_FILE) as f:
            return json.load(f)
    return {"cap_usd": SPEND_CAP_USD, "total_usd": 0.0, "calls": []}


def persist_spend(state):
    """Atomic write so a crash mid-run never loses track of real spend."""
    tmp = SPEND_FILE.with_suffix(".json.tmp")
    with open(tmp, "w") as f:
        json.dump(state, f, indent=2)
    os.replace(tmp, SPEND_FILE)


def claude_cost(input_tokens, output_tokens, model):
    in_rate, out_rate = CLAUDE_PRICING[model]
    return (input_tokens * in_rate + output_tokens * out_rate) / 1_000_000


# --- Extractive backend ----------------------------------------------------—-


def extractive_answer(excerpts, top_n=EXTRACTIVE_TOP_N):
    blocks = []
    for e in excerpts[:top_n]:
        blocks.append(f'From "{e["title"]}" ({e["url"]}):\n{e["text"]}')
    return "\n\n".join(blocks)


# --- Claude backend (harness-owned, measured) -----------------------------—-


def generate_claude_measured(prompt, model, spend_state):
    """Returns (full_text, meta). meta records whether the call ran, was
    skipped for the cap, or errored — plus real token usage and cost when it
    ran. Persists spend immediately after a real call."""
    import anthropic

    client = anthropic.Anthropic()

    # Pre-call gate: exact input tokens via the free count_tokens endpoint,
    # assume worst-case output (the full max_tokens) so we never cross the cap.
    try:
        counted = client.messages.count_tokens(
            model=model, messages=[{"role": "user", "content": prompt}]
        )
        est_input = counted.input_tokens
    except Exception:
        est_input = len(prompt) // 4  # rough fallback if count_tokens is unavailable

    est_cost = claude_cost(est_input, CLAUDE_MAX_TOKENS, model)
    projected = spend_state["total_usd"] + est_cost
    if projected > spend_state["cap_usd"]:
        return None, {
            "ran": False,
            "skipped_reason": (
                f"spend cap: running total ${spend_state['total_usd']:.4f} + "
                f"estimated ${est_cost:.4f} (>{est_input} in tokens, "
                f"{CLAUDE_MAX_TOKENS} out worst-case) would exceed "
                f"${spend_state['cap_usd']:.2f}"
            ),
        }

    t0 = time.perf_counter()
    try:
        response = client.messages.create(
            model=model,
            max_tokens=CLAUDE_MAX_TOKENS,
            messages=[{"role": "user", "content": prompt}],
        )
    except Exception as e:
        return None, {
            "ran": False,
            "error": f"{type(e).__name__}: {e}",
        }
    latency = time.perf_counter() - t0

    if response.stop_reason == "refusal":
        return None, {"ran": True, "latency_s": latency, "error": "Claude declined (stop_reason=refusal)"}

    full_text = "".join(b.text for b in response.content if b.type == "text")

    usage = response.usage
    cost = claude_cost(usage.input_tokens, usage.output_tokens, model)
    spend_state["total_usd"] = round(spend_state["total_usd"] + cost, 6)
    spend_state["calls"].append(
        {
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "model": model,
            "input_tokens": usage.input_tokens,
            "output_tokens": usage.output_tokens,
            "cost_usd": round(cost, 6),
        }
    )
    persist_spend(spend_state)

    return full_text, {
        "ran": True,
        "latency_s": latency,
        "input_tokens": usage.input_tokens,
        "output_tokens": usage.output_tokens,
        "cost_usd": round(cost, 6),
    }


# --- Structural checks ---------------------------------------------------—--—-


def cited_raw_value(full_text):
    """The text right after 'CITED:' on its line, or None if there is no CITED
    line. Mirrors how ask.CITED_RE / parse_cited_indices see it."""
    match = ask.CITED_RE.search(full_text)
    if not match:
        return None
    return match.group(1).strip().splitlines()[0].strip() if match.group(1).strip() else ""


def run_checks(full_text, excerpts, expects_decline, is_extractive):
    k = len(excerpts)
    answer_text = full_text.partition("CITED:")[0].strip()

    if is_extractive:
        return {
            "answer_text": full_text.strip(),
            "cited_line_present": None,
            "prose_before_cited": None,
            "citation_format_valid": None,
            "citations_in_range": None,
            "citation_count": None,
            "distinct_essays_available": len({(e["title"], e["url"]) for e in excerpts}),
            "cited_indices": None,
            "decline_correct": None,
            "looks_truncated": None,
            "notes": ["extractive baseline: top retrieved excerpts verbatim, no model call"],
        }

    raw = cited_raw_value(full_text)
    cited_line_present = raw is not None
    indices = ask.parse_cited_indices(full_text)
    said_none = raw is not None and raw.lower().startswith("none")

    if not cited_line_present:
        fmt_valid = False
        fmt_basis = "no CITED: line in output"
    elif said_none:
        fmt_valid = True
        fmt_basis = 'CITED line parsed as "CITED: none"'
    elif indices:
        fmt_valid = True
        fmt_basis = f'CITED line parsed as "CITED: {", ".join(map(str, indices))}"'
    else:
        fmt_valid = False
        fmt_basis = f'CITED line present but unparseable: "CITED: {raw}"'

    in_range = all(1 <= i <= k for i in indices)
    out_of_range = [i for i in indices if not (1 <= i <= k)]
    sources = ask._dedupe_sources(excerpts, indices)

    # How many distinct essays were even available to cite in the retrieved set —
    # the ceiling on citation_count. Retrieval often returns several chunks of one
    # essay, so a low citation_count can mean "narrow synthesis" or just "the top-k
    # was dominated by one essay". Reporting the denominator disambiguates.
    distinct_available = len({(e["title"], e["url"]) for e in excerpts})

    stripped = full_text.rstrip()
    looks_truncated = bool(stripped) and stripped[-1] not in '.!?)"”' and not cited_line_present

    decline_correct = None
    decline_basis = None
    if expects_decline:
        if not cited_line_present:
            decline_correct = False
            decline_basis = "expected CITED: none, got no CITED line"
        elif indices:
            decline_correct = False
            decline_basis = f"expected CITED: none, got CITED: {', '.join(map(str, indices))} (fabricated citations on a question the archive does not cover)"
        elif said_none:
            decline_correct = True
            decline_basis = "declined with CITED: none and cited nothing"
        else:
            decline_correct = False
            decline_basis = f'expected CITED: none, CITED line reads "{raw}"'

    return {
        "answer_text": answer_text,
        "cited_line_present": cited_line_present,
        "prose_before_cited": bool(answer_text),
        "citation_format_valid": fmt_valid,
        "citation_format_basis": fmt_basis,
        "citations_in_range": in_range,
        "citations_out_of_range": out_of_range,
        "citation_count": len(sources),
        "distinct_essays_available": distinct_available,
        "cited_sources": sources,
        "cited_indices": indices,
        "looks_truncated": looks_truncated,
        "decline_correct": decline_correct,
        "decline_basis": decline_basis,
    }


# --- Run one (question, backend) cell -----------------------------------—--—-


def run_cell(question_obj, backend, model, excerpts, spend_state):
    prompt = ask.build_prompt(question_obj["question"], excerpts)
    expects_decline = question_obj["expects_decline"]

    cell = {"backend": backend, "model": model}

    if backend == "extractive":
        t0 = time.perf_counter()
        full_text = extractive_answer(excerpts)
        cell["latency_s"] = round(time.perf_counter() - t0, 4)
        cell["checks"] = run_checks(full_text, excerpts, expects_decline, is_extractive=True)
        return cell

    if backend == "claude":
        full_text, meta = generate_claude_measured(prompt, model, spend_state)
        cell.update(meta)
        if "latency_s" in meta:
            cell["latency_s"] = round(meta["latency_s"], 3)
        if full_text is None:
            cell["checks"] = None
            return cell
        cell["checks"] = run_checks(full_text, excerpts, expects_decline, is_extractive=False)
        return cell

    # ollama / huggingface
    t0 = time.perf_counter()
    try:
        full_text = ask.generate_answer(prompt, backend, model)
    except ask.GenerationError as e:
        cell["latency_s"] = round(time.perf_counter() - t0, 3)
        cell["error"] = str(e)
        cell["debug_detail"] = e.debug_detail
        cell["checks"] = None
        return cell
    cell["latency_s"] = round(time.perf_counter() - t0, 3)
    cell["checks"] = run_checks(full_text, excerpts, expects_decline, is_extractive=False)
    return cell


# --- Report rendering ---------------------------------------------------—--—-


def fmt_verdict(value):
    if value is None:
        return "n/a"
    return str(value)


def render_markdown(run):
    cfg = run["config"]
    lines = []
    lines.append("# Backend benchmark — latest run")
    lines.append("")
    lines.append("## Methodology")
    lines.append("")
    lines.append(f"- **Run at:** {run['timestamp']}")
    lines.append(f"- **Corpus:** {cfg['corpus_chunk_count']} chunks in the vector store")
    lines.append(f"- **k (chunks retrieved per question):** {cfg['k']}")
    lines.append("- **Questions:**")
    for q in run["questions"]:
        tag = " *(expects decline)*" if q["expects_decline"] else ""
        lines.append(f"  - `{q['id']}` ({q['category']}){tag}: {q['question']}")
    lines.append("- **Backends / models:**")
    for b, m in cfg["backends"]:
        lines.append(f"  - `{b}`" + (f" / `{m}`" if m else " (retrieval-only baseline)"))
    if cfg["include_claude"]:
        s = run["spend_after"]
        lines.append(
            f"- **Claude spend:** this tool has now spent "
            f"${s['total_usd']:.4f} of its ${s['cap_usd']:.2f} self-imposed cap "
            f"(cumulative across all runs; tracks this tool only, not your account balance)"
        )
    lines.append("")
    lines.append("## How to read this")
    lines.append("")
    lines.append(REPORT_LEGEND)
    lines.append("")

    for qr in run["results"]:
        q = qr["question"]
        lines.append(f"## {q['id']} — {q['category']}")
        lines.append("")
        lines.append(f"**Question:** {q['question']}")
        lines.append("")
        lines.append(f"**Expects decline:** {q['expects_decline']}")
        lines.append("")
        lines.append("**Retrieved excerpts (shared across all backends):**")
        lines.append("")
        for i, e in enumerate(qr["excerpts"], 1):
            lines.append(f"{i}. \"{e['title']}\" (distance {e['distance']:.3f}) — {e['url']}")
        lines.append("")

        for cell in qr["cells"]:
            label = f"{cell['backend']}" + (f" / {cell['model']}" if cell.get("model") else "")
            lines.append(f"### {label}")
            lines.append("")

            if cell.get("error"):
                lines.append(f"**errored:** True — {cell['error']}")
                if cell.get("debug_detail"):
                    lines.append("")
                    lines.append(f"> debug: {cell['debug_detail']}")
                lines.append("")
                continue
            if cell.get("skipped_reason"):
                lines.append(f"**skipped:** {cell['skipped_reason']}")
                lines.append("")
                continue

            checks = cell["checks"]
            lines.append(f"**latency_s:** {cell.get('latency_s', 'n/a')}")
            if "cost_usd" in cell:
                lines.append(
                    f"  ·  {cell['input_tokens']} in / {cell['output_tokens']} out tokens  ·  ${cell['cost_usd']:.4f}"
                )
            lines.append("")
            lines.append("**Answer:**")
            lines.append("")
            for para in checks["answer_text"].split("\n"):
                lines.append(f"> {para}")
            lines.append("")

            if cell["backend"] == "extractive":
                lines.append("_citation / decline checks: n/a (retrieval-only baseline)_")
                lines.append("")
                continue

            lines.append(f"- **cited_line_present:** {fmt_verdict(checks['cited_line_present'])}")
            lines.append(f"- **prose_before_cited:** {fmt_verdict(checks['prose_before_cited'])}")
            lines.append(
                f"- **citation_format_valid:** {fmt_verdict(checks['citation_format_valid'])}"
                + (f" ({checks['citation_format_basis']})" if checks.get("citation_format_basis") else "")
            )
            range_line = f"- **citations_in_range:** {fmt_verdict(checks['citations_in_range'])}"
            if checks.get("citations_out_of_range"):
                range_line += f" (out of range: {checks['citations_out_of_range']}, only 1..{len(qr['excerpts'])} retrieved)"
            lines.append(range_line)
            cited_src_titles = ", ".join(f'"{s["title"]}"' for s in checks.get("cited_sources", [])) or "none"
            lines.append(
                f"- **citation_count:** {fmt_verdict(checks['citation_count'])} of "
                f"{checks['distinct_essays_available']} distinct essays in the retrieved set ({cited_src_titles})"
            )
            if checks.get("looks_truncated"):
                lines.append(
                    "- **looks_truncated:** True (output ends mid-sentence with no CITED line — "
                    "likely hit the backend's output token cap)"
                )
            if checks["decline_correct"] is not None:
                lines.append(
                    f"- **decline_correct:** {checks['decline_correct']} ({checks['decline_basis']})"
                )
            else:
                lines.append("- **decline_correct:** n/a (question should be answered, not declined)")
            lines.append("")

    lines.append("## Notes")
    lines.append("")
    lines.append("_Interpretation goes here — the harness does not auto-generate this._")
    lines.append("")
    return "\n".join(lines)


# --- Main ----------------------------------------------------------------—--—-


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--include-claude", action="store_true", help="Add a Claude Sonnet 5 column (subject to the spend cap)")
    parser.add_argument("--claude-model", default=CLAUDE_MODEL, help=f"Claude model id (default {CLAUDE_MODEL})")
    parser.add_argument("--questions", default=None, help="Comma-separated question ids to run (default: all)")
    parser.add_argument("-k", type=int, default=ask.TOP_K, help=f"Chunks retrieved per question (default {ask.TOP_K})")
    parser.add_argument("--reset-spend", action="store_true", help="Reset the cumulative Claude spend tracker to $0 and exit")
    args = parser.parse_args()

    if args.reset_spend:
        state = {"cap_usd": SPEND_CAP_USD, "total_usd": 0.0, "calls": []}
        persist_spend(state)
        print(f"Spend tracker reset: total_usd = 0.0, cap_usd = {SPEND_CAP_USD}")
        return

    all_questions = json.loads(QUESTIONS_FILE.read_text())
    if args.questions:
        wanted = {q.strip() for q in args.questions.split(",")}
        questions = [q for q in all_questions if q["id"] in wanted]
        missing = wanted - {q["id"] for q in questions}
        if missing:
            parser.error(f"unknown question id(s): {', '.join(sorted(missing))}")
    else:
        questions = all_questions

    backends = list(DEFAULT_BACKENDS)
    if args.include_claude:
        backends.append(("claude", args.claude_model))

    spend_state = load_spend()

    from vector_store import get_collection

    corpus_count = get_collection().count()

    config = {
        "k": args.k,
        "backends": backends,
        "include_claude": args.include_claude,
        "corpus_chunk_count": corpus_count,
    }

    print(f"Running {len(questions)} question(s) x {len(backends)} backend(s), k={args.k}")
    if args.include_claude:
        print(f"Claude included. Spend so far: ${spend_state['total_usd']:.4f} / ${spend_state['cap_usd']:.2f} cap")

    results = []
    for q in questions:
        print(f"\n[{q['id']}] {q['question']}")
        excerpts = ask.retrieve(q["question"], args.k)
        cells = []
        for backend, model in backends:
            print(f"  -> {backend}" + (f" / {model}" if model else ""), end="", flush=True)
            cell = run_cell(q, backend, model, excerpts, spend_state)
            if cell.get("error"):
                print(f"  [error: {cell['error'][:60]}]")
            elif cell.get("skipped_reason"):
                print("  [skipped: spend cap]")
            else:
                print(f"  [{cell.get('latency_s', '?')}s]")
            cells.append(cell)
        results.append(
            {
                "question": q,
                "excerpts": [
                    {"title": e["title"], "url": e["url"], "distance": e["distance"]}
                    for e in excerpts
                ],
                "cells": cells,
            }
        )

    run = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "config": config,
        "questions": questions,
        "results": results,
        "spend_after": spend_state,
    }

    RESULTS_DIR.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d-%H%M")
    json_path = RESULTS_DIR / f"{stamp}.json"
    json_path.write_text(json.dumps(run, indent=2))
    md_path = RESULTS_DIR / "latest.md"
    md_path.write_text(render_markdown(run))

    print(f"\nWrote {json_path.relative_to(REPO_ROOT)}")
    print(f"Wrote {md_path.relative_to(REPO_ROOT)}")
    if args.include_claude:
        print(f"Claude spend after this run: ${spend_state['total_usd']:.4f} / ${spend_state['cap_usd']:.2f}")


if __name__ == "__main__":
    main()
