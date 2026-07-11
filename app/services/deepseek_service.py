from typing import AsyncIterator, Optional
from openai import AsyncOpenAI
from app.core.config import settings


class DeepSeekService:
    def __init__(self) -> None:
        self._client = AsyncOpenAI(
            api_key=settings.deepseek_api_key,
            base_url=settings.deepseek_base_url,
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

    async def count_tokens(self, text: str) -> int:
        return len(text) // 4
