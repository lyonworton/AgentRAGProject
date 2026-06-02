import json
from typing import AsyncIterator
from langchain_ollama import ChatOllama
from langchain_core.messages import SystemMessage, HumanMessage
from app.adapters.llm.base import BaseLLM

class OllamaLLM(BaseLLM):
    def __init__(self, model="qwen2.5", base_url="http://localhost:11434"):
        self.llm = ChatOllama(model=model, base_url=base_url, temperature=0.0)

    async def agenerate(self, prompt, system_prompt="", **kwargs):
        msgs = []
        if system_prompt: msgs.append(SystemMessage(content=system_prompt))
        msgs.append(HumanMessage(content=prompt))
        resp = await self.llm.ainvoke(msgs)
        return resp.content

    async def astream(self, prompt, system_prompt="", **kwargs):
        msgs = []
        if system_prompt: msgs.append(SystemMessage(content=system_prompt))
        msgs.append(HumanMessage(content=prompt))
        async for chunk in self.llm.astream(msgs):
            if chunk.content: yield chunk.content

    async def agenerate_structured(self, prompt, system_prompt="", output_schema=None, **kwargs):
        full = system_prompt
        if output_schema: full += "\nValid JSON: " + json.dumps(output_schema)
        raw = await self.agenerate(prompt, full, **kwargs)
        raw = raw.strip()
        if raw.startswith("```"):
            parts = raw.split("\n", 1)
            raw = parts[1] if len(parts) > 1 else raw
            if raw.endswith("```"): raw = raw[:-3]
        return json.loads(raw)
