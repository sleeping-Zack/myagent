# 6. 核心项目一：智扫通机器人智能客服 Agent

- 仓库：https://github.com/sleeping-Zack/agentproject
- 时间：2025.10—至今
- 性质：个人主导项目
- 定位：第一主项目、技术深度项目

## 项目背景

面向扫地和扫拖机器人的故障排查、维护保养、选购咨询、环境适配、设备使用记录查询和个性化报告生成，构建 RAG + 多工具 Agent + Harness 控制层系统。

项目重点不是只完成问答，而是解决 Agent 在真实应用中的可控性问题：

- 执行步骤是否受限
- 工具调用是否越权
- 敏感数据是否需要人工审批
- Token、成本和时间是否超限
- 最终回答是否有证据
- 失败过程能否被追踪和复盘

## 技术栈

Python、FastAPI、Pydantic、LangChain、ReAct Agent、Chroma、SQLite、pytest、SSE、MCP JSON-RPC、BM25、RRF、Cross-Encoder Reranker、Qwen、Trace、Artifact、Metrics。

## 架构分层

### 执行面

- ReactAgent
- LangChain ReAct
- RAG Service
- 工具函数与数据服务
- 会话记忆

### 控制面

- AgentRunner
- AgentState
- BudgetManager
- ToolPolicy
- ApprovalStore
- AnswerVerifier
- ArtifactStore
- Diagnostic Trace

### 接入面

- FastAPI
- Streamlit
- MCP stdio / HTTP
- SSE 事件流

### 治理面

- API Key 鉴权
- tenant / role / principal 可信上下文
- 限流
- Prompt Injection 检测
- 检索内容安全检查
- Trace / Metrics
- 离线评测与 CI 门禁

## RAG 检索链路

1. 将机器人领域 PDF / TXT 文档切分为 Chunk。
2. 使用 Embedding 模型生成向量并存入 Chroma。
3. Dense 召回覆盖语义相关内容。
4. BM25 补足型号、部件名和精确词匹配。
5. RRF 融合双路排名。
6. 可选 Cross-Encoder Reranker 精排。
7. 返回结构化 Evidence 与引用来源。
8. 将证据交给模型生成回答。

## 当前离线结果

当前简历记录：

- 6 份领域文档
- 326 个 Chunk
- 30 条冻结检索测试样本
- Recall@5：80.6% → 93.3%
- MRR：0.878 → 0.933
- nDCG@5：0.768 → 0.904
- Hybrid 检索 P95：385ms

这些数据属于小规模离线评测结果，用于证明方案改进方向，不等同于真实线上大规模效果。

## Harness 控制层

### AgentRunner / AgentState

统一维护 request_id、session_id、tenant_id、user_role、scene、steps、observations、tool_calls、artifacts 和 status。

### BudgetManager

支持最大步骤数、最大工具调用数、Token、成本和 Deadline 五类约束。模型或工具调用前预留预算，执行后提交实际用量，失败时释放。

### ToolPolicy

依据 tenant、role、scene、tool 和 args 返回 allow、deny、need_approval 或 need_redaction。

### HITL

敏感工具请求进入 SQLiteApprovalStore，审批后再次校验工具、参数和租户，避免从其他入口绕过控制面。

### AnswerVerifier

检查 Evidence、引用、空答案、Claim 与证据对齐和高风险结论，必要时调用 LLM Judge。

## 测试与可观测

- pytest + FakeBackend
- Agent Golden Set
- Retrieval Golden Set
- Tool Recall
- Keyword Recall
- 拒答率
- P95 延迟
- 平均成本
- failure bucket
- Trace
- Artifact
- Prometheus 风格 Metrics
- CI smoke 与评测门禁

## 个人贡献

负责需求拆解、总体架构、RAG 混合检索、Agent Harness、工具权限、HITL、答案验证、Trace、Artifact、评测脚本、测试、CI 和持续迭代。

## 项目价值

证明候选人不只会调用模型和向量库，也能够处理 Agent 的权限、预算、安全、质量和可观测问题。

## 局限

- 当前主要为单机工程验证。
- 离线样本规模有限。
- 缺少真实业务用户量、SLA 和商业指标。
- 生产环境仍需更完善的身份系统、集中存储和分布式追踪。

---
