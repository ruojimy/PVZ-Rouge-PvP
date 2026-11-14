# 传送带僵尸正常部署与合作出生复查

2026-11-14。针对再次反馈“传送带不会搭”，补查原专项没有覆盖的入口。本轮只新增 [pvp742_conveyor_deployment_audit.cpp](../../src/uitools/pvp742_conveyor_deployment_audit.cpp)，生产源码零修改；没有操作用户对局、存档或活跃窗口。

## 已取得的结果

最终 [conveyor-deployment-r2.json](conveyor-deployment-r2.json) 为10/10通过、exit0。没有复现正常部署或合作出生导致的“不架设”，所以本轮没有借此声称修复了一个新根因，也没有调整架设条件或特殊移动规则。

| 真实入口 | 实际出生与过程 | 结果 |
| --- | --- | --- |
| Room.command，梯子僵尸，attack/follow/rally | Room命令先部署脑光墓碑，再明确选墓碑正常部署；出生x1986/y960、出场400、手持梯子250；第11个采样room tick自然到出场500 | 三种指令均在采样tick34搭普通梯，19行41列、belt=false |
| Room.command，传送带僵尸，attack/follow/rally | 同上；本体仍是梯子模板，但card/content正确为传送带，75血、手持250，未改被测单位位置/出场/装备 | 三种指令均在采样tick34搭传送带，19行41列、belt=true |
| 正常部署后实际魅惑菇转换，梯/带各一项 | 通过Room.command将魅惑菇部署到合法19行41列；僵尸自然完成入场并啃咬；采样tick11观察到魅惑 | 两项均在采样tick72搭建，普通梯/传送带类型分别正确 |
| 实际Room._start_pve，第10天、原pool/RNG/plan | 自然生成u8传送带，首次观察x1114.5152/y960、出场400、81血、手持250；不重放出生、不改该单位状态 | 累计1170room step后19行41列出现实际belt |
| 隔离的实际生产Director出生链 | 从真实第10天cold导出保留传送带的合法pool项，只在夹具缩成单卡pool、零时刻225预算一单位计划；原ColdAdmission入场与配置保持 | 采样tick121搭belt；不把受控计划当原随机合作整局 |

以上tick是0起的采样编号，不能当成绝对墙钟时间。

合作原pool场景为了不让先来的40个背景单位占满预算，夹具把72个非传送带背景对象HP置0，促使原Director继续其后续波次。原随机pool、计划、种子不变，75次出生明细保存；其中实际传送带出生1次。**这证明实际自然出生链可架设，不是未经干预的完整合作对局稳定性证明。** 被测传送带没有被改位置、出场、手持、HP或魅惑。

受控地图为24行、72列、底面20行、42–47列四格高台；英雄放在对应目标位置，资金和初始冷却由夹具准备。正常部署分支使用真实Room.command准入、实际资源/冷却扣除和出生登记，没有直接调用Session.spawn代替部署。attack/follow/rally通过实际指令形成，魅惑来自真实魅惑菇啃咬。

## 与原专项的区别

原 `natural_wall_build_*` 是Session.spawn后fixture_place_zombie并将出场写成500，证明的是“已经入场的正确实体遇到指定墙体时能架设”。本次验证了：

- Room.command从墓碑部署，会先生成出场400的单位，之后自然走完整入场；实际card/content和手持类型没有丢。
- 正常指挥、跟随、集结及真实魅惑都能够在当前指定几何下走到原架设分支。
- 合作Director的spawn_wave_zombie进入同一ColdAdmission/Content配置链，实际传送带仍保留梯子模板+传送带content及手持。

架设生产入口仍为 `ZombieMotion::chase`：向上寻路、跳跃cd=0、原梯子适用条件、下方非空且当前位置为空，并且手持仍为梯子。它不是“任意遇墙就强行造设施”。`ContentParticles::observe → ContentZombies64::tag_belt` 在原架梯子时识别传送带身份，设置该格belt并发布地形。没有将所有僵尸或所有地形都强制改为可架设。

本次正常Room分支直接核验原生地形块/标记；隔离Director分支另核验公开map_tiles中的native belt。没有重新做设施在每个皮肤下的像素可见性，也没有重演真实云端客机地形更新传播。因此若用户“看不到搭建”，显示/共享地形与模拟未搭仍需分开诊断。

## 首轮失败保留及更正

[conveyor-deployment-r1.json](conveyor-deployment-r1.json) 原始失败没有删改：

1. 魅惑菇用y960落到土格，被真实准入拒绝“此处不符合原版种植条件”；最终改为该空格中心y936，之后真实转换通过。没有跳过拒绝结果。
2. 合作第9天原pool没有抽到传送带。进一步读原规则发现 `COOP_TIER_UNLOCK_DAY[2]=10`，第9天仅对梯子有提前加入的特例，传送带不能自然进入该pool。最终测试改第10天；不能把第9天无该卡说成生产没有配置它。

第9天旧池和1200/1800等有限观察失败仅代表当时覆盖未取得。最终所有成功/失败命令结果、出生、轨迹、设施位置保留在JSON/sidecar；未通过吞异常或改战斗条件让测试假绿。

## 证据与复现

- [最终聚合报告](conveyor-deployment-r2.json)、[日志](conveyor-deployment-r2.log)。同名前缀的中文sidecar保存8组正常部署轨迹。
- [实际合作原pool出生明细](conveyor-deployment-r2.json.natural-coop.json)。
- [隔离生产Director计划](conveyor-deployment-r2.json.isolated-director.json)。
- 构建记录：[r1](conveyor-deployment-build-r1.log)、[r2](conveyor-deployment-build-r2.log)。未改生产模块。
- 测试EXE SHA-256：`9fa1903f052ca4f67d1b25db5308dafa58910f72ba27f7135e0c68d2a28e6798`。这是本次审计EXE的哈希，不是用户活跃正式游戏EXE的直接实测。

运行：仓库根目录、SDL video/audio dummy，独立 `PVP_USERDATA`，`PVP_CAPTURE_CPP_TRACE=1`，执行 `pvp742_conveyor_deployment_audit.exe <output.json>`。

仍未覆盖用户当时的完整地图状态、设施/壳占格、各类控制状态及高密度组合；未找到新生产根因。不能用这10项通过否认现场反馈，也不能为未复现的问题擅自重写寻路。

