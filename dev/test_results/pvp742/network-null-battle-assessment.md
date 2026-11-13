# 配置/BP 快照 battle=None 回归修复

## 根因与最小改动

全量 r1 的 8 个新增 ERROR 均为 `AttributeError: 'NoneType' object has no attribute 'get'`，分布在 5 个 UI/TCP 模块。它们发生在尚未开战的合法房间快照：`battle` 键存在，值为 None。

客机确认输入序号的 PvP74.2 hook 为修复合作第二席位重连，将读取改为 `local_seats()` + `seat_view::player_for_authority_seat`。改动时遗漏了原有 `(value.get("battle") or {})` 的显式 None 处理。`get("battle", {})` 只在键不存在时返回默认值，不能替代 `or {}`，导致 helper 对 None 读取 players。

只恢复这个入口原有的 `py_or(..., {})`：

- 生产生成文件：`src/ui/gen/pm_app.cpp` 客机 `room_snapshot` 分支的 `L_acknowledged` 表达式。
- 再生所有者：`tools/pvp741_hooks.json` 对应 hook 的 after 表达式。
- `tools/pvp72_sources/app.py` 原本已经有 `or {}`，无需重复修改。

保留 `local_seats()`、第二席位反投影、原序号 max 合并；未修改 `seat_view` helper，未增加泛化异常 catch 或虚假默认战斗状态。

## 验证

`pvp741_apply_hooks.py --check` 通过。统一重新构建 `PvZPvPNative`、`cpp_tests`、`app_run`、`pvp742_network_refresh_audit` 全部 exit 0，日志 `null-battle-build-r1.log`；四个二进制哈希见 `null-battle-build-sha256.json`。

5 个受影响模块使用新 cpp_tests、隔离目录和 strict 模式重跑，全部通过，无豁免：

| 模块 | PASS | FAIL/ERROR |
|---|---:|---:|
| test_pvp_51_ui | 2 | 0 |
| test_pvp_53_features | 13 | 0 |
| test_pvp_56_ui | 9 | 0 |
| test_pvp_57_map_editor | 8 | 0 |
| test_pvp_57_room_requests | 8 | 0 |
| 合计 | 40 | 0 |

证据目录 `null-battle-suite-r1/`，包含逐模块 JSON、status JSON 与日志。该轮 runner 总体 exit 1：模块 40/40 后，自动附加门禁的 duel/coop 通过，duo 的测试工具日志被截断而无法解析。不能将该轮总体声称为通过；下节记录工具修正及全部三模式独立重验。

网络专项的既有 guest_rejoin 用例加入真实 `Room(config, coop)` 的 `battle=None` 快照，经过 `pack_snapshot → Application.poll_network → merge_view`，断言成功处理且 plant2 序号保持 0；随后原战斗快照恢复 50，下一条 51 被主机接受。基础/优化两组仍各 10/10，battle 快照、按键输入顺序与复活玩家状态严格相同，`map_sync_error=false`。

网络证据 `network-refresh-audit-r5-null-battle/comparison.json` 的 passed 为 true，两个进程 exit 0；该轮用于正确性，未当作正式性能计时。此前 r4 的有效性能证据不由本轮并行 gate 下的时长替换。

修复后主 EXE SHA-256：`0981d73a1e8a3df39a344275bc46a979fd10df6e356a1f7d7621a2d3462d4641`。

## 门禁工具输出修复与独立重验

`src/uitools/app_run.cpp` 的 script call 分支原本对所有返回值显式执行 `dump(r).substr(0,2000)`。新性能计数增多后，duo 的 backend_audit JSON 超过 2000 字符，截在 `mode` 字符串内部；`pvp73_pure_typed_gate.py` 解析该不完整日志失败。这是工具输出错误，不是零 V 检查发现战斗调用 V，也不是新的 NoneType 错误。

唯一工具修复：`room.battle.backend_audit` 走完整 `PURE_TYPED_AUDIT` 记录，仍由原 `say` 同时输出 stderr 和 script.log；其他 call 日志保留原 2000 字符上限。未修改 runner/gate 标准，未删除性能计数或裁剪审计字段。仅重编 app_run，日志 `audit-output-build-r1.log`。

独立运行原版三模式门禁，`null-battle-pure-gate-r2/pure-typed-gate.json` passed=true、进程 exit 0。`output-integrity.json` 检查每份完整报告与工具修改前 duel 报告的性能键集合一致（55 键），存在 JSON 末尾 `v_native_tick_now`；每个要求入口实际执行且 V boxes/calls 为 0。

| 场景 | JSON 整行字符 | step / command_input / ai_tick 实际入口次数 | 三入口 V boxes/calls |
|---|---:|---|---|
| duel_ai | 1940 | 1221 / 1573 / 566 | 全部 0 |
| coop_ai | 1898 | 896 / 1197 / 443 | 全部 0 |
| duo_ai | 2151 | 1229 / 2325 / 2272 | 全部 0 |

总 V 活动计数均非 0，确认计数器存活。duo 原本被截断的长记录现在完整解析；55 个计数保留。最终 app_run SHA-256：`546342a99aed1ee6451d9a757123bbed1bcb242af2b773b8169416ed7e15e4d6`。主 EXE、cpp_tests 与网络 audit 未因本次工具输出单点重链。
