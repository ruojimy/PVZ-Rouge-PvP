"""PvP76 hooks in the translated Application / performance module (re-apply after UI regeneration).

Behaviour lives in src/ui/hand/pvp76_ui.cpp; these short hooks route to it.
    python tools/pvp76_ui_hooks.py           apply (idempotent)
    python tools/pvp76_ui_hooks.py --check   fail when a hook is missing (build gate)
"""
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
CHECK = '--check' in sys.argv
CRLF, LF = chr(13) + chr(10), chr(10)


def _load(rel):
    path = ROOT / rel
    raw = path.read_bytes().decode('utf8')
    return path, raw, (CRLF if CRLF in raw else LF), raw.replace(CRLF, LF)


def _store(path, raw, nl, text, rel):
    out = text.replace(LF, nl)
    if out == raw: return False
    if CHECK: raise SystemExit('Stale PvP76 hooks in ' + rel + ': run tools/pvp76_ui_hooks.py')
    path.write_bytes(out.encode('utf8')); return True


def replace(rel, edits):
    """(marker, old, new): `new` contains the marker; applied once, idempotent, --check aware."""
    path, raw, nl, text = _load(rel)
    for marker, old, new in edits:
        if marker in text: continue
        if text.count(old) != 1: raise RuntimeError('PvP76 hook anchor missing or ambiguous: ' + marker)
        text = text.replace(old, new)
    return _store(path, raw, nl, text, rel)


def replace_line(rel, edits):
    """(marker, unique line prefix, replacement line): replaces one whole generated line."""
    path, raw, nl, text = _load(rel)
    lines = text.split(LF)
    for marker, prefix, new in edits:
        if any(marker in l for l in lines): continue
        hits = [i for i, l in enumerate(lines) if l.startswith(prefix)]
        if len(hits) != 1: raise RuntimeError('PvP76 line anchor missing or ambiguous: ' + marker)
        lines[hits[0]] = new
    return _store(path, raw, nl, LF.join(lines), rel)


changed = replace('src/ui/gen/pm_app.cpp', [
    ('// PvP76 ui include', '#include "ui/hand/pvp75_ui.h" // PvP75 laser include' + LF,
     '#include "ui/hand/pvp75_ui.h" // PvP75 laser include' + LF + '#include "ui/hand/pvp76_ui.h" // PvP76 ui include' + LF),
    # 克苏鲁之仆 / test-mode Bosses: preview at the pointer, never snapped to a grave exit.
    ('// PvP76 free summon preview',
     '    L_error = SV("");' + LF + '    L_plan = V::none();' + LF + '    try {' + LF + '        L_validator = pm_preview::C_PreviewBattle::m_from_snapshot(',
     '    L_error = SV("");' + LF + '    L_plan = V::none();' + LF
     + '    if(pvz::pvp76_ui::free_summon_preview(self(),L_card,L_x,L_y))return V::none(); // PvP76 free summon preview' + LF
     + '    try {' + LF + '        L_validator = pm_preview::C_PreviewBattle::m_from_snapshot('),
])

# Performance evidence must never ask a typed battle for battle.g (whole-world projection,
# and every later command re-projects once those records are handed out).
G = 'rdm(pvz::getattr(L_b, SY("g")), &Obj::僵尸, SV("僵尸"))'
changed |= replace('src/ui/gen/pm_performance.cpp', [
    ('// PvP76 perf include', '#include "ui/gen/pm_performance.h"' + LF,
     '#include "ui/gen/pm_performance.h"' + LF + '#include "ui/hand/pvp76_ui.h" // PvP76 perf include' + LF),
    ('/* PvP76 crowd count */', '(py::len(rdm(pvz::getattr(L_battle, SY("g")), &Obj::僵尸, SV("僵尸"))) < V(48.0))',
     '(V(pvz::pvp76_perf::zombie_count(L_battle) /* PvP76 crowd count */) < V(48.0))'),
    ('/* PvP76 crowd sample */', '            if ((py::len(' + G + ') >= V(48.0))) {',
     '            if (!pvz::pvp76_perf::typed(L_b) /* PvP76 crowd sample */ && (V(pvz::pvp76_perf::zombie_count(L_b)) >= V(48.0))) {'),
])
changed |= replace_line('src/ui/gen/pm_performance.cpp', [
    ('// PvP76 population', '            (void)(py::m_append(a_population, py_dict({{SV("elapsed"), (L_now - a_started)}',
     '            (void)(py::m_append(a_population, [&]{V row=pvz::pvp76_perf::population(a_app,L_b);pvz::setitem(row,SV("elapsed"),(L_now - a_started));return row;}())); // PvP76 population'),
    ('// PvP76 current population', '        pvz::setitem(L_report, SV("current_population"), py_dict(',
     '        pvz::setitem(L_report, SV("current_population"), pvz::pvp76_perf::population(a_app,L_b)); // PvP76 current population'),
])
print('PvP76 UI hooks:', 'applied' if changed else ('checked' if CHECK else 'unchanged'))
