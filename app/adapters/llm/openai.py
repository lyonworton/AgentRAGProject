import json
from typing import AsyncIterator
from openai import AsyncOpenAI
from app.adapters.llm.base import BaseLLM
from app.core.config import get_settings
settings = get_settings()

class OpenAILLM(BaseLLM):
    def __init__(self):
        self.client = AsyncOpenAI(api_key=settings.openai_api_key, base_url=settings.openai_base_url)
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
        raw = await self.agenerate(prompt, full, **kwargs)
        raw = raw.strip()
        if raw.startswith("```"):
            parts = raw.split("\n", 1)
            raw = parts[1] if len(parts) > 1 else raw
            if raw.endswith("```"):
                raw = raw[:-3]
        return json.loads(raw)
