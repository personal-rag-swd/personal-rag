from pydantic_ai import Agent
from pydantic_ai.models.openrouter import OpenRouterModel
from pydantic_ai.providers.openrouter import OpenRouterProvider

from app.core.config import get_settings
from app.notebooks.schemas import (
    BlogPostReport,
    BriefingDocReport,
    CustomReport,
    StudyGuideReport,
)

_BRIEFING_SYSTEM = """
You are an expert analyst. Given source excerpts from a notebook, produce a concise briefing document.
- executive_summary: 2-3 paragraph synthesis of the material.
- key_takeaways: 5-8 bullet points capturing the most important facts or findings.
- strategic_implications: 3-5 actionable implications or decisions that follow from this material.
Respond only with the structured JSON output. Do not fabricate information not present in the sources.
""".strip()

_STUDY_GUIDE_SYSTEM = """
You are an expert educator. Given source excerpts from a notebook, produce a study guide.
- glossary: 8-15 important terms with clear, accurate definitions drawn from the sources.
- quiz: 5-8 multiple-choice questions (4 options each) that test deep understanding.
  Each quiz item must include the correct answer and a brief explanation.
Respond only with the structured JSON output. Do not fabricate information not present in the sources.
""".strip()

_BLOG_SYSTEM = """
You are a professional writer. Given source excerpts from a notebook, produce an engaging blog post.
- title: A compelling, SEO-friendly title.
- hook: An opening paragraph (2-4 sentences) that grabs the reader's attention.
- markdown_body: The full article body in Markdown, using headers, lists, and emphasis where appropriate.
Respond only with the structured JSON output. Do not fabricate information not present in the sources.
""".strip()

_CUSTOM_SYSTEM_BASE = """
You are a helpful assistant. Respond to the user's instructions using only the notebook sources provided.
Produce well-structured Markdown output in the markdown_content field.
Do not fabricate information not present in the sources.
""".strip()


def _make_model() -> OpenRouterModel:
    settings = get_settings()
    provider = OpenRouterProvider(api_key=settings.openrouter_api_key)
    return OpenRouterModel(settings.openrouter_model, provider=provider)


def _build_user_message(context: str, additional_instructions: str | None) -> str:
    parts = [f"SOURCE MATERIAL:\n\n{context}"]
    if additional_instructions and additional_instructions.strip():
        parts.append(f"Additional User Requirements: {additional_instructions.strip()}")
    return "\n\n".join(parts)


async def generate_briefing_doc(
    context: str,
    additional_instructions: str | None = None,
) -> BriefingDocReport:
    agent: Agent[None, BriefingDocReport] = Agent(
        _make_model(),
        result_type=BriefingDocReport,
        system_prompt=_BRIEFING_SYSTEM,
    )
    result = await agent.run(_build_user_message(context, additional_instructions))
    return result.data


async def generate_study_guide(
    context: str,
    additional_instructions: str | None = None,
) -> StudyGuideReport:
    agent: Agent[None, StudyGuideReport] = Agent(
        _make_model(),
        result_type=StudyGuideReport,
        system_prompt=_STUDY_GUIDE_SYSTEM,
    )
    result = await agent.run(_build_user_message(context, additional_instructions))
    return result.data


async def generate_blog_post(
    context: str,
    additional_instructions: str | None = None,
) -> BlogPostReport:
    agent: Agent[None, BlogPostReport] = Agent(
        _make_model(),
        result_type=BlogPostReport,
        system_prompt=_BLOG_SYSTEM,
    )
    result = await agent.run(_build_user_message(context, additional_instructions))
    return result.data


async def generate_custom_report(
    context: str,
    additional_instructions: str,
) -> CustomReport:
    """Custom reports treat additional_instructions as the entire core directive."""
    agent: Agent[None, CustomReport] = Agent(
        _make_model(),
        result_type=CustomReport,
        system_prompt=_CUSTOM_SYSTEM_BASE,
    )
    user_message = (
        f"USER REQUEST: {additional_instructions.strip()}\n\n"
        f"SOURCE MATERIAL:\n\n{context}"
    )
    result = await agent.run(user_message)
    return result.data
