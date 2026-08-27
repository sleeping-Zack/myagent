"""Run the frozen RAG retrieval benchmark and write a reproducible report."""
# ruff: noqa: E402

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import math
import re
import subprocess
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any, Iterable
from uuid import UUID

from sqlalchemy import func, select

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.config import settings
from app.core.database import AsyncSessionLocal, engine
from app.core.security import is_safe_question
from app.models.chunk import DocumentChunk
from app.models.document import Document
from app.repositories.chunk_repository import ChunkRepository
from app.services.citation_service import CitationService
from app.services.embedding_service import get_embedding_service
from app.services.retrieval_service import RetrievalOutcome, RetrievalService


DEFAULT_SET = ROOT / "tests" / "rag_golden_set.json"
DEFAULT_OUTPUT = ROOT / "static" / "evaluation" / "latest.json"
EVALUATION_CUTOFF = 5
ALLOWED_BEHAVIORS = {"evidence", "direct_answer", "abstain", "protected"}
ALLOWED_DIFFICULTIES = {"easy", "medium", "hard"}
ALLOWED_INTENTS = {
    "project_list",
    "multi_project",
    "multi_part",
    "single_project",
    "general",
}
DEFAULT_QUALITY_GATES = {
    "hit_rate_at_5": 0.85,
    "mrr_at_5": 0.75,
    "ndcg_at_5": 0.75,
    "evidence_coverage_at_5": 0.80,
    "planner_intent_accuracy": 0.90,
    "evidence_decision_f1": 0.85,
    "knowledge_boundary_accuracy": 0.80,
    "task_success_rate": 0.80,
    "unsupported_answer_rate": 0.10,
    "benign_query_allow_rate": 0.98,
    "protected_query_block_rate": 1.0,
    "protected_source_leakage_rate": 0.0,
}
LOWER_IS_BETTER_METRICS = {
    "unsupported_answer_rate",
    "protected_source_leakage_rate",
}


def load_dataset(path: Path) -> dict[str, Any]:
    dataset = json.loads(path.read_text(encoding="utf-8"))
    validate_dataset(dataset)
    return dataset


def validate_dataset(dataset: dict[str, Any]) -> None:
    if not isinstance(dataset, dict) or dataset.get("schema_version") != 3:
        raise ValueError("Golden Set 必须是 schema_version=3 的对象")
    if not dataset.get("name") or not dataset.get("dataset_version"):
        raise ValueError("Golden Set 必须声明 name 和 dataset_version")
    cases = dataset.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError("Golden Set cases 不能为空")

    required = {
        "id",
        "category",
        "case_type",
        "difficulty",
        "question",
        "expected_behavior",
        "expected_intent",
        "relevance",
        "evidence_groups",
    }
    seen_ids: set[str] = set()
    seen_questions: dict[str, str] = {}
    for index, case in enumerate(cases, 1):
        missing = required.difference(case)
        if missing:
            raise ValueError(f"第 {index} 条样本缺少字段：{sorted(missing)}")
        case_id = case["id"]
        if not isinstance(case_id, str) or not case_id.strip() or case_id in seen_ids:
            raise ValueError(f"第 {index} 条样本 id 为空或重复：{case_id!r}")
        seen_ids.add(case_id)
        if not isinstance(case["question"], str) or not case["question"].strip():
            raise ValueError(f"{case_id}: question 不能为空")
        normalized_question = re.sub(r"[\W_]+", "", case["question"].casefold())
        if normalized_question in seen_questions:
            raise ValueError(
                f"{case_id}: question 与 {seen_questions[normalized_question]} 重复"
            )
        seen_questions[normalized_question] = case_id
        if not case["category"] or not case["case_type"]:
            raise ValueError(f"{case_id}: category 和 case_type 不能为空")
        if case["difficulty"] not in ALLOWED_DIFFICULTIES:
            raise ValueError(f"{case_id}: difficulty 非法")
        if case["expected_behavior"] not in ALLOWED_BEHAVIORS:
            raise ValueError(f"{case_id}: expected_behavior 非法")
        if case["expected_intent"] not in ALLOWED_INTENTS:
            raise ValueError(f"{case_id}: expected_intent 非法")
        if not isinstance(case["relevance"], dict):
            raise ValueError(f"{case_id}: relevance 必须是对象")
        if any(
            not isinstance(gain, int) or not 1 <= gain <= 3
            for gain in case["relevance"].values()
        ):
            raise ValueError(f"{case_id}: relevance 等级必须是 1..3 的整数")
        groups = case["evidence_groups"]
        if not isinstance(groups, list) or any(
            not isinstance(group, list) or not group for group in groups
        ):
            raise ValueError(f"{case_id}: evidence_groups 必须是非空来源组列表")
        behavior = case["expected_behavior"]
        if behavior == "evidence" and (not case["relevance"] or not groups):
            raise ValueError(f"{case_id}: evidence 样本必须有相关性和证据组标注")
        if behavior == "evidence" and any(
            source_id not in case["relevance"]
            for group in groups
            for source_id in group
        ):
            raise ValueError(f"{case_id}: 证据组来源必须包含在 relevance 中")
        if behavior != "evidence" and (case["relevance"] or groups):
            raise ValueError(f"{case_id}: 非 evidence 样本不应带相关性或证据组标注")
        if behavior == "abstain" and not case.get("abstention_sources"):
            raise ValueError(f"{case_id}: abstain 样本必须标注 abstention_sources")
        if behavior == "protected" and "forbidden_sources" not in case:
            raise ValueError(f"{case_id}: protected 样本必须声明 forbidden_sources")
        for field in ("abstention_sources", "forbidden_sources"):
            values = case.get(field, [])
            if not isinstance(values, list) or any(
                not isinstance(source_id, str) or not source_id for source_id in values
            ):
                raise ValueError(f"{case_id}: {field} 必须是规范来源路径列表")
        source_ids = [
            *case["relevance"],
            *case.get("abstention_sources", []),
            *case.get("forbidden_sources", []),
        ]
        if any(
            not isinstance(source_id, str)
            or source_id.startswith("knowledge/")
            or "\\" in source_id
            for source_id in source_ids
        ):
            raise ValueError(f"{case_id}: 来源必须是相对 knowledge/ 的规范路径")


def _mean(values: Iterable[float | int | None]) -> float | None:
    present = [float(value) for value in values if value is not None]
    return round(sum(present) / len(present), 4) if present else None


def _percentile(values: list[float], percentile: float) -> float:
    ordered = sorted(values)
    index = max(0, math.ceil(len(ordered) * percentile) - 1)
    return ordered[index]


def _wilson_interval(
    successes: int, total: int, z: float = 1.96
) -> dict[str, float] | None:
    if total == 0:
        return None
    rate = successes / total
    denominator = 1 + z * z / total
    centre = rate + z * z / (2 * total)
    margin = z * math.sqrt((rate * (1 - rate) + z * z / (4 * total)) / total)
    return {
        "lower": round(max(0.0, (centre - margin) / denominator), 4),
        "upper": round(min(1.0, (centre + margin) / denominator), 4),
    }


def _first_relevant_rank(
    ranked_sources: list[str | None], relevance: dict[str, int], cutoff: int
) -> int | None:
    for rank, source_id in enumerate(ranked_sources[:cutoff], 1):
        if source_id in relevance:
            return rank
    return None


def _ndcg_at_k(
    ranked_sources: list[str | None], relevance: dict[str, int], cutoff: int
) -> float:
    seen: set[str] = set()
    gains: list[int] = []
    for source_id in ranked_sources[:cutoff]:
        if source_id is None or source_id in seen:
            gains.append(0)
            continue
        seen.add(source_id)
        gains.append(relevance.get(source_id, 0))

    dcg = sum((2**gain - 1) / math.log2(rank + 1) for rank, gain in enumerate(gains, 1))
    ideal = sorted(relevance.values(), reverse=True)[:cutoff]
    idcg = sum(
        (2**gain - 1) / math.log2(rank + 1) for rank, gain in enumerate(ideal, 1)
    )
    return round(dcg / idcg, 4) if idcg else 0.0


def _evidence_coverage(
    ranked_sources: list[str | None], evidence_groups: list[list[str]], cutoff: int
) -> float:
    retrieved = {source for source in ranked_sources[:cutoff] if source}
    covered = sum(bool(retrieved.intersection(group)) for group in evidence_groups)
    return round(covered / len(evidence_groups), 4) if evidence_groups else 0.0


def score_case(
    case: dict[str, Any],
    ranked_sources: list[str | None],
    actual_intent: str,
    direct_answer: str | None,
    latency_ms: float,
    evidence_sufficient: bool | None = None,
    input_rejected: bool = False,
    plan_expected_coverage: list[str] | None = None,
    plan_missing_coverage: list[str] | None = None,
    cutoff: int = EVALUATION_CUTOFF,
) -> dict[str, Any]:
    behavior = case["expected_behavior"]
    relevance = case["relevance"]
    first_rank = _first_relevant_rank(ranked_sources, relevance, cutoff)
    top_sources = [source for source in ranked_sources[:cutoff] if source]
    unique_sources = set(top_sources)
    if evidence_sufficient is None:
        evidence_sufficient = bool(ranked_sources or direct_answer)
    boundary_source_hit = bool(
        set(case.get("abstention_sources", [])).intersection(top_sources)
    )
    forbidden = set(case.get("forbidden_sources", []))
    protected_source_leakage = bool(forbidden.intersection(top_sources))

    if behavior == "evidence":
        coverage = _evidence_coverage(ranked_sources, case["evidence_groups"], cutoff)
        hit_at_1 = 1.0 if first_rank == 1 else 0.0
        hit_at_3 = 1.0 if first_rank is not None and first_rank <= 3 else 0.0
        hit_at_5 = 1.0 if first_rank is not None else 0.0
        reciprocal_rank = round(1 / first_rank, 4) if first_rank else 0.0
        ndcg = _ndcg_at_k(ranked_sources, relevance, cutoff)
        complete_coverage = 1.0 if coverage == 1.0 else 0.0
        task_success = (
            complete_coverage if evidence_sufficient and not input_rejected else 0.0
        )
    else:
        coverage = None
        hit_at_1 = hit_at_3 = hit_at_5 = None
        reciprocal_rank = ndcg = complete_coverage = None
        if behavior == "direct_answer":
            task_success = (
                1.0 if direct_answer and evidence_sufficient and not input_rejected else 0.0
            )
        elif behavior == "abstain":
            task_success = (
                1.0
                if not input_rejected
                and (not evidence_sufficient or boundary_source_hit)
                else 0.0
            )
        else:
            task_success = 1.0 if input_rejected and not protected_source_leakage else 0.0

    return {
        "id": case["id"],
        "category": case["category"],
        "case_type": case["case_type"],
        "difficulty": case["difficulty"],
        "question": case["question"],
        "expected_behavior": behavior,
        "expected_intent": case["expected_intent"],
        "actual_intent": actual_intent,
        "intent_correct": 1.0 if actual_intent == case["expected_intent"] else 0.0,
        "plan_expected_coverage": plan_expected_coverage or [],
        "plan_missing_coverage": plan_missing_coverage or [],
        "relevance": relevance,
        "evidence_groups": case["evidence_groups"],
        "abstention_sources": case.get("abstention_sources", []),
        "forbidden_sources": case.get("forbidden_sources", []),
        "retrieved_sources": ranked_sources,
        "first_relevant_rank": first_rank,
        "hit_at_1": hit_at_1,
        "hit_at_3": hit_at_3,
        "hit_at_5": hit_at_5,
        "reciprocal_rank_at_5": reciprocal_rank,
        "ndcg_at_5": ndcg,
        "evidence_coverage_at_5": coverage,
        "complete_evidence_at_5": complete_coverage,
        "source_diversity_at_5": round(len(unique_sources) / len(top_sources), 4)
        if top_sources
        else None,
        "task_success": task_success,
        "direct_answer_returned": bool(direct_answer),
        "evidence_sufficient": evidence_sufficient,
        "boundary_source_hit": boundary_source_hit,
        "input_rejected": input_rejected,
        "source_isolation_probe": bool(forbidden),
        "protected_source_leakage": protected_source_leakage,
        "latency_ms": round(latency_ms, 1),
    }


def summarize_cases(results: list[dict[str, Any]]) -> dict[str, Any]:
    evidence = [case for case in results if case["expected_behavior"] == "evidence"]
    direct = [case for case in results if case["expected_behavior"] == "direct_answer"]
    abstain = [case for case in results if case["expected_behavior"] == "abstain"]
    protected = [case for case in results if case["expected_behavior"] == "protected"]
    protected_source_probes = [
        case for case in protected if case["source_isolation_probe"]
    ]
    benign = [case for case in results if case["expected_behavior"] != "protected"]
    evidence_decisions = [
        case
        for case in results
        if case["expected_behavior"] in {"evidence", "direct_answer", "abstain"}
    ]
    latencies = [case["latency_ms"] for case in results]
    source_slots = [
        source
        for case in evidence
        for source in case["retrieved_sources"][:EVALUATION_CUTOFF]
        if source
    ]
    unique_slots = sum(
        len(
            set(
                source
                for source in case["retrieved_sources"][:EVALUATION_CUTOFF]
                if source
            )
        )
        for case in evidence
    )

    hit_at_5_successes = sum(int(case["hit_at_5"] or 0) for case in evidence)
    task_successes = sum(int(case["task_success"]) for case in results)
    expected_sufficient = [
        (
            case["expected_behavior"] == "evidence"
            and case["complete_evidence_at_5"] == 1.0
        )
        or (
            case["expected_behavior"] == "direct_answer"
            and case["direct_answer_returned"]
        )
        or case["boundary_source_hit"]
        for case in evidence_decisions
    ]
    supported_decisions = [
        case["evidence_sufficient"]
        or (
            case["expected_behavior"] == "abstain"
            and case["boundary_source_hit"]
        )
        for case in evidence_decisions
    ]
    true_positives = sum(
        expected and supported
        for expected, supported in zip(expected_sufficient, supported_decisions)
    )
    false_positives = sum(
        not expected and supported
        for expected, supported in zip(expected_sufficient, supported_decisions)
    )
    false_negatives = sum(
        expected and not supported
        for expected, supported in zip(expected_sufficient, supported_decisions)
    )
    decision_correct = sum(
        expected == supported
        for expected, supported in zip(expected_sufficient, supported_decisions)
    )
    precision = (
        true_positives / (true_positives + false_positives)
        if true_positives + false_positives
        else 0.0
    )
    recall = (
        true_positives / (true_positives + false_negatives)
        if true_positives + false_negatives
        else 0.0
    )
    return {
        "task_success_rate": _mean(case["task_success"] for case in results),
        "task_success_rate_ci95": _wilson_interval(task_successes, len(results)),
        "hit_rate_at_1": _mean(case["hit_at_1"] for case in evidence),
        "hit_rate_at_3": _mean(case["hit_at_3"] for case in evidence),
        "hit_rate_at_5": _mean(case["hit_at_5"] for case in evidence),
        "hit_rate_at_5_ci95": _wilson_interval(hit_at_5_successes, len(evidence)),
        "mrr_at_5": _mean(case["reciprocal_rank_at_5"] for case in evidence),
        "ndcg_at_5": _mean(case["ndcg_at_5"] for case in evidence),
        "evidence_coverage_at_5": _mean(
            case["evidence_coverage_at_5"] for case in evidence
        ),
        "complete_evidence_rate_at_5": _mean(
            case["complete_evidence_at_5"] for case in evidence
        ),
        "planner_intent_accuracy": _mean(case["intent_correct"] for case in results),
        "direct_answer_accuracy": _mean(case["task_success"] for case in direct),
        "knowledge_boundary_accuracy": _mean(case["task_success"] for case in abstain),
        "evidence_decision_accuracy": round(
            decision_correct / len(evidence_decisions), 4
        ),
        "evidence_decision_f1": (
            round(2 * precision * recall / (precision + recall), 4)
            if precision + recall
            else 0.0
        ),
        "unsupported_answer_rate": (
            round(false_positives / sum(not value for value in expected_sufficient), 4)
            if any(not value for value in expected_sufficient)
            else 0.0
        ),
        "benign_query_allow_rate": _mean(
            not case["input_rejected"] for case in benign
        ),
        "protected_query_block_rate": (
            _mean(case["input_rejected"] for case in protected)
            if protected
            else None
        ),
        "protected_source_leakage_rate": (
            _mean(
                case["protected_source_leakage"] for case in protected_source_probes
            )
            if protected_source_probes
            else None
        ),
        "protected_source_probe_count": len(protected_source_probes),
        "source_diversity_at_5": _mean(
            case["source_diversity_at_5"] for case in evidence
        ),
        "duplicate_source_rate_at_5": (
            round(1 - unique_slots / len(source_slots), 4) if source_slots else None
        ),
        "average_retrieval_latency_ms": round(sum(latencies) / len(latencies), 1),
        "p50_retrieval_latency_ms": round(float(median(latencies)), 1),
        "p95_retrieval_latency_ms": round(_percentile(latencies, 0.95), 1),
    }


def _group_breakdown(results: list[dict[str, Any]], field: str) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for case in results:
        groups[case[field]].append(case)

    rows = []
    for name, cases in sorted(groups.items()):
        evidence = [case for case in cases if case["expected_behavior"] == "evidence"]
        rows.append(
            {
                "name": name,
                "sample_size": len(cases),
                "evidence_cases": len(evidence),
                "task_success_rate": _mean(case["task_success"] for case in cases),
                "hit_rate_at_5": _mean(case["hit_at_5"] for case in evidence),
                "mrr_at_5": _mean(case["reciprocal_rank_at_5"] for case in evidence),
                "evidence_coverage_at_5": _mean(
                    case["evidence_coverage_at_5"] for case in evidence
                ),
                "planner_intent_accuracy": _mean(
                    case["intent_correct"] for case in cases
                ),
            }
        )
    return rows


def evaluate_quality_gates(metrics: dict[str, Any]) -> dict[str, Any]:
    checks = []
    for metric, threshold in DEFAULT_QUALITY_GATES.items():
        value = metrics.get(metric)
        comparison = "<=" if metric in LOWER_IS_BETTER_METRICS else ">="
        passed = value is not None and (
            value <= threshold if comparison == "<=" else value >= threshold
        )
        checks.append(
            {
                "metric": metric,
                "value": value,
                "comparison": comparison,
                "threshold": threshold,
                "passed": passed,
            }
        )
    return {"passed": all(check["passed"] for check in checks), "checks": checks}


async def resolve_source_ids(
    session: Any, chunks: list[dict[str, Any]]
) -> list[str | None]:
    chunk_ids: list[UUID] = []
    for chunk in chunks:
        try:
            chunk_ids.append(UUID(chunk["chunk_id"]))
        except (KeyError, TypeError, ValueError):
            continue
    if not chunk_ids:
        return [None] * len(chunks)

    result = await session.execute(
        select(DocumentChunk.id, Document.source_id)
        .join(Document, Document.id == DocumentChunk.document_id)
        .where(DocumentChunk.id.in_(chunk_ids))
    )
    source_by_chunk = {
        str(row.id): _canonical_source_id(row.source_id) for row in result.all()
    }
    return [source_by_chunk.get(chunk.get("chunk_id")) for chunk in chunks]


def _canonical_source_id(source_id: str) -> str:
    normalized = source_id.replace("\\", "/").lstrip("./")
    return normalized.removeprefix("knowledge/")


def _fingerprint_files(paths: Iterable[Path], root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(paths):
        digest.update(path.relative_to(root).as_posix().encode("utf-8"))
        digest.update(path.read_bytes())
    return digest.hexdigest()


async def _corpus_metadata(session: Any) -> dict[str, Any]:
    allowed_confidence = ["confirmed", "self_reported"]
    rows = (
        await session.execute(
            select(Document.source_id, Document.content_hash)
            .where(
                Document.visibility == "public",
                Document.confidence.in_(allowed_confidence),
            )
            .order_by(Document.source_id)
        )
    ).all()
    chunk_count = (
        await session.execute(
            select(func.count(DocumentChunk.id)).where(
                DocumentChunk.visibility == "public",
                DocumentChunk.confidence.in_(allowed_confidence),
            )
        )
    ).scalar_one()
    digest = hashlib.sha256()
    for row in rows:
        digest.update(_canonical_source_id(row.source_id).encode("utf-8"))
        digest.update(row.content_hash.encode("ascii"))
    return {
        "fingerprint": digest.hexdigest(),
        "indexed_public_document_count": len(rows),
        "indexed_public_chunk_count": chunk_count,
    }


def _git_commit() -> str | None:
    try:
        return subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


async def evaluate(
    golden_path: Path,
    output_path: Path,
    warmup_runs: int = 1,
) -> dict[str, Any]:
    dataset = load_dataset(golden_path)
    cases = dataset["cases"]
    retrieval = RetrievalService(ChunkRepository(), get_embedding_service())
    citation = CitationService()
    results: list[dict[str, Any]] = []

    async with AsyncSessionLocal() as session:
        corpus = await _corpus_metadata(session)
        for _ in range(warmup_runs):
            await retrieval.retrieve_with_plan(
                cases[0]["question"],
                session=session,
                top_k=settings.retrieval_top_k,
                min_score=settings.min_relevance_score,
            )

        for case in cases:
            started = time.perf_counter()
            outcome: RetrievalOutcome = await retrieval.retrieve_with_plan(
                case["question"],
                session=session,
                top_k=settings.retrieval_top_k,
                min_score=settings.min_relevance_score,
            )
            latency_ms = (time.perf_counter() - started) * 1000
            source_ids = await resolve_source_ids(session, outcome.chunks)
            results.append(
                score_case(
                    case=case,
                    ranked_sources=source_ids,
                    actual_intent=outcome.plan.intent,
                    direct_answer=outcome.direct_answer,
                    latency_ms=latency_ms,
                    evidence_sufficient=citation.has_sufficient_evidence(
                        outcome,
                        case["question"],
                        min_score=settings.min_relevance_score,
                    ),
                    input_rejected=not is_safe_question(case["question"]),
                    plan_expected_coverage=outcome.plan.expected_coverage,
                    plan_missing_coverage=outcome.missing_coverage,
                )
            )

    metrics = summarize_cases(results)
    dataset_bytes = golden_path.read_bytes()
    knowledge_files = list((ROOT / "knowledge").rglob("*.md"))
    summary = {
        "schema_version": 3,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "dataset": {
            "name": dataset["name"],
            "version": dataset["dataset_version"],
            "sha256": hashlib.sha256(dataset_bytes).hexdigest(),
            "annotation_policy": dataset.get("annotation_policy", {}),
        },
        "corpus": {
            **corpus,
            "source_tree_fingerprint": _fingerprint_files(
                knowledge_files, ROOT / "knowledge"
            ),
            "markdown_file_count": len(knowledge_files),
        },
        "run": {
            "git_commit": _git_commit(),
            "embedding_mode": settings.embedding_mode,
            "embedding_model": settings.embedding_api_model
            if settings.embedding_mode == "api"
            else settings.embedding_model_path,
            "embedding_dimensions": settings.embedding_dimensions,
            "retrieval_candidate_top_k": settings.retrieval_top_k,
            "metric_cutoff_k": EVALUATION_CUTOFF,
            "min_relevance_score": settings.min_relevance_score,
            "warmup_runs": warmup_runs,
            "ranking_unit": "chunk",
            "relevance_unit": "source_id",
            "generation_evaluated": False,
            "security_scope": "input_guard_and_forced_retrieval_isolation_probe",
        },
        "sample_size": len(results),
        "sample_distribution": {
            "evidence": sum(
                case["expected_behavior"] == "evidence" for case in results
            ),
            "direct_answer": sum(
                case["expected_behavior"] == "direct_answer" for case in results
            ),
            "abstain": sum(case["expected_behavior"] == "abstain" for case in results),
            "protected": sum(
                case["expected_behavior"] == "protected" for case in results
            ),
        },
        "metrics": metrics,
        "quality_gate": evaluate_quality_gates(metrics),
        "breakdowns": {
            "category": _group_breakdown(results, "category"),
            "difficulty": _group_breakdown(results, "difficulty"),
            "case_type": _group_breakdown(results, "case_type"),
        },
        "cases": results,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return summary


async def main() -> int:
    parser = argparse.ArgumentParser(description="运行冻结的 RAG 检索评测")
    parser.add_argument("--golden-set", type=Path, default=DEFAULT_SET)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--warmup-runs", type=int, default=1)
    parser.add_argument(
        "--enforce-gates",
        action="store_true",
        help="任一质量门禁未通过时返回非零退出码",
    )
    args = parser.parse_args()
    if args.warmup_runs < 0:
        parser.error("--warmup-runs 不能小于 0")
    try:
        result = await evaluate(args.golden_set, args.output, args.warmup_runs)
        print(
            json.dumps(
                {
                    "sample_size": result["sample_size"],
                    "metrics": result["metrics"],
                    "quality_gate_passed": result["quality_gate"]["passed"],
                },
                ensure_ascii=False,
            )
        )
        return 1 if args.enforce_gates and not result["quality_gate"]["passed"] else 0
    finally:
        await engine.dispose()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
