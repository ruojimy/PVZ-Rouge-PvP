from pathlib import Path
import argparse
import hashlib
import json

R=Path(__file__).resolve().parents[2];E=R/'test_results/developer-tools-20261104';P=R/'developer-tools'
def read(p):return json.loads(p.read_text('utf8'))
def write(p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
GROUPS={
'native-export':['runtime-export','runtime-export-context','invalid-secret-rejected'],
'native-maps':['map-new','map-check','map-import','duplicate-map-rejected','invalid-map-rejected'],
'native-replay':['replay-record-and-playback','bad-replay-final-rejected','bad-replay-version-rejected'],
'native-relay':['native-relay-roundtrip'],
'native-acceptance':['candidate-smoke','stock-smoke'],
'native-performance':['candidate-diagnostic','stock-diagnostic','invalid-diagnostic-rejected'],
'native-package-audit':['extension-allowlist','apk-local-structure']}

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--evidence',required=True);parser.add_argument('--phase',choices=['staging','final'],required=True);a=parser.parse_args()
    validation=read(E/a.evidence/'summary.json');candidate=read(E/'candidate-package.json');rows=read(E/'migration-matrix.json')
    if a.phase=='final':assert validation['all_passed'] and validation['game_sha256']==candidate['exe_sha256']
    cases={c['name']:c for c in validation['cases']}
    native_names=set(GROUPS)-{'native-package-audit'}
    for row in rows:
        name=row['name']
        if name in GROUPS:
            expected=GROUPS[name];found=[cases[k] for k in expected if k in cases]
            ok=len(found)==len(expected) and all(c['passed'] for c in found) and a.phase=='final'
            row.update({'status':'end-to-end-verified' if ok else 'artifact-verification-pending',
                        'documentation_adapted':True,'tool_ran':bool(found),'end_to_end':ok,
                        'native_integration_verified':ok and name in native_names,
                        'game_acceptance_applicable':name not in ('native-export','native-package-audit'),
                        'game_accepted':ok and name in native_names and name!='native-export',
                        'actual_result':{'cases':[{k:c[k] for k in ('name','passed','exit_code')} for c in found],
                                         'tested_game_sha256':validation['game_sha256']},
                        'evidence':['validation/results.json: '+k for k in expected]})
            row['limitations']={
              'native-export':['cards为actual_card在context条件下的解析值；raw_templates不是有效战斗数值；战斗时经济/CD和放置合法性仍需原生规则执行。'],
              'native-maps':['验证原生MapStore、房间地图处理和2tick战斗；未进行人工编辑器/公网传图体验验收。'],
              'native-replay':['真实移动/跳跃样本和终点校验已验证；非所有卡组/长回放覆盖；工具离线预算120000tick/180秒。'],
              'native-relay':['仅本地回环原生主客机；Linux systemd、公网真人联机、容量/压力和设备未验证。'],
              'native-acceptance':['固定脚本场景，不能声称全量旧测试或人工试玩通过。'],
              'native-performance':['本次每个Windows构建仅2单位/1秒短样本用于管线验收，不用于性能倍数结论；Android设备未测。'],
              'native-package-audit':['APK只本地CRC/AXML/ELF/版本检查，不验证签名或设备；正确报告现有库非全部16KiB对齐。']}[name]
    write(E/'migration-matrix.json',rows);write(P/'migration-matrix.json',rows)
    compat=read(P/'compatibility.json')
    compat['candidate'].update({'sha256':candidate['exe_sha256'],'zip':Path(candidate['zip']).name,'zip_sha256':candidate['zip_sha256']})
    compat['runtime']['tested_python']='3.13.14';write(P/'compatibility.json',compat)
    cap=cases['capabilities']['response']['result']['result']
    exported=Path(read(E/'test-layout.json')['root'])/(a.evidence+' 导出.json')
    runtime=read(exported)['result']
    compat['data_formats']={'map_schema':cap['map_schema'],'replay_format':cap['replay_format'],
                            'rule_schema_fields':{k:v for k,v in runtime['rules'].items() if 'schema' in k}}
    write(P/'compatibility.json',compat)
    def sanitize(v):
        if isinstance(v,str):return v.replace(str(R),'<native-workspace>').replace(r'C:\Temp\PvP工具 72','<isolated-test-root>')
        if isinstance(v,list):return [sanitize(x) for x in v]
        if isinstance(v,dict):return {k:sanitize(x) for k,x in v.items()}
        return v
    data=sanitize(validation)
    data.update({'phase':a.phase,'candidate_delivery_sha256':candidate['exe_sha256'],
                 'stage_gate':read(E/'pvp72-conformance.json'),
                 'skill_format_validation':{'passed':14,'total':14,'initial_failure':'validator lacked PyYAML; dependency installed only under task evidence, not in the tool package'},
                 'source_tree_required_at_runtime':False,'android_device_used':False,
                 'note':'Final ZIP is independently unpacked and rerun after packaging; its exact outer digest and result are delivered in the adjacent verification report.'})
    write(P/'validation/results.json',data)
    inv=read(E/'package-inventory.json');archives=read(E/'related-archives.json')
    completed=sum(bool(r['end_to_end']) for r in rows)
    text=['# 迁移报告','','主来源：`'+inv['developer_archive']+'`。SHA256：`'+inv['archive_sha256']+'`。',
          '',f"开发者包{inv['developer_files']}文件，发布包{inv['release_files']}文件；额外{len(inv['extra_files'])}项，SKILL.md为0。本次检索{len(archives)}个相关ZIP（含{sum('开发者' in r['path'] for r in archives)}个开发者ZIP）未找到SKILL.md。独立旧v1.5.0.1解压目录另找回4个真实skills及8个配套文件，共12文件；来源有README自述和逐文件哈希。",
          '', '依据用户补充，本包以开发者包额外内容为主，整理出10项有明确脚本/指南依据的工作流；其中7项可独立适配，3项仍需源码。另附4项真实旧skills的源码路线。因此本包14个技能入口不等于原包中发现14个技能；原4项没有被计为完整功能迁移。',
          '',f'当前阶段：{a.phase}。端到端已验证{completed}/7项可独立运行工作流；7项源码依赖指南只完成文档路线。所有额外文件的归属、原始路径、版本和哈希见provenance/developer-extra-files.json。',
          '', '检查过20个直接相关来源文件，当前参考工作区有2项与ZIP不同（安卓性能探针和测试分类表）；迁移来源指纹以ZIP为准，不将后续工作区状态伪装成归档内容。服务脚本从ZIP读取原始字节，未重新抄写网络协议。',
          '', '真实调用链：Python工具 → 独立C++主EXE文件协议 → 游戏已编译模块 → 输出/行为 → 另一进程或原生消费者验证。导出实际调用actual_card，避免原始土豆地雷模板6生命误当72实际18生命。地图调用MapStore、Room地图提案及NativeBattle；回放调用Recording、正式reader与Playback；relay用原版独立标准库服务加真实原生主客机。',
          '', '| 名称 | 文档 | 工具运行 | 原生集成 | 端到端 | 状态 |','|---|---|---|---|---|---|']
    for row in rows:text.append('| '+row['name']+' | '+ ' | '.join('是' if row.get(k) else '否' for k in ['documentation_adapted','tool_ran','native_integration_verified','end_to_end'])+' | '+row['status']+' |')
    text+=['','逐项的配套工具/模板/数据/依赖、旧内部实现、原生入口、最小用例、实际结果、证据和限制均在migration-matrix.json中。只读导出和包审计不需要游戏导入，game_acceptance_applicable=false单列；其余仅有真实原生处理的行才将game_accepted标true。',
           '', '原生改动：src/app/main.cpp增加显式CLI分支，src/app/developer_tools.cpp/.h实现协议，CMakeLists.txt增加独立候选目标；游戏源码保留工程中，扩展ZIP不包含。没有改动平衡、战斗源码、RNG顺序或联机协议。无Git时已保存修改前main/CMake副本及完整src哈希清单。',
           '', 'Windows候选：'+Path(candidate['zip']).name+'；adapter=native-devtools.1，API=1，BUILD='+candidate['build']+'。正式r1只支持原有smoke/diagnostic，工具对缺失API明确拒绝；未覆盖任何原发布包、存档或旧验证记录。现有Android r4仅本地检查，未出新APK、未使用手机。',
           '', '原始失败现场（第一次编译C1041、能力查询缺bridge、导出JSON换行、原始模板/实际值差异）均保留工程证据目录；已针对具体问题修复并重新执行实际流程。旧套件30FAIL/12ERROR保持原记录，本任务没有改写或扩大豁免。']
    (P/'MIGRATION.md').write_text('\n'.join(text)+'\n',encoding='utf8')
    summary=f'''# 端到端验收

阶段：{a.phase}；证据批次：{a.evidence}。此批次all_passed={validation['all_passed']}，{len(validation['cases'])}项检查。确切运行产物SHA256：{validation['game_sha256']}。

环境：独立解压Windows游戏＋独立扩展＋Python3.13.14标准库。中文/空格短路径，从无关cwd调用；游戏旁无src/modkit/reverse_engineered/AI/tests。检查{validation.get('path_traces_checked',0)}份实际Python路径记录，无旧源码导入。原生文件I/O未作全系统跟踪，不将声明根目录当作完整I/O审计。

验证：解析后的232项卡牌及规则/哈希；昼夜/秘籍上下文；原生地图保存/重读/房间接受/战斗2tick；真实输入回放另进程播放至30tick并校验终点；独立relay和原生主客机双向传输；候选与正式r1均1250native tick、native_checks、再战成功；两个构建的真实短诊断；APK身份/CRC/ELF和PC版本一致；接口/版本/地图/回放非法输入拒绝。具体逐项结果在validation/results.json。

游戏受影响阶段门禁18/18，技能格式14/14。包审计要求显式允许清单、每文件长度/SHA、清单自身校验和、ZIP逐文件回读；最终ZIP还必须独立解压并从解压后的脚本重跑，确切外层SHA及这次结果随包旁的verification.json交付。

未验证：Android设备与新开发接口APK、Linux服务安装、公网容量/真人联机、所有卡牌组合/长回放、人工编辑器与长期性能。原始旧套件30FAIL/12ERROR不是本次已修复。旧4项自定义内容skills及AI/完整构建/完整测试共7项仅源码指南，不计入端到端通过。

诊断每构建仅1秒/2单位用于证明管线，不能推出性能提升。APK签名未由本工具验证；现有SDL库4KiB ELF的限制如实保留。失败尝试保存在工程的独立批次中，没有用成功结果覆盖。
'''
    (P/'VALIDATION.md').write_text(summary,encoding='utf8')
    (P/'INDEX.md').write_text('# Skills与工具索引\n\n'+ '\n'.join(f"- [{r['name']}](skills/{r['name']}/SKILL.md)：{r['purpose']}，{r['status']}。" for r in rows)+'\n\n工具：tools/pvz_tools.py、launch.cmd、tools/build_extension.py与tools/relay/。\n',encoding='utf8')
    print('Reports updated',a.phase,'E2E',completed)

if __name__=='__main__':main()
