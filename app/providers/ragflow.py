"""Lazy RAGFlow knowledge adapter."""

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
                name=c.get("name", "unknown"),
                description=c.get("description", ""),
                knowledge_bases=tuple(c.get("knowledge_bases", [])),
            )
            for c in chats
        )

    def ask(self, assistant_name: str, question: str) -> KnowledgeAnswer:
        client = self._get_client()
        chats = client.list_chats()
        target = None
        for c in chats:
            if c.get("name") == assistant_name:
                target = c
                break
        if target is None:
            raise ValueError(f"Assistant not found: {assistant_name!r}")

        chat_id = target["id"]
        session = client.create_chat(chat_id, name=f"phase2-{assistant_name}")
        try:
            msgs = client.get_recent_messages(chat_id, session["id"])
            answer = ""
            if msgs:
                answer = msgs[-1].get("content", "")
            return KnowledgeAnswer(assistant_name=assistant_name, answer=answer)
        finally:
            client.delete_chats([session["id"]])
