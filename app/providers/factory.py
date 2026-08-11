"""Provider bundle factory from settings."""

from app.providers.contracts import ProviderBundle
from app.providers.mock import (
    MockCatalogProvider,
    MockKnowledgeRetriever,
    MockWebProvider,
)
from app.settings import Phase2Settings


def build_providers(settings: Phase2Settings) -> ProviderBundle:
    """Build ProviderBundle from settings. Real adapters are lazy."""
    web = _build_web(settings)
    catalog = _build_catalog(settings)
    knowledge = _build_knowledge(settings)
    return ProviderBundle(
        web=web,
        catalog=catalog,
        knowledge=knowledge,
        web_mode=settings.web_provider,
        catalog_mode=settings.catalog_provider,
        knowledge_mode=settings.knowledge_provider,
    )


def _build_web(settings: Phase2Settings):
    if settings.web_provider == "tavily":
        if not settings.tavily_api_key:
            raise ValueError("TAVILY_API_KEY required for tavily provider")
        from app.providers.tavily import TavilyWebProvider

        return TavilyWebProvider(api_key=settings.tavily_api_key)
    return MockWebProvider()


def _build_catalog(settings: Phase2Settings):
    if settings.catalog_provider == "mysql":
        if settings.mysql_user != "tutorial_reader":
            raise ValueError("MYSQL_USER must be 'tutorial_reader' for mysql provider")
        from app.providers.mysql import MySQLCatalogProvider

        return MySQLCatalogProvider(
            host=settings.mysql_host,
            port=settings.mysql_port,
            user=settings.mysql_user,
            password=settings.mysql_password,
            database=settings.mysql_database,
        )
    return MockCatalogProvider()


def _build_knowledge(settings: Phase2Settings):
    if settings.knowledge_provider == "qdrant-local":
        raise ValueError(
            "qdrant-local knowledge retrieval is available in the showcase profile"
        )
    return MockKnowledgeRetriever()
