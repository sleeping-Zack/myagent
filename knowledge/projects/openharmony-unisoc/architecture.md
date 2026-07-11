---
id: project-openharmony-architecture
title: OpenHarmony UNISOC 项目技术背景
type: project
project_slug: openharmony-unisoc
section: architecture
visibility: public
confidence: self_reported
importance: low
tags:
  - OpenHarmony
  - UNISOC
  - 嵌入式
  - Linux
  - 编译构建
updated_at: 2026-07-11
---

# OpenHarmony UNISOC 项目技术背景

## 项目背景

OpenHarmony 是华为主导、开源的面向物联网和嵌入式设备的操作系统，UNISOC（紫光展锐）是国产移动芯片厂商。该项目的目标是将 OpenHarmony 系统适配到 UNISOC 特定芯片平台上运行。

## 技术架构（了解范围内）

### OpenHarmony 构建系统
- 使用 `hb`（HarmonyOS Build）作为构建工具
- 基于 GN + Ninja 构建系统
- 内核支持 LiteOS-A 和 Linux 内核两种选项

### 仓库管理
- 使用 `repo` 工具管理多仓库代码（类似 Android AOSP）
- manifest 文件定义各子仓库的分支和路径

### 适配层结构
- HAL（硬件抽象层）负责隔离底层硬件差异
- 驱动框架（HDF，HarmonyOS Driver Framework）统一驱动接口
- 需要为目标芯片配置 `config.json` 和 `.hcs` 硬件配置文件

## 朱旭了解但未深入的内容

以下内容朱旭有基本概念，但没有实际开发经验：
- HDF 驱动模型（Host、Device、DeviceNode 三层结构）
- 内核裁剪和内存优化
- 驱动二进制的加载和绑定流程
