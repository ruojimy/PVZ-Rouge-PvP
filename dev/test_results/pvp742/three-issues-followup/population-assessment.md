# 合作人数上限冷接线复核

2026-11-14。密集堆叠复核时发现的独立问题，不作为“停止堆叠”的已确认根因。

## 可重现差异

通过真实 `Room.set_pve → 房主 Room.command(pve_population) → Room._start_pve → NativeBattle.spawn`，房间规则与 Director 均已收到设定，生产生成预算却仍使用默认40。

| 入口 | 修复前实际准入 | 修复后实际准入 |
| --- | ---: | ---: |
| 合作设2，尝试3只 | 3（错误） | 2 |
| 合作设40，尝试41只 | 40 | 40 |
| 合作设120，尝试121只 | 40（错误） | 120 |
| 普通对战规则写2，尝试5只 | 5 | 5 |

证据为 [修复前有效复现](population-before-r2.json)、[修复后11项](population-after.json) 及对应日志。最初 `population-before.json` 是错误地对已经启动的 typed wrapper 再做 cold export，出现夹具 TypeError，保留原记录；不把那次错误当游戏异常。

## 最小改动

`src/sim/typed72_app/cold_export.cpp` 与独立 `build/typed72-match-v1/cold72_export.cpp` 在冷边界读取原 `ScriptedSpawnBudget.limit` 的有效整数，导出 `scripted_spawn_limit`。原预算负责 Director 优先级、Python 整数转换和1–200约束，没有重新实现一套近似转换。

生产组合 owner `build/typed72-match-v1/match_probe.cpp` 的 `setup` 接入该值，保留 `budget.enabled` 的原模式开关。重新运行 `tools/typed72/make_app_composition.py`，生成组合源及清单。旧冻结冷输入没有新字段时仍保留其历史默认值；正常 Room 构造均走新导出。房间只允许在 config 阶段修改人数，所以每次对局冷入场解析一次符合现有契约。

附加的七组原规则输入 null、字符串整数、小数、布尔、负数、超限整数和无效字符串，其原冷预算值与生产准入分别一致，11/11通过。测试没有推进模拟、改位置或放宽准入；用户存档及活跃对局未操作。

## 边界

这是可配置人数失效的修复，不是堆叠算法或传送带架设修复。默认40与普通对战行为保持，密集堆叠仍需独立轨迹对照。当前是本地源码候选；发行74.2冻结全量结果不自动覆盖这些新源码，也不声称已上传或替换正式启动器。
