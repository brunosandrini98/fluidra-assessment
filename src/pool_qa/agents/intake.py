from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage

from pool_qa.agents import render_history
from pool_qa.contract import IntakeResult, Turn
from pool_qa.llm import structured

SYSTEM = """You are the intake step of a question-answering tool for pool professionals. The tool answers only from pool equipment documents.

Return:
- decision: "refuse" only when the question is unrelated to pool or spa equipment (installation, operation, maintenance, troubleshooting, safety, specifications). A question about pool equipment that the documents may not cover gets "proceed".
- language: the ISO 639-1 code of the language of the user's question.
- retrieval_query: on "proceed", a short search query in the pivot language ({pivot}) that captures what to look up, using the conversation for context. On "refuse", null."""


def intake_messages(question: str, history: list[Turn], pivot: str) -> list[BaseMessage]:
    return [
        SystemMessage(SYSTEM.format(pivot=pivot)),
        HumanMessage(f"Conversation so far:\n{render_history(history)}\n\nQuestion:\n{question}"),
    ]


async def run_intake(model, pivot: str, question: str, history: list[Turn]) -> IntakeResult:
    return await structured(model, IntakeResult, intake_messages(question, history, pivot))
