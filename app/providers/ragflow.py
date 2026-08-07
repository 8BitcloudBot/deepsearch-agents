"""Lazy RAGFlow knowledge adapter (0.26.0 API)."""

from app.providers.contracts import KnowledgeAnswer, KnowledgeAssistant


class RAGFlowKnowledgeProvider:
    def __init__(self, api_key: str, base_url: str):
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._client = None

    def _get_client(self):
        if self._client is None:
            from ragflow_sdk import RAGFlow

            self._client = RAGFlow(api_key=self._api_key, base_url=self._base_url)
        return self._client

    def list_assistants(self) -> tuple[KnowledgeAssistant, ...]:
        client = self._get_client()
        try:
            chats = client.list_chats()
        except Exception as exc:
            # Never propagate raw SDK text (may carry keys/paths/payloads).
            raise RuntimeError("RAGFlow list_assistants failed") from exc
        return tuple(
            KnowledgeAssistant(
                name=c.name,
                description=getattr(c, "description", ""),
                knowledge_bases=tuple(getattr(c, "knowledge_bases", [])),
            )
            for c in chats
        )

    def ask(self, assistant_name: str, question: str) -> KnowledgeAnswer:
        client = self._get_client()
        try:
            chats = client.list_chats()
        except Exception as exc:
            raise RuntimeError("RAGFlow ask failed") from exc
        target = None
        for c in chats:
            if c.name == assistant_name:
                target = c
                break
        if target is None:
            raise ValueError(f"Assistant not found: {assistant_name!r}")

        session = target.create_session()
        try:
            # Session.ask(stream=False) is a generator yielding Message objects
            messages = session.ask(question, stream=False)
            final_content = ""
            for msg in messages:
                final_content = getattr(msg, "content", str(msg))
            return KnowledgeAnswer(assistant_name=assistant_name, answer=final_content)
        except Exception as exc:
            # Never propagate raw SDK text (may carry keys/paths/payloads).
            raise RuntimeError("RAGFlow ask failed") from exc
        finally:
            target.delete_sessions([session.id])
