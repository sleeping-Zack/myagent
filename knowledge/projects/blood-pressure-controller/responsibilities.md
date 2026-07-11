---
id: project-bp-responsibilities
title: 血压控制模块 — 职责说明
type: project
project_slug: blood-pressure-controller
section: responsibility
visibility: public
confidence: self_reported
importance: medium
tags:
  - 嵌入式
  - Python
  - 串口通信
updated_at: 2026-07-11
---

# 血压控制模块 — 个人职责

## 负责的工作

### 串口通信协议解析

负责研究目标血压计设备的串口通信协议，包括指令格式、数据帧结构和校验方式，实现上位机与血压计之间的双向通信。

- 解析设备返回的原始字节流
- 处理通信超时和错误重试
- 实现基础的协议封装层

### 测量流程控制逻辑

负责设计并实现测量全流程的状态机控制，确保每次测量按照标准化步骤执行。

- 设计覆盖完整测量周期的状态机
- 实现各状态之间的转换条件和超时保护
- 处理异常状态的恢复逻辑

### 测试与调试

参与设备联调和功能测试，排查通信异常和流程逻辑问题。

- 记录典型问题和解决方案
- 验证测量数据的准确性

## 说明

本项目属于小型课程设计类项目，非正式实习或商业项目。规模有限，但涵盖了从协议分析到软件实现的完整过程。
