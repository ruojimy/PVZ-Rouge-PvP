# 特殊移动与寻路契约核对

本报告只读取已冻结的生产源和已有测试证据；未修改 src、tools、data、CMake，也未新增或运行测试。文件路径相对项目根目录。

## 实际分派入口

生产模拟目录为 `build/typed72-integrated-v44/source/src/sim/typed/`，以下模拟文件均指该目录。组合层所有者是 `build/typed72-match-v1/`，生成结果为 `src/sim/typed72_app/composition/`。

当前代码没有一个同时列出用户表中所有“原版单位、扩展卡、装备、临时状态”的单一特殊寻路白名单。不能把 `ContentZombies::custom`（内容卡/绘制分类）误当成全部移动规则清单。完整分派分为：

- `zombie_spawn.cpp:populate_original_zombie`：原版原型、手持装备、矿工出土、绳索入场、气球、车辆、撑杆等初始状态。
- `content_admission.cpp:ContentAdmission::configure(ZombieRef, ColdCard)`：红眼/史莱姆/传送带/掷弹兵、稻草人/乌鸦、舞王/雪橇小队、雪人、滚桶/小鬼炮/船长/鹦鹉等内容卡实际控制器分派；植物僵尸另由其配置与控制器约束。
- `ZombiePhase::run → ZombieActions::run`：保存原生逐体顺序，每体先 gate，再 `ZombieMotion::advance`，后 `ZombieActions::finish`。`MatchProbe::zombie_gate` 依次选择该单位集结场、结束前体内容控制、执行扩展 gate、执行本体内容 gate。
- `ContentZombies::gate/finish`、`ContentZombieBindings` 和 56/64/70/September 控制器：特殊目标、队形、抓取、飞行、钩索等接入点，不经过一个通用地面方向算法就结束。

本轮空间索引、共享路径与缓存只复用可共享计算；原目标规则、手持/状态分支和独立阶段继续执行。普通 `PathTracking::choose_target` 保留原生列表首个合法目标规则；普通雪人则使用自己的距离比较，不能把两者统一替换为“路径最近”。

## 用户清单逐项核对

“轨迹覆盖”指下节的 23 类 × 4 状态矩阵；它不等于该类每项能力已被强制触发。

| 对象/状态 | 生产接入与必须保留的规则 | 已有证据与本轮范围 |
|---|---|---|
| 梯子僵尸 | `ZombieMotion::chase` 根据原方向、上下格、地形和手持梯子条件铺 `梯子块`；同竖尸与已有梯子仍能影响原生跳跃，不能改成单位直接贴合流场。 | 轨迹覆盖；本轮自然建梯实际触发，24 行完整轨迹/RNG 等价；普通单位拾起二手梯子后也实际搭建。 |
| 传送带僵尸 | 沿用梯子原型/手持；`ContentZombies64::hand_kind/tag_belt/on_belt/gate/finish` 识别传送带，标记地形，影响经过的普通僵尸。`MatchProbe` 的粒子观察接回 tag_belt。 | 本轮补的是实际架设/标记接线；自然搭带、经过后清冰冻/黄油并向上加速、重发标记保留已触发。二手传送带拾取后普通单位可搭带。眩晕清除在原全量有断言，本轮地形专项未另行注入眩晕。 |
| 矿工僵尸 | `ZombieActions::miner` 保留地下进格、原目标列/最新集结点出土、地形约束、出土反向及动画；魅惑不读取敌方集结点。 | 轨迹覆盖；当前 r1 全量中“最新集结点出土”和“魅惑矿工忽略敌方集结”两条明确断言 PASS。 |
| 潜水僵尸 | `ZombieMotion::entry/environment/chase` 保留水中读取水面行方向、水中纵向速度/浮力和特殊跳跃条件。 | 水区/攻随集结魅惑轨迹覆盖；不由共享场抹平其水面取样行。未单独强断言所有溺水/出水长周期分支。 |
| 海豚僵尸 | `ZombieMotion::bite_plant/environment/chase` 以“海豚”手持判断水中跨植物动作、跳跃 CD、原生海豚实体与水中速度倍率。 | 水区四状态轨迹覆盖；没有把“存活且轨迹等价”当成每个跳跃时机均触发的证明。 |
| 气球僵尸 | 原生生成保留气球手持/高度；`ZombieMotion::chase` 的气球方向分支与 `ZombieActions::locomotion` 的纵向状态仍执行。 | 四状态轨迹覆盖；未专门覆盖每种破球、吹飞、落地与重新索敌组合。 |
| 飞贼/蹦极僵尸 | 原生名称是 `飞贼僵尸`；`populate_original_zombie`、`ZombieMotion::entry/advance`、`ZombieActions::locomotion` 保留绳索生成、下降、停留、离场，不接受普通位移覆盖。 | 轨迹 fixture 特意不强制其“出场=500”，保留真实绳索入场；原全量有新植物均可成为飞贼目标断言。短矩阵未为整套入场—取走—离场逐阶段设断言。 |
| 撑杆跳僵尸 | `ZombieMotion::status/bite_plant` 检查前格植物/水中状态并启动撑杆；`ZombieActions::pole` 推进原跳跃阶段。 | 四状态轨迹覆盖；原全量保留撑杆对魅惑本体的倍率断言。 |
| 黑撑杆僵尸 | 继承撑杆动作；`ExpansionCombat::finish_zombie` 在原存活/无撑杆状态/下落/落地条件下恢复撑杆，gate 处理对应显示。 | 四状态轨迹覆盖与静态接线核对；没有将本次短矩阵宣称为“失杆后所有重获条件均强制触发”。 |
| 蹦蹦僵尸 | 手持“弹跳杆”走 `ZombieActions::locomotion` 的原碰地反弹及音效状态；不是普通地面逐格移动。 | 四状态轨迹覆盖，保留手持状态判断；未逐地形强制全部弹跳/失杆分支。 |
| 普通雪人 | `SeptemberZombies::gate/chase` 单独比较合法植物的周期距离平方，保存实体目标，按目标格/地形版本共享独立路径快照；跟随/集结走各自条件。 | 四状态轨迹覆盖；map-key 专项真实选择了 70 个不同目标格，越过 64 项 bank 容量边界而无缺键。不是将其目标改成图距离最近。 |
| 斩首行动雪人 | `ColdZombieSecrets` 设置 headhunt；`SeptemberZombies::gate` 先走 headhunt 分支，借所选植物戴夫路径场，局部隐藏植物并在 finish 恢复，不落入普通雪人最近植物分支。 | 本轮单独强断言：雪人与戴夫之间有坚果，120 room ticks 后坚果 HP 仍为 1000；这证明所测阻挡植物未被啃，不等于所有障碍地图追击已全覆盖。 |
| 海盗鹦鹉、乌鸦 | `ContentZombies::finish_flyer` 直接追选定实体，乌鸦独立半速参数保留。跟随戴夫/集结旗之前调用 `ContentQueries::route_enemies`，选择途中更早的敌方植物、魅惑僵尸或植物戴夫；原 0.65 格路径投影精判与列表顺序平局保留。 | 本轮 20 场景：两种鸟 × follow/rally × 无阻挡/植物/魅惑僵尸/植物戴夫/甜薯。其中 16 组明确断言阻挡者或甜薯的目标 ID；4 组无阻挡断言目的地非空，并记录了戴夫/旗代理目标。没有退回无视沿途目标直冲旗帜。 |
| 甜薯对飞行单位 | `finish_flyer` 在路线拦截后以 `taunt_target` 优先替换目标；甜薯让鸟直奔甜薯。`SweetTaunts::apply` 对飞行单位不安装地面追击场。 | 上述 20 场景中的甜薯组已明确选中甜薯；保留用户补充的“甜薯优先于路径阻挡”契约。 |
| 雪橇车 | `ZombieActions::vehicle/locomotion` 保留车辆速度、冲撞、碾压、雪地/前格地形与生成相关阶段。 | 四状态轨迹覆盖；原全量有雪橇部署扣费与四个原生单位断言。长时间雪路耗尽、所有车辆死亡/碾压组合不由短矩阵证明。 |
| 投篮车 | `ContentZombies::cart_gate` 选择当前 follow/rally/魅惑对应目标和前进状态，`ZombieActions::vehicle/cart` 保留车辆与射击动作。 | 四状态轨迹与原 rally 特种移动断言；没有用普通地面目标场覆盖车辆停走/弹药状态。 |
| 小鬼炮 | `cart_gate/finish_summoner` 保留车辆方向/停靠半径、follow/rally 条件及接近后累积召唤时钟。 | 四状态轨迹和原 rally 断言；召唤周期是否在短矩阵每组真正触发没有单独计数，不能据此声称全召唤周期验证。 |
| 滚桶僵尸 | `ContentZombies::gate/finish`、`NativeBarrels` 保留推桶方向、接触、地形跳跃及破桶；魅惑清除手持并转入相应状态。 | 四状态轨迹和原 rally 断言；仍按其桶状态执行，未简化成普通僵尸路线。 |
| 钩索僵尸 | `ContentZombies70::hook_target/hook/projectiles` 保留原优先级、甜薯覆盖、发射/命中；命中后的 `hook_pull` 逐步移动僵尸自身。 | 四状态轨迹；原全量明确断言最远目标/魅惑目标、甜薯覆盖，以及超过六秒后真实 hit 和自身被拉动。新 120-tick 矩阵没有为六秒触发另设断言，不能替代该长周期用例。 |
| 稻草人 | `Scarecrows::grave_goal/advance` 从同归属活墓碑选目标，包含临时挂起的墓碑；保留周期跳跃/遇阻和稳定 ID 平局，既有契约不听原 F/旗指令。 | 四状态轨迹与静态能力核对；没有将“模式组合进 fixture”解释为稻草人必须服从这些指令。 |
| 舞王与伴舞 | `ContentZombies56::gate/finish/fill_group/anchor` 保留原始召唤钟、归属/队列槽；外力 impulse 使伴舞暂离编队，满足原回归条件才归槽。 | 当前 r1 全量的 999→1000 时刻正好四子、萝卜伞击飞后归槽断言 PASS。四状态矩阵仅另覆盖代表舞王轨迹，未穷举多个舞王全部补员组合。 |
| 黑橄榄 | `ExpansionCombat::zombie_gate/charge/finish_zombie` 保留冲锋状态及条件友军前推，内容 gate 在可能推人后失效空间查询缓存。 | 四状态轨迹；保留位移后失效索引接线。未在本专项逐个列举被推友军种类/所有连锁地形。 |
| 红眼巨人与被抓单位 | `ContentZombies64::throwable/redeye` 选合法同归属友军，抓取阶段直接控制被抓对象位置，满足原钟后抛出；`ContentZombies::finish` 在红眼可能移友军后失效索引。 | 四状态轨迹；原全量有周期抛友军和黄油暂停钟断言。独立 8 项装备审计验证巨人背鬼/抛鬼甲继承，不能把它等同于红眼所有抓取目标与整套八秒循环。 |
| 植物僵尸 | `PlantZombieShooting::enforce_motion/jump_assist/step` 按具体配置限制移动/撑杆/弹跳，部分配置有遇障跳跃辅助；头部与本体类型仍由原配置/碰撞处理。 | 矩阵仅用豌豆僵尸作代表；火焰/头部多判另有战斗专项。不能把一个代表单位外推为所有植物僵尸配置、速度与跳跃都已穷举。 |
| 地面甜薯吸引 | `SweetTaunts::update/apply/restore` 以甜薯目标设置专用追击场并临时隐藏非目标植物，之后恢复；区域/状态改变仍走原精判。 | 甜薯在普通矩阵场景中存在，飞行优先级另有强断言；本报告不把“存在甜薯”当成所有地面种类均被吸引的强证明。 |
| 跟随、集结、魅惑 | `SeatPathTracking::switch_for/select_rally`、`ZombiePhase`、`ContentZombies::follow/rally/destination` 保留真实席位路径银行；魅惑不接受原阵营旗，飞行/车辆/矿工按自己的能力组合处理。 | 每类四状态矩阵、原特种 rally、魅惑矿工断言；不是仅反转统一流场方向。合作/双人仍沿实际 seat 选择上下文，实体追踪不被换成路径终点。 |

## 已运行证据及精确含义

1. `test_results/pvp741/movement-final-r2/summary.json`：空间化对照 113 项，`all_trajectories_state_rng_equal=true`。该脚本比较整个 case，包括采样轨迹、最终状态、地形与 RNG，不只比较“没崩”。它是此前空间改造的 A/B 证据，不冒充后续所有补丁的重新双臂测量。
2. `test_results/pvp742/final-directed-r1/spatial741_movement_audit.json` 与同目录 `summary.json`：当前最终定向运行 113/113，exit 0。23 类 × attack/follow/rally/charmed=92；两种鸟的 follow/rally 五类阻挡=20；斩首雪人植物不受伤=1。普通矩阵每组 120 room ticks，中途移除障碍，水中单位配置水区，附同阵营单位/墓碑；它检查场景未提前结束并保存状态。没有为每一个长周期能力设置事件触发断言。
3. `test_results/pvp742-terrain-final.json`：5/5。自然梯/带均在第 2 个 room tick 铺设；传送带标记重发保留、经过者清冰冻/黄油并上升。24/32/64 行窄缝/边界 18 子情形；绿洲左高台 4/40 只各 1400 ticks，最高脚底 y 分别约 923.17/530.08，后者越过 y576 平台。原同竖尸辅助跳跃保留，没有新增实体踩踏碰撞模型。
4. `test_results/pvp742-terrain-24row-equivalence.json`：普通 24 行梯/带完整采样轨迹与 RNG 相等。
5. `test_results/pvp742/secondhand-r2.json`：20/20；其中普通僵尸拾梯/带后实际架设（第 4 tick），证明能力来自原手持逻辑而非只检查原卡牌名。`imp-armor-r1.json` 为独立装备 8/8，范围是装备槽、继承与磁吸/赠甲。
6. `test_results/pvp742/map-key-r3.json`：4/4；其中 70 雪人实际选中 70 个不同植物目标格并持续推进，无 map 缺键；未声称测得内部 bank 重建次数。

## 原全量明确断言

只引用实际读取到 PASS 的具体条目，不将整个历史全量目录称作全绿。原断言源为只读 `C:/Users/xiech/Downloads/PVZ-Rouge-v1.4.8/next-pvp71/tests/`，未改写。

| 断言 | 已有结果位置 | 明确覆盖 |
|---|---|---|
| `test_rally_special_mobile_units_and_charmed_parrot` | 当前 `full-suite-r1/test_pvp_53_features.json`，修 None 后 `null-battle-suite-r1/test_pvp_53_features.json` 亦 PASS | 鹦鹉/小鬼炮/投篮车/滚桶实际向集结点位移；魅惑鹦鹉不被强制指向植物戴夫。 |
| `test_miner_emerges_at_latest_rally_in_native_underground_loop`、`test_charmed_miner_ignores_enemy_rally` | 当前 `full-suite-r1/test_pvp_56_zombies.json` PASS | 最新旗位置决定实际出土终点，魅惑矿工不写敌旗矿工标记。 |
| `test_initial_dance_uses_native_clock_then_exactly_four_children`、`test_backup_native_umbrella_impulse_runs_then_returns_to_owned_slot` | 当前 `full-suite-r1/test_pvp_56_zombies.json` PASS | 原生 999/1000 钟、四槽；受萝卜伞外力后按原条件归队。 |
| `test_belt_is_placed_like_a_ladder_and_climbs_faster`、`test_zombies_on_belt_shrug_off_control` | 既有 `typed72-20261112-release/utf8env-r1/full-suite-w3/test_pvp_64_features.json` PASS | 梯子块与带标记、较快登高；带上冰冻/眩晕清除，普通梯不获该效果。 |
| `test_crow_bites_for_three_at_half_parrot_speed` | 同一既有全量的 `test_pvp_61_features.json` PASS | 乌鸦/鹦鹉速度比及乌鸦啃咬，不用同一速度替代。 |
| `test_throws_a_nearby_friend_every_eight_seconds_no_imp`、`test_butter_pauses_throw_clock` | 同一既有全量的 `test_pvp_64_features.json` PASS | 红眼友军抛出周期与黄油暂停钟。 |
| `test_hook_farthest_and_charmed_farthest_zombie`、`test_hook_respects_sweet_potato_and_shell`、`test_hook_actual_six_second_launch_hit_and_pull` | 同一既有全量的 `test_pvp_70_features.json` PASS | 最远合法目标、魅惑阵营、甜薯优先、真实钩索命中与自身拉动。 |

上表“当前”路径前缀均为 `test_results/pvp742/`；既有全量路径前缀为 `test_results/`。最终新全量是否完成、是否仍有其他基线差异，以父任务最终汇总为准，本报告不替代那次验收。

## 保留范围与未证明项

特殊分支继续由原生和各内容控制器管理；空间化主要改变候选集合获取、共享方向场/目标格缓存及其失效维护，没有给所有单位统一套一个地面 Voronoi 选敌规则。

矩阵只覆盖给定种子、固定压力/障碍/水区及有限时长。没有强制触发的破球、重获撑杆、完整蹦极离场、所有红眼抓取目标、全部召唤周期、全部植物僵尸配置及特殊能力叠加，仍不能称为已证明。原全量的特定长周期断言提供对应能力证据，但不能外推到全部地图、席位、魅惑时刻与网络重连组合。手机实机与广域网络体验也不由这些轨迹/逻辑测试代表。
