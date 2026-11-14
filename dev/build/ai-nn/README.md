# build/ai-nn · AI 训练用离线开局数据

2026-11-14 本机部署：Windows 原生推理与 WSL 训练语料驱动已接通，首轮 DeepSets 混合模型及三组参数比较已完成。入口 `./build/ai-nn/run-research.ps1 -Mode Play -Seat plant`；完整结果、强度区间和未通过的产品门禁见 [本机部署与首轮训练](../../docs/ai-nn/本机部署与首轮训练_20261114.md)。

当前语料为 `corpus-pvp743-r2/`（gzip）及 `corpus-pvp743-r2-plain/`（逐文件校验的 Windows 副本）。下面的 `cold-corpus/` 是保留的 PvP73 原始基线；其禁卡当时仅影响选卡，没有完整进入模拟构造，不能混作新版强度数据。

本机模型为 `test_results/ai-nn-local-20261114/training-v1/model.json`，checkpoint 为同目录 `selected.pt`。网络实际接管三个战略输出，其余继续由 r22 负责。正式游戏默认 AI 继续使用 r22。

Windows 重新构建（Developer PowerShell 或完整 CMake 路径）：

```powershell
cmake -S build/ai-nn -B build/ai-nn/windows-local -G "Visual Studio 17 2022" -A x64 -DAI_NN_SDL=system -DAI_NN_GZIP=OFF
cmake --build build/ai-nn/windows-local --config Release --target headless_neural neural_dataset neural_contract fixture_retention_test
```

Windows 已有仓库 SDL；原生推理无需 Python/PyTorch，训练脚本使用本机已有的 PyTorch。新增接口包括 `--planner nn --model <model.json> --nn-seat plant|zombie|both`。`headless_neural` 和 `headless_match` 共用一个源文件，前者是独立目标，避免覆盖仍在运行的基线 EXE。生成器 `--check` 为每次构建门禁；错误模型、源码指纹或 catalog 不匹配会明确拒绝加载。

研究脚本：`prepare_training.py` 固定输入来源，`train.py` 训练/验证选型并支持 `--initial` 微调，`verify_model.py` 比较 C++ 前向及负例，`compare.py` 做配对胜负检验，`validate_baselines.py` 核对完整 216 局两遍及跨系统结果。每次使用新的输出目录保留原始失败和 checkpoint。

无头 AI 对局（见 `docs/ai-nn/基础工作规格_20261112.md`）需要不依赖 V 运行时、也不依赖图片资源的开局数据。本目录提供一份预先导出的数据集，以及在 Windows 开发机上重新生成它的工具。

## 数据集 `cold-corpus/`

216 局 1v1 对战开局：12 张地图 × 昼夜 × 3 个种子 × 3 种禁卡变体。双方卡组由大厅 AI 的选卡逻辑（`draft_advisor.recommend_ai`，僵尸方先选，植物方已知僵尸卡组）生成，并经 `catalog.validate_deck` 校验全部合法。变体 0 不禁卡；变体 1、2 先禁掉双方 AI 首选卡组里各 2 张单位卡，再追加随机禁卡，以增加卡组多样性。共 147 种不同的对阵组合，涉及 55 张卡。

| 文件 | 内容 |
| --- | --- |
| `index.json` | 每局的地图、昼夜、种子、禁卡、双方卡组，以及各文件路径和 SHA256（按未压缩字节计） |
| `decks.json` | 生成器 `deck73_corpus` 的原始输出（场景列表） |
| `cold/<id>.json.gz` | 冷数据：`cold73_export` 输出的 `cold.json` |
| `draw/<hash>.json.gz` | 绘制图集：`cold73_export` 输出的 `atlas.bin.draw.json`，按哈希去重 |
| `atlas.bin.gz`、`atlas.bin.recipes.json.gz` | 图集像素和配方。与地图、卡组无关，导出时逐局校验过哈希一致，所以只存一份 |

使用时解压成 `cold.json`、`atlas.bin`、`atlas.bin.draw.json`（与 `atlas.bin` 同目录），就和 `cold73_export` 的输出完全一样。可以直接交给 `typed72_match_gate` / `match72`（`cold.json atlas.bin scenario.json out.jsonl report.json`）运行，也可以读成 `typed72app::ColdExport` 交给 `Session::create`。

已验证：
- 第 005 局解压后用 `typed72_match_gate` 跑 900 个房间 tick（30 秒游戏时间、7500 个原生 tick），走正式组合层，没有回退，墙钟 0.68 秒（不含 AI）。
- 同一场景重新导出，`cold.json` 完全相同。

种子不能直接改：地图地形由种子生成，冷数据中的地图、随机数状态和卡组相关字段（冷却、秘籍、英雄状态）都跟着变。需要新的种子、卡组或地图时，回到 Windows 开发机重新导出。

## 重新生成（Windows，需要完整开发环境和图片资源）

```
build/pvp73-tools/build/Release/deck73_corpus.exe decks.json 3 3      # 每图种子数、禁卡变体数
python build/ai-nn/export_corpus.py decks.json build/ai-nn/cold-corpus-new 6
```

`deck73_corpus.cpp` 和 `cold73_export.cpp` 在 `build/pvp73-tools/`，由那里的 CMakeLists 构建，并链接 `build/app-typed72-v2/Release` 下的库。`index.json` 记录了导出器的 SHA256 和 `extract/data/__init__.json` 的版本；规则或卡表变化后必须重新导出。

## 无头 AI 对局环境（Linux，不链接 V）

本目录下的 `CMakeLists.txt` 独立于根目录的构建，用 g++ 或 clang 在 Linux 上构建类型化内核、组合层、会话和 r22 AI，不含 `pvzcore`。设计与验收记录见 `docs/ai-nn/`（`摸底.md`、`进度.md`、`交接.md`）。

```
cmake -S build/ai-nn -B /tmp/ai-nn-build -DCMAKE_BUILD_TYPE=Release
cmake --build /tmp/ai-nn-build -j 4
```

需要系统 zlib。有 SDL2 开发包时自动使用；没有时用 `sdl_shim/`（只重写了内核用到的 `SDL_SoftStretch`，见该目录里的说明）。`-DAI_NN_SDL=system|shim` 可以强制选择。

| 程序 / 脚本 | 用途 |
| --- | --- |
| `typed72_match_gate` | 根 CMake 里同名的门禁程序（`composition/match_probe.cpp`，源码未改），在 Linux 上构建 |
| `headless_match` | 双方都由 AI 控制的 1v1 无头对局：`--corpus <dir> --id <局号> --out <jsonl>`；其余参数见 `src/headless_match.cpp` 开头 |
| `session_trace` | 用 `cold_file` 加 `Session::create` 空跑一局，逐 tick 输出随机数摘要、公开快照和日志，用来和门禁程序对拍 |
| `card_features` | 导出卡牌特征表：`card_features day|night <out.jsonl>`；当前卡表的导出结果在 `card-features/` |
| `replay_planner` | 用 `headless_match` 记录的规划器输入离线重算 r22，逐条比对计划 |
| `eval.py` | 评测台：按局号列表多进程跑 `headless_match`，汇总分阵营胜率、置信区间、超时率和时长 |

`headless_match` 的输出是 JSON Lines：一行文件头、每次重规划一行 `plan` 记录、一行结果。同样的参数得到逐字节相同的文件；墙钟时间只打印到标准输出。
