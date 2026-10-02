# PVZ-Rouge · 对战模式（PvP）

《植物大战僵尸》Roguelike 改版的**对战模式（PvP）**发布记录与完整包。当前版本 `1.6.0.0-pvp.61`。

## 下载

到 [Releases](../../releases) 取对应版本。

### 中文版 — [v1.6.0.0-pvp61](../../releases/tag/v1.6.0.0-pvp61)

| 附件 | 用途 |
| --- | --- |
| `PVZ-Rouge-v1.6.0.0-PvP61-Release-Package.zip` | 开箱即玩 + 联机，面向玩家 |
| `PVZ-Rouge-v1.6.0.0-PvP61-Developer-Package.zip` | 含 modkit 源码、测试套件、验证记录与文档，面向二次开发与自建联机中继。入口 `launch_pvp.cmd` |
| `PVZ-Rouge-v1.6.0.0-PvP61-Android.apk` | 已签名安卓安装包，与 PC 版同版本互通 |

### English edition — [v1.6.0.0-pvp61-en](../../releases/tag/v1.6.0.0-pvp61-en)

| Asset | Use |
| --- | --- |
| `PVZ-Rouge-v1.6.0.0-PvP61-EN-Developer-Package.zip` | Full English package (PC). Launch with `launch_pvp_en.cmd` |
| `PVZ-Rouge-v1.6.0.0-PvP61-EN-Android.apk` | English Android build — a **separate app** (`PVZ PvP (EN)`), installs alongside the Chinese one |
| `PVZ-Rouge-v1.6.0.0-PvP61-EN-Overlay.zip` | Overlay, **not standalone** — unzip over the Chinese PvP61 developer package to get the English one |

> 英文版与中文版共用同一个 `build` 与同一组 rules / catalog 哈希，可用同一房间与回放格式。
> 同一个 EXE/APK 设 `PVP_LANG=zh` 即显示原中文。

## 验证范围提示

PvP61（修订 `pvp61-art-20261002`，含新植物动画与图标）**重跑了全量测试**：中文 1597 项（1 项过时断言修正后重跑通过），
英文工作区 1606 项通过；英文卡面 824 行 0 漏翻，界面探针 0 处遗留中文。EXE 原生对战与回放冒烟通过。

**未覆盖**：安卓模拟器 / 真机（APK 只做签名与内容校验）、中英实时对局（TCP / 中继 / 观战 / 回放）、公网对局。
各 Release 的说明里列出了精确的验证范围与校验值 —— 下载前请一读。

## 校验

每个 Release 的说明里给出各产物的字节数与 SHA-256；包内另有 `SHA256SUMS.txt` 做逐文件校验。下载后请自行比对再使用。

## 说明

- 原版模式仍由游戏原引擎处理，对战使用独立规则。
- 分发包不含个人存档与联机凭据。
- 联机双方请使用同一版本（PvP61）。
- PvP61 起 PC 版存档位于 `%APPDATA%\PVZ-Rouge-PvP\pvp_userdata`，首次启动自动并入旧目录存档；从 PvP60 及更早版本升级请先用覆盖助手 `更新到旧版本.cmd`。
