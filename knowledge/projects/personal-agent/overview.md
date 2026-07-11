---
id: project-agentproject-overview
title: 智扫通机器人智能客服 Agent 概述
type: project
project_slug: agentproject
section: overview
visibility: public
confidence: confirmed
importance: flagship
repository: https://github.com/sleeping-Zack/agentproject
period: 2025.10-至今
status: ongoing
tags: [Agent, RAG, Harness, FastAPI, LangChain, Chroma, MCP, HITL, Evaluation, Python]
updated_at: 2026-07-11
---

# 智扫通机器人智能客服 Agent 概述

## 项目定位

面向扫地和扫拖机器人售后问答、选购咨询、环境适配、设备使用记录查询和个性化报告生成的 **RAG + 多工具 Agent + Harness 控制层**项目。

项目不止实现问答，而是集中解决 Agent 应用中的运行边界：

- 最多执行多少步骤
- 最多调用多少工具
- Token、成本和时间如何限制
- 哪些角色可以调用哪些工具
- 敏感数据何时需要人工审批
- 最终回答是否有证据
- 失败和中间产物如何留存
- 如何追踪、评测和复盘

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

## 项目性质

这是朱旭个人主导的工程化 AI 应用项目，从 RAG 知识库问答起步，逐步演进为具备治理控制面的 Agent 系统。开发中使用 Claude、Cursor 辅助部分代码生成和重构，但核心方案、模块整合、问题定位和最终验证由朱旭负责。

## 一句话定位

将 ReAct 执行面和请求级控制面分离，通过 AgentRunner、BudgetManager、ToolPolicy、ApprovalStore、AnswerVerifier、ArtifactStore 和 Trace 对 Agent 的权限、成本、质量和可追溯性进行治理。
