"""Time the Python PvP71 battle for a scenario (same setup as oracle_record, no state dump).
   bench_py.py <scenario> [room_ticks]   -> prints init / step seconds and whether _pvpcore is active."""
import sys, json, time
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import oracle_record as R

name = sys.argv[1]
sc = json.loads((HERE / "scenarios" / (name + ".json")).read_text(encoding="utf-8"))
sc["_name"] = name
t0 = time.perf_counter()
b = R.build(sc)
t1 = time.perf_counter()
n = int(sys.argv[2]) if len(sys.argv) > 2 else sc.get("room_ticks", 30)
for _ in range(n):
    b.step()
t2 = time.perf_counter()
from pvp import cppcore
print("init %.3fs, %d room ticks %.3fs, native ticks %d, cppcore=%s" % (t1 - t0, n, t2 - t1, b.engine.native_tick,
      cppcore.native() is not None if hasattr(cppcore, "native") else "?"))
