---
name: pvz-rouge-add-mode
description: "在原生源码中新增模式；需要独立原生源码工作区和编译器，不支持发布包热加载。"
---

# 在原生源码中新增模式

需要另备原生游戏源码；仅文档路线已适配，未完成对应功能端到端验收。

这是v1.5.0.1真实技能的源码路线适配，原始技能不在PvP71开发者ZIP中。

真实拥有者：src/sim/pvp/gen/pm_teams.cpp 的 MODES → src/ui/gen/pm_room.cpp 和 pm_app.cpp → pm_pve/pm_coop_progress 与 userdata。

现有duel/duo/pve/coop是已编译房间/座位/波次/界面分支。新增模式需要菜单、状态机、存档schema及必要网络版本设计；自定义地图不等同新增模式。

需要先导出目标版本规则/卡池，设计实际变更并在单独源码工作区实现，再构建独立候选和执行该对象的最小流程。卡池、部署、渲染、伤害/交互、保存重开及未改内容回归都必须有真实证据。本扩展没有新增上述内容，也没有可执行模板；不得把本文适配当作新增功能已可用。旧Python游戏模块、猴子补丁、字节码及完整源码均未打包。

来源版本：v1.5.0.1 archival extracted release; secondary reference, not PvP71 developer extras。原始路径与SHA见 [迁移对照表](../../migration-matrix.json)，配套接口见 [协议](../../sdk/protocol.md)。
