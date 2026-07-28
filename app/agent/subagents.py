"""Tutorial subagent definitions."""

from deepagents.middleware.subagents import SubAgent

WEB_RESEARCH: SubAgent = {
    "name": "web-research",
    "description": "Searches the web for relevant information.",
    "system_prompt": (
        "You are a web research specialist. Use the internet_search tool "
        "to find information. Summarize findings concisely."
    ),
    "tools": ["internet_search"],
}

STRUCTURED_DATA: SubAgent = {
    "name": "structured-data",
    "description": "Queries the structured research catalog.",
    "system_prompt": (
        "You are a structured data analyst. Use list_sql_tables, "
        "describe_table, preview_table, and execute_readonly_query "
        "to explore the catalog. Never modify data."
    ),
    "tools": [
        "list_sql_tables",
        "describe_table",
        "preview_table",
        "execute_readonly_query",
    ],
}

KNOWLEDGE_BASE: SubAgent = {
    "name": "knowledge-base",
    "description": "Queries the private knowledge base.",
    "system_prompt": (
        "You are a knowledge retrieval specialist. Use "
        "list_knowledge_assistants and ask_knowledge_assistant "
        "to query private knowledge."
    ),
    "tools": ["list_knowledge_assistants", "ask_knowledge_assistant"],
}

TUTORIAL_SUBAGENTS: list[SubAgent] = [WEB_RESEARCH, STRUCTURED_DATA, KNOWLEDGE_BASE]
