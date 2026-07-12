#!/usr/bin/env python3
"""
将 knowledge/zhuxu_personal_knowledge_base.zip 解压并重组为知识库目录结构。
执行后 knowledge/ 目录将包含新版知识库文件，可直接运行 ingest_knowledge.py。
"""
import zipfile
import shutil
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
KNOWLEDGE_DIR = PROJECT_ROOT / "knowledge"
ZIP_PATH = KNOWLEDGE_DIR / "zhuxu_personal_knowledge_base.zip"
EXTRACT_DIR = PROJECT_ROOT / "_kb_extract_tmp"

def main():
    if not ZIP_PATH.exists():
        print(f"找不到压缩包：{ZIP_PATH}")
        return

    # 解压到临时目录
    if EXTRACT_DIR.exists():
        shutil.rmtree(EXTRACT_DIR)
    EXTRACT_DIR.mkdir()

    with zipfile.ZipFile(ZIP_PATH, "r") as z:
        z.extractall(EXTRACT_DIR)
    print("解压完成")

    # 找到解压后的根目录
    subdirs = list(EXTRACT_DIR.iterdir())
    kb_root = subdirs[0] if len(subdirs) == 1 and subdirs[0].is_dir() else EXTRACT_DIR

    # 备份旧知识库（保留 zip 文件）
    backup_dir = PROJECT_ROOT / "_kb_backup"
    if backup_dir.exists():
        shutil.rmtree(backup_dir)
    backup_dir.mkdir()
    for item in KNOWLEDGE_DIR.iterdir():
        if item.name != "zhuxu_personal_knowledge_base.zip":
            dest = backup_dir / item.name
            if item.is_dir():
                shutil.copytree(item, dest)
            else:
                shutil.copy2(item, dest)
    print(f"旧知识库已备份到 {backup_dir}")

    # 清空旧知识库（保留 zip）
    for item in KNOWLEDGE_DIR.iterdir():
        if item.name != "zhuxu_personal_knowledge_base.zip":
            if item.is_dir():
                shutil.rmtree(item)
            else:
                item.unlink()

    # 复制新文件到 knowledge/
    for item in kb_root.iterdir():
        dest = KNOWLEDGE_DIR / item.name
        if item.is_dir():
            shutil.copytree(item, dest)
        else:
            shutil.copy2(item, dest)
    print("新知识库文件已写入 knowledge/")

    # 清理临时目录
    shutil.rmtree(EXTRACT_DIR)

    # 列出新结构
    print("\n新知识库结构：")
    for p in sorted(KNOWLEDGE_DIR.rglob("*.md")):
        print(f"  {p.relative_to(KNOWLEDGE_DIR)}")

if __name__ == "__main__":
    main()
