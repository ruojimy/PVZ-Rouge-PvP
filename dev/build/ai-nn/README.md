# build/ai-nn · AI 训练用离线开局数据

2026-11-19 家院双种群夜训到北京时间 09:00。每轮植物和僵尸各产生四个变体，交叉对战后分别对 r22、冻结对手及历史策略验证，独立守擂三次后缩小变异范围与步长。08:00 锁定晨测权重。实时轮数、磁盘占用、最终擂主和晨测结果见[夜训运行与结果](../../test_results/ai-nn-home-options-20261118/league-20261119/夜训进度与晨测.md)。

2026-11-19 家院训练把实际出兵与建墓分开计分，训练和验证各覆盖 8 个起手部署不同的 z16 胜局。24 个新开局对 r22、历史 H 和 B 的 72 个配对中，保节奏候选与 z16 均为 18 胜、7 超时、47 负，出兵均为每分钟 3.61。优先翻盘的副候选在同批开局保住 17/18 个旧胜，常规时限内旧败转胜为 0/47。切换次数、延长赛、六项时序输入的对照和两侧权重见[家院实际出兵与多开局保胜训练](../../docs/ai-nn/家院实际出兵与多开局保胜训练_20261119.md)。

2026-11-18 家院单招换头实验完成 1,295 场原生运行。新开局对 r22、历史 H 和 B 的 72 个僵尸配对中，单招头比 z16 多 2 个真胜，保住 11/19 个旧胜，赢下 7/50 个旧败。共同观察窗口的实际出兵由每分钟 2.60 降到 1.95。植物真胜由 35 降到 30，两侧候选继续留作研究。18 个历史配对的三路复盘、到位建墓与等待的干预结果及权重见[家院单招换头与到位决策](../../docs/ai-nn/家院单招换头与到位决策_20261118.md)。

2026-11-18 家院首次分歧实验复现了僵尸丢掉的全部 11 个旧胜局，并对 47 个前移位置比较原打法、先走再建和同址直建。主动换招候选在 24 个陌生开局对 r22、历史 H 和 B 的 72 个配对中，把 7 个 z16 旧败变成真胜，保住 15/26 个旧胜。5 个胜转超时延长后 2 胜、3 仍超时。保胜候选与 z16 在同一批轨迹相同。植物真胜 39 → 40。正式策略继续使用 r22。详见[家院首次分歧与前移建墓训练](../../docs/ai-nn/家院首次分歧与前移建墓训练_20261118.md)。

2026-11-18 家院研究加入事件驱动的僵尸决策入口。墓碑建成或被毁、卡牌冷却完成、资源够付原生实际费用时，网络会重新选择兵种、来源墓碑、目标位置或等待。108 个训练局面比较了 423 个不同的实发命令。两批陌生家院对 r22、历史 H 和 B，僵尸较 z16 净分 +1、+4，保住 14／25 个旧胜；植物较 plant-1p 净分 +2、0，保住 32／33 个旧胜。历史零触发局 25／25、新盲测零触发局 9／9 均实际启用新入口。两侧均未达到稳定晋级条件。原生入口、权重、延长赛和同墓换兵／同兵换墓的独立对照见[家院事件触发与墓碑选兵训练](../../docs/ai-nn/家院事件触发与墓碑选兵训练_20261118.md)。

2026-11-18 家院续打实验完成 934 场原生对局。僵尸在同一局面比较四条路线，选完一次后由冻结网络继续控制，随后换边练植物。两批独立家院对 r22、历史 H 和 B，僵尸较 z16 的净分为 0、+1，植物较 plant-1p 为 +1、−3。两侧候选均未通过稳定提升条件。逐局命令显示，64 个训练点中只有 8 个能用胜负或超时区分路线。权重、延长赛、覆盖限制和磁盘审计见[家院同局面续打与动作排序训练](../../docs/ai-nn/家院同局面续打与动作排序训练_20261118.md)。

2026-11-18 家院多步训练给僵尸增加了跨卡牌的路线价值网络。相同权重连续测试两批各 18 个未见家院开局，每个开局分别对 r22、历史 H 和 B。相对上一轮，僵尸两批净分为 +3、−1，植物实际更新的候选为 +7、+10。正式版继续使用 r22。原生分支、完整复测、延长与权重入口见[家院同局面多步决策训练](../../docs/ai-nn/家院同局面多步决策训练_20261118.md)。

2026-11-18 家院研究完成两轮固定对手交替训练。僵尸共享动作评分器接管来源墓碑、建墓位置及召集旗。第二轮在 18 个新家院开局各对三个对手的测试中较历史基线净减 5 分，正式版本继续使用 r22。训练结局、单动作对照、权重和重放入口见[家院交替训练与僵尸动作泛化](../../docs/ai-nn/家院交替训练与僵尸动作泛化_20261118.md)。

2026-11-18 家院对手池实验将胜、限时未决、负分别计为 +1、0、−1，在同一开局和对手下记录每次结局变化，另查双方部署与资源闲置。此前的 `tempo_gate.py` 保留历史实验口径。三种训练对手分布、冻结权重与独立开局结果见[家院对手池与超时重评](../../docs/ai-nn/家院对手池与超时重评_20261118.md)。

2026-11-18 通宵：07:37 按验证门槛收尾。完成 23 次监督拟合、1,444 epoch，另有 48 个有界残差搜索候选；执行 2,748 场常规原生评测和 27 场等价/兼容回归。主实验、独立/摘要分支、保持 r22 攻守节奏的残差及局部微调均未产生可晋级权重。保留正式 r22 和旧研究默认权重。新增实验数据与构建约 1.173 GiB，低于 4 GiB 上限；审计时 C 盘余约 326.35 GiB。报告：[通宵训练与硬盘控制](../../docs/ai-nn/通宵训练与硬盘控制_20261118.md)；最终收据：[all-completion.json](../../test_results/ai-nn-overnight-20261118/all-completion.json)。

本轮 `policy_version=2` 的绝对头能表示经济目标 11，但首批 8 个候选均未预测对验证中的 2 条目标 11，且合法 r22 目标可以高于 11。独立格式 `pvz-deepset-bounded-residual-1` 保持 r22 的攻守、储蓄和记忆，仅允许经济/墓碑目标 ±1，不把高经济目标截到 11；对应源码与程序冻结在 `test_results/ai-nn-overnight-20261118/residual/native-source`、`native-build/Release`，旧运行时明确拒绝新格式。它是已验证的研究实现，不代表权重变强或正式 AI 已更新。日期固定的通宵脚本和语料保持冻结，不能原目录覆盖复跑。

2026-11-17 启动、11月18日完成：最新 PvP74.4 r3 上完成 3 组 95 epoch、288 场对战评测，以及 2 场中性残差等价回归。新增 8 项局面摘要、攻守切换加权及一轮学生轨迹补训。封存测试新植物 7/24 胜、9 超时（旧权重 9 胜、8 超时）；新僵尸 8/24 胜、10 超时（旧权重 8 胜、6 超时），不采用新绝对策略。报告：[状态摘要与学生轨迹补训](../../docs/ai-nn/PvP744状态摘要与学生轨迹补训_20261117.md)；收据：[completion.json](../../test_results/ai-nn-dagger-20261117/completion.json)。

当前 `run-research.ps1` 默认 `-Build pvp744`，程序在 `windows-pvp744-20261117/Release`，语料在 `test_results/ai-nn-dagger-20261117/corpus-plain`。Play／Evaluate 使用当前游戏上实测的旧权重迁移基线 `warm/old.json`；Train 使用 `fit_imitation.py` 从本轮 `training-1/selected/model.json` 权重继续训练，支持 feature-v2 及独立验证文件。默认单侧植物对 r22；`-Seat both` 才是双方网络，仍不表示自对弈强化学习。旧环境显式使用 `-Build r4` 或 `-Build legacy`。Evaluate 的默认测试开局现在已经观察过，只能用作回归。

上述 11月17日研究的模型、程序和源码快照保持冻结。`residual_seed.py` 已支持 feature-v2，可保留其编码层并初始化零修正；生成的 `residual-neutral` 在两场当时游戏中与 r22 的全部规划／结果字段一致（排除来源标签），战斗日志逐字节一致，包含真实目标 11。它只是可训练的 r22 等价起点，未奖励训练；不得把它的独立 checkpoint 交给绝对标签训练器。该历史绝对模型的经济目标上限是 10，11月18日的研究扩展及其限制见上文。

以下为历史记录，其中默认入口和版本以上述最新条目为准。

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
