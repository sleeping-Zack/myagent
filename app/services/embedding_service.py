import asyncio
from typing import Optional
from functools import lru_cache
from openai import AsyncOpenAI
from app.core.config import settings


class EmbeddingService:
    def __init__(self) -> None:
        self._local_model = None
        self._api_client: Optional[AsyncOpenAI] = None

    # ── API 模式 ──────────────────────────────────────────────────────────────

    def _get_api_client(self) -> AsyncOpenAI:
        if self._api_client is None:
            self._api_client = AsyncOpenAI(
                api_key=settings.embedding_api_key,
                base_url=settings.embedding_api_base_url,
                timeout=settings.llm_timeout_seconds,
                max_retries=settings.llm_max_retries,
            )
        return self._api_client

    async def _api_embed_query(self, text: str) -> list[float]:
        client = self._get_api_client()
        resp = await client.embeddings.create(
            input=text,
            model=settings.embedding_api_model,
        )
        return resp.data[0].embedding

    async def _api_embed_documents(self, texts: list[str]) -> list[list[float]]:
        client = self._get_api_client()
        resp = await client.embeddings.create(
            input=texts,
            model=settings.embedding_api_model,
        )
        items = sorted(resp.data, key=lambda x: x.index)
        return [item.embedding for item in items]

    # ── 本地模式 ──────────────────────────────────────────────────────────────

    def _get_local_model(self):
        if self._local_model is None:
            from sentence_transformers import SentenceTransformer
            self._local_model = SentenceTransformer(
                settings.embedding_model_path,
                device=settings.embedding_device,
            )
        return self._local_model

    def _local_embed_query(self, text: str) -> list[float]:
        model = self._get_local_model()
        vec = model.encode(text, normalize_embeddings=True)
        return vec.tolist()

    def _local_embed_documents(self, texts: list[str]) -> list[list[float]]:
        model = self._get_local_model()
        vecs = model.encode(texts, normalize_embeddings=True, batch_size=32)
        return [v.tolist() for v in vecs]

    # ── 统一接口 ──────────────────────────────────────────────────────────────

    async def async_embed_query(self, text: str) -> list[float]:
        if settings.embedding_mode == "api":
            return await self._api_embed_query(text)
        return await asyncio.to_thread(self._local_embed_query, text)

    async def async_embed_documents(self, texts: list[str]) -> list[list[float]]:
        if settings.embedding_mode == "api":
            return await self._api_embed_documents(texts)
        return await asyncio.to_thread(self._local_embed_documents, texts)

    def is_configured(self) -> bool:
        if settings.embedding_mode == "api":
            return bool(
                settings.embedding_api_key
                and settings.embedding_api_base_url
                and settings.embedding_api_model
            )
        return bool(settings.embedding_model_path)


@lru_cache(maxsize=1)
def get_embedding_service() -> EmbeddingService:
    return EmbeddingService()
