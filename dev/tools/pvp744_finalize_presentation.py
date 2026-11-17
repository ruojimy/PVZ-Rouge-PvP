"""Freeze the validated local presentation candidate and its review evidence.

Does not replace the formal game or its user data. Run after all listed cases.
"""
import difflib
import hashlib
import json
from pathlib import Path
import shutil
import zipfile

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "test_results/pvp744/presentation-20261116"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def saves():
    base = ROOT / "PVZ_rougePvP_native/pvp_userdata"
    return {p.relative_to(base).as_posix(): sha(p) for p in base.rglob("*") if p.is_file()}


def main():
    checks = read(OUT / "checks-final.json")
    assert checks["total_checks"] == checks["total_passed"] == 82
    all_runs = {}
    for name in ("first-ab", "reverse-ab", "final-repeat", "wall-ab"):
        run = read(OUT / name / "summary.json")
        assert run["completed"]
        assert all(v["equal_state_rng"] for v in run["comparisons"].values())
        all_runs[name] = run
    exe = ROOT / "build/app-typed72-v2/Release/pvp743_pacing_lab.exe"
    expected = sha(exe)
    for name in ("reverse-ab", "final-repeat", "wall-ab"):
        for process in (OUT / name).glob("*/process.json"):
            assert read(process)["exe_sha256"] == expected, str(process)
    before = saves()
    candidate = OUT / "candidate"
    candidate.mkdir(exist_ok=True)
    target = candidate / "PvP744PresentationCandidate.exe"
    shutil.copy2(exe, target)
    for dll in exe.parent.glob("*.dll"):
        shutil.copy2(dll, candidate / dll.name)
    assert sha(target) == expected
    rel = target.relative_to(ROOT).as_posix()
    for name, arm in (("体验性能候选.cmd", "localframe"), ("体验性能对照.cmd", "view"), ("体验刷新复用.cmd", "view")):
        body = '@echo off\nsetlocal\ncd /d "%~dp0"\n'
        body += f'python -X utf8 tools/pvp744_scheduler_lab.py --exe "{rel}" --out auto --scenes grabber --arms {arm} --interactive --seconds 180\npause\n'
        (ROOT / name).write_bytes(body.replace("\n", "\r\n").encode("utf-8"))
    official = ROOT / "PVZ_rougePvP_native/PvZPvPNative.exe"
    assert sha(official) == "db52ea14fd5d722bde1a0cb173cd0164971d9ff2037a973cd8dc588a17c8d0e6"
    assert before == saves(), "User save changed during packaging"

    lines = ["# 本机呈现优化候选验收", "", "日期：2026-11-16。完成重复刷新插值修复和本机可见命令延迟投影；82/82项定向检查通过。高负载稳定30FPS、Android实机与人工手感尚未验收，T01/T02/T24继续开放。正式版本仍为PvP74.3 r3。", "", "## 改动及边界", "",
        "- 重复姿态更新最新血量、资源、ACK和动画字段，同时保留插值起点；同tick位置变化、传送、复活、地图/席位/对局变化及暂停等会断开旧插值。",
        "- `PVP744_LOCAL_FRAME=1`只在本地呈现作用域启用私有typed帧句柄，持有独立NativeFrame；按图层、隐藏实体和视口选择命令，再延迟构建V配方。每帧已构建的命令复用。倒下英雄支持显式完整投影。",
        "- 完整公共/网络/回放快照仍保持原协议；伤害、250Hz规则、RNG、draw副作用和像素变换不变。材质仍仅作用显示。",
        "- 这是单线程的局部数据通路优化：仍使用原有DrawReplay/像素材质处理，战斗JSON投影也仍存在；不是完全typed渲染器、GPU渲染或模拟worker。候选开关默认关闭，插值修复随新构建生效。",
        "- Windows与Android的构建源清单均加入local_frame.cpp；本轮只构建和验证Windows，没有新APK。", "", "## 等量工作对照", "",
        "同PC、两个逻辑核、BelowNormal、串行、SDL dummy完整软件绘制循环；固定0.20倍率、seed301、高HP、中性输入、原画/像素、关闭自动减绘。每组暖场150 room tick后测90 room tick=750 native tick。不是物理显示FPS或Android数据。两臂都含插值修复和本地副本复用，仅切换新的延迟投影。", "",
        "| 最终构建批次 | 场景 | 设置 | 呈现循环/秒 | 服务P95/P99 ms | 新状态刷新均值 ms | 绘制均值 ms |",
        "| --- | --- | --- | ---: | ---: | ---: | ---: |"]
    labels = {"view": "对照", "localframe": "延迟投影"}
    scenes = {"ordinary": "普通20", "barrage": "高弹幕240", "grabber": "抓人草120"}
    for name in ("reverse-ab", "final-repeat"):
        for row in all_runs[name]["results"]:
            p = row["phases"]
            lines.append(f"| {name} | {scenes[row['scene']]} | {labels[row['arm']]} | {row['fps']:.2f} | {p['frame_interval_actual']['p95']:.2f}/{p['frame_interval_actual']['p99']:.2f} | {p['refresh_advanced']['mean']:.2f} | {p['render']['mean']:.2f} |")
    lines += ["", "各场景各组终态、RNG、最终tick与native tick数一致。两轮抓人草交换执行顺序，仍只属于短时诊断；不能推断所有场景或所有设备的稳定收益。平均超过30并不代表长帧已解决。first-ab保留为初步样本，早于最终命令层级兼容处理，不混入最终构建统计。", "", "## 自动倍率45秒对照", "",
        "暖场5秒后测45秒。推进的逻辑工作不同，不比较终态哈希，也不据此宣称等量模拟吞吐提升。", "",
        "| 设置 | 呈现循环/秒 | 服务P95/P99 ms | 模拟/墙钟 | 最后倍率 | >100ms工作帧 |",
        "| --- | ---: | ---: | ---: | ---: | ---: |"]
    for row in all_runs["wall-ab"]["results"]:
        p = row["phases"]
        long_frames = next(v for k,v in row['long_frames'].items() if float(k)==100.)
        lines.append(f"| {labels[row['arm']]} | {row['fps']:.2f} | {p['frame_interval_actual']['p95']:.2f}/{p['frame_interval_actual']['p99']:.2f} | {row['ratio']:.3f} | {row['last_scale']:.3f} | {long_frames:.2f}% |")
    lines += ["", "## 验证与交付", "",
        "82项包括既有调度/快照10、性能6、机制17、网络22，加插值生命周期11、本机帧/像素5、启用本机帧开关的网络11。像素检查覆盖密集藤蔓、层级、裁剪、缩放、偏移、倒下英雄、材质覆盖/恢复；绘制不改变战斗RNG，持有的旧帧不随后续step改变。", "",
        "初始跨环断言把数值约960当成与0不同的位置；修正为周期坐标距离。初始材质夹具的相机没有覆盖被替换的植物英雄；改为围绕该英雄后，材质确实可见且两路径逐像素一致。失败证据保留，未通过修改运行逻辑绕过断言。最终汇总是checks-final.json，原始报告路径逐项列出。", "",
        "完整产品2366项门禁本轮未重跑；历史27项未豁免仍未关闭。混合场景、Android、真实公网、长时内存与用户手感未据此判为通过。", "",
        "根目录“体验性能候选.cmd”启动本轮冻结EXE并开启延迟投影；“体验性能对照.cmd”使用同一EXE与相同慢放设置，关闭延迟投影；“体验刷新复用.cmd”保留为同一对照入口。均为抓人草120、180秒、双方足额资源、独立test_results/pvp744/manual-*用户数据，原冷却和部署规则继续生效。", "",
        "正式启动器及独立存档保持r3，核对其实际EXE SHA-256。候选与源码补丁归档在candidate目录；补丁仍依赖现有工程和冻结生产阶段，不是完整源码发布包。前一候选在scheduler-20261116/candidate保留为测试证据。", "",
        "回退文件为backup-latest/performance-before.zip，保存本轮修改前的拥有者文件；r3的PC/源码/APK备份继续保留。此前被自动审批拒绝清理的t03-source未再次尝试删除，不能宣称旧备份已全部清理。", "",
        "复跑：tools/pvp744_verify_scheduler.py；tools/pvp744_scheduler_lab.py的view/localframe两臂。接下来应减少新状态的JSON/HUD提取成本，再决定独占Session worker的实现；未把完整typed渲染或线程隔离标为完成。", ""]
    (OUT / "assessment.md").write_text("\n".join(lines), encoding="utf-8")

    previous = read(ROOT / "test_results/pvp744/scheduler-20261116/candidate/manifest.json")
    source_names = set(previous["source_hashes"])
    new_names = {"src/sim/typed72_app/local_frame.h", "src/sim/typed72_app/local_frame.cpp",
        "src/uitools/pvp744_presentation_audit.cpp", "src/uitools/pvp744_local_frame_audit.cpp",
        "tools/pvp744_finalize_presentation.py"}
    with zipfile.ZipFile(ROOT / "backup-latest/performance-before.zip") as archive:
        originals = {n: archive.read(n) for n in archive.namelist() if n != "backup-info.json"}
    source_names.update(originals)
    source_names.update(new_names)
    diffs = []
    for name in sorted(set(originals) | new_names):
        old = originals.get(name, b"").decode("utf-8-sig").replace("\r\n", "\n")
        new = (ROOT / name).read_text(encoding="utf-8-sig")
        if old != new:
            diffs.extend(difflib.unified_diff(old.splitlines(True), new.splitlines(True), fromfile="before/"+name, tofile="after/"+name))
    (candidate / "changes.diff").write_text("".join(diffs), encoding="utf-8")
    with zipfile.ZipFile(candidate / "candidate-source-changes.zip", "w", zipfile.ZIP_DEFLATED) as archive:
        for name in sorted(source_names): archive.write(ROOT / name, name)
        archive.write(OUT / "assessment.md", "presentation-assessment.md")
    backup = ROOT / "backup-latest/performance-before.zip"
    with zipfile.ZipFile(backup, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, data in originals.items(): archive.writestr(name, data)
        archive.writestr("backup-info.json", json.dumps({"revision":"before-pvp744-presentation-v2", "sha256":{n:hashlib.sha256(data).hexdigest() for n,data in originals.items()}}, ensure_ascii=False, indent=2))
    backup_manifest = ROOT / "backup-latest/manifest.json"
    entries = read(backup_manifest)
    for entry in entries:
        if Path(entry["file"]).name == backup.name: entry["sha256"] = sha(backup)
    write(backup_manifest, entries)
    write(candidate / "manifest.json", {
        "kind": "isolated local presentation candidate; formal release remains pvp743-r3",
        "candidate_exe_sha256": expected, "production_exe_sha256": sha(official),
        "source_hashes": {name:sha(ROOT / name) for name in sorted(source_names)},
        "artifacts": {p.name:sha(p) for p in candidate.iterdir() if p.is_file() and p.name!="manifest.json"},
        "checks": {"passed":82,"total":82,"report":"../checks-final.json"},
        "same_logical_work": {n:all_runs[n]["comparisons"] for n in ("reverse-ab","final-repeat")},
        "save_protection": {"scope":"packaging window; experiments use separate userdata", "unchanged":True,"files":before},
        "limits": ["No new APK or Android validation", "No human responsiveness acceptance", "No full product gate rerun", "Not a complete typed renderer or worker", "Source archive requires existing project and frozen stages"],
    })
    print(json.dumps({"candidate":str(target),"sha256":expected,"checks":82,"save_files_unchanged":len(before)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
