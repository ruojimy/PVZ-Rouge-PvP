---
name: pvz-rouge-add-boss
description: "在原生源码中新增Boss；需要独立原生源码工作区和编译器，不支持发布包热加载。"
---

# 在原生源码中新增Boss

需要另备原生游戏源码；仅文档路线已适配，未完成对应功能端到端验收。

这是v1.5.0.1真实技能的源码路线适配，原始技能不在PvP71开发者ZIP中。

真实拥有者：src/sim/pvp/gen/pm_catalog.cpp 的 BOSS_NAMES/EXCLUDED/f_allowed → pm_pve/pm_native_battle → 对应原生Boss分支。

当前PvP明确阻止Boss进入普通卡池和召唤白名单。旧版Boss桥还依赖单人固定Boss/奖杯/存档状态，不能越过这些限制冒充迁移。本任务没有获准重新设计对战平衡；新Boss需单独的源码功能变更和完整血条/召唤/胜负/存档设计。

需要先导出目标版本规则/卡池，设计实际变更并在单独源码工作区实现，再构建独立候选和执行该对象的最小流程。卡池、部署、渲染、伤害/交互、保存重开及未改内容回归都必须有真实证据。本扩展没有新增上述内容，也没有可执行模板；不得把本文适配当作新增功能已可用。旧Python游戏模块、猴子补丁、字节码及完整源码均未打包。

来源版本：v1.5.0.1 archival extracted release; secondary reference, not PvP71 developer extras。原始路径与SHA见 [迁移对照表](../../migration-matrix.json)，配套接口见 [协议](../../sdk/protocol.md)。
