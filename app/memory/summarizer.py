import structlog
from app.core.llm_factory import get_llm

logger = structlog.get_logger()

SUMMARIZE_PROMPT = """You are a conversation summarizer. Combine the previous session summary with the new Q&A exchange into a concise updated summary.

Keep: key entities, relationships, conclusions, and context needed for future questions.
Drop: filler phrases, formatting instructions, search results, and low-value chitchat.

Previous summary: {old_summary}

New exchange:
Q: {query}
A: {answer[:800]}

Output ONLY the merged summary text (2-5 sentences). No JSON, no explanation."""


async def progressive_summarize(
    old_summary: str,
    query: str,
    answer: str,
) -> str:
    """Merge old summary with new Q&A via LLM to produce a progressive summary.

    Falls back to answer[:500] if LLM is unavailable.
    """
    if not answer:
        return old_summary or ""

    try:
        llm = get_llm()
        prompt = SUMMARIZE_PROMPT.format(
            old_summary=old_summary or "(no previous summary)",
            query=query[:300],
            answer=answer,
        )
        new_summary = await llm.agenerate(prompt, "You are a conversation summarizer.", max_tokens=200)
        return new_summary.strip() if new_summary else old_summary or answer[:500]
    except Exception:
        logger.warning("progressive_summarize_failed", exc_info=True)
        # Simple fallback: concatenate with truncation
        if old_summary:
            combined = f"{old_summary} | {answer[:300]}"
            return combined[:500]
        return answer[:500]