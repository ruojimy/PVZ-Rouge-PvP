"""Apply or check the ranked Golden Bloom placement hook after UI translation."""
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
CHECK = '--check' in sys.argv
CRLF, LF = chr(13) + chr(10), chr(10)


def replace(rel, original, previous, patched):
    path = ROOT / rel
    raw = path.read_bytes().decode('utf8')
    nl = CRLF if CRLF in raw else LF
    text = raw.replace(CRLF, LF)
    if text.count(patched) == 1:
        return False
    if CHECK:
        raise SystemExit('Stale PvP76 r3 hooks in ' + rel + ': run tools/pvp76r3_hooks.py')
    old = previous if previous in text else original
    if text.count(old) != 1:
        raise RuntimeError('PvP76 r3 hook anchor missing or ambiguous in ' + rel)
    path.write_bytes(text.replace(old, patched).replace(LF, nl).encode('utf8'))
    return True



# A guest's input succeeds when queued, before the host accepts or rejects it.
# Use the same published lock and clock as the HUD before sending a pickup.
original = '''            (void)(callm(self(), SY("input"), Args({L_side, SV("collect")}, {{SY("resource"), rd(L_resource, SV("id"))}})));
            return V::none();
'''
previous = '''            {V collect_error = callm(self(), SY("input"), Args({L_side, SV("collect")}, {{SY("resource"), rd(L_resource, SV("id"))}}));  // PvP76 r3 bloom click
            if (!(collect_error).truthy() || !(py::m_get(a_state, SV("selected_card"))).truthy()) return V::none();}
'''
patched = '''            // PvP76 r3 bloom click: a guest queues input before the host handles it.
            const V seat = callm(self(), SY("local_seat"), Args{L_side});
            const V players = py::m_get(L_battle, SV("players"), V::dict());
            const V player = py::m_get(players, seat, V::dict());
            const bool pickup_locked = py::m_get(player, SV("collect_locked_until"), V(0.0))
                                     > py::m_get(L_battle, SV("time"), V(0.0));
            if (!pickup_locked || !py::m_get(a_state, SV("selected_card")).truthy()) {
                (void)callm(self(), SY("input"), Args({L_side, SV("collect")}, {{SY("resource"), rd(L_resource, SV("id"))}}));
                return V::none();
            }
'''
changed = replace('src/ui/gen/pm_app.cpp', original, previous, patched)
print('PvP76 r3 hooks:', 'applied' if changed else ('checked' if CHECK else 'unchanged'))
