# 合作房主内存：自定义僵尸别名观察日志最小修复

2026-11-14。实测证据限定为观察日志的保留问题；真实双进程房间300秒效果由R6独立记录。本专项不提供前台FPS结论。

## 确认的根因与修复边界

生产组合中 `ContentZombie64Probe::alias_art` 每次仍把 `{source,target}` 追加到 `aliases64`，默认Session的 `no_trace=true/release_fixtures=true` 没有去掉这一处观察日志。`MatchProbe::alias_art` 经继承链先调用此观察器，再执行真正的 `canvas.alias`。自定义僵尸每模拟tick重复别名，因此日志随游戏时间持续保留。独立采样在 `../coop-rail-live-stack-r1/live-stack-summary.json` 锁定相同JSON分配栈；104秒房主曾有192670条别名，而其他仅诊断数组为0。

修复只增加 `tools/typed72/production_observers.py` 的精确SHA允许规则，生成生产时剥离这一条 `aliases64.push_back`；保留所有before/after业务回调及 `canvas.alias`。拥有源 `build/typed72-match-v1/probes/content_zombies64_probe.cpp` 保留原观察日志，独立fixture不会丢失别名断言。新规则缺失或未知append将使生成校验失败。`make_app_composition.py --check` 通过，观察器专项27/27通过、47个固定函数体。

## 10000模拟tick严格差分

相同seed74314、两只自定义僵尸（海盗船长/乌鸦）、相同合法生成和白盒存活设置；保留旧库实际运行写出的完整结果后，与新生产库同配置逐值比较。两只僵尸全程存活，1200房间tick=10000原生tick。每个采样完整比较snapshot、native_view、624词RNG及索引、native_frame描述，以及所有图像实际物化后的RGBA像素摘要。

|原生tick|旧alias条数|新alias条数|旧requested-live字节|新requested-live字节|五类完整契约相等|
|---:|---:|---:|---:|---:|---|
|0|0|0|0|0|是|
|100|1300|0|939718|678095|是|
|1000|13000|0|4020285|1368934|是|
|10000|130000|0|27874300|2062181|是|

最终像素摘要相同（12图像命令、12260个非透明像素，hash 10049222967475412913）。本夹具在40游戏秒结束时少保留25812119请求字节；这是诊断专用夹具，不替代真实房间增长率。

`comparison.json` 记录逐项断言和SHA；原始旧/新数据为 `before-fixture864.json` 的custom段和 `driver864.json`。旧完整程序随后原始豆夹具使用错误地面高度而失败，失败证据完整保留；其已完成的两僵尸10000tick结果有效。重链时旧库已由统一构建替换，因此未把名为before.exe的新库程序冒充旧版本。之后 `final960.json` 用合法地面960完成当前生产的10000tick零日志和原始豌豆真实过火：已观察火豆，单发命中实际减60；不声称原始豆也完成旧新同源差分。

## 其他内存路径的证伪及限制

`../session-v-projection-isolation-r1/` 的120游戏秒纯Session隔离：无投影requested-live增加1922067字节；每步snapshot→真正json.loads→V→丢弃增加1890003字节；每步直接V投影含FrameProjection增加2047203字节。前两种live_boxes始末51476不变；FrameProjection末51890、稳定保存相邻帧。它们不能单独解释真实R5每分钟约33MiB增长，不能将兼容records_out或V闭包循环认定为本次唯一根因。

本专项没有改写权威match_log/runtime_events日志、回放、音频游标、战斗状态、哈希、随机数、寻路或伤害；真实房主/客机300秒仍以R6原始内存日志为准。未根据源码猜测修复其他长期容器。
