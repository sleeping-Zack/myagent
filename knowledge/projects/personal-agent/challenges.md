---
id: project-agentproject-challenges
title: 智扫通机器人智能客服 Agent 技术挑战与取舍
type: project
project_slug: agentproject
section: challenges
visibility: public
confidence: self_reported
importance: flagship
repository: https://github.com/sleeping-Zack/agentproject
updated_at: 2026-07-11
tags: [Agent, Harness, RAG, HITL, Evaluation, FakeBackend]
---

# 智扫通机器人智能客服 Agent 技术挑战与取舍

## 1. 为什么在 ReAct 外面还要增加 Harness

ReAct 负责模型驱动的推理和工具调用，但不天然解决权限、预算、审批、证据、成本和审计问题。

问题来源：

- 模型可能在 Prompt 指示下仍然超出授权范围调用工具
- 没有外部限制时，多轮工具调用会无上限消耗 Token 和成本
- 没有独立审批流时，敏感操作无法人工干预
- 没有 AnswerVerifier 时，空答案和无来源答案会直接透出

解决方案：将这些非确定性执行之外的规则集中到确定性控制面（Harness），与 LLM 推理解耦。

## 2. BudgetManager 为什么采用预留机制

朴素做法：在每次工具调用后扣减预算。问题是，如果多次调用并发，或者在一次循环的最后才检查，可能在执行完成后才发现早已超限。

改进：调用前预留额度，调用成功后提交实际用量，调用失败则释放预留。这样可以保证剩余额度在调用之前就已足够。

## 3. ToolPolicy 如何防止绕过

工具权限必须在模型之外由代码执行，不能依赖 Prompt。原因：

- 模型可能忽略或被 Prompt Injection 攻击影响
- MCP 等外部入口如果不经过同一 ToolPolicy，会绕过治理边界

实现要点：MCP `tools/call` 与 HTTP 调用走同一 ToolPolicy 和 ApprovalStore，入口不能决定是否跳过权限校验。

## 4. HITL 如何设计恢复流程

挑战：审批是异步的，执行面在等待审批期间不能阻塞。

设计：

1. 敏感工具请求写入 ApprovalStore，状态 pending_approval
2. AgentRunner 检测到 pending_approval 时暂停执行，返回等待状态给前端
3. operator / admin 通过审批端点批准或拒绝
4. 审批后校验租户、工具名和参数，再恢复 AgentRunner 执行
5. 防止跨租户审批（租户隔离校验）

## 5. Evidence 如何从 RAG 回流到 Verifier

RAG Service 检索到的 Chunk 列表作为 evidence_ids 写入 AgentState，模型生成回答时将这些 evidence 传入 Prompt。AnswerVerifier 校验最终回答中是否存在有效引用，不存在则判定为验证失败。

## 6. 如何构建 Retrieval Golden Set 避免自证循环

问题：用候选分数或答案关键词自动标注，会把当前检索逻辑当成真值，无法真实评价相关性。

流程：

1. 固定语料和版本
2. Dense、BM25、Hybrid 生成候选并集
3. 人工进行 0—3 级相关性标注
4. 校验标注完整性
5. 固定随机种子划分 dev/test
6. 计算 Recall、MRR、nDCG

## 7. 为什么使用 FakeBackend 做测试

大模型调用有成本、延迟和随机性，无法直接用于确定性测试。

FakeBackend 可以：

- 注入预设的工具调用序列和模型回答
- 确定性覆盖状态机（blocked / rejected / completed 各分支）
- 覆盖预算超限、审批等待、验证失败等边缘状态
- 不产生 API 费用，CI 环境无 Key 时同样可运行

## 8. Semantic Cache 的错误复用风险

Semantic Cache 使用相似度阈值 0.92 判断是否命中。

风险：两个看似相似但实际语义不同的问题（例如"扫地机器人适合瓷砖吗"和"扫地机器人适合地毯吗"）可能被错误命中。

缓解：

- 阈值宁高勿低（0.92 偏严格）
- Cache Key 包含 tenant_id 和 scene，避免跨租户复用
- 对敏感工具的调用结果不进入 Cache

## 9. Prompt Injection 和检索污染的区别

- Prompt Injection：恶意指令通过用户输入注入，影响模型行为
- 检索污染：恶意内容混入知识库，模型在生成时引用被污染的 Chunk

两者防御层不同：前者在 Prompt 层过滤用户输入，后者在检索层扫描 Chunk 内容。

## 10. 已知局限

- Chroma 和 SQLite 适合单机作品，不代表分布式生产架构
- 缺少真实用户量、SLA、业务转化和线上成本数据
- `/chat/stream` 当前实现更接近 SSE 事件外观，需区分完整 Token 级流式
- 标注集和 Golden Set 仍偏小，30 条样本只能用于快速回归，不足以证明广泛泛化
- 依赖外部模型 API（DashScope / Qwen3-Max）
- 生产环境仍需 JWT、集中存储、消息队列、分布式追踪和密钥管理
