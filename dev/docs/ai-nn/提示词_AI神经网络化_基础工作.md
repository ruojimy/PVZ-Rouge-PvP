# 提示词：PvZ PvP AI 神经网络化 · 基础工作（云端第一阶段）

> 用法：把本文件全文交给云端会话。全程用中文汇报。

## 环境

- 你只能读取 GitHub 仓库 **https://github.com/ruojimy/PVZ-Rouge-PvP**。项目源码都在仓库的 `dev/` 目录，下文路径都相对于 `dev/`。
- 你**没有**以下东西：游戏的图片、音乐、音效；Windows 和 MSVC；能运行的游戏本体；V 运行时导出工具的运行环境。所以你不能开真实游戏，也不能自己导出新的开局数据。
- 你**有**：全部 C++ 源码、类型化内核，以及 216 局预先导出的 1v1 开局数据（`build/ai-nn/cold-corpus/`）。这些开局数据已经包含跑一局类型化对局需要的全部输入，图集像素也在里面。
- 在新分支 `ai-nn/foundation` 上工作，**不要改 `main`**，也不要改仓库根目录的 README、LICENSE、NOTICE。能推送就推送分支并开一个草稿 PR；不能推送就在最终汇报里附上完整补丁。

## 先读

1. `docs/ai-nn/基础工作规格_20261112.md`：整体设计。开头的勘误优先于正文。
2. `build/ai-nn/README.md`：开局数据集的格式、验证方式和限制。
3. `开发者包说明-PvP73.md`：目录结构。

## 任务

为 1v1 对战 AI 的"规划器神经网络化"打地基：做一个**纯 C++、不链接 V 运行时、能在 Linux 上批量并行跑的 AI 对 AI 无头对局环境**，加上卡牌特征表、规划记录器、可注入的规划器接口和评测台。本阶段**不训练网络**，也不改变游戏行为。2v2 和合作闯关不在范围内。

## 已核实的事实（开发机源码，2026-11-12）

1. **开局数据**：解压 `cold/<id>.json.gz` → `cold.json`，`atlas.bin.gz` → `atlas.bin`，`draw/<hash>.json.gz` → `atlas.bin.draw.json`，`atlas.bin.recipes.json.gz` → `atlas.bin.recipes.json`（后三个与 `atlas.bin` 放在同一目录）。解压结果与开发机导出的完全相同，SHA256 见 `index.json`。
   - 在开发机上，第 005 局用 `typed72_match_gate` 跑了 900 个房间 tick，走正式组合层，没有回退，墙钟 0.68 秒（不含 AI）。
   - 种子会改变地形，**不能只改种子或卡组**来造新的开局。只能用数据集里现成的 216 局。
2. **读文件开局的现成实现**：`build/typed72-match-v1/match_probe.cpp`。它在根 `CMakeLists.txt` 里对应 `typed72_match_gate` 目标，注释写明"不链接 pvzcore/V"，用法是 `cold.json atlas.bin scenario.json out.jsonl report.json`，其中 `load_atlas`、`install_frames`、`setup` 演示了怎样从文件建立对局。
3. **会话接口** `src/sim/typed72_app/session.h`：`ai_observe`、`ai_plan`、`ai_control`、`command`、`step`、`finished`、`result_json`、`rng_state` 都已经有了，接口不依赖 V。
   - `ai_plan` 把 `AiPlannerR22`（`ai_planner_r22.cpp`）写死在会话里。
   - 头文件注释里"still-V controller"已经过时：控制器 `src/sim/typed72_app/ai/` 是类型化的。
   - 根 CMake 的 `pvztyped72app` 库同时包含 `cold_export.cpp` 和 `typed_battle.cpp`，这两个文件接的是 V 那一侧，并且链接了 `pvzcore`。无头构建要把它们排除掉，只留 `session.cpp`、`ai_planner_r22.cpp`、`ai/*.cpp`、生成的组合层 `src/sim/typed72_app/composition`，以及内核 `build/typed72-integrated-v44/source/src/sim/typed/*.cpp`。
   - 哪些头文件或符号还会把 V 拖进来，要你自己确认。
4. **Linux 可编译性**：安卓版用 NDK clang 在 Linux 上编译全部代码，可参考 `android/` 和 `build/pvp73-tools/android_native_r73.sh` 里的源文件清单和编译选项。
   - 内核里只有 `native_art.cpp` 需要 `SDL.h`。可以装 `libsdl2-dev`，也可以确认无头路径用不到它后排除掉。
   - 根 `CMakeLists.txt` 面向 MSVC，用的是 `third_party/` 里的 Windows SDL 库。不要去改它，为无头环境单独写一份 CMake。
5. **AI 调度**（`AISeat`）的权威实现在 `tools/pvp72_sources/lobby_room.py`，在游戏里跑在 V 上：第 100 行起是 `class AISeat`，第 350–410 行附近是类型化 AI 的控制、规划和重置逻辑。
   - 游戏的控制频率是桌面 15 Hz、安卓 10 Hz；r22 每 `plan_every`（1.5 秒）重规划一次；`recovering` 来自控制器；重建 agent 时要重置记忆。
   - 你写的 C++ 调度循环必须逐条对照这段源码实现，不能凭规格里的伪代码猜。
6. 房间 tick 30/s，原生 tick 250 Hz。900 个房间 tick 等于 30 秒游戏时间、7500 个原生 tick。

## 硬约束

- **游戏行为不变。** 允许改 `session.h/.cpp`、`ai_planner_r22.*`，但只能做行为不变的重构（例如把规划器改成可注入，默认仍是 r22）。每改一处都要在 PR 说明里写清楚为什么不改变行为。最终会在 Windows 开发机上做逐 tick 对拍复核（见「交回开发机复核」）。
- 无头程序不得链接 `pvzcore`，不得包含 `core/obj.h` 等 V 头文件。验收时用 `nm` 或链接映射证明这一点。
- 不改 `tools/pvp72_sources/`（规则源码）和 `src/sim/pvp/gen`、`src/ui/gen`（生成代码）。
- 新代码放进 `build/ai-nn/`（驱动、CMake、记录器、评测脚本）和 `src/sim/typed72_app/`（规划器接口、开局加载器）。不要提交编译产物和大于 5 MB 的结果文件；证据摘要写进 `build/ai-nn/results/*.md`。

## 步骤与验收

按顺序做，每步达到验收标准后再往下走。

### 0. 摸底
- 写出 `AISeat` 的精确节拍：控制间隔、重规划间隔、`recovering` 来源、`reset_ai_*` 的调用时机、`set_ai_subsidy_seats`，以及 1v1 对战里哪些席位由 AI 控制。
- 清点类型化内核、typed72_app 和 ai/ 中的**跨对局全局可变状态**（函数内 `static`、命名空间级变量、单例），判断同一进程能不能连续跑多局。
- 用 grep 核对规格里的数字：计划键 62 / 27 / 37、卡表 232 条、行为 47 种。
- 核对联机：AI 席位是否只在房主那边计算，结果以房间指令下发并录入回放，客户端不重算。如果是，网络推理的浮点差异就不会破坏锁步同步。
- 产出 `docs/ai-nn/摸底.md`。

### 1. Linux 无头构建与开局加载器
- `build/ai-nn/CMakeLists.txt`：在 Linux 上用 g++ 或 clang 构建内核、组合层、会话和 AI，不含 V。
- `src/sim/typed72_app/cold_file.{h,cpp}`：从解压后的文件构造 `ColdExport`，或用系统 zlib 直接读 `.gz`（`third_party/zlib-1.3.2-compress` 只有压缩部分，读不了 `.gz`）。可以参照 `match_probe.cpp`，但不要 include 它。
- 先在 Linux 上把 `typed72_match_gate`（`match_probe.cpp`）编译出来，用它跑一局数据集里的开局。这样能证明 Linux 构建和开局数据是通的，后面也拿它当参照。
- **验收**：
  - a. 第 005 局在 Linux 上跑 900 个房间 tick，`report.json` 中 `fallback_count` 为 0、`unsupported_operations` 为空。
  - b. 同一局用你的加载器加 `Session::create` 跑同样的 tick 数，每 tick 的 `rng_state` 和 `log_entry` 都与 `typed72_match_gate` 相同。
  - c. 同一局跑两次，输出逐字节相同。
  - d. 任何平台差异都要定位清楚，不许放宽比较标准来让它通过。

### 2. 无头对局驱动
- `build/ai-nn/headless_match`：参数是 `--corpus <dir> --id <局号> --out <jsonl> [--planner r22] [--control-hz 15] [--limit-seconds N]`。双方都由 AI 控制，节拍严格按第 0 步的结论。
- **验收**：
  - a. 同参数运行两次，日志摘要（SHA256）相同。
  - b. 单核吞吐：模拟秒 ÷ 墙钟秒，以及每秒 tick 数，纯模拟和含 AI 两种情况分开报。
  - c. 同一进程连续跑 10 局，与 10 个独立进程逐局相同；不同的话，就规定一局一进程，并写明原因。
  - d. 216 局全部跑完：没有崩溃，记录胜负、超时、时长的分布。如果超时局占比很高，要分析原因。

### 3. 卡牌特征表
- 按规格「卡牌特征表」一节，从 `ColdCatalog` 导出**解析后的卡**（`player_card` / `unit_card`，含昼夜和秘籍改写）。文件头写 `catalog_hash` 和 `rules_hash`。
- **验收**：行数与卡表一致；昼、夜各一份，产出周期等字段的差异符合 PvP73 规则；重复导出字节相同。

### 4. 规划器接口与记录器
- `IPlanner`：输入是 `AiPlannerInput` 加记忆，输出是 `AiPlanR22`。`AiPlannerR22` 实现这个接口，`Session` 可以注入规划器，默认仍是 r22。
- 记录器：每次重规划写一行 JSON Lines，包括 tick、席位、输入的原始事实、输出的计划字典。文件头和文件尾按规格「记录格式」一节。
- **验收**：
  - a. 接口改造前后，第 2 步的 216 局逐局日志摘要不变。
  - b. 写 `replay_planner`，用记录里的输入离线重算 r22，计划逐条相同。

### 5. 评测台
- `build/ai-nn/eval.py`：读固定的局号列表，按 CPU 核数开多个进程跑，汇总植物方和僵尸方各自的胜率、95% 置信区间、超时率和平均时长。
- **验收**：r22 自对弈跑完全部 216 局，跑两遍结果完全相同；报告写明墙钟耗时。

### 只写建议，不做
- 状态复制：在第 2 步测出吞吐后，评估"重放式"（同一开局、同一种子，重放指令到第 N tick）的代价。
- **先调参，再上网络**：用评测台对 r22 的 27 个计划常量做黑盒调参（CMA-ES 或随机搜索），以胜率为目标。估算一轮调参需要多少局、多少时间。
- 216 局开局数据够不够用；如果要扩充，写清楚需要哪些地图、卡组和种子分布。扩充由开发机导出。

## 交回开发机复核

以下几项云端做不了，在 PR 说明里列成清单，由开发机完成：
- 改造后的游戏：`app_run airoom` 与 3 个对拍场景逐 tick 不变，纯血门禁 `tools/pvp73_pure_typed_gate.py` 仍然全过。
- 无头驱动与游戏内 r22 对局在同一开局上的一致性。需要的话，在驱动里留一个能接收"外部指令序列"的模式，方便开发机做对拍。

## 什么时候停下来问

- 第 1b 步对不上，而且差异来自内核逻辑，不是加载方式。
- 需要改游戏可见行为或规则数值，或者需要改生成代码。
- 内核里有跨对局全局状态，修它要动 typed 内核。
- 无头构建避不开 V。

## 汇报

- 每完成一步，在 `docs/ai-nn/进度.md` 追加：做了什么、怎么复跑、验收结果（带原始数字）、遗留问题。
- 最后写 `docs/ai-nn/交接.md`：完成到第几步、吞吐实测值、交回开发机复核的清单、调参和网络化的下一步建议。
- 没跑过的不要写成"已验证"；跳过的步骤要明说。
