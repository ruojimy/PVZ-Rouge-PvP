---
name: native-maps
description: "创建、校验和导入原生自定义地图，调用指定的原生游戏或独立工具并保存验证证据。"
---

# 创建、校验和导入原生自定义地图

使用范围与验收状态以migration-matrix.json和VALIDATION.md为准。

随后运行 map-check "地图.json"；运行 map-import "地图.json" --store "隔离用户目录/maps" 时必须显式指定目录。原生 validate_document、snapshot_from_document、Room._map_proposal、NativeBattle.step、MapStore.save/load 全链路执行。重复ID拒绝覆盖。默认示例不写玩家存档；真正用于玩家地图库时显式选择其maps目录。

来源版本：PvP71 developer ZIP。原始路径与SHA见 [迁移对照表](../../migration-matrix.json)，配套接口见 [协议](../../sdk/protocol.md)。

在任意工作目录，显式指定游戏与输出目录：

```powershell
python -I -X utf8 "<扩展>/tools/pvz_tools.py" --game "<游戏目录>" --work "<证据目录>" map-new --blank --name "我的地图" --output "地图.json"
```

工具不会自动发现开发源码、复制玩家存档或安装全局技能。错误时读取summary.json和paths.json；不得把格式检查成功视为游戏已接受。
