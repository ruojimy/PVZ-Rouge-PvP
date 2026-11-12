---
name: pvz-rouge-add-plant
description: "在原生源码中新增植物；需要独立原生源码工作区和编译器，不支持发布包热加载。"
---

# 在原生源码中新增植物

需要另备原生游戏源码；仅文档路线已适配，未完成对应功能端到端验收。

这是v1.5.0.1真实技能的源码路线适配，原始技能不在PvP71开发者ZIP中。

真实拥有者：src/sim/pvp/gen/pm_catalog.cpp → C_NativeBattle::m_spawn/m__configure_plant → src/sim/pvp/gen/pm_native_content.cpp 与 src/sim/gen/原生分支。

卡池、费用/CD、原生输入名、部署合法性、动画、攻击实体、秘籍/派生形态和回放均需一致。原生表初始化包含编译分支，不支持复制Python补丁或只改导出JSON。

需要先导出目标版本规则/卡池，设计实际变更并在单独源码工作区实现，再构建独立候选和执行该对象的最小流程。卡池、部署、渲染、伤害/交互、保存重开及未改内容回归都必须有真实证据。本扩展没有新增上述内容，也没有可执行模板；不得把本文适配当作新增功能已可用。旧Python游戏模块、猴子补丁、字节码及完整源码均未打包。

来源版本：v1.5.0.1 archival extracted release; secondary reference, not PvP71 developer extras。原始路径与SHA见 [迁移对照表](../../migration-matrix.json)，配套接口见 [协议](../../sdk/protocol.md)。
