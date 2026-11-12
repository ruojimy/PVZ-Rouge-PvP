# PvZ 肉鸽 PvP73 · C++ 原生版 开发者包

版本 `1.6.0.73-typed.20261112`。本包是 PvP73 发布版（PC `PvZ-PvP-Native-20261112-pvp73-r2`、安卓 versionCode 1112073）对应的完整源码与工具，目录结构与开发目录一致。玩家请下载发布包，不需要本包。

本次改动见 `更新说明-PvP73.md`；实现细节、根因与验证证据见 `PvP73_进度.md`；`README.md` 为项目历史说明（写于 PvP72 期间，保留作背景）。

## 目录

| 路径 | 内容 |
| --- | --- |
| `src/` | 全部 C++ 源码：`core` V 动态值运行时；`sim/pvp/gen` PvP 规则层（由 Python 源翻译生成）；`sim/typed72_app` 类型化对局会话、AI 控制器与生成的组合层 `composition`；`ui`、`pg`（SDL 版 pygame 接口）、`app`（入口、升级检查、安卓性能申请）；`cpptests` 旧测试套件翻译成的 C++ 测试 |
| `build/typed72-integrated-v44/source/src/sim/typed` | 类型化 C++ 内核（对局每帧逻辑：单位、伤害、寻路、内容、英雄等），不依赖 V |
| `build/typed72-match-v1` | 组合驱动源码（`match_probe.cpp`、`frame_layer.inc`、`snapshot_layer.inc`、`probes/`）、逐 tick 对拍工具与场景 `scenarios/` |
| `build/pvp73-tools` | PvP73 的参照记录器、批量对拍、打包与安卓构建脚本 |
| `tools/pvp72_sources` | PvP 规则的 Python 源码（PvP73 改动都从这里开始） |
| `extract/original` | 自写反编译器 `tools/pydec38.py` 反编译的原版游戏 Python（区段 + 函数） |
| `extract/live` | PvP 对局实际运行区段（含 `_pvp_*` 门控注入）的反编译结果 |
| `extract/data`、`extract/schema`、`extract/assets`、`extract/golden` | 数值数据（含 `data/__init__.json` 版本号）、结构定义、资源清单与参照样本 |
| `tools/` | 反编译 `pydec38.py`、翻译 `py2cpp.py`/`pvp2cpp.py`、再生成 `pvp72_regenerate.py`、类型化工具 `typed72/`、测试运行 `run_cpp_suite.py`、纯血门禁 `pvp73_pure_typed_gate.py` |
| `android/` | 安卓 NDK 构建与 APK 打包脚本（签名私钥不在包内，需自备） |
| `third_party/` | SDL2 / SDL2_image / SDL2_mixer / SDL2_ttf 的 VC 开发库、nlohmann/json、zlib |
| `docs/`、`developer-tools/` | 设计、验收、测试覆盖对照与开发者工具说明 |

图片、音乐、音效不在本包内：从 PC 发布包复制 `图片`、`音乐`、`音效` 三个文件夹到构建输出目录（EXE 同级）即可运行。

## 构建（Windows x64）

需要 Visual Studio 2022（C++ 桌面开发，含 CMake）与 Python 3.8+（仅构建期用于组合层校验和代码生成，游戏运行不需要 Python）。

```powershell
cmake -S . -B build/app -G "Visual Studio 17 2022" -A x64 -DPython3_EXECUTABLE=<python.exe>
cmake --build build/app --config Release --target PvZPvPNative
```

常用目标：`PvZPvPNative`（游戏）、`cpp_tests`（翻译后的测试套件）、`typed72_match_gate`（类型化逐 tick 对拍门禁）、`app_run`（脚本驱动真实界面）。

## 改动一条规则的流程

1. 改 `tools/pvp72_sources/*.py`。
2. `python tools/pvp72_regenerate.py`：翻译并三方合并进 `src/sim/pvp/gen`、`src/ui/gen`，冲突文件列在输出里，按 `PvP73_进度.md` 的规则解决。
3. 每帧逻辑同时改类型化内核（`build/typed72-integrated-v44/source/src/sim/typed`）或组合驱动（`build/typed72-match-v1`），然后 `python tools/typed72/make_app_composition.py` 重新生成 `src/sim/typed72_app/composition`。
4. 卡牌数值变化时，用 `v_cold_catalog_probe --export` 导出、`tools/typed72/drafts/cold_catalog_export.py --v-export` 生成类型化卡表，复制到内核源码目录。
5. 构建，并用 `build/pvp73-tools/compare73.py` / `batch73.py` 与 V 参照逐 tick、逐绘制帧对拍。

## 测试

- `tools/run_cpp_suite.py --exe <cpp_tests.exe> --out <新目录>`：在隔离进程里运行全部翻译测试，结束时附带纯血门禁（对战 AI、合作 AI、2v2 三局，要求每帧逻辑中 V 分配与调用为 0）。测试夹具读取原版 Python 工程中的只读资料（脚本顶部 `REFERENCE` 路径），本包不含原版游戏文件。
- PvP73 发布时：2304 通过；相对 PvP72 基线新增的 20 项全部是本版有意的规则变化，判定已直接在 `src/cpptests/gen` 中更新（带 `PvP73` 注释，清单见 `PvP73_进度.md`）。重新运行 `tools/gen_cpp_tests.py` 生成这些模块时需要重新套用。

## AI 训练基础工作（进行中）

- 规格：`docs/ai-nn/基础工作规格_20261112.md`，说明规划器网络的输入输出、卡牌特征表、状态复制和无头批量对局的设计；开头附有勘误。
- 离线开局数据集：`build/ai-nn/cold-corpus/`，216 局 1v1，双方卡组由大厅 AI 的选卡逻辑生成并校验合法；格式、验证和重新生成方法见 `build/ai-nn/README.md`。
- 卡组生成器 `build/pvp73-tools/deck73_corpus.cpp`、导出脚本 `build/ai-nn/export_corpus.py`：都要在 Windows 开发机上运行，需要完整构建和图片资源。

## 校验

`SHA256SUMS.txt` 列出包内每个文件的 SHA256（仅发布的 ZIP 包内有；GitHub 仓库 `dev/` 目录以 git 记录为准）。
