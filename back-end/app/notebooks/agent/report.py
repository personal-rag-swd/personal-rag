from pydantic_ai import Agent

from app.notebooks.agent.factory import resolve_chat_provider
from app.notebooks.prompt import (
    BLOG_SYSTEM,
    BRIEFING_SYSTEM,
    CUSTOM_SYSTEM_BASE,
    STUDY_GUIDE_SYSTEM,
)
from app.notebooks.schemas import (
    BlogPostReport,
    BriefingDocReport,
    CustomReport,
    StudyGuideReport,
)


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
        instructions=BRIEFING_SYSTEM,
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
        instructions=STUDY_GUIDE_SYSTEM,
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
        instructions=BLOG_SYSTEM,
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
        instructions=CUSTOM_SYSTEM_BASE,
    )
    user_message = (
        f"USER REQUEST: {additional_instructions.strip()}\n\n"
        f"SOURCE MATERIAL:\n\n{context}"
    )
    result = await agent.run(user_message)
    return result.output
