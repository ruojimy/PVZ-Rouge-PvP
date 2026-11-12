"""Regenerate only the AISeat boundary methods changed for the typed AI path
(observation: reset_observation/battle_tick; r22 planner: battle_tick/ensure_agent).

The current general translator also emits unrelated metadata/import rewrites.
Do not churn the rest of the already audited lobby module or its class headers.
The project-owned Python input remains the source of these method bodies.
--check verifies them without writing; no import bytecode is produced.
"""
import argparse
from pathlib import Path
import sys

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from pvp2cpp import Gen, GEN_UI
from production_observers import body_span

METHODS = ('reset_observation', 'battle_tick', 'ensure_agent')
TARGET = ROOT / 'src/ui/gen/pm_lobby_room.cpp'


def expected():
    GEN_UI[0] = True
    generator = Gen('lobby_room')
    _, generated = generator.run()
    if generator.todo:
        raise ValueError('Untranslated lobby constructs: ' + repr(generator.todo))
    old = TARGET.read_text(encoding='utf-8')
    changes = []
    for method in METHODS:
        signature = 'V C_AISeat::m_%s(const Args& A)' % method
        start, end = body_span(old, signature)
        gs, ge = body_span(generated, signature)
        changes.append((start, end, generated[gs:ge]))
    new = old
    for start, end, body in sorted(changes, reverse=True):
        new = new[:start] + body + new[end:]
    return old, new


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    old, new = expected()
    if old != new:
        if args.check:
            print('AISeat observation boundary is stale', file=sys.stderr)
            return 1
        TARGET.write_bytes(new.encode('utf-8'))
    print('AISeat typed observation boundary: ' + ('checked' if args.check else 'generated'))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
