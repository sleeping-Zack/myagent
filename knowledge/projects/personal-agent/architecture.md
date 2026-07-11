---
id: project-agentproject-architecture
title: 智扫通机器人智能客服 Agent 技术架构
type: project
project_slug: agentproject
section: architecture
visibility: public
confidence: confirmed
importance: flagship
repository: https://github.com/sleeping-Zack/agentproject
updated_at: 2026-07-11
tags: [Agent, RAG, Harness, FastAPI, LangChain, Chroma, MCP, HITL, Evaluation]
---

# 智扫通机器人智能客服 Agent 技术架构

## 技术栈

- Python 3.10
- FastAPI
- Pydantic
- Streamlit
- LangChain ReAct Agent
- Chroma
- SQLite
- pytest
- SSE
- MCP JSON-RPC
- Prometheus 风格 Metrics
- OpenTelemetry 风格 Trace
- Qwen3-Max / DashScope
- text-embedding-v4
- BM25、RRF、可选 BGE Reranker

## 架构分层

### 执行面

- ReactAgent
- LangChain ReAct
- RAG Service
- Tool Data Service
- Conversation Memory

### 控制面（Harness）

- AgentRunner
- AgentTask
- AgentState
- BudgetManager
- ToolPolicy
- ApprovalStore
- AnswerVerifier
- ArtifactStore
- Diagnostic Trace

### 接入面

- FastAPI HTTP API
- Streamlit 前端
- MCP stdio / HTTP

### 治理面

- API Key 鉴权
- tenant / role / principal 多租户模型
- 租户级限流
- Prompt Injection 检测
- Trace / Metrics
- 离线评测和 CI 门禁

## RAG 检索流程

公开代码和 README 可确认：

1. PDF / TXT 文档加载
2. Chroma 向量库存储
3. Dense 向量召回
4. BM25 召回
5. RRF 融合（不要求检索器分数同尺度，只用排名融合）
6. 可选 Reranker 精排（BGE Cross-Encoder，增加 Query—Document 交互）
7. RAG 注入过滤
8. Evidence 提取和引用来源标注
9. Retrieval Golden Set 标注流水线（dev/test 确定性划分）
10. Recall、MRR、nDCG 评测脚本

当前简历记录的检索数据（resume_current，需绑定固定 commit 和语料 manifest）：

- 6 份领域文档，326 个 Chunk，30 条独立测试样本
- Recall@5：80.6% → 93.3%
- MRR：0.878 → 0.933
- nDCG@5：0.768 → 0.904
- Hybrid 检索 P95：385ms

## Agent Harness 核心组件

### AgentRunner / AgentState

统一维护运行时状态：

| 字段 | 说明 |
|---|---|
| request_id | 唯一请求标识 |
| session_id | 会话标识 |
| tenant_id | 租户标识 |
| user_role | 用户角色 |
| scene | 业务场景 |
| budget | 预算对象 |
| steps | 已执行步骤 |
| observations | 工具观测结果 |
| tool_calls | 工具调用记录 |
| artifacts | 产物存储 |
| status | 运行状态（running / blocked / rejected / completed） |

### BudgetManager

五类约束：max_steps、max_tool_calls、max_tokens、max_cost、deadline

采用调用前预留、调用后提交、失败释放机制，避免执行结束后才发现超限。

### ToolPolicy

决策依据：scene、user_role、tenant_id、tool_name、args / risk

返回结果：allow / deny / need_approval / need_redaction

### ApprovalStore（HITL）

敏感工具请求进入 ApprovalStore：

1. 普通用户得到 pending_approval 响应
2. operator / admin 批准或拒绝
3. 审批后校验参数和租户
4. 防止 MCP 或其他入口绕过控制面

### AnswerVerifier

检查项目：是否存在 evidence、是否存在引用、是否空答案、工具结果是否有效、是否应重试或拒答。失败时保存 verification_failure artifact。

## 可观测体系

- request / tool / model 三层 Trace
- diagnostic event
- 记录字段：tokens、cost、evidence_ids、verifier、failure_reason
- ArtifactStore 保存 final answer、tool results 和失败信息
- Prometheus 风格 Metrics

### 评测指标

- Agent Golden Set：tool_recall、keyword_recall、拒答率、P95 延迟、平均成本、failure bucket
- pytest + FakeBackend 确定性回归
- CI smoke / EvalGate

当前简历记录（以仓库当前测试收集结果为最终依据）：

- 8 条在线 Agent Case
- 62 条确定性 Harness 回归用例
- 55 条 RAG Golden Set

## 安全与稳定性

- API Key 鉴权，租户级限流
- Prompt Injection 检测，检索内容污染扫描
- Semantic Cache，相似度阈值 0.92
- 审批角色校验，跨租户审批隔离
- 懒加载模型，避免 CI 无 Key 时导入失败
- 预算超限进入 blocked，验证失败进入 rejected
