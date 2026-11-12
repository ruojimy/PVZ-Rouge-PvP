"""One-task inventory/snapshot; never shipped as a game runtime dependency."""
from pathlib import Path
import collections
import hashlib
import json
import shutil
import zipfile

ROOT = Path(__file__).resolve().parents[2]
E = ROOT / 'test_results/developer-tools-20261104'
OLD = Path(r'C:\Users\xiech\Downloads\PVZ-Rouge-v1.4.8\next-pvp71')
ARCHIVE = OLD / 'dist/PVZ-Rouge-v1.6.0.0-PvP71-开发者包.zip'
PACK = ROOT / 'developer-tools'

def sha(p):
    h = hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda: f.read(1024*1024), b''): h.update(b)
    return h.hexdigest()

def write(p, value):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')

def main():
    E.mkdir(exist_ok=True)
    if not (E/'source-before.json').exists():
        paths = sorted((ROOT/'src').rglob('*')) + [ROOT/'CMakeLists.txt']
        write(E/'source-before.json', {p.relative_to(ROOT).as_posix(): sha(p) for p in paths if p.is_file()})
        for name in ['src/app/main.cpp', 'CMakeLists.txt']:
            dest = E/'source-before'/name
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT/name, dest)
    inv = json.loads((E/'package-inventory.json').read_text('utf8'))
    # Classify every actual additional file. A production module is not a skill.
    for f in inv['extra_files']:
        p = f['path']
        if p.startswith('server/'):
            f['disposition'] = 'portable-service-source; relay_server.py and health.py retained'
        elif p == 'modkit/export_pvp_rules.py':
            f['disposition'] = 'adapted-to-native-runtime-export'
        elif p.startswith('AI/') or p == 'modkit/sync_ai.py':
            f['disposition'] = 'source-required; compiled-native-AI; no Python module import'
        elif p.startswith('tests/') or 'test_catalog' in p or 'run_pvp_' in p or 'pvp_impact' in p:
            f['disposition'] = 'source-required; original test catalog/framework not a portable runtime suite'
        elif p.startswith('cpp_port/'):
            f['disposition'] = 'source-required; compiler/CPython extension and profiling integration'
        elif p.startswith('modkit/android/'):
            f['disposition'] = 'native Android build/source dependency; local APK inspection adapted; no device acceptance'
        elif p.startswith('modkit/tools/'):
            f['disposition'] = 'omitted bundled legacy Python/pygame/runtime; general Python declared separately'
        elif p.startswith('modkit/pvp/') or p.endswith('.pyc') or p.startswith('reverse_engineered/'):
            f['disposition'] = 'game-production-source; excluded; owning native modules used by API'
        elif p.startswith('modkit/') or p == 'rebuild-pvp.cmd':
            f['disposition'] = 'source-required legacy build/package/update; portable integrity audit adapted'
        else:
            f['disposition'] = 'reference/history/data; indexed with hashes, not represented as an executable skill'
    with zipfile.ZipFile(ARCHIVE) as z:
        for f in inv['extra_files']:
            f['sha256'] = hashlib.sha256(z.read(f['zip_entry'])).hexdigest()
    inv['archive_sha256'] = sha(ARCHIVE)
    inv['release_sha256'] = sha(Path(inv['release_archive']))
    write(E/'package-inventory.json', inv)
    PACK.mkdir(exist_ok=False)
    for name in ['relay_server.py', 'health.py']:
        target = PACK/'tools/relay'/name
        target.parent.mkdir(parents=True, exist_ok=True)
        # The bytes from the authenticated source archive, not a possibly drifting checkout.
        record = next(f for f in inv['extra_files'] if f['path'] == 'server/'+name)
        with zipfile.ZipFile(ARCHIVE) as z: target.write_bytes(z.read(record['zip_entry']))
    write(PACK/'tools/relay/config.example.json', {'host': '127.0.0.1', 'port': 24562})
    entries = [
        ('native-export', '规则/卡池导出', ['modkit/export_pvp_rules.py'], 'native-api', '导出运行时 CARDS/RULES/describe，与版本哈希及18血原始土豆地雷核对'),
        ('native-maps', '地图制作、导入和房间消费', ['docs/PVP46_MAP_EDITOR.md','modkit/pvp/custom_maps.py'], 'native-api', '生成底图文档、改名、验证、保存至隔离MapStore并由Room消费；坏出生点拒绝'),
        ('native-replay', '原生回放记录及终点校验', ['modkit/pvp/replay.py'], 'native-api', '原生记录输入、导出、从独立文件重新读取并实际Playback至终点；改终点/版本拒绝'),
        ('native-relay', '独立relay服务与原生客户端', ['server/relay_server.py','server/health.py','docs/SERVER_DEPLOY.md'], 'standalone-python+native-api', '本地标准库relay服务、原生主客机传输双向消息；非法协议拒绝'),
        ('native-acceptance', '正式程序自动验收', ['tests/run_pvp_exe_smoke.ps1'], 'existing-native-cli', '独立解压主EXE --smoke-report；1250tick、native_checks与rematch'),
        ('native-performance', '实际程序性能采样', ['cpp_port/tools/app_frame_probe.py','modkit/android/performance_probe.py'], 'existing-native-cli', '正式主EXE --diagnostic，读取真实PVP72报告；非法场景拒绝'),
        ('native-package-audit', '发布完整性与APK本地检查', ['modkit/verify_pvp_package.py','modkit/android/verify_apk.py'], 'external-data', '允许清单+SHA逐文件；APK ZIP/身份/ABI/ELF页对齐；篡改拒绝'),
        ('native-ai-source', '编译型AI同步', ['modkit/sync_ai.py','docs/AI_ROOM.md'], 'source-required', '需要原生源码/编译器，不能将Python大脑复制进发布包；本轮不声明行为迁移完成'),
        ('native-build-source', '原生构建与发行', ['rebuild-pvp.cmd','docs/PVP69_BUILD.md','modkit/build_pvp71.py'], 'source-required', '独立候选构建只验证本次CLI变更；旧PyInstaller/NDK工具链不随包'),
        ('native-test-source', '按影响范围的回归', ['modkit/run_pvp_affected.py','docs/PVP_TEST_MATRIX.md','modkit/pvp_test_catalog.json'], 'source-required', '保持既有失败和豁免，执行此次接口相关阶段门禁；不声称可在玩家包执行全套源码测试'),
    ]
    rows=[]
    for key,purpose,sources,kind,test in entries:
        rows.append({'name':key,'purpose':purpose,'source_version':'PvP71 developer ZIP','source_paths':sources,'source_hashes':{f['path']:f['sha256'] for f in inv['extra_files'] if f['path'] in sources},'old_dependencies':kind,'migration_plan':kind,'status':'planned','acceptance':test,'documentation_adapted':False,'tool_ran':False,'game_accepted':False,'end_to_end':False,'evidence':[],'limitations':[]})
    legacy=Path(r'C:\Users\xiech\Downloads\PVZ-Rouge-v1.4.8\PVZ-Rouge-v1.4.8\.workbuddy\unpack\旧解包备份-20260904\e2e测试解压-可删\PVZ-Rouge-v1.5.0.1改版-发布包\codex-skills')
    legacy_files={}
    for p in sorted(legacy.rglob('*')):
        if p.is_file():
            relative=p.relative_to(legacy).as_posix()
            legacy_files[relative]={'path':str(p),'sha256':sha(p)}
            dest=E/'original-skills'/relative
            dest.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(p,dest)
    for kind in ['plant','zombie','boss','mode']:
        name='pvz-rouge-add-'+kind
        rows.append({'name':name,'purpose':'旧版新增'+kind,'source_version':'v1.5.0.1 archival extracted release; secondary reference, not PvP71 developer extras','source_paths':[str(legacy/name/'SKILL.md')],'source_hashes':{k:v['sha256'] for k,v in legacy_files.items() if k.startswith(name+'/')},'old_dependencies':'ballistic_inprocess_patch.py globals, monkey patches, native wrappers, PyInstaller rebuild; optional legacy assets','migration_plan':'source-required; trace owning compiled native modules, no replacement data-only skill claim','status':'investigating-source-route','acceptance':'需要按实际新内容设计实现、编译并验证卡池/部署/动画/存档/模式；文档改接不计端到端通过','documentation_adapted':False,'tool_ran':False,'game_accepted':False,'end_to_end':False,'evidence':[],'limitations':[]})
    write(E/'migration-matrix.json', rows)
    write(E/'legacy-skill-provenance.json',legacy_files)
    print(json.dumps({'extra_files':len(inv['extra_files']),'extra_dispositions':dict(collections.Counter(f['disposition'] for f in inv['extra_files'])),'workflow_rows':len(rows),'original_skill_files':len(legacy_files),'primary_zip_skills':len(inv['skill_entries'])},ensure_ascii=True))

if __name__=='__main__': main()
