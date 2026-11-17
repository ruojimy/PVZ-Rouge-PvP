# PvP74.3 开发者包说明

本包版本为 `1.6.0.74.3-typed.20261114`，以已审核 PvP74.2 dev 为历史基底，使用当前工作区拥有源完整覆盖。请从根 README、`PvP74.3_任务总清单.md` 和 `更新说明-PvP74.3.md` 开始阅读。

此前的角斗士巨人和携带小鬼防具、二手防具掉落拾取与梯带搭建、植物索敌空间化、客机 move 心跳刷新合并及 plant2 序号恢复、allocator 修补均保留。`build/pvp743-tools/source-inheritance.json` 比较当前 src、实际生产内核、组合层拥有源与上版的 SHA-256，列出改变文件和其余一致数量；它是静态继承核对，不是行为回归。

用户最新要求先完成出包，暂不实际测试。本轮不追加对局、循环压力或实机测试，也不声称完成新的 74.3 全量。已完成专项结果按报告保留，74.2 全量及门禁仅为历史。未复现群友崩溃、现场堆叠现象和新版本实机性能仍按总清单标明边界；不能将未复现或源码一致改写为已解决。

必须同时保留生产 `build/typed72-integrated-v44/source/`、组合层拥有源 `build/typed72-match-v1/`、生成结果 `src/sim/typed72_app/composition/`、对应生成器与 hooks；只复制生成 C++ 不足以保证以后再生成不反弹。Windows 与 Android 复用大部分代码，仅必要平台层分开。

本包提供 SDL x64 开发依赖，排除项目自身 EXE/OBJ/PDB、个人存档、回放、设备日志、密钥与签名配置。运行素材、Android SDK/NDK/SDL ABI 库与签名条件见根 README。历史 marshal、AI 语料与许可证按原契约保留。

`MANIFEST-PvP74.3.json` 与 `SHA256SUMS.txt` 记录逐文件来源、大小和摘要。ZIP 对每个文件核对 CRC/SHA-256、UTF-8 文件名标志与 Unicode 路径；封包校验不运行游戏、不等于实机验收。历史 74.2 manifest/status 移入 `docs/history/`，避免与当前状态混淆。
