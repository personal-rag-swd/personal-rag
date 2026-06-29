import logging

from pydantic_ai import Agent

from app.core.config import Settings
from app.core.llm_provider import chat_provider_is_configured, resolve_chat_provider

logger = logging.getLogger(__name__)

query_rewrite_agent = Agent(
    instructions=(
        "You are an expert search query optimizer for a RAG (Retrieval-Augmented Generation) system. "
        "Your role is to rewrite the user's input search query to improve vector search retrieval precision. "
        "Apply the following rules:\n"
        "1. Strip out conversational filler, polite phrasing, and meta-questions (e.g., 'please look up', 'can you find information about', 'do we have documents on').\n"
        "2. Focus on the core semantic meaning and search keywords.\n"
        "3. Rephrase the query into a clear, direct, and search-optimized statement or set of search terms that is most likely to match the database text.\n"
        "4. Output ONLY the final rewritten search query. Do not wrap it in quotes, do not add introductory text, and do not provide any explanation."
    ),
)


def rewrite_query_text(query: str, settings: Settings) -> str:
    if not settings.enable_query_rewrite or not chat_provider_is_configured():
        return query

    try:
        model = resolve_chat_provider()
        result = query_rewrite_agent.run_sync(query, model=model)
        rewritten = result.output.strip()
        if rewritten:
            logger.info("Rewrote RAG query: %r -> %r", query, rewritten)
            return rewritten
    except Exception as e:
        logger.warning("Failed to rewrite query %r: %s", query, str(e))
    return query
