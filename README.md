# PVZ-Rouge · 对战模式（PvP）

《植物大战僵尸》Roguelike 改版的**对战模式（PvP）**发布记录与完整包。当前版本 `1.6.0.0-pvp.60`。

## 下载

到 [Releases](../../releases) 取对应版本。

### 中文版 — [v1.6.0.0-pvp60](../../releases/tag/v1.6.0.0-pvp60)

| 附件 | 用途 |
| --- | --- |
| `PVZ-Rouge-v1.6.0.0-PvP60-Release-Package.zip` | 开箱即玩 + 联机，面向玩家 |
| `PVZ-Rouge-v1.6.0.0-PvP60-Developer-Package.zip` | 含 modkit 源码、测试套件、验证记录与文档，面向二次开发与自建联机中继。入口 `launch_pvp.cmd` |
| `PVZ-Rouge-v1.6.0.0-PvP60-Android.apk` | 已签名安卓安装包，与 PC 版同版本互通 |

### English edition — [v1.6.0.0-pvp60-en](../../releases/tag/v1.6.0.0-pvp60-en)

| Asset | Use |
| --- | --- |
| `PVZ-Rouge-v1.6.0.0-PvP60-EN-Developer-Package.zip` | Full English package (PC). Launch with `launch_pvp_en.cmd` |
| `PVZ-Rouge-v1.6.0.0-PvP60-EN-Android.apk` | English Android build — a **separate app** (`PVZ PvP (EN)`), installs alongside the Chinese one |
| `PVZ-Rouge-v1.6.0.0-PvP60-EN-Overlay.zip` | Overlay, **not standalone** — unzip over the Chinese PvP60 developer package to get the English one |

> 英文版与中文版共用同一个 `build` 与同一组 rules / catalog 哈希，可用同一房间与回放格式。
> 同一个 EXE/APK 设 `PVP_LANG=zh` 即显示原中文。
> ★ 从 PvP60 起，英文交付**只发一个增量包**（此前是"核心增量包 + 画面增量包"两个）。

## ⚠️ 验证范围提示

PvP60（修订 `balance-turn-20261002`）与 PvP59 一样**未重跑全量测试**，只做了 41 项相关专项；
**Android 也未跑模拟器或真机**，只做签名与内容校验（并复用已核验的 PvP59 原生运行库）。
英文版同样如此，其记录明确写了「PvP59 英文版当时的模拟器与中英联机结论属历史，不是 PvP60 的结果」。

**未覆盖**：安卓模拟器 / 真机、中英实时对局（TCP / 中继 / 观战 / 回放）、公网对局。
各 Release 的说明里列出了精确的验证范围与校验值 —— 下载前请一读。

## 校验

每个 Release 的说明里给出各产物的字节数与 SHA-256；包内另有 `SHA256SUMS.txt` 做逐文件校验。下载后请自行比对再使用。

## 说明

- 原版模式仍由游戏原引擎处理，对战使用独立规则。
- 分发包不含个人存档与联机凭据。
- 联机双方请使用同一版本（PvP60）。
