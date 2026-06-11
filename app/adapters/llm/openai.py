import json, re, structlog
from typing import AsyncIterator
from openai import AsyncOpenAI
import httpx
from app.adapters.llm.base import BaseLLM
from app.core.config import get_settings
settings = get_settings()

logger = structlog.get_logger()


def _clean_json(raw: str) -> str:
    """Remove markdown fences and strip control characters from JSON."""
    raw = raw.strip()
    if raw.startswith("```"):
        parts = raw.split("\n", 1)
        raw = parts[1] if len(parts) > 1 else raw
        if raw.endswith("```"):
            raw = raw[:-3]
    # Remove common problematic control characters except \n and \t
    raw = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", raw)
    return raw.strip()


class OpenAILLM(BaseLLM):
    def __init__(self):
        self.client = AsyncOpenAI(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
            timeout=httpx.Timeout(60.0, connect=10.0),
        )
        self.model = settings.llm_model

    async def agenerate(self, prompt, system_prompt="", **kwargs):
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        resp = await self.client.chat.completions.create(
            model=self.model, messages=messages,
            temperature=kwargs.get("temperature", 0.0),
            max_tokens=kwargs.get("max_tokens", 2048),
        )
        return resp.choices[0].message.content or ""

    async def astream(self, prompt, system_prompt="", **kwargs):
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        stream = await self.client.chat.completions.create(
            model=self.model, messages=messages,
            temperature=kwargs.get("temperature", 0.0),
            max_tokens=kwargs.get("max_tokens", 2048), stream=True,
        )
        async for chunk in stream:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    async def agenerate_structured(self, prompt, system_prompt="", output_schema=None, **kwargs):
        full = system_prompt
        if output_schema:
            full += "\nValid JSON: " + json.dumps(output_schema)

        last_error = None
        for attempt in range(3):
            raw = await self.agenerate(prompt, full, max_tokens=kwargs.get("max_tokens", 2048))
            raw = _clean_json(raw)
            try:
                return json.loads(raw)
            except json.JSONDecodeError as e:
                last_error = e
                # Heuristic repair: try to find the outermost {} or []
                if attempt == 0:
                    m = re.search(r"\{.*\}", raw, re.DOTALL) or re.search(r"\[.*\]", raw, re.DOTALL)
                    if m:
                        try:
                            return json.loads(m.group())
                        except json.JSONDecodeError:
                            pass
                logger.warning("json_parse_retry", attempt=attempt, error=str(e)[:100])
                # Add repair instruction for retry
                prompt = f"{prompt}\n\nCRITICAL: Your previous output was invalid JSON. Output ONLY valid JSON — escape all quotes inside strings, use \\n for newlines, no control characters."

        raise ValueError(f"Failed to parse structured output after 3 attempts: {last_error}")
