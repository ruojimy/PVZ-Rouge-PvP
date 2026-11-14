#!/usr/bin/env python3
"""评测台：按固定局号列表并行跑 headless_match，汇总分阵营胜率。

  python3 build/ai-nn/eval.py --bin /tmp/ai-nn-build/headless_match \
      --corpus build/ai-nn/cold-corpus --out-dir /tmp/eval-r22 [--ids all|家院|036,037|@file]
      [--jobs N] [--planner r22] [--control-hz 15] [--limit-seconds 1800] [--resume] [--memory-limit-mb N]

--memory-limit-mb 给每个对局进程设地址空间上限（仅 Linux）。超限的对局以 std::bad_alloc 退出并记为崩溃，
不会拖垮同时在跑的其他对局。
--resume 复用输出目录里已经跑完的对局（文件最后一行是结果行），只跑缺的；被复用的对局没有耗时数据。

一局一个进程。输出目录里：
  matches/<id>.jsonl   每局的确定性输出（文件头、规划记录、结果）
  summary.json         确定性汇总（不含墙钟时间），两遍运行应逐字节相同
  timing.json          墙钟耗时与吞吐（每次运行都不同）
只用标准库。
"""
import argparse, concurrent.futures, hashlib, json, math, os, subprocess, sys, time


def wilson(k, n, z=1.959963984540054):
    """95% Wilson 置信区间。"""
    if n == 0:
        return None
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [round(max(0., c - h), 6), round(min(1., c + h), 6)]


def select(index, spec):
    entries = index['entries']
    if spec == 'all':
        return [e['id'] for e in entries]
    if spec.startswith('@'):
        with open(spec[1:], encoding='utf-8') as fh:
            wanted = fh.read().split()
    else:
        wanted = [x for x in spec.split(',') if x]
    ids = []
    known = {e['id'] for e in entries}
    for w in wanted:
        if w in known:
            ids.append(w)
        else:
            hit = [e['id'] for e in entries if e['map'] == w]
            if not hit:
                raise SystemExit('未知的局号或地图：%s' % w)
            ids += hit
    return ids


def run_one(args, match_id):
    out = os.path.join(args.out_dir, 'matches', match_id + '.jsonl')
    if args.resume and os.path.exists(out):
        with open(out, 'rb') as fh:
            data = fh.read()
        lines = data.rstrip(b'\n').rsplit(b'\n', 1)
        try:
            footer = json.loads(lines[-1].decode('utf-8'))
        except ValueError:
            footer = None
        if footer and footer.get('type') == 'result':
            footer['file_sha256'] = hashlib.sha256(data).hexdigest()
            return match_id, footer, None
    cmd = [args.bin, '--corpus', args.corpus, '--id', match_id, '--out', out, '--planner', args.planner,
           '--control-hz', repr(args.control_hz), '--limit-seconds', repr(args.limit_seconds)] + args.extra
    resource_file = os.path.join(args.out_dir, 'matches', match_id + '.resources.json')
    if sys.platform == 'linux' and os.path.exists('/usr/bin/time'):
        cmd = ['/usr/bin/time', '-f', '{"max_rss_kib":%M,"user_seconds":%U,"system_seconds":%S,"elapsed_seconds":%e}', '-o', resource_file] + cmd
    started = time.perf_counter()
    limit = None
    if args.memory_limit_mb and hasattr(os, 'fork'):
        import resource
        cap = int(args.memory_limit_mb) * 1024 * 1024
        limit = lambda: resource.setrlimit(resource.RLIMIT_AS, (cap, cap))
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, preexec_fn=limit)
    wall = time.perf_counter() - started
    if proc.returncode != 0:
        return match_id, None, dict(returncode=proc.returncode, stderr=proc.stderr.decode('utf-8', 'replace')[-2000:], process_seconds=wall)
    timing = json.loads(proc.stdout.decode('utf-8').strip().splitlines()[-1])
    timing['process_seconds'] = wall
    if os.path.exists(resource_file):
        with open(resource_file, encoding='utf-8') as f:
            timing['resources'] = json.load(f)
    with open(out, 'rb') as fh:
        data = fh.read()
    footer = json.loads(data.rstrip(b'\n').rsplit(b'\n', 1)[-1].decode('utf-8'))
    footer['file_sha256'] = hashlib.sha256(data).hexdigest()
    return match_id, footer, timing


def group_stats(rows):
    n = len(rows)
    wins = {'plant': 0, 'zombie': 0, 'draw': 0}
    timeouts = errors = 0
    seconds = []
    for r in rows:
        if r.get('ai_error'):
            errors += 1
        elif r['timeout']:
            timeouts += 1
        else:
            wins[r['result']['winner']] += 1
            seconds.append(r['time'])
    decided = wins['plant'] + wins['zombie'] + wins['draw']
    return dict(matches=n, plant_wins=wins['plant'], zombie_wins=wins['zombie'], draws=wins['draw'], timeouts=timeouts, ai_errors=errors,
                plant_win_rate=round(wins['plant'] / n, 6) if n else None, plant_ci95=wilson(wins['plant'], n),
                zombie_win_rate=round(wins['zombie'] / n, 6) if n else None, zombie_ci95=wilson(wins['zombie'], n),
                timeout_rate=round(timeouts / n, 6) if n else None,
                mean_seconds=round(sum(seconds) / len(seconds), 3) if seconds else None,
                min_seconds=min(seconds) if seconds else None, max_seconds=max(seconds) if seconds else None,
                median_seconds=sorted(seconds)[len(seconds) // 2] if seconds else None, decided=decided)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--bin', required=True)
    ap.add_argument('--corpus', required=True)
    ap.add_argument('--out-dir', required=True)
    ap.add_argument('--ids', default='all')
    ap.add_argument('--jobs', type=int, default=min(4, os.cpu_count() or 1))
    ap.add_argument('--planner', default='r22')
    ap.add_argument('--control-hz', type=float, default=15.)
    ap.add_argument('--limit-seconds', type=float, default=1800.)
    ap.add_argument('--resume', action='store_true')
    ap.add_argument('--memory-limit-mb', type=int, default=0)
    ap.add_argument('extra', nargs='*', help='追加给 headless_match 的参数（写在 -- 之后）')
    args = ap.parse_args()
    with open(os.path.join(args.corpus, 'index.json'), encoding='utf-8') as fh:
        index = json.load(fh)
    meta = {e['id']: e for e in index['entries']}
    ids = select(index, args.ids)
    os.makedirs(os.path.join(args.out_dir, 'matches'), exist_ok=True)
    started = time.perf_counter()
    footers, timings, failures = {}, {}, {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as pool:
        for match_id, footer, timing in pool.map(lambda i: run_one(args, i), ids):
            if footer is None:
                failures[match_id] = timing
            else:
                footers[match_id] = footer
                if timing is not None:
                    timings[match_id] = timing
    wall = time.perf_counter() - started
    rows = [footers[i] for i in ids if i in footers]
    by_map = {}
    for i in ids:
        if i in footers:
            by_map.setdefault(meta[i]['map'], []).append(footers[i])
    by_night = {}
    for i in ids:
        if i in footers:
            by_night.setdefault('night' if meta[i]['night'] else 'day', []).append(footers[i])
    summary = dict(format='pvz-ai-nn-eval-1', planner=args.planner, control_hz=args.control_hz, limit_seconds=args.limit_seconds,
                   extra=args.extra, ids=ids, crashed=sorted(failures),
                   crash_messages={i: (failures[i].get('stderr') or '').strip()[-200:] for i in sorted(failures)}, overall=group_stats(rows),
                   by_map={m: group_stats(r) for m, r in sorted(by_map.items())},
                   by_daylight={m: group_stats(r) for m, r in sorted(by_night.items())},
                   matches={i: dict(map=meta[i]['map'], night=meta[i]['night'], seed=meta[i]['seed'],
                                    winner=(footers[i]['result'] or {}).get('winner'), reason=(footers[i]['result'] or {}).get('reason'),
                                    timeout=footers[i]['timeout'], tick=footers[i]['tick'], time=footers[i]['time'],
                                    hp=footers[i]['hp'], ai_error=footers[i]['ai_error'], log_sha256=footers[i]['log_sha256'],
                                    file_sha256=footers[i]['file_sha256'], ai=footers[i]['ai'])
                            for i in ids if i in footers})
    with open(os.path.join(args.out_dir, 'summary.json'), 'w', encoding='utf-8') as fh:
        json.dump(summary, fh, ensure_ascii=False, indent=1, sort_keys=True)
        fh.write('\n')
    game = sum(t['game_seconds'] for t in timings.values())
    cpu = sum(t['wall_seconds'] for t in timings.values())
    ticks = sum(t['room_ticks'] for t in timings.values())
    timing = dict(jobs=args.jobs, resumed=len(footers) - len(timings), wall_seconds=wall, game_seconds=game, match_cpu_seconds=cpu, room_ticks=ticks,
                  single_core_speed=game / cpu if cpu else None, single_core_ticks_per_second=ticks / cpu if cpu else None,
                  wall_speed=game / wall if wall else None, per_match=timings, failures=failures)
    # Preserve the foundation's keys for readers, but label the legacy metric
    # truthfully: headless_match reports simulation wall time, not OS CPU time.
    timing['legacy_timing_note'] = 'match_cpu_seconds and single_core_* use accumulated simulation wall_seconds; OS CPU is in per_match.resources'
    with open(os.path.join(args.out_dir, 'timing.json'), 'w', encoding='utf-8') as fh:
        json.dump(timing, fh, ensure_ascii=False, indent=1, sort_keys=True)
        fh.write('\n')
    o = summary['overall']
    print('局数 %d  植物胜 %d (%.1f%%, 95%% CI %s)  僵尸胜 %d (%.1f%%, 95%% CI %s)  平局 %d  超时 %d  AI 异常 %d  崩溃 %d' % (
        o['matches'], o['plant_wins'], 100 * (o['plant_win_rate'] or 0), o['plant_ci95'], o['zombie_wins'], 100 * (o['zombie_win_rate'] or 0),
        o['zombie_ci95'], o['draws'], o['timeouts'], o['ai_errors'], len(failures)))
    print('平均时长 %s 游戏秒；墙钟 %.1f 秒，%d 进程；单核吞吐 %.1f 倍实时（%.0f tick/s）' % (
        o['mean_seconds'], wall, args.jobs, timing['single_core_speed'] or 0, timing['single_core_ticks_per_second'] or 0))
    return 1 if failures or o['ai_errors'] else 0


if __name__ == '__main__':
    sys.exit(main())
