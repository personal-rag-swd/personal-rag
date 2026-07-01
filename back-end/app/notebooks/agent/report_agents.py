from __future__ import annotations

import asyncio
from contextvars import ContextVar

import logfire
from pydantic_ai import Agent
from pydantic_ai.exceptions import ModelHTTPError
from pydantic_ai.models import Model
from pydantic_ai.run import AgentRunResult
from pydantic_ai.usage import RunUsage

from app.core.llm_provider import resolve_chat_provider
from app.notebooks.prompt import (
    BLOG_SYSTEM,
    BRIEFING_SYSTEM,
    CUSTOM_SYSTEM_BASE,
    FLASHCARDS_SYSTEM,
    MINDMAP_SYSTEM,
    QUIZ_SYSTEM,
    STUDY_GUIDE_SYSTEM,
    build_custom_report_user_message,
    build_flashcards_user_message,
    build_mindmap_user_message,
    build_quiz_user_message,
    build_report_user_message,
)
from app.notebooks.schemas import (
    BlogPostReport,
    BriefingDocReport,
    CustomReport,
    FlashcardItem,
    FlashcardReport,
    MindMapReport,
    QuizQuestion,
    QuizReport,
    StudyGuideReport,
)

# Statically defined report agents
briefing_agent = Agent(
    output_type=BriefingDocReport,
    instructions=BRIEFING_SYSTEM,
)

study_guide_agent = Agent(
    output_type=StudyGuideReport,
    instructions=STUDY_GUIDE_SYSTEM,
)

blog_agent = Agent(
    output_type=BlogPostReport,
    instructions=BLOG_SYSTEM,
)

custom_agent = Agent(
    output_type=CustomReport,
    instructions=CUSTOM_SYSTEM_BASE,
)

mindmap_agent = Agent(
    output_type=MindMapReport,
    instructions=MINDMAP_SYSTEM,
)

quiz_agent = Agent(
    output_type=QuizReport,
    instructions=QUIZ_SYSTEM,
)

flashcards_agent = Agent(
    output_type=FlashcardReport,
    instructions=FLASHCARDS_SYSTEM,
)


# Set by ``_run_agent_with_retry`` after each successful run and read by
# ``run_report_generation`` right after a ``generate_*`` call returns, so
# token usage is captured without threading a usage-sink parameter through
# every report-generation function's signature. Safe across ``await``s within
# the same task since contextvars propagate through the call stack.
_last_report_usage: ContextVar[RunUsage | None] = ContextVar(
    "_last_report_usage", default=None
)


def get_last_report_usage() -> RunUsage | None:
    """Return (and clear) the usage captured by the most recent report agent run."""
    usage = _last_report_usage.get()
    _last_report_usage.set(None)
    return usage


async def _run_agent_with_retry[OutputT](
    agent: Agent[None, OutputT],
    user_msg: str,
    model: Model,
    max_retries: int = 4,
    initial_delay: float = 2.0,
) -> AgentRunResult[OutputT]:
    delay = initial_delay
    for attempt in range(max_retries):
        try:
            result = await agent.run(user_msg, model=model)
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
        else:
            _last_report_usage.set(result.usage)
            return result
    raise RuntimeError("Model retry loop exited without a result")


async def generate_briefing_doc(
    context: str,
    additional_instructions: str | None = None,
) -> BriefingDocReport:
    model = resolve_chat_provider()
    result = await _run_agent_with_retry(
        briefing_agent,
        build_report_user_message(context, additional_instructions),
        model=model,
    )
    return result.output


async def generate_study_guide(
    context: str,
    additional_instructions: str | None = None,
) -> StudyGuideReport:
    model = resolve_chat_provider()
    result = await _run_agent_with_retry(
        study_guide_agent,
        build_report_user_message(context, additional_instructions),
        model=model,
    )
    return result.output


async def generate_blog_post(
    context: str,
    additional_instructions: str | None = None,
) -> BlogPostReport:
    model = resolve_chat_provider()
    result = await _run_agent_with_retry(
        blog_agent,
        build_report_user_message(context, additional_instructions),
        model=model,
    )
    return result.output


async def generate_custom_report(
    context: str,
    additional_instructions: str,
) -> CustomReport:
    """Custom reports treat additional_instructions as the entire core directive."""
    model = resolve_chat_provider()
    user_message = build_custom_report_user_message(context, additional_instructions)
    result = await _run_agent_with_retry(custom_agent, user_message, model=model)
    return result.output


async def generate_mindmap(
    context: str,
    detail_level: str | None = None,
    additional_instructions: str | None = None,
) -> MindMapReport:
    model = resolve_chat_provider()
    user_message = build_mindmap_user_message(
        context, detail_level, additional_instructions
    )
    result = await _run_agent_with_retry(mindmap_agent, user_message, model=model)
    return result.output


async def generate_quiz(
    context: str,
    count: int = 20,
    difficulty: str | None = None,
    additional_instructions: str | None = None,
) -> QuizReport:
    model = resolve_chat_provider()
    user_message = build_quiz_user_message(
        context, count, difficulty, additional_instructions
    )
    result = await _run_agent_with_retry(quiz_agent, user_message, model=model)
    return _sanitize_quiz(result.output)


def _sanitize_quiz(quiz: QuizReport) -> QuizReport:
    """Keep only well-formed questions so client-side scoring stays reliable.

    A question is valid only if it has exactly 4 options and a correct_index that
    points at one of them. Caps the quiz at 50 questions and raises if nothing
    valid remains (so the report is marked failed rather than silently empty).
    """
    valid: list[QuizQuestion] = []
    for q in quiz.questions:
        if not q.question.strip():
            continue
        options = [opt for opt in q.options if isinstance(opt, str) and opt.strip()]
        if len(options) != 4:
            continue
        if not 0 <= q.correct_index < len(options):
            continue
        valid.append(
            QuizQuestion(
                question=q.question.strip(),
                options=options,
                correct_index=q.correct_index,
                explanation=q.explanation.strip(),
            )
        )
        if len(valid) >= 50:
            break
    if not valid:
        raise ValueError("Quiz generation produced no valid multiple-choice questions")
    return QuizReport(questions=valid)


async def generate_flashcards(
    context: str,
    count: int = 20,
    difficulty: str | None = None,
    additional_instructions: str | None = None,
) -> FlashcardReport:
    model = resolve_chat_provider()
    user_message = build_flashcards_user_message(
        context, count, difficulty, additional_instructions
    )
    result = await _run_agent_with_retry(flashcards_agent, user_message, model=model)
    return _sanitize_flashcards(result.output)


def _sanitize_flashcards(deck: FlashcardReport) -> FlashcardReport:
    """Keep only cards that have a non-empty front and back; cap at 50.

    Raises if nothing valid remains so the report is marked failed rather than
    silently empty.
    """
    valid: list[FlashcardItem] = []
    for card in deck.cards:
        front = card.front.strip()
        back = card.back.strip()
        if not front or not back:
            continue
        valid.append(FlashcardItem(front=front, back=back))
        if len(valid) >= 50:
            break
    if not valid:
        raise ValueError("Flashcard generation produced no valid cards")
    return FlashcardReport(cards=valid)
