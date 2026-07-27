from __future__ import annotations

from time import sleep
from typing import Type
import os
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel
from ..alerts import slack_alert


LLM_MODEL_NAME = "gpt-5-mini"


class LLMClient:
    """Wrapper around ChatOpenAI with retry and structured output."""

    def __init__(self, model_name: str = LLM_MODEL_NAME, retries: int = 2, api_key=None, key_label: str = ""):
        self.llm = ChatOpenAI(model=model_name, api_key=api_key)
        self.retries = retries
        self.key_label = key_label

    def _call_with_retry(self, llm_fn, messages, retries: int | None = None):
        if retries is None:
            retries = self.retries
        try:
            return llm_fn.invoke(messages)
        except Exception as exc:  # pragma: no cover - network errors
            if retries <= 0:
                if type(exc).__name__ == "RateLimitError":
                    label = f" [{self.key_label}]" if self.key_label else ""
                    slack_alert(
                        f":rotating_light: *LLM call failed{label}*\n"
                        f"*Type:* `{type(exc).__name__}`\n"
                        f"*Error:* {str(exc)[:300]}",
                        cooldown_key=f"llm_failure_{self.key_label or 'default'}",
                    )
                raise
            sleep(5)
            return self._call_with_retry(llm_fn, messages, retries - 1)

    def generate(self, content: str, schema: Type[BaseModel], need_token_data: bool = False):
        structured_llm = self.llm.with_structured_output(schema, include_raw=need_token_data)
        messages = [SystemMessage(content=content), HumanMessage(content=" ")]
        res = self._call_with_retry(structured_llm, messages)
        if need_token_data:
            return res["parsed"], res["raw"].response_metadata
        return res
