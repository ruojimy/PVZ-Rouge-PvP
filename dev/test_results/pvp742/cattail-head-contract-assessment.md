# 猫尾、植物僵尸头部多判与232卡语义覆盖核对

日期：2026-11-14。只读审计；本审计代理没有改生产/测试源码，没有新增或重跑测试。以下区分已执行断言、静态实现、文案一致与尚未覆盖，不能互相替代。文案差异记录的是本次取证时的状态；总代理随后已安排UI代理只修文字、保留220px战斗规则，其完成结果应另行追加，不能提前记为通过。

生产内核为 `build/typed72-integrated-v44/source/src/sim/typed/`，组合来源为 `build/typed72-match-v1/`。本文的“猫尾草”对应卡牌 `plant:香蒲`；“猫尾秘籍”对应 `secret:猫尾`。

## 1. 可以直接回答的结论

1. 小体型索敌失准有真实typed Session回归，当前74.2的已有最终定向执行也再次通过六类目标；不是只找到追踪函数。
2. 猫尾秘籍“满120秒、对僵尸戴夫首伤2、命中不刷新标记”有当前typed Session实际断言；标记/范围/视线组合另有旧全量兼容路径断言和当前生产代码支持。
3. 花盆上的大喷菇对植物僵尸具有额外头部多判，已有真实typed Session对照：普通僵尸总伤10，豌豆僵尸270，当前74.2再次得到相同结果。这个案例可以确认用户希望保留的特点。
4. 不能说猫尾与全部图鉴逐条完全一致。已确认图鉴“约2.75格标记”的单位口径与默认48px地图上固定220px实现不一致；其余未独立覆盖的边界见第3节。
5. 找到的232卡总表是路由/测试模块索引，不是232张卡逐条语义验收。不能用该表或696处显示文本同步来宣布全卡机制完整还原。

## 2. 已执行的强证据

### 2.1 真实typed Session：74.1与当前74.2

审计源：[pvp741_combat_audit.cpp](../../src/uitools/pvp741_combat_audit.cpp)。这些用例通过 `typed72app::wrap_battle`、`start_battle_session` 进入生产Session，而非仅调用翻译后的原V函数。

| 断言 | 74.2现有实际结果 | 能证明的范围 |
| --- | --- | --- |
| `cattail_普通僵尸` | 总伤310，PASS | 高生命静止普通目标能被香蒲实际尖刺命中 |
| `cattail_海盗鹦鹉` | 总伤310，PASS | 小体型飞行目标能命中 |
| `cattail_小鬼僵尸` | 总伤310，PASS | 小鬼高度处理能命中 |
| `cattail_小型史莱姆` | 总伤310，PASS | 小型史莱姆能命中 |
| `cattail_中型史莱姆` | 总伤310，PASS | 中型史莱姆能命中 |
| `cattail_乌鸦` | 总伤310，PASS | 乌鸦高度处理能命中 |
| `hero_cattail_waits_120_seconds_and_hits_for_two_without_mark_refresh` | 首次命中时间122.233333秒、伤害2、mark未刷新，PASS | 120秒前不射；原射击周期可使首伤晚于120秒，不能误写成恰在120.000秒命中 |
| `potted_fumeshroom_plant_zombie_multiple_hit` | 普通10、豌豆僵尸270，PASS | 特定花盆/大喷菇/豌豆僵尸几何下，身体+头部多判真实发生 |

六类小目标各运行600个room step，固定种子741，将敌目标HP提高至1,000,000并用黄油固定，避免提前死亡让“没有子弹”的场景假通过。断言为实际HP下降；另存尖刺轨迹样本和目标记录。它没有穷举高速移动、所有姿态/地图/网络延迟。

秘籍测试先推进到120秒前且确认英雄未受伤，再继续等待真实首个命中；“不刷标记”检查的是这一近距站立自动可见场景。已存在非零受伤标记即将过期时是否延长，不由这一个数值断言单独证明；当前 `HeroCombat::on_damage` 另有显式猫尾排除代码。

证据：

- [74.1 combat-final-r4.json](../pvp741/combat-final-r4.json)，17/17通过。
- [74.2 final-directed-r1/pvp741_combat_audit.json](final-directed-r1/pvp741_combat_audit.json)，17/17通过。
- [74.2执行日志](final-directed-r1/pvp741_combat_audit.log)，同目录 `.case0.json` 至 `.case5.json` 是六类尖刺轨迹和目标明细。

上述文件是对应那次构建的证据，不代替后续最终交付EXE的哈希/全量门禁。

### 2.2 旧全量中的标记、范围和遮挡断言

[74.1 full-suite-r5/test_pvp_native_battle_combat.json](../pvp741/full-suite-r5/test_pvp_native_battle_combat.json) 中以下两项PASS，模块23/23通过：

- `test_production_cattails_gate_each_native_source_by_mark_range_and_los`：`unmarked/clear/wall` 三种情况，近香蒲和远香蒲同时存在；标记后将操作者戴夫移远，只有近香蒲可出尖刺，远香蒲不能借用全局戴夫门槛；无标记或遮挡则无尖刺。
- `test_production_dave_tail_requires_actual_mark_nearby_source_and_clear_los`：`unmarked/clear/wall/far` 四种情况，120秒激活后只在近距、有标记、无遮挡时出尖刺，并核验植物方归属和英雄来源ID。

实现断言可读 [pm_test_pvp_native_battle_combat.cpp](../../src/cpptests/gen/pm_test_pvp_native_battle_combat.cpp) 的上述两个函数。该全量模块直接构造翻译兼容 `pm_native_battle::new_NativeBattle`；没有在这两函数显式启动typed Session。因此应称“旧全量兼容语义断言”，不能冒充当前生产typed四种组合已重新逐项验证。

[test_pvp_tail_start.json](../pvp741/full-suite-r5/test_pvp_tail_start.json) 另有开局尾巴计时保持、120秒开门后原生射击显示与可回放断言通过；这也不能替代猫尾所有战斗规则。

## 3. 图鉴与当前猫尾实现逐项核对

当前图鉴来源：[catalog.py](../../tools/pvp72_sources/catalog.py)、[almanac_text.py](../../tools/pvp72_sources/almanac_text.py)、[extract/data/almanac_text.json](../../extract/data/almanac_text.json)。[catalog-text-final.json](catalog-text-final.json) 的232卡文本、20条简版附注和11项重点展示检查通过，文字同步没有漂移；它仅证明显示来源一致。

| 图鉴/规则 | 当前生产实现 | 已证明与尚缺边界 |
| --- | --- | --- |
| 优先最近敌方目标 | `NativeTracking::target_index` 按当前合法对象的周期欧氏距离，距离相同按ID、再原序；排除同归属、无效入场、死亡/灰烬等 | 代码明确；13组空间/扫描A/B对照状态/RNG相同，但没有专门穷举猫尾每种等距、魅惑、目标死亡转换组合 |
| 英雄必须被标记、在锁定范围且可见 | `hero_lock` 先判断受伤标记/路灯/站立植物戴夫，再对每个攻击来源做锁定距离与LOS | 旧全量组合PASS；typed近距命中PASS；所有地图精确边界未单独重跑 |
| 受伤后3秒标记 | `HeroCombat::on_damage` 使用 `mark_seconds`，当前规则为3 | 静态接入明确；不是本轮新造测试。猫尾命中显式不刷新 |
| 香蒲/猫尾对僵尸戴夫每发2 | `projectile.cpp` 给香蒲/植物英雄来源尖刺标cattail；`HeroCombat` 统一覆盖为2 | typed猫尾秘籍首伤2已证明；香蒲对英雄与多人席位的所有伤害组合没有由六个小僵尸测试直接证明 |
| 猫尾秘籍满120秒启用 | `NativeTick → HeroPhase::effects → HeroPhysics::effects` 使用规则 `tail_activation_seconds=120`，禁用期保存原尾巴计时 | typed等待实测和旧开局计时断言均支持 |
| 小体型可以被追踪命中 | `EntityContacts::home` 用合并后的 `homing_height`，不再固定向所有目标高2格处导引 | 六目标typed实际伤害PASS；高速/跳跃/缩小/水中/姿态转换全组合未穷举 |
| 猫尾是追踪功能 | 每tick `EntityRegion::tracking_gate → target_index` 选当前最近合法对象，再 `home` 读实时Motion导引 | **不是出生时锁一个永久ID**，可以动态重选；抓人草的head.target才是已登记实体ID追踪。无需反阵营障碍流场 |
| 路灯/站立戴夫约2.75格内标记 | 实现固定220px圆形距离+LOS，详见下一节 | **默认48px图的数值口径有明确差异**；“横纵”文案也没有精确表达当前圆形距离 |

生产源：[native_tracking.cpp](../../build/typed72-integrated-v44/source/src/sim/typed/native_tracking.cpp)、[entity_contacts.cpp](../../build/typed72-integrated-v44/source/src/sim/typed/entity_contacts.cpp)、[entity_region.cpp](../../build/typed72-integrated-v44/source/src/sim/typed/entity_region.cpp)、[hero.cpp](../../build/typed72-integrated-v44/source/src/sim/typed/hero.cpp)、[hero_phase.cpp](../../build/typed72-integrated-v44/source/src/sim/typed/hero_phase.cpp)、[hero_physics.cpp](../../build/typed72-integrated-v44/source/src/sim/typed/hero_physics.cpp)、[projectile.cpp](../../build/typed72-integrated-v44/source/src/sim/typed/projectile.cpp)、[plant_region.cpp](../../build/typed72-integrated-v44/source/src/sim/typed/plant_region.cpp)。

### 3.1 已确认的2.75格与220px尺度差异

不能只凭“旧引擎可能是80px”推断当前坐标。实际证据链如下：

1. [真实typed整App r3/grabber-current/report.json](application-performance-r3/grabber-current/report.json) 中 `final_state.map.tile_size=48`、`final_state.native_frame.tile=48`；公开植物戴夫高度91.2，等于1.9×48。不是只引用地图默认参数。
2. [cold_export.cpp](../../src/sim/typed72_app/cold_export.cpp) 导出 `battle.tile` 原值；[match_probe.cpp](../../build/typed72-match-v1/match_probe.cpp) 中 `runtime.tile=b.at("tile")`，玩家位置直接读取 `player.x/y`、高度直接读取 `player.h`，原生frame Motion直接读取avatar的 `玩家位置`。这些导入点没有80/48的坐标转换。
3. `NativeTracking` 的 `player_center` 只从同尺度位置减去半高；路灯中心是 `(cell+.5)*tile`。`within_sight` 对横向周期距离与y差做 `hypot`，直接与传入半径比较。`hero_lock` 两个自动标记分支传入固定 `220.`，未乘tile或worldscale。
4. 当前规则 `hero_lock_range=360`、`mark_seconds=3`、`tail_activation_seconds=120`；锁定范围360与自动标记范围220是两道门槛，不能混成同一个“2.75格”。

因此默认48px地图上自动标记半径为220/48≈4.583格；只有80px格子时220px才等于2.75格。原V [native_battle.py](../../tools/pvp72_sources/native_battle.py) 同样用固定220，因此这是既有图鉴单位/尺度口径问题，不是本轮空间索引新增的战斗范围变化。路灯花PvP附注写“横纵2.75格内”，实现却为欧氏圆形+LOS，不能声称矩形角落也完全遵照字面描述。

旧全量用目标x=1000、源x=800/700验证200px可自动标、300px不可自动标；另有远源x=400排除锁定。它没有220±ε精确边界，更没有2.75×48=132px边界断言。当前typed猫尾专项使用近距144px场景证明可攻击，不是220边界专项。

本轮只记录差异，不调战斗半径。若保持已有行为，应后续修图鉴单位/圆形描述，并单独补精确边界验收；不应为匹配文字而把既有220px玩法缩到132px。

### 3.2 实体导引与小目标高度

[cold_export.cpp](../../src/sim/typed72_app/cold_export.cpp) 合并 `content_assets::SCALE_TILES` 与 `native_scale::SCALE_TILES`，缩小后的表优先；组合层导入 `rules.homing_height`。`EntityContacts::home` 按目标root查高度，导引y为 `target.y - tile*min(1,height/2)`，缺表仍有旧默认2。该路径重读Motion，不缓存旧指针；`NativeTracking` 的周期chart也保留现场x/梯子标记验证。

不能把“表已导入”单独算成正确性；真正命中证据是第2节六个typed案例。猫尾当前动态重选最近，与抓人草最高当前HP、已登记ID追踪属于不同选择契约，不能统一成一个流场选目标。

## 4. 植物僵尸头部typed多判

### 4.1 接入与命中规则

`PlantRegion::fume` 保留大喷菇的两部分：原攻击动画阶段执行身体范围伤害10，动画期间另产生多枚“大泡泡”。`BonusScan::after` 实际调用 `BonusProjectiles::head_hits`；不是只生成了头部碰撞几何而没有接伤害。

`head_hits` 从typed `patch.plant_zombie`、`plant_name` 与13种 [plant_zombie_catalog.cpp](../../build/typed72-integrated-v44/source/src/sim/typed/plant_zombie_catalog.cpp) 的头部配置生成椭圆。空间覆盖只缩候选，保留原逐点椭圆精判；具体弹幕按原规则决定穿透、一次命中标记与每目标identity排重。大泡泡头部伤害为20，每枚泡泡对同一头部只登记一次；身体命中与头部登记分开。

因此“多判”不等于任意一枚弹幕无限重复伤害，也不等于所有弹幕都必须身体+头各算一次。不同弹种沿用自身规则；已有芦笋战机单枚弹幕“植物僵尸只命中一次”断言不与大喷菇多泡泡头部特点矛盾。

源：[bonus_scan.cpp](../../build/typed72-integrated-v44/source/src/sim/typed/bonus_scan.cpp)、[bonus_projectiles.cpp](../../build/typed72-integrated-v44/source/src/sim/typed/bonus_projectiles.cpp)、[plant_region.cpp](../../build/typed72-integrated-v44/source/src/sim/typed/plant_region.cpp)。

### 4.2 花盆大喷菇真实断言的确切含义

测试在夜晚，花盆 `(2136,864)`、大喷菇 `(2136,816)`，目标 `(2256,864)`。普通和豌豆僵尸均HP=1,000,000、固定姿态；把射击阶段设为1后走55次实际Session step，不直接调用头部damage helper。

| 目标 | 实际掉血序列 | 合计 |
| --- | --- | ---: |
| 普通僵尸 | 仅采样tick=17时掉10 | 10 |
| 豌豆僵尸 | 13次各20的头部泡泡伤害，外加同一次身体阶段10 | 270 |

原测试强断言是“植物僵尸总伤高于普通”，报告还保存上述270/10及每次掉血。它不是把270写死成所有大喷菇/植物僵尸几何下的固定伤害，也不是声明所有13种头部配置、朝向、钢门护甲、魅惑和高速运动均已独立覆盖。

另 [74.1全量hero_fume](../pvp741/full-suite-r5/test_pvp_hero_fume.json) 的花盆大喷菇对僵尸英雄双向身体/头部断言PASS，但英雄头部与植物僵尸头部不是同一目标，不能拿它替代上面的typed豌豆僵尸用例。[74.2 flying_plants已有结果](full-suite-r1/test_pvp_56_flying_plants.json) 中芦笋单枚弹幕命中植物僵尸一次、忽略魅惑友军也PASS；该全量测试为兼容路径，不冒称13种头部typed实战矩阵。

## 5. 232卡总表、已知差异与未覆盖项

### 5.1 总表实际是什么

[catalog-route-audit.json](../pvp741/catalog-route-audit.json) 有232条，字段为 `id/name/description/behavior/native_input_name/routes/test_modules/status`：

- 231条标记 `route located; semantic assertions require manual check`。
- `plant:蓝火树桩` 一条标记 `generic/table route needs manual check`，字面路由为空。
- `secret:磁力` 有生产路由但没有被该静态检索找到测试模块；实际上74.1/74.2 combat专项已有14格磁吸断言。

该表的“没有字面route/test_modules”不能直接判成机制未实现；同样，“找到了route/测试模块名”不能判成全部图鉴都正确。例如蓝火可能由模板/表配置路由，必须继续看实际卡解析及真实火焰命中；已有 [fire-production-final-r2.json](../pvp741/fire-production-final-r2.json) 的18项真生产火焰回归是独立证据。

没有找到另一份已经逐条把232卡全部图鉴语句标为“已验收/未还原”的完整语义总表。不能将这个缺失填成“232卡全还原”。全量历史仍有30FAIL/12ERROR，详见 [regression-comparison-final.json](../pvp741/regression-comparison-final.json)；其中包含版本期望、夹具/身份问题，不能不经分析就把42项全部列成42个玩法缺陷。

### 5.2 当前明确差异、已关闭旧缺口与证据不足

| 分类 | 项目 | 当前判断 |
| --- | --- | --- |
| 本轮已关闭文案差异 | 香蒲/猫尾/路灯标记“约2.75格”“横纵” | 固定220px欧氏圆形与默认48px地图文字不一致，第3.1节已给实际坐标证据链；后续由UI同步为标准地图约4.6格，战斗220未改 |
| 用户已更正文案 | 抓人草对僵尸戴夫8→4 | 4为用户明确规则，typed首伤4已证明，当前图鉴已同步；不能再列为未移植 |
| 本轮已关闭 | 传送带不搭、巨人小鬼丢甲、二手新甲不显示/不能正确拾取 | 各有真实Session/WorldView专项；见 [terrain汇总](../pvp742-terrain-summary.json)、[imp8项](imp-armor-r1.json)、[二手20项](secondhand-r2.json)，不能仍当作未修复清单 |
| 早期已关闭 | 模仿者模板/灰色/抓人草来源错误 | PvP73进度和本轮密植真实模仿链已有证据；不因旧描述再次宣称“从未移植”。本轮生命周期通过也不等于所有模仿卡已穷举 |
| 陈旧待办，当前已修 | AI死墓位记忆、解除封印所有墓碑出兵口 | 当前 `layers11.cpp` flag已为true；`layers19.cpp` 已临时打开unrestricted_exits，不把旧待办A1/A2当当前事实 |
| 未覆盖 | 所有卡的每条图鉴、全部倍率/魅惑/双打席位/边界组合 | 232路由和232显示同步都不能证明；仍需逐条语义清单及实际断言 |
| 未复现 | 用户密植偶发闪退、invalid-map、bad_alloc | 保留未解决状态，与猫尾/头部多判通过不是同一证明，亦未归因用户10GB |

当前显示同步的11重点卡还包括补贴、抓人草、多向红火、墓碑吞噬者、猫尾两项、魅惑、传送带、鹦鹉、乌鸦、斩首行动；[catalog-text-final.json](catalog-text-final.json) 只证明其当前展示文字正确取源。具体机制分别依其真实专项，不能把文本对齐冒充机制全量验收。

已知还原缺口的陈述必须以现源码和具体失败断言为依据。本次确证的现存图鉴差异是标记范围尺度/几何；对没有逐项审计的其余卡只能标“未证明”，不能伪造“全部一致”或凭历史待办列“未实现”。


## 审计后的修复状态

上述发现保留为历史证据。随后唯一文案修复已完成：owner/gen/data/cold同步“约4.6格（标准地图）”，220战斗规则与布局2.75不变；696字段、20简版、12重点显示入口通过。证据`catalog-text-cattail-final.json`、`cattail-mark-text-sync.json`、`cattail-text-regeneration-proof.json`。不是改成以路径距离选目标。
