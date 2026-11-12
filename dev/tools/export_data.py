"""Export every module-level constant of the PvP71 package (and the original
literal tables) to extract/data/<module>.json, plus the actual resolved card
table for each secret/night combination used by the game.

Constants = JSON-representable values (numbers, strings, lists/tuples/dicts/sets
of those).  Callables, classes, modules and large atlas blobs are skipped.
"""
import sys, json, os, types, importlib, math
from pathlib import Path
REF = Path(r"C:\Users\xiech\Downloads\PVZ-Rouge-v1.4.8\next-pvp71")
OUT = Path(__file__).resolve().parents[1] / "extract" / "data"
SKIP_MODULES = {"expansion_atlas_data", "content_atlas_data", "rv_knowledge", "pvp66_material_data",
                "pvp56_plants_parts", "pvp54_native_parts"}


class Skip(Exception):
    pass


def plain(v, depth=0):
    if depth > 12:
        raise Skip()
    if v is None or isinstance(v, (bool, int, str)):
        return v
    if isinstance(v, float):
        if math.isnan(v) or math.isinf(v):
            return {"__float__": repr(v)}
        return v
    if isinstance(v, (list, tuple)):
        return [plain(x, depth + 1) for x in v]
    if isinstance(v, (set, frozenset)):
        items = [plain(x, depth + 1) for x in v]
        try:
            items = sorted(items, key=lambda x: json.dumps(x, ensure_ascii=False, sort_keys=True))
        except Exception:
            pass
        return {"__set__": items}
    if isinstance(v, dict):
        out = {}
        for k, x in v.items():
            if not isinstance(k, (str, int, float, bool)) and k is not None:
                if isinstance(k, tuple):
                    k = "__tuple__" + json.dumps(plain(k), ensure_ascii=False)
                else:
                    raise Skip()
            out[str(k) if not isinstance(k, str) else k] = plain(x, depth + 1)
        return out
    if isinstance(v, (bytes, bytearray)):
        if len(v) > 4096:
            raise Skip()
        return {"__bytes__": v.hex()}
    raise Skip()


def main():
    sys.path[:0] = [str(REF / "modkit"), str(REF / "tests")]
    os.chdir(str(REF))
    OUT.mkdir(parents=True, exist_ok=True)
    pvp_dir = REF / "modkit" / "pvp"
    index = {}
    for f in sorted(pvp_dir.glob("*.py")):
        name = f.stem
        if name in SKIP_MODULES or name.startswith("smoke") or name.startswith("acceptance"):
            continue
        try:
            mod = importlib.import_module("pvp." + name)
        except Exception as ex:
            index[name] = "IMPORT FAIL %r" % ex
            continue
        consts = {}
        for k, v in vars(mod).items():
            if k.startswith("__") or isinstance(v, (types.ModuleType, types.FunctionType, type)) or callable(v):
                continue
            # skip names imported from elsewhere in the package
            try:
                consts[k] = plain(v)
            except Skip:
                continue
            except RecursionError:
                continue
        # drop re-exports: keep only names assigned in this module's source text
        src = f.read_text(encoding="utf-8")
        own = {k: v for k, v in consts.items() if (k + "=") in src.replace(" ", "") or ("," + k) in src or (k + ",") in src}
        if own:
            (OUT / (name + ".json")).write_text(json.dumps(own, ensure_ascii=False, indent=1), encoding="utf-8")
        index[name] = len(own)
    # original literal tables from the marshalled game
    import multiworker_fixtures as F
    br = F.bridge()
    orig = {}
    for k, v in br._globals.items() if hasattr(br, "_globals") else []:
        try:
            orig[k] = plain(v)
        except Skip:
            pass
    (OUT / "_original_literals.json").write_text(json.dumps(orig, ensure_ascii=False, indent=1), encoding="utf-8")
    # resolved cards for each side under no secrets, day/night
    from pvp.catalog import CARDS, actual_card
    resolved = {}
    for night in (False, True):
        tab = {}
        for key in CARDS:
            try:
                tab[key] = plain(actual_card(key, (), night=night))
            except Exception as ex:
                tab[key] = {"__error__": repr(ex)}
        resolved["night" if night else "day"] = tab
    (OUT / "_resolved_cards.json").write_text(json.dumps(resolved, ensure_ascii=False, indent=1), encoding="utf-8")
    (OUT / "_index.json").write_text(json.dumps(index, ensure_ascii=False, indent=1), encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps(index, ensure_ascii=False))


if __name__ == "__main__":
    main()
