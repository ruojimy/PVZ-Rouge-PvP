# build/ai-nn · AI 训练用离线开局数据

2026-11-16 r4 节奏复核：新增 43 局诊断，r4 的 24 局基线与 r3 逐字节一致，19,824 条特征/标签一致。已定位新小网络的长时间不部署、资源积压和进攻模式偏离；两侧均未通过新增完赛/节奏门槛。详见 [r4 对局节奏与行为克隆复核](../../docs/ai-nn/r4对局节奏与蒸馏复核_20261116.md)。`run-research.ps1` 现默认 r4、保留旧权重、仅植物网络对 r22；双方网络需显式 `-Seat both`，历史构建用 `-Build legacy`。Evaluate 默认是已观察的回归集，不是新的封存测试。

`teacher_trace` 可对学生实际状态取得 r22 的反事实标签，保留原执行计划；本轮生成 5,516 条训练用途样本，未补训新权重。`tempo_gate.py` 检查配对开局、相同时限/控制频率、胜局不退化、不新增超时和封顶平均时长增长默认不超过 5%；通过初筛仍须查看成功部署与资源等有效行动指标。先完成能打的行为克隆，再进入奖励训练与自对弈；历史 `study_run.py` 不含这个新门槛，不能直接把它的选型当作晋级依据。

2026-11-16：用户恢复加强训练，完成 10 组、615 epoch 和 411 局检查。小网络留出植物 9/24 胜（r22 13/24、旧模型 12/24），僵尸 4/24（r22 4/24、旧模型 3/24），不替换默认权重；宽网络验证对战未优于小网络。新工具、模型、数据隔离、逻辑加速与渲染边界见 [本轮架构评估](../../docs/ai-nn/加强训练与架构评估_20261116.md)。实验使用独立冻结目录 `windows-20261116/Release`；工作区随后新增 NativeTick 阶段计时，字节指纹不同，不要在冻结目录重建或手动重标模型。

`residual_seed.py --backbone <已验证绝对模型> --features <同指纹数据> --out <新目录>` 生成可训练的中性残差起点：保留编码层，输出头归零并偏置中性类别，初始行为等于 r22。它与 `identity_model.py` 的全零等价夹具不同；后者隐藏层梯度为零。新起点的合成梯度探针会恢复中性权重，不是奖励训练；专用 `residual_state_dict` checkpoint 不能交给绝对标签训练器。

2026-11-15：已合入 T22 修正量模型和重新标注增强工具，并完成 MSVC、PyTorch 复测。零修正保持 r22；增强模型暂未胜出。入口 `./build/ai-nn/run-research.ps1 -Mode Play -Seat plant`；见 [本轮验证](../../docs/ai-nn/T22与缺键本地验证_20261115.md)，首轮历史见 [本机部署与首轮训练](../../docs/ai-nn/本机部署与首轮训练_20261114.md)。

当前语料为 `corpus-pvp743-r2/`（gzip）及 `corpus-pvp743-r2-plain/`（逐文件校验的 Windows 副本）。下面的 `cold-corpus/` 是保留的 PvP73 原始基线；其禁卡当时仅影响选卡，没有完整进入模拟构造，不能混作新版强度数据。

本机研究入口当前默认模型为 `test_results/ai-nn-r4-tempo-20261116/models/old.json`，权重仍来自首轮，经过本轮 r4 兼容核验后另存。历史模型 `test_results/ai-nn-followup-20261115/training-v1-revalidated/model.json` 保留用于旧构建；当时乌鸦眩晕绘制修复后曾复核 22,032 条特征/标签，再登记原权重的兼容指纹。源码指纹守卫保留，不允许未经核验直接改标。网络实际接管三个战略输出，其余继续由 r22 负责，正式游戏默认 AI 继续使用 r22。

`identity_model.py --like <当前数据集> --out <新模型>` 生成零修正夹具。`prepare_training.py --augment 1 --seed 743` 生成增强数据；`train.py` 只将增强行用于训练。r4 研究入口 `-Mode Train` 默认使用 `test_results/ai-nn-r4-tempo-20261116/features-r4.jsonl`（19,824 条开发样本），历史 `-Build legacy` 使用 `test_results/ai-nn-followup-20261115/dataset.jsonl`，也可通过 `-Data` 指定其他数据。它仍是监督模仿训练。`tune.py` 比较固定修正量，要求选型与留出开局互斥，并拒绝复用已有输出目录。不要把绝对值分类器的权重直接标成 residual 模型。

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
