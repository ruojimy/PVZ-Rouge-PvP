import dis, marshal, sys, collections
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from slice_regions import REGIONS, ROOT
root = marshal.loads((ROOT / "reverse_engineered/raw/pvzrouge.pyc").read_bytes())
ins = list(dis.get_instructions(root))
print("total bytes", len(root.co_code), "instructions", len(ins))
c = collections.Counter()
for i in ins:
    if any(s <= i.offset < e for s, e in REGIONS.values()):
        c[i.opname] += 1
for k, v in c.most_common():
    print(v, k)
# nested code objects
for k in root.co_consts:
    if hasattr(k, "co_code"):
        print("CODE", k.co_name, len(k.co_code))
