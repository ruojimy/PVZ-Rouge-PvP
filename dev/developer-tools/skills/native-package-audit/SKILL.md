---
name: native-package-audit
description: "检查允许清单、哈希和原生APK结构，调用指定的原生游戏或独立工具并保存验证证据。"
---

# 检查允许清单、哈希和原生APK结构

使用范围与验收状态以migration-matrix.json和VALIDATION.md为准。

audit 对完整允许清单、逐文件长度和SHA256、SHA256SUMS再读校验。apk-inspect "游戏.apk" 校验ZIP CRC、包身份、原生游戏版本JSON、ABI/ELF LOAD段对齐；如传--game还核对PC构建版本。它不验证签名或设备运行，4KiB ELF不会被误报成16KiB兼容。没有构建/签名/安装动作。

来源版本：PvP71 developer ZIP。原始路径与SHA见 [迁移对照表](../../migration-matrix.json)，配套接口见 [协议](../../sdk/protocol.md)。

在任意工作目录，显式指定游戏与输出目录：

```powershell
python -I -X utf8 "<扩展>/tools/pvz_tools.py" --game "<游戏目录>" --work "<证据目录>" audit --target "developer-tools" --manifest "developer-tools/manifest.json"
```

工具不会自动发现开发源码、复制玩家存档或安装全局技能。错误时读取summary.json和paths.json；不得把格式检查成功视为游戏已接受。
