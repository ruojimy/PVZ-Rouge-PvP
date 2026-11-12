---
name: native-export
description: "导出目标原生版本的规则和卡池，调用指定的原生游戏或独立工具并保存验证证据。"
---

# 导出目标原生版本的规则和卡池

使用范围与验收状态以migration-matrix.json和VALIDATION.md为准。

读取游戏进程运行时 actual_card、RULES、describe、排除项和版本哈希。cards是指定条件下的实际解析值，raw_templates明确只保留基础模板；可传--night及多次--secret，context说明条件。所有数值来自指定游戏，旧 export_pvp_rules.py 中固定的说明文字不再作为72规则依据。输出是分析资料，不是热加载规则补丁。

来源版本：PvP71 developer ZIP。原始路径与SHA见 [迁移对照表](../../migration-matrix.json)，配套接口见 [协议](../../sdk/protocol.md)。

在任意工作目录，显式指定游戏与输出目录：

```powershell
python -I -X utf8 "<扩展>/tools/pvz_tools.py" --game "<游戏目录>" --work "<证据目录>" export --output "运行时数据.json"
```

工具不会自动发现开发源码、复制玩家存档或安装全局技能。错误时读取summary.json和paths.json；不得把格式检查成功视为游戏已接受。
