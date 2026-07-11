---
id: project-agentproject-responsibilities
title: 智扫通机器人智能客服 Agent 个人职责
type: project
project_slug: agentproject
section: responsibility
visibility: public
confidence: confirmed
importance: flagship
tags: [Agent, Harness, RAG, 个人职责, 独立完成]
updated_at: 2026-07-11
---

# 个人职责

本项目为个人独立完成，以下各模块均由本人负责设计和实现。

## 需求拆解与架构设计

将业务需求（售后问答、设备查询、报告生成）转化为技术模块边界，设计执行面 / 控制面 / 接入面 / 治理面四层架构。

## RAG 混合检索链路

- PDF / TXT 文档加载与 Chunk 切分
- Chroma 向量库存储
- Dense 向量召回 + BM25 召回 + RRF 融合
- 可选 BGE Reranker 精排
- RAG 注入过滤
- Evidence 和引用来源返回
- Retrieval Golden Set 标注流水线
- dev / test 确定性划分
- Recall、MRR、nDCG 评测脚本

## Agent Harness 控制层

- AgentRunner / AgentState：统一维护 request_id、session_id、tenant_id、user_role、scene、budget、steps、observations、tool_calls、artifacts、status
- BudgetManager：max_steps / max_tool_calls / max_tokens / max_cost / deadline 五类约束，调用前预留、调用后提交、失败释放
- ToolPolicy：依据 scene / user_role / tenant_id / tool_name / args / risk 返回 allow / deny / need_approval / need_redaction
- ApprovalStore（HITL）：敏感工具进入审批队列，operator / admin 批准或拒绝，防止绕过控制面
- AnswerVerifier：检查 evidence、引用、空答案、工具结果有效性，失败时保存 verification_failure artifact

## 可观测与评测

- Diagnostic Trace（request / tool / model 三级）
- Artifact 保存最终答案、工具结果和失败信息
- Prometheus 风格 Metrics
- Agent Golden Set + tool_recall + keyword_recall + 拒答率 + P95 延迟 + 平均成本
- pytest + FakeBackend 确定性测试
- CI smoke / EvalGate

## 安全与稳定性

- API Key 鉴权
- 租户级限流
- Prompt Injection 检测
- 检索内容污染扫描
- Semantic Cache（相似度阈值 0.92）
- 审批角色校验 + 跨租户隔离
- 懒加载模型（避免 CI 无 Key 时导入失败）

## 个人贡献口径

> 我负责项目的需求拆解、总体架构、RAG 混合检索、Harness 控制层、工具治理、审批、答案验证、Trace、Artifact、评测脚本、测试和 CI 集成。开发中使用 Claude、Cursor 辅助部分代码生成和重构，但核心方案、模块整合、问题定位和最终验证由我负责。
