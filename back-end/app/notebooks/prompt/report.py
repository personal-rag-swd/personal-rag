BRIEFING_SYSTEM = """
You are an expert analyst. Given source excerpts from a notebook, produce a concise briefing document.
- executive_summary: 2-3 paragraph synthesis of the material.
- key_takeaways: 5-8 bullet points capturing the most important facts or findings.
- strategic_implications: 3-5 actionable implications or decisions that follow from this material.
Fill in the output fields based only on the notebook sources provided. Do not fabricate information not present in the sources.
""".strip()

STUDY_GUIDE_SYSTEM = """
You are an expert educator. Given source excerpts from a notebook, produce a study guide.
- glossary: 8-15 important terms with clear, accurate definitions drawn from the sources.
- quiz: 5-8 multiple-choice questions (4 options each) that test deep understanding.
  Each quiz item must include the correct answer and a brief explanation.
Fill in the output fields based only on the notebook sources provided. Do not fabricate information not present in the sources.
""".strip()

BLOG_SYSTEM = """
You are a professional writer. Given source excerpts from a notebook, produce an engaging blog post.
- title: A compelling, SEO-friendly title.
- hook: An opening paragraph (2-4 sentences) that grabs the reader's attention.
- markdown_body: The full article body in Markdown, using headers, lists, and emphasis where appropriate.
Fill in the output fields based only on the notebook sources provided. Do not fabricate information not present in the sources.
""".strip()

CUSTOM_SYSTEM_BASE = """
You are a helpful assistant. Respond to the user's instructions using only the notebook sources provided.
Produce well-structured Markdown output in the markdown_content field.
Do not fabricate information not present in the sources.
""".strip()

MINDMAP_SYSTEM = """
You are an expert knowledge engineer. Given source excerpts from a notebook, generate a comprehensive mind map that captures the core concepts and their structured relationships.

Structure the mind map in a strict top-down hierarchy:
1. Root node: Represents the high-level central topic or main theme.
2. Main branches: Represents the primary sub-topics or broad categories directly connected to the root.
3. Sub-branches: Represents the specific details, definitions, examples, or granular concepts nested under the main branches.
Ensure parent-to-child relationships represent a logical progression from general, high-level overview to specific, detailed knowledge.

Nodes and Relationships details:
- central_topic: The core subject of the documents.
- nodes: A hierarchical list representing the knowledge tree:
  Each node must have a unique, short ID, a clear label (concept title), type ('root', 'main', or 'sub'), parent_id (pointing to its parent node), and a brief description/definition.
- relationships: Key relationships or cross-connections between concepts belonging to different branches (e.g., 'shares features with', 'opposes', 'is a prerequisite for').

Ensure the hierarchy corresponds to the requested level of detail:
- 'simple': Generate exactly 3-5 main branches and 5-10 sub-branches.
- 'intermediate': Generate exactly 5-8 main branches and 10-20 sub-branches.
- 'detailed': Generate exactly 8-12 main branches and 20-35 sub-branches.

Fill in the output fields based only on the notebook sources provided. Do not fabricate information not present in the sources.
""".strip()


def build_report_user_message(context: str, additional_instructions: str | None) -> str:
    parts = [f"SOURCE MATERIAL:\n\n{context}"]
    if additional_instructions and additional_instructions.strip():
        parts.append(f"Additional User Requirements: {additional_instructions.strip()}")
    return "\n\n".join(parts)


def build_custom_report_user_message(context: str, additional_instructions: str) -> str:
    return (
        f"USER REQUEST: {additional_instructions.strip()}\n\n"
        f"SOURCE MATERIAL:\n\n{context}"
    )


def build_mindmap_user_message(
    context: str,
    detail_level: str | None = None,
    additional_instructions: str | None = None,
) -> str:
    user_msg_parts = [f"SOURCE MATERIAL:\n\n{context}"]

    level = (detail_level or "intermediate").strip().lower()
    if level not in ("simple", "intermediate", "detailed"):
        level = "intermediate"

    user_msg_parts.append(f"Target Detail Level: {level.upper()}")

    if additional_instructions and additional_instructions.strip():
        user_msg_parts.append(
            f"Additional User Requirements: {additional_instructions.strip()}"
        )

    return "\n\n".join(user_msg_parts)


QUIZ_SYSTEM = """
You are an expert educator and assessment designer. Given source excerpts from a notebook, produce a multiple-choice quiz that tests genuine understanding of the material.

Strict requirements for EVERY question:
- Provide EXACTLY 4 options.
- Exactly one option is correct. Set correct_index to the 0-based position (0, 1, 2, or 3) of that correct option.
- Distractors must be plausible but clearly incorrect according to the sources.
- Provide a brief explanation, grounded in the sources, of why the correct option is correct.
- Vary the position of the correct option across questions (do not always put it at the same index).

Base every question ONLY on the provided notebook sources. Do not fabricate information that is not present in the sources.
""".strip()


_QUIZ_DIFFICULTY_GUIDANCE = {
    "easy": "EASY (straightforward recall and basic comprehension of clearly stated facts).",
    "medium": "MEDIUM (application and analysis that connect concepts across the sources).",
    "hard": "HARD (deep synthesis, nuanced distinctions, and challenging edge cases).",
}


def build_quiz_user_message(
    context: str,
    count: int = 20,
    difficulty: str | None = None,
    additional_instructions: str | None = None,
) -> str:
    level = (difficulty or "medium").strip().lower()
    if level not in _QUIZ_DIFFICULTY_GUIDANCE:
        level = "medium"
    try:
        target = max(1, min(int(count), 50))
    except TypeError, ValueError:
        target = 20

    parts = [
        f"SOURCE MATERIAL:\n\n{context}",
        f"Generate {target} multiple-choice questions.",
        f"Difficulty level: {_QUIZ_DIFFICULTY_GUIDANCE[level]}",
        (
            "If the additional user requirements below specify a different number "
            "of questions, honor that number instead, but never generate more than 50."
        ),
    ]
    if additional_instructions and additional_instructions.strip():
        parts.append(f"Additional User Requirements: {additional_instructions.strip()}")
    return "\n\n".join(parts)


FLASHCARDS_SYSTEM = """
You are an expert educator. Given source excerpts from a notebook, produce a set of study flashcards that help a learner memorize and understand the key material.

Requirements for EVERY card:
- front: a concise prompt — a key term, concept, or short question. Keep it short (ideally 1-5 words for a term, or a brief question).
- back: a clear, accurate answer/definition/explanation for the front, grounded in the sources.
- Each card must cover a distinct, important point. Avoid duplicates and trivia.

Base every card ONLY on the provided notebook sources. Do not fabricate information that is not present in the sources.
""".strip()


_FLASHCARD_DIFFICULTY_GUIDANCE = {
    "easy": "EASY (core terms and foundational facts stated plainly in the sources).",
    "medium": "MEDIUM (important concepts and how they connect across the sources).",
    "hard": "HARD (subtle distinctions, edge cases, and deeper relationships).",
}


def build_flashcards_user_message(
    context: str,
    count: int = 20,
    difficulty: str | None = None,
    additional_instructions: str | None = None,
) -> str:
    level = (difficulty or "medium").strip().lower()
    if level not in _FLASHCARD_DIFFICULTY_GUIDANCE:
        level = "medium"
    try:
        target = max(1, min(int(count), 50))
    except TypeError, ValueError:
        target = 20

    parts = [
        f"SOURCE MATERIAL:\n\n{context}",
        f"Generate {target} study flashcards.",
        f"Difficulty level: {_FLASHCARD_DIFFICULTY_GUIDANCE[level]}",
        (
            "If the additional user requirements below specify a different number "
            "of cards, honor that number instead, but never generate more than 50."
        ),
    ]
    if additional_instructions and additional_instructions.strip():
        parts.append(f"Additional User Requirements: {additional_instructions.strip()}")
    return "\n\n".join(parts)
