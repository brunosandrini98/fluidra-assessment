# Contract

Schemas and invariants shared by the API, agents, and eval. Rationale in `DECISIONS.md` (D2–D4, D10–D13).

## Glossary

| Term | Meaning |
|---|---|
| `answer` | Grounded response with at least one citation |
| `clarify` | One question back to the user; no citations |
| `abstain` | Evidence insufficient or verification failed; no citations |
| `refuse` | Question outside the tool's domain; no citations |
| `proceed` | Intake decision to hand the question to the Researcher |
| Revision | One Researcher retry after a failed citation check or a `revise` verdict |
| Pivot language | Language of the indexed corpus (`en`) |
| Page | 1-indexed PDF page number, not the printed page number |

## API

### `POST /ask` request

```
question: str                      # non-empty
history: list[Turn] = []

Turn:
  role: "user" | "assistant"
  content: str
  outcome: Outcome | null          # set on assistant turns
```

### Response

```
outcome: "answer" | "clarify" | "abstain" | "refuse"
language: str                      # ISO 639-1, user's language
message: str                       # meaning given by outcome
citations: list[Citation]
warnings: list[Warning]            # reserved; empty until structured safety warnings exist
trace: Trace

Citation:
  id: str                          # "c1", "c2", ...
  chunk_id: str
  document: str
  page: int
  page_in_language: int | null
  section: str | null
  quote: str                       # ≤ 200 chars

Warning:
  id: str
  kind: str                        # e.g. "safety"
  text: str
  page: int

Trace:
  search_calls: int
  revisions: int                   # 0 or 1
  verdict: "pass" | "revise" | "abstain" | null
```

The CLI takes the same request fields and prints the same response.

### Errors

```
error: str                         # "invalid_request" | "provider_error" | "timeout"
detail: str
```

| Status | When |
|---|---|
| 422 | Invalid request |
| 502 | LLM provider failure after retries |
| 504 | Request deadline exceeded |

## Corpus

```
Chunk:
  chunk_id: str
  document: str
  source_type: str                 # e.g. "manual"
  effective_date: date | null
  language: str
  page: int
  section: str | null
  text: str
  figure_refs: list[str]           # e.g. ["Fig. 5"]
  warning_ids: list[str]           # reserved; empty
```

### `search`

```
search(query: str, filters: Filters, k: int) -> list[Chunk]

Filters:
  language: str                    # set by code to the pivot language
  section: str | null
  page_range: (int, int) | null
```

## Agents

### Intake

```
in:  question, history
out: IntakeResult
  decision: "proceed" | "refuse"
  language: str                    # ISO 639-1
  retrieval_query: str | null      # pivot language; null on refuse
```

Refusal `message` is a static phrase per `language`, English fallback.

### Researcher

```
in:  question, history, IntakeResult, issues: list[str] = []
out: ResearchResult
  outcome: "answer" | "clarify" | "abstain"
  message: str                     # answer: draft with [chunk_id] markers, user's language
                                   # clarify: the question; abstain: the reason
  citations: list[{chunk_id: str, quote: str}]
```

### Citation check (code)

```
in:  ResearchResult, retrieved chunks
out: issues: list[str]             # empty = pass
```

### Verifier

```
in:  question, language, draft message, full text of cited chunks
out: VerifierResult
  verdict: "pass" | "revise" | "abstain"
  claims: list[{text: str, supported: bool, chunk_ids: list[str]}]
  issues: list[str]                # non-empty when verdict = revise
```

### Response builder (code)

```
in:  IntakeResult, final ResearchResult | null, VerifierResult | null, retrieved chunks
out: Response
```

## Invariants

1. `citations` is non-empty if and only if `outcome = answer`.
2. Every `[cN]` marker in `message` matches exactly one `citations[].id`, and every citation is referenced.
3. Every cited `chunk_id` was returned by `search` in the same request.
4. Every `quote` is a verbatim substring of its chunk's `text` and ≤ 200 chars.
5. `warnings` is empty.
6. `message` is in `language` for every outcome.
7. At most one revision per request. A failure after it yields `abstain`.
8. `clarify` and `abstain` from the Researcher skip the Verifier.
9. At most one `clarify` per conversation: if `history` contains an assistant turn with `outcome = clarify`, the Researcher may only return `answer` or `abstain`.
10. The server uses the first user turn plus the last N turns of `history` (config, default 5).
11. The Verifier prompt states that evidence is in the pivot language and the draft in `language`.

## Eval

### `eval/golden.jsonl` record

```
id: str
question: str
language: str
expected_outcome: "answer" | "clarify" | "abstain" | "refuse"
expected_pages: list[int]          # empty unless answer
must_include: list[str]            # key facts, including key safety warning; empty unless answer
```
