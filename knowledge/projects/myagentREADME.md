# 朱旭个人 Agent

基于 RAG 架构的个人知识问答 Agent，通过自然语言对话展示个人项目经历、技能和教育背景。后端使用 FastAPI + DeepSeek LLM，向量检索基于 pgvector，前端支持 SSE 流式输出。

## 快速启动

```bash
# 1. 复制环境变量模板并填写密钥
cp .env.example .env

# 2. 启动所有服务（PostgreSQL + pgvector、Web、Nginx）
docker compose up -d
```

服务启动后访问 http://localhost（Nginx 会自动将 HTTP 重定向至 HTTPS）。

## 知识库导入

```bash
# 容器运行后执行一次性导入
docker compose exec web python scripts/ingest_knowledge.py
```

## 目录结构

```
personal-agent/
├── app/          # FastAPI 应用（API、services、repositories、core）
├── deploy/       # Nginx 配置、TLS 证书（挂载路径）
├── knowledge/    # 知识库 JSON 源文件
├── migrations/   # Alembic 数据库迁移
├── models/       # 本地 embedding 模型（bge-small-zh-v1.5）
├── scripts/      # 知识库导入等运维脚本
├── static/       # 前端静态资源
├── templates/    # Jinja2 HTML 模板
└── tests/        # pytest 测试及评测题集
```

## 技术栈

- **后端**：Python 3.11、FastAPI、SQLAlchemy 2（async）、Alembic
- **LLM**：DeepSeek API（deepseek-v4-flash）
- **向量检索**：pgvector、BGE-small-zh-v1.5 本地 embedding
- **数据库**：PostgreSQL 16
- **前端**：Jinja2 模板、Server-Sent Events（SSE）流式输出
- **部署**：Docker Compose、Nginx（TLS 反向代理）
