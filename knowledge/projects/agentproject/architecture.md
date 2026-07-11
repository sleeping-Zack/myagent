---
id: project-agentproject-architecture
title: 智扫通机器人智能客服 Agent 技术架构
type: project
project_slug: agentproject
section: architecture
visibility: public
confidence: confirmed
importance: flagship
tags: [Agent, Harness, RAG, FastAPI, LangChain, 架构, ReAct]
updated_at: 2026-07-11
---

# 技术架构

## 四层分离设计

### 执行面

负责推理和工具调用，由 LangChain ReAct 驱动：

- ReactAgent：ReAct 循环，Thought → Action → Observation
- RAG Service：混合检索，返回 Evidence 和引用
- Tool Data Service：具体工具实现（查询设备记录、生成报告等）
- Conversation Memory：会话上下文管理

### 控制面

独立于执行面，负责确定性治理规则：

- AgentRunner：协调执行面和控制面，维护完整 AgentState
- AgentTask / AgentState：请求生命周期内的所有状态
- BudgetManager：调用前预留资源，防止执行后才发现超限
- ToolPolicy：细粒度权限控制，依据角色、场景和工具风险决策
- ApprovalStore（HITL）：敏感工具的人工审批队列
- AnswerVerifier：回答质量门禁，无证据则拒答
- ArtifactStore：最终答案、工具结果和失败信息的持久化

### 接入面

- FastAPI：RESTful API + SSE 流式输出
- Streamlit：本地演示 UI
- MCP stdio / HTTP：标准协议工具接入

### 治理面

- API Key 鉴权
- tenant / role / principal 多租户隔离
- 租户级限流
- Prompt Injection 检测
- Trace / Metrics
- 离线评测和 CI 门禁

## RAG 检索流程

```
用户问题
→ Dense 向量召回（Chroma）
→ BM25 召回
→ RRF 融合排序
→ 可选 BGE Reranker 精排
→ RAG 注入过滤
→ 返回 Top-K Evidence + 引用来源
```

## Agent 执行流程（含控制面）

```
请求进入 AgentRunner
→ 初始化 AgentState（budget、policy、approval）
→ ReactAgent 开始 ReAct 循环
  → Thought：推理下一步
  → Action：选择工具
    → ToolPolicy 检查（allow / deny / need_approval）
    → BudgetManager 预留
    → 若需审批：进入 ApprovalStore 等待
    → 工具执行
    → BudgetManager 提交
  → Observation：记录结果
→ 生成最终答案
→ AnswerVerifier 检查证据
→ ArtifactStore 保存
→ Trace 记录
→ SSE 流式返回
```
