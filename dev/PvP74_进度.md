# PvP74 实现与交付记录

功能拥有源为 `src/ui/hand/texture74_{model,editor,network,files}.cpp`，公共边界在 `texture_pack.h`，绘画模型与内部状态在 `texture74_internal.h`。没有修改只读 71 项目。

`tools/pvp74_resource_catalog.py` 汇总正式图集、原始图片、扩展资源及用生产绘制器烘焙的完整卡面；结果是 `extract/data/texture_resources74.json` 与 `texture_card_icons74.json`。原始素材仍保留，用户包仅在用户数据目录中存储。

`tools/pvp74_apply_hooks.py` 维护 app、首页、Renderer、NativeArt、WorldView、DrawReplay 和 PNG 读取边界的少量原生接入；CMake 检查 `--check` 防止未来重新翻译后静默丢失。观战消息白名单只增加只读材质请求、确认和观战保活；部署、移动等输入的限制保留。

显示用 DrawReplay resolver 有单独标识，原始 materializer 与原图读取强制排除材质覆盖，避免透明像素改变权威粒子随机采样。缓存带材质版本号，启用、关闭和切包都会失效重建。卡面图标、完整原图和各状态变体均有对应显示接入。

连接状态按 Application 实例隔离，关闭时释放，避免同一进程中的多个客户端互相清除分片与确认进度。全量回归发现的三个观战房间用例已修复并通过定向复测，最终以重新运行的干净完整套件为准。

`src/uitools/pvp74_texture_audit.cpp` 检查真实界面输入、原始资源覆盖、图层/PNG/包往返、灰色与受伤等变体、实际 WorldView 像素变化及相同战斗状态哈希。`test_results/pvp74/network_fixture.py` 使用三个实际应用进程、真实直连或私有云端房间检查多分片共享、后加入观众、反向材质拒绝和退出恢复。没有使用用户正式存档。

本轮最终包、完整套件、源码指纹、启动器目标和未通过的旧测试清单见 `test_results/pvp74/交付验收.md` 与 `dist/PvP74-20261113-release-manifest.json`。这些最终清单在验收结束后生成；过程截图和候选文件不等同于最终交付。
