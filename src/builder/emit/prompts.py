"""Prompts for the Emit phase."""

TRIGGER_DESC_SYSTEM = (
    "You write Claude Code skill 'description' fields that trigger reliably. "
    "Skills tend to under-trigger by default, so descriptions must be slightly "
    "pushy: include both what the skill does AND specific contexts when to use "
    "it. The output is one paragraph, plain text, no markdown. Maximum ~120 words."
)


def trigger_desc_prompt(skill_name: str, dominant_topics: list[str]) -> str:
    topics = ", ".join(dominant_topics) if dominant_topics else "various concepts"
    return (
        f"Generate a triggering description for the skill `{skill_name}`. "
        f"The skill answers questions and supports brainstorming about: {topics}. "
        f"Include concrete example phrases that should trigger the skill (e.g., "
        f"'questions about X', 'when the user wants to understand Y'). "
        f"Return the description as plain text, one paragraph."
    )
