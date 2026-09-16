from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage

from pool_qa.agents import render_chunks
from pool_qa.contract import Chunk, VerifierResult
from pool_qa.llm import structured

SYSTEM = """You verify a draft answer for pool professionals against the document chunks it cites. You never write or rewrite the answer.

The evidence chunks are in the pivot language ({pivot}); the draft is in the user's language ({language}). Compare meaning across the two languages.

Markers like [chunk_id] in the draft show which chunk supports each claim. For each factual claim, record its text, whether the cited chunks support it, and the chunk_ids that support it.

Verdict:
- "pass": every claim is supported by its cited chunks and the draft answers the question.
- "revise": some claims are unsupported or wrongly cited, or the draft does not answer the question, and a corrected draft from the documents seems possible. List each problem in issues.
- "abstain": the cited chunks cannot support an answer to the question."""


def verifier_messages(
    question: str, language: str, draft: str, chunks: list[Chunk], pivot: str
) -> list[BaseMessage]:
    return [
        SystemMessage(SYSTEM.format(pivot=pivot, language=language)),
        HumanMessage(f"Question:\n{question}\n\nDraft:\n{draft}\n\nCited chunks:\n{render_chunks(chunks)}"),
    ]


async def run_verifier(
    model, pivot: str, question: str, language: str, draft: str, chunks: list[Chunk]
) -> VerifierResult:
    return await structured(
        model, VerifierResult, verifier_messages(question, language, draft, chunks, pivot),
        valid=lambda r: r.verdict != "revise" or bool(r.issues),
    )
