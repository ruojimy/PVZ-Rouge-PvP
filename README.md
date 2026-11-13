# PVZ-Rouge · 对战模式（PvP）

中文版当前为 **PvP74.1**（`1.6.0.74.1-typed.20261113`，C++ 原生版，无需 Python）。英文版仍为 PvP64，两者不能混用联机。

## 下载最新版

[PvP74.1 中文版发布页](https://github.com/ruojimy/PVZ-Rouge-PvP/releases/tag/v1.6.0.74.1-pvp741)

| 附件 | 用途 |
| --- | --- |
| [Windows 玩家包](https://github.com/ruojimy/PVZ-Rouge-PvP/releases/download/v1.6.0.74.1-pvp741/PvZ-PvP-Native-20261113-pvp741-r1.zip) | 解压后运行 `PvZ-PvP-Native/PvZPvPNative.exe`；覆盖升级会保留用户数据 |
| [Android ARM64](https://github.com/ruojimy/PVZ-Rouge-PvP/releases/download/v1.6.0.74.1-pvp741/PvZ-PvP-Native-1.6.0.74.1-typed.20261113-1113075-20261113-pvp741-r3.apk) | 已签名原生 APK，包名 `org.pvzrouge.pvzpvpnative`，版本码 1113075 |
| [开发者源码包](https://github.com/ruojimy/PVZ-Rouge-PvP/releases/download/v1.6.0.74.1-pvp741/PvZ-PvP-Native-20261113-pvp741-r1-Developer-Package.zip) | C++ 源码、实际类型化内核与组合层、生成器、原版反编译源码、工具、数据和精选验证记录 |
| [SHA256 校验清单](https://github.com/ruojimy/PVZ-Rouge-PvP/releases/download/v1.6.0.74.1-pvp741/zh-SHA256SUMS.txt) | 对照发行附件的 SHA256 |

材质工坊支持卡牌、弹幕、墓碑和双方英雄绘制，房主向客机／观众共享；状态滤镜保留，草坪、石块排除。空间索引优化弹幕碰撞和目标查询，修复合作客机昼夜、小目标追踪、抓人草及前序热修问题。慢动作保留开局保护和恢复控制。详情见发布页公告、[更新说明](dev/更新说明-PvP74.1.md)与[完整验收报告](dev/docs/PVP74.1_空间优化与验收.md)。

## 源码（dev/）

dev/ 已覆盖为本次开发者包的源码与资料，README 版本索引及相应校验项随 GitHub 发布同步维护，其他文件与开发者包内容一致。入口为 [开发者包说明](dev/开发者包说明-PvP74.1.md)。既有 AI 训练基础材料位于 dev/docs/ai-nn/ 和 dev/build/ai-nn/。

生产内核位于 `dev/build/typed72-integrated-v44/source/src/sim/typed/`，组合层来源为 `dev/build/typed72-match-v1/`。不要仅修改早期 `dev/src/sim/typed/`。PC、Android 共用生产内核、空间索引、寻路、UI 和材质代码。运行时图片／音乐／音效从同版本玩家包准备，签名私钥与原测试外部夹具需自行配置，详见开发者包说明。

## 验证范围

2026-11-13：全量 2366 项，2324 PASS、30 FAIL、12 ERROR，与上一正式版基线一致，无新增非通过项；15 项精确豁免、27 项其他既有失败，不能称全绿。真实 PvP／合作／双打应用的动态战斗步、输入和 AI 路径内，旧 V 运行时分配与调用均为零。

生产特殊移动差分 113 项、火焰豌豆矩阵 18 项、战斗与压力 17 项、英雄材质 8 项及数学索引 5 项等专项通过。直连／私有中继三进程昼夜通过，PC 解压启动和覆盖升级通过，APK 签名、包名、版本码、嵌入库和资源一致。

固定种子高弹幕场景原速实测 2.31→10.82 FPS；重抓人草压力场景仍有绘制瓶颈，不承诺高压全面流畅。Android 本轮未作真机验收，未验证异地公网。普通点弹仍保留原精判，不宣称全面新增 CCD；图鉴路由检查不等于所有卡牌描述均已逐条证明。原始证据与来源摘要见 dev/docs/evidence/pvp741/。

## 更新与兼容

中文版联机玩家及观众请统一使用 PvP74.1。Windows 玩家包保持单一顶层目录，退出游戏后覆盖升级，保留原存档目录。Android 与上一原生中文版同包名、同签名且版本码递增；与 PvP64 及更早的 Python 中文版是不同应用，会并存。旧版回放使用录制时的版本播放。

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
