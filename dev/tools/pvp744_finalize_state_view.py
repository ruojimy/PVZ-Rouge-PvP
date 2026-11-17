"""Freeze the checked local state/HUD candidate, serial A/B evidence and sources."""
import difflib
import hashlib
import json
from pathlib import Path
import shutil
import zipfile

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'test_results/pvp744/state-view-20261116'


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def read(p):
    return json.loads(p.read_text('utf8'))


def write(p, value):
    p.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', 'utf8')


def saves():
    folder = ROOT/'PVZ_rougePvP_native/pvp_userdata'
    return {p.relative_to(folder).as_posix(): sha(p) for p in folder.rglob('*') if p.is_file()}


def main():
    before = read(OUT/'before.json')
    assert saves() == before['saves'], 'User save changed during this round'
    official = ROOT/'PVZ_rougePvP_native/PvZPvPNative.exe'
    assert sha(official) == before['official']
    checks = read(OUT/'checks/summary.json')
    assert checks['completed'] and all(x['checks'] == x['passed'] and x['exit_code'] == 0 for x in checks['results'])
    total = sum(x['checks'] for x in checks['results'])
    runs = {name: read(OUT/name/'summary.json') for name in ('ab', 'ba', 'wall-ab', 'profile')}
    exe = ROOT/'build/app-typed72-v2/Release/pvp743_pacing_lab.exe'
    expected = sha(exe)
    for name, run in runs.items():
        assert run['completed'] and all(x['equal_state_rng'] for x in run['comparisons'].values())
        for p in (OUT/name).glob('*/process.json'):
            assert read(p)['exe_sha256'] == expected, str(p)
        for r in run['results']:
            report = read(OUT/name/(r['scene']+'-'+r['arm'])/'report.json')
            assert report['backend_audit']['local_frame']['frames'] > 0
            if name != 'profile': assert report['backend_audit']['performance']['function_profile'] == {}
            if r['arm'] == 'stateview': assert report['backend_audit']['state_view']['builds'] > 0
    anchors = {r['scene']: r for r in read(ROOT/'test_results/pvp744/presentation-20261116/reverse-ab/summary.json')['results'] if r['arm']=='localframe'}
    for name in ('ab', 'ba'):
        for r in runs[name]['results']:
            if r['scene'] in anchors:
                assert all(r[k] == anchors[r['scene']][k] for k in ('state', 'rng', 'tick', 'native_ticks')), 'Previous candidate state drift'
    candidate = OUT/'candidate'
    candidate.mkdir(exist_ok=True)
    target = candidate/'PvP744StateViewCandidate.exe'
    shutil.copy2(exe, target)
    for p in exe.parent.glob('*.dll'):
        shutil.copy2(p, candidate/p.name)
    assert sha(target) == expected
    rel = target.relative_to(ROOT).as_posix()
    for name, arm in [('体验性能候选.cmd', 'stateview'), ('体验性能对照.cmd', 'localframe'), ('体验刷新复用.cmd', 'view')]:
        text = '@echo off\nsetlocal\ncd /d "%~dp0"\n'
        text += f'python -X utf8 tools/pvp744_scheduler_lab.py --exe "{rel}" --out auto --scenes grabber --arms {arm} --interactive --seconds 180\npause\n'
        (ROOT/name).write_bytes(text.replace('\n', '\r\n').encode('utf8'))

    labels = {'localframe': '原 JSON 路径', 'stateview': '直接状态投影'}
    scenes = {'ordinary': '普通20', 'barrage': '弹幕240', 'grabber': '抓人草120', 'mixed': '混合120'}
    lines = ['# 新状态与 HUD 提取优化验收', '',
        f'2026-11-16。本机单位提取已绕过逐单位 JSON 中间层，HUD 统计随同一次发布提取。{total}/{total} 项定向检查通过。以下数据来自 Windows 两逻辑核、BelowNormal、SDL dummy 完整软件绘制循环，不是物理屏幕 FPS，也不是 Android 结果。正式版本仍为 PvP74.3 r3。', '',
        '## 架构变化', '',
        '旧路径每个新状态都会逐单位解析完整卡牌，生成 ordered JSON，转换成普通 JSON，再递归生成 UI 的 V 字典。原有卡牌 V 缓存发生在 JSON 构造之后，因此不能省掉前面的重复工作。', '',
        '新路径仍以生产 Session 的 RoomPublicState 为唯一发布事实源：同步读取已发布单位，直接生成独立 V 行；相同所属方、卡种、滚桶形态的卡牌每个新状态只解析一次。去重只限当前发布，避免秘籍、昼夜、复制目标变化后使用陈旧描述。旧 JSON 路径保留为开关对照及逐字段差分基准。', '',
        '```mermaid', 'flowchart LR', '  P[类型化已发布单位] --> U[直接生成 UI 单位行]', '  P --> H[同次遍历提取 HUD 计数]', '  U --> L[本机视图与插值]', '  H --> L', '  M[玩家与其余元数据] --> J[保留 JSON 转换]', '  J --> L', '```', '',
        '- 墓碑数、受损墓碑数、稻草人数随单位投影生成；HUD 价格和反馈读取本机摘要，非本机视图继续原扫描逻辑。植物方反馈省去不会显示的墓碑扫描。',
        '- 失效沿用既有状态版本，不以 tick 当缓存键；同 tick 的资源、指令、记录写入也会失效。公开读取先生成快照时，直接复用其单位行，只补提取一次 HUD 摘要。',
        '- 借用的类型化引用只在同步函数内读取，不跨 step 保存；UI 行独立持有值。公开深拷贝契约、网络隐私、回放字段、250Hz、RNG、机制和材质保持原路径。私有 `_local_hud` 不进入公开快照。',
        '- `PVP744_STATE_VIEW=1` 只在本机呈现作用域开启，默认关闭。玩家、放置、音频等元数据仍经过 JSON，单位 UI 行仍会构造和复制；这不是完整无 JSON 渲染器，也没有引入模拟线程。', '',
        '## 同等逻辑工作量对照', '',
        '同一 EXE 切换 stateview/localframe；两臂均保留前轮可见帧延迟投影、插值修复与相同调度。植物方反馈省去无用扫描也是两臂共有变化，下面没有单独量化它的收益。固定0.20倍率，seed301，暖场150 room tick，测90 room tick，即750 native tick。函数计时关闭；原画、原像素与完整绘制，不自动减绘。AB 与 BA 交换高负载执行顺序。', '',
        '| 批次 | 场景 | 路径 | 呈现循环/秒 | 新状态刷新均值 ms | 服务间隔 P95/P99 ms | 绘制均值 ms |',
        '| --- | --- | --- | ---: | ---: | ---: | ---: |']
    for name in ('ab', 'ba'):
        for r in runs[name]['results']:
            p = r['phases']
            lines.append(f"| {name.upper()} | {scenes[r['scene']]} | {labels[r['arm']]} | {r['fps']:.2f} | {p['refresh_advanced']['mean']:.2f} | {p['frame_interval_actual']['p95']:.2f}/{p['frame_interval_actual']['p99']:.2f} | {p['render']['mean']:.2f} |")
    lines += ['', '各组终态、RNG、room tick、native tick 均相同；两高负载场景还与前轮冻结候选的同场景终态/RNG证据一致。平均呈现率高于30不等于稳定30；服务间隔的尾部仍需单独看。短时 PC 诊断不能外推为所有设备和场景的收益。', '', '## 自动倍率对照', '',
        '暖场5秒后测45秒，模拟推进量随控制器不同，不据此比较等量模拟吞吐。', '',
        '| 路径 | 呈现循环/秒 | 服务间隔 P95/P99 ms | 模拟/墙钟 | 最后倍率 | >100ms工作帧 |',
        '| --- | ---: | ---: | ---: | ---: | ---: |']
    for r in runs['wall-ab']['results']:
        p = r['phases']; long_frames = next(v for k,v in r['long_frames'].items() if float(k)==100)
        lines.append(f"| {labels[r['arm']]} | {r['fps']:.2f} | {p['frame_interval_actual']['p95']:.2f}/{p['frame_interval_actual']['p99']:.2f} | {r['ratio']:.3f} | {r['last_scale']:.3f} | {long_frames:.2f}% |")
    lines += ['', '## 成本归因', '',
        '独立开启 PVP741_PROFILE 的抓人草诊断批次用于归因，不混入上面的性能统计。各函数计时含嵌套调用，不能直接相加；StateView 三阶段互不重叠，只计新状态。TypedBattle::refresh 还包括静止复用，其调用次数不同，均值不能当作新状态耗时。', '',
        '| 路径 | 计时点 | 次数 | 每次均值 ms |', '| --- | --- | ---: | ---: |']
    profiles = {}
    for arm in ('localframe', 'stateview'):
        report = read(OUT/'profile'/('grabber-'+arm)/'report.json')
        backend = report['backend_audit']; profiles[arm] = backend['state_view']
        functions = backend['performance']['function_profile']
        for key in ('StateView::metadata_json', 'StateView::unit_values', 'StateView::metadata_values', 'TypedBattle::refresh'):
            v = functions[key]
            lines.append(f"| {labels[arm]} | {key} | {int(v['calls'])} | {v['total_ms']/max(1,v['calls']):.3f} |")
    v = profiles['stateview']
    lines += ['', f"诊断全程（含暖场）直接投影 {v['units_projected']} 条单位行，解析 {v['cards_resolved']} 次卡牌，构建 {v['builds']} 次新状态；计数是执行证据，不是内存节省量。", '',
        '## 正确性及交付范围', '',
        f'{total}项定向检查包括原82项、新状态6项、启用新路径的像素5项、调度5项与网络11项。新状态检查含32组字段组合对照、四对局模式、同tick资源变化、静止复用、旧视图保持、公开深拷贝、HUD价格与反馈。像素检查覆盖密集抓人草、层级、缩放、裁剪、插值偏移、倒下英雄、材质替换和恢复。', '',
        '第一次检查暴露“公开读取先生成快照”缺少本机 HUD 摘要；已修复并重跑全部109项。原失败记录保留。完整2366项产品回归未重跑，历史27项未豁免未关闭；Android、新候选公网、长时内存及用户按键手感仍待验收。', '',
        '根目录“体验性能候选.cmd”打开本轮冻结候选，“体验性能对照.cmd”打开同一 EXE 的原 JSON 路径；两者都有上一轮帧优化。“体验刷新复用.cmd”保留更早的仅视图复用对照。每次运行使用独立 manual-* 测试数据，自动布置抓人草120、双方足额资源、180秒；规则及冷却不变。', '',
        f'候选 EXE SHA-256：`{expected}`。正式 EXE 和 {len(before["saves"])} 个用户数据文件的 SHA-256 保持不变，正式入口仍指向 r3。无新APK。', '',
        '源码归档是本工程及冻结生产阶段上的补丁，不是独立开发包。生产组合层修改在 build/typed72-match-v1/snapshot_layer.inc，由生成器同步进 composition；未改只读参照。最新回退源文件位于 backup-latest/performance-before.zip，前轮候选保留为测试证据；历史 t03-source 清理仍受此前审批拒绝限制，本轮未重试删除。', '',
        '下一处应继续量化玩家/放置元数据 JSON 与 snapshot 深拷贝的占比；当前结果不足以批准跨线程共享 Session。T01/T02/T24继续开放，T22神经网络AI仍暂停。', '',
        '复跑：tools/pvp744_verify_scheduler.py；tools/pvp744_scheduler_lab.py --arms localframe stateview。原始结果在 ab、ba、wall-ab、profile、checks 子目录。']
    (OUT/'assessment.md').write_text('\n'.join(lines)+'\n', 'utf8')
    handoff = ROOT/'交接_性能与交互体验优化_20261116.md'
    text = handoff.read_text('utf8')
    text = text.replace('最新续建结果见第10节及[本机呈现候选验收](test_results/pvp744/presentation-20261116/assessment.md)。第9节保留前一候选的历史状态。',
        '最新续建结果见第11节及[新状态与HUD候选验收](test_results/pvp744/state-view-20261116/assessment.md)。第9、10节保留前两轮候选的历史状态。')
    heading = '## 11. 新状态与 HUD 提取架构优化'
    if heading not in text:
        text += '\n'+heading+'\n\n本机新状态直接从 RoomPublicState 生成 UI 单位行，卡牌按当前发布去重；墓碑和稻草人 HUD 统计在同次遍历提取。109/109定向检查通过，完成同构建 AB/BA、自动倍率和独立函数计时。正式r3与用户存档保留，高负载稳定30FPS、Android和人工手感门禁不关闭。详见[验收、边界与原始测试入口](test_results/pvp744/state-view-20261116/assessment.md)。\n'
    handoff.write_text(text, 'utf8')
    todo = ROOT/'待办清单.md'; text = todo.read_text('utf8')
    heading = '## 2026-11-16 新状态与 HUD 提取续建'
    if heading not in text:
        text += '\n'+heading+'\n\n新状态单位 JSON 中间层已在本机候选路径移除；卡牌单次发布去重、HUD计数融合提取，109/109定向检查通过。前后同构建AB/BA、自动倍率、函数计时已归档。玩家/放置等其余元数据仍经JSON；完整typed渲染、Session worker、Android和人工手感未完成。T01/T02/T24继续开放，T22继续暂停。详见[状态投影验收](test_results/pvp744/state-view-20261116/assessment.md)。\n'
    todo.write_text(text, 'utf8')

    old = read(ROOT/'test_results/pvp744/presentation-20261116/candidate/manifest.json')
    files = set(old['source_hashes']) | set(before['files']) | {'CMakeLists.txt',
        'src/sim/typed72_app/unit_projection.h', 'src/uitools/pvp744_state_view_audit.cpp',
        'tools/pvp744_finalize_state_view.py', 'src/sim/typed72_app/composition/MANIFEST.json'}
    # Windows spelling of MANIFEST.json is canonical in the archive.
    files.discard('src/sim/typed72_app/composition/manifest.json')
    files = sorted({p.replace('\\', '/') for p in files if (ROOT/p).is_file()})
    with zipfile.ZipFile(candidate/'candidate-source-changes.zip', 'w', zipfile.ZIP_DEFLATED) as z:
        for p in files: z.write(ROOT/p, p)
    backup = ROOT/'backup-latest/performance-before.zip'
    changes = []
    with zipfile.ZipFile(backup) as z:
        old_files = set(z.namelist())
        for p in files:
            if p not in old_files and p not in ('src/sim/typed72_app/unit_projection.h', 'src/uitools/pvp744_state_view_audit.cpp', 'tools/pvp744_finalize_state_view.py'):continue
            a = z.read(p).decode('utf8') if p in old_files else ''
            b = (ROOT/p).read_text('utf8')
            changes += difflib.unified_diff(a.splitlines(True), b.splitlines(True), fromfile='before/'+p, tofile='after/'+p)
    (OUT/'changes.diff').write_text(''.join(changes), 'utf8')
    manifest = read(ROOT/'backup-latest/manifest.json')
    for row in manifest:
        if Path(row['file']).name == backup.name: row['sha256'] = sha(backup)
    write(ROOT/'backup-latest/manifest.json', manifest)
    assert saves() == before['saves'] and sha(official) == before['official']
    write(candidate/'manifest.json', dict(kind='local state/HUD experimental candidate; formal r3 unchanged',
        candidate_exe_sha256=expected, production_exe_sha256=sha(official),
        checks=total, source_hashes={p: sha(ROOT/p) for p in files},
        artifact_hashes={p.name: sha(p) for p in candidate.iterdir() if p.is_file() and p.name!='manifest.json'},
        user_save_hashes=before['saves'], backup_sha256=sha(backup),
        limitations=['No Android build/device acceptance', 'No physical/human input acceptance',
                      'Full 2366-product gates not rerun', 'Metadata JSON and V row copies remain']))
    print(json.dumps(dict(candidate=str(target), sha256=expected, checks=total, saves_unchanged=len(before['saves'])), ensure_ascii=False))


if __name__ == '__main__':
    main()
