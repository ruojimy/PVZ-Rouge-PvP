"""Write versioned tool-package documentation, schemas and evidence indexes."""
from pathlib import Path
import json
import shutil

ROOT=Path(__file__).resolve().parents[2]
E=ROOT/'test_results/developer-tools-20261104'
P=ROOT/'developer-tools'

def jsonfile(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf8')

def textfile(path,text):
    path.parent.mkdir(parents=True,exist_ok=True);path.write_text(text.strip()+'\n',encoding='utf8')

GUIDES={
'native-export':('导出目标原生版本的规则和卡池','export --output "运行时数据.json"','读取游戏进程运行时 actual_card、RULES、describe、排除项和版本哈希。cards是指定条件下的实际解析值，raw_templates明确只保留基础模板；可传--night及多次--secret，context说明条件。所有数值来自指定游戏，旧 export_pvp_rules.py 中固定的说明文字不再作为72规则依据。输出是分析资料，不是热加载规则补丁。'),
'native-maps':('创建、校验和导入原生自定义地图','map-new --blank --name "我的地图" --output "地图.json"','随后运行 map-check "地图.json"；运行 map-import "地图.json" --store "隔离用户目录/maps" 时必须显式指定目录。原生 validate_document、snapshot_from_document、Room._map_proposal、NativeBattle.step、MapStore.save/load 全链路执行。重复ID拒绝覆盖。默认示例不写玩家存档；真正用于玩家地图库时显式选择其maps目录。'),
'native-replay':('记录和验证实际原生回放','replay-demo --ticks 30 --output "示例回放.json"','演示以真实 NativeBattle 接受移动/跳跃输入并通过 Recording.export 保存。工具另启新进程调用 read_recording 和 Playback，实际步进到终点核对状态哈希。对自己的回放运行 replay-check "回放.json"。离线工具上限120000房间tick/180秒；正常游戏回放上限未修改。版本或终点哈希不符必须失败，不能仅重算JSON摘要。'),
'native-relay':('运行独立relay并验证原生客户端','relay-test','保留旧开发者包 server/relay_server.py、health.py 的原始字节，只用标准库。relay-test 临时监听127.0.0.1随机端口并实际使用原生 RelayHostTransport/RelayClientTransport 双向传输，随后停止服务。长期前台服务：python -I -X utf8 tools/relay/relay_server.py --config tools/relay/config.example.json；健康检查：python -I -X utf8 tools/relay/health.py 127.0.0.1 --port 24562。配置默认仅本机；公网部署需另行配置和实测，不自动安装systemd或修改防火墙。'),
'native-acceptance':('从玩家发布包执行正式入口自动验收','smoke','只调用目标主程序 --smoke-report。证据必须同时满足 passed、native_checks_passed、native_tick=1250、rematched；不以exit=0单独代替。每次显式PVP_USERDATA隔离，真实玩家存档不参与。这是固定脚本场景验收，不是完整旧测试套件，也不是真人试玩。'),
'native-performance':('采集目标程序的实际性能诊断','diagnostic --scene ordinary --units 20 --warmup 1 --seconds 5','只调用真实主程序 --diagnostic，保留原报告和native72元数据。ordinary/mixed/barrage可选，使用显式隔离存档。结果含初始化、设备及桌面负载影响；短样本不用于倍数承诺。PVZ72_RENDER_STATS=1仅在本次诊断子进程启用。Android设备流程没有迁移验收；不自动连接手机。'),
'native-package-audit':('检查允许清单、哈希和原生APK结构','audit --target "developer-tools" --manifest "developer-tools/manifest.json"','audit 对完整允许清单、逐文件长度和SHA256、SHA256SUMS再读校验。apk-inspect "游戏.apk" 校验ZIP CRC、包身份、原生游戏版本JSON、ABI/ELF LOAD段对齐；如传--game还核对PC构建版本。它不验证签名或设备运行，4KiB ELF不会被误报成16KiB兼容。没有构建/签名/安装动作。'),
'native-ai-source':('在原生源码中修改并验证编译型AI','', '源码依赖：旧sync_ai.py是把Python大脑扁平化为rv_*.py；原生运行的是src/ui/gen/pm_rv_*.cpp中的已编译模块，没有Python插件导入入口。本工具包提供规则导出用于分析，但不伪装支持热替换大脑。需单独取得原生工程和编译器，沿既有r22/当前默认入口小改，确认1v1/2v2/合作使用同一摘要并做对应场景验收。固定房间保持既有中立显示。源码工作区不得被本扩展自动查找、导入或同步。'),
'native-build-source':('在独立原生工作区构建候选','', '源码依赖：旧PyInstaller、marshal/字节码采集、python-for-android和旧.pyd流程不能构建独立C++版。实际原生入口是CMakeLists.txt和src；本次添加PVZ_BUILD_DEVELOPER_CANDIDATE选项，单独目标PvZPvPNativeDev。需自行提供VS2022/CMake/原生依赖，串行/MP1构建。扩展不含这些环境、游戏源码或资源。Android仍使用原生android工程与同签名发行流程，本轮不构建/安装新APK。'),
'native-test-source':('在原生源码工作区按影响范围回归','', '源码依赖：旧run_pvp_affected.py依赖tests/与modkit游戏对象，不能复制到玩家包后运行。原生已有cpp_tests/run_cpp_suite和分类门禁，需要源码测试/只读夹具，故不纳入轻量扩展。本次CLI只触及app，执行真实发布入口、协议负控、地图/回放/relay集成和72定向门禁。继承的30FAIL/12ERROR仍保持，不扩大豁免；不能把本包smoke称为全量回归。')}

CONTENT={
'plant':('植物','src/sim/pvp/gen/pm_catalog.cpp → C_NativeBattle::m_spawn/m__configure_plant → src/sim/pvp/gen/pm_native_content.cpp 与 src/sim/gen/原生分支','卡池、费用/CD、原生输入名、部署合法性、动画、攻击实体、秘籍/派生形态和回放均需一致。原生表初始化包含编译分支，不支持复制Python补丁或只改导出JSON。'),
'zombie':('僵尸','src/sim/pvp/gen/pm_catalog.cpp → C_NativeBattle::m_spawn/m__register → pm_native_expansion/pm_plant_zombies 与已编译原生僵尸分支','普通/植物僵尸的卡池、召唤白名单、原生输入名、护甲、魅惑、动画与所有权依赖编译代码。没有已发布的自定义单位插件ABI。'),
'boss':('Boss','src/sim/pvp/gen/pm_catalog.cpp 的 BOSS_NAMES/EXCLUDED/f_allowed → pm_pve/pm_native_battle → 对应原生Boss分支','当前PvP明确阻止Boss进入普通卡池和召唤白名单。旧版Boss桥还依赖单人固定Boss/奖杯/存档状态，不能越过这些限制冒充迁移。本任务没有获准重新设计对战平衡；新Boss需单独的源码功能变更和完整血条/召唤/胜负/存档设计。'),
'mode':('模式','src/sim/pvp/gen/pm_teams.cpp 的 MODES → src/ui/gen/pm_room.cpp 和 pm_app.cpp → pm_pve/pm_coop_progress 与 userdata','现有duel/duo/pve/coop是已编译房间/座位/波次/界面分支。新增模式需要菜单、状态机、存档schema及必要网络版本设计；自定义地图不等同新增模式。')}

def main():
    rows=json.loads((E/'migration-matrix.json').read_text('utf8'))
    details={
      'native-export':('from pvp.catalog import CARDS/RULES/describe; embedded Python game imports','tools/pvz_tools.py export → --developer-tools/export → pm_catalog CARDS/RULES/f_describe','运行时export JSON，版本及规则/卡池哈希'),
      'native-maps':('pvp.custom_maps/maps/native_bridge/Room/NativeBattle and filesystem MapStore','tools/pvz_tools.py map-* → native API → f_validate_document/f_snapshot_from_document/C_Room::m__map_proposal/C_NativeBattle::step/C_MapStore::save/load','地图JSON、原生地图库文件、房间与战斗接受结果'),
      'native-replay':('pvp.replay Recording/Playback/state_hash and NativeBattle','tools/pvz_tools.py replay-* → native API → C_Recording::export/f_read_recording/C_Playback::update','回放JSON、真实输入返回值、终点哈希验证'),
      'native-relay':('server source is standalone standard library; client originally pvp.relay/network','tools/relay/relay_server.py + --developer-tools/relay-probe → compiled C_RelayHostTransport/C_RelayClientTransport','本地监听、健康响应、原生双向payload验证；不记录凭证'),
      'native-acceptance':('old EXE smoke script launches a PyInstaller game, not the native game','tools/pvz_tools.py smoke → actual native EXE --smoke-report','1250tick/部署/结算/再战报告；隔离userdata'),
      'native-performance':('old probes inspect CPython objects, bytecode/core hooks and game modules','tools/pvz_tools.py diagnostic → actual native EXE --diagnostic → run_diagnostic72','真实诊断JSON/计数；不等于长时间性能或设备结果'),
      'native-package-audit':('old APK/package guard requires staging manifests, Python game/core and old layout','tools/pvz_tools.py audit/apk-inspect → stdlib ZIP/SHA256/AXML/ELF readers','允许清单/SHA证据和APK结构；签名/设备不在此工具承诺'),
      'native-ai-source':('sync_ai.py flattens AI/brain Python modules and knowledge; compiled native rv_* cannot import them','独立源码 tools/pvp72_sources/及src/ui/gen/pm_rv_*.cpp，按现有生成归属更新/构建/回归','本轮仅源码指南；未同步/替换AI'),
      'native-build-source':('PyInstaller/marshal/_pvpcore.pyd/Python Android and full build inputs','CMakeLists.txt/PVZ_BUILD_DEVELOPER_CANDIDATE/PvZPvPNativeDev；游戏源码留在工程','本次独立Windows候选；完整开发环境不随工具包'),
      'native-test-source':('tests/, unittest, pvp game objects and catalog plus original/reference evidence','原生源码测试工具/定向conformance；发布包只运行smoke而非冒充完整套件','本次相关原生阶段门禁；保留既有非通过状态')}
    for row in rows:
        if row['name'] in details:
            dep,entry,output=details[row['name']]
        else:
            kind=row['name'].rsplit('-',1)[1];label,route,notes=CONTENT[kind]
            dep='SKILL.md → ballistic_inprocess_patch.py + build_smart_ballistics_exe.py → globals/monkey patches/PyInstaller；开发者包冻结副本为modkit/pvzrouge_runtime_patch_source_20260904.py'
            entry=route+'；同源包装器已编译在src/sim/pvp/gen/pm_patch1501.cpp、pm_original_patch1501.cpp'
            output='仅源码迁移路线；未新增对应内容，未生成虚假功能产物'
        row['old_internal_dependencies']=dep
        row['native_entry']=entry
        row['outputs']=output
        row['supporting_tools']=['tools/pvz_tools.py'] if row['migration_plan']!='source-required' and not row['name'].startswith('pvz-rouge-') else []
        row['templates_and_data']='仅示例请求/启动脚本；规则/卡池/地图schema从目标原生导出，不内置PvP71数值'
        row['runtime_dependencies']='Python 3.10+ standard library and explicitly selected native release' if row['supporting_tools'] else '独立原生游戏源码、构建依赖和受影响回归；不随扩展提供'
    for row in rows:
        name=row['name']
        if name in GUIDES:
            title,command,body=GUIDES[name]
            source_required=row['migration_plan']=='source-required'
        else:
            kind=name.rsplit('-',1)[1];label,route,notes=CONTENT[kind]
            title='在原生源码中新增'+label
            command='';source_required=True
            body=f'这是v1.5.0.1真实技能的源码路线适配，原始技能不在PvP71开发者ZIP中。\n\n真实拥有者：{route}。\n\n{notes}\n\n需要先导出目标版本规则/卡池，设计实际变更并在单独源码工作区实现，再构建独立候选和执行该对象的最小流程。卡池、部署、渲染、伤害/交互、保存重开及未改内容回归都必须有真实证据。本扩展没有新增上述内容，也没有可执行模板；不得把本文适配当作新增功能已可用。旧Python游戏模块、猴子补丁、字节码及完整源码均未打包。'
        state='需要另备原生游戏源码；仅文档路线已适配，未完成对应功能端到端验收。' if source_required else '使用范围与验收状态以migration-matrix.json和VALIDATION.md为准。'
        description=(title+'；需要独立原生源码工作区和编译器，不支持发布包热加载。') if source_required else title+'，调用指定的原生游戏或独立工具并保存验证证据。'
        content=f'''---
name: {name}
description: {json.dumps(description,ensure_ascii=False)}
---

# {title}

{state}

{body}

来源版本：{row['source_version']}。原始路径与SHA见 [迁移对照表](../../migration-matrix.json)，配套接口见 [协议](../../sdk/protocol.md)。
'''
        if command:content+=f'''
在任意工作目录，显式指定游戏与输出目录：

```powershell
python -I -X utf8 "<扩展>/tools/pvz_tools.py" --game "<游戏目录>" --work "<证据目录>" {command}
```

工具不会自动发现开发源码、复制玩家存档或安装全局技能。错误时读取summary.json和paths.json；不得把格式检查成功视为游戏已接受。
'''
        textfile(P/'skills'/name/'SKILL.md',content)
        row['documentation_adapted']=True
        if source_required:
            row['status']='source-required-documentation-only'
            row['limitations']=['原生源码/编译器不随扩展分发；该功能的实际源码变更与完整端到端流程未在本次实施。']
    jsonfile(E/'migration-matrix.json',rows);jsonfile(P/'migration-matrix.json',rows)
    inv=json.loads((E/'package-inventory.json').read_text('utf8'))
    # Full item-by-item inventory, but no original production file bodies.
    jsonfile(P/'provenance/developer-extra-files.json',inv)
    for name in ['related-archives.json','legacy-skill-provenance.json','source-checkout-comparison.json']:
        shutil.copy2(E/name,P/'provenance'/name)
    jsonfile(P/'compatibility.json',{
        'toolkit_version':'1.0.0','skill_versions':{r['name']:'1.0.0' for r in rows},
        'developer_protocol':1,'game_network_protocol':1,'adapter_id':'native-devtools.1',
        'game_builds':['1.6.0.72-native.20261104'],
        'stock_windows_r1':{'supported':['smoke','diagnostic','apk-inspect','audit'],'developer_api':False},
        'separate_candidate_required_for':['export','map-new','map-check','map-import','replay-demo','replay-check','relay-test'],
        'candidate':{'build':'1.6.0.72-native.20261104','adapter':'native-devtools.1','developer_api':1,'sha256':'pending-validation'},
        'runtime':{'python':'>=3.10','modules':'standard library only','tested_python':'3.13.14','platform':'Windows x64; service source is cross-platform, Linux not exercised'},
        'android':{'tested_package':'org.pvzrouge.pvzpvpnative','tested_version_code':1104003,'local_inspection_only':True,'device_tested_this_task':False,'developer_api_built_for_android':False},
        'unsupported':['Python game module hotloading','unit/Boss/mode plugins','AI hotloading','old PyInstaller builds','public multiplayer/device acceptance','16KiB-page compatibility guarantee']})
    textfile(P/'sdk/protocol.md', '''
# 原生开发接口 v1

独立候选提供：`PvZPvPNative.exe --developer-tools <request.json绝对路径> <response.json绝对路径>`。Windows原版r1没有此接口；不能只复制工具就获得接口。新候选不修改BUILD/规则哈希/卡池哈希/联机协议，另以adapter=native-devtools.1和developer_api=1标识；兼容性必须核对完整identity。

请求外层字段：protocol=1、operation、arguments对象；除capabilities外还须提供上次capabilities响应中的完整expected identity。未知字段/操作拒绝。响应为protocol、ok、operation、identity、result或error.code/message。退出0成功；2参数/协议/版本失败；3原生游戏拒绝；6输出文件存在或写入失败。禁止覆盖已有响应、回放或同ID地图。响应原子写入，失败的.pending需人工检查，不自动覆盖。

capabilities返回操作列表、游戏导出的地图schema/调色板/地图列表/回放格式，不携带自定义插件能力。export从运行时actual_card/RULES/describe导出JSON；cards为已解析值，raw_templates仅为基础模板，context标明night/secrets；不把这些JSON当可写配置或战斗时动态资源/CD的完整枚举。map-new调用真实生成器，map-check调用原生验证、房间地图提案、构建战斗并步进2tick。map-import再使用原生MapStore保存和重读，目录必须显式给出。replay-demo仅是有真实输入的短样本，replay-check调用正式reader/Playback到终点，而非JSON摘要比较。relay-probe仅连接127.0.0.1的指定临时服务，使用真实原生主客机双向传输。

错误CLI参数数量退出2并打印用法，不进入游戏界面。输出路径由用户或调用工具明确指定；不自动寻找源码、手机、玩家存档或公网服务器。Python进程实际打开路径和子进程命令记录在paths.json；原生数据/资源根目录同时列出。物理隔离发布包验收加静态调用链核验排除了旧Python游戏依赖；未声称收集了全系统文件I/O跟踪。

输入上限：请求16MiB、回放64MiB/120000房间tick、离线回放180秒、relay验收15秒；其余地图约束由原生schema给出。未知/非法输入必须返回错误，不能静默忽略。此接口是本地文件协议，未新增网络协议。
''')
    jsonfile(P/'sdk/request.schema.json',{'$schema':'https://json-schema.org/draft/2020-12/schema','title':'PVZ native developer request v1','type':'object','additionalProperties':False,'required':['protocol','operation'],'properties':{'protocol':{'const':1},'operation':{'enum':['capabilities','export','map-new','map-check','map-import','replay-demo','replay-check','relay-probe']},'arguments':{'type':'object'},'expected':{'type':'object','description':'Exact capability identity including build, rule/catalog hashes, adapter and protocol; required except for capabilities'}},'description':'Operation-specific fields and limits are enforced by native API and documented in protocol.md.'})
    textfile(P/'README.md', '''
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
''')
    textfile(P/'GAPS.md','''
# 明确缺口与源码依赖

| 项目 | 原因、已调查入口与下一步 | 完成级别 |
|---|---|---|
| 旧新增植物/僵尸 | 运行时猴子补丁改为已编译catalog、原生生成/行为/动画分支。需具体内容需求、独立源码候选及卡池/部署/动画/战斗/保存验收；不提供假热加载。 | 仅文档路线适配 |
| 旧Boss | PvP的BOSS_NAMES/EXCLUDED和f_allowed明确拒绝Boss。单人Boss桥/奖杯/存档不能直接复用；需独立源码功能设计，不能在工具迁移时擅改PvP规则。 | 未实现功能迁移 |
| 旧新增模式 | MODES、房间/座位/菜单/存档/波次均编译，新增模式需要源码及必要协议设计；地图不是模式。 | 仅文档路线适配 |
| AI热更新 | sync_ai.py生成Python模块；原生AI已编译，无已发布插件ABI。需独立源码工作区更新并验证1v1/2v2/合作固定房。 | 源码依赖 |
| 完整测试与旧构建/发布 | 旧测试对象、字节码、PyInstaller/.pyd/NDK环境不应进轻量包。原生工程保留完整回归入口和本次候选源码；工具只提供正式入口smoke/诊断/完整性。 | 源码依赖，不冒充全量 |
| Android开发API | 本次只本地检查现有r4 APK；未编译含新API的Android候选，未使用手机。 | 未设备验收 |
| 服务部署/公网/16KiB设备 | 本地relay原生往返不能代替Linux systemd、公网容量、真人联机或16KiB页设备测试；现有4KiB SDL ELF仍如实报告。 | 未验证 |

本次没有实现任意单位/AI/模式插件SDK，因为这样的ABI必须同时定义确定性状态、回放、原生绘制和联机兼容约束；只暴露已有真实能力的最小文件CLI，不将任意内存写入接口伪装成稳定SDK。上述7项源码指南保留在skills目录供拥有独立源码的人使用；全部end_to_end=false。
''')
    textfile(P/'INDEX.md','\n'.join(['# Skills 与工具索引','']+[f"- [{r['name']}](skills/{r['name']}/SKILL.md)：{r['purpose']}（{r['status']}）" for r in rows]+['','工具：tools/pvz_tools.py、launch.cmd、tools/relay/relay_server.py、tools/relay/health.py、tools/relay/config.example.json。']))
    textfile(P/'THIRD_PARTY_NOTICES.txt','''
来源：用户提供的PvP71开发者ZIP；准确路径、SHA256与各文件来源在provenance/。
tools/relay/relay_server.py与health.py保留来源归档字节；源归档没有随附明确许可文本，不为其虚构MIT/Apache授权。使用和再分发须遵守原权利人的许可。
适配工具和文档为本任务产物。游戏程序、游戏生产源码、图像/音频、SDL及编译环境不随此扩展分发，沿用目标游戏自己的许可与版权。
Python是外部通用依赖，其许可证由解释器发行版提供；本包不内置解释器。
''')
    textfile(P/'VALIDATION.md','# 验收记录\n\n尚在执行。最终结果与失败现场将在打包前更新。')
    print('Authored 14 skills, 7 source-required guides; no portable workflow pass claimed yet.')

if __name__=='__main__':main()
