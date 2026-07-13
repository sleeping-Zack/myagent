from functools import lru_cache
import math
import re
from typing import AsyncIterator, Optional
from openai import AsyncOpenAI
from app.core.config import settings


class DeepSeekService:
    def __init__(self) -> None:
        self._client = AsyncOpenAI(
            api_key=settings.deepseek_api_key,
            base_url=settings.deepseek_base_url,
            timeout=settings.llm_timeout_seconds,
            max_retries=settings.llm_max_retries,
        )

    async def stream_chat(
        self,
        messages: list[dict],
        model: Optional[str] = None,
    ) -> AsyncIterator[str]:
        effective_model = model or settings.deepseek_model
        stream = await self._client.chat.completions.create(
            model=effective_model,
            messages=messages,
            stream=True,
        )
        async for chunk in stream:
            delta = chunk.choices[0].delta
            if delta.content:
                yield delta.content

    def estimate_tokens(self, text: str) -> int:
        """Conservative display/logging estimate, not provider-billed usage."""
        cjk_count = len(re.findall(r"[\u3400-\u9fff]", text))
        non_cjk = re.sub(r"[\u3400-\u9fff]", " ", text)
        ascii_units = sum(
            max(1, math.ceil(len(unit) / 4))
            for unit in re.findall(r"\w+|[^\w\s]", non_cjk, re.UNICODE)
        )
        return cjk_count + ascii_units

    def is_configured(self) -> bool:
        return bool(settings.deepseek_api_key and settings.deepseek_model)


@lru_cache(maxsize=1)
def get_deepseek_service() -> DeepSeekService:
    return DeepSeekService()
