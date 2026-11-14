# 传送带搭成后的客机地形与显示复查

2026-11-14。最终 [conveyor-guest-r3.json](conveyor-guest-r3.json) 为PASS、进程exit0。只新增/修正 [pvp742_conveyor_guest_display_audit.cpp](../../src/uitools/pvp742_conveyor_guest_display_audit.cpp)，没有修改生产代码，没有操作用户窗口、存档或正在运行的房间。结论是本次路径未复现传送带状态丢失或默认资产不可见，不是已定位用户现场问题。

## 真实链路

实际合作Room第10天 `_start_pve`，原Director计划/池/RNG自然生成传送带僵尸，走原ColdAdmission入场和架设。在受控高台地图上推进1204个room step后，实际21行41列成为 `kind=梯子块、ladder=true、native._pvp_belt=true`。被测传送带未改位置、HP、装备或出场；为允许后续波次，84个非传送带背景对象由夹具置HP0，此干预明确保留。

从该实际房间经过：

`Application.publish_network → Room.snapshot → pack_snapshot → encode_frame → 后台ClientTransport._read/FrameDecoder → UI Application.poll_network/unpack_snapshot/merge_view → Application.render/WorldView`

复用 [pvp742_guest_memory_fixture.h](../../src/uitools/pvp742_guest_memory_fixture.h) 的真实接收/解码路径，只替换socket recv为分块录制输入；没有手写替代JSON合并或假codec。房主使用生产同步打包回退，测试没有覆盖异步pack-worker调度。

| 检查 | 最终实际结果 |
| --- | --- |
| 初始完整快照 | 合法房间原始map与battle当前map均存在，客机通过地形哈希检查 |
| 架设后的地形版本 | terrain_revision从0变为3，房主发送含当前battle.map的快照 |
| wire/merge保留 | 客机对应格kind、ladder、native belt均正确，无map_sync_error |
| 未变化的后续快照 | 生产publish省略两份map；merge保留已有带子地形 |
| 重连 | 向实际host poll注入reconnected协议事件，Room.connect及Application逻辑清掉该peer的sent_map；全新guest收完整当前地形并保留带子 |
| 原生绘制 | 原客机/重连客机Application均完成绘制，native_error为空，整App画面哈希一致 |

## 可见性证据

在**显示夹具**中将实际设施格居中，不挪设施、单位、出生点或英雄，不修改模拟状态。实际全场WorldView对照只改变所收到地图中该格的显示数据，其余battle/native_frame保持相同。

| 对照 | 原客机改变像素 | 重连客机改变像素 |
| --- | ---: | ---: |
| 传送带 vs 去掉该设施格 | 1934 | 1934 |
| 传送带 vs 普通梯子标记 | 1544 | 1544 |
| 移除native_frame后，带 vs 空 | 2392 | 2392 |
| 移除native_frame后，带 vs 普通梯 | 1848 | 1848 |
| 孤立实际 `_tile`，带 vs 空 | 3584 | 3584 |
| 孤立实际 `_tile`，带 vs 普通梯 | 2868 | 2868 |

`NativeArt.raw(传送带块)` 实际非None，48×48、1608个非透明像素；普通梯子16×16、176个非透明像素。设施实际投影左上角为(614.4,334.4)，缩放1.0667，在画布内。已目视检查 [实际客机画面](conveyor-guest-r3.after.png) 与 [重连画面](conveyor-guest-r3.reconnect.png)，带子可见。

## 首轮像素失败的真实原因

[r1](conveyor-guest-r1.json) 与 [诊断r2](conveyor-guest-r2.json) 的失败完整保留。它们没有移动相机，实际首个设施在第21行，控制画面的投影y=739.2，超出720px画布。因此同帧带/空/普通梯对照全为0像素；不是地形没传，也不是资产缺失、缓存不失效或原生前景覆盖。r2已经证明孤立tile和原图正常、wire与重连状态正常。最终只修审计的显示相机，对照才取得可见像素，**没有进行生产显示修复**。

## 边界与复现

这是内存端点回放的真实生产编解码/发布/合并/绘制链，不连接公网中继、不经过VPN，也没有装载用户现场的自定义材质包。不能据此证明某个云端延迟/重连时序或特定共享皮肤没有问题；异步打包、丢包/拥塞及用户完整地图组合也没有由这一个用例穷举。

测试EXE SHA-256：`d4e578068fbd2bb46cdd37ece52ba76b4329e1fdf06f97e32d31cf3e6eee74a5`。构建：[conveyor-guest-build-r4.log](conveyor-guest-build-r4.log)，执行：[conveyor-guest-r3.log](conveyor-guest-r3.log)。仓库根目录、独立 `PVP_USERDATA`、SDL video/audio dummy、`PVP_CAPTURE_CPP_TRACE=1`，运行 `pvp742_conveyor_guest_display_audit.exe <输出前缀>`。

