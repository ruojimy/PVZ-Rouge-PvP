# PvZ PvP 原生源码 · 神经网络 AI 研究快照

当前研究修订：ai-nn-20261114-r1，基于已交付 PvP74.3 r2。完整保留生产源码、拥有源、生成器、hooks、数据及依赖。正式玩家包仍为 r2；本快照新增的七项探针补强/禁卡冷数据链已进入源码与测试构建，尚未作为新的正式玩家包发布。

进入 [神经网络 AI 工具](build/ai-nn/README.md)，或阅读[本机部署与首轮训练报告](docs/ai-nn/本机部署与首轮训练_20261114.md)、[T01–T23待办](待办清单.md)。本快照没有附带项目自己的编译 EXE；Windows 即用推理请下载同仓库的 AI 研究运行包。

Windows 研究构建：
```powershell
cmake -S build/ai-nn -B build/ai-nn/windows-local -G "Visual Studio 17 2022" -A x64 -DAI_NN_SDL=system -DAI_NN_GZIP=OFF
cmake --build build/ai-nn/windows-local --config Release --target headless_neural neural_dataset neural_contract fixture_retention_test --parallel 2
python -X utf8 build/ai-nn/bootstrap.py --training
./build/ai-nn/run-research.ps1 -Mode Play -Seat plant
```

Linux 无头构建使用完整 zlib，SDL2 不在时使用已披露的 shim。实际生产内核是 build/typed72-integrated-v44/source/src/sim/typed/，组合拥有源为 build/typed72-match-v1/。不得只修改早期 src/sim/typed/。AGENTS.md 记录启动器、备份、存档和代码生成约定。

原始 r2 源码仍由正式 r2 标签/开发者包固定；此前说明保存在 docs/history。清单及逐文件 SHA256 说明本次源快照的精确内容，不代表产品全量测试通过。
