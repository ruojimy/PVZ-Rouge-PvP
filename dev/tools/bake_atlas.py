"""Bake every image the Python PvP71 battle namespace holds into PNG files.

Builds a reference battle (which runs the original 加载游戏 + 1.5.0.1 asset
patches + PvP content assets), then writes each Surface found in the atlas
dictionaries of the match namespace to extract/assets/<atlas>/<n>.png and an
index extract/assets/index.json  {atlas: {key: [file, w, h]}}.
"""
import sys, os, json, hashlib
from pathlib import Path
REF = Path(r"C:\Users\xiech\Downloads\PVZ-Rouge-v1.4.8\next-pvp71")
OUT = Path(__file__).resolve().parents[1] / "extract" / "assets"


def main():
    sys.path[:0] = [str(REF / "tests"), str(REF / "modkit")]
    os.chdir(str(REF))
    import multiworker_fixtures as F
    pg = F.pygame_module()
    b = F.new_battle(seed=1)
    g = b.g
    OUT.mkdir(parents=True, exist_ok=True)
    index = {}
    seen = {}
    real_pg = getattr(pg, "pg", None) or pg

    def surf_of(v):
        for attr in ("pixels", "surface", "_surface", "image", "raw"):
            s = getattr(v, attr, None)
            if s is not None and hasattr(s, "get_size"):
                return s
        if hasattr(v, "get_size") and hasattr(v, "get_at"):
            return v
        return None

    def dump(atlas_name, mapping):
        d = OUT / atlas_name
        d.mkdir(exist_ok=True)
        entry = {}
        keys = list(mapping.keys()) if hasattr(mapping, "keys") else []
        for k in keys:
            try:
                v = mapping[k]
            except Exception as ex:
                entry[str(k)] = ["ERROR %r" % ex, 0, 0]; continue
            s = surf_of(v)
            if s is None:
                if isinstance(v, (list, tuple)):
                    for j, item in enumerate(v):
                        si = surf_of(item)
                        if si is not None:
                            entry["%s#%d" % (k, j)] = save(si, d)
                continue
            entry[str(k)] = save(s, d)
        index[atlas_name] = entry
        print(atlas_name, len(entry), flush=True)

    def save(s, d):
        try:
            raw = real_pg.image.tostring(s, "RGBA")
        except Exception:
            s = s.convert_alpha() if hasattr(s, "convert_alpha") else s
            raw = real_pg.image.tostring(s, "RGBA")
        h = hashlib.sha1(raw + repr(s.get_size()).encode()).hexdigest()[:16]
        if h not in seen:
            fn = "%s.png" % h
            real_pg.image.save(s, str(d.parent / "_png" / fn))
            seen[h] = fn
        w, hh = s.get_size()
        return [seen[h], w, hh]

    (OUT / "_png").mkdir(exist_ok=True)
    for name in ("图集", "ui图集", "背景图集", "近景图集", "拟人图集"):
        m = g.get(name)
        if m is None:
            continue
        inner = getattr(m, "_items", None) or getattr(m, "data", None) or m
        try:
            dump(name, inner)
        except Exception as ex:
            import traceback; traceback.print_exc()
    # report other Surface-bearing globals
    others = {}
    for k, v in g.items():
        if surf_of(v) is not None:
            others[k] = save(surf_of(v), OUT / "_png")
    index["_globals"] = others
    (OUT / "index.json").write_text(json.dumps(index, ensure_ascii=False, indent=0), encoding="utf-8")
    print("unique pngs", len(seen))
    b.close()


if __name__ == "__main__":
    main()
