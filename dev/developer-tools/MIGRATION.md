# 迁移报告

主来源：`C:\Users\xiech\Downloads\PVZ-Rouge-v1.4.8\next-pvp71\dist\PVZ-Rouge-v1.6.0.0-PvP71-开发者包.zip`。SHA256：`5380e0ee86d5fcf0600b159603be7110af0d5aff6ba87aa38db2c35f56dc251b`。

开发者包2745文件，发布包881文件；额外1864项，SKILL.md为0。本次检索33个相关ZIP（含17个开发者ZIP）未找到SKILL.md。独立旧v1.5.0.1解压目录另找回4个真实skills及8个配套文件，共12文件；来源有README自述和逐文件哈希。

依据用户补充，本包以开发者包额外内容为主，整理出10项有明确脚本/指南依据的工作流；其中7项可独立适配，3项仍需源码。另附4项真实旧skills的源码路线。因此本包14个技能入口不等于原包中发现14个技能；原4项没有被计为完整功能迁移。

当前阶段：final。端到端已验证7/7项可独立运行工作流；7项源码依赖指南只完成文档路线。所有额外文件的归属、原始路径、版本和哈希见provenance/developer-extra-files.json。

检查过20个直接相关来源文件，当前参考工作区有2项与ZIP不同（安卓性能探针和测试分类表）；迁移来源指纹以ZIP为准，不将后续工作区状态伪装成归档内容。服务脚本从ZIP读取原始字节，未重新抄写网络协议。

真实调用链：Python工具 → 独立C++主EXE文件协议 → 游戏已编译模块 → 输出/行为 → 另一进程或原生消费者验证。导出实际调用actual_card，避免原始土豆地雷模板6生命误当72实际18生命。地图调用MapStore、Room地图提案及NativeBattle；回放调用Recording、正式reader与Playback；relay用原版独立标准库服务加真实原生主客机。

| 名称 | 文档 | 工具运行 | 原生集成 | 端到端 | 状态 |
|---|---|---|---|---|---|
| native-export | 是 | 是 | 是 | 是 | end-to-end-verified |
| native-maps | 是 | 是 | 是 | 是 | end-to-end-verified |
| native-replay | 是 | 是 | 是 | 是 | end-to-end-verified |
| native-relay | 是 | 是 | 是 | 是 | end-to-end-verified |
| native-acceptance | 是 | 是 | 是 | 是 | end-to-end-verified |
| native-performance | 是 | 是 | 是 | 是 | end-to-end-verified |
| native-package-audit | 是 | 是 | 否 | 是 | end-to-end-verified |
| native-ai-source | 是 | 否 | 否 | 否 | source-required-documentation-only |
| native-build-source | 是 | 否 | 否 | 否 | source-required-documentation-only |
| native-test-source | 是 | 否 | 否 | 否 | source-required-documentation-only |
| pvz-rouge-add-plant | 是 | 否 | 否 | 否 | source-required-documentation-only |
| pvz-rouge-add-zombie | 是 | 否 | 否 | 否 | source-required-documentation-only |
| pvz-rouge-add-boss | 是 | 否 | 否 | 否 | source-required-documentation-only |
| pvz-rouge-add-mode | 是 | 否 | 否 | 否 | source-required-documentation-only |

逐项的配套工具/模板/数据/依赖、旧内部实现、原生入口、最小用例、实际结果、证据和限制均在migration-matrix.json中。只读导出和包审计不需要游戏导入，game_acceptance_applicable=false单列；其余仅有真实原生处理的行才将game_accepted标true。

原生改动：src/app/main.cpp增加显式CLI分支，src/app/developer_tools.cpp/.h实现协议，CMakeLists.txt增加独立候选目标；游戏源码保留工程中，扩展ZIP不包含。没有改动平衡、战斗源码、RNG顺序或联机协议。无Git时已保存修改前main/CMake副本及完整src哈希清单。

Windows候选：PvZ-PvP-Native-20261104-devtools-api1-r1.zip；adapter=native-devtools.1，API=1，BUILD=1.6.0.72-native.20261104。正式r1只支持原有smoke/diagnostic，工具对缺失API明确拒绝；未覆盖任何原发布包、存档或旧验证记录。现有Android r4仅本地检查，未出新APK、未使用手机。

原始失败现场（第一次编译C1041、能力查询缺bridge、导出JSON换行、原始模板/实际值差异）均保留工程证据目录；已针对具体问题修复并重新执行实际流程。旧套件30FAIL/12ERROR保持原记录，本任务没有改写或扩大豁免。
