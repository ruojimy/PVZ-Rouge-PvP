"""Freeze metadata candidate and produce its assessment from raw PC/device evidence."""
import difflib
import hashlib
import json
from pathlib import Path
import re
import shutil
import zipfile

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'test_results/pvp744/metadata-20261116'
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p): return json.loads(p.read_text('utf8'))
def write(p, obj): p.write_text(json.dumps(obj, ensure_ascii=False, indent=2)+'\n', 'utf8')

def main():
    before = read(OUT/'before.json')
    saves = ROOT/'PVZ_rougePvP_native/pvp_userdata'
    assert {p.relative_to(saves).as_posix():sha(p) for p in saves.rglob('*') if p.is_file()} == before['saves']
    official = ROOT/'PVZ_rougePvP_native/PvZPvPNative.exe'
    assert sha(official) == before['official']
    checks = read(OUT/'checks-final/summary.json')
    assert checks['completed'] and all(r['exit_code']==0 and r['checks']==r['passed'] for r in checks['results'])
    total = sum(r['checks'] for r in checks['results'])
    runs = {n:read(OUT/n/'summary.json') for n in ('ab','ba','wall-ab','profile')}
    exe = ROOT/'build/app-typed72-v2/Release/pvp743_pacing_lab.exe'
    expected = sha(exe)
    for name, run in runs.items():
        assert run['completed'] and all(v['equal_state_rng'] for v in run['comparisons'].values())
        for p in (OUT/name).glob('*/process.json'): assert read(p)['exe_sha256']==expected
        for r in run['results']:
            report = read(OUT/name/(r['scene']+'-'+r['arm'])/'report.json')
            b = report['backend_audit']
            if name!='profile': assert b['performance']['function_profile']=={}
            if r['arm']=='metadata': assert b['metadata_view']['private_adoptions']>0
    anchors={r['scene']:r for r in read(ROOT/'test_results/pvp744/state-view-20261116/ab/summary.json')['results'] if r['arm']=='stateview'}
    for name in ('ab','ba'):
        for r in runs[name]['results']:
            assert all(r[k]==anchors[r['scene']][k] for k in ('state','rng','tick','native_ticks'))
    device=read(OUT/'android-clean-final/summary.json')
    assert device['completed']
    for r in device['results']:
        assert r['userdata_audit']['unchanged'] and r['userdata_audit']['before']
        assert r['backend_audit']['performance']['function_profile']=={}
        assert r['neutral_input_audit']['passed']
    install=read(OUT/'android-install.json')
    assert install['apk_sha256']==install['installed_sha256']
    candidate=OUT/'candidate';candidate.mkdir(exist_ok=True)
    target=candidate/'PvP744MetadataCandidate.exe';shutil.copy2(exe,target)
    for p in exe.parent.glob('*.dll'):shutil.copy2(p,candidate/p.name)
    assert sha(target)==expected
    for name,arm in [('体验性能候选.cmd','metadata'),('体验性能对照.cmd','stateview'),('体验刷新复用.cmd','view')]:
        body='@echo off\nsetlocal\ncd /d "%~dp0"\n'
        body+=f'python -X utf8 tools/pvp744_scheduler_lab.py --exe "{target.relative_to(ROOT).as_posix()}" --out auto --scenes grabber --arms {arm} --interactive --seconds 180\npause\n'
        (ROOT/name).write_bytes(body.replace('\n','\r\n').encode('utf8'))
    labels={'stateview':'前轮状态投影','metadata':'元数据直投与接管'}
    lines=['# 玩家元数据与快照所有权优化验收','',
      f'2026-11-16。{total}/{total}项定向检查通过；PC同工作量AB/BA、自动倍率、独立函数计时及Android同APK自动压力已完成。正式PC仍为r3；手机安装的是保留数据升级的诊断候选，正常游戏入口默认未开启实验开关。','',
      '## 架构与正确性','',
      'Session通过同步SnapshotSink输出玩家、冷却、卡组、放置、资源和触手字段，UI端直接构造独立V对象，省去这些字段的ordered JSON→普通JSON→V中间链。既有姿态JSON在原地读取；稀有元数据、事件、音频和pvp70弹道仍保留JSON。没有把可变Session引用交给UI或其他线程。','',
      '本机新视图接管刚构造的对象图，省去随后一次元数据深复制和单位行浅复制；公开快照使用独立对象图及原复制契约。状态版本与投影次数分离，公开读取同一状态不会使已存在的本机视图失效。同tick写入仍使状态失效，旧视图独立持有数据。','',
      '生产拥有者仍是build/typed72-match-v1/snapshot_layer.inc与生产Session，已由生成器同步composition；只读next-pvp71未改。250Hz、伤害4、随机数顺序、材质和公共协议保持。PVP744_METADATA_VIEW默认关闭，仅在本机呈现作用域启用。函数计时显式开启，默认关闭。','',
      '定向检查含字段组合/四模式差分、玩家键顺序、放置睡眠/藤蔓/飞行字段、资源可选值、同tick玩家更新、私有/公开变更隔离、旧视图保持、像素、调度、网络。另用真正诊断主程序校验了隔离存档SHA审计。初期暴露合作卡牌缓存陈旧、公共投影误失效本机版本，均已修复；一个测试辅助函数无条件删除可选键也已修正。初始失败记录保留。','',
      '## PC同等逻辑工作量','',
      'Windows两个逻辑核、BelowNormal、SDL dummy完整软件绘制；同一EXE、相同调度与前轮单位/HUD/帧优化，只切换本轮元数据路径。固定0.20倍率，暖场150 room tick、测量90 room tick（750 native tick），计时插桩关闭。性能采样与编译串行。','',
      '| 批次 | 场景 | 路径 | 呈现循环/秒 | 新状态刷新均值 ms | 服务间隔P95/P99 ms |',
      '| --- | --- | --- | ---: | ---: | ---: |']
    for name in ('ab','ba'):
        for r in runs[name]['results']:
            p=r['phases'];t=p['frame_interval_actual']
            lines.append(f"| {name} | {r['scene']} | {labels[r['arm']]} | {r['fps']:.2f} | {p['refresh_advanced']['mean']:.2f} | {t['p95']:.2f}/{t['p99']:.2f} |")
    lines+=['','同场景终态、RNG、room/native tick完全一致，且与前轮冻结结果一致。这是软件服务循环，不是物理屏幕FPS。新状态刷新在AB/BA均下降；服务间隔尾部没有全面改善，例如BA弹幕P95略高，不能宣称长帧已解决。','',
      '## PC自动倍率','', '暖场5秒后测45秒；不同推进量，不能当作等量模拟吞吐对照。','',
      '| 路径 | 呈现循环/秒 | 服务间隔P95/P99 ms | 模拟/墙钟 | 最后倍率 |', '| --- | ---: | ---: | ---: | ---: |']
    for r in runs['wall-ab']['results']:
        t=r['phases']['frame_interval_actual'];lines.append(f"| {labels[r['arm']]} | {r['fps']:.2f} | {t['p95']:.2f}/{t['p99']:.2f} | {r['ratio']:.3f} | {r['last_scale']:.3f} |")
    lines+=['','自动倍率样本呈现率和模拟推进均有小幅提升，但P95仍约52ms且略高；这是减少刷新开销的阶段性结果，不是稳定30FPS。','',
      '## 独立函数计时','', '抓人草固定0.20归因样本；计时含嵌套，不能相加。刷新三阶段互斥，旧metadata_json包含JSON构造，新同名阶段主要为直接投影。函数计数还包含收尾公开快照投影，因此新路径出现32次而本机新视图为30次，不能当作严格逐帧配对计时。','',
      '| 路径 | 函数/阶段 | 次数 | 均值 ms |','| --- | --- | ---: | ---: |']
    for arm in ('stateview','metadata'):
        d=read(OUT/'profile'/('grabber-'+arm)/'report.json')['backend_audit']['performance']['function_profile']
        for key in ('StateView::metadata_json','StateView::metadata_values','StateView::unit_values','StateView::snapshot_copy','LocalFrame::copy','Room::snapshot','Application::merge_view'):
            if key in d:
                v=d[key];lines.append(f"| {labels[arm]} | {key} | {v['calls']:.0f} | {v['total_ms']/max(1,v['calls']):.3f} |")
    lines+=['','## Android实机','',
      'vivo V2456A，Android16，ARM64。相同签名和包名覆盖升级，未卸载/清数据。首轮8场中的前7场有真实触控，植物方有效序列达到12–42，普通候选还额外放置2株植物，因此该批保留为交互现场证据，不用来断言纯性能增益。此前中途报告的7.91→8.39等首轮数值不作为受控A/B结论。原始结果见android-ab。','',
      '下表是另外补跑的抓人草中性输入对照：每组独立进程，原画/像素、完整绘制、高HP，暖场5秒后测30秒，同APK切换路径。核验两侧最终seq=1、last_input_tick=2、move=0、jump_held=false；入口调用允许2或4次。生产CommandInput在处理新动作前递增序列，旧序列会被拒绝，故入口计数不等于有效输入数。第一次补测因错误要求入口只能2次而被工具拒绝，原始记录保留在android-clean，修正的是校验口径而非游戏行为。额外调用的具体UI来源没有单独追踪。','',
      '两臂均为自动倍率，推进量不同；不能要求终态相同或据此声称等量模拟加速。仅一轮短时手机对照，不外推所有场景。','',
      '| 顺序/场景/路径 | 呈现循环/秒 | 新状态刷新 ms | 服务间隔P95/P99 ms | 模拟/墙钟 | 电池温度前→后 ℃ |',
      '| --- | ---: | ---: | ---: | ---: | ---: |']
    for r in device['results']:
        case=OUT/'android-clean-final'/r['name'];temps=[]
        for side in ('before','after'):
            m=re.search(r'^\s*temperature:\s*(\d+)',(case/f'battery-{side}.txt').read_text('utf8'),re.M);temps.append(int(m.group(1))/10 if m else 0)
        t=r['frame_phases_ms']['frame_interval_actual']
        refresh=r['frame_phases_ms']['refresh_advanced']['mean']
        lines.append(f"| {r['name']} | {r['presentation']['frames_per_second']:.2f} | {refresh:.2f} | {t['p95']:.2f}/{t['p99']:.2f} | {r['simulation_wall_ratio']:.3f} | {temps[0]:.1f}→{temps[1]:.1f} |")
    lines+=['',
      '每次报告确认真实typed Session、对应开关执行、native step内动态V计数为零。截图及前后台生命周期日志留存。每次隔离诊断前后内部原存档逐文件SHA一致；旧正式APK不允许run-as，因此这些哈希从候选升级后取得，不能冒充升级前内部存档字节比对。安装连续性由相同证书、包名和firstInstallTime及保留数据升级核验。','',
      '## 交付与剩余边界','',
      f'PC体验入口已指向本轮冻结EXE：SHA-256 `{expected}`。候选/对照分别为metadata/stateview，自动布置抓人草120，独立userdata，180秒。正式PC EXE和{len(before["saves"])}个存档文件SHA未变，正式入口仍为最新正式r3。','',
      f'手机版本：{install["version_name"]} / {install["version_code"]}。安装APK与实装base.apk SHA一致：`{install["apk_sha256"]}`。APK路径：{install["apk"]}。该包正常游戏入口保留原默认设置，实验开关由诊断Intent显式传入。','',
      '双击根目录“体验安卓性能候选.cmd”可在唯一在线ADB手机启动180秒独立触控场景，显式启用metadata；保持正常冷却和合法放置，测试存档隔离。该人工入口已做脚本语法检查。用户在本轮反馈：“按键响应及时，绘制与逻辑匹配比之前好，不错”。此为初步主观手感证据，未绑定到某个采样组，也没有量化物理触控到呈现延迟。最后倒序采样前已提醒暂时不触屏。','',
      '这轮不等于完成高负载稳定30FPS或跨场景全面手感验收。完整2366项产品回归未重跑，历史27项未豁免未关闭；候选公网、长时内存、实体触控到呈现延迟仍待覆盖。T01/T02/T24继续开放，T22保持暂停。独立PC计时显示LocalFrame复制约0.046ms，已不是主要热点；下一步优先看手机完整绘制成本、不可分割Session step和App视图合并，不继续无差别移除小JSON，也不跨线程共享当前Session。','',
      '回退源在backup-latest/performance-before.zip，本轮补丁与闭包SHA在candidate；前轮构建保留为测试证据。Android首轮构建因默认SDL依赖目录失效中止，改用当前缓存已验证的sdl2285目录完成c2；没有改只读参照目录。原始证据：checks-final、ab、ba、wall-ab、profile、android-ab、android-clean、android-clean-final、android-build；复跑工具及配置随源码归档。']
    (OUT/'assessment.md').write_text('\n'.join(lines)+'\n','utf8')
    for filename,heading,text in [
      ('交接_性能与交互体验优化_20261116.md','## 12. 玩家元数据与快照所有权优化',f'{total}/{total}项定向检查通过。玩家/放置/资源/触手改为同步直接投影，本机新视图接管独立对象图；公开快照保持隔离。PC AB/BA与同APK Android实机对照已完成，正式PC仍r3，手机为诊断候选。性能、存档核验及未完成边界见[本轮验收](test_results/pvp744/metadata-20261116/assessment.md)。'),
      ('待办清单.md','## 2026-11-16 元数据与安卓候选续建',f'元数据直接投影与私有快照接管已完成，{total}/{total}定向检查、PC等工作量AB/BA、Android同APK自动压力已归档。用户初步反馈按键响应及时、绘制与逻辑更匹配；跨场景手感及物理延迟尚未全面验收。T01/T02/T24仍开放，完整产品回归和候选公网未完成，T22仍暂停。详见[验收与原始结果](test_results/pvp744/metadata-20261116/assessment.md)。')]:
        p=ROOT/filename;body=p.read_text('utf8')
        if heading not in body:body+='\n'+heading+'\n\n'+text+'\n'
        if filename.startswith('交接_'):body=re.sub(r'最新续建结果见第11节[^\n]*','最新续建结果见第12节及[元数据与安卓候选验收](test_results/pvp744/metadata-20261116/assessment.md)。前节保留历轮历史结果。',body)
        p.write_text(body,'utf8')
    old=read(ROOT/'test_results/pvp744/state-view-20261116/candidate/manifest.json')
    new={'src/sim/typed72_app/snapshot_sink.h','src/sim/typed72_app/value_snapshot_sink.h','src/sim/typed72_app/metadata_projection.h','tools/pvp744_finalize_metadata.py','tools/pvp744_android_manual.py','体验安卓性能候选.cmd'}
    files=sorted(set(old['source_hashes'])|set(before['files'])|new)
    backup=ROOT/'backup-latest/performance-before.zip';diff=[]
    with zipfile.ZipFile(backup) as z:
        names=set(z.namelist())
        for f in files:
            if f not in names and f not in new:continue
            a=z.read(f).decode('utf8').splitlines() if f in names else []
            b=(ROOT/f).read_text('utf8').splitlines()
            diff.extend(difflib.unified_diff(a,b,fromfile='before/'+f,tofile='after/'+f,lineterm=''))
    (OUT/'changes.diff').write_text('\n'.join(diff)+'\n','utf8')
    with zipfile.ZipFile(candidate/'candidate-source-changes.zip','w',zipfile.ZIP_DEFLATED) as z:
        for f in files:z.write(ROOT/f,f)
    manifest=read(ROOT/'backup-latest/manifest.json')
    for row in manifest:
        if Path(row['file']).name==backup.name:row['sha256']=sha(backup)
    write(ROOT/'backup-latest/manifest.json',manifest)
    write(candidate/'manifest.json',dict(kind='metadata experimental candidate; formal PC r3 retained',checks=total,
      candidate_exe_sha256=expected,production_exe_sha256=sha(official),user_save_hashes=before['saves'],
      source_hashes={f:sha(ROOT/f) for f in files},artifact_hashes={p.name:sha(p) for p in candidate.iterdir() if p.is_file() and p.name!='manifest.json'},
      backup_sha256=sha(backup),android=install,product_acceptance=False))
    print(json.dumps(dict(checks=total,exe_sha256=expected,device_cases=len(device['results']),sources=len(files))))

if __name__=='__main__':main()
