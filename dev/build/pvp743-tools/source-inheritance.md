# PvP74.3 源码继承静态核对

与已审核 PvP74.2 dev 实际文件逐一核对 SHA-256；先核对该基底与其原 manifest 一致。此核对不运行游戏，也不把字节一致当作本轮行为回归。

| 范围 | 上版文件 | 当前文件 | 未变化 | 改动 |
| --- | ---: | ---: | ---: | ---: |
| src | 1313 | 1318 | 1308 | 10 |
| build/typed72-integrated-v44/source/src/sim/typed | 342 | 342 | 342 | 0 |
| build/typed72-match-v1 | 212 | 212 | 210 | 2 |

基底摘要不符：0。完整新旧摘要、未变集合摘要与专项保留文件见 `source-inheritance.json`。

## 本轮改变的文件

- `src/sim/typed72_app/cold_export.cpp`：modified。
- `src/sim/typed72_app/composition/MANIFEST.json`：modified。
- `src/sim/typed72_app/composition/match_probe.cpp`：modified。
- `src/ui/hand/texture74_model.cpp`：modified。
- `src/uitools/pvp742_conveyor_deployment_audit.cpp`：added。
- `src/uitools/pvp742_conveyor_guest_display_audit.cpp`：added。
- `src/uitools/pvp742_crowd_stack_audit.cpp`：added。
- `src/uitools/pvp742_population_entry_audit.cpp`：added。
- `src/uitools/pvp742_rage_resource_audit.cpp`：added。
- `src/uitools/pvp742_ui_regressions_audit.cpp`：modified。
- `build/typed72-match-v1/cold72_export.cpp`：modified。
- `build/typed72-match-v1/match_probe.cpp`：modified。

## 重点继承

角斗士巨人/携带小鬼/二手防具、植物空间索敌、客机 move 刷新与 plant2 序号恢复、allocator，以及组合层拥有源均按当前工作区文件进入计划。各文件与上版是否相同及其 SHA-256 在 JSON 的 `critical_groups` 中逐项列出。

本轮按用户最新要求跳过新增对局与实机验证。74.2 全量和旧专项只证明各自记录的构建；本核对不声称 74.3 新全量通过。
