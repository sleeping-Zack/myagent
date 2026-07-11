---
id: project-iot-platform
title: IoT 边缘—云数据同步监控平台
type: project
project_slug: iot-platform
section: overview
visibility: public
confidence: confirmed
importance: supplementary
repository: https://github.com/sleeping-Zack/iot-platform
status: course_project
tags: [Django, DRF, MySQL, Trigger, StoredProcedure, EventScheduler, Chart.js]
updated_at: 2026-07-11
---

# IoT 边缘—云数据同步监控平台

## 项目性质

课程团队项目，不是商业生产平台。模拟 IIoT 数据链路：

> 边缘设备采集 → 阈值告警 → 同步队列 → 云端归档 → 日报生成 → API 和图表展示

## 技术栈

- Python 3.11、Django、Django REST Framework
- MySQL 8.0、Trigger、Stored Procedure、Event Scheduler
- Chart.js、drf-spectacular / Swagger

## 个人职责

仓库 README 明确记录朱旭负责：

- 云端归档
- 存储过程与报表
- 后端接口
- 告警与同步控制

其他成员：胡振鹏（数据库设计、设备信息和采集逻辑、文档）、吕文潇（前端页面）

## 系统能力

- 超阈值自动告警和数据自动入队（MySQL Trigger）
- 队列同步到 cloud_data（Stored Procedure）
- 每 5 分钟同步 + 每日 00:05 日报（Event Scheduler）
- 云端时间序列 API、日报 API、设备列表 API、最近告警 API
- 图表页面（Chart.js）

## 项目价值与口径

证明 MySQL 触发器、存储过程、事件调度实践，Django/DRF API 能力，以及对数据队列和云端归档链路的理解。

不应夸大：不说接入真实工业设备、不说处理大规模工业流量、不说具备生产级消息队列、不把课程项目写成企业商业平台。
