from pathlib import Path
import json,re
root=Path(__file__).resolve().parents[3];out=Path(__file__).resolve().parent
def read(path):return json.loads(path.read_text('utf8'))
full=read(out/'full-comparison.json');apk=read(out/'delivery/android-package-verification.json');pc=read(out/'delivery/pc-smoke/verification.json')
assert pc['passed'] and apk['passed'] and not full['new_nonpass']
content=f'''# T24 快照排队与高负载联机：r3交付证据

本轮完成原生收包解压、后台打包、逐玩家发送队列和桥接缓冲优化，继续完成完整回归、PC运行验证及ARM64签名包。最终归档与启动器切换结果见 `delivery/local-delivery-verification.json`；若该文件尚未生成，封包/本机切换仍在执行中。神经网络T22保持暂停，实机只在出包后安排。

## 快照打包

`packing-comparison.json` 与 before/after-r2/r3 原始报告：同一300单位真实Room、实际生产SnapshotPackWorker、3个接收者、每臂24任务，A/B/B/A。三接收者每轮平均完成时间由65.68/67.12 ms降到33.52/32.10 ms；内核由17.95/15.65 ms降到7.05/7.11 ms。主线程重获锁P95由8.10/8.86 ms降到0.0008/0.0008 ms，已剔除Windows sleep时间。Private峰值相对暖场增量由22.8/21.7 MiB降到5.2/4.4 MiB。

四臂压缩载荷SHA相同：`cd38967039bdaeac6ecc39d5b1990bfc4a47de02f9a9f3a529681fa94ff4ed44`。后台新路径只接触std字节数据；特殊/无效输入回退原V语义；真实worker容量耗尽时不转为主线程同步压缩。不同时间的测量不是手机FPS、帧率或无限时内存保证。

## 发送排队与实际网络

`final-checks/transport.json` 9/9：地图全量前置、同流替换、普通消息边界、代际取消、调用方修改、容量、清理、慢连接与其它玩家隔离。每次取队列为每个玩家预留至多一帧，适配原生生成器提前展开迭代器的行为；待写缓冲未空时，未编码快照仍可替换。输入和已编码帧不丢弃、不重排。

`tcp-load-r1.json` 对比 `final-checks/tcp-idle.json`：固定真实房间载荷33341字节，2个正常玩家、1个128 KiB/s限速玩家、1个暂停消费5秒的观众，20秒内实际322个快照时刻。单连接应用层已编码待写峰值100882→33611字节（约-67%）。正常玩家各322份快照、40/40输入确认，快照年龄P95约16 ms保持；慢玩家40/40输入确认，快照年龄P95约4.73→4.39秒，仍有明显排队。该峰值不包含系统/代理缓冲，也不表示全部积压只有一帧。

编译器并发占用相同两核的 `tcp-deferred-reserved-contention.json` 保留为CPU争用正确性证据：实际39/39输入确认、待写峰值33567字节；不能与空闲基线直接比较性能。`tcp-snd64-r1.json` 是早先尾部验证器未继续处理主机事件导致的未完成确认，后续修正了测试驱动并保留失败，不计为通过。

`cloud-native/native.json`：生产原生RelayHostTransport/RelayClientTransport，公网私有房间、20秒约5Hz，99/99快照和40/40确认，首次真实解包状态一致；快照年龄P95 124.4 ms、输入RTT P95 138.8 ms。服务端RSS前后25903104字节，房间在TTL后归零，配置未修改。两端同PC；不是双物理机、手机或服务器并发容量验收。

## 回归与发布

- 最终专项：有界解压25/25、发送队列9/9、后台打包与随机数值/错误输入兼容检查通过、客机快照链4/4、应用层刷新A/B通过。结果在 `final-checks/`。
- 最新完整回归：{full['tests']}项/{full['modules']}模块，{full['counts']['PASS']} PASS / {full['counts']['FAIL']} FAIL / {full['counts']['ERROR']} ERROR，missing={full['missing']}，{full['waived']}项精确豁免，{full['unwaived']}项未豁免。没有新增非通过ID；原始42项不重写为通过，`product_acceptance_passed=false`。
- 三模式typed动态门禁通过；源/夹具/EXE无漂移，门禁结束后再核对源与构建。额外冻结vendor、网络生成清单、cpp_tests/app_run/游戏EXE，见 `additional-freeze.json`、`full-comparison.json`。
- PC待交付EXE：`{pc['exe_sha256']}`。从独立发布目录启动普通20单位实际诊断并完成；SDL dummy，仅证明包体运行与数据路径隔离，不是前台FPS验收。
- APK versionCode=1114083，ARM64原生库与候选逐字节一致，assets={apk['assets_verified']}项逐文件核验，CRC及证书连续性通过。APK SHA：`{apk['sha256']}`。不是实机验收。
- 保留原兼容BUILD，未改变规则/卡表；未训练或优化神经网络。带入先前T03生命周期及T05眩晕高度表修复，其历史长测边界保留。

## 剩余边界

极慢链路的多秒排队、正常前台帧率下双端高密度云联机、安卓抓人草高压FPS/温度、观众长时抖动/重连和群友偶发崩溃仍需实测。旧的27项未豁免问题继续在T07跟踪。不能把这次局部效果写成全场景流畅或全部内存问题消失。
'''
(out/'assessment.md').write_text(content,encoding='utf8')
todo=root/'待办清单.md';text=todo.read_text('utf8')
text=text.replace('# 当前待办清单（PvP74.3 r2）','# 当前待办清单（PvP74.3 r3）',1)
status='T24 最新进展：r3完成有界解压、后台无V打包、逐玩家可替换发送队列及TCP/桥接缓冲约束。300单位三接收者打包轮次约减半；实际TCP单连接已编码待写峰值下降约67%，正常玩家延迟保持，极慢链路仍有数秒排队。原生公网私有房间99/99快照、40/40输入确认及清理通过；最新2366项仍为2324 PASS/30 FAIL/12 ERROR，无新增失败ID，15精确豁免、27未豁免，typed三模式通过。PC独立发布目录运行及ARM64签名/资源校验完成；PC/APK/源码归档、正式启动器SHA和存档保护结果以[交付记录](test_results/pvp743/t24-queue-20261116/delivery/local-delivery-verification.json)为准。实机及全产品验收未计通过。详见[本轮评估](test_results/pvp743/t24-queue-20261116/assessment.md)。'
text=re.sub(r'T24 最新进展：[^\n]*',status,text,count=1)
text=text.replace('用r2 APK 1114082重做','出包后用r3 APK 1114083重做')
text += '\n## 2026-11-16 r3网络优化与交付追加\n\n'+status+'\n\nT03引用环与T05内容僵尸眩晕高度表修复已纳入本轮生产构建；此前“正式r2未包含”的记录保留为历史。T01/T02/T04/T06/T08/T09/T17等实机、现场与性能门禁仍开放，T22继续暂停。根目录启动器保留独立存档路径；实际切换结果与最新一组r2备份见交付记录。\n'
todo.write_text(text,encoding='utf8')
handoff=root/'交接_游戏待办与验收_20261115.md'
handoff.write_text(handoff.read_text('utf8')+'\n## 9. 2026-11-16 r3网络与出包接续\n\n'+status+'\n\n网络拥有层新增 `tools/pvp72_sources/network.py`、`relay.py`；`tools/pvp743_network_sources.py`仅生成完整network、Application.publish_network与RelayHostTransport.bridge，保留其它原生适配。跨平台构建前执行`--check`。打包内核位于`src/core/snapshot_json.*`与`src/sim/pvp/hand/snapshot_pack.cpp`，有界解压位于`src/core/snapshot_inflation.*`。不得仅改早期模拟目录。T22暂停；出包后才开展实机，不能把PC dummy诊断当手机或前台FPS验收。\n',encoding='utf8')
print('Release assessment and handoff updated',flush=True)
