# Decisions

Append-only. To change a decision, add a new entry that supersedes it. Status: `fixed` or `provisional`.

---

## D1 — Scope cut
2026-09-15 · fixed

**Context:** ~4h of implementation left; multi-agent graph plus a 15-item baseline does not fit.
**Decision:**
- Essential: Docling ingestion with parsed output committed; table-aware chunks; figure references as chunk metadata; chunk metadata; hybrid BM25 + dense retrieval, fused, behind a filterable retriever interface; grounding contract with page citations; agent graph; FastAPI `POST /ask` plus thin CLI; golden set of ~12–15 questions with one eval command; deployment doc; README.
- Later: cross-encoder reranker; Langfuse tracing; VLM figure descriptions; 25-question golden set; single-agent baseline.
**Consequences:** Reviewers run the app without running Docling.

## D2 — Agent roster
2026-09-15 · fixed

**Context:** The brief requires multiple agents. Field evidence says decomposition does not raise accuracy; it is defensible for context isolation and safety gating.
**Decision:** Three agents.
- Intake: sees the question and history only. Relevance guardrail (off-topic → refusal); extracts language, product, symptom, task; writes the retrieval query.
- Researcher: sole corpus access via one generic `search(query, filters)` tool, bounded number of calls. Returns a cited draft, a clarifying question, or insufficient evidence.
- Verifier: fresh context with question, draft, and raw text of cited chunks. Returns `pass`, `revise(issues)`, or `abstain`. Does not write content.
**Justification:** Agents are split by context and authority: one faces the technician, one reads the corpus, one can veto.
**Consequences:** No separate composer, table, scoping, or safety agent.

## D3 — Clarification and state
2026-09-15 · fixed

**Context:** Whether clarification is needed depends on retrieved evidence, not the question alone. A 1-document corpus rarely needs it.
**Decision:** Researcher decides. Default is a conditional answer with cited branches; it asks one question only when branches cannot be listed briefly. Server is stateless; the request carries optional client-held `history`.
**Consequences:** Multi-turn works without persistence. LangGraph checkpointer only if substantial time remains. Richer clarification is v2.

## D4 — Verification loop
2026-09-15 · fixed

**Context:** Evaluator-optimizer pattern; critics that author content go unchecked.
**Decision:** Code check first: every citation ID exists in retrieved evidence. Then the LLM Verifier checks claim-level grounding, answer relevance, and missing safety warnings. Max one revision; second failure → abstain.
**Consequences:** Safety warnings must be retrievable with their procedure (see D5).

## D5 — Tables, figures, safety warnings at ingestion
2026-09-15 · provisional

**Context:** Table representation depends on what Docling produces for this manual; not yet tested.
**Decision:** No table-specific tool. Tables keep row/column semantics inside chunks. Figure references and inline safety warnings attach to their procedure chunks. Exact representation set after a Docling spike.
**Consequences:** The spike runs before ingestion code is committed.

## D6 — LLM provider and models
2026-09-15 · fixed

**Context:** Reviewer needs one key. Fluidra targets AWS; Claude is on Bedrock.
**Decision:** Anthropic. Intake `claude-haiku-4-5`, Researcher `claude-sonnet-5`, Verifier `claude-opus-5`. Model per agent is a config string; no provider-only features (citations built from chunk IDs).
**Consequences:** Verifier is a different model but same family as the generator; self-evaluation bias is mitigated only by fresh context and the code check. Switching provider may need prompt retuning, measured by the eval.

## D7 — Embeddings
2026-09-15 · provisional

**Context:** Anthropic has no embeddings API; one-key constraint.
**Decision:** Local `multilingual-e5-small` via `sentence-transformers`. Upgrade to `bge-m3` if the eval shows retrieval misses.
**Consequences:** First run downloads the model (~0.5 GB).

## D8 — Languages
2026-09-15 · fixed

**Context:** The manual contains 9 parallel language sections.
**Decision:** Index English only as pivot language. Intake writes the retrieval query in the pivot language. Answers are in the technician's language. Citations map to the technician's language section via page offsets from the manual index, stored as metadata.
**Consequences:** Big simplification that will not survive corpus growth. Assumes every language has identical facts and parallel page structure; at scale coverage is asymmetric and layouts differ, requiring multilingual indexing with dedup and passage-level translation linkage. To be stated in the deployment doc.

## D9 — Repo documents
2026-09-15 · fixed

**Decision:** `README.md` (run, scope), `DESIGN.md` (architecture, agents, stack, evals, steps with time budgets), `CONTRACT.md` (answer schema, agent I/O), `DECISIONS.md` (this file), `CLAUDE.md`/`AGENTS.md` (coding-agent instructions).

## D10 — Evaluation
2026-09-15 · fixed

**Context:** Evals define done for every step; grounding and abstention are the core risks.
**Decision:**
- Golden set: 14 dev-owned questions in `eval/golden.jsonl` covering procedure, tables, figure reference, safety, non-English, not-in-manual, off-topic, ambiguous. Fields: `id`, `question`, `language`, `expected_outcome`, `expected_pages`, `must_include`, `expected_warning_ids`.
- Code gates: outcome match ≥ 13/14; 0 answers where abstain/refuse was expected; retrieval recall@k ≥ 90%; citation page in `expected_pages` ≥ 90%; citation IDs valid 100%; answer language match 100%; `expected_warning_ids` ⊆ returned `safety_warning_ids` 100%.
- LLM-judge gates: groundedness as claim counts (`supported/total`), 0 unsupported claims; `must_include` coverage ≥ 90%.
- Judge validation: dev labels claims for ~5 answers; report judge–human agreement.
- Harness: own script, `python -m eval.run`, table plus JSON report.
**Consequences:** Ingestion must assign warning IDs linked to procedure chunks (D5). Judge shares model family with the Verifier (D6). RAGAS/DeepEval are later.

## D11 — Safety warnings attached in code
2026-09-15 · fixed · supersedes the safety-warning check in D4

**Context:** Ingestion links warning IDs to chunks (D5, D10); an LLM check is unnecessary for presence.
**Decision:** The response builder attaches warnings as the union of `warning_ids` of cited chunks. The Verifier no longer checks for missing warnings.
**Consequences:** Warning coverage depends on ingestion linkage quality, measured by the `expected_warning_ids` gate. Documents without warnings return an empty list.

## D12 — Delivery tiers
2026-09-15 · fixed · supersedes the essential/later split in D1

**Context:** A flat essential list does not guarantee a working submission if time runs out mid-list.
**Decision:** Interfaces and schemas are final at Tier 0; later tiers change implementations only. Every tier ends running, committed, and documented.
- Tier 0: crude text extraction of English pages; BM25 inside `search()`; 3 agents with revision cap; `/ask` and CLI; 5 golden questions and `eval.run`; draft deployment doc; README. Exit: end-to-end on 5 questions, 0 answers where abstain/refuse expected, citation IDs valid.
- Tier 1: Docling (tables, warnings, sections); hybrid retrieval; 14 golden questions. Exit: all D10 gates pass.
- Tier 2: judge validation; per-language page mapping; clarification cap enforced; deployment doc final. Exit: judge–human agreement reported.
- Later: items listed as later in D1.
**Consequences:** Tier 0 chunks carry every field with empty or null values where data is missing; consumers handle empties. Golden set keys on pages, not chunk IDs, so re-chunking does not invalidate it. Gates not yet reachable in a tier are reported as pending, not failed.

## D13 — Contract conventions
2026-09-15 · fixed

**Context:** Contract terms must be consistent across agents, API, and eval.
**Decision:**
- One outcome vocabulary: `answer | clarify | abstain | refuse`. Intake returns `proceed | refuse`; Researcher `answer | clarify | abstain`; Verifier `verdict: pass | revise | abstain`.
- Single `message` field; `outcome` gives its meaning. `citations` non-empty only for `answer`.
- Markers `[cN]` in `message` map 1:1 to `citations[].id`; Researcher cites `chunk_id`s, code renumbers.
- Citation `quote` ≤ 300 chars, verbatim substring of the chunk, checked in code.
- History is client-held, roles `user | assistant`; assistant turns carry `outcome`. Server uses the last N turns.
- Max 1 clarification per conversation, enforced in code from history; afterwards conditional answer or abstain.
- Retriever filters include `language`, set by code to the pivot language, not by the LLM.
- Warnings carry `kind` (e.g. `safety`) so other notice types, such as superseding bulletins, fit without a schema change; empty list when none.
- Intake does not extract product, symptom, or task; nothing consumes them with one document. Product/model becomes a filter when the corpus has several products.
- Verifier prompt states evidence is in the pivot language and the draft in the user's language.
**Consequences:** `CONTRACT.md` includes a glossary and these invariants.

## D14 — Stack
2026-09-15 · fixed

**Decision:** Python 3.12 with `uv`; `pypdf` (Tier 0 extraction); `docling` (Tier 1); `bm25s`; `sentence-transformers` with `multilingual-e5-small` (D7); in-memory numpy vectors persisted to disk; reciprocal rank fusion; `langgraph` + `langchain-anthropic` via `init_chat_model`; `pydantic` v2; `fastapi` + `uvicorn`; `argparse` CLI; `pydantic-settings` with `.env`; `lingua-language-detector` for eval language checks; `pytest`.
**Context:** ~100 chunks need no vector DB; `pypdf` avoids PyMuPDF's AGPL; `bm25s` is maintained; `lingua` is more accurate on short text (per its own benchmarks, unverified).
**Consequences:** Vector store is replaceable behind the retriever interface.

## D15 — Initial skeleton
2026-09-15 · fixed · extends D9

**Context:** Verification criteria are defined before implementation.
**Decision:** The initial commit contains `DESIGN.md`, `CONTRACT.md`, `DECISIONS.md`, `AGENTS.md`, `CLAUDE.md` (imports `@AGENTS.md`), a `README.md` skeleton, and `eval/golden.jsonl` with the 5 Tier 0 questions. `DEPLOYMENT.md` is written during Tier 0. Known simplifications are listed in one place: `DESIGN.md` § Known limitations.
**Consequences:** `DEPLOYMENT.md` and `README.md` reference Known limitations instead of repeating it.

## D16 — Structured safety warnings deferred
2026-09-15 · fixed · supersedes D11; supersedes the warning parts of D4, D5, D10, D12

**Context:** Warning IDs require ingestion linkage coupled to the golden set; high cost, low technical value within Tiers 0–2.
**Decision:** No warning IDs, warning store, code attachment, or warning gate. Researcher prompt includes safety instructions present in retrieved chunks. Safety golden questions list the key warning in `must_include`. `warnings` (response) and `warning_ids` (chunk) remain as empty reserved fields. Structured warnings move to Later.
**Consequences:** Safety coverage is prompt-dependent, measured only by `must_include` coverage. Listed in Known limitations.

## D17 — Contract details
2026-09-15 · fixed · supersedes the quote cap in D13

**Decision:**
- `page` is the 1-indexed PDF page, not the printed page; golden `expected_pages` use the same convention.
- Researcher selects each citation `quote`; ≤ 200 chars, verbatim, checked in code.
- Refusal messages are static phrases per language, English fallback; Intake does not generate them.
- Errors: LLM call timeout; retry with exponential backoff on 429, 5xx, connection errors; per-request deadline. HTTP 422 invalid request, 502 provider failure, 504 deadline.
- Server uses the first user turn plus the last N turns of history, N = 5 by default. Rolling summary is Later.
**Context:** PDF page indices open directly in viewers; static refusals cannot hallucinate; provider failures are not evidence outcomes.
