"""PvP75 激光豆 hooks in the translated Application / battle_view (re-apply after UI regeneration).

The behaviour lives in src/ui/hand/pvp75_ui.cpp; these one-line hooks only route
world clicks, cancel/jump guards and the aiming range hint there.
    python tools/pvp75_ui_hooks.py           apply (idempotent)
    python tools/pvp75_ui_hooks.py --check   fail when a hook is missing (build gate)
"""
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
CHECK = '--check' in sys.argv


def apply(rel, hooks):
    path = ROOT / rel
    raw = path.read_bytes().decode('utf8'); nl = '\r\n' if '\r\n' in raw else '\n'
    text = raw.replace('\r\n', '\n')
    for marker, start, anchor, addition, before in hooks:
        if marker in text: continue
        if anchor is None:  # file head: never splits an include pair other hooks pin
            text = addition + text; continue
        base = text.index(start) if start else 0
        at = text.find(anchor, base)
        if at < 0 or (start and text.find(anchor, base) != at): raise RuntimeError('PvP75 hook anchor missing: ' + marker)
        if not start and text.count(anchor) != 1: raise RuntimeError('PvP75 hook anchor ambiguous: ' + marker)
        cut = at if before else at + len(anchor)
        text = text[:cut] + addition + text[cut:]
    out = text.replace('\n', nl)
    if out == raw: return False
    if CHECK: raise SystemExit('Stale PvP75 UI hooks in ' + rel + ': run tools/pvp75_ui_hooks.py')
    path.write_bytes(out.encode('utf8')); return True


INCLUDE = ('// PvP75 laser include', None, None, '#include "ui/hand/pvp75_ui.h" // PvP75 laser include' + chr(10), False)
changed = apply('src/ui/gen/pm_app.cpp', [
    INCLUDE,
    ('// PvP75 laser click', 'V C_Application::m_world_click(',
     '    if (((L_right).truthy() && (callm(self(), SY("cannon_aiming"), Args{})).truthy())) {\n',
     '    if(pvz::pvp75_ui::world_click(self(),L_pos,L_right))return V::none(); // PvP75 laser click\n', True),
    ('// PvP75 laser cancel', 'V C_Application::m_cancel_battle_action(',
     'V C_Application::m_cancel_battle_action(const Args& A) {\n',
     '    pvz::pvp75_ui::cancel(self()); // PvP75 laser cancel\n', False),
    ('// PvP75 laser jump guard', 'V C_Application::m_world_touch_can_jump(',
     '    L_point = callm(a_renderer, SY("world_point"), Args{L_pos});\n',
     '    if(pvz::pvp75_ui::blocks_jump(self(),L_pos))return V(false); // PvP75 laser jump guard\n', True),
    ('// PvP75 laser over turn', 'V C_Application::m_turn_plant_at(',
     '    if ((callm(self(), SY("cannon_at"), Args{L_x, L_y})).truthy()) {\n        return V::none();\n    }\n',
     '    if(!pvz::pvp75_ui::laser_at(self(),L_x,L_y).is_none())return V::none(); // PvP75 laser over turn\n', False),
])
changed |= apply('src/ui/gen/pm_battle_view.cpp', [
    INCLUDE,
    ('// PvP75 laser ring', 'V f_draw_placement_ring(',
     '    V L_side = A.get(6, SY("side"), nullptr, "draw_placement_ring");\n',
     '    pvz::pvp75_ui::draw_laser_ring(L_r,L_view,L_state,L_game,L_terrain,L_players,L_side); // PvP75 laser ring\n', False),
])
changed |= apply('src/ui/gen/pm_performance_probe.cpp', [
    INCLUDE,
    ('// PvP75 laser diagnostic', None,
     '        pvz::setattr(L_app, SY("move_inputs"), V::func([=, this](const Args& A) -> V { V L_dt = A.get(0, SY("dt"), nullptr); return V::none(); }));\n',
     '        pvz::pvp75_ui::diagnostic_lasers(L_app,L_b,a_config); // PvP75 laser diagnostic (after the neutral seq-1 inputs)\n', True),
])
def replace(rel, edits):
    """(marker, old, new): `new` contains the marker; applied once, idempotent, --check aware."""
    path = ROOT / rel
    raw = path.read_bytes().decode('utf8'); nl = '\r\n' if '\r\n' in raw else '\n'
    text = raw.replace('\r\n', '\n')
    for marker, old, new in edits:
        if marker in text: continue
        if text.count(old) != 1: raise RuntimeError('PvP75 replace anchor missing or ambiguous: ' + marker)
        text = text.replace(old, new)
    out = text.replace('\n', nl)
    if out == raw: return False
    if CHECK: raise SystemExit('Stale PvP75 hooks in ' + rel + ': run tools/pvp75_ui_hooks.py')
    path.write_bytes(out.encode('utf8')); return True


# PvP75 replay cache: pure transform chains are keyed without alpha and with 1/4-degree rotations
# (src/core/render_cache.cpp native_replay_normalize); the outer alpha is set at blit time.
changed |= replace('src/sim/pvp/gen/pm_native_animation.cpp', [
    ('// PvP75 replay normalize', '              L_json = py::stdlib_module(SV("json"));\n',
     '              V pvp75_alpha;bool pvp75_alpha_set=false;const V pvp75_norm=pvz::native_replay_normalize(L_description,pvp75_alpha,pvp75_alpha_set); // PvP75 replay normalize\n'
     '              L_json = py::stdlib_module(SV("json"));\n'),
    # After the per-frame identity memo (keyed on the original description, which the frame owns),
    # the key and the rebuilt surface use the normalised copy; PvP74.1's key lines stay untouched.
    ('// PvP75 normalized description', '                  L_identity = V::tuple({py::id(L_description), (!py_is(L_area, V::none()) ? V(py::tuple_it(L_area)) : V(V::none())), L_scale});\n',
     '                  L_identity = V::tuple({py::id(L_description), (!py_is(L_area, V::none()) ? V(py::tuple_it(L_area)) : V(V::none())), L_scale});\n'
     '                  L_description=pvp75_norm; // PvP75 normalized description\n'),
    ('// PvP75 cache bytes', '    a_cache_limit = ((V(32.0) * V(1024.0)) * V(1024.0));\n',
     '    a_cache_limit = V(pvz::native_replay_cache_bytes()); // PvP75 cache bytes\n'),
    ('/* PvP75 cache entries */', '(py::len(a_cache) >= V(512.0))',
     '(py::len(a_cache) >= V(pvz::native_replay_cache_entries()) /* PvP75 cache entries */)'),
    ('// PvP75 blit alpha', '              (void)(callm(L_screen, SY("blit"), Args({L_surface, L_pos}, ',
     '              if(pvp75_alpha_set)(void)callm(L_surface,SY("set_alpha"),Args{pvp75_alpha}); // PvP75 blit alpha\n'
     '              (void)(callm(L_screen, SY("blit"), Args({L_surface, L_pos}, '),
])

print('PvP75 UI hooks:', 'checked' if CHECK else ('applied' if changed else 'unchanged'))
