---
id: project-fao-rag-responsibilities
title: 法奥机器人智能客服平台个人职责
type: project
project_slug: farino
section: responsibility
visibility: public
confidence: self_reported
importance: high
repository: https://github.com/sleeping-Zack/farino
period: 2026.01-2026.06
tags: [AIFlowy, Agent, 路由, 规划, QA数据闭环, 工单, 部署]
updated_at: 2026-07-11
---

# 法奥机器人智能客服平台个人职责

> 说明：本项目基于 AIFlowy 进行二次开发，以下职责均为在已有平台基础上的新增或改造工作，不涵盖 AIFlowy 上游框架的原有能力。

## Direct / Agentic 两级路由

针对简单问题也进入完整 Agent 流程的问题，设计并实现了两级路由机制：

- 规则判断 + Qwen 意图识别
- 普通寒暄直接交给对话模型
- 复杂请求进入知识库、Workflow、插件和 MCP 链路

面试时可说明路由规则、误判处理和降级策略。

## 动态规划模块

- 根据问题和 Bot 已绑定能力生成 3—5 步执行计划
- 校验工具类型、工具 ID 和参数
- 异常时降级处理
- 通过 SSE 同步计划生成、步骤执行和完成状态到前端

## QA 数据闭环

GitHub 最新提交可确认该模块功能，包含：

- 从历史会话抽取 User—Assistant 问答对
- 消息配对与低质量过滤
- message_id 幂等去重
- 人工审核流程
- Markdown 批量导出
- 优质问答回流知识库

## 售后工单

当前简历记录工单模块支持以下状态流转：

- 待处理
- 处理中
- 待补充
- 已解决
- 已关闭

支持问题类型分类、优先级设置和用户身份数据隔离。

该模块在 GitHub 抽样中未充分核验，属于 `resume_current`，可补充对应文件和演示证据。

## 部署

- Docker Compose 编排后端、前端、MySQL、Redis
- Nginx API 反向代理
- 静态资源服务
- SSE 长连接（已配置 Nginx proxy_read_timeout 和关闭缓冲）
- 企业内网私有化部署

GitHub 提交可确认 Nginx SSE 超时配置；完整私有化部署效果需补充部署文档或截图。

## GitHub 可确认的改动方向

以下内容可通过仓库 commit 和 diff 确认：

- Plan 层更新
- Execution 层更新
- 工作流步骤显示
- 根据工具判断规划逻辑
- Markdown 渲染和输出美化
- Token 计量
- 聊天底部固定和自动滚动
- 新消息浮动按钮
- 助手市场与侧边栏状态同步
- SSE Nginx 配置
- 问答精选管理
- Markdown 导出
- 知识库导入

## 正确的贡献边界

推荐表述：

> 我在 AIFlowy 现有平台上负责 Agent 和客服工作台相关二次开发，重点包括路由判断、动态规划、QA 数据闭环、工单状态管理和私有化部署链路。AIFlowy 的 RAG 基础能力、多模型接入和插件系统属于上游平台已有能力，不作为个人主要贡献。
