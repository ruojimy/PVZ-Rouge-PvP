# PVZ-Rouge · 对战模式（PvP）

《植物大战僵尸》Roguelike 改版的**对战模式（PvP）**发布记录与完整包。当前版本 `1.6.0.0-pvp.53`。

## 下载

到 [Releases](../../releases) 取对应版本。

### 中文版 — [v1.6.0.0-pvp53](../../releases/tag/v1.6.0.0-pvp53)

| 附件 | 用途 |
| --- | --- |
| `PVZ-Rouge-v1.6.0.0-PvP53-Release-Package.zip` | 开箱即玩 + 联机，面向玩家 |
| `PVZ-Rouge-v1.6.0.0-PvP53-Developer-Package.zip` | 含 modkit 源码、测试套件、验证记录与文档，面向二次开发与自建联机中继。入口 `launch_pvp.cmd` |
| `PVZ-Rouge-v1.6.0.0-PvP53-Android.apk` | 已签名安卓安装包，与 PC 版同版本互通 |

### English edition — [v1.6.0.0-pvp53-en](../../releases/tag/v1.6.0.0-pvp53-en)

| Asset | Use |
| --- | --- |
| `PVZ-Rouge-v1.6.0.0-PvP53-EN-Developer-Package.zip` | Full English package (PC). Launch with `launch_pvp_en.cmd` |
| `PVZ-Rouge-v1.6.0.0-PvP53-EN-Android.apk` | English Android build — a **separate app** (`PVZ PvP (EN)`), installs alongside the Chinese one |
| `PVZ-Rouge-v1.6.0.0-PvP53-EN-Core-Delta.zip` + `-Graphics-Delta.zip` | Deltas, **not standalone** — unzip both over the Chinese PvP53 developer package to get the English one |

> 英文版与中文版共用同一个 `build` 与同一组 rules / catalog 哈希，**中英双方可同房联机、互相观战、互导回放**。
> 同一个 EXE/APK 设 `PVP_LANG=zh` 即显示原中文。

## 校验

每个 Release 的说明里给出各产物的字节数与 SHA-256；包内另有 `SHA256SUMS.txt` 做逐文件校验。下载后请自行比对再使用。

## 说明

- 原版模式仍由游戏原引擎处理，对战使用独立规则。
- 分发包不含个人存档与联机凭据。
- 联机双方请使用同一版本。
- 英文版 APK 未在实体手机或模拟器上安装验证，详见该 Release 的「已知边界」。
