from pydantic_ai import Agent

from app.notebooks.agent.factory import resolve_chat_provider
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


def _build_user_message(context: str, additional_instructions: str | None) -> str:
    parts = [f"SOURCE MATERIAL:\n\n{context}"]
    if additional_instructions and additional_instructions.strip():
        parts.append(f"Additional User Requirements: {additional_instructions.strip()}")
    return "\n\n".join(parts)


async def generate_briefing_doc(
    context: str,
    additional_instructions: str | None = None,
) -> BriefingDocReport:
    agent = Agent(
        resolve_chat_provider().build_model(),
        output_type=BriefingDocReport,
        instructions=_BRIEFING_SYSTEM,
    )
    result = await agent.run(_build_user_message(context, additional_instructions))
    return result.output


async def generate_study_guide(
    context: str,
    additional_instructions: str | None = None,
) -> StudyGuideReport:
    agent = Agent(
        resolve_chat_provider().build_model(),
        output_type=StudyGuideReport,
        instructions=_STUDY_GUIDE_SYSTEM,
    )
    result = await agent.run(_build_user_message(context, additional_instructions))
    return result.output


async def generate_blog_post(
    context: str,
    additional_instructions: str | None = None,
) -> BlogPostReport:
    agent = Agent(
        resolve_chat_provider().build_model(),
        output_type=BlogPostReport,
        instructions=_BLOG_SYSTEM,
    )
    result = await agent.run(_build_user_message(context, additional_instructions))
    return result.output


async def generate_custom_report(
    context: str,
    additional_instructions: str,
) -> CustomReport:
    """Custom reports treat additional_instructions as the entire core directive."""
    agent = Agent(
        resolve_chat_provider().build_model(),
        output_type=CustomReport,
        instructions=_CUSTOM_SYSTEM_BASE,
    )
    user_message = (
        f"USER REQUEST: {additional_instructions.strip()}\n\n"
        f"SOURCE MATERIAL:\n\n{context}"
    )
    result = await agent.run(user_message)
    return result.output
