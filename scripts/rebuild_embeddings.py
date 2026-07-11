#!/usr/bin/env python3
"""
强制重建所有 Embedding 脚本

忽略内容 hash 缓存，重新处理所有 knowledge/ 目录下的文档。
适用于更换 Embedding 模型后需要全量重建的场景。

等价于：python scripts/ingest_knowledge.py --force

用法：
    python scripts/rebuild_embeddings.py
"""

import asyncio
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# 直接复用 ingest_knowledge 的主逻辑
# 避免代码重复，仅改变 force=True 参数
from scripts.ingest_knowledge import main as ingest_main  # noqa: E402


if __name__ == "__main__":
    print("=== 强制重建所有 Embedding ===")
    print("此操作将重新处理所有知识文档，忽略内容缓存。")
    print("通常在更换 Embedding 模型后使用。\n")

    confirm = input("确认继续？(y/N): ").strip().lower()
    if confirm != "y":
        print("已取消")
        sys.exit(0)

    asyncio.run(ingest_main(force=True, dry_run=False))
