---
id: project-fao-rag-architecture
title: 法奥机器人智能客服平台技术架构
type: project
project_slug: farino
section: architecture
visibility: public
confidence: self_reported
importance: high
repository: https://github.com/sleeping-Zack/farino
period: 2026.01-2026.06
tags: [AIFlowy, Java, SpringBoot, Vue3, SSE, Docker, Nginx, MySQL, Redis]
updated_at: 2026-07-11
---

# 法奥机器人智能客服平台技术架构

## 项目性质说明

本项目是南昌大学 × 法奥机器人校企合作项目，基于 AIFlowy 大型 AI 应用平台进行二次开发。以下架构内容涵盖整体平台和个人参与改造的模块，请注意区分。

## 整体技术栈

| 层次 | 技术 |
|------|------|
| 后端语言 | Java |
| 后端框架 | Spring Boot |
| ORM | MyBatis-Flex |
| 前端框架 | Vue 3 |
| 数据库 | MySQL |
| 缓存 | Redis |
| 大模型 | Qwen |
| 实时推流 | SSE（Server-Sent Events） |
| 容器化 | Docker Compose |
| 反向代理 | Nginx |

## 两级路由架构

```
用户消息
    ↓
意图识别（规则 + Qwen 分类）
    ├── 简单寒暄 → 对话模型直接回复
    └── 复杂请求
            ↓
        动态规划模块
            ↓
        步骤执行（知识库 / Workflow / 插件 / MCP）
            ↓
        SSE 实时推送执行状态
```

## 动态规划模块

```
问题 + Bot 已绑定能力
    ↓
生成 3—5 步执行计划（工具类型、工具 ID、参数）
    ↓
参数校验
    ↓
步骤执行（并发或串行）
    ↓
异常降级
    ↓
SSE 通知：计划生成 / 步骤进行 / 步骤完成
```

## QA 数据闭环架构

```
历史会话数据
    ↓
问答对抽取（User—Assistant 消息配对）
    ↓
低质量过滤（长度、空内容、重复检测）
    ↓
message_id 幂等去重
    ↓
人工审核队列
    ↓
审核通过 → Markdown 导出 / 知识库导入
审核拒绝 → 丢弃
```

## 部署架构

```
企业内网
    ↓
Docker Compose
    ├── 后端服务（Spring Boot）
    ├── 前端服务（Vue 3 构建产物）
    ├── MySQL
    └── Redis
    ↓
Nginx
    ├── API 反向代理
    ├── 静态资源服务
    └── SSE 长连接配置
        （proxy_read_timeout、proxy_buffering off）
```

## 关键设计决策

### Direct / Agentic 两级路由

AIFlowy 默认所有请求都进入完整 Agent 流程，导致简单问候也要走完整链路，延迟高且 Token 浪费。路由层通过规则 + 意图分类将请求分流，降低简单场景的响应时间和成本。

### SSE 长连接稳定性

SSE 在 Nginx 反向代理下容易因超时或缓冲被中断。解决方案：

- `proxy_read_timeout 3600s`
- `proxy_buffering off`
- `X-Accel-Buffering: no`
- 心跳保活

GitHub 提交中有对应的 Nginx 配置改动。

### QA 数据幂等去重

历史会话抽取存在重复运行场景，通过 `message_id` 唯一键做幂等处理，避免重复数据进入审核队列。

## 上游平台能力（AIFlowy 已有，非个人贡献）

以下能力属于 AIFlowy 平台原有，不作为个人项目贡献叙述：

- RAG 基础检索框架
- 多模型统一接入层
- 插件市场和 MCP 接入
- 基础会话管理
- 用户权限体系
