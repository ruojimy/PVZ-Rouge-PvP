---
name: native-acceptance
description: "从玩家发布包执行正式入口自动验收，调用指定的原生游戏或独立工具并保存验证证据。"
---

# 从玩家发布包执行正式入口自动验收

使用范围与验收状态以migration-matrix.json和VALIDATION.md为准。

只调用目标主程序 --smoke-report。证据必须同时满足 passed、native_checks_passed、native_tick=1250、rematched；不以exit=0单独代替。每次显式PVP_USERDATA隔离，真实玩家存档不参与。这是固定脚本场景验收，不是完整旧测试套件，也不是真人试玩。

来源版本：PvP71 developer ZIP。原始路径与SHA见 [迁移对照表](../../migration-matrix.json)，配套接口见 [协议](../../sdk/protocol.md)。

在任意工作目录，显式指定游戏与输出目录：

```powershell
python -I -X utf8 "<扩展>/tools/pvz_tools.py" --game "<游戏目录>" --work "<证据目录>" smoke
```

工具不会自动发现开发源码、复制玩家存档或安装全局技能。错误时读取summary.json和paths.json；不得把格式检查成功视为游戏已接受。
