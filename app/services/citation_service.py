import re
from app.schemas.citation import CitationOut


class CitationService:
    def format_citations(self, chunks: list[dict]) -> list[CitationOut]:
        citations: list[CitationOut] = []
        for chunk in chunks:
            preview = (chunk.get("content") or "")[:150]
            citations.append(
                CitationOut(
                    id=chunk["chunk_id"],
                    title=chunk.get("source_name") or chunk["title"],
                    section=chunk.get("section"),
                    content_preview=preview,
                    project_slug=chunk.get("project_id"),
                    tags=chunk.get("tags") or [],
                    ranking_score=chunk["score"],
                )
            )
        return citations

    def has_sufficient_evidence(
        self,
        chunks: list[dict],
        question: str,
        min_score: float = 0.40,
    ) -> bool:
        if not chunks:
            return False

        top_score = chunks[0]["score"]
        if top_score < min_score:
            return False

        # 问题含数字/排名 → 必须有含数字的证据
        if re.search(r"\d|排名|第[一二三四五六七八九十\d]|top\s*\d", question, re.IGNORECASE):
            has_numeric = any(
                re.search(r"\d", c.get("content") or "") for c in chunks
            )
            if not has_numeric:
                return False

        # 问题含"主导/独立" → 必须命中 section=responsibility
        if re.search(r"主导|独立", question):
            has_resp = any(
                (c.get("section") or "").lower() in ("responsibility", "职责") for c in chunks
            )
            if not has_resp:
                return False

        # 问题含“实习” → 证据本身必须明确提及实习经历。
        if "实习" in question:
            has_exp = any(
                "experience" in (c.get("tags") or [])
                or "实习" in " ".join([
                    c.get("title") or "",
                    c.get("section") or "",
                    c.get("content") or "",
                ])
                for c in chunks
            )
            if not has_exp:
                return False

        return True
