---
name: native-replay
description: "记录和验证实际原生回放，调用指定的原生游戏或独立工具并保存验证证据。"
---

# 记录和验证实际原生回放

使用范围与验收状态以migration-matrix.json和VALIDATION.md为准。

演示以真实 NativeBattle 接受移动/跳跃输入并通过 Recording.export 保存。工具另启新进程调用 read_recording 和 Playback，实际步进到终点核对状态哈希。对自己的回放运行 replay-check "回放.json"。离线工具上限120000房间tick/180秒；正常游戏回放上限未修改。版本或终点哈希不符必须失败，不能仅重算JSON摘要。

来源版本：PvP71 developer ZIP。原始路径与SHA见 [迁移对照表](../../migration-matrix.json)，配套接口见 [协议](../../sdk/protocol.md)。

在任意工作目录，显式指定游戏与输出目录：

```powershell
python -I -X utf8 "<扩展>/tools/pvz_tools.py" --game "<游戏目录>" --work "<证据目录>" replay-demo --ticks 30 --output "示例回放.json"
```

工具不会自动发现开发源码、复制玩家存档或安装全局技能。错误时读取summary.json和paths.json；不得把格式检查成功视为游戏已接受。
