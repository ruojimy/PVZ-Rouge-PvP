# PVZ-Rouge · 对战模式（PvP）

中文版最新正式版为 **PvP75 r2**（`1.6.0.75-typed.20261121-r2`，C++ 原生版，无需 Python），Android versionCode **1121077**。英文版仍为 PvP64，不可混用联机。

## 下载

[PvP75 r2 正式发布页](https://github.com/ruojimy/PVZ-Rouge-PvP/releases/tag/v1.6.0.75-pvp75-r2) · [历史版本](https://github.com/ruojimy/PVZ-Rouge-PvP/releases)

| 附件 | 用途 |
| --- | --- |
| [Windows 玩家包](https://github.com/ruojimy/PVZ-Rouge-PvP/releases/download/v1.6.0.75-pvp75-r2/PvZ-PvP-Native-20261121-pvp75-r2.zip) | 解压后运行“启动PvP.cmd”；默认使用独立用户数据目录 |
| [Android ARM64](https://github.com/ruojimy/PVZ-Rouge-PvP/releases/download/v1.6.0.75-pvp75-r2/PvZ-PvP-Native-1.6.0.75-typed.20261121-r2-1121077-pvp75-r2-20261121.apk) | 同包名、同签名覆盖升级，versionCode 1121077 |
| [完整开发者包](https://github.com/ruojimy/PVZ-Rouge-PvP/releases/download/v1.6.0.75-pvp75-r2/PvZ-PvP-Native-20261121-pvp75-r2-Developer-Package.zip) | PvP75 r2 正式源码、生成器、冻结生产阶段和配套验证 |
| [SHA-256 清单](https://github.com/ruojimy/PVZ-Rouge-PvP/releases/download/v1.6.0.75-pvp75-r2/zh-SHA256SUMS.txt) | 核对三个正式包 |

## PvP75 更新

新卡：巴豆、激光豆、盾卫僵尸、克苏鲁之仆（新贴图与动画，全部收入材质工坊，并接入合作模式）。平衡：小鬼、黑普通、撑杆 50 脑光，海豚 40；投篮车与小鬼炮 120 血；雪橇车小队逐秒出场；三叶草改为不可选中的飞行植物；杨桃 300 阳光、星星穿透 3 个单位，大帝改为穿透 +1；加农炮 32 秒装填；补贴秘籍改为无僵尸时周期补给 6 秒后再给 15 脑光；Boss 的冰冻、黄油、眩晕改为同时长减速。

r2 修正：激光豆在正式版中无法瞄准发射的问题；范围提示改为面朝方向 ±80° 扇形；激光豆、巴豆静置动画；盾卫僵尸中毒变色；克苏鲁之仆冷却 20 秒；测试模式“该方0冷却”开关；材质工坊卡面图标修正。性能：激光光束分段绘制，单位旋转与受伤闪烁的绘制缓存改进，身首分开画的僵尸与带防具僵尸在持续受击时明显减少卡顿。[完整更新说明](dev/更新说明-PvP75.md) · [公开验证摘要](docs/pvp75-r2-validation.json)。

联机双方应统一使用 PvP75 r2（与 r1、74.4 不兼容）。本次完整产品回归已重跑：2351 通过、3 失败、12 错误、0 缺失，其余 15 项均为既有已豁免问题，相对 r1 无新增。Android 已在一台实机（vivo V2456A）上完成覆盖安装与性能诊断场景实测；**实机触控手感、双机联机与长时压力尚未正式验收**。

## 神经网络 AI 研究

独立的[神经网络AI板块](ai-nn/README.md)：提供Windows即用研究包、模型/checkpoint、216组语料、训练工具、完整源码及验证报告。[研究下载](https://github.com/ruojimy/PVZ-Rouge-PvP/releases/tag/ai-nn-20261114-r1)。该研究包为 11-14 冻结版本；正式游戏默认 AI 及行为以当前发行说明为准。

## 历史待办

[旧待办清单](待办清单.md) 是 74.3 r2 时的快照，未逐项更新；不要把其条目状态视为当前验收结果。

## 源码与升级

`dev/` 与 PvP75 r2 开发者包逐文件一致（仅 `.gitignore` 排除的 AI 研究语料目录不上传，见上方研究发布页）。正式包清单及逐文件哈希见 `dev/MANIFEST-PvP75.json` 和 `dev/SHA256SUMS.txt`。

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
