# PVZ-Rouge · 对战模式（PvP）

中文版最新为 **PvP74.3 r2**（`1.6.0.74.3-typed.20261114`，C++原生版，无需Python），Android versionCode **1114082**。英文版仍为PvP64，不能混用联机。

## 下载

[当前发布页](https://github.com/ruojimy/PVZ-Rouge-PvP/releases/tag/v1.6.0.74.3-pvp743)：在原PvP74.3发布页覆盖旧r1附件，不另建仓库。

| 附件 | 用途 |
| --- | --- |
| [Windows玩家包](https://github.com/ruojimy/PVZ-Rouge-PvP/releases/download/v1.6.0.74.3-pvp743/PvZ-PvP-Native-20261114-pvp743-r2.zip) | 解压运行，覆盖升级保留userdata |
| [Android ARM64](https://github.com/ruojimy/PVZ-Rouge-PvP/releases/download/v1.6.0.74.3-pvp743/PvZ-PvP-Native-1.6.0.74.3-typed.20261114-1114082-20261114-pvp743-r2.apk) | 同包名/同签名覆盖升级，versionCode1114082 |
| [完整开发者包](https://github.com/ruojimy/PVZ-Rouge-PvP/releases/download/v1.6.0.74.3-pvp743/PvZ-PvP-Native-20261114-pvp743-r2-Developer-Package.zip) | 正式r2冻结源码；最新含AI研究的完整源码见下方AI板块 |
| [SHA-256清单](https://github.com/ruojimy/PVZ-Rouge-PvP/releases/download/v1.6.0.74.3-pvp743/zh-SHA256SUMS.txt) | 校验包和公开附件 |

## 神经网络 AI 研究

新增独立的[神经网络AI板块](ai-nn/README.md)：提供Windows即用研究包、模型/checkpoint、当前216组语料、训练工具、完整源码及验证报告。[研究下载](https://github.com/ruojimy/PVZ-Rouge-PvP/releases/tag/ai-nn-20261114-r1)。

模型实际接管经济、植物进攻模式和墓碑目标数。648局基线无崩溃/AI异常；54组留出对照每阵营各多胜3局，统计尚不显著，继续作为研究候选。正式游戏默认AI仍为r22，正式玩家包保持r2。

## r2修复与验收

修复基础/详细记录按钮在点击当帧读取未初始化计时的num - absent闪退、停止/切换记录器的回调自环，以及误留在生产路径的僵尸绘图别名观察日志。实际贴图、状态滤镜和战斗机制保留。

相同合作场景300秒，房主Private由585.35→848.15MiB降为584.79→649.86MiB；后段requested-live增速33.08→4.40MiB/分钟（降低86.70%）。**仍有少量增长，长期/跨局上限未验证，不宣称完全无泄漏。** [内存对照](docs/pvp743-r2-memory.md)。

25项定向检查、主/客×基础/详细4条完整记录流程通过；10000原生tick的完整state/native/RNG/frame/pixels相同，原始豌豆过火单发60。PC包内EXE隔离诊断、ZIP逐文件/CRC/UTF-8、APK同签名/资源/原生库/源码指纹已核验。[交付记录](docs/pvp743-publication.md) · [公开验证](docs/pvp743-r2-validation.json)。

**r2安卓真机、前台FPS及长期跨局未验收。** 旧r1同机抓人草仅1.54FPS、性能未通过；该结果不代表r2，见[历史r1手机报告](docs/pvp743-android-device-comparison.md)。历史742全量2366项为2324 PASS/30 FAIL/12 ERROR，不是全绿，也不冒充r2新全量。

## 后续工作

[统一待办T01–T23](待办清单.md)区分待优化、待复现和待验收，覆盖手机高压性能、长期内存、偶发崩溃、云端前台卡顿、全量回归和机制覆盖等。旧迁移计划已归档，A1死墓位记忆、A2解除封印出兵口已实现，不重复列未完成。

[39项历史需求及r2状态](dev/PvP74.3_任务总清单.md) · [修复说明](dev/更新说明-PvP74.3-r2.md) · [600字内纯文本公告](dev/更新公告-PvP74.3-r2.txt)。

## 源码与升级

`dev/`已覆盖为最新AI研究源码（7533文件），与[最新完整开发者包](https://github.com/ruojimy/PVZ-Rouge-PvP/releases/download/ai-nn-20261114-r1/PvZ-PvP-Native-20261114-ai-nn-r1-Developer-Package.zip)逐文件对应；正式r2源码由原标签/开发者包固定。当前源码完整继承巨人/背部小鬼防具、二手掉落/拾取搭建、空间碰撞/植物索敌/共享寻路、特殊僵尸、工坊皮肤/英雄/墓碑/滤镜、PC/Android共用推进绘制和联机修复。

实际生产内核为`dev/build/typed72-integrated-v44/source/src/sim/typed/`，组合拥有源为`dev/build/typed72-match-v1/`；须保留拥有源、生成器和hooks。[开发者说明](dev/开发者包说明-PvP74.3.md)。PC/Android共用大部分代码，必须平台层单独适配。

联机统一74.3，Windows保留userdata，Android同签名覆盖升级，旧回放按录制版本播放。发布包不含私人存档、原始logcat/getprop和签名私钥。

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
- `third_party/` 中的 SDL2 系列、nlohmann/json、zlib 沿用各自的许可。

每个 Release 提供附件 SHA256，ZIP 内另有逐文件校验清单。分发包不含个人存档和签名私钥。
