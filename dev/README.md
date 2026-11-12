# PvZ 肉鸽 PvP72 · C++ 原生版

本机游玩：双击根目录 `启动PvP.cmd`，使用内层 `PVZ_rougePvP_native/pvp_userdata` 独立存档。目录安排见 [本机游玩目录说明](docs/本机游玩目录说明.md)。

当前构建：`1.6.0.72-native.20261104`。Windows x64 与 Android ARM64 包位于 `dist/`；改动、验证口径、存档继承及平台边界见 [PVP72 变更与验收](docs/PVP72_变更与验收.md)。最终摘要见 `dist/PVP72-20261104-release-manifest.json`。

当前修复版为R8（Android versionCode1104008）：已完成正式APK的虚拟机选卡、出兵、铲除、前后台、结算与存档冷启动验证，Windows与文件接口回归也已通过。详见 [R8交互与存档验收](docs/PVP72_R8_安卓交互与存档验收_20261104.md) 和 [600字内更新报告](docs/PVP72_更新报告_600字内.md)。[历史实机性能报告](docs/PVP72_安卓实机性能测试_20261104.md) 为R4数据，不代表R8手机FPS。

下文保留原生71的立项与历史实现说明；72的数值、机制和验收以本次变更记录为准。

## 类型化内核迁移（2026-11-05，尚未完成整款游戏）

最新接手入口见 [2026-11-06 类型化内核交接](交接_类型化CPP内核_20261106.md)，包含后续草稿／构建对应、组合验证、当前失败及续跑命令。

`src/sim/typed/` 是独立的 C++20 阶段库，当前实现原版伤害、六类射手攻击块、
洪水寻路、粒子生成/更新、碰撞位移、英雄目标上下文与受伤链、单位数值伤害保护、
投射物出生标记、目标伤害分发、原始伤害包装/死亡触发选择及原始僵尸构造器，
以及弹道寿命/火形态变更、篮球移动目标碰撞、瓜类/火豆溅射和共享事件队列。
已增加原始植物构造/清除、地形记录、方块破坏与 PvP 基岩保护，墓碑吞噬者落墓/植物转生，
以及内容攻击的植物/僵尸/英雄分发和碰撞。毁灭菇的 PvP 目标筛选、击杀、击退、
视觉实体与方块破坏也已迁入，辣椒/毁灭菇/墓碑的同步死亡链已组合来源上下文、
出生后归属标记、己方英雄弹飞和毁灭菇自动计时；主循环与生产召唤服务仍待接线。
状态与调用不依赖 `V`、`Args` 或旧战斗后端。
它尚未接管 `NativeBattle`，不包含完整 PvP72 规则覆盖、单位更新、英雄物理、AI、回放和联机接线，
不能作为“纯类型化 PvP72 游戏”发布，也没有整局性能提升结论。

构建与状态不变量验证：

```powershell
cmake -S src/sim/typed -B build/typed72 -G "Visual Studio 17 2022" -A x64
cmake --build build/typed72 --config Release --parallel 1
ctest --test-dir build/typed72 -C Release --output-on-failure
build/typed72/Release/typed72_probe.exe --capabilities
```

也可在主工程配置 `-DPVZ_BUILD_TYPED72_STAGES=ON`，构建 `typed72_probe` 目标。
Windows/Android 正式游戏目标排除这些尚未接线的阶段，现用游戏和存档未被替换。

离线对照入口为 `tools/typed72/verify_stages.py`（使用本项目已有的 Python 3.8 解释器），
`--exe <typed72_probe.exe> --out <新的证据目录>`；Python 只执行参照，不是该库的运行依赖。
当前 Release 对照：216 组、73,128 次阶段调用一致，原版字节码检查 RNG 和全部阶段输出；
这不是完整对局或旧全量套件。对照脚本、输入、输出、源码指纹和当前源码副本保存在
`test_results/typed72-20261105/proxy-regression/release-stages/`。
迁移对应与未接入的 PvP 覆盖层见 `docs/coverage/typed72-stage-migration.json`，
完整源逻辑初始盘点见 `test_results/typed72-20261104/inventory/`（含未解决项）。

继续迁移的英雄链由 `hero72_probe` 和 `tools/typed72/verify_heroes.py` 对拍当前 PvP72
源码与原始伤害字节码，覆盖四座位归属、缺失/None、代理扣血与状态、嵌套恢复、
爆炸预算、强健/石更、最后攻势、伤害事件、投射物归属/飞行初值与粒子 RNG。
已接入普通僵尸模板生成的完整英雄代理，保留构造 RNG、位置别名、转换写保护和来源引用寿命。
当前 1507 组、8968 个状态检查点通过 Release 与 AddressSanitizer；新增五种构造故障均被捕获。
`protection72_probe` 与 `tools/typed72/verify_protection.py` 覆盖单位保护策略，
352 组、37120 个检查点通过 Release 与 AddressSanitizer；包括 256 种相关秘籍组合和
时间边界。`targets72_probe` 覆盖同一伤害包去重缩放、护盾优先、护甲通知和目标列表恢复，
246 组、3919 个检查点通过；`patch72_probe` 覆盖伤害包装、击退与死亡触发选择，
508 组、2304 个检查点通过；实际同步死亡组合另由 `death72_probe` 验证。
`spawn72_probe` 对拍原始僵尸构造器，42 组、1302 次出生状态通过，尚未代表完整 PvP 构造链。
`entity72_probe` 覆盖实体出生、归属、删除与保留来源引用，296 组、3800 个检查点通过；
`projectiles72_probe` 覆盖弹道射程、地图接缝、篮球候选排序、植物僵尸头部碰撞、
溅射、实时列表追加/替换、异常清理和跨系统事件顺序，592 组、6532 个检查点通过。
`plants72_probe` 对拍植物出生、部分构造失败、南瓜优先、方块破坏、基岩保护、
辣椒行定位、墓碑回调替换/异常，以及内容攻击和植物/英雄碰撞，675 组、5862 个检查点通过。
`doom72_probe` 对拍现行 PvP 毁灭菇效果，覆盖同步回调、爆炸边界、阵营捕获、
列表替换/删除、视觉 RNG 和额外目标恢复，200 组、1143 个检查点通过。
`chili72_probe` 对拍辣椒地形、行提示、15 段火焰生成、敌我伤害、弹飞锁、
回调替换列表与空列表异常边界，580 组、3212 个检查点通过；6 种故障注入均被捕获。
`sourced72_probe` 对拍来源包装与新实体再标记，168 组、240 个检查点通过；
`death72_probe` 组合实际死亡效果与八个来源钩子，覆盖默认快速路径、完整上下文、
60 Hz 自动计时、实时数字下标、目标列表替换后的引用保留和己方英雄弹飞，512 组、1472 个检查点通过。
`registry72_probe` 对拍真实额外目标收集，覆盖四模式、墓碑/遗留桶 HP 筛选、
注册顺序、替换/删除/重插、嵌套目标列表和实际毁灭菇死亡组合，240 组、5888 个检查点通过。
`aim72_probe` 对拍完整 13 类植物僵尸目录、寻敌次序、实时目标引用、90° 边界、
“我是僵尸”旧修复与 PvP 来源包装，369 组、2501 个检查点通过，6 种故障均被捕获。
`wind72_probe` 对拍原生三叶草风场、PvP59 范围/下标映射、PvP56 隐藏弹幕、PvP70 骨弹/手雷和英雄逐帧吹风，
344 组、2168 个检查点通过；9 种错误被实际差异检出。单位/实体位置现在保留独立列表身份，回调替换位置不会改写已捕获的引用。
`lantern72_probe` 对拍原生回血、英雄拒绝回血、光疗特效与路灯花魅惑脉冲，336 组、2080 个检查点通过，6 种故障被捕获。
`service72_probe` 对拍萝卜伞反射/击退、PvP70 四倍攻速与吸金磁送桶/吸附，600 组、3936 个检查点通过，11 种故障被捕获。
`fume72_probe` 对拍大喷菇寻敌、受保护伤害、延迟多脉冲、雷霆、来源包装与气泡时钟，744 组、3520 个检查点通过，13 种故障被捕获。
`squash72_probe` 对拍窝瓜选敌、拦截弹道、早晚锁定、出生列表身份、来源包装、伤害回退与 PvP66 压顶溅射，1008 组、5216 个检查点通过，16 类故障被检出。
`pea72_probe` 对拍僵尸豌豆的原生生成、移动、碰撞、溅射、来源包装、英雄射击和散弹连射。21 组组件的 Release 与 AddressSanitizer 各通过 10795 个用例、180551 个检查点。记录位于 `test_results/typed72-20261105/checkpoint-pea-chain/` 与 `pea-regression-alias/`。
24 类豌豆故障都有针对性差异。最初的实体列表替换故障未被检出，修订夹具后单独重编译，16 例能识别写错列表；另 23 个故障沿用输入逐字节相同的原反例。两轮原始结果均保留。
豌豆源码对应见 `docs/coverage/typed72-pea-chain.json`。随后接入的植物僵尸射击调度在 `test_results/typed72-20261105/shooting-initial/` 完成首次 Release 对拍，604 个用例、3632 个检查点通过。完整 PvP 外层规则、整场调度与发布门禁仍在迁移。
寻敌来源见 `docs/coverage/typed72-aim-chain.json`；此前代理构造来源见
`docs/coverage/typed72-proxy-chain.json`；此前各链的来源与缺口见
`docs/coverage/typed72-target-chain.json`、`docs/coverage/typed72-projectile-chain.json`
以及 `docs/coverage/typed72-plant-chain.json`、`docs/coverage/typed72-doom-chain.json`、
`docs/coverage/typed72-chili-chain.json`、`docs/coverage/typed72-death-chain.json`、`docs/coverage/typed72-registry-chain.json`。
完整代理接入前的十四组对照在 Android x86_64 模拟器通过；当时 ARM64 与 x86_64 组件交叉编译通过，
历史证据见 `test_results/typed72-20261105/registry-android-differential/`；代理/寻敌/风场/治疗/服务链的新版本仍需重做 Android 验证。
这些是命令行组件验证，未构建类型化游戏 APK，未证明 ARM64 实机运行或正式性能。
窝瓜检查点尚有三个僵尸豌豆来源钩子、bonus 调度、生产注册/召唤与主循环待完成；当前正在接入豌豆、火焰溅射、散弹和英雄发射。
`TypedBattleState` 让单位、实体、来源引用和伤害操作共享状态，事件保存在同一份类型化队列。
世界中的注册表持有这些权威记录的引用，按实际键顺序收集额外目标；自动注册/清理的生产调用者仍待迁移。
`EntityCollection` 保留原列表身份语义，并一次压缩批量回收的句柄；这不代表已测得整局性能收益。
`WorldTerrain` 由地形记录直接提供碰撞/空格/水格查询；寻路、粒子和位移重载可读取同一份记录，
不要求每 tick 转换整张地图。当前植物对照直接验证了位移重载，洪水/粒子完整主循环组合仍待验证。
仍无完整逐 tick 驱动、生产图集/目录装载及联机/回放消费端。负向注入的原始失败均保留。
这些是迁移检查点，不是完整对局、全量机制、性能或成品验收。

## 原生71立项记录

2026-11-01 立项。目标：从零用 C++ 重写 PvP 肉鸽版，**数值与机制全部参照 PvP71（1.6.0.71.2）**，
本期只做：**合作模式（PvE）、PvP（1v1）、2v2、AI 对手**。

## 已定决策（用户 2026-11-01）

| 项 | 决定 |
| --- | --- |
| 形态 | 纯 C++ 独立 EXE：SDL2 渲染/音频、C++ 联机、C++ AI，**不带 Python** |
| 互通 | **不与 Python PvP71 互通**（只 C++↔C++ 联机/录像）。允许浮点细节差异，但用逐刻对拍 Python 版验证偏差 |
| 平台 | 先 PC（Windows x64），安卓后做；代码保持可移植（SDL2、无 Win32 依赖于核心） |
| 目录 | 本目录独立；参照源 `Downloads/PVZ-Rouge-v1.4.8/next-pvp71` **只读，不得修改** |

## 参照源（真相来源）

1. **原版战斗逻辑**：`next-pvp71/reverse_engineered/raw/pvzrouge.pyc`（Python 3.8 字节码，无源码）。
   用自写反编译器 `tools/pydec38.py` 反编译为 `extract/original/`（区段 + 85 个函数，约 5200 行）。
   校验：`tools/verify_decompile.py` 把反编译结果重新编译、比对指令多重集 —— 僵尸/植物/实体等战斗区段全部一致。
2. **1.5.0.1 补丁源码**：`next-pvp71/modkit/pvzrouge_runtime_patch_source_20260904.py`（14k 行，弹道/植物僵尸等）。
3. **PvP 层**：`next-pvp71/modkit/pvp/*.py`（约 3.2 MB 实际代码）。PvP 战斗 = 原版区段（带字节码门控注入）
   + 补丁函数 + PvP 内容模块，入口 `native_battle.NativeBattle._step_original`。
4. **AI**：`next-pvp71/AI/brain/r22.py` 及其依赖链 + `modkit/pvp/rv_*.py`。

## 目录

```
tools/            提取/反编译/对拍工具（Python 3.8 嵌入版运行，见下）
  pydec38.py        原版字节码结构化反编译器
  decompile_all.py  反编译全部区段与函数 → extract/original/
  verify_decompile.py 反编译正确性校验
extract/          从参照源提取的只读资料（反编译源码、数值 JSON、资源清单）
src/              C++ 源码
third_party/      SDL2 等
docs/             设计文档、移植对照表
```

运行工具一律用：`next-pvp71/modkit/tools/python38-embed/python.exe tools/xxx.py`
（Bash 里不要用裸 python，会卡死。）

## 回归与临时豁免（2026-11-04）

`tools/run_cpp_suite.py --out test_results/<新目录>` 默认按当前内存优先并行运行模块。
`--workers auto` 为默认值；`--workers 4` 设置最多4个，`--workers 1` 强制串行。
派发同时检查可用物理内存和系统提交额度，为在跑进程预留后续增长；默认每个 worker
预算1536 MiB、系统余量1024 MiB，可用 `--worker-memory-mib` / `--memory-reserve-mib` 调整。
检测到更大的进程会提高本轮后续预算，余量不足时暂停新任务，无法读取内存时退回单 worker。
这是调度预算，不是操作系统硬性内存上限。编译仍使用 `/MP1`、`--parallel 1`。

并行模块使用各自的可写夹具目录与玩家数据目录，公共只读输入按硬链接共享；
具体路径见每轮 `module-fixtures.json`，并行度和内存派发记录见 `scheduling.jsonl`。

用户已临时豁免 full98 剩余的 **6 FAIL / 12 ERROR，共18项**，精确清单在
`docs/coverage/temporary-native-waivers.json`。测试继续实际执行，原始逐例结果和 `counts`
保持不变；只有 ID、结果类型和详情 SHA256 全部匹配才列入 `waivers-applied.json`。
仅有这些已知差异时，汇总 `success=true`、`accepted_with_waivers=true`，命令退出0；
`execution_success` 仍反映原始结果是否全通过。新失败、签名变化、跳过、缺例、崩溃、超时、
英雄隔离异常、输入或二进制变动继续阻断。用例转为 PASS 时正常通过并标记 resolved。

需要暂时禁用豁免时追加 `--strict`；修复某项后删除其清单条目。
`tools/full_test.sh` 同样使用自动内存调度和这份默认豁免，独立本地检查顺序执行，
只有同一网络场景的配对进程同时运行。严格契约检查：
`python38-embed/python.exe tools/test_native_suite_policy.py`。

## 文档

- [V 路径到类型化 C++ 内核：实验实施方案](docs/PVP72_V路径到类型化CPP内核_实验实施方案.md)：冷路径保留 V、动态战斗重建、双后端对拍、全量测试适配及最终电脑／手机性能验收。
- [PvP72 性能优化与平衡调整指导](docs/PVP72_性能优化与平衡调整指导.md)：r2 实测基线、热点整链类型化、手机绘制／缩放排查，以及 72 规则与优化分开验证的执行路线。
- `工作汇总.md`：已完成的工作与验证证据。
- `待办.md`：阶段计划与下一步。
- `docs/`：各子系统移植说明。
