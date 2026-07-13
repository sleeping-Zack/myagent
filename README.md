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

## 对话历史与记忆

- 首次访问会签发仅浏览器持有的 `HttpOnly` 匿名会话 Cookie；服务端只保存令牌哈希。
- 每个访客可创建多条独立对话，刷新后可从左侧历史记录恢复；不同访客无法读取彼此的会话 UUID。
- 每条对话同一时间只允许一个回答生成，并通过 `client_message_id` 防止重复提交。
- 模型上下文由滚动摘要、最近消息和当前问题检索到的知识证据组成，不会把其他对话的内容混入当前记忆。
- 匿名会话和对话默认保留 30 天；清除浏览器 Cookie 后无法继续访问原历史。

历史接口位于 `/api/v1/conversations`，支持列表、新建、读取消息、重命名和软删除。

## 知识库导入

```bash
# 容器运行后执行一次性导入
docker compose exec web python scripts/ingest_knowledge.py
```

## RAG 检索评测

冻结题集位于 `tests/rag_golden_set.json`。服务和数据库启动后运行：

```bash
docker compose exec web python scripts/evaluate_rag.py
```

结果会写入 `static/evaluation/latest.json`，并展示在 `/evaluation` 页面。Recall@5 的口径是每个问题的 Top 5 结果至少命中一个预先标注的可接受来源。

## 健康检查

- `/health/live`：进程存活检查。
- `/health/ready`：数据库、Embedding 配置和模型配置就绪检查；仅返回总体状态。

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
