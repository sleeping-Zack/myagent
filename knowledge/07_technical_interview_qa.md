# 技术面试问答

## 智扫通项目为什么不只使用纯向量检索

纯向量检索擅长语义匹配，但对型号、部件名和精确术语的召回可能不足。因此项目采用 Dense 与 BM25 双路召回，再通过 RRF 融合排名，并可选 Cross-Encoder Reranker 进行精排。

## RRF 的作用是什么

RRF 不直接比较不同检索器的原始分数，而是依据各自排名进行融合，降低 Dense 相似度和 BM25 分数尺度不一致带来的问题。

## Harness 控制层解决什么问题

Harness 位于 ReAct 执行逻辑之外，统一管理状态、预算、工具权限、人工审批、答案验证、Trace 和 Artifact，使 Agent 执行过程具备更明确的边界和可追踪性。

## BudgetManager 控制哪些资源

控制最大步骤数、最大工具调用数、Token、成本和 Deadline。调用前预留预算，执行后提交实际消耗，失败时释放预留。

## ToolPolicy 有哪些结果

根据 tenant、role、scene、tool 和 args，返回 allow、deny、need_approval 或 need_redaction。

## HITL 如何防止绕过

敏感调用先进入 ApprovalStore。审批后再次校验工具、参数和租户上下文，确保审批记录只能恢复对应请求，不能跨租户或替换参数执行。

## 如何验证最终回答

AnswerVerifier 检查证据、引用、空答案、Claim 与 Evidence 对齐以及高风险结论。必要时使用 LLM Judge，但不将 Judge 作为唯一评测手段。

## 法奥项目中的 Direct / Agentic 路由是什么

简单寒暄和普通问答通过 Direct 链路直接交给对话模型；需要知识库、Workflow、插件或 MCP 的复杂请求进入 Agentic 链路，减少不必要的完整 Agent 执行开销。

## 法奥项目的动态规划做了什么

根据用户问题和 Bot 已绑定能力生成 3—5 步计划，并校验工具类型、工具 ID、参数结构和必填项。执行状态通过 SSE 同步给前端。

## QA 数据闭环如何实现

从历史会话中完成 User–Assistant 消息配对、低质量过滤、消息 ID 幂等去重、原始快照保留、人工编辑审核和 Markdown 批量导出，支持优质问答回流知识库。

## 个人知识 Agent 为什么使用 pgvector

个人知识、项目、Chunk、会话和反馈均需要关系型数据管理，同时需要向量检索。PostgreSQL + pgvector 能在同一数据体系中完成结构化查询和向量召回。

## 个人知识 Agent 如何避免没有证据时编造

检索后先判断证据是否充分。证据不足时采用保守拒答；证据充分时先通过 SSE 返回来源，再调用模型生成并保存引用信息。

## Mood Tracker 的机器学习流程是什么

公开数据和补充样本经过标签映射、分层切分、文本清洗、jieba 分词和停用词过滤，再使用 TF-IDF 构建特征，训练 MultinomialNB、LogisticRegression 和 LinearSVC。最终依据验证集 Macro-F1 选择默认模型，并在测试集上输出混淆矩阵和误分类样本。

## Mood Tracker 能否证明深度学习能力

不能。该项目证明的是传统机器学习文本分类、数据处理、模型评估和 Web 集成能力。Hugging Face 仅作为对照基线，不应扩大为深度学习训练经验。
