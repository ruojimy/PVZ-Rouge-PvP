# PvP72 开发者工具扩展 1.0.0

这是可选工具扩展。以旧PvP71开发者包额外内容为主来源，工具改接独立C++版；旧包中没有SKILL.md。另找回v1.5.0.1的4个真实skills作为次级源码指南，不能称作PvP71原有skills。

把developer-tools目录放在解压的游戏旁边或里面。需要Windows x64、Python 3.10+标准库；无需旧Python游戏、pip、modkit或编译器。工具不会安装全局skills，不改启动器，不自动覆盖游戏、玩家数据或发布包。卸载时删除developer-tools目录；自行指定的输出与地图另行保留/删除。

```powershell
python -I -X utf8 "D:/游戏/developer-tools/tools/pvz_tools.py" --work "D:/工具输出" list
python -I -X utf8 "D:/游戏/developer-tools/tools/pvz_tools.py" --game "D:/游戏/PvP72" --work "D:/工具输出" capabilities
```

也可运行launch.cmd。输出目录每次生成独立子目录，summary.json记录结果，paths.json记录实际Python文件打开路径、子进程及目标游戏摘要。不要把输出目录设在扩展目录内，否则完整允许清单审计会正确地报告新增文件。路径支持中文和空格；仍须使用较短路径避开游戏已有SDL/MAX_PATH限制。

**游戏最低要求**：smoke、diagnostic使用现有PvP72 Windows r1。export、地图、回放、relay-test需要单独的native-devtools.1候选游戏（同72规则，开发协议1）；它未替换正式r1，未构建Android新接口。没有接口时工具立即报MISSING_NATIVE_API，不启动旧Python游戏或静默降级。精确构建和候选哈希见compatibility.json。

7项可独立运行的工具工作流：native-export、native-maps、native-replay、native-relay、native-acceptance、native-performance、native-package-audit。实际验收结果见VALIDATION.md，不能只凭此索引宣称全部通过。其余7项为源码依赖指南（AI、构建、测试和旧版植物/僵尸/Boss/模式）；它们没有被计为完整功能迁移。

主索引：INDEX.md、migration-matrix.json、MIGRATION.md、GAPS.md。来源及1864个额外文件的归属/SHA见provenance/。sdk/提供文件协议说明与schema。manifest.json为明确允许清单，SHA256SUMS.txt包括清单本身；ZIP外部SHA另随包交付。

示例：先map-new生成地图文件，编辑后map-check，再显式map-import到隔离maps目录；正式玩家地图库必须由使用者明确指定。回放replay-demo会用独立原生进程再播放核验。APK仅本地结构/版本检查，没有签名验证或设备验收；Linux服务部署、公网真人联机和Android实机均未在本任务测试。当前旧套件记录的30FAIL/12ERROR未改写，也未扩大豁免。
