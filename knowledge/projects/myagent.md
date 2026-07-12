# 8. 核心项目三：朱旭个人招聘知识 Agent

- 仓库：https://github.com/sleeping-Zack/myagent
- 时间：2026.07—至今
- 性质：个人项目
- 定位：产品化、RAG 服务化与部署能力项目

## 项目背景

面向 HR 和技术面试官构建个人知识问答网站。访问者可以询问教育背景、实习经历、项目职责、技术能力、项目取舍和岗位匹配情况。

## 技术栈

Python、FastAPI、SQLAlchemy 2 Async、asyncpg、Alembic、PostgreSQL 16、pgvector、DeepSeek API、BGE Embedding、Jinja2、SSE、Docker Compose、Nginx、TLS、pytest、structlog。

## 系统组成

### 页面

首页、项目列表、项目详情、Agent 对话页、简历页、关于页面。

### API

- `/api/v1/chat`
- 项目查询
- 消息反馈
- 健康检查

### 服务层

- EmbeddingService
- RetrievalService
- CitationService
- DeepSeekService
- ConversationService
- RagService

### 数据层

PostgreSQL、pgvector、SQLAlchemy Async、Alembic，存储项目、文档、Chunk、会话、消息和反馈。

## RAG 回答流程

1. 校验空问题和长度。
2. 检测 API Key、私有 IP、PEM 等敏感内容模式。
3. 将问题转换为向量。
4. 在 pgvector 中检索公开且可信的数据。
5. 在向量召回基础上叠加标题、标签和项目相关权重。
6. 判断证据是否充分。
7. 证据不足时保守拒答。
8. 先通过 SSE 返回 source 事件。
9. 加载最近 6 条对话上下文。
10. 调用 DeepSeek 流式生成。
11. 保存答案、引用、模型、Token 和延迟。
12. 支持用户反馈。

## Embedding

支持本地 BGE 模型和兼容 OpenAI Embeddings 接口的 API 模式，可使用 SiliconFlow 的 BGE 中文 Embedding 服务，降低服务器本地推理负担。

## 部署

Docker Compose 编排 Web、PostgreSQL + pgvector 和 Nginx，支持健康检查、环境变量、静态资源、知识库挂载、TLS 和 SSE 长连接。

## 个人贡献

负责产品定位、网站架构、数据模型、RAG 流程、DeepSeek 接入、Embedding 接入、pgvector 检索、SSE、Docker Compose、Nginx、知识库整理和上线排障。

## 项目价值

证明能够把个人知识库做成真实可访问产品，覆盖 RAG、API、数据库、流式交互、页面、部署、日志和反馈。

## 局限

- 当前是早期 MVP。
- 检索融合和阈值仍需继续评测。
- 个人事实需要版本化维护。
- 需要补充自动回归评测与更完整限流。

---
