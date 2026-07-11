---
id: project-bp-architecture
title: 血压控制模块 — 技术架构
type: project
project_slug: blood-pressure-controller
section: architecture
visibility: public
confidence: self_reported
importance: low
tags:
  - Python
  - pyserial
  - 状态机
  - 串口通信
updated_at: 2026-07-11
---

# 血压控制模块 — 技术架构

## 整体结构

项目是一个 Python 上位机程序，通过串口与血压计硬件通信，控制测量流程并采集数据。

```
上位机 (Python)
    └── SerialController        # 串口通信层
    └── ProtocolParser          # 协议解析层
    └── MeasurementStateMachine # 测量流程控制
    └── DataLogger              # 数据记录
```

## 技术选型

| 组件         | 技术方案     | 说明                           |
|------------|----------|------------------------------|
| 串口通信       | pyserial  | Python 标准串口库，跨平台              |
| 流程控制       | 自实现状态机    | 状态枚举 + 转换函数，结构清晰              |
| 数据记录       | CSV / 日志文件 | 记录每次测量的时间戳、收缩压、舒张压、脉率 |
| 运行环境       | Python 3.x | 纯软件，无特殊依赖                    |

## 测量流程状态机

```
IDLE
  │ 发送开始测量指令
  ▼
MEASURING          (等待充气/测量过程)
  │ 收到测量完成帧
  ▼
RESULT_RECEIVED    (解析血压数值)
  │ 数据合法
  ▼
LOGGING            (写入日志)
  │
  ▼
IDLE               (准备下次测量)

异常路径：任何状态超时 → ERROR → IDLE（重试或停止）
```

## 数据格式

测量完成后，记录格式：

```
timestamp, systolic(mmHg), diastolic(mmHg), pulse(bpm), status
2026-07-11 10:00:00, 120, 80, 72, OK
```

## 局限性

- 仅支持特定型号血压计的私有协议，通用性有限
- 没有 GUI，依赖命令行操作
- 未实现多设备并发控制
