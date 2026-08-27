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
from textwrap import dedent

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import delete
from app.models.project import Project
from app.core.config import settings
from app.core.html_sanitizer import safe_url, sanitize_html


AGENTPROJECT_HTML = dedent("""
<h2>项目简介</h2>
<p>面向扫地 / 扫拖机器人的 <strong>RAG + 多工具 Agent + Harness 控制层</strong> 系统。项目不仅覆盖知识库问答、天气与环境适配、用户设备使用记录查询、个性化报告生成，还把 Agent 生产化中常见的可控性问题纳入架构：统一状态、预算停止、动态工具策略、真实人工审批、答案验证、artifact 留存、诊断 trace、评测门禁和服务化交付。</p>
<blockquote><p><code>ReactAgent</code> 负责 ReAct 推理和工具调用，<code>AgentRunner</code> 负责请求级控制；工具、RAG、MCP、审批、artifact、trace、metrics 都围绕 Harness 形成可治理的 Agent 运行框架。</p></blockquote>

<h2>核心功能</h2>
<ul>
  <li><strong>RAG 知识库</strong>：从 PDF / TXT 构建 Chroma 向量库，Dense 向量分数与中文 BM25 双路召回，经 RRF 融合与可选 Cross-Encoder 精排后生成 evidence 与引用。</li>
  <li><strong>多工具 Agent</strong>：支持知识库检索、天气、用户位置、用户 ID、当前月份、使用记录查询和报告上下文切换。</li>
  <li><strong>Harness 控制层</strong>：统一 <code>AgentRunner</code> / <code>AgentState</code>，支持 Direct / ReAct / Plan-Execute 路由、共享预算、动态工具策略、真实审批、答案验证、artifact 存储和诊断 trace。</li>
  <li><strong>共享预算</strong>：<code>BudgetManager</code> 默认限制 8 steps、8 tool calls 和 32k tokens，通过 reserve / commit / release 避免并发调用超卖。</li>
  <li><strong>动态工具治理</strong>：<code>ToolRegistry</code> 管工具元数据，<code>ToolPolicy</code> 从版本化 YAML 加载 tenant / role / scene / tool / args 规则，输出可审计的 <code>allow / deny / need_approval / need_redaction</code> 决策。</li>
  <li><strong>真实 HITL 审批</strong>：敏感工具进入 <code>SQLiteApprovalStore</code>，普通用户需审批，operator / admin 可审批。</li>
  <li><strong>答案质量闸门</strong>：<code>AnswerVerifier</code> 依次执行结构校验、Claim-Evidence 对齐与危险结论检测，仅在高风险或低置信时调用 <code>LLMJudge</code>。</li>
  <li><strong>产物留存</strong>：<code>SQLiteArtifactStore</code> 按 request_id 保存 final answer、verification failure、evidence、tool results 等运行产物。</li>
  <li><strong>MCP 工具服务</strong>：支持 JSON-RPC <code>initialize</code>、<code>tools/list</code>、<code>tools/call</code>；MCP 工具调用同样经过 ToolPolicy 和审批存储。</li>
  <li><strong>可观测性</strong>：包含 request / tool / model trace、diagnostic event、OpenTelemetry 风格 span、Prometheus 指标，以及带序号、心跳、背压和断线重放的实时 SSE 事件流。</li>
  <li><strong>评测门禁</strong>：PR 固定运行 30 条检索、12 条生成和 62 条 Agent 回归，校验绝对阈值与版本化 baseline；600+ Pytest 用例覆盖审批、重试、超时、熔断降级和 SSE 时序。</li>
  <li><strong>多实例服务</strong>：支持 SQLite / PostgreSQL 存储切换、Redis Streams 事件重放与共享限流缓存，并通过 OpenTelemetry 导出请求级链路。</li>
</ul>

<h2>系统架构</h2>
<p>整体分为四个层面：</p>
<ul>
  <li><strong>执行面</strong>：<code>TaskRouter</code>、Direct / ReAct / Plan-Execute、工具、RAG、数据服务。</li>
  <li><strong>控制面</strong>：<code>AgentRunner</code>、<code>AgentState</code>、<code>Budget</code>、<code>ToolPolicy</code>、审批、Verifier、Artifact、Diagnostic Trace。</li>
  <li><strong>接入面</strong>：FastAPI（<code>/chat</code>、<code>/chat/stream</code>、<code>/harness/run</code>、审批、artifact、MCP、trace、metrics、judge）、Streamlit、MCP stdio / HTTP。</li>
  <li><strong>治理面</strong>：API Key 鉴权、租户 / 角色 / principal 可信上下文、限流、Prompt Injection 检测、metrics、trace、评测门禁。</li>
</ul>

<h2>个人负责</h2>
<ul>
  <li>作为个人开源项目作者 / 维护者，完成执行 / 控制 / 接入 / 治理四层架构拆分。</li>
  <li>RAG 双路召回、RRF 融合与 Cross-Encoder 精排链路。</li>
  <li>Harness 控制层：AgentState 状态机、Budget、动态工具策略、审批、Verifier、Artifact、Trace 整套实现。</li>
  <li>ToolPolicy 版本化 YAML 规则引擎和可审计决策输出。</li>
  <li>MCP JSON-RPC 服务与 <code>fetch_external_data</code> 等敏感工具的审批门。</li>
  <li>FastAPI 全部 HTTP / SSE 接口、事件序号与断线重放。</li>
  <li>Prometheus / OpenTelemetry 风格 metrics、trace 采集。</li>
  <li>评测门禁：检索排名冻结集 + Agent golden，CI 阈值与基线比对。</li>
</ul>

<h2>项目价值</h2>
<p>项目重点解决 Agent 生产化过程中普遍存在的可控性问题：让工具调用、审批、答案验证、观测、评测都成为可治理的一等公民，而不是散落在应用代码里的旁支能力。</p>
""").strip()


FARINO_HTML = dedent("""
<h2>项目简介</h2>
<p>南昌大学与法奥机器人校企合作智能客服平台，面向机器人技术咨询、资料检索与售后服务，基于 <strong>AIFlowy 进行企业级二次开发</strong>。个人贡献集中在 RAG 评测、可观测链路、Human-in-the-loop QA 闭环，以及既有 Plan-Execute 的中日双语扩展。</p>

<h2>核心功能</h2>

<h3>1. RAG Gold Dataset 与证据对齐</h3>
<p>围绕 FAIRINO v3.9.1 用户手册构建 <strong>168 条 / 26 类 Gold Dataset</strong>（164 可答、4 拒答）与 <strong>79 个页级证据块</strong>：</p>
<ul>
  <li>以稳定 chunk ID 对齐手册物理页码、证据片段与标准答案。</li>
  <li>覆盖事实查询、操作步骤、故障处理、参数约束、拒答和版本混淆等 26 类问题。</li>
  <li>保留可追溯的 reference chunk，为检索、生成和引用评测提供统一基准。</li>
</ul>

<h3>2. RAG 可观测评测链路</h3>
<p>建立检索、上下文、生成、引用、拒答、安全与性能 7 层评测，通过 SSE Trace 输出召回、重排、最终上下文和引用证据，统计并归因：</p>
<ul>
  <li>Recall、Precision、MRR、nDCG 等检索指标。</li>
  <li>Claim Coverage、Faithfulness 与引用准确率。</li>
  <li>拒答、安全、P50 / P95 延迟和 Token 消耗。</li>
  <li>自动生成评测摘要和 Bad Case 报告。</li>
</ul>

<h3>3. Human-in-the-loop QA 闭环</h3>
<p>从 0 到 1 打通历史对话到可回灌知识资产的 QA 闭环：</p>
<ul>
  <li>按 Bot 与时间窗抽取并配对 User→Assistant 消息。</li>
  <li>基于源消息 ID 幂等去重，过滤空内容、系统错误和噪声。</li>
  <li>支持人工复核、标签筛选和 Markdown 批量导出。</li>
</ul>

<h3>4. Plan-Execute 中日双语扩展</h3>
<p>在既有 Plan-Execute 架构上增加语言检测与约束，将其贯穿规划、执行、校验和兜底流程，同时兼容 JSON / 纯文本历史消息，保证多轮售后对话语言一致。</p>

<h2>技术栈</h2>
<ul>
  <li><strong>后端</strong>：Java 17、Spring Boot 3.5、Agents-Flex、TinyFlow、MyBatis-Flex、MySQL、Redis、SSE。</li>
  <li><strong>评测</strong>：Python、RAG Gold Dataset、Recall / MRR / nDCG、Faithfulness、Citation、Bad Case Analysis。</li>
  <li><strong>前端</strong>：Vue 3、TypeScript、Vite、Pinia、Element Plus、pnpm、Turbo。</li>
  <li><strong>Agent 与模型</strong>：Qwen、知识库 RAG、Workflow、Plugin、MCP、Plan-Execute。</li>
</ul>

<h2>贡献边界</h2>
<p>该项目是在 AIFlowy 现有平台基础上的企业级二次开发。个人角色为 <strong>Agent / RAG 核心开发（RAG 评测与 QA 闭环负责人）</strong>；AIFlowy 平台基础能力及 Plan-Execute 核心架构不归为个人独立成果。</p>
""").strip()


MYAGENT_HTML = dedent("""
<h2>项目简介</h2>
<p>面向 HR 和技术面试官的<strong>个人招聘知识 Agent 网站</strong>。通过自然语言对话展示个人项目经历、技能和教育背景，后端使用 FastAPI + DeepSeek LLM，向量检索基于 pgvector，前端支持 SSE 流式输出。</p>

<h2>核心能力</h2>
<ul>
  <li><strong>RAG 问答</strong>：从 <code>knowledge/</code> 中的 Markdown 文档构建 pgvector 向量库，检索相关片段后调用 DeepSeek 生成引用式回答。</li>
  <li><strong>SSE 流式输出</strong>：Token 逐字返回，附带引用来源列表，用户可点击溯源到原文档。</li>
  <li><strong>项目展示</strong>：独立 Projects 页面，支持每个项目的详情页、技术栈标签和跳转到 AI 深度问答。</li>
  <li><strong>反馈闭环</strong>：<code>question_feedback</code> 表记录用户对回答的评分与原因，为知识库迭代提供依据。</li>
  <li><strong>会话记录</strong>：<code>conversations</code> / <code>messages</code> 表持久化对话上下文，支持多轮追问。</li>
</ul>

<h2>系统架构</h2>
<ul>
  <li><strong>Web 服务</strong>：FastAPI + Jinja2 模板，路由拆分为 pages / chat / projects / feedback / health。</li>
  <li><strong>数据层</strong>：SQLAlchemy 2 async + Alembic 迁移，PostgreSQL 16 + pgvector 扩展承载向量与业务数据。</li>
  <li><strong>RAG 流程</strong>：<code>ingest_knowledge.py</code> 分块 → BGE-small-zh-v1.5 本地 embedding → pgvector 存储；查询时召回 Top-K 片段 → 拼装 prompt → DeepSeek 生成 → 引用回填。</li>
  <li><strong>部署</strong>：Docker Compose 编排 Postgres、Web、Nginx；Nginx 反向代理并处理 TLS 证书；HTTP 自动重定向至 HTTPS。</li>
</ul>

<h2>目录结构</h2>
<pre><code>personal-agent/
├── app/          # FastAPI 应用（API、services、repositories、core）
├── deploy/       # Nginx 配置、TLS 证书
├── knowledge/    # 知识库 Markdown 源文件
├── migrations/   # Alembic 数据库迁移
├── models/       # 本地 embedding 模型（bge-small-zh-v1.5）
├── scripts/      # 知识库导入等运维脚本
├── static/       # 前端静态资源
├── templates/    # Jinja2 HTML 模板
└── tests/        # pytest 测试及评测题集
</code></pre>

<h2>技术栈</h2>
<ul>
  <li><strong>后端</strong>：Python 3.11、FastAPI、SQLAlchemy 2（async）、Alembic。</li>
  <li><strong>LLM</strong>：DeepSeek API。</li>
  <li><strong>向量检索</strong>：pgvector、BGE-small-zh-v1.5 本地 embedding。</li>
  <li><strong>数据库</strong>：PostgreSQL 16。</li>
  <li><strong>前端</strong>：Jinja2 模板、Server-Sent Events（SSE）流式输出、Tailwind CSS。</li>
  <li><strong>部署</strong>：Docker Compose、Nginx（TLS 反向代理）。</li>
</ul>

<h2>项目价值</h2>
<p>该项目将招聘场景中的常见问题（HR 面、技术面、项目细节、简历要点）沉淀到可检索的知识库，通过 Agent 形式让访客随时提问、按需深挖，替代静态简历页的单向展示。同时作为 RAG + FastAPI + pgvector 全链路的端到端实践载体。</p>
""").strip()


MOOD_TRACKER_HTML = dedent("""
<h2>项目简介</h2>
<p>在保留原 Django 情绪日记网页交互层与 SQLite 数据库的前提下，把"情绪识别内核"从原先依赖 Hugging Face API 的在线推理升级为完全本地的<strong>传统机器学习五分类系统</strong>：<code>jieba</code> 分词 + <code>TfidfVectorizer</code> 特征 + <code>MultinomialNB / LogisticRegression / LinearSVC</code> 分类器 + <code>joblib</code> 持久化 + <code>views.py</code> 调用 <code>predict_emotion()</code>。</p>
<p>当前推理、入库和展示都以五分类为准：<strong>难过、焦虑、生气、平静、开心</strong>。</p>

<h2>技术路线</h2>
<pre><code>现有 Django 项目
    └── 文本提交 (mood/views.py)
            └── ml.predict.predict_emotion(text)
                    ├── ml.preprocess.segment_text   # jieba + 停用词 + 自定义词典
                    ├── joblib.load(tfidf_vectorizer.joblib)
                    └── joblib.load(lr_model.joblib)  # LinearSVC / LogisticRegression
            └── MoodEntry.objects.create(...)
            └── 渲染 templates/mood/index.html
</code></pre>

<h2>五分类标签规范</h2>
<ul>
  <li><code>0 → 难过</code>（sad，score = -2）</li>
  <li><code>1 → 焦虑</code>（anxious，score = -1）</li>
  <li><code>2 → 生气</code>（angry，score = -2）</li>
  <li><code>3 → 平静</code>（calm，score = 0）</li>
  <li><code>4 → 开心</code>（happy，score = +2）</li>
</ul>
<p>主训练数据来自 Hugging Face <code>zzhdbw/Simplified_Chinese_Multi-Emotion_Dialogue_Dataset</code>。公开数据集里没有焦虑类，因此另外手工补了约 260 条<strong>大学生日记焦虑样本</strong>（期末、答辩、PPT、项目 DDL、老师检查、代码调不通等）。</p>

<h2>端到端流程</h2>
<ol>
  <li><strong>数据准备</strong>：五分类语料整合 + 焦虑样本补全，8:1:1 分层切分。</li>
  <li><strong>预处理与特征</strong>：Unicode 清洗、jieba 分词、自定义词典、停用词过滤、TF-IDF Unigram + Bigram 向量化。</li>
  <li><strong>模型训练</strong>：Naive Bayes、Logistic Regression、LinearSVC 三个分类器同数据同特征训练；LR / SVC 使用 <code>class_weight=balanced</code> 处理类别不均衡。</li>
  <li><strong>评估</strong>：测试集 Accuracy、Macro-F1、Weighted-F1、五分类混淆矩阵与误分类样本分析。</li>
  <li><strong>持久化</strong>：joblib 保存向量器与模型，Django 进程内懒加载复用。</li>
  <li><strong>拓展实验</strong>：Hugging Face API 作为对照基线，K-Means / LSA + K-Means 作为无监督拓展（非默认推理链路）。</li>
</ol>

<h2>离线评估结果</h2>
<p>在 430 条独立测试样本上，当前 LinearSVC 的离线结果：</p>
<ul>
  <li>Accuracy：<strong>91.86%</strong></li>
  <li>Macro-F1：<strong>92.08%</strong></li>
  <li>Weighted-F1：<strong>91.84%</strong></li>
</ul>
<p>以上指标仅代表当前数据集和划分方式下的小规模离线实验结果，不等同于开放场景下的实际效果。</p>

<h2>Django 集成</h2>
<p>用户在文本框写入心情并提交后，<code>mood/views.py</code> 调用 <code>predict_emotion(text)</code>，得到五分类结果与所用模型信息，写入 <code>MoodEntry</code> 后重定向回首页展示：</p>
<ul>
  <li>本次分析结果：文本、五分类中文情绪、所用模型、分析时间、趋势分值、建议语句。</li>
  <li>心情趋势图：基于 <code>display_score</code> 字段绘制，y 轴范围 <code>-2 ~ +2</code>。</li>
  <li>历史记录列表：所有 <code>MoodEntry</code> 按时间倒序。</li>
</ul>

<h2>技术栈</h2>
<p>Python、scikit-learn、pandas、jieba、TF-IDF、MultinomialNB、LogisticRegression、LinearSVC、joblib、Django 5.2、SQLite、Matplotlib、datasets。</p>

<h2>项目定位</h2>
<p>该项目体现了从数据准备、文本预处理、特征工程、模型训练、离线评估到 Web 应用集成的完整传统机器学习流程，是候选人机器学习基础项目的展示载体。机器学习并非当前主要求职方向，核心方向仍是 Agent、RAG 和 AI 应用后端。</p>
""").strip()


PROJECTS = [
    {
        "slug": "agentproject",
        "title": "智能硬件客服可治理 Agent 平台",
        "one_liner": "以 ReactAgent 为执行面、AgentRunner Harness 为控制面，统一路由、预算、审批、证据验证、Trace 与评测门禁。",
        "project_type": "个人开源项目",
        "role_summary": "个人开源项目作者 / 维护者，负责总体架构、RAG 混合检索、Agent Harness、工具权限、HITL、答案验证、Trace、Artifact、服务化和 CI。",
        "tech_stack": ["Python", "FastAPI", "LangChain/LangGraph", "Chroma", "BM25", "RRF", "PostgreSQL", "Redis", "MCP", "SSE", "OpenTelemetry", "Pytest"],
        "status": "运行中",
        "visibility": "public",
        "start_date": date(2025, 12, 1),
        "end_date": None,
        "sort_order": 1,
        "duration": "2025.12 — 至今",
        "is_featured": True,
        "cover_image": "/static/images/projects/agentproject.svg",
        "content_html": AGENTPROJECT_HTML,
        "related_links": [
            {"label": "GitHub 仓库", "url": "https://github.com/sleeping-Zack/agentproject"},
        ],
    },
    {
        "slug": "farino",
        "title": "法奥机器人智能客服平台",
        "one_liner": "基于 AIFlowy 的企业级二次开发，负责 168 条 / 26 类 Gold Dataset、7 层 RAG 评测、QA 闭环与中日双语链路。",
        "project_type": "南昌大学 × 法奥机器人校企合作",
        "role_summary": "Agent / RAG 核心开发（RAG 评测与 QA 闭环负责人），并扩展既有 Plan-Execute 中日双语链路。",
        "tech_stack": ["Java 17", "Spring Boot 3.5", "Agents-Flex", "TinyFlow", "MyBatis-Flex", "Python", "Vue 3", "MySQL", "Redis", "SSE", "Docker", "Qwen"],
        "status": "已完成",
        "visibility": "public",
        "start_date": date(2026, 1, 1),
        "end_date": date(2026, 8, 4),
        "sort_order": 2,
        "duration": "2026.01 — 2026.08",
        "is_featured": True,
        "cover_image": "/static/images/projects/farino.svg",
        "content_html": FARINO_HTML,
        "related_links": [
            {"label": "GitHub 仓库", "url": "https://github.com/sleeping-Zack/farino"},
        ],
    },
    {
        "slug": "myagent",
        "title": "朱旭个人招聘知识 Agent",
        "one_liner": "面向 HR 和技术面试官的个人知识问答网站，基于 pgvector + DeepSeek 构建 RAG 服务，支持流式对话和引用溯源。",
        "project_type": "个人项目",
        "role_summary": "AI 应用开发 / Python 后端，负责产品定位、网站架构、数据模型、RAG 流程、DeepSeek 接入、pgvector 检索、SSE、Docker Compose 和上线排障。",
        "tech_stack": ["Python 3.11", "FastAPI", "PostgreSQL 16", "pgvector", "DeepSeek", "BGE Embedding", "SQLAlchemy Async", "Alembic", "SSE", "Docker Compose", "Nginx"],
        "status": "运行中",
        "visibility": "public",
        "start_date": date(2026, 7, 1),
        "end_date": None,
        "sort_order": 3,
        "duration": "2026.07 — 至今",
        "is_featured": False,
        "cover_image": "/static/images/projects/myagent.svg",
        "content_html": MYAGENT_HTML,
        "related_links": [
            {"label": "GitHub 仓库", "url": "https://github.com/sleeping-Zack/myagent"},
        ],
    },
    {
        "slug": "mood_tracker",
        "title": "情绪分析日记与 AI 心情助手",
        "one_liner": "面向大学生日记场景的中文情绪五分类系统，使用传统机器学习模型本地推理，集成 Django Web 应用。",
        "project_type": "个人机器学习项目",
        "role_summary": "机器学习与 Django 应用开发，负责数据处理、TF-IDF 特征工程、多模型训练对比、评估分析和 Django 集成。",
        "tech_stack": ["Python", "scikit-learn", "jieba", "TF-IDF", "LinearSVC", "LogisticRegression", "Django 5.2", "SQLite", "pandas", "Matplotlib"],
        "status": "已完成",
        "visibility": "public",
        "start_date": None,
        "end_date": None,
        "sort_order": 4,
        "duration": "机器学习课程项目",
        "is_featured": False,
        "cover_image": "/static/images/projects/mood_tracker.svg",
        "content_html": MOOD_TRACKER_HTML,
        "related_links": [
            {"label": "GitHub 仓库", "url": "https://github.com/sleeping-Zack/mood_tracker"},
        ],
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

        for project_data in PROJECTS:
            data = {
                **project_data,
                "content_html": sanitize_html(project_data.get("content_html")),
                "related_links": [
                    {**link, "url": safe_url(link.get("url"))}
                    for link in project_data.get("related_links", [])
                    if safe_url(link.get("url"))
                ],
            }
            from sqlalchemy import select
            result = await session.execute(select(Project).where(Project.slug == data["slug"]))
            existing = result.scalar_one_or_none()
            if existing:
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
