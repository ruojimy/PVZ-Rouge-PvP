---
name: native-build-source
description: "在独立原生工作区构建候选；需要独立原生源码工作区和编译器，不支持发布包热加载。"
---

# 在独立原生工作区构建候选

需要另备原生游戏源码；仅文档路线已适配，未完成对应功能端到端验收。

源码依赖：旧PyInstaller、marshal/字节码采集、python-for-android和旧.pyd流程不能构建独立C++版。实际原生入口是CMakeLists.txt和src；本次添加PVZ_BUILD_DEVELOPER_CANDIDATE选项，单独目标PvZPvPNativeDev。需自行提供VS2022/CMake/原生依赖，串行/MP1构建。扩展不含这些环境、游戏源码或资源。Android仍使用原生android工程与同签名发行流程，本轮不构建/安装新APK。

来源版本：PvP71 developer ZIP。原始路径与SHA见 [迁移对照表](../../migration-matrix.json)，配套接口见 [协议](../../sdk/protocol.md)。
