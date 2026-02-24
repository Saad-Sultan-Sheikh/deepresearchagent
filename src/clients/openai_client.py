"""OpenAI GPT-4o client wrapper."""

from __future__ import annotations

from typing import Any, Type, TypeVar

from langchain_openai import ChatOpenAI
from pydantic import BaseModel

from src.config import get_settings

T = TypeVar("T", bound=BaseModel)


_OPENAI_MODEL = "gpt-4o"


def get_openai_llm(temperature: float | None = None) -> ChatOpenAI:
    settings = get_settings()
    return ChatOpenAI(
        model=_OPENAI_MODEL,
        temperature=temperature if temperature is not None else settings.llm_temperature,
        api_key=settings.openai_api_key,
    )


async def structured_completion(
    prompt_messages: list[dict[str, str]],
    output_schema: Type[T],
    temperature: float | None = None,
) -> T:
    """Call GPT-4o with structured output (JSON schema enforced)."""
    settings = get_settings()
    llm = ChatOpenAI(
        model=_OPENAI_MODEL,
        temperature=temperature if temperature is not None else settings.llm_temperature,
        api_key=settings.openai_api_key,
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
