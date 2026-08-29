# Backend benchmark — latest run

## Methodology

- **Run at:** 2026-08-29T19:19:19
- **Corpus:** 1749 chunks in the vector store
- **k (chunks retrieved per question):** 5
- **Questions:**
  - `well-covered-1` (well_covered): What has Vanna written about how AI changes code review?
  - `near-miss-1` (near_miss) *(expects decline)*: What does Vanna think about quantum computing?
  - `cross-essay-1` (cross_essay_synthesis): How does Vanna connect agentic AI coordination to platform engineering governance?
- **Backends / models:**
  - `ollama` / `llama3.1`
  - `huggingface` / `openai/gpt-oss-20b`
  - `extractive` (retrieval-only baseline)

## How to read this

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


## well-covered-1 — well_covered

**Question:** What has Vanna written about how AI changes code review?

**Expects decline:** False

**Retrieved excerpts (shared across all backends):**

1. "Vibe Coding Has a Governance Problem" (distance 0.364) — https://vwinland.github.io/blog/vibe-coding-has-a-governance-problem
2. "Code Review Cannot Scale to the AI Era" (distance 0.408) — https://vwinland.github.io/blog/code-review-cannot-scale-to-the-ai-era
3. "Platform Engineering Is the New Factory Floor" (distance 0.415) — https://vwinland.github.io/blog/platform-engineering-is-the-new-factory-floor
4. "Code Review Cannot Scale to the AI Era" (distance 0.433) — https://vwinland.github.io/blog/code-review-cannot-scale-to-the-ai-era
5. "Code Review Cannot Scale to the AI Era" (distance 0.438) — https://vwinland.github.io/blog/code-review-cannot-scale-to-the-ai-era

### ollama / llama3.1

**latency_s:** 32.864

**Answer:**

> Vanna has written that AI changes the human review bottleneck that used to catch code problems, making it harder for code review to scale in the AI era. This is because AI-generated code is overwhelming human review capabilities, making it difficult to catch problems that used to be caught by human review.

- **cited_line_present:** True
- **prose_before_cited:** True
- **citation_format_valid:** True (CITED line parsed as "CITED: 1, 2, 4")
- **citations_in_range:** True
- **citation_count:** 2 of 3 distinct essays in the retrieved set ("Vibe Coding Has a Governance Problem", "Code Review Cannot Scale to the AI Era")
- **decline_correct:** n/a (question should be answered, not declined)

### huggingface / openai/gpt-oss-20b

**latency_s:** 2.415

**Answer:**

> Vanna argues that the rise of AI‑generated code is breaking the traditional human‑review bottleneck that once served as a reliable proxy for code quality. She explains that while AI review agents and generation models are doing real work—merging faster and catching fewer surface‑level defects—the correlation between a quick human scan and later problems is weakening. As a result, the confidence that reviewers once derived from a human scan no longer guarantees quality, and the tools that are emerging (such as CodeRabbit, Copilot Review, and Claude Code Review) are still ahead of the measurement that would confirm their effectiveness. Vanna stresses that the evidence for structural debt is still early and that the field is still grappling with how to properly evaluate AI‑assisted review, warning against dismissing these tools outright while acknowledging their potential to close the gap in the future.

- **cited_line_present:** True
- **prose_before_cited:** True
- **citation_format_valid:** True (CITED line parsed as "CITED: 2, 4, 5")
- **citations_in_range:** True
- **citation_count:** 1 of 3 distinct essays in the retrieved set ("Code Review Cannot Scale to the AI Era")
- **decline_correct:** n/a (question should be answered, not declined)

### extractive

**latency_s:** 0.0

**Answer:**

> From "Vibe Coding Has a Governance Problem" (https://vwinland.github.io/blog/vibe-coding-has-a-governance-problem):
> *Next in the series: "Code Review Cannot Scale to the AI Era" — why the human review bottleneck that used to catch exactly these problems is breaking down under AI-generated volume, and what has to replace it.*
> 
> From "Code Review Cannot Scale to the AI Era" (https://vwinland.github.io/blog/code-review-cannot-scale-to-the-ai-era):
> # Code Review Cannot Scale to the AI Era
> 
> Open two pull requests side by side. One was written by a person who’s owned this module for three years. The other was written by an agent that has never seen this codebase before today. Strip the author field and the timestamps. Look only at the diff.

_citation / decline checks: n/a (retrieval-only baseline)_

## near-miss-1 — near_miss

**Question:** What does Vanna think about quantum computing?

**Expects decline:** True

**Retrieved excerpts (shared across all backends):**

1. "Use the A2A protocol for AI agent communication" (distance 0.631) — https://www.ibm.com/think/tutorials/use-a2a-protocol-for-ai-agent-communication
2. "If AI Is Coming for Your Job, Why Can't Anyone Tell You How to Use It?" (distance 0.641) — https://vwinland.github.io/blog/if-ai-is-coming-for-your-job-why-cant-anyone-tell-you-how-to-use-it
3. "What is pair programming?" (distance 0.659) — https://www.ibm.com/think/topics/pair-programming
4. "If AI Is Coming for Your Job, Why Can't Anyone Tell You How to Use It?" (distance 0.691) — https://vwinland.github.io/blog/if-ai-is-coming-for-your-job-why-cant-anyone-tell-you-how-to-use-it
5. "Vibe Coding Has a Governance Problem" (distance 0.694) — https://vwinland.github.io/blog/vibe-coding-has-a-governance-problem

### ollama / llama3.1

**latency_s:** 14.855

**Answer:**

> Unfortunately, the excerpts do not provide any information about Vanna's thoughts on quantum computing.

- **cited_line_present:** True
- **prose_before_cited:** True
- **citation_format_valid:** True (CITED line parsed as "CITED: none")
- **citations_in_range:** True
- **citation_count:** 0 of 4 distinct essays in the retrieved set (none)
- **decline_correct:** True (declined with CITED: none and cited nothing)

### huggingface / openai/gpt-oss-20b

**latency_s:** 3.282

**Answer:**

> I’m sorry, but none of the provided excerpts contain any statement or discussion that reveals Vanna Winland’s personal thoughts or opinions about quantum computing. The only mention of quantum computing appears as a prompt in an AI‑assistant tutorial, which does not reflect her own views.

- **cited_line_present:** True
- **prose_before_cited:** True
- **citation_format_valid:** True (CITED line parsed as "CITED: none")
- **citations_in_range:** True
- **citation_count:** 0 of 4 distinct essays in the retrieved set (none)
- **decline_correct:** True (declined with CITED: none and cited nothing)

### extractive

**latency_s:** 0.0003

**Answer:**

> From "Use the A2A protocol for AI agent communication" (https://www.ibm.com/think/tutorials/use-a2a-protocol-for-ai-agent-communication):
> - **Web Search**: "Search for recent news about artificial intelligence"
> - **Weather Data**: "What's the weather like in Tokyo?"
> - **Wikipedia**: "Tell me about quantum computing"
> - **Reasoning**: "What are three reasons why the sky is blue?"
> 
> From "If AI Is Coming for Your Job, Why Can't Anyone Tell You How to Use It?" (https://vwinland.github.io/blog/if-ai-is-coming-for-your-job-why-cant-anyone-tell-you-how-to-use-it):
> # Nobody can tell you how to learn it
> 
> Somewhere in that episode, the host admitted something almost in passing: he’s still bad at using AI himself. He tries it for pulling up an old speech, building a contact list, gets frustrated partway through, and goes back to making phone calls. It wasn’t a gotcha moment, but an honest one in the conversation, and it stuck with me because it’s not an isolated case. He was describing his own job, on air, while reporting on whether the technology is about to upend everyone else’s.

_citation / decline checks: n/a (retrieval-only baseline)_

## cross-essay-1 — cross_essay_synthesis

**Question:** How does Vanna connect agentic AI coordination to platform engineering governance?

**Expects decline:** False

**Retrieved excerpts (shared across all backends):**

1. "Platform Engineering Is the New Factory Floor" (distance 0.300) — https://vwinland.github.io/blog/platform-engineering-is-the-new-factory-floor
2. "Platform Engineering Is the New Factory Floor" (distance 0.321) — https://vwinland.github.io/blog/platform-engineering-is-the-new-factory-floor
3. "Platform Engineering Is the New Factory Floor" (distance 0.325) — https://vwinland.github.io/blog/platform-engineering-is-the-new-factory-floor
4. "Vibe Coding Has a Governance Problem" (distance 0.342) — https://vwinland.github.io/blog/vibe-coding-has-a-governance-problem
5. "The Developer Workstation Is Becoming an Autonomous System" (distance 0.349) — https://vwinland.github.io/blog/the-developer-workstation-is-becoming-an-autonomous-system

### ollama / llama3.1

**latency_s:** 44.235

**Answer:**

> Vanna connects agentic AI coordination to platform engineering governance by framing the governance challenge of agentic systems in terms of the need for governance primitives, such as identity, policy, audit, and access boundaries, which platform teams build to encode an organization's risk posture, compliance requirements, and architectural standards into the environment agents operate inside. This is analogous to how Kubernetes needed RBAC and admission controllers before it was enterprise-ready (1).
> 
> Additionally, she suggests that the scalable response to the structural problem of AI-assisted development generating software at a rate that outpaces human review capacity is a platform engineering practice that embeds governance into the production environment (2). This is presented as a necessary investment for organizations to absorb the production capacity provided by AI-assisted development tools without collapsing under the complexity they generate (3).

- **cited_line_present:** True
- **prose_before_cited:** True
- **citation_format_valid:** True (CITED line parsed as "CITED: 1, 2, 3")
- **citations_in_range:** True
- **citation_count:** 1 of 3 distinct essays in the retrieved set ("Platform Engineering Is the New Factory Floor")
- **decline_correct:** n/a (question should be answered, not declined)

### huggingface / openai/gpt-oss-20b

**latency_s:** 2.387

**Answer:**

> Vanna argues that agentic AI systems need the same kind of governance primitives that made Kubernetes enterprise‑ready—identity, policy, audit, and access boundaries—so that they can be deployed responsibly at scale. She then identifies platform engineering as the function that builds and enforces those primitives for a specific organization, embedding governance directly into the production environment to keep pace with AI‑assisted development. By treating platform engineering as foundational governance and coordination infrastructure, rather than merely a developer‑experience improvement, she shows how it can absorb the production capacity of autonomous tools without collapsing under their complexity. She further explains that architecture must be enforced by mechanisms other than habit, using golden paths, internal developer portals, and platform‑level constraints to shape generation, which she calls the new factory floor. Finally, she notes that the developer workstation has become a production system that requires operational discipline, underscoring the need for platform‑driven governance when thousands of developers operate agentic workstations.

- **cited_line_present:** True
- **prose_before_cited:** True
- **citation_format_valid:** True (CITED line parsed as "CITED: 1, 2, 3, 4, 5")
- **citations_in_range:** True
- **citation_count:** 3 of 3 distinct essays in the retrieved set ("Platform Engineering Is the New Factory Floor", "Vibe Coding Has a Governance Problem", "The Developer Workstation Is Becoming an Autonomous System")
- **decline_correct:** n/a (question should be answered, not declined)

### extractive

**latency_s:** 0.0

**Answer:**

> From "Platform Engineering Is the New Factory Floor" (https://vwinland.github.io/blog/platform-engineering-is-the-new-factory-floor):
> The infrastructure analogy is useful here. [Microsoft, in its open source contributions to the Agentic AI Foundation](https://opensource.microsoft.com/blog/2026/05/18/from-open-source-to-agentic-systems-microsoft-at-open-source-summit-north-america-2026/), framed the governance challenge this way: just as Kubernetes needed RBAC and admission controllers before it was enterprise-ready, agentic systems need governance primitives – identity, policy, audit, access boundaries – before organizations can deploy them responsibly at scale. The platform team is the function that builds those primitives for a specific organization, encoding its particular risk posture, compliance requirements, and architectural standards into the environment agents operate inside.
> 
> From "Platform Engineering Is the New Factory Floor" (https://vwinland.github.io/blog/platform-engineering-is-the-new-factory-floor):
> AI-assisted development generates software at a rate that outpaces human review capacity. That’s not a temporary condition during a transition period – it’s a structural feature of what these tools do. A platform engineering practice that embeds governance into the production environment is one of the few scalable responses to that structural problem.

_citation / decline checks: n/a (retrieval-only baseline)_

## Notes

_Interpretation goes here — the harness does not auto-generate this._
