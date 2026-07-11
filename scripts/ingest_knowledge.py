#!/usr/bin/env python3
"""
知识库导入脚本

扫描 knowledge/ 目录下所有 Markdown 文件，解析 Front Matter，
切块后生成 Embedding 并写入 PostgreSQL（documents + document_chunks 表）。

支持增量更新：内容 hash 未变化的文件会被跳过。

用法：
    python scripts/ingest_knowledge.py
    python scripts/ingest_knowledge.py --force   # 强制重建所有 chunk（同 rebuild_embeddings.py）
    python scripts/ingest_knowledge.py --dry-run # 只解析，不写库
"""

import argparse
import asyncio
import hashlib
import os
import re
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

# 把项目根目录加入 sys.path，以便 import app.*
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv

load_dotenv(PROJECT_ROOT / ".env")

# 延迟导入（需要 DATABASE_URL 已经加载）
from sqlalchemy import text, select, delete
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.services.embedding_service import get_embedding_service
from app.models.document import Document
from app.models.chunk import DocumentChunk


# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------

KNOWLEDGE_DIR = PROJECT_ROOT / "knowledge"
REQUIRED_FIELDS = {"id", "title", "type", "visibility", "confidence"}
ALLOWED_VISIBILITY = {"public"}
ALLOWED_CONFIDENCE = {"confirmed", "self_reported"}

# chunk 大小上限（中文字符数）
CHUNK_MAX_CHARS = 500
CHUNK_MIN_CHARS = 50


# ---------------------------------------------------------------------------
# Front Matter 解析
# ---------------------------------------------------------------------------

def parse_front_matter(text: str) -> tuple[dict[str, Any], str]:
    """
    解析 Markdown 文件的 YAML Front Matter。
    返回 (meta_dict, body_content)。
    不依赖 python-frontmatter，手动解析以减少依赖。
    """
    if not text.startswith("---"):
        return {}, text

    end = text.find("\n---", 3)
    if end == -1:
        return {}, text

    yaml_block = text[3:end].strip()
    body = text[end + 4:].strip()

    meta: dict[str, Any] = {}
    current_key: Optional[str] = None
    list_items: list[str] = []
    in_list = False

    for line in yaml_block.splitlines():
        # 列表项
        if line.startswith("  - ") or line.startswith("- "):
            item = line.lstrip("- ").strip()
            list_items.append(item)
            in_list = True
            continue

        # 键值对
        if ":" in line:
            # 先保存上一个列表
            if in_list and current_key:
                meta[current_key] = list_items[:]
                list_items = []
                in_list = False

            key, _, val = line.partition(":")
            key = key.strip()
            val = val.strip()

            if val == "" or val is None:
                # 可能是列表开头
                current_key = key
                in_list = False
            else:
                current_key = key
                # 去掉引号
                val = val.strip("'\"")
                meta[key] = val

    # 收尾
    if in_list and current_key:
        meta[current_key] = list_items

    return meta, body


# ---------------------------------------------------------------------------
# Markdown 切块
# ---------------------------------------------------------------------------

def chunk_markdown(content: str, title: str, section: str) -> list[dict[str, str]]:
    """
    按 H2 标题分割 Markdown，段落超过 CHUNK_MAX_CHARS 再细分。
    每个 chunk 携带标题上下文。

    返回 [{"title": str, "section": str, "content": str}, ...]
    """
    chunks: list[dict[str, str]] = []

    # 按 H2（## ）分割
    h2_pattern = re.compile(r"^## .+", re.MULTILINE)
    h2_positions = [m.start() for m in h2_pattern.finditer(content)]

    if not h2_positions:
        # 没有 H2，整体作为一个或多个段落处理
        paragraphs = _split_to_paragraphs(content)
        merged = _merge_short_paragraphs(paragraphs)
        for para in merged:
            if len(para.strip()) >= CHUNK_MIN_CHARS:
                chunks.append({
                    "title": title,
                    "section": section,
                    "content": para.strip(),
                })
        return chunks

    # 有 H2，逐段处理
    segments: list[tuple[str, str]] = []  # (h2_title, segment_body)

    for i, pos in enumerate(h2_positions):
        end_pos = h2_positions[i + 1] if i + 1 < len(h2_positions) else len(content)
        segment_text = content[pos:end_pos].strip()

        # 第一行是 H2 标题
        lines = segment_text.splitlines()
        h2_title = lines[0].lstrip("#").strip()
        body = "\n".join(lines[1:]).strip()
        segments.append((h2_title, body))

    for h2_title, body in segments:
        paragraphs = _split_to_paragraphs(body)
        merged = _merge_short_paragraphs(paragraphs)
        for para in merged:
            para = para.strip()
            if len(para) < CHUNK_MIN_CHARS:
                continue
            # 如果段落过长，再细分
            if len(para) > CHUNK_MAX_CHARS:
                sub_chunks = _split_long_paragraph(para)
            else:
                sub_chunks = [para]

            for sub in sub_chunks:
                sub = sub.strip()
                if len(sub) >= CHUNK_MIN_CHARS:
                    chunks.append({
                        "title": title,
                        "section": f"{section} > {h2_title}" if section else h2_title,
                        "content": sub,
                    })

    return chunks


def _split_to_paragraphs(text: str) -> list[str]:
    """按空行分割段落。"""
    return [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]


def _merge_short_paragraphs(paragraphs: list[str]) -> list[str]:
    """
    把过短的段落和相邻段落合并，避免碎片化 chunk。
    """
    if not paragraphs:
        return []

    merged: list[str] = []
    buffer = paragraphs[0]

    for para in paragraphs[1:]:
        if len(buffer) + len(para) + 2 <= CHUNK_MAX_CHARS:
            buffer = buffer + "\n\n" + para
        else:
            merged.append(buffer)
            buffer = para

    merged.append(buffer)
    return merged


def _split_long_paragraph(text: str, max_chars: int = CHUNK_MAX_CHARS) -> list[str]:
    """
    把超长段落按句子（。！？\n）切分成不超过 max_chars 的片段。
    """
    # 按中文句号、感叹号、问号、换行分割
    sentence_endings = re.compile(r"(?<=[。！？\n])")
    sentences = sentence_endings.split(text)

    chunks: list[str] = []
    buffer = ""

    for sent in sentences:
        if not sent:
            continue
        if len(buffer) + len(sent) > max_chars:
            if buffer:
                chunks.append(buffer.strip())
            buffer = sent
        else:
            buffer += sent

    if buffer.strip():
        chunks.append(buffer.strip())

    return chunks if chunks else [text[:max_chars]]


# ---------------------------------------------------------------------------
# Embedding 文本组装
# ---------------------------------------------------------------------------

def build_embed_text(meta: dict, chunk_content: str, chunk_section: str) -> str:
    """
    组装用于 Embedding 的文本，加入文档级元数据作为上下文前缀。
    """
    title = meta.get("title", "")
    tags = meta.get("tags", [])
    tags_str = "、".join(tags) if isinstance(tags, list) else str(tags)
    section = chunk_section or meta.get("section", "")

    prefix_parts = []
    if title:
        prefix_parts.append(f"文档：{title}")
    if section:
        prefix_parts.append(f"章节：{section}")
    if tags_str:
        prefix_parts.append(f"标签：{tags_str}")

    prefix = "\n".join(prefix_parts)
    return f"{prefix}\n\n{chunk_content}" if prefix else chunk_content


# ---------------------------------------------------------------------------
# 导入逻辑
# ---------------------------------------------------------------------------

async def ingest_all(
    engine,
    session_factory,
    force: bool = False,
    dry_run: bool = False,
) -> dict[str, int]:
    """
    主导入流程。

    返回统计信息：
    {
        "files_scanned": int,
        "files_skipped_filter": int,
        "files_skipped_hash": int,
        "files_processed": int,
        "chunks_new": int,
        "chunks_updated": int,
        "docs_deleted": int,
        "errors": int,
    }
    """
    stats = {
        "files_scanned": 0,
        "files_skipped_filter": 0,
        "files_skipped_hash": 0,
        "files_processed": 0,
        "chunks_new": 0,
        "chunks_updated": 0,
        "docs_deleted": 0,
        "errors": 0,
    }

    embedding_service = get_embedding_service()

    # 收集所有 md 文件
    md_files = sorted(KNOWLEDGE_DIR.rglob("*.md"))
    stats["files_scanned"] = len(md_files)
    print(f"\n扫描到 {len(md_files)} 个 Markdown 文件")

    # 记录本次处理的 source_id 集合（用于后续清理孤儿文档）
    processed_source_ids: set[str] = set()

    async with session_factory() as session:
        for md_path in md_files:
            rel_path = md_path.relative_to(PROJECT_ROOT)
            source_id = str(rel_path).replace("\\", "/")

            try:
                raw = md_path.read_text(encoding="utf-8")
            except Exception as e:
                print(f"  [错误] 读取文件失败 {rel_path}: {e}")
                stats["errors"] += 1
                continue

            meta, body = parse_front_matter(raw)

            # 验证必填字段
            missing = REQUIRED_FIELDS - set(meta.keys())
            if missing:
                print(f"  [跳过] 缺少必填字段 {missing}: {rel_path}")
                stats["files_skipped_filter"] += 1
                continue

            # 过滤 visibility 和 confidence
            if meta.get("visibility") not in ALLOWED_VISIBILITY:
                print(f"  [跳过] visibility={meta.get('visibility')}: {rel_path}")
                stats["files_skipped_filter"] += 1
                continue

            if meta.get("confidence") not in ALLOWED_CONFIDENCE:
                print(f"  [跳过] confidence={meta.get('confidence')}: {rel_path}")
                stats["files_skipped_filter"] += 1
                continue

            processed_source_ids.add(source_id)

            # 计算内容 hash
            content_hash = hashlib.sha256(raw.encode("utf-8")).hexdigest()

            # 检查是否需要更新（增量）
            if not force:
                existing_doc = await _get_document_by_source_id(session, source_id)
                if existing_doc and existing_doc.content_hash == content_hash:
                    print(f"  [跳过] hash 未变化: {rel_path}")
                    stats["files_skipped_hash"] += 1
                    continue

            print(f"  [处理] {rel_path}")

            if dry_run:
                stats["files_processed"] += 1
                continue

            # 切块
            title = meta.get("title", md_path.stem)
            section = meta.get("section", "")
            raw_chunks = chunk_markdown(body, title, section)

            if not raw_chunks:
                print(f"    警告：切块结果为空，跳过")
                stats["files_skipped_filter"] += 1
                continue

            # 组装 Embedding 文本
            embed_texts = [
                build_embed_text(meta, c["content"], c["section"])
                for c in raw_chunks
            ]

            # 批量生成 Embedding
            try:
                embeddings = await embedding_service.async_embed_documents(embed_texts)
            except Exception as e:
                print(f"    [错误] Embedding 生成失败: {e}")
                stats["errors"] += 1
                continue

            # 写入 documents 表（upsert）
            now = datetime.now(timezone.utc)
            doc_data = {
                "source_id": source_id,
                "title": title,
                "document_type": meta.get("type", "general"),
                "source_path": source_id,
                "content_hash": content_hash,
                "visibility": meta.get("visibility", "public"),
                "confidence": meta.get("confidence", "self_reported"),
                "tags": meta.get("tags", []) if isinstance(meta.get("tags"), list) else [],
                "updated_at": now,
            }

            doc_id = await _upsert_document(session, doc_data)

            # 删除旧 chunk，写入新 chunk
            await _delete_chunks_by_doc(session, doc_id)

            new_count = 0
            for idx, (chunk, embedding) in enumerate(zip(raw_chunks, embeddings)):
                tags_val = meta.get("tags", [])
                chunk_data = {
                    "id": uuid.uuid4(),
                    "document_id": doc_id,
                    "chunk_index": idx,
                    "title": chunk["title"],
                    "section": chunk["section"],
                    "content": chunk["content"],
                    "embedding": embedding,
                    "visibility": meta.get("visibility", "public"),
                    "confidence": meta.get("confidence", "self_reported"),
                    "tags": tags_val if isinstance(tags_val, list) else [],
                    "token_count": len(chunk["content"]),
                    "created_at": now,
                    "updated_at": now,
                }
                session.add(DocumentChunk(**chunk_data))
                new_count += 1

            await session.commit()
            stats["files_processed"] += 1
            stats["chunks_new"] += new_count
            print(f"    写入 {new_count} 个 chunk")

        # 清理数据库中已不存在的旧文档
        if not dry_run:
            deleted = await _delete_orphan_documents(session, processed_source_ids)
            stats["docs_deleted"] = deleted
            if deleted:
                print(f"\n清理孤儿文档：删除 {deleted} 条")

    return stats


# ---------------------------------------------------------------------------
# 数据库辅助函数
# ---------------------------------------------------------------------------

async def _get_document_by_source_id(session: AsyncSession, source_id: str) -> Optional[Document]:
    result = await session.execute(
        select(Document).where(Document.source_id == source_id)
    )
    return result.scalar_one_or_none()


async def _upsert_document(session: AsyncSession, data: dict) -> uuid.UUID:
    """upsert document，返回其 id。"""
    stmt = (
        pg_insert(Document)
        .values(**data)
        .on_conflict_do_update(
            index_elements=["source_id"],
            set_={k: v for k, v in data.items() if k != "source_id"},
        )
        .returning(Document.id)
    )
    result = await session.execute(stmt)
    await session.commit()
    return result.scalar_one()


async def _delete_chunks_by_doc(session: AsyncSession, doc_id: uuid.UUID) -> None:
    await session.execute(
        delete(DocumentChunk).where(DocumentChunk.document_id == doc_id)
    )
    await session.commit()


async def _delete_orphan_documents(
    session: AsyncSession,
    valid_source_ids: set[str],
) -> int:
    """删除 source_id 不在 valid_source_ids 中的文档（及其 chunk，通过 CASCADE）。"""
    if not valid_source_ids:
        return 0

    result = await session.execute(select(Document.source_id))
    all_source_ids = {row[0] for row in result.fetchall()}

    orphans = all_source_ids - valid_source_ids
    if not orphans:
        return 0

    await session.execute(
        delete(Document).where(Document.source_id.in_(orphans))
    )
    await session.commit()
    return len(orphans)


# ---------------------------------------------------------------------------
# 入口
# ---------------------------------------------------------------------------

async def main(force: bool = False, dry_run: bool = False) -> None:
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        print("错误：未设置 DATABASE_URL 环境变量，请检查 .env 文件")
        sys.exit(1)

    print(f"连接数据库：{database_url.split('@')[-1]}")  # 只打印 host 部分，不打印密码

    engine = create_async_engine(database_url, echo=False, pool_pre_ping=True)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    mode_label = ""
    if dry_run:
        mode_label = " [DRY RUN - 不写入数据库]"
    elif force:
        mode_label = " [FORCE - 忽略 hash 缓存]"

    print(f"\n=== 知识库导入{mode_label} ===")

    try:
        stats = await ingest_all(engine, session_factory, force=force, dry_run=dry_run)
    finally:
        await engine.dispose()

    # 打印报告
    print("\n=== 导入报告 ===")
    print(f"  扫描文件数      : {stats['files_scanned']}")
    print(f"  过滤跳过        : {stats['files_skipped_filter']}")
    print(f"  hash 未变化跳过 : {stats['files_skipped_hash']}")
    print(f"  实际处理文件数  : {stats['files_processed']}")
    if not dry_run:
        print(f"  新增/更新 chunk : {stats['chunks_new']}")
        print(f"  删除孤儿文档    : {stats['docs_deleted']}")
    if stats["errors"]:
        print(f"  错误数          : {stats['errors']}")
    print()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="知识库导入脚本")
    parser.add_argument("--force", action="store_true", help="忽略 hash 缓存，强制重建所有 chunk")
    parser.add_argument("--dry-run", action="store_true", help="只解析验证，不写入数据库")
    args = parser.parse_args()

    asyncio.run(main(force=args.force, dry_run=args.dry_run))
