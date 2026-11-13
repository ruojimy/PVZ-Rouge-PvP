# PvP73 进度（2026-11-12 起）

需求与用户决定见 Claude 记忆 `pvp73-requirements`；本文件记录实际改动、证据与待办。

## 工具链（PvP73 新增）

- `build/pvp73-tools/`：V 参照记录器 `ref73_record.exe`、冷导出 `cold73_export.exe`，链接 **当前源码** 编出的 `build/app-typed72-v2/Release/*.lib`（旧 `typed72-ref-recorder-v*` 链接 11-05 冻结库，PvP73 改动后不能再当参照）。
- `build/pvp73-tools/compare73.py <场景> <输出目录>`：沿用 `compare_match.py` 逐 tick 对拍，类型化侧为生产门禁 `typed72_match_gate.exe`（App 同一组合与内核）。
- `src/sim/pvp/battle_api.cpp`：场景 `"night": true` 改为通过 `MapSnapshot.from_dict` 重建（含校验和），V 不再拒绝夜晚场景。
- `src/uitools/app_run.cpp`：新增 `app_run script <script.json> <outdir>` 通用脚本驱动（等待界面/阶段/路径值，执行 action/state/call/截图/日志；`"$screen"` 代表显示表面）。

## 已修复

| 问题 | 根因 | 修复 | 证据 |
|---|---|---|---|
| 合作模式开局夜晚（第 3/7/11… 天，如第 7 天 瀑布（夜））开战即报 `missing typed field` | 夜间残骸墓碑在任何英雄作用域之外生成，类型化原生工厂读取全局"玩家位置"，而冷导入从未设置该全局（V 运行时初值为地图中点） | `build/typed72-match-v1/match_probe.cpp` 冷导入时若缺失则取 `g["玩家位置"]` | `test_results/pvp73/coop_night7-r2`：7501 tick 与 V 逐 tick 一致，事件日志一致 |
| 夜晚向日葵/双子向日葵/脑光墓碑仍按白天 16 秒产出（V 为 20 秒） | 类型化产出策略登记的是未解析的原始卡表；V 每 tick 用 `_card(side,key)` 按当前地图昼夜+秘籍+禁卡解析 | `protection.h` 新增 `resolve/policy()`，`economy.cpp` 两处改用；组合驱动按 (席位,卡,昼夜) 缓存解析结果 | 同上（修复前 r1 在 t=1500 出现 `_pvp_sun_due` 5000/4000 差异） |

| 墓碑吞噬者僵尸死后墓碑"不可被植物攻击、不能出兵" | 类型化内核死亡效果走了**原版单机的地块坟墓**（`GravebusterEffects::grave` 把格子改成"坟墓"方块），没有走 PvP 的 `_install_grave_deaths` 覆盖；魅惑死亡同样未走 PvP 登记 | 按用户决定改为"死后原地释放骨头"：V `PvP70Content.drop_bone` + `NativeBattle._install_grave_deaths`；类型化 `ContentZombies70::drop_bone`、`DeathServices::gravebuster_bone/gravebuster_charmed_plant`（组合层实现，含魅惑分支：准入检查、`_card` 登记、绑定墓碑）；落地格合法才生成骨头墓碑，昼夜均生效 | `test_results/pvp73/r4-pvp73_gravebuster_death`：12501 tick 数值一致，事件一致（释放 3 根骨头、2 个合法落点成墓） |
| 墓碑吞噬者僵尸伤害 | 新平衡（72 时用户要求改 3，"实际游戏内还是 6"） | 高于半血 3、半血及以下 6（用户先要 1.5，后改回 3）；植物（`plant_bite`/内容啃咬）、戴夫（`_player_damage`，72 版固定 6，这是"改成 3 实际仍是 6"的根因）、魅惑互咬（补丁 `zombie_bite_damage` ×10 → 30/60，72 版固定 60）三条路径 V/类型化同步 | `batch-gb3`：新场景 `pvp73_gravebuster_dave` 戴夫每口 3（52 口共 156），V/类型化 7501 tick 一致；`pvp73_gravebuster_bite` 仅原版寻路追踪投影字段（目标植物/目标位置/洪水cd）在第 1 tick 不同，忽略这些字段后 12501 tick 全一致（单位状态、事件、绘制帧均一致，属导出投影差异，不影响对局） |
| 模仿者复制甜椒投手/原始豌豆等变成西瓜/普通豌豆 | 类型化内核**从未移植** `NativeImitater`：变身按原生模板名种植，再被通用"出生登记"按模板卡登记；"变身成功"标记也从未设置（补光秘籍奖励因此会误发） | `ColdAdmission::imitate`（解析复制卡、死斗生产者拦截、模板工厂种植、配置/登记/内容配置/灰色/成功标记），`PlantRegionServices::imitate` 钩子；修了参数引用随名册扩容悬空的段错误 | `r4-pvp73_imitate`：5001 tick 一致，复制体登记为 `plant:甜椒投手` |
| 肆意模仿：僵尸方看不到模仿者实际费用 | V 键选的模仿目标只在本机界面状态，对方 HUD 只能按"上次种下的植物"计价 | 新房间指令 `copy_target`（仅显示用，不进战斗/回放），房间快照公开 `copy_targets`，对方卡栏用它计价 | 待联机实测 |
| 平衡数值 | 用户 PvP73 清单 | `balance.py`/`catalog.py`：草坪 25/16 秒（速植 12 秒）、石块 -25、石化火炬 48 秒、小鬼炮 275、报纸僵尸 275、滚桶 225、海盗船长 250；类型化冷卡表由当前 V 导出重新生成（与 Python 参照 232 张 0 差异） | `test_results/pvp73/catalog/` |
| 图鉴文字 | 只保留现行数值 | 去掉全部"PVP72："前缀与"原为…"；墓碑吞噬者/石块/草坪描述同步新机制 | 同上 |
| 合作 10000 金币跳关 | 新功能 | `Campaign.skip_day`、`CoopProgress.skip`（仅房主、在准备界面、扣房主座位 10000、所有入座玩家记通关并给奖励选择、不发通关金币）、房间指令 `coop_skip`、选卡界面"$10000 跳关"按钮（4 秒内二次确认） | 待实测 |

| AI 待办 A1/A2 | 72 按"已发布 V 行为"保留了两处 Python 设计失效 | A1：`layers11.cpp` 开启"死墓位"记忆；A2：`Zombie18::deploy_logic` 持有"解除封印"时出兵口视野判定恒真（等同 Python 临时补丁 `ztactics61.in_view`） | 有意改变 AI 行为，V 影子审计在此两处预期出现差异 |
| 版本号 | 用户决定升 73、拒绝 72 联机 | `extract/data/__init__.json` 与 `tools/pvp72_export_data.py` 的 BUILD → `1.6.0.73-typed.20261112`；`RULES['ruleset']='pvp73'`（规则哈希变化，72 客户端/回放判为不一致） | — |
| PC 升级覆盖 | 用户选"固定目录名 + 清理旧文件"；72 及更早没写过版本标记，存档目录已有 `player.json` 即视为升级并提示 | `main.cpp`：发布目录（有 SHA256SUMS 且≥1000 项）首次以新 build 启动时，只在 extract/图片/音乐/音效/fonts 中删除清单外的旧文件，记录到存档目录 `upgrade-cleanup.txt`，弹窗提示"已升级到 …，存档不变"；打包 zip 顶层目录固定为 `PvZ-PvP-Native` | 待打包验证 |
| 纯血门禁 | 用户要求全量测试加"动态函数必须纯血 C++" | V 运行时新增线程计数（Box 分配 + 调用分派）；`TypedBattle` 在 step / command_input / ai_tick 三个动态入口内取差值（AI 输入经 Room.command 的边界单独扣除），经 `backend_audit()['dynamic_v_work']` 公布；`tools/pvp73_pure_typed_gate.py` 跑真实 App 对局（对战 AI、合作 AI），要求三入口都执行过且计数全为 0；已接入 `tools/run_cpp_suite.py`（缺报告即失败）；`PVP_PURE_TYPED_STRICT=1` 时运行期直接抛错 | 待运行 |
| 安卓性能申请（原 PvP71 perf_boost） | C++ 版从未安装 provider | `src/app/perf_boost_native.cpp`：大核绑定、ADPF（dlsym，API 33+）、慢放时 30 帧、核心/频率/温控诊断与导出，安卓启动时安装 | 待真机 |
| 手机切后台返回卡顿（推测） | 每次回前台/重获焦点都会 `apply_display`，逻辑画布被重新创建、相关缓存全部失效 | `apply_scale` 在尺寸不变时复用现有逻辑画布 | 待真机 |
| 商店"不像原版" | PC 1280×800 下与 Python PvP66 截图逐项一致 | 待在手机宽屏/触屏下截图对比 | — |

| 联机越打越卡（渲染耗时 14→22 ms，60→50 帧） | 文字/图片缓存 `BudgetCache` 每次命中都 `move_to_end`：V 运行时里是线性查找 + 删除重插并使字典哈希索引失效；键 `(font, 文本, 颜色)` 含实例，索引不支持→整表线性比较；缓存越满越慢 | `src/ui/hand/native_budget_cache.cpp` 原生 O(1) LRU（同样的条目/字节上限与统计），`pm_bounded_cache.surface_cache` 改用它；V 字典索引对 pg `Font`/`Surface` 键按身份哈希；方法分派的标记符号改为静态驻留 | 本机两进程联机 60 秒：主机渲染约 7 ms、客机 7–10 ms，稳定 60 帧（之前 14→22 ms、50 帧） |
| 合作第 7 天等夜晚关卡 | 见上 | — | `r6` 起批量全过 |
| 结算动画/胜负音效（安卓） | PC 真实流程（投降→结算）正常：落败方镜头、"游戏结束"音效、开合动画中心标题都在 | pg 层在音效/音乐加载失败时写日志（SDL_Log），待真机 logcat | 待真机 |
| 铁道第 6 波"自动失败" | 白盒从第 6 波开局（`director.start_wave`）：一次刷 25 只，两名挂机戴夫 31 s/46 s 倒地判负，V 与类型化同一 tick 判负；高血量版 20000 tick 无判负且两侧逐 tick 一致 → 未发现自动判负逻辑 | 需要用户补充现象 | `r6-coop_rail8_w6*` |
| 既有分叉（待查） | 合作中戴夫倒地后，雪人僵尸追踪起跳与 V 在第 10535 tick 不同（两侧判负 tick 相同） | — | `r7-rail_real` |
| 滚桶僵尸死后脱落的滚桶不显示 | 用户说明"二类防具滚桶向实体转化，是两种状态"后定位：类型化原生帧对孤立滚桶调用 `presentation.draw_barrel`，而 App 组合层的该实现只是记录桩，从不画到画布（对拍工具走的是另一条记录路径，所以帧对拍看不出） | `frame_layer.inc` 的 `draw_barrel` 真正绘制（`barrels.draw`）；补发 `barrel_detached` 事件 | App 脚本 `bap7`：滚桶僵尸死后孤立滚桶 u7 每帧都有绘制命令（修复前 0 条），截图可见；`batch-gb3` 帧/数值一致 |
| 商店"不像原版" | 1280×800 与 Python PvP66 截图一致；2400×1080 触屏下完整显示（16:9 原图按高适配） | 需要用户截图 | — |
| A3 plant2 只移动不部署 | 2v2 全 AI 对局 plant 33 次、plant2 34 次部署，未复现 | — | — |

批量对拍（`batch73.py b1`）：70 个场景 68 个与当前源码录制的 V 参照逐 tick 一致（固定 58 + 补充 5 + 合作夜晚 + 模仿者 + 墓碑吞噬者死亡/魅惑 + 铁道高血量），其余 2 个见上表。

纯血门禁（`pure-gate-r1`）：对战 AI 1217 step / 1596 指令 / 572 AI tick，合作 AI、2v2 全 AI 同样，动态入口内 V 分配与调用全为 0。

## 出包（11-12，r2；r1 已作废删除）

- PC：`dist/PvZ-PvP-Native-20261112-pvp73-r2`（3453 文件，EXE `7add575f…`），`PvZ-PvP-Native-20261112-pvp73-r2.zip`（`a199953c…`，顶层目录固定 `PvZ-PvP-Native`）。检查：清单一致；解压后无关目录启动冒烟通过并进入类型化会话；覆盖 72 r5 目录升级（残留清理、存档保留、提示）；72 无版本标记但有存档 → 提示"原版本 PvP72 或更早"；全新安装不提示。证据 `test_results/pvp73/pc-package-20261112-pvp73-r2/summary.json`。
- 安卓：`dist/apk-pvp73-20261112/PvZ-PvP-Native-1.6.0.73-typed.20261112-1112073-20261112-pvp73-r2.apk`（`477e5233…`），versionCode 1112073，签名与正式版 r9b 同证书，APK 内 libmain 与候选一致（`0a45cb80…`）。未真机实测（用户要求直接出包）。
- 全量测试 `full-suite-r2`：2304 通过 / 50 失败 / 12 错误（15 项豁免）；对比 72 基线新增 20 项，全部是 PvP73 有意的规则变化（墓碑吞噬者残骸墓碑→骨头 15 项、费用/冷却 2 项、石化火炬 3 项…见上），r1 的两项 BudgetCache 回归已消除；纯血门禁 duel/coop/duo 全通过（动态入口 V 分配/调用均 0）。
- 测试判定随规则更新（用户 11-12 要求，未再跑整轮）：20 项直接改在生成的 C++ 测试里（原 Python 测试目录只读），每处带 `PvP73` 注释；单项复跑 20/20 通过。**以后若对这些模块重跑 `tools/gen_cpp_tests.py`，需重新套用：**
  - `pm_test_pvp_native_battle_combat.cpp`（其余 10 个模块继承同一方法）：墓碑吞噬者死后先有 `bone_released`，骨头落地后 1 个非生产墓碑 + `bone_grave` 事件，其余检查不变；
  - `pm_test_pvp_balance_economy.cpp`：昼夜都释放骨头并落地成墓（原为白天立即残骸、夜晚无）；
  - `pm_test_pvp_melon_remnants.cpp`：空中死亡不再悬空锚定，骨头落到下方地面成墓，西瓜伤害/出兵检查不变；
  - `pm_test_pvp_balance.cpp`、`pm_test_pvp_september_rules.cpp`：石块 -25、草坪 25/16 秒；
  - `pm_test_pvp_petrified_torch.cpp`：石化火炬冷却 48 秒（数值、经济列、卡面文字）。
- 对拍 `batch-gb3`：墓碑吞噬者（啃戴夫/死亡/魅惑）、滚桶脱落 逐 tick + 绘制帧一致。

V 再生成：`tools/pvp72_regenerate.py` 清单新增 `pve`、`coop_progress`（模拟层）与 `pve_ui`（界面层）为 72 自有源。合并冲突处理规则：本次新改动取新生成；72 版已审核的历史冲突（`pm_replay`、`pm_room` 类元数据等）保留现有代码；`pm_room` 的类型化手工接入保留并补入 `copy_targets` 重置；`pm_app` 因行尾差异整文件冲突，改用"旧生成→新生成"差量打补丁（7 处全部命中）。

说明：手机截图（第 7 天、0/7 波、夜晚水图）与本机复现的"合作夜晚开局崩溃"完全吻合；旧存档本身不是崩溃原因——本机 PvP67 格式合作存档改到第 7 天即可在修复前稳定复现，第 5 天（白天）正常。

## 待办（按用户清单）

见记忆；逐项完成后在上表追加。

## GitHub 发布（11-12）

- 仓库 `ruojimy/PVZ-Rouge-PvP`：新建 Release `v1.6.0.73-pvp73`（设为 Latest），附 PC 包、开发者包 `PvZ-PvP-Native-20261112-pvp73-r2-Developer-Package.zip`（`72b6e789…`，34 MB，`build/pvp73-tools/package_dev73.py` 生成，说明 `开发者包说明-PvP73.md`）、APK、`zh-SHA256SUMS.txt`；服务端摘要与本地一致。
- README 只替换中文部分（提交 `5e64c65`），英文 PvP64 部分不动。旧中文 PvP64 Release 保留：英文 Overlay 必须基于其中文开发者包。

## PvP73.1（2026-11-13，小版本修复）

用户最后确认：墓碑吞噬者半血前单次基础伤害回调到 3，半血及以下保持 6；保留移除旧补伤的修复。原版 `BonusPlants::grave_damage` 会在 native bite 之后将小于 6 的植物伤害补足到 6，正是短暂 6→3 随即继续扣血的根因。PvP 的 V match-owned patch namespace 与生产 typed BonusScan 均禁用此重复补伤。

- 开局补贴 +25 取消，周期规则保留；同步 Python 拥有源、生成 C++ 常量、静态冷卡表与发布数据。
- `ColdAdmission::imitate` 只配置工厂这次最初生成的植物；复制抓人草不会递归把新头配置成根。生头流程保留 PlantRef 值，避免名册扩容后使用悬空引用。
- `frame_layer.inc` 接通 FlyingPlants 的真实绘制；芦笋线弹及芜菁球弹不再只有观察桩。
- 内容植物替换包括灰色变体；三向射手的灰色完整图、根、头，以及水面的灰色素材用游戏自身 `换黑白` 生成（`src/uitools/pvp73_gray_assets.cpp`），进入正式图集。
- 二手防具按像素非透明边界裁切后等比渲染；保持原防具材质、拾取规则及快照只读。
- 云端观众每 2 秒进行只读 `spectator_watch` / `spectator_watch_ack` 往返，不注入对局输入。
- 回放：`Sound` 保留发出时的 tick。普通战斗音效用当帧 tick；房间经济音效在帧间发出时保留最后完成的 tick，稍后 drain 不会重标时。原有状态哈希与损坏检测保留。
- 项目长期要求已写入 AGENTS.md：每次出包同步本机实际 EXE，保存并核验摘要；仅保留最近一次备份，存档与回放不覆盖。

定向验收：`test_results/pvp73/r3-hotfix-final.json`（大蒜 3/6、专注 6/12、真实魅惑 30/60、抓人草 1/3 头、8 倍速往返 seek、损坏拒绝、11 种防具）；实际画面 `r3-visual/summary.json` 与 PNG；V 录制→typed 播放的 60 Hz 控制场景 `r3-v-replay.*`。完整套件、云端静置、最终包摘要另见本轮最终清单，不能把过程候选当成最终包。
