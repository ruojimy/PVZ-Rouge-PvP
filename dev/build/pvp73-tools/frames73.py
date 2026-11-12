"""Native draw-frame identity for one scenario with the PvP73 tools:
V frames (ref73_record REF_FRAMES) vs typed frames (typed72_match_gate MATCH_FRAMES) on one cold export.

    python frames73.py <scenario> <out-dir>
"""
import os, subprocess, sys
from pathlib import Path
ROOT = Path(r'C:\Users\xiech\Downloads\PVZ_rougePvP_native')
TOOLS = ROOT / 'build/pvp73-tools/build/Release'
GATE = ROOT / 'build/app-typed72-v2/Release/typed72_match_gate.exe'
name, out = sys.argv[1], (ROOT / sys.argv[2]).resolve()
out.mkdir(parents=True, exist_ok=True)
src = ROOT / 'build/typed72-match-v1/scenarios' / (name + '.json')
if not src.exists():
    src = ROOT / 'tools/scenarios' / (name + '.json')
base = dict(os.environ, SDL_VIDEODRIVER='dummy', SDL_AUDIODRIVER='dummy', PYTHONIOENCODING='utf-8')
def run(cmd, **env):
    r = subprocess.run([str(c) for c in cmd], cwd=str(ROOT), env=dict(base, **env), capture_output=True)
    if r.returncode:
        raise SystemExit('%s failed %d %s' % (Path(str(cmd[0])).name, r.returncode, r.stderr[-600:]))
run([TOOLS / 'ref73_record.exe', src, out / 'ref.jsonl'], REF_FRAMES=str(out / 'ref.frames.jsonl'), PVP_USERDATA=str(out / 'ud_ref'))
run([TOOLS / 'cold73_export.exe', src, out / 'cold.json', out / 'atlas.bin'], PVP_USERDATA=str(out / 'ud_cold'))
run([GATE, out / 'cold.json', out / 'atlas.bin', src, out / 'typed.jsonl', out / 'report.json', out / 'final.json'],
    MATCH_FRAMES=str(out / 'typed.frames.jsonl'), MATCH_NO_TRACE='1')
r = subprocess.run([sys.executable, str(ROOT / 'build/typed72-match-v1/compare_frames.py'), str(out / 'ref.frames.jsonl'),
                    str(out / 'typed.frames.jsonl'), str(out / 'cmp.json')], cwd=str(ROOT), env=base, capture_output=True)
print(r.stdout.decode('utf8', 'replace')[-1500:], r.stderr.decode('utf8', 'replace')[-800:])
for f in ('ref.jsonl', 'typed.jsonl', 'atlas.bin'):
    try: (out / f).unlink()
    except OSError: pass
