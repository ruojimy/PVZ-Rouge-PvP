---
name: native-relay
description: "运行独立relay并验证原生客户端，调用指定的原生游戏或独立工具并保存验证证据。"
---

# 运行独立relay并验证原生客户端

使用范围与验收状态以migration-matrix.json和VALIDATION.md为准。

保留旧开发者包 server/relay_server.py、health.py 的原始字节，只用标准库。relay-test 临时监听127.0.0.1随机端口并实际使用原生 RelayHostTransport/RelayClientTransport 双向传输，随后停止服务。长期前台服务：python -I -X utf8 tools/relay/relay_server.py --config tools/relay/config.example.json；健康检查：python -I -X utf8 tools/relay/health.py 127.0.0.1 --port 24562。配置默认仅本机；公网部署需另行配置和实测，不自动安装systemd或修改防火墙。

来源版本：PvP71 developer ZIP。原始路径与SHA见 [迁移对照表](../../migration-matrix.json)，配套接口见 [协议](../../sdk/protocol.md)。

在任意工作目录，显式指定游戏与输出目录：

```powershell
python -I -X utf8 "<扩展>/tools/pvz_tools.py" --game "<游戏目录>" --work "<证据目录>" relay-test
```

工具不会自动发现开发源码、复制玩家存档或安装全局技能。错误时读取summary.json和paths.json；不得把格式检查成功视为游戏已接受。
