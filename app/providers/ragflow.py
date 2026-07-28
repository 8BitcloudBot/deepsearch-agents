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
        chats = client.list_chats()
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
        chats = client.list_chats()
        target = None
        for c in chats:
            if c.name == assistant_name:
                target = c
                break
        if target is None:
            raise ValueError(f"Assistant not found: {assistant_name!r}")

        session = target.create_session()
        try:
            answer_data = session.ask(question, stream=False)
            # answer_data may be str or dict
            answer = ""
            if isinstance(answer_data, str):
                answer = answer_data
            elif isinstance(answer_data, dict):
                answer = answer_data.get("answer", str(answer_data))
            return KnowledgeAnswer(assistant_name=assistant_name, answer=answer)
        finally:
            target.delete_sessions([session.id])
