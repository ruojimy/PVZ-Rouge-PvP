"""PvP76 r2 hooks in translated modules (re-apply after a UI / PvP module regeneration).

Behaviour lives in src/sim/pvp/hand/pvp76r2_coop.cpp; these short hooks route to it:
  * coop_progress: the run remembers the day its zombie-secret count began
    ("zombie_secret_from", day 1; runs saved before r2 count every cleared day, user 11-22) and
    publishes the run's zombie secrets in room.pve;
  * room._start_pve: a co-op battle's dormant zombie seat carries those secrets;
  * co-op room page: one line lists them.
    python tools/pvp76r2_hooks.py           apply (idempotent)
    python tools/pvp76r2_hooks.py --check   fail when a hook is missing (build gate)
"""
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
CHECK = '--check' in sys.argv
CRLF, LF = chr(13) + chr(10), chr(10)
INCLUDE = '#include "sim/pvp/hand/pvp76r2_coop.h" // PvP76 r2 coop include'


def replace(rel, edits):
    """(marker, old, new): `new` contains the marker; applied once, idempotent, --check aware."""
    path = ROOT / rel
    raw = path.read_bytes().decode('utf8')
    nl = CRLF if CRLF in raw else LF
    text = raw.replace(CRLF, LF)
    for marker, old, new in edits:
        if marker in text: continue
        if text.count(old) != 1: raise RuntimeError('PvP76 r2 hook anchor missing or ambiguous: %s (%s)' % (marker, rel))
        text = text.replace(old, new)
    out = text.replace(LF, nl)
    if out == raw: return False
    if CHECK: raise SystemExit('Stale PvP76 r2 hooks in ' + rel + ': run tools/pvp76r2_hooks.py')
    path.write_bytes(out.encode('utf8'))
    return True


changed = replace('src/sim/pvp/gen/pm_coop_progress.h', [
    ('// PvP76 r2 zombie secret start', '    V a_applied;' + LF,
     '    V a_applied;' + LF + '    V a_zombie_from;  // PvP76 r2 zombie secret start (not a Python slot)' + LF),
])
changed |= replace('src/sim/pvp/gen/pm_coop_progress.cpp', [
    ('// PvP76 r2 coop include', '#include "sim/pvp/gen/pm_teams.h"' + LF,
     '#include "sim/pvp/gen/pm_teams.h"' + LF + INCLUDE + LF),
    ('// PvP76 r2 reset', '    a_day = V(1.0);' + LF + '    a_campaigns = py_dict({});' + LF,
     '    a_day = V(1.0);' + LF + '    a_zombie_from = V(1.0);  // PvP76 r2 reset' + LF + '    a_campaigns = py_dict({});' + LF),
    ('// PvP76 r2 load', '            a_day = py::max_it(V::list({V(1.0), py::int_(rd(L_value, SV("day")))}), py::Key(), V());' + LF,
     '            a_day = py::max_it(V::list({V(1.0), py::int_(rd(L_value, SV("day")))}), py::Key(), V());' + LF
     + '            a_zombie_from = py::max_it(V::list({V(1.0), py::int_(py::m_get(L_value, SV("zombie_secret_from"), V(1.0)))}), py::Key(), V());  // PvP76 r2 load' + LF),
    ('// PvP76 r2 migrate', '        a_day = pvz::getattr(L_initial, SY("day"));' + LF,
     '        a_day = pvz::getattr(L_initial, SY("day"));' + LF + '        a_zombie_from = V(1.0);  // PvP76 r2 migrate' + LF),
    ('// PvP76 r2 save', '    L_text = py::stdlib_call(SV("json.dumps"), Args({L_value}, {{SY("ensure_ascii"), V(false)}, {SY("indent"), V(1.0)}}));' + LF,
     '    pvz::setitem(L_value, SV("zombie_secret_from"), a_zombie_from);  // PvP76 r2 save' + LF
     + '    L_text = py::stdlib_call(SV("json.dumps"), Args({L_value}, {{SY("ensure_ascii"), V(false)}, {SY("indent"), V(1.0)}}));' + LF),
    ('// PvP76 r2 sync', '    pvz::setitem(L_pve, SV("run_day"), a_day);' + LF,
     '    pvz::setitem(L_pve, SV("run_day"), a_day);' + LF
     + '    pvz::setitem(L_pve, SV("coop_zombie_from"), a_zombie_from);pvz::setitem(L_pve, SV("coop_zombie_secrets"), pvz::pvp76r2::coop_zombie_secrets(a_run_id, a_zombie_from, a_day));  // PvP76 r2 sync' + LF),
])
changed |= replace('src/ui/gen/pm_room.cpp', [
    ('// PvP76 r2 coop include', '#include "sim/pvp/gen/pm_coop_progress.h"' + LF,
     '#include "sim/pvp/gen/pm_coop_progress.h"' + LF + INCLUDE + LF),
    ('// PvP76 r2 coop zombie secrets', '    pvz::setitem(a_decks, SV("zombie"), V::list({}));' + LF,
     '    pvz::setitem(a_decks, SV("zombie"), (a_mode == SV("coop")) ? pvz::pvp76r2::coop_battle_secrets(a_pve) : V::list({}));  // PvP76 r2 coop zombie secrets' + LF),
])
LINE = 'SV("各自产阳光；天降阳光与金币共用")}));'
for rel, include_anchor in (('src/ui/gen/pm_pve_ui.cpp', '#include "ui/hand/seat_view.h"' + LF),  # after the PvP74.1 include
                            ('src/ui/gen/pm_app.cpp', '#include "ui/hand/pvp76_ui.h" // PvP76 ui include' + LF)):
    changed |= replace(rel, [
        ('// PvP76 r2 coop include', include_anchor, include_anchor + INCLUDE + LF),
        ('/* PvP76 r2 coop secrets line */', LINE,
         'SV("各自产阳光；天降阳光与金币共用"), pvz::pvp76r2::coop_secret_line(L_pve) /* PvP76 r2 coop secrets line */}));'),
    ])
print('PvP76 r2 hooks:', 'applied' if changed else ('checked' if CHECK else 'unchanged'))
