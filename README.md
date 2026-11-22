# PVZ-Rouge · 对战模式（PvP）

中文版最新正式版 **PvP76 r2**（`1.6.0.76-typed.20261122-r2`，C++ 原生版，无需 Python）。Android versionCode **1122077**。英文版为 PvP64。

## 下载

[PvP76 r2 正式发布页](https://github.com/ruojimy/PVZ-Rouge-PvP/releases/tag/v1.6.0.76-pvp76-r2) · [历史版本](https://github.com/ruojimy/PVZ-Rouge-PvP/releases)

| 附件 | 用途 |
| --- | --- |
| [Windows 玩家包](https://github.com/ruojimy/PVZ-Rouge-PvP/releases/download/v1.6.0.76-pvp76-r2/PvZ-PvP-Native-20261122-pvp76-r2.zip) | 完整解压后运行“启动PvP.cmd” |
| [Android ARM64](https://github.com/ruojimy/PVZ-Rouge-PvP/releases/download/v1.6.0.76-pvp76-r2/PvZ-PvP-Native-1.6.0.76-typed.20261122-r2-1122077-pvp76-r2b-20261122.apk) | 同包名同签名覆盖升级，versionCode 1122077 |
| [完整开发者包](https://github.com/ruojimy/PVZ-Rouge-PvP/releases/download/v1.6.0.76-pvp76-r2/PvZ-PvP-Native-20261122-pvp76-r2-Developer-Package.zip) | 正式源码、生成器、冻结生产阶段和配套验证 |
| [SHA-256 清单](https://github.com/ruojimy/PVZ-Rouge-PvP/releases/download/v1.6.0.76-pvp76-r2/zh-SHA256SUMS.txt) | 核对三个正式包 |

## PvP76 r2 更新

- 调整：克苏鲁之仆冷却 24 秒，会被三叶草与三叶草僵尸的风吹动；投篮车僵尸、小鬼炮移速减半；大运！小子覆盖两车；携带坤坤后投篮车不服从跟随与召集旗帜；阳光收集秘籍开局 80 秒内自动收集会让植物戴夫感冒 2 秒。
- 合作模式：每通关一天，敌方加入一个僵尸秘籍（前体需进入当天卡池）。
- 修复：掷弹兵改为炸 6 格内阳光消耗最高的植物；钩索被萝卜伞挡下不再造成任何伤害。[完整更新说明](dev/更新说明-PvP76.md)。

联机双方请使用 PvP76 r2。

本版重跑了 2366 项全量回归，2351 项通过，3 项失败，12 项错误。15 项非通过结果与 PvP76 r1 基线相同并沿用既有豁免，缺失和未豁免均为 0。三道生产门禁通过。Windows 已通过出包冒烟（含 r2 专项审计 8 组）并核对实际启动 EXE。Android 已验证包名、版本号和签名连续性，实机验收待完成。[验证摘要](docs/pvp76-r2-validation.json)。

## 神经网络 AI 研究

独立的[神经网络AI板块](ai-nn/README.md)：提供Windows即用研究包、模型/checkpoint、216组语料、训练工具、完整源码及验证报告。[研究下载](https://github.com/ruojimy/PVZ-Rouge-PvP/releases/tag/ai-nn-20261114-r1)。该研究包为 11-14 冻结版本；正式游戏默认 AI 及行为以当前发行说明为准。

## 历史待办

[旧待办清单](待办清单.md) 是 74.3 r2 时的快照，未逐项更新；不要把其条目状态视为当前验收结果。

## 源码与升级

`dev/` 对应 PvP76 r2 开发者包，研究数据等 Git 忽略项随相应下载发布。发行清单和逐文件 SHA-256 见 [MANIFEST-PvP76.json](dev/MANIFEST-PvP76.json) 和 [SHA256SUMS.txt](dev/SHA256SUMS.txt)。

生产内核位于 `dev/build/typed72-integrated-v44/source/src/sim/typed/`，组合层源位于 `dev/build/typed72-match-v1/`。Windows 默认使用 `%APPDATA%/PVZ-PvP-Native/pvp_userdata`。

## 英文版及其依赖

英文 PvP64 和其 Overlay 所需的 [PvP64 中文基础包](https://github.com/ruojimy/PVZ-Rouge-PvP/releases/tag/v1.6.0.0-pvp64)继续保留。

### English edition — [PvP64 EN](../../releases/tag/v1.6.0.0-pvp64-en)

| Asset | Use |
| --- | --- |
| `PVZ-Rouge-v1.6.0.0-PvP64-EN-Release-Package.zip` | Complete player package; run `launch_pvp_en.cmd` |
| `PVZ-Rouge-v1.6.0.0-PvP64-EN-Developer-Package.zip` | Complete English developer package |
| `PVZ-Rouge-v1.6.0.0-PvP64-EN-Android.apk` | Updates the English app in place; installs alongside Chinese |
| `PVZ-Rouge-v1.6.0.0-PvP64-EN-Overlay.zip` | Apply over this release's Chinese developer package to reconstruct the English developer package; requires the exact base ZIP |

English PvP64:

- 原版模式由游戏原引擎处理，对战使用独立规则。PC 存档位于 `%APPDATA%\PVZ-Rouge-PvP\pvp_userdata`。
- Windows 覆盖旧英文目录请运行 `更新旧英文版.cmd`；玩家数据、地图、回放与已有中继配置保留，覆盖前备份。
- Android 英文包名 `org.pvzrouge.pvzpvp.en`，可与中文版并存。

## 许可与归属

- 本项目自己编写的部分（C++ 源码、PvP 规则源码、反编译器、翻译与测试／构建工具、文档）以 [MIT 许可](LICENSE) 发布，转载或改作请保留版权声明；适用范围见 [NOTICE](NOTICE)。
- 原版肉鸽游戏的代码（含 `extract/original`、`extract/live` 中的反编译结果）与数据归原作者所有，不在 MIT 许可范围内；公开它们仅供研究与改版参考。原作者如有异议请提 Issue，会及时处理。
- 植物大战僵尸的名称、图片、音乐与音效归 PopCap Games / Electronic Arts。本项目为非商业粉丝作品。
- Terraria 相关名称、原版图像与音效属于其权利人；来源记录见 `dev/extract/assets/terraria/`，不属于本项目 MIT 许可范围。
- `third_party/` 中的 SDL2 系列、nlohmann/json、zlib 沿用各自的许可。

每个 Release 提供附件 SHA256，ZIP 内另有逐文件校验清单。分发包不含个人存档和签名私钥。
