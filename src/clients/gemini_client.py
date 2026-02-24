"""Google Gemini 1.5 Pro client wrapper."""

from __future__ import annotations

from typing import Type, TypeVar

from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel

from src.config import get_settings

T = TypeVar("T", bound=BaseModel)


def get_gemini_llm(temperature: float | None = None) -> ChatGoogleGenerativeAI:
    settings = get_settings()
    return ChatGoogleGenerativeAI(
        model=settings.extractor_model,
        temperature=temperature if temperature is not None else settings.llm_temperature,
        google_api_key=settings.google_api_key,
    )


async def structured_completion(
    prompt_messages: list[dict[str, str]],
    output_schema: Type[T],
    temperature: float | None = None,
) -> T:
    """Call Gemini with structured output."""
    settings = get_settings()
    llm = ChatGoogleGenerativeAI(
        model=settings.extractor_model,
        temperature=temperature if temperature is not None else settings.llm_temperature,
        google_api_key=settings.google_api_key,
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
