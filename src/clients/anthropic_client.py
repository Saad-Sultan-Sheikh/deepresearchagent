"""Anthropic Claude client wrapper."""

from __future__ import annotations

from typing import Any, Type, TypeVar

from langchain_anthropic import ChatAnthropic
from pydantic import BaseModel

from src.config import get_settings

T = TypeVar("T", bound=BaseModel)


def get_anthropic_llm(temperature: float | None = None) -> ChatAnthropic:
    settings = get_settings()
    return ChatAnthropic(
        model=settings.analyzer_model,
        temperature=temperature if temperature is not None else settings.llm_temperature,
        api_key=settings.anthropic_api_key,
        max_tokens=4096,
    )


async def structured_completion(
    prompt_messages: list[dict[str, str]],
    output_schema: Type[T],
    temperature: float | None = None,
) -> T:
    """Call Claude with structured output."""
    settings = get_settings()
    llm = ChatAnthropic(
        model=settings.analyzer_model,
        temperature=temperature if temperature is not None else settings.llm_temperature,
        api_key=settings.anthropic_api_key,
        max_tokens=4096,
    ).with_structured_output(output_schema)

    from langchain_core.messages import HumanMessage, SystemMessage

    messages = []
    for msg in prompt_messages:
        if msg["role"] == "system":
            messages.append(SystemMessage(content=msg["content"]))
        else:
            messages.append(HumanMessage(content=msg["content"]))

    result = await llm.ainvoke(messages)
    return result  # type: ignore[return-value]


async def text_completion(
    prompt_messages: list[dict[str, str]],
    temperature: float | None = None,
) -> str:
    """Call Claude and return raw text response."""
    settings = get_settings()
    llm = ChatAnthropic(
        model=settings.analyzer_model,
        temperature=temperature if temperature is not None else settings.llm_temperature,
        api_key=settings.anthropic_api_key,
        max_tokens=4096,
    )

    from langchain_core.messages import HumanMessage, SystemMessage

    messages = []
    for msg in prompt_messages:
        if msg["role"] == "system":
            messages.append(SystemMessage(content=msg["content"]))
        else:
            messages.append(HumanMessage(content=msg["content"]))

    result = await llm.ainvoke(messages)
    return result.content  # type: ignore[return-value]
