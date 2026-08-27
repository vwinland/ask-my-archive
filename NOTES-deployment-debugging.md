# Deployment debugging notes

Three distinct issues found while getting the Streamlit Cloud deployment
working end-to-end. Each is a separate root cause; grouped here because they
surfaced close together while chasing "why doesn't the deployed app behave
like it does locally."

Published as: [Build Log: Deployment Debugging](https://vwinland.github.io/blog/build-log-deployment-debugging/)

---

## 2026-08-09 — Relative path resolution broke the deployed store lookup

**Symptom:** The deployed app returned "cannot find any information" on
questions that were well-covered by the archive, even though the vector
store (392 chunks) was committed to the repo and present the whole time.

**Root cause:** `DB_PATH` in `ingest/vector_store.py` was a bare relative
path (`"../store/chroma_db"`), which Python resolves against
`os.getcwd()` at import time — not against the location of the file that
defines it. Every ingest script and `query/ask.py` are documented to be run
from their own directory (`ingest/` or `query/`), so that relative path
always happened to land on `store/chroma_db` correctly in local/CLI use.
Streamlit Cloud, however, runs `streamlit run app/app.py` from the repo
root. From there, `"../store/chroma_db"` resolves to a directory *outside*
the repo entirely. Chroma doesn't error on a missing path — it silently
creates a fresh, empty collection there instead, so the app looked like it
was running fine while actually querying nothing.

**Fix:** Anchor `DB_PATH` to `vector_store.py`'s own file location
(`Path(__file__).parent`) instead of the caller's cwd, so it resolves to the
same directory regardless of which directory the process was launched from.
Verified `collection.count() == 392` from the repo root, `ingest/`, and
`query/` after the fix — all three previously-inconsistent call sites now
resolve to the same store. (Commit `632893d`.)

**Why it's worth remembering:** any relative path in a module that's meant
to be imported from multiple entry points (CLI script vs. deployed app vs.
tests) is a latent bug — it will pass in whichever environment you happened
to test in and silently break in the others. `Path(__file__)`-anchored paths
are the fix whenever "where was this run from" isn't guaranteed.

---

## 2026-08-10 — Ollama vs. Hugging Face: same near-miss question, different failure surface

**Symptom:** The near-miss test question ("What does Vanna think about
quantum computing?") is the one case in `comparison_results.md` specifically
designed to check that a backend declines rather than hallucinates. Ollama
(`llama3.1`) passed it cleanly with a full declining sentence. The Hugging
Face backend (`Qwen/Qwen2.5-7B-Instruct`), on the same question, same
retrieved excerpts, same prompt, returned *only* `CITED: none` — no sentence
of explanation at all. Since the app splits the model's raw output on the
`CITED:` marker and displays everything before it as "the answer," this
produced a blank "Answer" section in the UI: correct in substance (it didn't
fabricate a connection to quantum computing) but presented as if something
had broken.

**Root cause:** The prompt told the model to answer the question and *then*
write the `CITED:` line, but never said a decline still counts as "the
answer" that needs a sentence. Larger/better-instructed models (Claude,
and apparently `llama3.1` too) generalize "answer the question" to include
explaining a decline. Qwen2.5-7B, on this prompt, treated "the excerpts
don't cover this" as satisfied by the `CITED: none` line alone and produced
nothing else — technically compliant with the letter of the instructions,
not the spirit. This reads as a serving/model difference rather than a
retrieval or hallucination problem: nothing about *what* was retrieved
changed between backends, only how tersely the model chose to communicate
a correct decline.

**Fix:** see the next entry — this and the prompt-hardening fix are two
halves of one investigation, split out here because they're conceptually
distinct findings (a behavioral difference between backends vs. the prompt
change that closes the gap).

**Why it's worth remembering:** "the model didn't hallucinate" and "the
model produced a usable response" are different bars. A smaller/free-tier
model can clear the first and still fail the second in a way that's
invisible unless you're testing the exact question shape (a decline) where
minimal-effort compliance and full compliance produce different output
lengths.

---

## 2026-08-10 — Prompt hardening: models can decline with no explanatory sentence

**Root cause:** Same as above — `query/ask.py`'s prompt asked the model to
answer the question and cite sources, but never explicitly required prose
*before* the `CITED:` line in the specific case where the answer is "I
can't." The instruction "say so directly instead of guessing" told the model
*what* to conclude on a non-covered question, but not that it still had to
write that conclusion out as a sentence rather than encoding it purely in
`CITED: none`.

**Fix:** Added an explicit line to the prompt in `build_prompt()`
(`query/ask.py`):

> Always write at least one sentence of explanation before the CITED line,
> even if you are declining to answer because the excerpts don't cover the
> question. Never respond with only the CITED line.

Re-ran all three standard test questions against the Hugging Face backend
after the change. The near-miss question now returns: *"The provided
excerpts do not contain any information about Vanna Winland's thoughts on
quantum computing. Therefore, I cannot provide an answer based on the given
information."* — matching the shape of Ollama's original passing answer.
Full results in `query/comparison_results.md`.

**Defense in depth — UI fallback:** Independent of the prompt fix, added a
guard in `app/app.py` so that if `result.answer` is ever empty or
whitespace-only after the `CITED:` split — regardless of backend, model, or
whether some future prompt regresses this again — the UI shows "No relevant
information found in the archive for this question." instead of a blank
"Answer" section with nothing under it. Verified visually: ran the Streamlit
dev server locally, forced an empty-answer `AskResult` through a temporary
test hook wired to a magic input string, confirmed the fallback text renders
with normal styling and no layout oddities under the "Answer" heading, then
removed the test hook (verified via `git diff` that only the intended
fallback-guard change remains in `app/app.py`).

**Why it's worth remembering:** the prompt fix addresses the *cause*
(the model under-explaining a decline); the UI fallback addresses the
*symptom* (a blank section shown to a user) and is deliberately redundant
with the prompt fix — it's what keeps the UI from ever showing a broken-looking
blank answer again, even if a future model or prompt change reintroduces
sparse output on a decline.

---

## 2026-08-27 — Same decline symptom recurred on IBM explainer questions, root cause was `seed`, not the prompt

**Symptom:** The deployed app declined a well-covered question ("What has
Vanna written about feature extraction?") with a real explanatory sentence
this time — "the excerpts provided do not contain any information about
Vanna Winland or her writings on feature extraction" — so the earlier
`CITED:`-only and blank-answer bugs were both already ruled out by the
symptom shape itself.

**Investigation:** Queried the vector store directly for the same question:
top result is exactly the IBM Think "What is feature extraction?" chunk at
distance ~0.43, so retrieval is not at fault. Re-ran `query/ask.py --backend
huggingface` locally at HEAD (temperature=0 already in place) across four
phrasings of the question — all four returned correct, well-cited answers.
Not reproducible on demand, which pointed at request-to-request variance
rather than a deterministic prompt or retrieval bug.

**Root cause:** `InferenceClient` in `_generate_huggingface()` never passed
`provider=`, so HF's router auto-selects a backend per request. Inspecting
a raw response object surfaced an `x_groq` field, confirming `openai/gpt-oss-20b`
requests are actually being served by Groq — and every response carried a
different, randomly-assigned `seed`, even with `temperature=0` set on our
end. Groq doesn't derive a deterministic seed from `temperature=0`; without
an explicit `seed`, each call is free to sample a different reasoning path.
`gpt-oss-20b` is a reasoning model (responses carry a separate hidden
`reasoning` field ahead of `content`), so a different sampled path can lead
the model to a different judgment call on the exact question the prompt
hardening was already trying to pin down: whether to trust that an
impersonal, citation-heavy explainer chunk still counts as "written by
Vanna." `temperature=0` constrained *how* it samples at each step, not
*which* random path it starts from.

**Fix:** Added `seed=0` alongside `temperature=0` in the `chat_completion()`
call in `_generate_huggingface()` (`query/ask.py`). `InferenceClient.chat_completion`
supports `seed` as a first-class parameter; pinning it removes the
remaining source of run-to-run variance for a fixed prompt. Not re-verified
live end-to-end — this investigation's own repeated test calls exhausted
this month's free HF inference credits (hit the `402` handled by the prior
entry) partway through, so live confirmation is blocked until the credit
reset or a different token is used.

**Why it's worth remembering:** `temperature=0` reads as "deterministic" but
only constrains sampling *given* a seed — it says nothing about the seed
itself. On a router that silently multiplexes across backend providers
(here, Groq under HF's "auto" provider), the seed is provider-chosen and can
vary per request unless pinned explicitly. This is a second, distinct way
for the same symptom (decline despite good retrieval) to reappear after the
first fix — worth checking response metadata for hidden provider-specific
fields (`x_groq` and friends) whenever "same bug, still intermittent after
the prompt fix" comes up again.
