"""Knowledge base LangChain tools."""

import asyncio

from langchain_core.tools import tool

from app.providers.contracts import KnowledgeProvider


def create_knowledge_tools(provider: KnowledgeProvider):
    @tool
    async def list_knowledge_assistants() -> str:
        """List available knowledge base assistants."""
        result = await asyncio.to_thread(provider.list_assistants)
        return "\n".join(f"- {a.name}: {a.description}" for a in result)

    @tool
    async def ask_knowledge_assistant(assistant_name: str, question: str) -> str:
        """Ask a question to a specific knowledge assistant."""
        result = await asyncio.to_thread(provider.ask, assistant_name, question)
        return f"[{result.assistant_name}] {result.answer}"

    return [list_knowledge_assistants, ask_knowledge_assistant]
