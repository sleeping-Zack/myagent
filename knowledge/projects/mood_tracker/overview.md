---
id: project-mood-tracker
title: 情绪分析日记与 AI 心情助手
type: project
project_slug: mood_tracker
section: overview
visibility: public
confidence: confirmed
importance: medium
repository: https://github.com/sleeping-Zack/mood_tracker
status: early_project
tags: [Django, NLP, Transformers, RoBERTa, Matplotlib]
updated_at: 2026-07-11
---

# 情绪分析日记与 AI 心情助手

## 项目定位

用户输入日记或情绪文本，系统分析情绪、保存记录、绘制趋势图，并返回激励语录。

完整链路：输入 → 模型推理 → 业务判断 → 数据库存储 → 趋势可视化 → 页面反馈

## 技术栈

- Python、Django、Django ORM
- Hugging Face Transformers
- `uer/roberta-base-finetuned-jd-binary-chinese`（中文 RoBERTa）
- Matplotlib、HTML 模板

## GitHub 已确认功能

- 情绪分析：Transformers pipeline，置信度阈值 0.8，positive/negative/neutral 映射
- 情绪记录：保存日期、文本和情绪，按日期查询
- 趋势图：Matplotlib 折线图（positive=1, neutral=0.5, negative=0）
- 激励语录：根据情绪从预设库随机选择

README 提到"关键词推荐"，当前公开代码未确认进入主业务链路，不作为已实现能力描述。

## 已知技术问题

- 模型标签映射存在风险（LABEL_0/LABEL_1）
- 模型训练领域与个人情绪日记不完全一致
- 中性情绪由低置信度推断，缺少标注验证
- 全部用户共用同一数据，不适合多用户场景
- 不具备心理诊断能力

## 推荐面试表述

> 这是我较早的 AI 应用项目。我使用 Django 把中文文本分类模型接入完整业务链路，实现输入、推理、数据库记录、趋势图和反馈。它也让我认识到模型标签映射、领域适配、多用户隔离和敏感数据治理的重要性。

## 在成长中的作用

证明模型调用到 Web 产品的早期闭环，Django 和 ORM 基础，以及从简单 AI 应用逐步演进到 Agent 工程化的轨迹。
