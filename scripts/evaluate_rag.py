"""Run the frozen retrieval Golden Set and write a public result artifact."""
import argparse
import asyncio
import json
import math
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.database import AsyncSessionLocal, engine
from app.repositories.chunk_repository import ChunkRepository
from app.services.embedding_service import get_embedding_service
from app.services.retrieval_service import RetrievalService


DEFAULT_SET = ROOT / "tests" / "rag_golden_set.json"
DEFAULT_OUTPUT = ROOT / "static" / "evaluation" / "latest.json"


async def evaluate(golden_path: Path, output_path: Path) -> dict:
    cases = json.loads(golden_path.read_text(encoding="utf-8"))
    retrieval = RetrievalService(ChunkRepository(), get_embedding_service())
    results = []

    async with AsyncSessionLocal() as session:
        for case in cases:
            started = time.perf_counter()
            chunks = await retrieval.retrieve(
                case["question"],
                session=session,
                top_k=5,
                min_score=0.0,
            )
            latency_ms = round((time.perf_counter() - started) * 1000, 1)
            sources = [chunk.get("source_name") for chunk in chunks]
            expected = case["expected_sources"]
            hits = sorted(set(expected).intersection(source for source in sources if source))
            hit_rate = 1.0 if hits else 0.0
            results.append({
                "id": case["id"],
                "category": case["category"],
                "question": case["question"],
                "expected_sources": expected,
                "retrieved_sources": sources,
                "matched_sources": hits,
                "hit_at_5": round(hit_rate, 4),
                "latency_ms": latency_ms,
            })

    latencies = sorted(item["latency_ms"] for item in results)
    p95_index = max(0, math.ceil(len(latencies) * 0.95) - 1)
    summary = {
        "schema_version": 2,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "dataset": golden_path.name,
        "sample_size": len(results),
        "metrics": {
            "hit_rate_at_5": round(
                sum(item["hit_at_5"] for item in results) / len(results), 4
            ),
            "average_retrieval_latency_ms": round(sum(latencies) / len(latencies), 1),
            "p95_retrieval_latency_ms": latencies[p95_index],
        },
        "cases": results,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return summary


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--golden-set", type=Path, default=DEFAULT_SET)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    try:
        result = await evaluate(args.golden_set, args.output)
        print(json.dumps(result["metrics"], ensure_ascii=False))
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
