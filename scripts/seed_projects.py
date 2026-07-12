#!/usr/bin/env python3
"""
初始化 projects 表数据

用法：
    python scripts/seed_projects.py
    python scripts/seed_projects.py --clear  # 清空后重建
"""

import argparse
import asyncio
import sys
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import delete, text
from app.models.project import Project
from app.core.config import settings

PROJECTS = [
    {
        "slug": "agentproject",
        "title": "智扫通机器人智能客服 Agent",
        "one_liner": "面向扫地机器人故障排查与维护的 RAG + 多工具 Agent + Harness 控制层系统，重点解决 Agent 可控性问题。",
        "project_type": "个人主导项目",
        "role_summary": "AI 应用开发 / Agent 开发，负责需求拆解、总体架构、RAG 混合检索、Agent Harness、工具权限、HITL、答案验证、Trace、Artifact、评测脚本、测试和 CI。",
        "tech_stack": ["Python", "FastAPI", "LangChain", "ReAct Agent", "Chroma", "BM25", "RRF", "Cross-Encoder Reranker", "MCP", "SSE", "pytest", "SQLite"],
        "status": "active",
        "visibility": "public",
        "start_date": date(2025, 10, 1),
        "end_date": None,
        "sort_order": 1,
    },
    {
        "slug": "farino",
        "title": "法奥机器人智能客服平台",
        "one_liner": "基于 AIFlowy 的企业级二次开发，构建机器人技术咨询 Agent 客服工作台，覆盖 Agent 路由、动态规划、QA 数据沉淀和售后工单。",
        "project_type": "南昌大学 × 法奥机器人校企合作",
        "role_summary": "Agent 后端开发 / AI 应用开发，负责 Direct/Agentic 两级路由、Agent 动态规划模块、QA 数据闭环模块、售后工单流程和私有化部署。",
        "tech_stack": ["Java", "Spring Boot", "Vue 3", "TypeScript", "MySQL", "Redis", "AIFlowy", "MCP", "SSE", "Docker Compose", "Nginx"],
        "status": "completed",
        "visibility": "public",
        "start_date": date(2026, 1, 1),
        "end_date": date(2026, 6, 30),
        "sort_order": 2,
    },
    {
        "slug": "myagent",
        "title": "朱旭个人招聘知识 Agent",
        "one_liner": "面向 HR 和技术面试官的个人知识问答网站，基于 pgvector + DeepSeek 构建 RAG 服务，支持流式对话和引用溯源。",
        "project_type": "个人项目",
        "role_summary": "AI 应用开发 / Python 后端，负责产品定位、网站架构、数据模型、RAG 流程、DeepSeek 接入、pgvector 检索、SSE、Docker Compose 和上线排障。",
        "tech_stack": ["Python", "FastAPI", "PostgreSQL", "pgvector", "DeepSeek", "BGE Embedding", "SQLAlchemy Async", "Alembic", "SSE", "Docker Compose", "Nginx"],
        "status": "active",
        "visibility": "public",
        "start_date": date(2026, 7, 1),
        "end_date": None,
        "sort_order": 3,
    },
    {
        "slug": "mood_tracker",
        "title": "情绪分析日记与 AI 心情助手",
        "one_liner": "面向大学生日记场景的中文情绪五分类系统，使用传统机器学习模型本地推理，集成 Django Web 应用。",
        "project_type": "个人机器学习项目",
        "role_summary": "机器学习与 Django 应用开发，负责数据处理、TF-IDF 特征工程、多模型训练对比、评估分析和 Django 集成。",
        "tech_stack": ["Python", "scikit-learn", "jieba", "TF-IDF", "Django", "SQLite", "pandas", "Matplotlib"],
        "status": "completed",
        "visibility": "public",
        "start_date": None,
        "end_date": None,
        "sort_order": 4,
    },
]


async def seed(clear: bool = False):
    engine = create_async_engine(settings.database_url, echo=False)
    async_session = async_sessionmaker(engine, expire_on_commit=False)

    async with async_session() as session:
        if clear:
            await session.execute(delete(Project))
            await session.commit()
            print("已清空 projects 表")

        for data in PROJECTS:
            # 已存在则跳过
            from sqlalchemy import select
            result = await session.execute(select(Project).where(Project.slug == data["slug"]))
            existing = result.scalar_one_or_none()
            if existing:
                # 更新
                for k, v in data.items():
                    setattr(existing, k, v)
                print(f"更新: {data['title']}")
            else:
                project = Project(**data)
                session.add(project)
                print(f"新增: {data['title']}")

        await session.commit()
        print("完成")

    await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--clear", action="store_true", help="清空后重建")
    args = parser.parse_args()
    asyncio.run(seed(clear=args.clear))
