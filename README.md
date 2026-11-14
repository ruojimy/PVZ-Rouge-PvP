# PVZ-Rouge · 对战模式（PvP）

中文版当前为 **PvP74.3**（`1.6.0.74.3-typed.20261114`，C++ 原生版，无需 Python）。英文版仍为 PvP64，不能混用联机。

## 下载

[PvP74.3 发布页](https://github.com/ruojimy/PVZ-Rouge-PvP/releases/tag/v1.6.0.74.3-pvp743)。发行附件与最终验证边界见发布页及[交付记录](docs/pvp743-publication.md)。

| 附件 | 用途 |
| --- | --- |
| [Windows 玩家包](https://github.com/ruojimy/PVZ-Rouge-PvP/releases/download/v1.6.0.74.3-pvp743/PvZ-PvP-Native-20261114-pvp743-r1.zip) | 解压运行；覆盖升级保留原用户数据 |
| [Android ARM64](https://github.com/ruojimy/PVZ-Rouge-PvP/releases/download/v1.6.0.74.3-pvp743/PvZ-PvP-Native-1.6.0.74.3-typed.20261114-1114081-20261114-pvp743-r1.apk) | 同包名、同签名，versionCode 1114081，支持覆盖升级 |
| [开发者源码包](https://github.com/ruojimy/PVZ-Rouge-PvP/releases/download/v1.6.0.74.3-pvp743/PvZ-PvP-Native-20261114-pvp743-r1-Developer-Package.zip) | 当前完整源码、拥有源、生产内核/组合层、素材数据、生成工具与精选证据 |
| [SHA-256 清单](https://github.com/ruojimy/PVZ-Rouge-PvP/releases/download/v1.6.0.74.3-pvp743/zh-SHA256SUMS.txt) | 校验三个包及公开说明/验证附件 |

本次修复合作人数上限未进入生产预算，补齐暴怒实际蓝火炬/树桩资源关联，并使工坊打开资源时先成功构建画布再提交选择。详见[更新说明](dev/更新说明-PvP74.3.md)、[不超过600字公告](dev/更新公告-PvP74.3.txt)及[39项任务总清单](dev/PvP74.3_任务总清单.md)。

## 完整继承与验证范围

74.3 完整承接 74.2，不只包含上述三个新反馈。角斗士/普通巨人携带小鬼防具继承、独立甲槽、二手掉落拾取与梯带搭建、弹幕空间碰撞、植物空间索敌、特殊僵尸移动、PC/Android 共用刷新绘制推进、前台心跳重复刷新减少、plant2 重连序号修复、allocator，以及皮肤/英雄/墓碑/状态滤镜均保留。

源码继承静态核对：原生产内核342/342文件与已审核74.2字节一致；src中1308个文件未变，5个修改、5个新增；组合层拥有目录212中210未变。逐文件来源与重点机制摘要见[继承核对](dev/build/pvp743-tools/source-inheritance.md)及其JSON；字节一致不等于新行为回归。

**手机抓人草仍严重卡顿，性能验收未通过。** 同机74.1→74.3：普通23.70→24.39FPS；混合10.70→13.75FPS，但模拟比0.674→0.665没有改善；高弹幕3.41→3.98FPS，模拟比0.556→0.692；抓人草1.97→1.54FPS（-21.9%），模拟比0.328→0.597。不能把减少慢动作直接写成全面更流畅。

四场各版本一次，共八份完成。详见[去标识实机报告](docs/pvp743-android-device-comparison.md)及[完整公开数据](docs/pvp743-android-device-comparison.json)。默认压力控制开启、墙钟推进步数不同，旧版抓人草记录到触屏动作等限制均保留；这不是最终状态严格等价或统计显著性证明。

封包时用户要求先出包、不追加测试；之后用户重新授权才追加手机复测。三个包和dev冻结树不变，包内“未实测”是先前封包时点，最新结果另附。历史74.2完整2366项为2324 PASS、30 FAIL、12 ERROR，只对应当时构建，不能称全绿或冒充74.3新全量。

本次三个包均核验SHA-256，Windows与开发者ZIP逐文件/CRC/UTF-8校验，Android核验签名连续、包名/版本码、五个原生库、资源及编译前后源码指纹。已完成的合作人数、实际梯带部署/客机wire显示、密集高台堆叠等专项保持各自输入和边界；未复现现场不等于问题不存在。

密植/抓人草偶发崩溃、invalid map key/bad allocation、客机长期内存增长和真实云端前台卡主机仍需现场证据，不宣称全部解决。设备帧率也不能替代这些长时与联机验收。公开验证附件不包含私人存档明细、getprop/logcat或直播原始快照。

## 源码与升级

`dev/` 与743开发者包逐文件对应。实际生产内核为 `dev/build/typed72-integrated-v44/source/src/sim/typed/`，组合层拥有源为 `dev/build/typed72-match-v1/`。须同时保留拥有源、生成器和hooks，不能只改早期typed目录。参见[开发者包说明](dev/开发者包说明-PvP74.3.md)。Windows和Android共用大部分代码，只有必须平台层单独适配。

联机玩家/观众统一74.3；Windows覆盖时保留userdata，Android同签名覆盖升级。旧回放按录制版本播放。Python仅用于生成/构建/测试，正式游戏不依赖解释器；历史异步夹具AST指纹由Python3.8生成。开发资源、SDK和签名条件详见dev/README。历史AI语料不自动成为本轮重新导出的训练集。

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
