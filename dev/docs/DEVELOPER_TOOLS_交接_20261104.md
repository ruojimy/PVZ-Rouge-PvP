# PvP72 开发者工具扩展交付

工具目录：C:\Users\xiech\Downloads\PVZ_rougePvP_native\developer-tools

工具ZIP：PvP72-Developer-Tools-1.0.0-20261104.zip，177725字节（173.6KiB），40文件。

SHA256：`e38f9e1ffc08b8481936dcc0f77038dddaa058484569ec387aea4a177cce5154`

主来源为PvP71开发者包与发布包的1864项差集，主ZIP中SKILL.md=0。另找回v1.5.0.1的4个真实skills（12配套文件）。本包将开发者额外内容整理为10个工作流入口，外加这4个旧技能；共14入口，7项工作流完成实际适配和端到端，7项明确保留源码依赖。原4项自定义植物/僵尸/Boss/模式只有源码路线文档，完整功能迁移=0，不能说全部技能都已迁移。

已运行：目标游戏actual_card规则/卡池导出（232项，区分原模板与当前值，支持昼夜/秘籍）、原生地图MapStore/房间/战斗、跨进程回放终点校验、独立relay和真实原生主客机、正式入口smoke、真实短诊断、允许清单/哈希/APK本地检查。

最终ZIP独立解压，在含中文/空格的短路径和无关cwd中执行32/32项检查通过；18项原生阶段门禁、14项技能格式检查通过。包括非法地图/重复ID、回放终点和版本、协议/版本/整数范围、错误参数、已有响应保护、文件篡改和额外文件拒绝。检查24份实际Python路径记录，目标游戏旁无源码，主EXE不导入Python DLL，游戏目录内Python生产模块为0。未声称完整系统I/O跟踪或全量旧套件通过。

配套候选：PvZ-PvP-Native-20261104-devtools-api1-r1.zip，166222181字节，SHA256 `5971e50439cc875040cd60fc5fb5f1c8cda2e4e82e9cc0a01c1c09819d9d5300`。由正式Windows PvP72 r1的允许文件清单组成，只替换主EXE、重建校验和并加候选说明；游戏资源全部逐字节一致。EXE SHA256 `1fb0fd2cb2f7dd12011c0f81b86385ac1ade1a5493aad19e5edb1e9bf76fd0c2`。开发接口标识native-devtools.1/API1，BUILD仍为1.6.0.72-native.20261104，规则/卡池哈希和联机协议保持原值。完整资源/主程序不在工具扩展ZIP中。

当前正式r1可使用原有smoke/diagnostic；规则导出、地图、回放和relay验收需要上述独立候选。没有覆盖原正式ZIP、APK、发布清单或玩家数据。没有新Android候选、没有占用手机。SDK/NDK/编译器/完整游戏源码和历史测试不随扩展。

本迁移源码仅改main.cpp和CMakeLists.txt，新增app/developer_tools.cpp/.h；有修改前副本与src指纹清单。期间另出现3个uitools审计源文件，保持原样、未纳入迁移和交付。继承的旧套件30FAIL/12ERROR不变，未扩豁免。

证据：C:\Users\xiech\Downloads\PVZ_rougePvP_native\test_results\developer-tools-20261104\final1\summary.json；详细外层哈希/清单验证：PvP72-Developer-Tools-1.0.0-20261104.verification.json。完整对照表和限制位于developer-tools/migration-matrix.json、MIGRATION.md、GAPS.md、VALIDATION.md。

后续从dist中的这份交付报告与verification.json继续。工具扩展与候选均已冻结；若再改源码或运行脚本，使用新版本/新证据目录，不覆盖现有报告。
