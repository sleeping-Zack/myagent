# 风险与一致性检查

## 经历性质

- 长冈医疗科技有限公司：正式嵌入式实习。
- 法奥机器人智能客服平台：校企合作。
- Agentproject、Myagent、Mood Tracker：个人项目。

## Farino 贡献边界

必须说明基于 AIFlowy 二次开发。知识库、Workflow、插件和平台基础能力不能描述为个人从零实现。

## Agentproject 指标边界

当前离线指标必须同时说明：

- 6 份领域文档
- 326 个 Chunk
- 30 条冻结检索测试样本
- Recall@5、MRR、nDCG@5 和 P95 均属于小规模离线结果

不得替换为真实线上用户效果。

## Mood Tracker 表述边界

默认推理链路是：

`jieba → TF-IDF → MultinomialNB / LogisticRegression / LinearSVC`

不得继续写成 RoBERTa 三分类主流程。Hugging Face 只作为对照基线。

## 机器学习能力边界

机器学习经验主要来自一个传统文本分类项目，不描述为：

- 精通机器学习
- 深度学习模型训练
- 算法研究
- 机器学习平台建设
- 机器学习算法工程师级能力

## 通用风险

- 不虚构线上流量、SLA、收入、医院落地或企业用户数量。
- 不声称所有代码完全手写。
- 不将 AI 工具辅助隐瞒为完全独立编码。
- 不使用“精通”描述技术栈。
