---
id: project-agentproject-responsibilities
title: 智扫通机器人智能客服 Agent 个人职责
type: project
project_slug: agentproject
section: responsibility
visibility: public
confidence: confirmed
importance: flagship
repository: https://github.com/sleeping-Zack/agentproject
updated_at: 2026-07-11
tags: [Agent, RAG, Harness, FastAPI, LangChain, Chroma, HITL, Evaluation]
---

# 智扫通机器人智能客服 Agent 个人职责

## 个人贡献口径

推荐表述：

> 我负责项目的需求拆解、总体架构、RAG 混合检索、Harness 控制层、工具治理、审批、答案验证、Trace、Artifact、评测脚本、测试和 CI 集成。开发中使用 Claude、Cursor 辅助部分代码生成和重构，但核心方案、模块整合、问题定位和最终验证由我负责。

## 具体职责

### 需求拆解与架构设计

- 分析扫地机器人售后场景下的问答、咨询、记录查询和报告生成需求
- 设计执行面（ReactAgent）与控制面（AgentRunner 等）分离的整体架构
- 确定 Chroma + BM25 + RRF 混合检索方案

### RAG 混合检索

- 搭建 PDF / TXT 文档加载、Chunk、Embedding 写入 Chroma 的完整管道
- 实现 Dense 向量召回 + BM25 召回 + RRF 融合双路检索
- 集成可选 BGE Reranker 精排
- 设计 RAG 注入过滤、Evidence 提取和引用来源标注
- 搭建 Retrieval Golden Set 标注流水线，dev/test 确定性划分
- 实现 Recall、MRR、nDCG 等检索评测脚本

### Agent Harness 控制层

- 实现 AgentRunner / AgentState，统一维护 request_id、session_id、tenant_id、user_role、scene、budget、steps、observations、tool_calls、artifacts、status
- 实现 BudgetManager：调用前预留、调用后提交、失败释放，五类约束（max_steps、max_tool_calls、max_tokens、max_cost、deadline）
- 实现 ToolPolicy：依据 scene、user_role、tenant_id、tool_name、args/risk 返回 allow / deny / need_approval / need_redaction
- 实现 ApprovalStore 和 HITL 人工审批流程（pending → approve/deny → 校验 → 恢复执行）
- 实现 AnswerVerifier：检查 evidence、引用、空答案、工具结果有效性，失败时保存 verification_failure artifact
- 实现 ArtifactStore：保存 final answer、tool results 和失败信息

### 可观测与评测

- 设计 request / tool / model 三层 Trace 和 diagnostic event
- 记录 tokens、cost、evidence_ids、verifier、failure_reason
- 集成 Prometheus 风格 Metrics
- 搭建 Agent Golden Set（tool_recall、keyword_recall、拒答率、P95 延迟、平均成本、failure bucket）
- 实现 pytest + FakeBackend 确定性回归测试
- 配置 CI smoke 和 EvalGate 评测门禁

### 安全与稳定性

- API Key 鉴权、租户级限流
- Prompt Injection 检测、检索内容污染扫描
- Semantic Cache（相似度阈值 0.92）
- 审批角色校验和跨租户审批隔离
- 懒加载模型，避免 CI 无 Key 时导入失败
- 预算超限进入 blocked、验证失败进入 rejected 状态

### 接入与部署

- FastAPI HTTP 接口、Streamlit 前端、MCP stdio / HTTP 三类接入
- SSE 长连接实时推流
- CI 集成和基础自动化测试
