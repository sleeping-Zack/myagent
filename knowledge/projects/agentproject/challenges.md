---
id: project-agentproject-challenges
title: 智扫通机器人智能客服 Agent 技术挑战与取舍
type: project
project_slug: agentproject
section: challenges
visibility: public
confidence: confirmed
importance: high
tags: [Agent, Harness, ReAct, 技术取舍, 已知局限]
updated_at: 2026-07-11
---

# 技术挑战与关键取舍

## 为什么 ReAct 外还需要 Harness

ReAct 负责模型的推理和工具调用，但不天然解决：

- 工具权限（哪些角色可以调用哪些工具）
- 预算（Token、成本、步骤上限）
- 审批（敏感操作需要人工介入）
- 证据验证（回答必须有来源支撑）
- 成本审计（每次调用的费用追踪）

Harness 将这些规则集中到确定性控制面，与 ReAct 执行面解耦。

## 为什么预算要"预留"

如果等执行结束再检查是否超限，已产生的费用无法撤销。BudgetManager 在每次工具调用前预留资源，失败时释放，确保不会因并发或连续调用而意外超出预算。

## 为什么 ToolPolicy 要防绕过

Agent 可以通过多个接入点调用工具（FastAPI、MCP、Streamlit）。如果权限检查在各接入点单独实现，容易遗漏或不一致。ToolPolicy 在控制面统一检查，任何入口的工具调用都必须经过同一套策略。

## 为什么评测需要人工标注 Golden Set

如果用模型自己的候选结果作相关性标签，会形成自证循环——模型越偏，标签越偏。因此将候选生成、人工判断和 Golden Set 拆分为独立流程。

## 为什么使用 FakeBackend

大模型调用有成本、延迟和随机性。FakeBackend 可以确定性地覆盖状态机（budget 超限、审批等待、验证失败）各种分支，不依赖真实 API 也能保证测试可重复。

## HITL 如何恢复执行

当工具调用进入 ApprovalStore 等待后：

1. 审批者（operator / admin）批准或拒绝
2. 批准后校验参数和租户一致性
3. AgentRunner 收到批准信号，从 pending_approval 状态恢复执行
4. 拒绝则工具调用失败，进入拒绝分支

## 已知局限

- Chroma 和 SQLite 适合单机演示，不代表分布式生产架构
- 缺少真实用户量、SLA、业务转化和线上成本数据
- 标注集和 Golden Set 仍偏小，指标需固定可复现实验
- 依赖外部模型 API（Qwen3-Max / DashScope）
- 生产环境仍需 JWT、集中存储、队列、分布式追踪和密钥管理
