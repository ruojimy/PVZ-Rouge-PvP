# PvP74.2 发布回执

2026-11-14，正式发布：[v1.6.0.74.2-pvp742](https://github.com/ruojimy/PVZ-Rouge-PvP/releases/tag/v1.6.0.74.2-pvp742)。main中的dev与开发者ZIP逐文件一致，源提交`7f235e434c4e1d6a335c040ef4016408c39da20a`。本回执属于发布元数据，未改任何dev载荷。

本机原生启动器已同步74.2，实际EXE SHA256为`c21032a51cdab66e4382865cabd36a1ba3cba07220285064c4b78d78f495b846`；3629发行文件匹配，544用户文件前后摘要相同。唯一backup-latest保存上一74.1的PC和源码ZIP。

8附件服务器SHA256全部一致，PC/APK/源码ZIP和校验清单已实际回下载核对。6949个dev文件的Git blob与开发者包载荷完全一致。旧74.1发布及tag已移除，英文64和中文64基础包保留；临时源码分支已清理。

完整回归2366项：2324 PASS、30 FAIL、12 ERROR，与上一版逐ID逐结果完全相同；无新增非通过，不能称全绿。15项已有精确豁免和27项其他旧非通过保留。三个真实typed路径门禁通过，源码/夹具/测试EXE在运行期间无漂移。

Android ARM64 versionCode1114071完成签名/5库/资源核验，本次同场景实机性能未完成：提供的无线端口38551已拒绝连接，WLAN直连绕代理路由正常。发布页、公告及报告均明确此限制。PC离屏性能不能当手机FPS。

密植偶发闪退、群友invalid map<K,T> key/bad allocation、长时客机内存增长仍需真实日志。包内debug-run.cmd可记录原始C++抛点，userdata/crashes保存带时间戳日志；未宣称两类异常已经修复。232路由/文本同步也不等于全部机制验收。

[302字纯文本公告](https://github.com/ruojimy/PVZ-Rouge-PvP/releases/download/v1.6.0.74.2-pvp742/pvp742-announcement.txt)、[性能与交付](../dev/docs/PVP742_性能与交付.md)、[专项证据与未覆盖项](../dev/docs/PVP742_专项验收与剩余问题.md)。源码包中的STAGING_STATUS及历史进度是封包时点记录，当前发布状态以本回执及Release附件为准。
