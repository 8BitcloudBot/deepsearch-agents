"""Tutorial subagent definitions.

Uses real LangChain tool callables, not string names.
Tools are injected by the builder function.
"""

from deepagents.middleware.subagents import SubAgent


def build_tutorial_subagents(
    web_tools: list,
    catalog_tools: list,
    knowledge_tools: list,
) -> list[SubAgent]:
    """Build the three tutorial subagents with real tool callables."""
    return [
        {
            "name": "web-research",
            "description": "Searches the web for relevant information.",
            "system_prompt": (
                "You are a web research specialist. Use the internet_search "
                "tool to find information. Summarize findings concisely."
            ),
            "tools": web_tools,
        },
        {
            "name": "structured-data",
            "description": "Queries the structured research catalog.",
            "system_prompt": (
                "You are a structured data analyst. Use list_sql_tables, "
                "describe_table, preview_table, and execute_readonly_query "
                "to explore the catalog. Never modify data."
            ),
            "tools": catalog_tools,
        },
        {
            "name": "knowledge-base",
            "description": "Queries the private knowledge base.",
            "system_prompt": (
                "You are a knowledge retrieval specialist. Use "
                "search_knowledge to retrieve evidence chunks from the local "
                "knowledge index. Do not invent answers or source identities."
            ),
            "tools": knowledge_tools,
        },
    ]
