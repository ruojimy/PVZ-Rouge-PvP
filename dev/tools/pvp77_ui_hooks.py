"""Apply PvP77 UI hooks after the earlier generation hooks; --check never writes."""
import argparse
import json
from pathlib import Path

root = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument("--check", action="store_true")
check = parser.parse_args().check
for rel, old, new in json.loads(Path(__file__).with_name("pvp77_ui_edits.json").read_text(encoding="utf8")):
    path = root / rel
    raw = path.read_bytes()
    nl = b"\r\n" if b"\r\n" in raw else b"\n"
    old, new = (s.encode("utf8").replace(b"\n", nl) for s in (old, new))
    if raw.count(new) == 1:
        continue
    if check or raw.count(old) != 1:
        raise SystemExit(f"Missing or ambiguous PvP77 hook in {rel}: {new[:110]!r}")
    path.write_bytes(raw.replace(old, new))
print("PvP77 hooks checked")
