"""Write hand-maintained shim modules (src/sim/pvp/shim/pm_<m>.h/.cpp) for PvP modules that
are presentation/tooling only (assets, profiling, the old CPython core, worker pools ...).
Each shim exposes the symbols the translated battle core references, with behaviour that
matches the Python defaults (performance flags on, no native core, no workers)."""
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "src/sim/pvp/shim"
OUT.mkdir(parents=True, exist_ok=True)

NOOP_MODULE = 'V module_ns() { return py::noop_module(SV("%s")); }'

SHIMS = {
    "app": (["V f__pygame(const Args& A);"],
            ['V f__pygame(const Args& A) { throw PyError("RuntimeError", "pygame is not available in the native build"); }']),
    "content_assets": (["extern V SCALE_TILES;", "V f_install(const Args& A);"],
                       ["V SCALE_TILES;", "V f_install(const Args& A) { return V::none(); }",
                        "static void load_() { SCALE_TILES = py::data_value(\"content_assets\", \"SCALE_TILES\"); }"]),
    "cppcore": (["V module_ns();", "V f_configure_final_regions(const Args& A);", "V f_copy_module(const Args& A);",
                 "V f_fast_deepcopy(const Args& A);", "V f_native(const Args& A);", "V f_native_for(const Args& A);"],
                [NOOP_MODULE % "cppcore",
                 "V f_configure_final_regions(const Args& A) { return V::none(); }",
                 "V f_copy_module(const Args& A) { return py::stdlib_module(SV(\"copy\")); }",
                 "V f_fast_deepcopy(const Args& A) { return A.pos.empty() ? V::none() : A.pos[0]; }",
                 "V f_native(const Args& A) { return V::none(); }",
                 "V f_native_for(const Args& A) { return V::none(); }"]),
    "expansion_assets": (["V f_install(const Args& A);", "V cls_TemplateAtlas();"],
                         ["V f_install(const Args& A) { return V::none(); }",
                          "V cls_TemplateAtlas() { static V c = V::func([](const Args& A) { return A.pos.empty() ? V::dict() : py::dict_of(A.pos[0]); }); return c; }"]),
    "gc_policy": (["V module_ns();"], [NOOP_MODULE % "gc_policy"]),
    "hero_guard": (["V module_ns();"], [NOOP_MODULE % "hero_guard"]),
    "native_assets": (["V f_load_original_assets(const Args& A);"],
                      ["V f_load_original_assets(const Args& A) { pvz::gfx::install_atlases(match_of(A.pos.at(0))); return py_dict({{SV(\"tile\"), V(48.0)}}); }"]),
    "native_bytecode": (["V f_instruction_window(const Args& A);", "V f_instructions(const Args& A);", "V f_decode(const Args& A);"],
                        ["V f_instruction_window(const Args& A) { return V::list(); }",
                         "V f_instructions(const Args& A) { return V::list(); }",
                         "V f_decode(const Args& A) { return V::none(); }"]),
    "native_candidates": (["V module_ns();"], [NOOP_MODULE % "native_candidates"]),
    "native_multiworker": (["V cls_JobSystem();", "V f_configured_workers(const Args& A);", "V f_fastpath_enabled(const Args& A);"],
                           ["V cls_JobSystem() { static V c = V::func([](const Args& A) { return py::noop_module(SV(\"JobSystem\")); }); return c; }",
                            "V f_configured_workers(const Args& A) { return V(0.0); }",
                            "V f_fastpath_enabled(const Args& A) { return V(true); }"]),
    "performance": (["V f_enabled(const Args& A);", "V cls_FramePixels();"],
                    ["V f_enabled(const Args& A) { return V(true); }",
                     "V cls_FramePixels() { static V c = V::func([](const Args& A) { return py::noop_module(SV(\"FramePixels\")); }); return c; }"]),
    "pvp64_sprite_atlas": (["V f_ground_gap(const Args& A);"],
                           ["// transparent rows under the pose's lowest opaque pixel / canvas height, from the baked atlas",
                            "V f_ground_gap(const Args& A) { return py::atlas_ground_gap(A.pos.at(1)); }"]),
    "pvp67_assets": (["V f_taco(const Args& A);"], ["V f_taco(const Args& A) { return py::atlas_image(SV(\"taco\")); }"]),
    "world_view": (["V f_sun_scale(const Args& A);"],
                   ["// world_view.sun_scale: 1 for <= 25 sun, else min(2.4, sqrt(amount/25))",
                    "V f_sun_scale(const Args& A) { double a = A.pos.at(0).num(); return V(a <= 25 ? 1.0 : std::min(2.4, std::sqrt(a / 25.0))); }"]),
}

for m, (decls, defs) in SHIMS.items():
    h = ["// Shim for modkit/pvp/%s.py (presentation/tooling module) - see tools/gen_shims.py" % m,
         "#pragma once", '#include "sim/pvp/pvprt.h"', "namespace pvz { namespace pm_%s {" % m, "void init();"]
    h += decls
    h.append("}}  // namespace pvz::pm_%s" % m)
    c = ['#include "sim/pvp/shim/pm_%s.h"' % m, '#include "sim/pvp/hand/graphics.h"', "#include <cmath>", "#include <algorithm>",
         "namespace pvz { namespace pm_%s {" % m]
    c += defs
    loader = any("load_()" in d for d in defs)
    c.append("void init() { static bool done = false; if (done) return; done = true;%s }" % (" load_();" if loader else ""))
    c.append("}}  // namespace pvz::pm_%s" % m)
    (OUT / ("pm_%s.h" % m)).write_text("\n".join(h) + "\n", encoding="utf-8")
    (OUT / ("pm_%s.cpp" % m)).write_text("\n".join(c) + "\n", encoding="utf-8")
print(len(SHIMS), "shims")
