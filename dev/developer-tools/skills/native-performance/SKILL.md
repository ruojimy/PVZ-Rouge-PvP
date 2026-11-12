---
name: native-performance
description: "采集目标程序的实际性能诊断，调用指定的原生游戏或独立工具并保存验证证据。"
---

# 采集目标程序的实际性能诊断

使用范围与验收状态以migration-matrix.json和VALIDATION.md为准。

只调用真实主程序 --diagnostic，保留原报告和native72元数据。ordinary/mixed/barrage可选，使用显式隔离存档。结果含初始化、设备及桌面负载影响；短样本不用于倍数承诺。PVZ72_RENDER_STATS=1仅在本次诊断子进程启用。Android设备流程没有迁移验收；不自动连接手机。

来源版本：PvP71 developer ZIP。原始路径与SHA见 [迁移对照表](../../migration-matrix.json)，配套接口见 [协议](../../sdk/protocol.md)。

在任意工作目录，显式指定游戏与输出目录：

```powershell
python -I -X utf8 "<扩展>/tools/pvz_tools.py" --game "<游戏目录>" --work "<证据目录>" diagnostic --scene ordinary --units 20 --warmup 1 --seconds 5
```

工具不会自动发现开发源码、复制玩家存档或安装全局技能。错误时读取summary.json和paths.json；不得把格式检查成功视为游戏已接受。
