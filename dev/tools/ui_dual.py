"""Rename the UI translations of dual-use modules: the simulation links the headless shim pm_<m>
(recording graphics), the UI links the real translation as pm_ui_<m>. Run after generating src/ui/gen."""
import re, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
DUAL = ["content_assets", "expansion_assets", "pvp64_sprite_atlas", "pvp67_assets", "pvp66_icons"]
GEN = ROOT / "src/ui/gen"
pat = re.compile(r"\b(pm|init_deps)_(%s)\b" % "|".join(DUAL))
for f in list(GEN.glob("*.cpp")) + list(GEN.glob("*.h")):
    t = f.read_text(encoding="utf-8")
    n = pat.sub(lambda m: "%s_ui_%s" % (m.group(1), m.group(2)), t)
    if n != t:
        f.write_text(n, encoding="utf-8")
for m in DUAL:
    for ext in ("cpp", "h"):
        src = GEN / ("pm_%s.%s" % (m, ext))
        if src.exists():
            dst = GEN / ("pm_ui_%s.%s" % (m, ext))
            if dst.exists():
                dst.unlink()
            src.rename(dst)
print("dual modules renamed:", ", ".join(DUAL))
