# 旧 Python 全量测试 → 纯 C++ 版 覆盖对照

生成：`tools/old_suite_inventory.py` + `tools/coverage_map.py`。旧套件 = `next-pvp71/tests/test_pvp_*.py`（pvp71 基线 232 模块 / 2548 例，现有 235 模块 / 2561 例；另有旧 C++ 闸门 cpp-gate）。

**判定口径（严格）**：「已覆盖」= 该模块的断言已经在 C++ 构建上执行并通过；只有相同功能的 C++ 集成测试、但没有执行同样断言的，一律记「待迁移」，并在「相关 C++ 测试」列注明重叠部分；「不适用」= 被测对象是 C++ 版不存在的 Python/打包/多进程机制，附原因。

## 汇总

| 状态 | 模块 | 用例 |
|---|---|---|
| 已覆盖 | 0 | 0 |
| 待迁移 | 200 | 2326 |
| 不适用 | 35 | 235 |
| 合计 | 235 | 2561 |

| 主题 | 模块 | 用例 | 其中待迁移用例 | 其中不适用用例 |
|---|---|---|---|---|
| 战斗内核/规则/数值 | 104 | 1118 | 1115 | 3 |
| UI/渲染 | 64 | 875 | 875 | 0 |
| AI | 14 | 166 | 166 | 0 |
| 联机/中继/观战 | 17 | 148 | 148 | 0 |
| 打包/发行/工具链 | 9 | 72 | 0 | 72 |
| 安卓平台 | 11 | 60 | 11 | 49 |
| 多进程/多 worker | 7 | 56 | 0 | 56 |
| 原版字节码/补丁运行时 | 8 | 55 | 0 | 55 |
| 回放/审计 | 1 | 11 | 11 | 0 |

## 实际执行的是 Python 还是 C++

- **旧套件（2561 例）**：CPython 3.8 运行 modkit/pvp 源码（+ 旧 _pvpcore C++ 加速核心 pyd，真 pygame/SDL）。它们验证的是 Python 发行版，**没有一条调用纯 C++ 版**。
- **C++ 套件（tools/full_test.sh，17 组）**：
  - `check_all`：C++ run_battle.exe（翻译后的战斗内核）逐刻输出 vs CPython 预先录制的 oracle（extract/oracle/*.jsonl，34 场景：全部 232 卡、秘籍、输入、墓碑、2v2、合作波次）；比较脚本为 Python
  - `smoke`：C++ app_run.exe 运行翻译后的 smoke.py 驱动（主页→配置→BP→对战→结算→再来一局）
  - `evidence`：C++ app_run.exe：smoke + 各阶段截图 + 回放保存/重放终点校验 + 固定 AI 房
  - `almanac`：C++ app_run.exe：本地房 BP 中右键全部 232 张卡（简略/详细图鉴）渲染
  - `probe`：C++ app_run.exe：mixer/音效/音乐/全屏切换
  - `mapedit`：C++ app_run.exe：地图编辑器画图→保存→回读→开房使用
  - `cooplobby`：C++ app_run.exe：主页合作入口→固定合作 AI 房→闯关→对战，AI 队友种植
  - `airoom`：C++ app_run.exe：大厅固定 AI 房（r22）BP+对战 30 秒
  - `regex`：C++ re 引擎 vs CPython re 的期望值（27 条）
  - `nettest`：C++ ServerTransport/ClientTransport 同进程回环握手+双向消息
  - `netpeer_duel`：3 个 C++ 进程：主机/客机/观战，TCP 回环 BP→对战→投降→回放校验
  - `netpeer_coop`：2 个 C++ 进程：合作房队伍聊天
  - `netpeer_relay`：2 个 C++ 进程经公网中继私有房 BP→对战
  - 其中只有 `check_all` 的参照数据与 `regex` 的期望值来自 CPython；被测对象全部是 C++ 二进制。

## 不适用、但 C++ 版需新写等价测试

| 旧模块 | C++ 版要新写的测试 |
|---|---|
| 57_android_userdata | C++ APK：卸载重装/升级后 files/pvp_userdata 存档保留 |
| 67_android_upgrade | C++ APK：覆盖安装同签名新版本，存档与设置保留；包内不含凭据 |
| 67_android_fullscreen | C++ APK：沉浸式全屏、切后台/回前台后画面与输入恢复 |
| android_audio | C++ APK：音效/音乐播放，切后台暂停、回前台恢复 |
| android_label | C++ APK：启动器名称为正确 UTF-8 中文 |
| storage_inputs | C++ 发行包/APK 不含 keystore.env、私有存档、开发工具 |
| 57_update | C++ 版若提供更新器，需新写覆盖安装测试（当前未提供） |

另：`perf_boost`（安卓性能申请 ADPF/绑大核，11 例）在 C++ APK 中**功能尚未移植**，记为待迁移（先移植功能再迁测试）。

## 迁移方案

1. **翻译测试模块**：用现有 pvp2cpp 把 `tests/test_pvp_*.py` 翻成 C++（被测模块已是翻译代码，导入关系一致），配一个 C++ unittest 外壳（TestCase / assert* / setUp / tearDown / subTest / skip、临时目录、APPDATA 隔离），生成 `cpp_tests.exe`，按模块分组并行，输出与旧套件同格式的 Ran/OK/FAIL。每个旧断言都在 C++ 上执行后，对应模块才从「待迁移」改为「已覆盖」。
2. **翻译测试时要补的运行期能力**：unittest.mock（patch、MagicMock）、tempfile、subprocess（联机测试起本地中继 server/*.py 作为 Python 夹具，被测仍是 C++ 客户端）、pygame 像素读取与事件注入的完整兼容、importlib.reload 等。
3. **安卓成品测试**（测 APK 本身，不能拿 PC 结果代替）：模拟器 x86_64 与真机 arm64 各跑一遍：首次安装解压→起名→主页→本地对战→教学关卡→联机直连/中继→回放→地图编辑器→切后台恢复→覆盖安装保留存档→长时间运行的内存/帧率，留设备日志与截图。
4. 上面两项都通过之前，现有 `dist/PvZ-PvP-Native`（PC）和 APK 只算**候选包**，不算全量验收通过。

## 逐模块清单

| 旧模块 | 用例 | 主题 | 状态 | 原因 / 迁移方式 | 相关 C++ 测试（仅功能重叠，非断言等价） | 旧测试说明 |
|---|---|---|---|---|---|---|
| 66_ai_capability | 10 | AI | 待迁移 | pvp2cpp 翻译测试模块（unittest 外壳），直接调用 C++ 内核 | check_all, airoom, evidence(固定AI房) | AI capability regression on the EMBEDDED AI (modkit/pvp/rv_*), user requirement 10-13. |
| 66_ai_gates | 10 | AI | 待迁移 | pvp2cpp 翻译测试模块（unittest 外壳），直接调用 C++ 内核 | check_all, airoom, evidence(固定AI房) | AI release gates (full suite, user requirement 10-13): |
| 66_ai_maps_gift_oct16 | 6 | AI | 待迁移 | pvp2cpp 翻译测试模块（unittest 外壳），直接调用 C++ 内核 | check_all, airoom, evidence(固定AI房), mapedit | Oct16 feedback: continuous ladder inputs, usable maps and teammate grants. |
| 66_duo_ai | 2 | AI | 待迁移 | pvp2cpp 翻译测试模块（unittest 外壳），直接调用 C++ 内核 | check_all, airoom, evidence(固定AI房) | PvP66 2v2 fixed lobby room: three seats taken by the room's players, a full match flows. |
| 66_feedback | 19 | AI | 待迁移 | pvp2cpp 翻译测试模块（unittest 外壳），直接调用 C++ 内核 | check_all, airoom, evidence(固定AI房) | Player feedback: native outcomes, team consent, BP and actual UI controls. |
| 66_feedback_ai_oct15 | 3 | AI | 待迁移 | pvp2cpp 翻译测试模块（unittest 外壳），直接调用 C++ 内核 | airoom, evidence(固定AI房) | AI surrender follows the actual human seat, including a watching host. |
| 66_firing | 8 | AI | 待迁移 | pvp2cpp 翻译测试模块（unittest 外壳），直接调用 C++ 内核 | check_all, airoom, evidence(固定AI房) | Current embedded r19: route-aware planting, with real native hit checks. |
| 66_firing_replan | 7 | AI | 待迁移 | pvp2cpp 翻译测试模块（unittest 外壳），直接调用 C++ 内核 | check_all, airoom, evidence(固定AI房) |  |
| 66_team_support | 16 | AI | 待迁移 | pvp2cpp 翻译测试模块（unittest 外壳），直接调用 C++ 内核 | check_all, airoom, evidence(固定AI房) | Safety, resource, ownership and timing boundaries for teammate support. |
| 67_coop_growth_oct18 | 7 | AI | 待迁移 | pvp2cpp 翻译测试模块（unittest 外壳），直接调用 C++ 内核 | airoom, evidence(固定AI房), cooplobby | Co-op restrictions and real fixed/invited AI preparation commands. |
| 68003_balance | 22 | AI | 待迁移 | pvp2cpp 翻译测试模块（unittest 外壳），直接调用 C++ 内核 | check_all, airoom, evidence(固定AI房) | PvP68 68003 balance update through the original 250 Hz engine. |
| 68004_minor | 30 | AI | 待迁移 | pvp2cpp 翻译测试模块（unittest 外壳），直接调用 C++ 内核 | check_all, airoom, evidence(固定AI房) | PvP68 68004 minor update. |
| 70_balance | 16 | AI | 待迁移 | pvp2cpp 翻译测试模块（unittest 外壳），直接调用 C++ 内核 | check_all, airoom, evidence(固定AI房) | Focused native-engine regressions for the post-70006 balance update. |
| fixed_room | 10 | AI | 待迁移 | pvp2cpp 翻译测试模块（unittest 外壳），直接调用 C++ 内核 | check_all, airoom, evidence(固定AI房) | PvP65 fixed lobby room: offline host room, seat lifecycle, delays, records, names. |
| 51_performance | 5 | UI/渲染 | 待迁移 | pvp2cpp 翻译测试模块，跑在 pvzui（SDL 兼容层）上；像素断言需兼容层逐像素一致 | check_all, smoke, evidence, evidence(回放) | Real pygame pixels, immutable local frames and native replay parity. |
| 51_ui | 2 | UI/渲染 | 待迁移 | pvp2cpp 翻译测试模块，跑在 pvzui（SDL 兼容层）上；像素断言需兼容层逐像素一致 | check_all, smoke, evidence | Seven configurable card slots and read-only synchronized spectator BP. |
| 52_performance | 8 | UI/渲染 | 待迁移 | pvp2cpp 翻译测试模块，跑在 pvzui（SDL 兼容层）上；像素断言需兼容层逐像素一致 | check_all, smoke, evidence, evidence(回放) | Same-tick authority, deferred pixels, camera changes and measured hot paths. |
| 53_features | 13 | UI/渲染 | 待迁移 | pvp2cpp 翻译测试模块，跑在 pvzui（SDL 兼容层）上；像素断言需兼容层逐像素一致 | check_all, smoke, evidence, evidence(回放) | Rally authority/movement/replay and editable backgrounds/weather. |
| 54_ui | 10 | UI/渲染 | 待迁移 | pvp2cpp 翻译测试模块，跑在 pvzui（SDL 兼容层）上；像素断言需兼容层逐像素一致 | check_all, smoke, evidence | PvP54 mobile actions and live native card-bank display regressions. |
| 56_ui | 9 | UI/渲染 | 待迁移 | pvp2cpp 翻译测试模块，跑在 pvzui（SDL 兼容层）上；像素断言需兼容层逐像素一致 | check_all, smoke, evidence, evidence(回放) | Real SDL input/layout, native replay timing and persistent identity checks. |
| 57_deathmatch | 7 | UI/渲染 | 待迁移 | pvp2cpp 翻译测试模块，跑在 pvzui（SDL 兼容层）上；像素断言需兼容层逐像素一致 | check_all, smoke, evidence, evidence(回放) |  |
| 57_map_editor | 8 | UI/渲染 | 待迁移 | pvp2cpp 翻译测试模块，跑在 pvzui（SDL 兼容层）上；像素断言需兼容层逐像素一致 | check_all, smoke, evidence, evidence(回放), mapedit | Expanded native palettes, color persistence and pointer-safe palette panels. |
| 57_rematch | 4 | UI/渲染 | 待迁移 | pvp2cpp 翻译测试模块，跑在 pvzui（SDL 兼容层）上；像素断言需兼容层逐像素一致 | check_all, smoke, evidence | Same-deck rematches retain the legal draft and build a fresh native battle. |
| 58_features | 35 | UI/渲染 | 待迁移 | pvp2cpp 翻译测试模块，跑在 pvzui（SDL 兼容层）上；像素断言需兼容层逐像素一致 | check_all, smoke, evidence, evidence(回放) | PvP58: vines, petrified vine, two secrets, pea range, torch income and fixes. |
| 58_ui | 4 | UI/渲染 | 待迁移 | pvp2cpp 翻译测试模块，跑在 pvzui（SDL 兼容层）上；像素断言需兼容层逐像素一致 | check_all, smoke, evidence | PvP58 pointer regressions through the real app: sun sweep and rally flag. |
| 59_features | 17 | UI/渲染 | 待迁移 | pvp2cpp 翻译测试模块，跑在 pvzui（SDL 兼容层）上；像素断言需兼容层逐像素一致 | check_all, smoke, evidence | PvP59: dense coffee, masochist rise, clover winds, turnip/gloom vs Dave, |
| 59_stack_care | 13 | UI/渲染 | 待迁移 | pvp2cpp 翻译测试模块，跑在 pvzui（SDL 兼容层）上；像素断言需兼容层逐像素一致 | check_all, smoke, evidence | Native deployment and real UI paths for the capped-stack/care revision. |
| 60_features | 14 | UI/渲染 | 待迁移 | pvp2cpp 翻译测试模块，跑在 pvzui（SDL 兼容层）上；像素断言需兼容层逐像素一致 | check_all, smoke, evidence | PvP60 focused native deployment, economy gates, turning and card artwork. |
| 61_art | 7 | UI/渲染 | 待迁移 | pvp2cpp 翻译测试模块，跑在 pvzui（SDL 兼容层）上；像素断言需兼容层逐像素一致 | check_all, smoke, evidence, evidence(回放) | Focused native art/status checks; no whole-suite certification. |
| 61_features | 31 | UI/渲染 | 待迁移 | pvp2cpp 翻译测试模块，跑在 pvzui（SDL 兼容层）上；像素断言需兼容层逐像素一致 | check_all, smoke, evidence, evidence(回放) | PvP61 focused checks: balance, grave sleep, reeds, secrets, scarecrow, crow, |
| 62_features | 13 | UI/渲染 | 待迁移 | pvp2cpp 翻译测试模块，跑在 pvzui（SDL 兼容层）上；像素断言需兼容层逐像素一致 | check_all, smoke, evidence | PvP62 feature requests. |
| 62_tick_rate | 4 | UI/渲染 | 待迁移 | pvp2cpp 翻译测试模块，跑在 pvzui（SDL 兼容层）上；像素断言需兼容层逐像素一致 | check_all, smoke, evidence, evidence(回放) | PvP62: 60 Hz room steps on PC hosts with the C++ core. |
| 63_features | 10 | UI/渲染 | 待迁移 | pvp2cpp 翻译测试模块，跑在 pvzui（SDL 兼容层）上；像素断言需兼容层逐像素一致 | check_all, smoke, evidence, evidence(回放) | PvP63 source-only regression checks through the original 250Hz engine. |
| 64_art_positions | 3 | UI/渲染 | 待迁移 | pvp2cpp 翻译测试模块，跑在 pvzui（SDL 兼容层）上；像素断言需兼容层逐像素一致 | check_all, smoke, evidence, evidence(回放) | Regression evidence for the requested squash art and lily waterline/layers. |
| 64_features | 78 | UI/渲染 | 待迁移 | pvp2cpp 翻译测试模块，跑在 pvzui（SDL 兼容层）上；像素断言需兼容层逐像素一致 | check_all, smoke, evidence, evidence(回放) | PvP64 focused checks through the original 250 Hz engine. |
| 66_feedback_runtime_oct15 | 6 | UI/渲染 | 待迁移 | pvp2cpp 翻译测试模块，跑在 pvzui（SDL 兼容层）上；像素断言需兼容层逐像素一致 | check_all, smoke, evidence | Player feedback: actual prices, finite cart ammo, graves and co-op HUD. |
| 66_material_maps_oct16 | 5 | UI/渲染 | 待迁移 | pvp2cpp 翻译测试模块，跑在 pvzui（SDL 兼容层）上；像素断言需兼容层逐像素一致 | smoke, evidence, evidence(回放), mapedit | New material/state, secret-picture and campaign-map integration checks. |
| 66_native_seed_bank_oct15 | 5 | UI/渲染 | 待迁移 | pvp2cpp 翻译测试模块，跑在 pvzui（SDL 兼容层）上；像素断言需兼容层逐像素一致 | smoke, evidence | Original-bank pixel fixtures captured before the renderer implementation. |
| 66_pause_stun | 5 | UI/渲染 | 待迁移 | pvp2cpp 翻译测试模块，跑在 pvzui（SDL 兼容层）上；像素断言需兼容层逐像素一致 | check_all, smoke, evidence | Native movement windows and multi-seat pause controls. |
| 66_pve_ui | 29 | UI/渲染 | 待迁移 | pvp2cpp 翻译测试模块，跑在 pvzui（SDL 兼容层）上；像素断言需兼容层逐像素一致 | check_all, smoke, evidence, cooplobby | PvP66 PvE screens in the original layout, team chat and IME handling. |
| 66_room_layout_oct15 | 6 | UI/渲染 | 待迁移 | pvp2cpp 翻译测试模块，跑在 pvzui（SDL 兼容层）上；像素断言需兼容层逐像素一致 | smoke, evidence | Real map previews, seat cards and connection/footer geometry at small/wide sizes. |
| 66_secondhand_art_oct15 | 4 | UI/渲染 | 待迁移 | pvp2cpp 翻译测试模块，跑在 pvzui（SDL 兼容层）上；像素断言需兼容层逐像素一致 | check_all, smoke, evidence | Second-hand armour keeps its existing black art across wire snapshots. |
| 66_ui | 14 | UI/渲染 | 待迁移 | pvp2cpp 翻译测试模块，跑在 pvzui（SDL 兼容层）上；像素断言需兼容层逐像素一致 | check_all, smoke, evidence | PvP66 real Application screens: PvE campaign, mode switch and team HUD. |
| 67_art | 2 | UI/渲染 | 待迁移 | pvp2cpp 翻译测试模块，跑在 pvzui（SDL 兼容层）上；像素断言需兼容层逐像素一致 | smoke, evidence | Independent rotor, transparent single-muzzle vine and shared atlas checks. |
| 67_scaled_display | 14 | UI/渲染 | 待迁移 | pvp2cpp 翻译测试模块，跑在 pvzui（SDL 兼容层）上；像素断言需兼容层逐像素一致 | smoke, evidence | PVP_SCALED display backend: off is inert, on keeps one coordinate space, |
| 68_performance_foundation | 12 | UI/渲染 | 待迁移 | pvp2cpp 翻译测试模块，跑在 pvzui（SDL 兼容层）上；像素断言需兼容层逐像素一致 | check_all, smoke, evidence | Exact timing cohorts, bounded caches/queues and unchanged snapshot bytes. |
| 68_wave_population | 11 | UI/渲染 | 待迁移 | pvp2cpp 翻译测试模块，跑在 pvzui（SDL 兼容层）上；像素断言需兼容层逐像素一致 | check_all, smoke, evidence | Campaign population, completion gates, save compatibility and authority. |
| barrel_crush_visual | 4 | UI/渲染 | 待迁移 | pvp2cpp 翻译测试模块，跑在 pvzui（SDL 兼容层）上；像素断言需兼容层逐像素一致 | smoke, evidence, evidence(回放) | Moving wooden barrels must use the native giant/vehicle squash remains. |
| chili_zombie_fire | 5 | UI/渲染 | 待迁移 | pvp2cpp 翻译测试模块，跑在 pvzui（SDL 兼容层）上；像素断言需兼容层逐像素一致 | check_all, smoke, evidence | Chili-zombie death fire: allegiance, one judgement per explosion, launch lock. |
| content | 117 | UI/渲染 | 待迁移 | pvp2cpp 翻译测试模块，跑在 pvzui（SDL 兼容层）上；像素断言需兼容层逐像素一致 | check_all, smoke, evidence | Actual native combat acceptance for the pirate/ancient content batch. |
| content_acceptance | 18 | UI/渲染 | 待迁移 | pvp2cpp 翻译测试模块，跑在 pvzui（SDL 兼容层）上；像素断言需兼容层逐像素一致 | smoke, evidence, evidence(回放) | Cross-system acceptance: native callbacks, draft rules and client assets. |
| custom_maps | 13 | UI/渲染 | 待迁移 | pvp2cpp 翻译测试模块，跑在 pvzui（SDL 兼容层）上；像素断言需兼容层逐像素一致 | check_all, smoke, evidence, mapedit | Persistence, authority, native combat and rendered editor acceptance. |
| deployment_controls | 15 | UI/渲染 | 待迁移 | pvp2cpp 翻译测试模块，跑在 pvzui（SDL 兼容层）上；像素断言需兼容层逐像素一致 | check_all, smoke, evidence | Public placement and real SDL press regressions, including fortress steps. |
| display_pipeline | 6 | UI/渲染 | 待迁移 | pvp2cpp 翻译测试模块，跑在 pvzui（SDL 兼容层）上；像素断言需兼容层逐像素一致 | check_all, smoke, evidence, evidence(回放) | Shared display quality must preserve authority, coordinates and UI scale. |
| draw_cache | 2 | UI/渲染 | 待迁移 | pvp2cpp 翻译测试模块，跑在 pvzui（SDL 兼容层）上；像素断言需兼容层逐像素一致 | smoke, evidence, evidence(回放) |  |
| expansion_view | 4 | UI/渲染 | 待迁移 | pvp2cpp 翻译测试模块，跑在 pvzui（SDL 兼容层）上；像素断言需兼容层逐像素一致 | check_all, smoke, evidence, evidence(回放) | Exercise the independent UI atlas, not the authority's asset resolver. |
| feedback49_ui | 9 | UI/渲染 | 待迁移 | pvp2cpp 翻译测试模块，跑在 pvzui（SDL 兼容层）上；像素断言需兼容层逐像素一致 | check_all, smoke, evidence, evidence(回放) | Actual pointer events, native replay ticks and mobile battle input regressions. |
| hero_damage_balance | 14 | UI/渲染 | 待迁移 | pvp2cpp 翻译测试模块，跑在 pvzui（SDL 兼容层）上；像素断言需兼容层逐像素一致 | check_all, smoke, evidence | Flat hero-damage balance: named sources vs Dave heroes. |
| hud | 4 | UI/渲染 | 待迁移 | pvp2cpp 翻译测试模块，跑在 pvzui（SDL 兼容层）上；像素断言需兼容层逐像素一致 | smoke, evidence | Real battle rendering and read-only feedback/hidden-page regressions. |
| imp_client_states | 1 | UI/渲染 | 待迁移 | pvp2cpp 翻译测试模块，跑在 pvzui（SDL 兼容层）上；像素断言需兼容层逐像素一致 | smoke, evidence, evidence(回放) | A frozen armoured imp must not abort an independent client's draw frame. |
| input_latency | 10 | UI/渲染 | 待迁移 | pvp2cpp 翻译测试模块，跑在 pvzui（SDL 兼容层）上；像素断言需兼容层逐像素一致 | check_all, smoke, evidence, evidence(回放) | Client feel: input latency, the jump gates, and the per-frame stall fixes. |
| match_quality | 7 | UI/渲染 | 待迁移 | pvp2cpp 翻译测试模块，跑在 pvzui（SDL 兼容层）上；像素断言需兼容层逐像素一致 | check_all, smoke, evidence | Hero recovery, original falling suns and room/input feedback regressions. |
| native_animation | 10 | UI/渲染 | 待迁移 | pvp2cpp 翻译测试模块，跑在 pvzui（SDL 兼容层）上；像素断言需兼容层逐像素一致 | smoke, evidence, evidence(回放) | Pixel equivalence with actual marshal draw functions, not self-made poses. |
| native_battle_combat | 69 | UI/渲染 | 待迁移 | pvp2cpp 翻译测试模块，跑在 pvzui（SDL 兼容层）上；像素断言需兼容层逐像素一致 | check_all, smoke, evidence, evidence(回放) | Production Room/NativeBattle combat wiring, using real native assets/code. |
| native_draft_display | 1 | UI/渲染 | 待迁移 | pvp2cpp 翻译测试模块，跑在 pvzui（SDL 兼容层）上；像素断言需兼容层逐像素一致 | smoke, evidence | Real draft controls retain base IDs while rendering native secret forms. |
| native_flood_wrap | 2 | UI/渲染 | 待迁移 | pvp2cpp 翻译测试模块，跑在 pvzui（SDL 兼容层）上；像素断言需兼容层逐像素一致 | check_all, smoke, evidence | Flood-matrix horizontal wrap: native zombie AI must survive off-edge columns. |
| native_gravebuster | 7 | UI/渲染 | 待迁移 | pvp2cpp 翻译测试模块，跑在 pvzui（SDL 兼容层）上；像素断言需兼容层逐像素一致 | smoke, evidence | Run the real native Grave Buster creator, plant loop and draw function. |
| native_menus | 3 | UI/渲染 | 待迁移 | pvp2cpp 翻译测试模块，跑在 pvzui（SDL 兼容层）上；像素断言需兼容层逐像素一致 | smoke, evidence | Native menu screenshots and control geometry at supported small windows. |
| native_replay_world | 6 | UI/渲染 | 待迁移 | pvp2cpp 翻译测试模块，跑在 pvzui（SDL 兼容层）上；像素断言需兼容层逐像素一致 | smoke, evidence, evidence(回放) | The real WorldView replays original frames with a separate local atlas. |
| native_units | 11 | UI/渲染 | 待迁移 | pvp2cpp 翻译测试模块，跑在 pvzui（SDL 兼容层）上；像素断言需兼容层逐像素一致 | smoke, evidence, evidence(回放) | Original bytecode unit-loop matrix; fixtures bypass BP/economy explicitly. |
| native_world | 14 | UI/渲染 | 待迁移 | pvp2cpp 翻译测试模块，跑在 pvzui（SDL 兼容层）上；像素断言需兼容层逐像素一致 | check_all, smoke, evidence | Native-art ratios, real PNG rendering, camera mapping and Dave body tests. |
| replay48 | 8 | UI/渲染 | 待迁移 | pvp2cpp 翻译测试模块，跑在 pvzui（SDL 兼容层）上；像素断言需兼容层逐像素一致 | check_all, smoke, evidence, evidence(回放) | Real native recording round trips, seeking, tamper detection and touch UI. |
| review_followup | 7 | UI/渲染 | 待迁移 | pvp2cpp 翻译测试模块，跑在 pvzui（SDL 兼容层）上；像素断言需兼容层逐像素一致 | check_all, smoke, evidence | Current user balance: real price authority, supported bites and timers. |
| status_stack_audit | 13 | UI/渲染 | 待迁移 | pvp2cpp 翻译测试模块，跑在 pvzui（SDL 兼容层）上；像素断言需兼容层逐像素一致 | smoke, evidence, evidence(回放) | Regression coverage for the post-art/size, armor and status audit. |
| tail_start | 3 | UI/渲染 | 待迁移 | pvp2cpp 翻译测试模块，跑在 pvzui（SDL 兼容层）上；像素断言需兼容层逐像素一致 | check_all, smoke, evidence, evidence(回放) |  |
| touch | 51 | UI/渲染 | 待迁移 | pvp2cpp 翻译测试模块，跑在 pvzui（SDL 兼容层）上；像素断言需兼容层逐像素一致 | smoke, evidence | Touch controls: virtual buttons, multi-finger input, long-press, platform guards. |
| tutorial | 4 | UI/渲染 | 待迁移 | pvp2cpp 翻译测试模块，跑在 pvzui（SDL 兼容层）上；像素断言需兼容层逐像素一致 | check_all, smoke, evidence | PvP65 newcomer guide (rename) and the playable teaching level. |
| ui | 29 | UI/渲染 | 待迁移 | pvp2cpp 翻译测试模块，跑在 pvzui（SDL 兼容层）上；像素断言需兼容层逐像素一致 | check_all, smoke, evidence, evidence(回放) | Real SDL/pygame UI smoke and host/guest presentation contract tests. |
| audit_log | 11 | 回放/审计 | 待迁移 | pvp2cpp 翻译测试模块（unittest 外壳），直接调用 C++ 内核 | check_all, evidence(回放) | Long-match storage, complete streaming export and explicit I/O failure. |
| perf_boost | 11 | 安卓平台 | 待迁移 | 改写为 C++ APK 设备测试（模拟器/真机） | — | PvP71 Android performance diagnostics and requests, exercised on PC with fake sysfs. |
| 51_combat | 3 | 战斗内核/规则/数值 | 待迁移 | pvp2cpp 翻译测试模块（unittest 外壳），直接调用 C++ 内核 | check_all | Native projectile range and source-specific Dave damage contracts. |
| 54_ghost_range_art | 3 | 战斗内核/规则/数值 | 待迁移 | pvp2cpp 翻译测试模块（unittest 外壳），直接调用 C++ 内核 | check_all, evidence(回放) | Ghost range artwork lifecycle, dimensions and independent replay. |
| 54_native_art_revision | 4 | 战斗内核/规则/数值 | 待迁移 | pvp2cpp 翻译测试模块（unittest 外壳），直接调用 C++ 内核 | check_all, evidence(回放) | Native draw-stream checks for the requested September artwork correction. |
| 55_balance | 5 | 战斗内核/规则/数值 | 待迁移 | pvp2cpp 翻译测试模块（unittest 外壳），直接调用 C++ 内核 | check_all | PvP55 balance at the authoritative card and native combat boundaries. |
| 56_flying_plants | 19 | 战斗内核/规则/数值 | 待迁移 | pvp2cpp 翻译测试模块（unittest 外壳），直接调用 C++ 内核 | check_all | Real native 250 Hz paths for the two flying plants and their projectiles. |
| 56_zombies | 13 | 战斗内核/规则/数值 | 待迁移 | pvp2cpp 翻译测试模块（unittest 外壳），直接调用 C++ 内核 | check_all | Real 250 Hz tests for ordinary dancers, native sleds and rally miners. |
| 57_balance | 7 | 战斗内核/规则/数值 | 待迁移 | pvp2cpp 翻译测试模块（unittest 外壳），直接调用 C++ 内核 | check_all | PvP57 native projectile travel and card/atlas balance contracts. |
| 57_day_income | 7 | 战斗内核/规则/数值 | 待迁移 | pvp2cpp 翻译测试模块（unittest 外壳），直接调用 C++ 内核 | check_all, evidence(回放) | Continuous original-engine timing for the daylight zombie allowance. |
| 57_producer_protection | 13 | 战斗内核/规则/数值 | 待迁移 | pvp2cpp 翻译测试模块（unittest 外壳），直接调用 C++ 内核 | check_all | Opening protection through native damage and removal paths at 250 Hz. |
| 65_features | 11 | 战斗内核/规则/数值 | 待迁移 | pvp2cpp 翻译测试模块（unittest 外壳），直接调用 C++ 内核 | check_all | PvP65 focused checks: balance numbers, primal mine 750 ash, deathmatch |
| 66_cart_ammo_oct15 | 5 | 战斗内核/规则/数值 | 待迁移 | pvp2cpp 翻译测试模块（unittest 外壳），直接调用 C++ 内核 | check_all | Finite cart ammunition uses native throw timing and leaves other cars intact. |
| 66_coop_roster_oct15 | 4 | 战斗内核/规则/数值 | 待迁移 | pvp2cpp 翻译测试模块（unittest 外壳），直接调用 C++ 内核 | check_all, cooplobby | Seat replacement inherits saved growth and clears readiness; reconnect keeps readiness. |
| 66_duo_precursor_oct15 | 4 | 战斗内核/规则/数值 | 待迁移 | pvp2cpp 翻译测试模块（unittest 外壳），直接调用 C++ 内核 | check_all | 2v2 forward completion reserves each secret's precursor for its own seat. |
| 66_features | 11 | 战斗内核/规则/数值 | 待迁移 | pvp2cpp 翻译测试模块（unittest 外壳），直接调用 C++ 内核 | check_all | PvP66 focused checks through the original 250 Hz engine. |
| 66_feedback_pve_oct15 | 25 | 战斗内核/规则/数值 | 待迁移 | pvp2cpp 翻译测试模块（unittest 外壳），直接调用 C++ 内核 | check_all, cooplobby | Focused regression evidence for the October 15 PvE/co-op feedback. |
| 66_fortress_chase_oct16 | 2 | 战斗内核/规则/数值 | 待迁移 | pvp2cpp 翻译测试模块（unittest 外壳），直接调用 C++ 内核 | check_all | Native co-op route regressions from the 2026-10-16 fortress report. |
| 66_guest_presentation_oct15 | 5 | 战斗内核/规则/数值 | 待迁移 | pvp2cpp 翻译测试模块（unittest 外壳），直接调用 C++ 内核 | check_all | Second-seat guest interpolation preserves real native hero identities. |
| 66_native_feedback_oct16 | 5 | 战斗内核/规则/数值 | 待迁移 | pvp2cpp 翻译测试模块（unittest 外壳），直接调用 C++ 内核 | check_all | Player reports exercised through original native physics and SDL audio. |
| 66_personal_commands | 12 | 战斗内核/规则/数值 | 待迁移 | pvp2cpp 翻译测试模块（unittest 外壳），直接调用 C++ 内核 | check_all, evidence(回放) | 2v2 seat-owned orders, flags and their native combat effects. |
| 66_sun_ownership | 3 | 战斗内核/规则/数值 | 待迁移 | pvp2cpp 翻译测试模块（unittest 外壳），直接调用 C++ 内核 | check_all |  |
| 66_teams | 27 | 战斗内核/规则/数值 | 待迁移 | pvp2cpp 翻译测试模块（unittest 外壳），直接调用 C++ 内核 | check_all, evidence(回放) | PvP66 seats: 2v2 and co-op Daves inside the original 250 Hz engine. |
| 66_zombie_secrets | 47 | 战斗内核/规则/数值 | 待迁移 | pvp2cpp 翻译测试模块（unittest 外壳），直接调用 C++ 内核 | check_all | PvP66 zombie secrets (僵尸秘籍 v4) through the original 250 Hz engine. |
| 67_author_maps | 5 | 战斗内核/规则/数值 | 待迁移 | pvp2cpp 翻译测试模块（unittest 外壳），直接调用 C++ 内核 | check_all, mapedit | Author-map coverage, ordered progression and native room layouts. |
| 67_coop_dave_pursuit | 3 | 战斗内核/规则/数值 | 待迁移 | pvp2cpp 翻译测试模块（unittest 外壳），直接调用 C++ 内核 | check_all, cooplobby | Co-op waves chase Daves after they leave producers at the old spawn. |
| 67_coop_seat_saves | 5 | 战斗内核/规则/数值 | 待迁移 | pvp2cpp 翻译测试模块（unittest 外壳），直接调用 C++ 内核 | check_all, cooplobby | Seat saves survive replacement/reconnect/reopen and isolate solo profiles. |
| 67_coop_shared_routes | 4 | 战斗内核/规则/数值 | 待迁移 | pvp2cpp 翻译测试模块（unittest 外壳），直接调用 C++ 内核 | check_all, cooplobby | Co-op must reuse the proven 2v2 native route, with global ladder support. |
| 67_crowd_routing | 4 | 战斗内核/规则/数值 | 待迁移 | pvp2cpp 翻译测试模块（unittest 外壳），直接调用 C++ 内核 | check_all | Expired native split routing and bounded evidence for the recorded crowd. |
| 67_flood_cache | 2 | 战斗内核/规则/数值 | 待迁移 | pvp2cpp 翻译测试模块（unittest 外壳），直接调用 C++ 内核 | check_all | A read-batch geometry cache must preserve every actor's original path field. |
| 67_map_migration | 7 | 战斗内核/规则/数值 | 待迁移 | pvp2cpp 翻译测试模块（unittest 外壳），直接调用 C++ 内核 | check_all, mapedit | Deleted maps stay deleted when another old install is discovered later. |
| 67_pve_shared_tracking | 3 | 战斗内核/规则/数值 | 待迁移 | pvp2cpp 翻译测试模块（unittest 外壳），直接调用 C++ 内核 | check_all, cooplobby | Solo wave optimization retains native pursuit, terrain and contact damage. |
| 67_scatter_king_poison | 2 | 战斗内核/规则/数值 | 待迁移 | pvp2cpp 翻译测试模块（unittest 外壳），直接调用 C++ 内核 | check_all |  |
| 68005_minor | 10 | 战斗内核/规则/数值 | 待迁移 | pvp2cpp 翻译测试模块（unittest 外壳），直接调用 C++ 内核 | check_all, evidence(回放) | 68005: actual SDL bank selection, native rail deployment and cart lifecycle. |
| 68006 | 13 | 战斗内核/规则/数值 | 待迁移 | pvp2cpp 翻译测试模块（unittest 外壳），直接调用 C++ 内核 | check_all | 68006: native hero hit packets, per-torch conversions and Android controls. |
| 68006_black_slots | 5 | 战斗内核/规则/数值 | 待迁移 | pvp2cpp 翻译测试模块（unittest 外壳），直接调用 C++ 内核 | check_all | Black-piece effects are independent from the carrier's native body. |
| 68006_secondhand | 6 | 战斗内核/规则/数值 | 待迁移 | pvp2cpp 翻译测试模块（unittest 外壳），直接调用 C++ 内核 | check_all | Actual native type-II drops, cross-body pickups, placement and piercing. |
| 68_spawn_budget | 10 | 战斗内核/规则/数值 | 待迁移 | pvp2cpp 翻译测试模块（unittest 外壳），直接调用 C++ 内核 | check_all | Real native campaign admission, delayed summons and trusted wave ancestry. |
| 68_vine_sun_ownership | 3 | 战斗内核/规则/数值 | 待迁移 | pvp2cpp 翻译测试模块（unittest 外壳），直接调用 C++ 内核 | check_all | Real vine production keeps its producing seat through merge and collection. |
| 69002 | 28 | 战斗内核/规则/数值 | 待迁移 | pvp2cpp 翻译测试模块（unittest 外壳），直接调用 C++ 内核 | check_all | PvP69 v2 source acceptance: native rules, co-op, sockets and player UI. |
| 69002_balance | 14 | 战斗内核/规则/数值 | 待迁移 | pvp2cpp 翻译测试模块（unittest 外壳），直接调用 C++ 内核 | check_all | October 26 balance follow-up: real deployment and charm attack boundaries. |
| 70_70005 | 8 | 战斗内核/规则/数值 | 待迁移 | pvp2cpp 翻译测试模块（unittest 外壳），直接调用 C++ 内核 | check_all | 70005: basin teleport, lantern pulse burn, homing spikes on small units, art/cost and almanac notes. |
| 70_animation | 7 | 战斗内核/规则/数值 | 待迁移 | pvp2cpp 翻译测试模块（unittest 外壳），直接调用 C++ 内核 | check_all | Zombie part animation, deploy previews and PvP70 effect art on the native engine. |
| 70_coop | 11 | 战斗内核/规则/数值 | 待迁移 | pvp2cpp 翻译测试模块（unittest 外壳），直接调用 C++ 内核 | check_all, cooplobby | PvP70 cards in the solo/co-op campaign: pools, director spawns, bone graves. |
| 70_extra | 17 | 战斗内核/规则/数值 | 待迁移 | pvp2cpp 翻译测试模块（unittest 外壳），直接调用 C++ 内核 | check_all | Cooldowns, grenade/airdrop books, charm semantics and basin stack audit. |
| 70_features | 59 | 战斗内核/规则/数值 | 待迁移 | pvp2cpp 翻译测试模块（unittest 外壳），直接调用 C++ 内核 | check_all, evidence(回放) | PvP70 mechanical integration checks on the real 250 Hz native engine. |
| 71002 | 5 | 战斗内核/规则/数值 | 待迁移 | pvp2cpp 翻译测试模块（unittest 外壳），直接调用 C++ 内核 | check_all, almanac | 71002: 肆意模仿, plant-Dave marks, ghost pepper on the zombie Dave, pirate 海陆空 grouping. |
| audio56 | 6 | 战斗内核/规则/数值 | 待迁移 | pvp2cpp 翻译测试模块（unittest 外壳），直接调用 C++ 内核 | check_all, probe |  |
| balance | 17 | 战斗内核/规则/数值 | 待迁移 | pvp2cpp 翻译测试模块（unittest 外壳），直接调用 C++ 内核 | check_all | Requested PvP balance, verified through original production objects. |
| balance50 | 6 | 战斗内核/规则/数值 | 待迁移 | pvp2cpp 翻译测试模块（unittest 外壳），直接调用 C++ 内核 | check_all | PvP50 requested card values and native combat interactions. |
| balance_economy | 11 | 战斗内核/规则/数值 | 待迁移 | pvp2cpp 翻译测试模块（unittest 外壳），直接调用 C++ 内核 | check_all |  |
| banned_imp_throw | 27 | 战斗内核/规则/数值 | 待迁移 | pvp2cpp 翻译测试模块（unittest 外壳），直接调用 C++ 内核 | check_all | Bans block manual imp cards, while both original giant throws still work. |
| barrel_feedback34 | 13 | 战斗内核/规则/数值 | 待迁移 | pvp2cpp 翻译测试模块（unittest 外壳），直接调用 C++ 内核 | check_all, evidence(回放) | Real native targeting and projectile regressions for replay-1789307176. |
| black_armor_drop | 31 | 战斗内核/规则/数值 | 待迁移 | pvp2cpp 翻译测试模块（unittest 外壳），直接调用 C++ 内核 | check_all | Black armour honors opening protection and reaps plants it actually empties. |
| campaign_pool | 3 | 战斗内核/规则/数值 | 待迁移 | pvp2cpp 翻译测试模块（unittest 外壳），直接调用 C++ 内核 | check_all |  |
| draft56 | 7 | 战斗内核/规则/数值 | 待迁移 | pvp2cpp 翻译测试模块（unittest 外壳），直接调用 C++ 内核 | check_all |  |
| draft_completion49 | 9 | 战斗内核/规则/数值 | 待迁移 | pvp2cpp 翻译测试模块（unittest 外壳），直接调用 C++ 内核 | check_all | Tight secret prerequisites and production slots must leave a legal next pick. |
| expansion | 17 | 战斗内核/规则/数值 | 待迁移 | pvp2cpp 翻译测试模块（unittest 外壳），直接调用 C++ 内核 | check_all |  |
| feedback5805 | 4 | 战斗内核/规则/数值 | 待迁移 | pvp2cpp 翻译测试模块（unittest 外壳），直接调用 C++ 内核 | check_all | Projectile continuation and cold-fire regressions from player log 5805. |
| flag_performance | 2 | 战斗内核/规则/数值 | 待迁移 | pvp2cpp 翻译测试模块（unittest 外壳），直接调用 C++ 内核 | check_all | Real flag reinforcements retain native behaviour without unused N*N scans. |
| flag_reinforcement | 28 | 战斗内核/规则/数值 | 待迁移 | pvp2cpp 翻译测试模块（unittest 外壳），直接调用 C++ 内核 | check_all | The flag zombie's grave reinforcements, and what a ban may and may not do. |
| floating_graves | 3 | 战斗内核/规则/数值 | 待迁移 | pvp2cpp 翻译测试模块（unittest 外壳），直接调用 C++ 内核 | check_all |  |
| giant_headgear | 7 | 战斗内核/规则/数值 | 待迁移 | pvp2cpp 翻译测试模块（unittest 外壳），直接调用 C++ 内核 | check_all, evidence(回放) | Headgear on oversized bodies must sit on the head, in either facing. |
| giant_imp_headgear | 37 | 战斗内核/规则/数值 | 待迁移 | pvp2cpp 翻译测试模块（unittest 外壳），直接调用 C++ 内核 | check_all | The imp on a giant's back wears headgear of its own, and keeps it on a throw. |
| gladiator_giant | 39 | 战斗内核/规则/数值 | 待迁移 | pvp2cpp 翻译测试模块（unittest 外壳），直接调用 C++ 内核 | check_all | The gladiator giant: a giant wearing the black rugby helmet, whose riding imp |
| grave_targeting47 | 6 | 战斗内核/规则/数值 | 待迁移 | pvp2cpp 翻译测试模块（unittest 外壳），直接调用 C++ 内核 | check_all | Native attacks across the periodic seam, based on the user's screenshot. |
| grave_water34 | 2 | 战斗内核/规则/数值 | 待迁移 | pvp2cpp 翻译测试模块（unittest 外壳），直接调用 C++ 内核 | check_all | Graves float on the surface; clicking the submerged floor cannot bypass it. |
| hardening_copy | 7 | 战斗内核/规则/数值 | 待迁移 | pvp2cpp 翻译测试模块（unittest 外壳），直接调用 C++ 内核 | check_all | Null-HP catalog and native imitator interaction regressions. |
| hero_fume | 1 | 战斗内核/规则/数值 | 待迁移 | pvp2cpp 翻译测试模块（unittest 外壳），直接调用 C++ 内核 | check_all | Native fume attacks at supported body/head height, both directions. |
| hero_isolation | 6 | 战斗内核/规则/数值 | 待迁移 | pvp2cpp 翻译测试模块（unittest 外壳），直接调用 C++ 内核 | check_all, evidence(回放) | Hero isolation gate: one Dave's state never lands on another Dave. |
| ice_heading34 | 3 | 战斗内核/规则/数值 | 待迁移 | pvp2cpp 翻译测试模块（unittest 外壳），直接调用 C++ 内核 | check_all | Ice vehicle deployment heading must survive F without replacing native motion. |
| imitater49 | 7 | 战斗内核/规则/数值 | 待迁移 | pvp2cpp 翻译测试模块（unittest 外壳），直接调用 C++ 内核 | check_all | Native 300-frame copies retain PvP identity, balance and admission. |
| imitater_grey | 2 | 战斗内核/规则/数值 | 待迁移 | pvp2cpp 翻译测试模块（unittest 外壳），直接调用 C++ 内核 | check_all | Release gate (71002): a new plant copied by the imitater is drawn grey. |
| important_blocks | 2 | 战斗内核/规则/数值 | 待迁移 | pvp2cpp 翻译测试模块（unittest 外壳），直接调用 C++ 内核 | check_all |  |
| input_events | 2 | 战斗内核/规则/数值 | 待迁移 | pvp2cpp 翻译测试模块（unittest 外壳），直接调用 C++ 内核 | check_all | Event-backed held movement and short embedded key-state regression. |
| input_silence | 8 | 战斗内核/规则/数值 | 待迁移 | pvp2cpp 翻译测试模块（unittest 外壳），直接调用 C++ 内核 | check_all | Battle movement input must never disappear without a trace. |
| late_feedback33 | 9 | 战斗内核/规则/数值 | 待迁移 | pvp2cpp 翻译测试模块（unittest 外壳），直接调用 C++ 内核 | check_all | Follow-up player logs: template bans, terrain, knockback and third jump. |
| maps | 7 | 战斗内核/规则/数值 | 待迁移 | pvp2cpp 翻译测试模块（unittest 外壳），直接调用 C++ 内核 | check_all, mapedit |  |
| melon_remnants | 4 | 战斗内核/规则/数值 | 待迁移 | pvp2cpp 翻译测试模块（unittest 外壳），直接调用 C++ 内核 | check_all |  |
| mushroom_layer34 | 3 | 战斗内核/规则/数值 | 待迁移 | pvp2cpp 翻译测试模块（unittest 外壳），直接调用 C++ 内核 | check_all | The player's corrected underground-layer request concerns Scaredy-shroom. |
| native_bite_scaling | 2 | 战斗内核/规则/数值 | 待迁移 | pvp2cpp 翻译测试模块（unittest 外壳），直接调用 C++ 内核 | check_all | Black/captain scaling at real native plant contact, with charm unchanged. |
| native_physics | 17 | 战斗内核/规则/数值 | 待迁移 | pvp2cpp 翻译测试模块（unittest 外壳），直接调用 C++ 内核 | check_all | Native Dave physics tested against independently entered original wordcode. |
| native_placement | 7 | 战斗内核/规则/数值 | 待迁移 | pvp2cpp 翻译测试模块（unittest 外壳），直接调用 C++ 内核 | check_all | Native source parity and read-only client planting/occupancy regressions. |
| native_targets | 14 | 战斗内核/规则/数值 | 待迁移 | pvp2cpp 翻译测试模块（unittest 外壳），直接调用 C++ 内核 | check_all | Run native projectile collisions / Chomper wordcode against the hero proxy. |
| petrified_torch | 45 | 战斗内核/规则/数值 | 待迁移 | pvp2cpp 翻译测试模块（unittest 外壳），直接调用 C++ 内核 | check_all | 石化火炬: a brain-light grave that ignites peas like a torchwood. |
| plant_zombie_allegiance | 7 | 战斗内核/规则/数值 | 待迁移 | pvp2cpp 翻译测试模块（unittest 外壳），直接调用 C++ 内核 | check_all | Native-frame regressions for charmed shooters and squash/doom allegiance. |
| player_art32 | 4 | 战斗内核/规则/数值 | 待迁移 | pvp2cpp 翻译测试模块（unittest 外壳），直接调用 C++ 内核 | check_all | Native render and forward-barrel splash regressions found in visual QA. |
| player_feedback32 | 9 | 战斗内核/规则/数值 | 待迁移 | pvp2cpp 翻译测试模块（unittest 外壳），直接调用 C++ 内核 | check_all, evidence(回放) | Regressions from replay-1789295205 and actual SDL deployment/render paths. |
| player_feedback33 | 8 | 战斗内核/规则/数值 | 待迁移 | pvp2cpp 翻译测试模块（unittest 外壳），直接调用 C++ 内核 | check_all, evidence(回放) | Real native regressions from replay-1789302407 (PvP32). |
| ported_mechanics | 8 | 战斗内核/规则/数值 | 待迁移 | pvp2cpp 翻译测试模块（unittest 外壳），直接调用 C++ 内核 | check_all | Execute the shipped 1.5.0.1 mechanisms through the PvP namespace. |
| presentation | 4 | 战斗内核/规则/数值 | 待迁移 | pvp2cpp 翻译测试模块（unittest 外壳），直接调用 C++ 内核 | check_all |  |
| result_animation | 4 | 战斗内核/规则/数值 | 待迁移 | pvp2cpp 翻译测试模块（unittest 外壳），直接调用 C++ 内核 | check_all | Level-end UI uses the original curve and remains outside battle state. |
| room | 45 | 战斗内核/规则/数值 | 待迁移 | pvp2cpp 翻译测试模块（unittest 外壳），直接调用 C++ 内核 | check_all |  |
| september_content | 15 | 战斗内核/规则/数值 | 待迁移 | pvp2cpp 翻译测试模块（unittest 外壳），直接调用 C++ 内核 | check_all | Real 250 Hz coverage of the four PvP54 units and their old interactions. |
| september_rules | 9 | 战斗内核/规则/数值 | 待迁移 | pvp2cpp 翻译测试模块（unittest 外壳），直接调用 C++ 内核 | check_all | PvP54 terrain/economy rules through authority, preview and native ticks. |
| star_shovel | 7 | 战斗内核/规则/数值 | 待迁移 | pvp2cpp 翻译测试模块（unittest 外壳），直接调用 C++ 内核 | check_all | Native automatic targeting, real draw frames, shovel and independent banks. |
| starfruit_symmetry | 27 | 战斗内核/规则/数值 | 待迁移 | pvp2cpp 翻译测试模块（unittest 外壳），直接调用 C++ 内核 | check_all | Starfruit fires five stars, and its left-facing spread mirrors the right one. |
| status_visuals | 4 | 战斗内核/规则/数值 | 待迁移 | pvp2cpp 翻译测试模块（unittest 外壳），直接调用 C++ 内核 | check_all | Original damage/control clocks and recorded state sprites, not just HP. |
| summon_bans | 4 | 战斗内核/规则/数值 | 待迁移 | pvp2cpp 翻译测试模块（unittest 外壳），直接调用 C++ 内核 | check_all | Actual native summon triggers remain active when the child card is banned. |
| sweet_potato_taunt | 4 | 战斗内核/规则/数值 | 待迁移 | pvp2cpp 翻译测试模块（unittest 外壳），直接调用 C++ 内核 | check_all | Sweet-potato taunt must not leak out of the zombie that was taunted. |
| teleport | 3 | 战斗内核/规则/数值 | 待迁移 | pvp2cpp 翻译测试模块（unittest 外壳），直接调用 C++ 内核 | check_all |  |
| triple_jump | 27 | 战斗内核/规则/数值 | 待迁移 | pvp2cpp 翻译测试模块（unittest 外壳），直接调用 C++ 内核 | check_all | 「疾行」 additionally arms the PLANT hero with a third airborne jump. |
| unit_animation | 3 | 战斗内核/规则/数值 | 待迁移 | pvp2cpp 翻译测试模块（unittest 外壳），直接调用 C++ 内核 | check_all | Every new card must be animated: the release gate for unit animation (ui.animation). |
| unit_scale | 8 | 战斗内核/规则/数值 | 待迁移 | pvp2cpp 翻译测试模块（unittest 外壳），直接调用 C++ 内核 | check_all |  |
| zombie_pea | 28 | 战斗内核/规则/数值 | 待迁移 | pvp2cpp 翻译测试模块（unittest 外壳），直接调用 C++ 内核 | check_all | Zombie peas: one pea, one draw, and no damage to the torchwood. |
| 57_room_requests | 8 | 联机/中继/观战 | 待迁移 | pvp2cpp 翻译测试模块 + C++ unittest 外壳，在 C++ 进程内跑真实回环 | check_all, nettest, netpeer_duel | Guest proposals and observing-host approval over the native room and TCP. |
| 66_coop_own_deck_oct16 | 6 | 联机/中继/观战 | 待迁移 | pvp2cpp 翻译测试模块 + C++ unittest 外壳，在 C++ 进程内跑真实回环 | check_all, nettest, netpeer_duel, cooplobby | Actual co-op UI/TCP regression: unchanged guest selection must reach its own seat. |
| 66_latency_oct15 | 12 | 联机/中继/观战 | 待迁移 | pvp2cpp 翻译测试模块 + C++ unittest 外壳，在 C++ 进程内跑真实回环 | nettest, netpeer_duel, netpeer_relay, evidence(回放) | Bounded host-authoritative RTT, including real direct and relay sockets. |
| 66_room_admission_oct16 | 14 | 联机/中继/观战 | 待迁移 | pvp2cpp 翻译测试模块 + C++ unittest 外壳；本地中继服务器夹具仍用 Python server/（被测为 C++ 客户端） | check_all, nettest, netpeer_duel, netpeer_relay | Focused Oct16 room admission, restart and explicit AI-seat regressions. |
| 67_coop_pool | 6 | 联机/中继/观战 | 待迁移 | pvp2cpp 翻译测试模块 + C++ unittest 外壳；本地中继服务器夹具仍用 Python server/（被测为 C++ 客户端） | check_all, nettest, netpeer_duel, cooplobby | Real TCP co-op: independent run growth, authoritative shop/slots/rewards. |
| 67_coop_spectators | 2 | 联机/中继/观战 | 待迁移 | pvp2cpp 翻译测试模块 + C++ unittest 外壳；本地中继服务器夹具仍用 Python server/（被测为 C++ 客户端） | check_all, nettest, netpeer_duel, netpeer_duel(观战), cooplobby | Real TCP host observer, spectator admission, independent rewards and UI. |
| match_network | 3 | 联机/中继/观战 | 待迁移 | pvp2cpp 翻译测试模块 + C++ unittest 外壳；本地中继服务器夹具仍用 Python server/（被测为 C++ 客户端） | check_all, nettest, netpeer_duel | Real loopback transport driving the actual room and combat authority. |
| network | 16 | 联机/中继/观战 | 待迁移 | pvp2cpp 翻译测试模块 + C++ unittest 外壳；本地中继服务器夹具仍用 Python server/（被测为 C++ 客户端） | nettest, netpeer_duel | Real loopback transport tests; these do not prove LAN/off-site connectivity. |
| network_memory67 | 6 | 联机/中继/观战 | 待迁移 | pvp2cpp 翻译测试模块 + C++ unittest 外壳；本地中继服务器夹具仍用 Python server/（被测为 C++ 客户端） | nettest, netpeer_duel | Bounded queues and real TCP relay delivery; no device/WAN proof implied. |
| network_optimization | 10 | 联机/中继/观战 | 待迁移 | pvp2cpp 翻译测试模块 + C++ unittest 外壳，在 C++ 进程内跑真实回环 | check_all, nettest, netpeer_duel, evidence(回放) | Scheduling, real socket wakeup, detached delivery and visual continuity. |
| quit_forfeit | 3 | 联机/中继/观战 | 待迁移 | pvp2cpp 翻译测试模块 + C++ unittest 外壳，在 C++ 进程内跑真实回环 | nettest, netpeer_duel | 对局中直接关游戏 = 退出方判负（真实回环联机，主机 / 客机两个方向）。 |
| relay | 29 | 联机/中继/观战 | 待迁移 | pvp2cpp 翻译测试模块 + C++ unittest 外壳；本地中继服务器夹具仍用 Python server/（被测为 C++ 客户端） | nettest, netpeer_duel, netpeer_relay | Real TCP relay tests. Local by default; no cloud or player proof implied. |
| replay_transfer | 3 | 联机/中继/观战 | 待迁移 | pvp2cpp 翻译测试模块 + C++ unittest 外壳，在 C++ 进程内跑真实回环 | check_all, nettest, netpeer_duel, evidence(回放) | Real lobby transport, private device directories, native replay and failures. |
| room_refill | 3 | 联机/中继/观战 | 待迁移 | pvp2cpp 翻译测试模块 + C++ unittest 外壳；本地中继服务器夹具仍用 Python server/（被测为 C++ 客户端） | nettest, netpeer_duel, netpeer_relay | A real departing guest must free both the room roster and TCP reservation. |
| room_roles54 | 8 | 联机/中继/观战 | 待迁移 | pvp2cpp 翻译测试模块 + C++ unittest 外壳；本地中继服务器夹具仍用 Python server/（被测为 C++ 客户端） | check_all, nettest, netpeer_duel, netpeer_relay | Seat changes over real TCP/direct and local relay with native battle state. |
| spectator_ui49 | 5 | 联机/中继/观战 | 待迁移 | pvp2cpp 翻译测试模块 + C++ unittest 外壳；本地中继服务器夹具仍用 Python server/（被测为 C++ 客户端） | check_all, nettest, netpeer_duel, netpeer_duel(观战), evidence(回放) | Actual Application clients over loopback and relay; no WAN/device proof. |
| spectators49 | 14 | 联机/中继/观战 | 待迁移 | pvp2cpp 翻译测试模块 + C++ unittest 外壳；本地中继服务器夹具仍用 Python server/（被测为 C++ 客户端） | nettest, netpeer_duel, netpeer_relay, netpeer_duel(观战), evidence(回放) | Spectator admission, authority and independent real TCP relay channels. |
| 68_original_optimizations | 5 | 原版字节码/补丁运行时 | 不适用 | 原版模块定义/构造器的 Python 优化；C++ 版已翻译 | — | Original module definitions/constructors, exact scans/copy and native pixels. |
| legacy | 13 | 原版字节码/补丁运行时 | 不适用 | 执行发行版 pvzrouge.pyc 的原版战斗函数；C++ 版已翻译（行为由 check_all 对拍） | — | Regression tests that execute the shipped runtime's actual combat functions. |
| native_bytecode_windows | 4 | 原版字节码/补丁运行时 | 不适用 | 原版 marshal 字节码解码器；C++ 版已把原版函数离线翻译，运行期无字节码 | — | Small-window decoder parity and immutable gate-cache isolation. |
| native_catalog | 13 | 原版字节码/补丁运行时 | 不适用 | 目录解析 vs 发行 marshal/补丁函数；C++ 版目录为提取后的数据 | — | Compare catalogue resolution against actual shipped marshal/patch functions. |
| native_gate | 4 | 原版字节码/补丁运行时 | 不适用 | 原版字节码 gate 解释路径与缓存；C++ 版无解释器（由 check_all 对拍原版行为） | — | Original-loop gate parity, including original mutable state and RNG. |
| native_patch | 7 | 原版字节码/补丁运行时 | 不适用 | 在隔离适配器里执行原始 1.5.0.1 补丁源码；C++ 版是翻译产物（行为由 check_all 对拍） | — | Execute the real combat patch through its isolated PvP adapter. |
| native_patch_targets | 6 | 原版字节码/补丁运行时 | 不适用 | 同上：原始补丁回调 | — | Actual 1.5.0.1 source callbacks under mixed-allegiance native contexts. |
| reference | 3 | 原版字节码/补丁运行时 | 不适用 | 原版 live/隔离数据提取边界（反编译工具链） | — | Native catalogue data extraction and live/isolated comparison boundaries. |
| multiworker_failover | 15 | 多进程/多 worker | 不适用 | 多进程 JobSystem 后端/故障切换；C++ 版单进程无 worker | — | Job system: backends, deterministic merge, all-or-nothing failover, config. |
| multiworker_history | 13 | 多进程/多 worker | 不适用 | 快路径开关 == worker 等价历史夹具；C++ 版无 worker（快路径行为由 check_all 对拍） | — | Historical gameplay fixtures: fast path off == on == workers, and behaviour kept. |
| multiworker_parity | 4 | 多进程/多 worker | 不适用 | 单/多 worker 权威一致；C++ 版无多 worker | — | Single worker <-> multi worker authority parity on real NativeBattle fixtures. |
| multiworker_projectiles | 6 | 多进程/多 worker | 不适用 | 多 worker 下星星伤害顺序/失效；C++ 版无 worker | — | Order-sensitive star damage, invalidation, exceptions, seam and RNG. |
| multiworker_schedule_jitter | 6 | 多进程/多 worker | 不适用 | worker 调度抖动、帧复制、pack worker 进程；C++ 版无 | — | Schedule jitter, copy-once frames, MatchCopy exactness and the pack worker. |
| multiworker_seam | 5 | 多进程/多 worker | 不适用 | C 内核 vs Python 宽相交检测一致；C++ 版只有一份实现 | — | Box broad-phase kernels: exact vs brute force, seam halo, C == Python. |
| multiworker_targets | 7 | 多进程/多 worker | 不适用 | C++ 版单进程无多 worker | — | Exact-equivalence properties of the serial fast paths. |
| 56_probe_checks | 4 | 安卓平台 | 不适用 | p4a 以 PYTHONOPTIMIZE=2 运行时的诊断检查；C++ APK 无 Python | — | Android diagnostic checks must survive Python's optimized runtime. |
| 57_android_editor_probe | 2 | 安卓平台 | 不适用 | p4a 诊断探针跟随编辑器 UI；C++ APK 无该探针 | — | Android's shared diagnostic follows real editor UI without a battle. |
| 57_android_userdata | 2 | 安卓平台 | 不适用 | p4a 解压目录外存档；C++ APK 存档在 files/pvp_userdata（需另写设备测试） | — | Keep Android player data outside the replaceable app extraction folder. |
| 66_package_manual_oct15 | 4 | 安卓平台 | 不适用 | Python APK 手工交接证明（旧 APK/二进制证明）；C++ APK 流程不同 | — | Manual device handoff cannot hide stale APK or missing binary proof. |
| 67_android_entry | 7 | 安卓平台 | 不适用 | p4a 原版菜单→PvP 交接；C++ APK 直接进 PvP | — | Android original-menu handoff keeps the bundled cloud-room endpoint. |
| 67_android_fullscreen | 3 | 安卓平台 | 不适用 | jnius 沉浸式 API；C++ APK 用 SDL 全屏（需另写设备测试） | — | Android immersive APIs and SDL context/input lifecycle regression checks. |
| 67_android_upgrade | 7 | 安卓平台 | 不适用 | p4a 版升级保留私有数据/凭据排除；C++ APK 包名不同，需另写升级测试 | — | Stable Android upgrade preserves private data; developer packages exclude credentials. |
| 67_original_touch | 11 | 安卓平台 | 不适用 | 原版单人模式触屏→键鼠映射；C++ 版不含原版单人模式 | — | Original-mode SDL touches feed real native keyboard and mouse semantics. |
| android_audio | 6 | 安卓平台 | 不适用 | p4a main.py 音频入口钩子；C++ APK 由 SDLActivity 管理（需另写设备测试） | — | Android entry hooks and audio: full action signature, intact engine settings, no process side effects. |
| android_label | 3 | 安卓平台 | 不适用 | p4a 启动器标签编码；C++ APK 标签另需新检查（已列入安卓成品测试） | — | The packaged launcher label must be the intended UTF-8 text, never mojibake. |
| 67_dart_broadphase | 3 | 战斗内核/规则/数值 | 不适用 | 多 worker 宽相交跳过优化；C++ 版无 | — | Dart misses may be skipped; the native full-scan reference owns contacts. |
| 56_smoke_optimized | 2 | 打包/发行/工具链 | 不适用 | CPython -O 优化运行时下断言被剥离的问题；C++ 无此运行时 | — | Acceptance must reject broken checks even in an optimized Python runtime. |
| 57_smoke_rooms | 3 | 打包/发行/工具链 | 不适用 | 同上：打包验收在 python -O 下仍须生效 | — | Exercise package room acceptance with assertions compiled out. |
| 57_update | 9 | 打包/发行/工具链 | 不适用 | Python 版 Windows 更新器（覆盖旧安装）；C++ 版尚无更新器，若做需新写测试 | — | Execute the distributed Windows updater against isolated old installations. |
| 57_visual_probe | 4 | 打包/发行/工具链 | 不适用 | 同上：python -O 打包视觉验收 | — | Packaged visual acceptance must execute and reject faults under -O. |
| 66_coexist | 2 | 打包/发行/工具链 | 不适用 | Python 版 PvP65/66/67 并存与只读迁移；C++ 版存档独立（%APPDATA%/PVZ-PvP-Native），不迁移旧档 | — | PvP67 installs beside PvP66/PvP65, with read-only migration from both. |
| 67_final_cpp_regions | 1 | 打包/发行/工具链 | 不适用 | 旧 _pvpcore 构建产物检查（cpp_port）；C++ 版没有该构建 | — | A built core must contain FINAL installed regions, not intermediate slices. |
| integration | 17 | 打包/发行/工具链 | 不适用 | Python 嵌入加载器/启动集成（3.8 pyc 加载）；C++ 版无 | — | Integration presentation and embedded-loader regressions (Python 3.8). |
| storage_inputs | 6 | 打包/发行/工具链 | 不适用 | Python 打包输入/开发者包排除凭据（cpp_port、APK staging）；C++ 包另需新检查 | — |  |
| test_catalog | 28 | 打包/发行/工具链 | 不适用 | 按改动影响选测试的工具本身（不碰游戏世界） | — | Regression coverage for impact-based test selection (no game worlds). |
