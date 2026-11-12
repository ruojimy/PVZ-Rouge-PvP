# build/ai-nn · AI 训练用离线开局数据

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
