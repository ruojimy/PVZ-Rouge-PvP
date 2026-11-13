# 合作密植闪退：std::map 缺键审计

## 异常来源

当前 MSVC 14.43.34808 的 `include/map` 第 352、361 行，`std::map::at` 缺键抛出 `std::out_of_range("invalid map<K, T> key")`。这与 `V` 字典、nlohmann JSON、typed Store、vector 越界的报错文字不同。不能仅凭此文字就将问题归为内存不足，也不能据此证明是新空间网格失效。

## 生产调用核对

审计范围为当前生产阶段 `build/typed72-integrated-v44/source/src/sim/typed/`、组合来源 `build/typed72-match-v1/` 及应用/UI/core/动态兼容层；不把早期 typed 核心当成生产。

| 位置 | std::map 的 at 调用 | 当前约束与判断 |
|---|---|---|
| `native_canvas.cpp:install` | `atlas.atlas.at(name)`、`before.at(name)` | 会话创建期；来源是 cold exporter 的 `world/world_before`。需确认同一导出物内键一致；不会在每株植物索敌时调用。 |
| `native_canvas.cpp:tint_poison` | `colors.at(level)` | 颜色表仅 1、2 两级；`NativeStatus::apply` 严格拒绝其他级别。应以真实毒气/毒镖攻击覆盖两级，不能用默认颜色隐藏异常状态。 |
| `native_canvas.cpp:tint_roots` | `atlas.atlas.at(key)` | key 来自同一 atlas 当前遍历结果，循环期间只替换值，不删键。 |
| `native_plant_draw.cpp:show` | `atlas.at(old)`、`atlas.at(next)` | 两个键均由同一分支的 contains 检查保护；后续只替换值。 |
| `expansion_art.cpp:alias_one` | `store_.atlas.at(old/next)` | 当前 `alias` 调用先验证两键。真实 ExpansionCombat 服务路由到 NativeCanvas 的 find 保护别名接口。 |
| `september_zombies.cpp:chase` | `banks_.at(key)` | 超过 64 项淘汰时保留当前 shared_ptr、清空后重新插入当前 key；测试须真实覆盖超过 64 个不同目标格。 |
| `ai/controller.cpp` | `side_threat.at(±1/-main_front)`、`SHELL_VINES.at(k)` | 首个表初始化 ±1 后才使用；藤蔓角色只由同一个 SHELL_VINES 清单产生。 |
| `sim/pvp/pvprt.cpp` | `module_attr_tables().at(root)` | 同一分支先 count，模块注册只插入/替换，不删除。 |
| `sim/terrain.cpp` | `wl.at(map_id)` | 同一表达式先 count；地图初始化期。 |
| `ui/hand/texture74_network.cpp` | `parts.at(n)` | 分片索引先验证 0≤n<chunks，且所有不同分片收齐才拼接；同步错误有专门错误路径，不会进入战斗模拟。 |

`ProducerPolicy::cards`、cold catalog、typed Store 的实体指针索引等为 unordered_map；缺键文字与 std::map 不同。FrameProjection、NativeCanvas 的 tint 缓存、动画 LRU、目标查询缓存本身使用 find，不以 `map::at` 读取缺省项。MovingCoverageGrid/MovingPointGrid 的 `.at` 是 vector 条目读取，不是 std::map。

截至静态审计没有找到一个可证明的合法输入缺键路径，因此没有把 `.at` 改成 `[]`、没有设置假默认值，也没有新增生产 catch 吞错。父代理新增的原始 C++ throw-site 栈记录用于捕捉真正的失败调用位置。

## 回归入口

`src/uitools/pvp742_map_key_audit.cpp` 使用真实生产 Session 和 WorldView，隔离用户数据，SDL dummy。测试包含工具链异常指纹、夜晚大喷菇+毒气与回旋镖+毒镖秘籍的真实两级中毒命中、70 个雪人/植物目标格、混合抓人草/芦笋战机/黑桶的重复会话创建绘制销毁。

第一项故意触发并在测试内部捕获 map/unordered_map 缺键，仅确认错误原文，不能计为游戏崩溃复现。其他项任何异常均失败，并打印原 throw-site 栈。

## 2026-11-14 实测结果

Windows Release，`SDL_VIDEODRIVER=dummy`、`SDL_AUDIODRIVER=dummy`、`PVP_CAPTURE_CPP_TRACE=1`，独立 `PVP_USERDATA=test_results/pvp742/map-key-r3-userdata`。最终 `map-key-r3.json` 为 4/4 通过，进程 exit 0。

| 检查 | 实际结果 |
|---|---|
| STL 缺键指纹 | map 为 `invalid map<K, T> key`，unordered_map 为 `invalid unordered_map<K, T> key`，可区分。 |
| 真实一级/二级中毒及显示 | 150 room ticks；一级中毒观测 133 次，二级 134 次；实际 WorldView 绘制 30 次，无异常。 |
| 雪人共享路径 bank 淘汰边界 | 70 个雪人实际选中最多 70 个不同地面植物目标，超过 64 bank 上限；18 room ticks、6 次 WorldView 绘制，无异常。 |
| 混合会话创建/销毁 | 4 个独立会话，共 192 次真实植物/僵尸生成，48 次实际 WorldView 绘制，无异常。 |

这些是有限的确定性生产路径覆盖，不是性能测试，也不能证明用户报告的偶发合作闪退已经修复。合作密植三主体+壳、第二席位、昼夜/地图扩展由另一个独立生命周期专项覆盖。后续真实异常需要原 throw-site 记录来定位具体键和值状态。

前两轮的失败属于测试条件错误，证据保留：r1 把派生毒镖直接放进起手卡组，被合法卡牌校验拒绝；改为基础回旋镖+秘籍。空中坚果没有承托，按原规则被删除，未触发多目标门槛；r3 改成 70 个不同地面格。r2 的失败诊断本身对空数组使用 JSON `.at(0)`，已修为输出 null，未改生产。

原始抛出栈在前两轮分别准确定位到 `pm_simulation.cpp:287` 的卡牌校验，以及 audit 自身的 JSON 越界；未将这些 fixture 异常当作用户游戏复现。

证据：`map-key-r3.json`、`map-key-r3.log`、`map-key-build-r3.log`。本轮 audit EXE SHA-256：`1cd08d791a0d1217a6c0dcfed6edd5eea0a897ff721174b74273f3d35c262b03`。

本专项只新增测试与证据，没有修改生产战斗逻辑，没有对缺键使用假默认值，也没有新增 catch 掩盖错误。
