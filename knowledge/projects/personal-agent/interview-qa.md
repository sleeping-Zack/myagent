---
id: project-agentproject-interview-qa
title: 智扫通机器人智能客服 Agent 面试问答
type: project
project_slug: agentproject
section: interview-qa
visibility: public
confidence: self_reported
importance: flagship
repository: https://github.com/sleeping-Zack/agentproject
updated_at: 2026-07-11
tags: [Agent, Harness, RAG, HITL, Evaluation, 面试]
---

# 智扫通机器人智能客服 Agent 面试问答

## Q：这个项目解决了什么问题？

面向扫地和扫拖机器人售后问答、选购咨询、环境适配、设备使用记录查询和个性化报告生成。核心问题不是"如何接入模型"，而是"如何让 Agent 在生产中可控"——包括最多执行多少步、如何限制成本、哪些操作需要人工审批、最终答案是否有据可查。

## Q：项目架构是什么样的？

两层分离：

- **执行面**：ReactAgent（LangChain ReAct）负责思考和工具调用，RAG Service 提供检索，Tool Data Service 提供工具数据，Conversation Memory 维护上下文。
- **控制面**：AgentRunner 统一维护请求状态（request_id、session_id、tenant_id、user_role、scene、budget、status），BudgetManager 控制预算，ToolPolicy 控制权限，ApprovalStore 管理审批，AnswerVerifier 验证答案，ArtifactStore 留存产物，Trace 记录完整运行链路。

接入面包括 FastAPI、Streamlit 和 MCP stdio/HTTP。

## Q：RAG 检索是怎么做的？

混合检索：Dense 向量召回 + BM25 关键词召回，用 RRF（Reciprocal Rank Fusion）融合排名，可选 BGE Reranker 精排。

原因：纯 Dense 对型号、错误码等精确词效果弱；BM25 对词面匹配更敏感；RRF 不要求两路分数同尺度，只用排名融合。

当前简历数据：6 份领域文档，326 个 Chunk，30 条独立测试，Recall@5 从 80.6% 提升到 93.3%，MRR 0.878 → 0.933，nDCG@5 0.768 → 0.904，Hybrid 检索 P95 385ms。这些数字属于简历版本，仓库上线前应以固定 commit 的可复现实验为准。

## Q：Harness 和 ReAct 的边界在哪里？

ReAct 解决"怎么执行"，Harness 解决"执行边界是什么"。

- ReAct：模型决定何时思考、调用哪个工具、是否需要下一步
- Harness：预算多少、哪些工具允许哪些角色调用、敏感操作是否需要审批、最终答案是否有证据、失败如何处理

把控制逻辑写在 Prompt 里不可靠，模型可能忽略或被攻击影响。

## Q：BudgetManager 为什么要预留？

调用前预留，保证剩余额度足够；调用成功后提交实际用量；失败释放预留。避免在一次循环末尾才发现早已超限，或并发调用时过度消耗。

五类约束：max_steps、max_tool_calls、max_tokens、max_cost、deadline。

## Q：HITL 怎么实现？

1. ToolPolicy 返回 need_approval 时，写入 ApprovalStore，AgentRunner 状态设为 pending_approval
2. 前端收到 pending_approval 提示用户等待审批
3. operator / admin 通过审批端点批准或拒绝
4. 批准后校验 tenant_id、tool_name 和参数匹配，再恢复执行
5. 防止跨租户审批：批准只对同一 tenant 的请求有效

## Q：MCP 会不会绕过权限控制？

不会。MCP `tools/call` 必须进入同一 ToolPolicy 和 ApprovalStore。控制面与接入通道解耦，所有入口（FastAPI、Streamlit、MCP）都必须经过相同的权限校验层。

## Q：AnswerVerifier 检查什么？

- 是否存在 evidence（RAG 检索到的有效 Chunk）
- 是否存在引用标注
- 是否为空答案
- 工具结果是否有效
- 是否应该重试或拒答

验证失败时保存 verification_failure artifact，状态进入 rejected。

## Q：评测体系是什么？

三层：

1. **Retrieval**：Recall@5、MRR、nDCG@5，Golden Set 人工标注，dev/test 固定随机种子划分
2. **Agent**：tool_recall、keyword_recall、拒答率，8 条在线 Agent Case
3. **Harness 回归**：pytest + FakeBackend，62 条确定性用例，覆盖状态机、预算、审批、验证各分支

CI：smoke + EvalGate，指标低于阈值时拦截合并。

## Q：数据规模够说明问题吗？

坦率说：30 条 Retrieval 测试样本、8 条 Agent Case 只能用于快速回归和方向判断，不足以证明广泛泛化。需要扩大问题类型覆盖、增加独立 test set、做置信区间分析和 Bad Case 分类。这是当前已知短板，不在面试中回避。

## Q：项目的个人贡献范围？

负责需求拆解、总体架构、RAG 混合检索、Harness 控制层、工具治理、审批、答案验证、Trace、Artifact、评测脚本、测试和 CI 集成。开发中使用 Claude、Cursor 辅助部分代码生成和重构，但核心方案、模块整合、问题定位和最终验证由本人负责。

## Q：已知技术局限？

- Chroma 和 SQLite 适合单机作品，不代表分布式生产架构
- 缺少真实用户量、SLA、业务转化和线上成本数据
- 标注集和 Golden Set 仍偏小
- 依赖外部模型 API
- 生产还需 JWT、集中存储、消息队列、分布式追踪、密钥管理

## Q：如果要上生产，你会先做什么？

1. 把 SQLite 换成 PostgreSQL，Chroma 换成可分布式的向量库（如 Qdrant）
2. 增加 JWT 鉴权和集中密钥管理
3. 引入消息队列解耦异步操作
4. 扩充 Golden Set 到 200 条以上，建立持续评测流水线
5. 补充分布式追踪（OpenTelemetry）和告警
