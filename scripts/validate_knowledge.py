#!/usr/bin/env python3
"""
知识库验证脚本

只做验证，不写数据库。检查：
1. 所有 .md 文件是否有 Front Matter
2. 必填字段是否完整
3. id 是否唯一

用法：
    python scripts/validate_knowledge.py
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
KNOWLEDGE_DIR = PROJECT_ROOT / "knowledge"

REQUIRED_FIELDS = {"id", "title", "type", "visibility", "confidence"}
VALID_TYPES = {"profile", "project", "skill", "experience", "faq"}
VALID_VISIBILITY = {"public", "private"}
VALID_CONFIDENCE = {"confirmed", "self_reported", "unverified"}


def parse_front_matter(text: str) -> dict:
    """简单解析 YAML Front Matter，返回字段字典（值均为字符串或列表）。"""
    if not text.startswith("---"):
        return {}

    end = text.find("\n---", 3)
    if end == -1:
        return {}

    yaml_block = text[3:end].strip()
    meta = {}
    current_key = None
    list_items = []
    in_list = False

    for line in yaml_block.splitlines():
        if line.startswith("  - ") or line.startswith("- "):
            item = line.lstrip("- ").strip()
            list_items.append(item)
            in_list = True
            continue

        if ":" in line:
            if in_list and current_key:
                meta[current_key] = list_items[:]
                list_items = []
                in_list = False

            key, _, val = line.partition(":")
            key = key.strip()
            val = val.strip().strip("'\"")
            current_key = key
            if val:
                meta[key] = val
            in_list = False

    if in_list and current_key:
        meta[current_key] = list_items

    return meta


def validate_all() -> bool:
    """
    验证所有 .md 文件。
    返回 True 表示全部通过，False 表示有错误。
    """
    md_files = sorted(KNOWLEDGE_DIR.rglob("*.md"))

    if not md_files:
        print("警告：knowledge/ 目录下没有找到任何 .md 文件")
        return True

    print(f"扫描 {len(md_files)} 个文件...\n")

    errors: list[str] = []
    warnings: list[str] = []
    seen_ids: dict[str, str] = {}  # id -> file path

    for md_path in md_files:
        rel = str(md_path.relative_to(PROJECT_ROOT)).replace("\\", "/")

        try:
            raw = md_path.read_text(encoding="utf-8")
        except Exception as e:
            errors.append(f"{rel}: 读取失败 - {e}")
            continue

        # 检查 Front Matter 存在
        if not raw.startswith("---"):
            errors.append(f"{rel}: 缺少 Front Matter（文件不以 --- 开头）")
            continue

        meta = parse_front_matter(raw)

        if not meta:
            errors.append(f"{rel}: Front Matter 解析失败或为空")
            continue

        # 必填字段
        missing = REQUIRED_FIELDS - set(meta.keys())
        for field in sorted(missing):
            errors.append(f"{rel}: 缺少必填字段 '{field}'")

        # id 唯一性
        doc_id = meta.get("id")
        if doc_id:
            if doc_id in seen_ids:
                errors.append(
                    f"{rel}: id '{doc_id}' 重复（另一个文件：{seen_ids[doc_id]}）"
                )
            else:
                seen_ids[doc_id] = rel
        else:
            errors.append(f"{rel}: id 字段为空")

        # type 合法性
        doc_type = meta.get("type")
        if doc_type and doc_type not in VALID_TYPES:
            warnings.append(
                f"{rel}: type='{doc_type}' 不在已知类型列表 {VALID_TYPES} 中"
            )

        # visibility 合法性
        visibility = meta.get("visibility")
        if visibility and visibility not in VALID_VISIBILITY:
            errors.append(
                f"{rel}: visibility='{visibility}' 不合法，应为 {VALID_VISIBILITY}"
            )

        # confidence 合法性
        confidence = meta.get("confidence")
        if confidence and confidence not in VALID_CONFIDENCE:
            errors.append(
                f"{rel}: confidence='{confidence}' 不合法，应为 {VALID_CONFIDENCE}"
            )

        # 正文内容不能为空
        end = raw.find("\n---", 3)
        body = raw[end + 4:].strip() if end != -1 else ""
        if not body:
            warnings.append(f"{rel}: 正文内容为空")

    # 打印结果
    if warnings:
        print("=== 警告 ===")
        for w in warnings:
            print(f"  警告  {w}")
        print()

    if errors:
        print("=== 错误 ===")
        for e in errors:
            print(f"  错误  {e}")
        print()
        print(f"验证失败：{len(errors)} 个错误，{len(warnings)} 个警告")
        return False

    print(f"验证通过：{len(md_files)} 个文件，{len(warnings)} 个警告，id 均唯一")
    return True


if __name__ == "__main__":
    ok = validate_all()
    sys.exit(0 if ok else 1)
