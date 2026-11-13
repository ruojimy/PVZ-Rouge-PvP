# 项目长期约定

- 用户于 2026-11-12 明确要求：根目录原生启动器必须启动最新正式交付构建。出包后同步更新本机启动入口，并核对实际目标 EXE 的 SHA-256；不能只生成 dist 包而继续启动旧副本。
- 项目备份只保留最近一次，统一放在 `backup-latest/`，每轮更新替换这一组备份。存档、回放、测试证据和构建必需的冻结阶段不是可随意清除的备份。
- 保留启动器既有的独立存档目录。发布包默认用户数据路径与本机独立存档分别核验，禁止用测试存档覆盖用户存档。
- PvP73 的实际生产内核由 `build/typed72-integrated-v44/source/src/sim/typed/` 编译；组合层来源是 `build/typed72-match-v1/{match_probe.cpp,frame_layer.inc,snapshot_layer.inc}`，由 `tools/typed72/make_app_composition.py` 生成到 `src/sim/typed72_app/composition/`。不要只修改早期 `src/sim/typed/` 就宣称生产修复生效。
- `Downloads/PVZ-Rouge-v1.4.8/next-pvp71` 为只读参照。更新本项目拥有的源文件、生成桥和测试，禁止改写参照目录。

- PvP74 材质系统由 `src/ui/hand/texture74_*.cpp` 拥有。重新翻译 UI 后运行 `tools/pvp74_apply_hooks.py`，`--check` 是构建门禁；资源清单由 `tools/pvp74_resource_catalog.py` 生成。覆盖必须只作用于显示，禁止把材质 PNG 写进生产模拟图集或粒子采样；共享只接受房主方向，退出后恢复用户本地包。
- PvP74.1 的共用掉帧控制与平铺笔画补丁由 `src/ui/hand/pressure_pacing.cpp`、生产阶段 `NativeCanvas` 和 `tools/pvp741_hooks.json` 拥有；UI 重新生成后再运行 `tools/pvp741_apply_hooks.py`，构建时 `--check` 拒绝缺失补丁。合作昼夜投影只限 `director.coop_cycle()`；PvP 昼夜、雨天保持开局地图环境原样，不能补入改变回放哈希的缺省字段。
- 用户于本轮明确：抓人草对僵尸戴夫单次伤害为 4，原图鉴 8 是文案错误。图鉴与机制冲突先查已有全量回归的明确断言；已覆盖时按回归约束，未覆盖时按图鉴；用户明确更正优先。

- PvP74.1 动画配方缓存使用 `src/core/render_cache.*` 的链表加哈希索引，图像尺寸、透明度和淘汰顺序保持原契约；`PVP741_RENDER_LRU=0` 仅用于对照。函数计时由 `PVP741_PROFILE=1` 显式启用，默认关闭，不得混入回放或战斗状态。周期坐标索引必须核对实时单位坐标、重新解析 Motion，英雄代理始终读取实时指针。
