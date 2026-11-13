# PvP74.2 开发者包说明

本轮开发者源码暂存使用已审核的 PvP74.1 Git dev 目录作历史基底，覆盖当前拥有的 src、android、tools、运行数据与图集、生产阶段和组合层输入。请先读根README；本次完整回归与三模式门禁已完成，结果与上一正式版一致。Android构建核验完成，实机性能待连接恢复；相关未验收范围明确保留。

必须同时保留：

- `build/typed72-integrated-v44/source/` 全部生产 C++ 与头文件，包括 cold 目录和数据表。
- `build/typed72-match-v1/{match_probe.cpp,frame_layer.inc,snapshot_layer.inc}`、probes 及生成规则。
- `src/sim/typed72_app/composition/` 和 `MANIFEST.json`，以及 `tools/typed72/production_observers.py` 等生成契约。
- `tools/pvp74_apply_hooks.py`、`tools/pvp741_apply_hooks.py`、对应拥有源、资源清单和数据；只复制生成 C++ 不足以保证以后再生成不反弹。
- `build/ai-nn/` 旧离线语料与 `docs/ai-nn/` 规格，作为历史训练材料保留，不宣称已按本轮规则重新导出。

Windows 入口是根 CMakeLists，Android 入口是 android。两平台共用生产代码，仅系统接口和必须的移动适配分支不同。运行时三类原版图片/音乐/音效资源、relay.json 和 Android CJK 字体需从同版本游戏资源准备；SDK、NDK、SDL Android 依赖和签名密钥由开发者配置。

本包应包含根 CMake 需要的 SDL `lib/x64` 开发依赖，修正旧打包器把所有 x64 目录一并过滤的问题。项目自身 EXE、OBJ、PDB、构建目录、个人设备日志、用户数据和密钥不进入暂存。历史 `.marshal` 输入和 AI `.gz` 数据不属于可随意删除的项目编译输出。

逐文件来源和摘要见 MANIFEST-PvP74.2.json 与 SHA256SUMS.txt。最终ZIP由经过来源哈希复核的staging封装，精选完整回归和专项证据随包提供。STAGING_STATUS记录Android实机、未复现崩溃等剩余范围，不把构建校验当作手机性能证明。
