from __future__ import annotations

import asyncio
from typing import Any

import logfire
from pydantic_ai import Agent
from pydantic_ai.exceptions import ModelHTTPError
from pydantic_ai.run import AgentRunResult

from app.notebooks.agent.factory import resolve_chat_provider
from app.notebooks.prompt import (
    BLOG_SYSTEM,
    BRIEFING_SYSTEM,
    CUSTOM_SYSTEM_BASE,
    MINDMAP_SYSTEM,
    STUDY_GUIDE_SYSTEM,
    build_custom_report_user_message,
    build_mindmap_user_message,
    build_report_user_message,
)
from app.notebooks.schemas import (
    BlogPostReport,
    BriefingDocReport,
    CustomReport,
    MindMapReport,
    StudyGuideReport,
)


async def _run_agent_with_retry(
    agent: Agent,
    user_msg: str,
    max_retries: int = 4,
    initial_delay: float = 2.0,
) -> AgentRunResult[Any]:
    delay = initial_delay
    for attempt in range(max_retries):
        try:
            return await agent.run(user_msg)
        except ModelHTTPError as exc:
            if exc.status_code in (429, 502, 503, 500) and attempt < max_retries - 1:
                logfire.warning(
                    "Model HTTP error status_code={status_code} on attempt {attempt_num}. Retrying in {delay}s...",
                    status_code=exc.status_code,
                    attempt_num=attempt + 1,
                    delay=delay,
                )
                await asyncio.sleep(delay)
                delay *= 2
            else:
                raise
    raise RuntimeError("Model retry loop exited without a result")


async def generate_briefing_doc(
    context: str,
    additional_instructions: str | None = None,
) -> BriefingDocReport:
    agent = Agent(
        resolve_chat_provider().build_model(),
        output_type=BriefingDocReport,
        instructions=BRIEFING_SYSTEM,
    )
    result = await _run_agent_with_retry(
        agent, build_report_user_message(context, additional_instructions)
    )
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
    result = await _run_agent_with_retry(
        agent, build_report_user_message(context, additional_instructions)
    )
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
    result = await _run_agent_with_retry(
        agent, build_report_user_message(context, additional_instructions)
    )
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
    user_message = build_custom_report_user_message(context, additional_instructions)
    result = await _run_agent_with_retry(agent, user_message)
    return result.output


async def generate_mindmap(
    context: str,
    detail_level: str | None = None,
    additional_instructions: str | None = None,
) -> MindMapReport:
    agent = Agent(
        resolve_chat_provider().build_model(),
        output_type=MindMapReport,
        instructions=MINDMAP_SYSTEM,
    )
    user_message = build_mindmap_user_message(
        context, detail_level, additional_instructions
    )
    result = await _run_agent_with_retry(agent, user_message)
    return result.output
