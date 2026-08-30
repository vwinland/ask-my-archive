# Backend benchmark harness

`query/ask.py` supports three swappable generation backends: Claude, Ollama, and
Hugging Face. Every time Hugging Face's free tier changes routing or drops a
model, the comparison in `query/comparison_results.md` has to be re-run and
re-transcribed by hand. This turns that into a script: run the same eval
questions against whichever backends are current, get a structured report back.

## Running it

From the repo root:

```
python3 -m bench.run_benchmark                          # free backends only
python3 -m bench.run_benchmark --include-claude         # adds Claude Sonnet 5, cap-gated
python3 -m bench.run_benchmark --questions near-miss-1 -k 8
python3 -m bench.run_benchmark --reset-spend            # zero the spend tracker
python3 -m bench.run_benchmark --help                   # this list
```

Flags:

| Flag | Default | What it does |
| --- | --- | --- |
| `--include-claude` | off | Add a Claude column. Every call is checked against the spend cap first; if it would go over, that call is skipped and the report says so. |
| `--claude-model MODEL` | `claude-sonnet-5` | Which Claude model the `--include-claude` column uses. Only `claude-sonnet-5` has a price entry, so other models will error on the cost check. |
| `--questions IDs` | all | Comma-separated question ids from `eval_questions.json`, e.g. `near-miss-1,cross-essay-1`. Unknown ids are rejected. |
| `-k N` | 5 | How many excerpts to retrieve per question. Retrieval happens once and is shared across all backends in the run. |
| `--reset-spend` | — | Set the cumulative Claude spend back to $0 and exit without running anything. |

Reads credentials from the repo-root `.env`, same as `ask.py`. Ollama needs
`ollama serve` running; Hugging Face needs `HF_TOKEN` and unspent free credits.
A backend that's unavailable is recorded as a result, not treated as a harness
failure.

A default run takes a few minutes — Ollama is the slow part (roughly 15-100s
per question), Hugging Face and extractive are seconds.

Each run writes `results/<timestamp>.json` (full structured data, for tracking
trends across runs) and regenerates `results/latest.md` (human-readable, with a
methodology header and a legend so any verdict is checkable against the answer
text next to it).

## When to run it

Run it when something could have changed the answers, not on a schedule:

- Hugging Face's free tier shifts — new routing, a dropped model, or you swap in
  a replacement. Run this before hand-testing to see whether the new model keeps
  the citation format, still declines the near-miss question, and doesn't
  truncate on the synthesis question.
- You edit the prompt in `build_prompt()`.
- You re-ingest or grow the corpus, or change `TOP_K` / `retrieve()`.
- You want current numbers for a build-log entry instead of the older ones in
  `query/comparison_results.md`.

A scheduled run with no code change just produces noise — the free backends
vary run to run even with a fixed prompt.

## Cost

A default run never calls Claude. `--include-claude` adds a Claude Sonnet 5
column gated by a hard $0.50 cumulative cap tracked in `spend_tracker.json`
(gitignored), computed from the real `usage` field on every response. Once a
call's estimated cost would push the running total past the cap, further Claude
calls are refused. The cap only tracks this tool's own spend — Anthropic's API
doesn't expose account credit balance, so check that at
platform.claude.com/settings/billing.

## What it checks

Structural properties only, no LLM-as-judge: decline correctness on questions
tagged `expects_decline`, citation-format validity (reusing
`ask.parse_cited_indices`), citation count against the distinct essays retrieval
surfaced, output truncation, backend errors captured verbatim, and latency. The
`extractive` "backend" is non-generative — it returns the top retrieved excerpts
as the answer, as a groundedness baseline.

It does not check semantic faithfulness — whether a model misrepresented an
excerpt while still citing it correctly. That gap needs a judge model or manual
spot-checking and is deliberately deferred. `latest.md` ends with an empty
`## Notes` section for that reading.

## Adding questions

Append to `eval_questions.json`: an `id`, a `category`, the `question`, and
`expects_decline` (which is what makes the decline check possible without a
human in the loop).

## Design note

No changes to `ask.py`. The harness reuses its seams directly — `retrieve()`,
`build_prompt()`, `generate_answer()`, `parse_cited_indices()` — and does not
call `ask()` itself, because `ask()` strips the `CITED:` line out of the answer
before returning and the structural checks need the raw model output. The Claude
call is the one exception: the harness makes it directly rather than through
`generate_answer()`, because it needs the token `usage` back for the spend cap.

Built with Claude Code against a spec written collaboratively in a Claude chat
session; see the spec for the full rationale and the decisions left open.
