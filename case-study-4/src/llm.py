"""
Gemini access layer: a bounded tool-calling (ReAct-style) loop used by
the tool-using workers, plus a structured-output helper used at every
handoff boundary. Retries wrap every live call (NFR-04); offline-mode
signaling lets each node fall back to a deterministic heuristic without
crashing (graceful degradation).
"""

from __future__ import annotations

import logging

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from pydantic import BaseModel
from tenacity import retry, stop_after_attempt, wait_exponential

from src.config import has_gemini_key, load_config

logger = logging.getLogger("copilot.llm")


def get_chat_model():
    from langchain_google_genai import ChatGoogleGenerativeAI

    cfg = load_config()["generation"]
    return ChatGoogleGenerativeAI(model=cfg["model"], temperature=cfg["temperature"])


async def run_tool_calling_agent(
    tools: list,
    system_prompt: str,
    human_content: str,
    max_iterations: int = 4,
) -> tuple[list, list[str]]:
    """Bounded ReAct-style loop: the model decides, turn by turn, which
    (if any) tools to call, until it stops calling tools or the
    iteration budget runs out. Returns (full_message_transcript,
    tool_names_called)."""
    cfg = load_config()["generation"]
    tools_by_name = {t.name: t for t in tools}
    llm = get_chat_model().bind_tools(tools) if tools else get_chat_model()

    messages: list = [SystemMessage(content=system_prompt), HumanMessage(content=human_content)]
    tools_called: list[str] = []

    @retry(
        stop=stop_after_attempt(cfg["max_retries"]),
        wait=wait_exponential(multiplier=cfg["retry_backoff_seconds"]),
        reraise=True,
    )
    async def _invoke(msgs: list) -> AIMessage:
        return await llm.ainvoke(msgs)

    for _ in range(max_iterations):
        response = await _invoke(messages)
        messages.append(response)

        tool_calls = getattr(response, "tool_calls", None) or []
        if not tool_calls:
            break

        for call in tool_calls:
            tool = tools_by_name.get(call["name"])
            if tool is None:
                result = f"Error: unknown tool {call['name']}"
            else:
                try:
                    result = await tool.ainvoke(call["args"])
                except Exception as exc:  # noqa: BLE001 - tool failure must not crash the loop
                    logger.warning("Tool %s failed: %s", call["name"], exc)
                    result = f"Error calling {call['name']}: {exc}"
            tools_called.append(call["name"])
            messages.append(ToolMessage(content=str(result), tool_call_id=call["id"]))

    return messages, tools_called


async def structured_extract(schema: type[BaseModel], system_prompt: str, content: str) -> BaseModel:
    """Asks Gemini to produce a validated instance of `schema`. Raises on
    failure so the caller can fall back."""
    cfg = load_config()["generation"]
    llm = get_chat_model().with_structured_output(schema)

    @retry(
        stop=stop_after_attempt(cfg["max_retries"]),
        wait=wait_exponential(multiplier=cfg["retry_backoff_seconds"]),
        reraise=True,
    )
    async def _invoke():
        result = await llm.ainvoke([SystemMessage(content=system_prompt), HumanMessage(content=content)])
        return result if isinstance(result, schema) else schema.model_validate(result)

    return await _invoke()


def gemini_available() -> bool:
    return has_gemini_key()
