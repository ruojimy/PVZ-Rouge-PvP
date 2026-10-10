# PVZ-Rouge · 对战模式（PvP）

当前版本 `1.6.0.0-pvp.64`，包含迫击炮索敌与部署范围圈内存修复。中英两版规则、卡牌 ID、网络协议和回放格式一致。

## 下载

### 中文版 — [PvP64](../../releases/tag/v1.6.0.0-pvp64)

| 附件 | 用途 |
| --- | --- |
| `PVZ-Rouge-v1.6.0.0-PvP64-Release-Package.zip` | 玩家完整包；入口 `launch_pvp.cmd` |
| `PVZ-Rouge-v1.6.0.0-PvP64-Developer-Package.zip` | 完整源码、Python/C++ 工具、测试与验证记录 |
| `PVZ-Rouge-v1.6.0.0-PvP64-Android.apk` | 已签名安卓包，可覆盖更新旧中文版 |

### English edition — [PvP64 EN](../../releases/tag/v1.6.0.0-pvp64-en)

| Asset | Use |
| --- | --- |
| `PVZ-Rouge-v1.6.0.0-PvP64-EN-Release-Package.zip` | Complete player package; run `launch_pvp_en.cmd` |
| `PVZ-Rouge-v1.6.0.0-PvP64-EN-Developer-Package.zip` | Complete English developer package |
| `PVZ-Rouge-v1.6.0.0-PvP64-EN-Android.apk` | Updates the English app in place; installs alongside Chinese |
| `PVZ-Rouge-v1.6.0.0-PvP64-EN-Overlay.zip` | Apply over this release's Chinese developer package to reconstruct the English developer package; requires the exact base ZIP |

## 验证范围

中文 1536 项／148 模块，英文 1545 项／149 模块；最终零失败、零错误、零跳过。

中英 APK 已在 Android 35 模拟器上通过从 PvP61 升级、原数据保留、两版并存和原生战斗／回放验证。PC 与安卓中英双向主机、直连／本地中继、观战与跨语言回放均已验证。英文图鉴 845 行、PC 与触屏界面巡检 0 漏翻。EXE 启动、APK 签名内容、ZIP 逐文件哈希及实际英文安装目录检查通过。

PC 联机使用与 EXE 模块一致的生产 Application 源码，EXE 另有原生战斗／回放启动检查；安卓使用安装后的签名 APK。未连接真机，未验证异地公网玩家对局。环境失败与复测记录、完整范围和截图均在包内 `验证记录/最终验证20261010/`。

## 更新与兼容

- 原版模式由游戏原引擎处理，对战使用独立规则。
- PvP61 起 PC 存档位于 `%APPDATA%\PVZ-Rouge-PvP\pvp_userdata`，首次启动会并入旧目录存档；从 PvP60 及更早版本升级请先运行对应更新助手。
- Windows 覆盖旧目录请运行对应版本的更新助手：`更新到旧版本.cmd` 或 `更新旧英文版.cmd`。玩家数据、地图、回放与已有中继配置保留，覆盖前备份。
- Android 保留各自既有签名和包名，直接覆盖安装。英文包名 `org.pvzrouge.pvzpvp.en`，可与中文版并存。
- 双方请使用本次修复包。修复前迫击炮遇到不可达目标的旧 PvP64 回放可能在该处校验失败。
- 同一个 EXE/APK 设置 `PVP_LANG=zh` 可显示中文；玩家自填名称按原样显示。原版单人模式的竖排菜单标题仍为中文。
- 每个 Release 附有产物字节数和 SHA256，ZIP 内有逐文件 `SHA256SUMS.txt`。分发包不含个人存档和签名私钥。
