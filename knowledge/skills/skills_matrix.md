---
id: skills-matrix
title: 朱旭技能矩阵
type: skill
section: skills
visibility: public
confidence: confirmed
importance: high
tags: [Python, FastAPI, RAG, Agent, LangChain, LLM, 技能矩阵]
updated_at: 2026-07-11
---

# 技能矩阵

## 编程语言

| 技能 | 熟练度 | 说明 |
|---|---|---|
| Python | 熟悉 | 主力语言，用于 FastAPI、RAG、Agent、数据处理、测试 |
| Java | 基础阅读和二次开发 | 在 farino（AIFlowy）中完成 Spring Boot 模块二次开发，不宜表述为资深 |
| TypeScript / Vue | 基础阅读和二次开发 | 在 farino 中阅读和修改 Vue3 前端代码 |
| SQL | 熟悉 | MySQL 存储过程、触发器、事件调度；SQLite 应用存储 |

## Python 生态

| 技能 | 熟练度 | 说明 |
|---|---|---|
| FastAPI | 熟悉且有项目 | agentproject 后端主框架，包括 SSE、依赖注入、Pydantic 校验 |
| Pydantic | 熟悉且有项目 | 数据模型、请求/响应校验、配置管理 |
| Django | 有项目实践 | mood_tracker，ORM、视图、模板 |
| pytest | 熟悉且有项目 | agentproject 中 FakeBackend、单元测试、CI 集成 |
| Streamlit | 有项目实践 | agentproject 前端演示界面 |

## AI / LLM 应用

| 技能 | 熟练度 | 说明 |
|---|---|---|
| LangChain | 熟悉且有项目 | ReAct Agent、Chain、Tool Calling |
| RAG（混合检索） | 熟悉且有项目 | Dense + BM25 + RRF + 可选 Reranker，Evidence 和引用溯源 |
| Chroma | 有项目实践 | agentproject 向量库，PDf/TXT 入库、查询 |
| Embedding | 有项目实践 | text-embedding-v4（DashScope），Hugging Face Transformers |
| Qwen / DashScope | 有项目实践 | agentproject 主模型，Qwen3-Max |
| MCP JSON-RPC | 有项目实践 | agentproject MCP stdio / HTTP 接入 |
| Prompt Engineering | 熟悉 | 系统 Prompt 设计、Prompt Injection 检测、Prompt 版本管理 |

## Agent 工程化

| 技能 | 熟练度 | 说明 |
|---|---|---|
| ReAct Agent | 熟悉且有项目 | LangChain ReAct，执行面设计 |
| Agent Harness / 控制面 | 熟悉且有项目 | AgentRunner、BudgetManager、ToolPolicy、ApprovalStore、AnswerVerifier、ArtifactStore |
| HITL（Human-in-the-Loop） | 有项目实践 | 敏感工具审批，operator/admin 角色，跨租户隔离 |
| Trace / Metrics | 有项目实践 | OpenTelemetry 风格 Trace，Prometheus 风格 Metrics，Diagnostic Event |
| 离线评测 | 有项目实践 | Golden Set 标注、Recall/MRR/nDCG、CI EvalGate |
| Semantic Cache | 有项目实践 | 相似度阈值 0.92 缓存，防止错误复用 |

## 数据库

| 技能 | 熟练度 | 说明 |
|---|---|---|
| MySQL | 熟悉 | iot-platform，触发器、存储过程、事件调度、DRF API |
| SQLite | 有项目实践 | agentproject 应用存储，适合单机项目 |
| Redis | 了解或有项目使用 | farino 技术栈中使用，了解基本用法 |

## 基础设施 / 部署

| 技能 | 熟练度 | 说明 |
|---|---|---|
| Docker / Docker Compose | 了解或有项目使用 | farino 私有化部署编排 |
| Nginx | 了解或有项目使用 | farino SSE 长连接配置，反向代理 |
| SSE（Server-Sent Events） | 有项目实践 | agentproject 流式输出，farino 计划执行同步 |
| CI（GitHub Actions） | 有项目实践 | agentproject smoke 测试、EvalGate 门禁 |

## Java / Spring Boot（二次开发）

| 技能 | 熟练度 | 说明 |
|---|---|---|
| Spring Boot | 基础阅读和二次开发 | farino，能定位模块、理解请求链路、完成功能改造 |
| MyBatis-Flex | 基础阅读和二次开发 | farino ORM 层 |
| Vue 3 / TypeScript | 基础阅读和二次开发 | farino 前端，能修改组件和交互逻辑 |

## 早期项目涉及

| 技能 | 熟练度 | 说明 |
|---|---|---|
| Hugging Face Transformers | 有项目实践 | mood_tracker，RoBERTa 中文文本分类 |
| Matplotlib | 有项目实践 | mood_tracker 情绪趋势图 |
| Django ORM | 有项目实践 | mood_tracker 数据模型 |

## 技能边界说明

- **不使用"精通"**：任何技能均不标注精通
- **Java / Vue**：更接近项目阅读与二次开发，不宜表述为资深熟练
- **Redis / Docker / Nginx**：了解或有项目使用，需要以实际部署和排障案例支撑
- **AI 编程工具辅助**：使用 Claude、Cursor 辅助代码生成和重构，但核心方案、模块整合、问题定位和最终验证由本人负责，能解释和调试核心代码
