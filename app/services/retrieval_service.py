from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any
from sqlalchemy.ext.asyncio import AsyncSession
from app.repositories.chunk_repository import ChunkRepository
from app.repositories.project_repository import ProjectRepository
from app.services.embedding_service import EmbeddingService
from app.services.query_planner import QueryPlan, plan_question

_PROJECT_ALIASES = {
    "面向智能硬件客服场景的可治理agent平台": (
        "面向智能硬件客服场景的可治理agent平台",
        "智能硬件客服",
        "可治理agent平台",
        "agentproject",
    ),
    "法奥机器人": ("法奥", "法奥机器人", "farino", "aiflowy"),
    "个人招聘知识agent": ("个人agent", "招聘知识agent", "myagent", "本站"),
    "情绪分析日记": ("情绪分析", "心情助手", "moodtracker", "mood tracker"),
}


def _normalize(text: str) -> str:
    return re.sub(r"[^0-9a-z\u4e00-\u9fff]+", "", text.lower())


def _cjk_bigrams(text: str) -> set[str]:
    chinese = "".join(re.findall(r"[\u4e00-\u9fff]", text))
    return {chinese[i:i + 2] for i in range(max(0, len(chinese) - 1))}


_LEXICAL_STOP_TERMS = {
    "请问", "请列", "列出", "所有", "全部", "可以", "可用", "什么", "哪些",
    "怎么", "如何", "一下", "介绍", "分别", "以及", "还有", "他的", "你的",
}


def _lexical_terms(text: str) -> list[str]:
    terms = set(re.findall(r"[a-z][a-z0-9_-]{1,}", text.lower()))
    terms.update(_cjk_bigrams(text))
    terms.difference_update(_LEXICAL_STOP_TERMS)
    return sorted(terms, key=lambda value: (-len(value), value))[:12]


@dataclass
class RetrievalOutcome:
    chunks: list[dict]
    plan: QueryPlan
    missing_coverage: list[str]
    direct_answer: str | None = None


class RetrievalService:
    def __init__(
        self,
        chunk_repo: ChunkRepository,
        embedding_svc: EmbeddingService,
        project_repo: ProjectRepository | None = None,
    ) -> None:
        self._chunk_repo = chunk_repo
        self._embedding_svc = embedding_svc
        self._project_repo = project_repo or ProjectRepository()

    async def retrieve(
        self,
        question: str,
        session: AsyncSession,
        top_k: int = 10,
        min_score: float = 0.40,
    ) -> list[dict]:
        outcome = await self.retrieve_with_plan(
            question=question,
            session=session,
            top_k=top_k,
            min_score=min_score,
        )
        return outcome.chunks

    async def retrieve_with_plan(
        self,
        question: str,
        session: AsyncSession,
        top_k: int = 10,
        min_score: float = 0.40,
    ) -> RetrievalOutcome:
        projects = await self._project_repo.get_all_public(session)
        plan = plan_question(question, projects)

        if plan.intent == "project_list":
            lines = [f"{index}. {project.title}" for index, project in enumerate(projects, 1)]
            content = "\n".join(lines) if lines else "当前没有公开项目。"
            answer = (
                f"目前公开展示的项目共 {len(projects)} 个：\n\n{content}"
                if projects else "当前没有公开展示的项目。"
            )
            chunk = {
                "chunk_id": "structured-project-list",
                "title": "公开项目列表",
                "section": "项目名称",
                "content": content,
                "score": 1.0,
                "tags": ["project", "structured"],
                "project_id": None,
                "project_slug": None,
                "coverage_keys": ["project_list"],
            }
            return RetrievalOutcome([chunk], plan, [], answer)

        project_by_slug = {project.slug: project for project in projects}
        quota = 1 if plan.requires_complete_coverage else top_k
        merged: dict[str, dict] = {}

        if len(plan.targets) > 1:
            embeddings = await self._embedding_svc.async_embed_documents(
                [target.query for target in plan.targets]
            )
        else:
            embeddings = [
                await self._embedding_svc.async_embed_query(plan.targets[0].query)
            ]

        for target, embedding in zip(plan.targets, embeddings):
            project = project_by_slug.get(target.project_slug) if target.project_slug else None
            project_ids = [project.id] if project else None
            target_results = await self._retrieve_target(
                question=target.query,
                session=session,
                top_k=max(4, min(top_k, quota * 2)),
                min_score=min_score,
                project_ids=project_ids,
                project_slugs={value.id: value.slug for value in projects},
                section_terms=list(target.section_terms),
                embedding=embedding,
            )

            if not target_results and target.section_terms:
                target_results = await self._retrieve_target(
                    question=target.query,
                    session=session,
                    top_k=max(4, min(top_k, quota * 2)),
                    min_score=min_score,
                    project_ids=project_ids,
                    project_slugs={value.id: value.slug for value in projects},
                    section_terms=None,
                    embedding=embedding,
                )

            # 存量数据尚未回填 project_id 时仍可按项目标题检索，避免部署窗口内完全无结果。
            if not target_results and project_ids:
                target_results = await self._retrieve_target(
                    question=target.query,
                    session=session,
                    top_k=max(4, min(top_k, quota * 2)),
                    min_score=min_score,
                    project_ids=None,
                    project_slugs={value.id: value.slug for value in projects},
                    section_terms=list(target.section_terms),
                    embedding=embedding,
                )

            for result in target_results[:quota]:
                chunk_id = result["chunk_id"]
                if chunk_id in merged:
                    merged[chunk_id]["coverage_keys"] = sorted(set(
                        merged[chunk_id]["coverage_keys"] + [target.coverage_key]
                    ))
                    merged[chunk_id]["score"] = max(merged[chunk_id]["score"], result["score"])
                    continue
                result["coverage_keys"] = [target.coverage_key]
                merged[chunk_id] = result

        chunks = sorted(merged.values(), key=lambda item: item["score"], reverse=True)
        result_limit = plan.context_limit if plan.requires_complete_coverage else min(top_k, plan.context_limit)
        chunks = chunks[:result_limit]
        covered = {
            key
            for chunk in chunks
            for key in chunk.get("coverage_keys", [])
        }
        missing = [key for key in plan.expected_coverage if key not in covered]
        return RetrievalOutcome(chunks, plan, missing)

    async def _retrieve_target(
        self,
        question: str,
        session: AsyncSession,
        top_k: int,
        min_score: float,
        project_ids: list | None,
        project_slugs: dict,
        section_terms: list[str] | None,
        embedding: list[float],
    ) -> list[dict]:
        raw_chunks = await self._chunk_repo.search_similar(
            session=session,
            embedding=embedding,
            top_k=top_k * 2,
            visibility="public",
            confidence_levels=["confirmed", "self_reported"],
            project_ids=project_ids,
            section_terms=section_terms,
        )

        lexical_chunks = await self._chunk_repo.search_lexical(
            session=session,
            terms=_lexical_terms(question),
            top_k=top_k * 2,
            visibility="public",
            confidence_levels=["confirmed", "self_reported"],
            project_ids=project_ids,
            section_terms=section_terms,
        )

        candidates: dict[str, dict] = {}
        for rank, (chunk, cosine_distance) in enumerate(raw_chunks, 1):
            candidates[str(chunk.id)] = {
                "chunk": chunk,
                "vector_score": max(0.0, min(1.0, 1.0 - cosine_distance)),
                "vector_rank": rank,
                "lexical_score": 0.0,
                "lexical_rank": None,
            }
        for rank, (chunk, lexical_score) in enumerate(lexical_chunks, 1):
            candidate = candidates.setdefault(str(chunk.id), {
                "chunk": chunk,
                "vector_score": 0.0,
                "vector_rank": None,
                "lexical_score": 0.0,
                "lexical_rank": None,
            })
            candidate["lexical_score"] = lexical_score
            candidate["lexical_rank"] = rank

        results: list[dict] = []
        for candidate in candidates.values():
            chunk = candidate["chunk"]
            base_score = max(candidate["vector_score"], candidate["lexical_score"] * 0.85)
            final_score = self._score(base_score, chunk, question)
            if candidate["vector_rank"] and candidate["lexical_rank"]:
                rrf = (
                    1 / (60 + candidate["vector_rank"])
                    + 1 / (60 + candidate["lexical_rank"])
                ) / (2 / 61)
                final_score = min(1.0, final_score + rrf * 0.04)
            if final_score >= min_score:
                results.append({
                    "chunk_id": str(chunk.id),
                    "document_id": str(chunk.document_id) if chunk.document_id else None,
                    "title": chunk.title,
                    "section": chunk.section,
                    "content": chunk.content,
                    "score": round(final_score, 4),
                    "tags": chunk.tags or [],
                    "project_id": str(chunk.project_id) if chunk.project_id else None,
                    "project_slug": project_slugs.get(chunk.project_id),
                })

        results.sort(key=lambda x: x["score"], reverse=True)
        deduplicated: list[dict] = []
        document_counts: dict[str, int] = {}
        for result in results:
            document_id = result.pop("document_id")
            if document_id:
                count = document_counts.get(document_id, 0)
                if count >= 2:
                    continue
                document_counts[document_id] = count + 1
            deduplicated.append(result)
        return deduplicated[:top_k]

    def _score(self, vector_score: float, chunk: Any, question: str) -> float:
        q_lower = question.lower()
        title_lower = (chunk.title or "").lower()
        q_normalized = _normalize(question)
        title_normalized = _normalize(title_lower)

        alias_match = any(
            any(_normalize(alias) in q_normalized for alias in aliases)
            and _normalize(canonical) in title_normalized
            for canonical, aliases in _PROJECT_ALIASES.items()
        )
        ngram_overlap = _cjk_bigrams(question).intersection(_cjk_bigrams(title_lower))
        title_match = 1.0 if alias_match or len(ngram_overlap) >= 2 else 0.0

        tags: list[str] = chunk.tags or []
        tag_match = 0.0
        for tag in tags:
            normalized_tag = _normalize(tag)
            if normalized_tag and normalized_tag in q_normalized:
                tag_match = 1.0
                break

        # project_match: 有 project_id 且问题提到项目相关词
        project_keywords = ["项目", "project", "经历", "实习", "开发"]
        project_match = 1.0 if chunk.project_id and any(k in q_lower for k in project_keywords) else 0.0

        return min(
            1.0,
            vector_score
            + title_match * 0.10
            + tag_match * 0.10
            + project_match * 0.05,
        )
