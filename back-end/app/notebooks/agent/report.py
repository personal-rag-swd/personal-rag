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
    MindMapReport,
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


_MINDMAP_SYSTEM = """
You are an expert knowledge engineer. Given source excerpts from a notebook, generate a comprehensive mind map that captures the core concepts and their structured relationships.

- central_topic: The core subject of the documents.
- nodes: A hierarchical list representing the knowledge tree:
  1. Root node: The central topic itself.
  2. Main branches: Major topics or categories directly connected to the root.
  3. Sub-branches: Detailed concepts or sub-topics nested under main branches.
  Each node must have a unique, short ID, a clear label (concept title), type ('root', 'main', or 'sub'), parent_id (pointing to its parent node), and a brief description/definition.
- relationships: Key relationships or cross-connections between concepts belonging to different branches (e.g., 'shares features with', 'opposes', 'is a prerequisite for').

Ensure the hierarchy corresponds to the requested level of detail:
- 'simple': Generate exactly 3-5 main branches and 5-10 sub-branches.
- 'intermediate': Generate exactly 5-8 main branches and 10-20 sub-branches.
- 'detailed': Generate exactly 8-12 main branches and 20-35 sub-branches.

Respond only with the structured JSON output. Do not fabricate information not present in the sources.
""".strip()


async def generate_mindmap(
    context: str,
    detail_level: str | None = None,
    additional_instructions: str | None = None,
) -> MindMapReport:
    agent = Agent(
        resolve_chat_provider().build_model(),
        output_type=MindMapReport,
        instructions=_MINDMAP_SYSTEM,
    )
    user_msg_parts = [f"SOURCE MATERIAL:\n\n{context}"]
    
    level = (detail_level or "intermediate").strip().lower()
    if level not in ("simple", "intermediate", "detailed"):
        level = "intermediate"
        
    user_msg_parts.append(f"Target Detail Level: {level.upper()}")
    
    if additional_instructions and additional_instructions.strip():
        user_msg_parts.append(f"Additional User Requirements: {additional_instructions.strip()}")
        
    result = await agent.run("\n\n".join(user_msg_parts))
    return result.output
