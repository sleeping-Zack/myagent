---
id: project-agentproject-interview-qa
title: 智扫通机器人智能客服 Agent 面试问答
type: project
project_slug: agentproject
section: interview_qa
visibility: public
confidence: confirmed
importance: high
tags: [Agent, Harness, RAG, 面试, 技术问答]
updated_at: 2026-07-11
---

# 面试常见问题与口径

## Q: 这个项目和普通 RAG 问答有什么区别？

普通 RAG 问答只解决"检索 + 生成"，本项目在此基础上增加了：

- 多工具 Agent：不只是问答，还能查询设备记录、生成报告
- Harness 控制层：权限、预算、审批、验证、Trace 等治理能力
- 离线评测体系：Golden Set、FakeBackend、CI 门禁

差异化在于从功能原型推进到"可治理"的工程系统。

## Q: ReAct 和 Harness 的边界在哪里？

- ReAct（执行面）：模型推理下一步该做什么、选择哪个工具、观察结果
- Harness（控制面）：规定能做什么、做多少、谁能做、做完后是否合格

两者完全解耦，ReAct 不知道 Harness 存在，Harness 通过拦截工具调用来执行规则。

## Q: ToolPolicy 具体怎么防绕过？

无论请求来自 FastAPI、MCP 还是 Streamlit，工具调用都经过同一个 ToolPolicy 实例检查。ToolPolicy 依据 `scene / user_role / tenant_id / tool_name / risk` 返回决策，不在各接入点分别实现，消除遗漏可能。

## Q: BudgetManager 为什么要预留而不是事后检查？

事后检查无法撤销已产生的费用。预留机制在工具调用前锁定资源，执行失败则释放，并发场景下也不会超限。

## Q: HITL 审批后如何恢复执行？

工具调用进入 ApprovalStore 后 Agent 进入 pending_approval 状态暂停。审批者操作后，AgentRunner 轮询或接收通知，批准则校验参数一致性后继续执行，拒绝则进入拒绝分支并记录到 ArtifactStore。

## Q: Evidence 怎么从 RAG 回流到 AnswerVerifier？

RAG Service 返回的每条结果都携带 evidence_id 和引用来源。这些 evidence_id 随 AgentState 传递到最终回答生成阶段，AnswerVerifier 检查最终答案是否包含有效引用，无引用则拒答并保存失败 Artifact。

## Q: 评测的 Golden Set 怎么构建？

1. 运行检索，收集候选结果
2. 人工判断每条候选是否相关（避免自证循环）
3. 将人工标注固定为 Golden Set
4. 每次评测对比当前结果与 Golden Set，计算 Recall / MRR / nDCG

## Q: 小样本指标怎么避免误导？

明确说明测试集规模，不用小样本上的精确小数点营造虚假精度，评测报告绑定固定 commit 和数据文件，确保可复现。当前数据集仍偏小，这是已知局限。

## Q: SQLite / Chroma 如何演进到生产组件？

SQLite → PostgreSQL（会话、审批、Artifact）；Chroma → pgvector 或 Milvus（向量检索）；本地文件 → 对象存储（Artifact）；进程内 Metrics → Prometheus + Grafana。架构层已按这个方向预留接口。

## Q: Semantic Cache 的错误复用风险？

如果阈值过低，语义相似但实际不同的问题会复用旧答案。当前阈值 0.92 较严格，但仍需定期审查缓存命中案例，发现错误复用时降低阈值或针对特定 query 类型禁用缓存。
