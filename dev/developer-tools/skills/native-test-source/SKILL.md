---
name: native-test-source
description: "在原生源码工作区按影响范围回归；需要独立原生源码工作区和编译器，不支持发布包热加载。"
---

# 在原生源码工作区按影响范围回归

需要另备原生游戏源码；仅文档路线已适配，未完成对应功能端到端验收。

源码依赖：旧run_pvp_affected.py依赖tests/与modkit游戏对象，不能复制到玩家包后运行。原生已有cpp_tests/run_cpp_suite和分类门禁，需要源码测试/只读夹具，故不纳入轻量扩展。本次CLI只触及app，执行真实发布入口、协议负控、地图/回放/relay集成和72定向门禁。继承的30FAIL/12ERROR仍保持，不扩大豁免；不能把本包smoke称为全量回归。

来源版本：PvP71 developer ZIP。原始路径与SHA见 [迁移对照表](../../migration-matrix.json)，配套接口见 [协议](../../sdk/protocol.md)。
