# PVZ-Rouge · 对战模式（PvP）

中文版当前为 **PvP74.2**（`1.6.0.74.2-typed.20261113`，C++原生版，无需Python）。英文版仍为PvP64，不能混用联机。

## 下载最新版

[PvP74.2 发布页](https://github.com/ruojimy/PVZ-Rouge-PvP/releases/tag/v1.6.0.74.2-pvp742)

| 附件 | 用途 |
| --- | --- |
| [Windows玩家包](https://github.com/ruojimy/PVZ-Rouge-PvP/releases/download/v1.6.0.74.2-pvp742/PvZ-PvP-Native-20261114-pvp742-r2.zip) | 固定顶层PvZ-PvP-Native，解压运行EXE；覆盖升级保留用户数据 |
| [Android ARM64](https://github.com/ruojimy/PVZ-Rouge-PvP/releases/download/v1.6.0.74.2-pvp742/PvZ-PvP-Native-1.6.0.74.2-typed.20261113-1114071-20261114-pvp742-r5.apk) | 同签名原生APK，versionCode1114071；构建/库/资源已核验，本版本实机性能仍待完成 |
| [开发者源码包](https://github.com/ruojimy/PVZ-Rouge-PvP/releases/download/v1.6.0.74.2-pvp742/PvZ-PvP-Native-20261114-pvp742-r2-Developer-Package.zip) | C++源码、生产内核/组合层、拥有源、数据、构建工具、原代码参考、精选证据和旧AI训练材料 |
| [SHA256清单](https://github.com/ruojimy/PVZ-Rouge-PvP/releases/download/v1.6.0.74.2-pvp742/zh-SHA256SUMS.txt) | 核对发行附件 |

本轮减少植物全场索敌、抓人草占格重复遍历、显示帧JSON中转、绘制配方编码与前台心跳重复刷新，修复跨线程小对象回收。合作客机结算、重连、工坊暴怒、传送带、扩展绿洲导航、多向红火和巨人背鬼防具继承/二手拾取等均有专项。详细说明见 [更新说明](dev/更新说明-PvP74.2.md)、[性能与交付](dev/docs/PVP742_性能与交付.md)、[专项验收与剩余问题](dev/docs/PVP742_专项验收与剩余问题.md)。

## 验证范围

2026-11-14：204模块/2366项，2324 PASS、30 FAIL、12 ERROR，与上一正式版逐项相同，没有新增非通过；15项已有精确豁免、27项其他旧问题仍保留，不能称全绿。源码/夹具/测试EXE运行中无漂移。真实PvP、合作、双打的战斗步、输入与AI原生入口内V分配/调用均0，三个门禁通过。

同一当前EXE的性能分支离屏对照（Intel Core Ultra 9 275HX，300 room ticks，关闭慢动作）为：普通60.41→60.45FPS、混合44.36→54.47、高弹幕11.73→17.88、抓人草6.42→12.93；完整战斗状态/原生帧/RNG相同。这不是手机帧率或旧版二进制实机对照。13组索敌/移动/密集/体型/生死测试逐值一致，千单位空闲核心步P50 195.03→18.41ms。

Android已验证签名连续、包名/版本码、5个原生库及资源一致；手机当前无线调试端口关闭，**74.2同场景实机复测尚未完成**。上一版真实手机基线见 [74.1实机记录](docs/pvp741-android-device-performance.md)，不能把PC数字当安卓结果。

密植偶发闪退、群友invalid map<K,T> key/bad allocation及长时客机内存增长仍待现场日志，未宣称已修复；包内debug-run.cmd可开启原始C++抛点，日志另存实际userdata/crashes。232卡路由/文字同步不代表全部图鉴机制验收，高压场景仍有瓶颈。

## 源码与兼容

`dev/` 与本次开发者源码包逐文件对应，包含同版本生成器、实际生产阶段、源数据和精选测试证据。生产内核在 `dev/build/typed72-integrated-v44/source/src/sim/typed/`，组合拥有源在 `dev/build/typed72-match-v1/`，不可只改早期typed目录。PC/Android共用生产代码；材质覆盖仅影响显示，英雄/墓碑与状态滤镜保留，草坪和石块仍排除。

参见 [开发者包说明](dev/开发者包说明-PvP74.2.md)。原异步夹具AST指纹由Python3.8生成，完整回归请使用3.8并按runner准备原始只读夹具/oracle；正式游戏不依赖Python。运行图片/音乐/音效从同版本玩家包准备。SDK、签名密钥和个人存档不在源码包中。

联机玩家/观众请统一74.2。Windows覆盖游戏目录并保留原userdata，Android同包名同签名覆盖安装；旧回放按录制版本播放。历史AI材料保留，不宣称已重新生成74.2训练集。

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
