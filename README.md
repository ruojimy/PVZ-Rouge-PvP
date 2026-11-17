# PVZ-Rouge · 对战模式（PvP）

中文版最新正式版为 **PvP74.4 r3**（`1.6.0.74.4-typed.20261117-r3`，C++ 原生版，无需 Python），Android versionCode **1117003**。英文版仍为 PvP64，不可混用联机。

## 下载

[74.4 r3 正式发布页](https://github.com/ruojimy/PVZ-Rouge-PvP/releases/tag/v1.6.0.74.4-pvp744-r3) · [历史版本](https://github.com/ruojimy/PVZ-Rouge-PvP/releases)

| 附件 | 用途 |
| --- | --- |
| [Windows 玩家包](https://github.com/ruojimy/PVZ-Rouge-PvP/releases/download/v1.6.0.74.4-pvp744-r3/PvZ-PvP-Native-20261117-pvp744-r3.zip) | 解压后运行“启动PvP.cmd”；默认使用独立用户数据目录 |
| [Android ARM64](https://github.com/ruojimy/PVZ-Rouge-PvP/releases/download/v1.6.0.74.4-pvp744-r3/PvZ-PvP-Native-1.6.0.74.4-typed.20261117-r3-1117003-pvp744-release-20261117-r3-gift-final.apk) | 同包名、同签名覆盖升级，versionCode 1117003 |
| [完整开发者包](https://github.com/ruojimy/PVZ-Rouge-PvP/releases/download/v1.6.0.74.4-pvp744-r3/PvZ-PvP-Native-20261117-pvp744-r3-Developer-Package.zip) | 74.4 r3 正式源码、生成器、冻结生产阶段和配套验证 |
| [SHA-256 清单](https://github.com/ruojimy/PVZ-Rouge-PvP/releases/download/v1.6.0.74.4-pvp744-r3/zh-SHA256SUMS.txt) | 核对三个正式包 |

## 74.4 r3 更新与验证

合作第 8、16、24 关加入泰拉瑞亚 Boss 与钻石奖励；新增合作赠送金币、AI 资源支援及 Boss 注意力选敌。改进合作结算、手机布局和陀螺仪，Boss 资源加入材质工坊；修复磁力菇崩溃、戴夫材质变白和电疗眩晕问题。此前的测试模式、材质与天气修复也包含在内。[完整更新说明](dev/更新说明-PvP74.4.md) · [公开验证摘要](docs/pvp744-r3-validation.json)。

联机双方应统一使用 74.4 r3。本次完成生产内核、UI、资源、Boss、结算定向检查及发行包校验；**完整产品回归未重跑，Android 实机触控、陀螺仪手感和长时压力尚未验收**。历史 27 项未豁免问题保留，不能据此宣称全产品通过。

## 神经网络 AI 研究

新增独立的[神经网络AI板块](ai-nn/README.md)：提供Windows即用研究包、模型/checkpoint、当前216组语料、训练工具、完整源码及验证报告。[研究下载](https://github.com/ruojimy/PVZ-Rouge-PvP/releases/tag/ai-nn-20261114-r1)。

模型实际接管经济、植物进攻模式和墓碑目标数。648局基线无崩溃/AI异常；54组留出对照每阵营各多胜3局，统计尚不显著，继续作为研究候选。正式游戏默认AI仍为r22，74.4 r3 玩家包的交付及默认行为以本次发行说明为准。

## 历史待办

[旧待办清单](待办清单.md) 是 74.3 r2 时的快照，尚未逐项更新至 74.4 r3；不要把其条目状态视为当前验收结果。

## 源码与升级

`dev/` 以 74.4 r3 开发者包为基础更新，并保留仓库原有的历史/AI 研究证据；因此 `dev/` 含少量旧文件，不应把整个目录当成与 ZIP 完全相同的文件集合。正式包清单及逐文件哈希见 `dev/MANIFEST-PvP74.4.json` 和 `dev/SHA256SUMS.txt`。AI 研究的冻结版本仍见上述研究发布页。

生产内核位于 `dev/build/typed72-integrated-v44/source/src/sim/typed/`，组合层拥有源位于 `dev/build/typed72-match-v1/`。Windows 默认使用 `%APPDATA%/PVZ-PvP-Native/pvp_userdata`；Android 同包名同签名覆盖升级。发行包不含个人存档和签名私钥。

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
