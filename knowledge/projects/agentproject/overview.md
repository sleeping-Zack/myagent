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

## 项目性质

个人主导，独立完成需求拆解、总体架构、RAG 检索链路、Harness 控制层、工具治理、评测脚本和 CI 集成。开发中使用 Claude、Cursor 辅助部分代码生成和重构，但核心方案、模块整合、问题定位和最终验证由本人负责。

## 技术栈

- Python 3.10
- FastAPI + Pydantic
- Streamlit
- LangChain ReAct Agent
- Chroma 向量库
- SQLite
- pytest + FakeBackend
- SSE
- MCP JSON-RPC
- Prometheus 风格 Metrics
- OpenTelemetry 风格 Trace
- Qwen3-Max / DashScope
- text-embedding-v4
- BM25、RRF、可选 BGE Reranker
