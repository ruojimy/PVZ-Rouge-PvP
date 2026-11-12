"""Final receipt; do not rewrite the verified archives or their internal results."""
from pathlib import Path
import hashlib
import json
import zipfile

R=Path(__file__).resolve().parents[2];E=R/'test_results/developer-tools-20261104'
def read(p):return json.loads(p.read_text('utf-8-sig'))
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def write(p,value):p.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf8')

def main():
    final=read(E/'final1/summary.json');candidate=read(E/'candidate-package.json');source=read(E/'source-change-manifest.json')
    assert final['all_passed'] and all(c['passed'] for c in final['cases'])
    assert final['game_sha256']==candidate['exe_sha256']
    assert read(E/'launcher-validation.json')['passed']
    assert read(E/'pvp72-conformance.json')['counts']=={'PASS':18,'FAIL':0}
    own_added={'src/app/developer_tools.cpp','src/app/developer_tools.h'}
    assert set(source['modified'])=={'src/app/main.cpp','CMakeLists.txt'} and not source['removed']
    source['migration_owned_added']=sorted(own_added)
    source['other_additions_not_modified_or_packaged']=[p for p in source['added'] if p not in own_added]
    assert own_added.issubset(source['added'])
    write(E/'source-change-manifest.json',source)
    inputs=read(E/'release-input-fingerprints.json')
    assert all(sha(Path(p))==expected for p,expected in inputs.items())
    toolzip=R/'dist/PvP72-Developer-Tools-1.0.0-20261104.zip'
    unpack=Path(final['tool_source']);manifest=read(unpack/'manifest.json');allow=read(unpack/'allowlist.json')['files']
    with zipfile.ZipFile(toolzip) as z:
        assert z.testzip() is None
        assert set(z.namelist())=={'developer-tools/'+name for name in allow}
        for name in allow:
            assert hashlib.sha256(z.read('developer-tools/'+name)).hexdigest()==sha(unpack/name)
            # The directory delivered beside the ZIP is byte-for-byte the verified one.
            assert sha(R/'developer-tools'/name)==sha(unpack/name)
    forbidden={'src','modkit','reverse_engineered','build','test_results','pvp_userdata','node_modules'}
    assert not any(forbidden.intersection(Path(name).parts) for name in allow)
    assert not any(Path(name).suffix.lower() in ('.exe','.dll','.pyd','.so','.cpp','.h','.apk','.marshal','.pyc') for name in allow)
    rows=read(unpack/'migration-matrix.json')
    assert sum(r['end_to_end'] for r in rows)==7 and len(rows)==14
    receipt={'toolkit':{'version':'1.0.0','directory':str(R/'developer-tools'),'zip':str(toolzip),
                        'bytes':toolzip.stat().st_size,'sha256':sha(toolzip),'files':len(allow),
                        'independently_unpacked':True,'allowlist_and_hashes_verified':True,'no_game_source_or_program':True},
             'provenance':{'primary':'PvP71 developer archive extra files','extra_files':1864,'primary_SKILL_md':0,
                           'recovered_legacy_skills':4,'legacy_version':'v1.5.0.1','workflow_adapters':10},
             'skills':{'packaged':14,'documented':14,'portable_workflows':7,'end_to_end_verified':7,'source_required_only':7,
                       'original_four_fully_migrated':0},
             'candidate':candidate,'acceptance':{'final_checks':len(final['cases']),'all_passed':True,
                       'native_stage_gate':'18 PASS / 0 FAIL','skill_format':'14 PASS / 0 FAIL',
                       'paths_checked':final['path_traces_checked'],'no_source_files_adjacent':final['no_source_files_adjacent'],
                       'runtime_loaded_python_dll':False,'candidate_game_python_files':0,'launcher_verified':True},
             'evidence':str(E),'final_test_report':str(E/'final1/summary.json'),
             'source_change_manifest':str(E/'source-change-manifest.json'),
             'other_source_additions_left_alone':source['other_additions_not_modified_or_packaged'],
             'original_release_hashes_unchanged':True,'new_android_candidate':False,'android_device_used':False,
             'limits':['4 legacy content skills plus AI/full-build/full-test are source-required guides, not completed runtime migrations',
                       'APK inspection is local structural/version checking, not signature/device acceptance',
                       'No Linux systemd/public multiplayer/load/16KiB-page-device verification',
                       'Diagnostic is a short pipeline check, no performance-improvement claim',
                       'Unchanged legacy suite retains30 FAIL/12 ERROR; no raw-result rewriting or waiver expansion']}
    output=R/'dist/PvP72-Developer-Tools-1.0.0-20261104.verification.json';write(output,receipt)
    report=f'''# PvP72 开发者工具扩展交付

工具目录：{R/'developer-tools'}

工具ZIP：{toolzip.name}，{toolzip.stat().st_size}字节（{toolzip.stat().st_size/1024:.1f}KiB），40文件。

SHA256：`{sha(toolzip)}`

主来源为PvP71开发者包与发布包的1864项差集，主ZIP中SKILL.md=0。另找回v1.5.0.1的4个真实skills（12配套文件）。本包将开发者额外内容整理为10个工作流入口，外加这4个旧技能；共14入口，7项工作流完成实际适配和端到端，7项明确保留源码依赖。原4项自定义植物/僵尸/Boss/模式只有源码路线文档，完整功能迁移=0，不能说全部技能都已迁移。

已运行：目标游戏actual_card规则/卡池导出（232项，区分原模板与当前值，支持昼夜/秘籍）、原生地图MapStore/房间/战斗、跨进程回放终点校验、独立relay和真实原生主客机、正式入口smoke、真实短诊断、允许清单/哈希/APK本地检查。

最终ZIP独立解压，在含中文/空格的短路径和无关cwd中执行{len(final['cases'])}/{len(final['cases'])}项检查通过；18项原生阶段门禁、14项技能格式检查通过。包括非法地图/重复ID、回放终点和版本、协议/版本/整数范围、错误参数、已有响应保护、文件篡改和额外文件拒绝。检查{final['path_traces_checked']}份实际Python路径记录，目标游戏旁无源码，主EXE不导入Python DLL，游戏目录内Python生产模块为0。未声称完整系统I/O跟踪或全量旧套件通过。

配套候选：{Path(candidate['zip']).name}，{candidate['bytes']}字节，SHA256 `{candidate['zip_sha256']}`。由正式Windows PvP72 r1的允许文件清单组成，只替换主EXE、重建校验和并加候选说明；游戏资源全部逐字节一致。EXE SHA256 `{candidate['exe_sha256']}`。开发接口标识native-devtools.1/API1，BUILD仍为{candidate['build']}，规则/卡池哈希和联机协议保持原值。完整资源/主程序不在工具扩展ZIP中。

当前正式r1可使用原有smoke/diagnostic；规则导出、地图、回放和relay验收需要上述独立候选。没有覆盖原正式ZIP、APK、发布清单或玩家数据。没有新Android候选、没有占用手机。SDK/NDK/编译器/完整游戏源码和历史测试不随扩展。

本迁移源码仅改main.cpp和CMakeLists.txt，新增app/developer_tools.cpp/.h；有修改前副本与src指纹清单。期间另出现3个uitools审计源文件，保持原样、未纳入迁移和交付。继承的旧套件30FAIL/12ERROR不变，未扩豁免。

证据：{E/'final1/summary.json'}；详细外层哈希/清单验证：{output.name}。完整对照表和限制位于developer-tools/migration-matrix.json、MIGRATION.md、GAPS.md、VALIDATION.md。
'''
    (R/'dist/PvP72-Developer-Tools-交付报告-20261104.md').write_text(report,encoding='utf8')
    handoff=report+'\n后续从dist中的这份交付报告与verification.json继续。工具扩展与候选均已冻结；若再改源码或运行脚本，使用新版本/新证据目录，不覆盖现有报告。\n'
    (R/'docs/DEVELOPER_TOOLS_交接_20261104.md').write_text(handoff,encoding='utf8')
    print(json.dumps({'zip':str(toolzip),'bytes':toolzip.stat().st_size,'sha256':sha(toolzip),'checks':len(final['cases']),'portable_verified':7,'source_required':7,'receipt':str(output)},ensure_ascii=True))

if __name__=='__main__':main()
