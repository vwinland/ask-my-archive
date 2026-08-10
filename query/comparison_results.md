# Backend comparison: Claude vs. local Ollama vs. Hugging Face

Test questions run against `query/ask.py`, comparing the hosted Claude backend,
a local Ollama model, and Hugging Face's free Serverless Inference API, on the
same retrieval pipeline (top-5 chunks, same prompt, same citation-parsing
logic). The Hugging Face results below were run after the prompt-hardening fix
described in `NOTES-deployment-debugging.md` (requiring at least one sentence
of prose before the `CITED:` line) — see that doc for why the fix was needed.

## Ollama (`llama3.1`)

### 1. Well-covered question

**Question:** What has Vanna written about how AI changes code review?

**Answer:**

> Vanna has written that AI changes code review in two main ways:
>
> - The human review bottleneck is breaking down under AI-generated volume, making it harder to catch problems through traditional code review (2).
> - What review confidence used to be evidence of (i.e. code quality) no longer correlates as well with what causes problems later, because the things a fast human scan could catch are not as strongly correlated with defects as they once were (4).

**Sources:**
- Code Review Cannot Scale to the AI Era (https://vwinland.github.io/blog/code-review-cannot-scale-to-the-ai-era)

---

### 2. Near-miss question

**Question:** What does Vanna think about quantum computing?

**Answer:**

> Vanna does not mention quantum computing in any of her essays.

**Sources:** (none cited)

**Note:** This is the important result. `llama3.1` correctly declined rather
than confidently guessing, and cited nothing — the retrieval returned
whatever was closest in the corpus (nothing about quantum computing), and the
model didn't fabricate a connection just because it had excerpts in front of
it.

---

### 3. Cross-essay synthesis question

**Question:** How does Vanna connect agentic AI coordination to platform engineering governance?

**Answer:**

> Vanna connects agentic AI coordination to platform engineering governance in the following ways:
>
> - Agentic systems need governance primitives such as identity, policy, audit, and access boundaries before they can be deployed responsibly at scale (1).
> - The platform team is responsible for building these primitives for a specific organization, encoding its particular risk posture, compliance requirements, and architectural standards into the environment agents operate inside (1).
> - A platform engineering practice that embeds governance into the production environment is one of the few scalable responses to the problem of AI-assisted development generating software at a rate that outpaces human review capacity (2).
> - Platform engineering provides the governance infrastructure needed for AI systems to respect boundaries and conform to agreed-upon architecture, rather than relying on habit or internal developer portals (4).

**Sources:**
- Platform Engineering Is the New Factory Floor (https://vwinland.github.io/blog/platform-engineering-is-the-new-factory-floor)
- Vibe Coding Has a Governance Problem (https://vwinland.github.io/blog/vibe-coding-has-a-governance-problem)

---

## Claude (`claude-opus-5`)

### 1. Well-covered question

**Question:** What has Vanna written about how AI changes code review?

**Answer:**

> Vanna's main treatment of this is the essay **"Code Review Cannot Scale to the AI Era"** [2, 4, 5], which is positioned as a follow-on to **"Vibe Coding Has a Governance Problem"** [1].
>
> **The framing of the problem.** The series note at the end of the vibe-coding piece describes the next essay as being about "why the human review bottleneck that used to catch exactly these problems is breaking down under AI-generated volume, and what has to replace it" [1]. The code review essay itself opens with a thought experiment: two pull requests side by side, one from a person who has owned the module for three years, one from an agent that has never seen the codebase before that day — strip the author field and timestamps and look only at the diff [2]. (The excerpt stops there, so I can't tell you what conclusion she draws from the comparison.)
>
> **What she says actually changed.** In a section called "Where the Value Actually Went," she explicitly rejects both the claim that AI code review tools don't work and the call to go back to manual review. Review agents and the underlying generation models are "doing real work" — faster merges and genuinely fewer surface-level defects "are not illusions." The shift is in *what review confidence is evidence of*: it used to be a reasonable proxy for code quality, because the things a fast human scan could catch correlated fairly well with the things that caused problems later, and that correlation is weakening [4].
>
> **Her stated uncertainty.** She is unusually explicit about the limits of the argument: the structural-debt evidence is early, "More Code, Less Reuse" is one study rather than a consensus, and the RLHF-driven explanation for the inversion is the authors' proposed mechanism — an interpretation, not established fact. She flags that the defect-rate figures come from CodeRabbit's published report and the "comfortable-assumption" numbers from Anthropic's blog post about its own product, both vendors with a direct stake in the result. She also notes that the tools implicitly criticized in the piece (CodeRabbit, Copilot Review, Claude Code Review) are "the most plausible path to eventually closing the gap they're currently obscuring," and concludes that "the tooling is ahead of the measurement, in both directions" — including her own essay in the caution about overconfident claims [5].
>
> **Related context from another essay.** In "Platform Engineering Is the New Factory Floor," she makes an adjacent point about why AI raises the stakes: when a developer writes code manually, much quality control happens implicitly in the act of writing — noticing a function is getting too complex, remembering a service's contract, recognizing a duplicated pattern. "Writing is slow enough that judgment is woven into production" [3].

**Sources:**
- Vibe Coding Has a Governance Problem (https://vwinland.github.io/blog/vibe-coding-has-a-governance-problem)
- Code Review Cannot Scale to the AI Era (https://vwinland.github.io/blog/code-review-cannot-scale-to-the-ai-era)
- Platform Engineering Is the New Factory Floor (https://vwinland.github.io/blog/platform-engineering-is-the-new-factory-floor)

---

### 2. Near-miss question

**Question:** What does Vanna think about quantum computing?

**Answer:**

> The excerpts provided don't contain anything about quantum computing. They cover three other topics: the gap between confident predictions about AI displacing jobs and anyone's ability to explain how to actually get good at using AI ("If AI Is Coming for Your Job, Why Can't Anyone Tell You How to Use It?"), vibe coding as a path into building for people who wouldn't have learned to code traditionally ("Vibe Coding Has a Governance Problem"), and multi-agent coordination research like ChatDev, MacNet, and Puppeteer ("Agentic Coordination Isn't New. It's 25 Years Old").
>
> I can't answer your question without guessing, so I'd need excerpts from writing that actually addresses quantum computing.

**Sources:** (none cited)

---

### 3. Cross-essay synthesis question

**Question:** How does Vanna connect agentic AI coordination to platform engineering governance?

**Answer:**

> Across the excerpts, Vanna's argument runs from the individual workstation up to the organization-wide platform.
>
> **The scaling problem that creates the need.** In "The Developer Workstation Is Becoming an Autonomous System," she frames the workstation itself as a production system requiring operational discipline, and then poses the coordination question directly: what happens when thousands of developers run agentic workstations inside one engineering organization, each generating code faster than the shared infrastructure was built to handle? She explicitly names that as the hand-off into the platform engineering argument — why platform engineering is "no longer optional in the age of AI-generated software" [5]. "Platform Engineering Is the New Factory Floor" states the underlying structural claim: AI-assisted development produces software faster than human review capacity can absorb, and this is a permanent feature of the tools rather than a transitional condition [2].
>
> **Governance primitives as the answer.** In that same essay she uses an infrastructure analogy drawn from Microsoft's open source contributions to the Agentic AI Foundation: just as Kubernetes required RBAC and admission controllers before it was enterprise-ready, agentic systems need governance primitives — identity, policy, audit, access boundaries — before organizations can deploy them responsibly at scale. The platform team is the function that builds those primitives for a specific organization, encoding its risk posture, compliance requirements, and architectural standards into the environment agents operate inside [1]. Embedding governance into the production environment is, she argues, one of the few *scalable* responses to the review-capacity problem [2].
>
> **Why enforcement has to be structural, not cultural.** "Vibe Coding Has a Governance Problem" supplies the reason this can't be left to team norms: architecture has to be enforced by something other than habit, because AI systems don't inherently respect the boundaries a team has agreed to. Golden paths, internal developer portals, and platform-level constraints exist to give generation "a shape to conform to" — which she identifies as the same governance infrastructure the factory-floor essay describes [4].
>
> **The framing that ties it together.** Her conclusion is that platform engineering should be treated not as a developer experience improvement but as the governance *and coordination* infrastructure that makes AI-assisted development sustainable — the thing that lets organizations absorb the production capacity these tools provide without collapsing under the complexity they generate [3].

**Sources:**
- Platform Engineering Is the New Factory Floor (https://vwinland.github.io/blog/platform-engineering-is-the-new-factory-floor)
- Vibe Coding Has a Governance Problem (https://vwinland.github.io/blog/vibe-coding-has-a-governance-problem)
- The Developer Workstation Is Becoming an Autonomous System (https://vwinland.github.io/blog/the-developer-workstation-is-becoming-an-autonomous-system)

---

## Hugging Face (`Qwen/Qwen2.5-7B-Instruct`)

### 1. Well-covered question

**Question:** What has Vanna written about how AI changes code review?

**Answer:**

> Vanna Winland discusses how AI changes the landscape of code review, particularly in the context of scaling to the volume generated by AI. She notes that the traditional human review process, which used to catch many issues, is becoming less effective as AI-generated code increases in volume. This shift means that the value of code review is changing, as the correlation between initial review and later issues is weakening. Cited changes in how code quality is perceived and the need for new approaches to code review are discussed.

**Sources:**
- Vibe Coding Has a Governance Problem (https://vwinland.github.io/blog/vibe-coding-has-a-governance-problem)
- Code Review Cannot Scale to the AI Era (https://vwinland.github.io/blog/code-review-cannot-scale-to-the-ai-era)

---

### 2. Near-miss question

**Question:** What does Vanna think about quantum computing?

**Answer:**

> The provided excerpts do not contain any information about Vanna Winland's thoughts on quantum computing. Therefore, I cannot provide an answer based on the given information.

**Sources:** (none cited)

**Note:** Before the prompt-hardening fix, this exact question was where Qwen
failed: it emitted only `CITED: none` with no sentence in front of it,
producing a blank "Answer" section in the UI. Same retrieval, same excerpts,
same underlying task as the Ollama near-miss case above — the difference was
purely in whether the model wrote a declining sentence before its citation
line. See `NOTES-deployment-debugging.md` for the root cause and fix.

---

### 3. Cross-essay synthesis question

**Question:** How does Vanna connect agentic AI coordination to platform engineering governance?

**Answer:**

> Vanna connects agentic AI coordination to platform engineering governance by framing the governance challenge in a way that parallels the evolution of infrastructure management. Just as Kubernetes needed specific governance primitives (like RBAC and admission controllers) to become enterprise-ready, agentic systems require similar governance mechanisms to be deployed responsibly at scale. Platform engineering teams are responsible for building these governance primitives tailored to the organization's risk posture, compliance requirements, and architectural standards.

**Sources:**
- Platform Engineering Is the New Factory Floor (https://vwinland.github.io/blog/platform-engineering-is-the-new-factory-floor)

---

## Observations

- **Near-miss handling was the deciding test, and all three backends ultimately passed it — but not on the first try.** Neither Claude nor Ollama ever fabricated a connection to quantum computing. Hugging Face's Qwen model also never fabricated a connection, but it initially failed the test in a different way: it declined correctly in substance (`CITED: none`, nothing cited) while omitting the sentence explaining *why*, which read as a blank/broken answer in the UI rather than a correct decline. That's a formatting failure, not a hallucination, but it's still a real failure mode for a public-facing tool — see `NOTES-deployment-debugging.md`.
- **Citation format compliance was 100% across all three backends on the numeric `CITED: n, n` format** — the gap wasn't in whether the model could follow the citation instruction, it was in whether it treated "explain your answer" as equally mandatory on a decline as on a normal answer.
- **Depth and synthesis differ more than correctness does.** Claude's answers are longest and quote source text directly. Ollama and Hugging Face are both shorter and more summary-like; Hugging Face's synthesis answer (question 3) cited only 1 source where Claude and Ollama both cited multiple, suggesting its synthesis across essays is shallower even when the underlying facts are correct.
- **Practical read:** for this retrieval task, neither free backend (local Ollama or hosted Hugging Face) is obviously wrong on any of the three tests in terms of hallucination — the real gap between backends is in richness of synthesis and, for Hugging Face specifically, in strict adherence to output-format instructions under sparse-output conditions (i.e. when the "correct" answer is short, like a decline).
