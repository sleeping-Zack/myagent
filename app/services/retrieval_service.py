from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import re
from typing import Any, Optional, cast
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

_SECTION_FOCUS_BOOST = 0.15


def _lexical_terms(text: str) -> list[str]:
    chinese = "".join(re.findall(r"[\u4e00-\u9fff]", text))
    terms = re.findall(
        r"[a-z][a-z0-9_-]{1,}|\d{4}(?:[./-]\d{1,2})?|\d+",
        text.lower(),
    )
    terms.extend(chinese[index:index + 2] for index in range(max(0, len(chinese) - 1)))
    counts = Counter(term for term in terms if term not in _LEXICAL_STOP_TERMS)
    return sorted(
        counts,
        key=lambda value: (-counts[value], -len(value), value),
    )[:32]


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
        quota = (
            min(2, max(1, plan.context_limit // max(1, len(plan.targets))))
            if plan.requires_complete_coverage
            else top_k
        )
        merged: dict[str, dict] = {}
        selected_documents: set[str] = set()
        target_queries = [
            target.query
            if target.query == question
            else (
                f"{target.query}\n{question}"
                if plan.intent in {"multi_part", "general"}
                else f"{question}\n{target.query}"
            )
            for target in plan.targets
        ]

        if len(plan.targets) > 1:
            embeddings = await self._embedding_svc.async_embed_documents(
                target_queries
            )
        else:
            embeddings = [
                await self._embedding_svc.async_embed_query(target_queries[0])
            ]

        for target, target_query, embedding in zip(plan.targets, target_queries, embeddings):
            project = project_by_slug.get(target.project_slug) if target.project_slug else None
            project_ids = [project.id] if project else None
            target_results = await self._retrieve_target(
                question=target_query,
                session=session,
                top_k=max(4, min(top_k, quota * 2)),
                min_score=min_score,
                project_ids=project_ids,
                project_slugs={value.id: value.slug for value in projects},
                section_terms=list(target.section_terms),
                embedding=embedding,
            )
            focused_results: list[dict] = []

            if target.section_terms:
                if plan.intent == "general" and target.query != question:
                    target_results = [
                        {
                            **result,
                            "score": round(
                                min(1.0, result["score"] + _SECTION_FOCUS_BOOST),
                                4,
                            ),
                        }
                        for result in target_results
                    ]
                focused_results = target_results
                broad_results = await self._retrieve_target(
                    question=target_query,
                    session=session,
                    top_k=max(4, min(top_k, quota * 2)),
                    min_score=min_score,
                    project_ids=project_ids,
                    project_slugs={value.id: value.slug for value in projects},
                    section_terms=None,
                    embedding=embedding,
                )
                combined_results = {
                    result["chunk_id"]: result for result in target_results
                }
                for result in broad_results:
                    current = combined_results.get(result["chunk_id"])
                    if current is None or result["score"] > current["score"]:
                        combined_results[result["chunk_id"]] = result
                target_results = sorted(
                    combined_results.values(),
                    key=lambda item: item["score"],
                    reverse=True,
                )

            # 存量数据尚未回填 project_id 时仍可按项目标题检索，避免部署窗口内完全无结果。
            if not target_results and project_ids:
                target_results = await self._retrieve_target(
                    question=target_query,
                    session=session,
                    top_k=max(4, min(top_k, quota * 2)),
                    min_score=min_score,
                    project_ids=None,
                    project_slugs={value.id: value.slug for value in projects},
                    section_terms=list(target.section_terms),
                    embedding=embedding,
                )
                focused_results = target_results

            selected_results = target_results[:quota]
            if plan.requires_complete_coverage:
                candidate_results = [
                    result
                    for result in target_results
                    if not result.get("document_id")
                    or result["document_id"] not in selected_documents
                ]
                if not candidate_results:
                    candidate_results = target_results
                selected_results = candidate_results[:quota]
                if focused_results:
                    focused_candidates = [
                        result
                        for result in focused_results
                        if not result.get("document_id")
                        or result["document_id"] not in selected_documents
                    ] or focused_results
                    selected_results = focused_candidates[:quota]
                    selected_ids = {
                        result["chunk_id"] for result in selected_results
                    }
                    selected_results.extend(
                        result
                        for result in candidate_results
                        if result["chunk_id"] not in selected_ids
                    )
                    selected_results = selected_results[:quota]

            for result in selected_results:
                if result.get("document_id"):
                    selected_documents.add(result["document_id"])
                chunk_id = result["chunk_id"]
                if chunk_id in merged:
                    merged[chunk_id]["coverage_keys"] = sorted(set(
                        merged[chunk_id]["coverage_keys"] + [target.coverage_key]
                    ))
                    merged[chunk_id]["score"] = max(merged[chunk_id]["score"], result["score"])
                    if any(
                        focused["chunk_id"] == chunk_id
                        for focused in focused_results
                    ):
                        merged[chunk_id]["_focused_coverage_keys"] = sorted(set(
                            merged[chunk_id].get("_focused_coverage_keys", [])
                            + [target.coverage_key]
                        ))
                    continue
                result["coverage_keys"] = [target.coverage_key]
                result["_focused_coverage_keys"] = (
                    [target.coverage_key]
                    if any(
                        focused["chunk_id"] == chunk_id
                        for focused in focused_results
                    )
                    else []
                )
                merged[chunk_id] = result

        if plan.requires_complete_coverage:
            synthesis_results = await self._retrieve_target(
                question=question,
                session=session,
                top_k=2,
                min_score=min_score,
                project_ids=None,
                project_slugs={value.id: value.slug for value in projects},
                section_terms=None,
                embedding=embeddings[0],
            )
            for result in synthesis_results:
                chunk_id = result["chunk_id"]
                if chunk_id in merged:
                    merged[chunk_id]["score"] = max(
                        merged[chunk_id]["score"], result["score"]
                    )
                    continue
                result["coverage_keys"] = []
                result["_focused_coverage_keys"] = []
                merged[chunk_id] = result

        ranked_chunks = sorted(merged.values(), key=lambda item: item["score"], reverse=True)
        unique_documents: list[dict] = []
        repeated_documents: list[dict] = []
        document_counts: dict[str, int] = {}
        for chunk in ranked_chunks:
            document_id = cast(Optional[str], chunk.get("document_id"))
            if not document_id:
                unique_documents.append(chunk)
                continue
            count = document_counts.get(document_id, 0)
            if count >= 2:
                continue
            document_counts[document_id] = count + 1
            if count == 0:
                unique_documents.append(chunk)
            else:
                repeated_documents.append(chunk)

        chunks = unique_documents + repeated_documents

        if plan.requires_complete_coverage:
            coverage_ordered: list[dict] = []
            remaining = list(chunks)
            while True:
                added = False
                for coverage_key in plan.expected_coverage:
                    candidate = next(
                        (
                            chunk
                            for chunk in remaining
                            if coverage_key
                            in chunk.get("_focused_coverage_keys", [])
                        ),
                        None,
                    ) or next(
                        (
                            chunk
                            for chunk in remaining
                            if coverage_key in chunk.get("coverage_keys", [])
                        ),
                        None,
                    )
                    if candidate is None:
                        continue
                    coverage_ordered.append(candidate)
                    remaining.remove(candidate)
                    added = True
                if not added:
                    break
            chunks = coverage_ordered + remaining

        if plan.intent == "multi_project":
            first_per_project: list[dict] = []
            repeated_projects: list[dict] = []
            seen_projects: set[str] = set()
            for chunk in chunks:
                project_slug = chunk.get("project_slug")
                if project_slug and project_slug not in seen_projects:
                    seen_projects.add(project_slug)
                    first_per_project.append(chunk)
                else:
                    repeated_projects.append(chunk)
            chunks = first_per_project + repeated_projects

        result_limit = plan.context_limit if plan.requires_complete_coverage else min(top_k, plan.context_limit)
        chunks = chunks[:result_limit]
        covered = {
            key
            for chunk in chunks
            for key in chunk.get("coverage_keys", [])
        }
        missing = [key for key in plan.expected_coverage if key not in covered]
        for chunk in chunks:
            chunk.pop("document_id", None)
            chunk.pop("_focused_coverage_keys", None)
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
        unique_documents: list[dict] = []
        repeated_documents: list[dict] = []
        document_counts: dict[str, int] = {}
        for result in results:
            document_id = result.get("document_id")
            if document_id:
                count = document_counts.get(document_id, 0)
                if count >= 2:
                    continue
                document_counts[document_id] = count + 1
                if count == 1:
                    repeated_documents.append(result)
                    continue
            unique_documents.append(result)
        return (unique_documents + repeated_documents)[:top_k]

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
