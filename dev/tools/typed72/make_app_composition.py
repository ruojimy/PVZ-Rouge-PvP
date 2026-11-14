"""Generate the app-only composition after validating every input in memory.

The independent driver/probes are read-only reference inputs. Reuse the pinned
historical strip rules, with null statements instead of empty text to preserve
C++ if/else structure, plus production_observers' reviewed body contracts.

--check [--out PATH] compares bytes without writing (including no __pycache__).
Generation never removes a tree: unknown output files/directories, links and
junctions are errors. Only known, changed generated files are updated, and only
after all input contracts and the entire existing output tree have passed.
"""
import sys

# Set this before even stdlib imports: --check must not create bytecode files.
sys.dont_write_bytecode = True

import argparse
import ast
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import stat

if __package__:
    from .production_observers import ObserverContractError, RULES, transform, validate_observers
else:
    # Embedded Python's isolated (-I) mode omits the script directory.
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from production_observers import ObserverContractError, RULES, transform, validate_observers

ROOT = Path(__file__).resolve().parents[2]
DRIVER = ROOT / 'build/typed72-match-v1'
OUT = ROOT / 'src/sim/typed72_app/composition'
STRIP_SHA256 = '19597600f3623a13ef5d645caa21bd50bd5ce0a0dd1771421526046bf25f157b'


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def load_legacy_strip(path):
    """Load ONLY reviewed definitions; never execute the stage generator body."""
    raw = path.read_bytes()
    if digest(raw) != STRIP_SHA256:
        raise ObserverContractError('unreviewed make_stripped.py: ' + str(path))
    source = raw.decode('utf8')
    old = 'out.append(text[pos:m.start()]);removed.append('
    if source.count(old) != 1:
        raise ObserverContractError('historical strip statement slot changed')
    source = source.replace(old, "out.append(text[pos:m.start()]+';');removed.append(", 1)
    wanted = {'RECORD_CALLS', 'LOGS', 'PATTERN', 'balanced_end', 'strip'}
    nodes = []
    found = []
    for node in ast.parse(source, filename=str(path)).body:
        name = None
        if isinstance(node, ast.FunctionDef):
            name = node.name
        elif isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            name = node.targets[0].id
        if name in wanted:
            nodes.append(node)
            found.append(name)
    if set(found) != wanted or len(found) != len(wanted):
        raise ObserverContractError('historical strip definitions changed')
    namespace = {'re': re}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), 'exec'), namespace)
    return namespace['strip']


# These are metadata/configuration changes, not blanket replacements of similarly
# named fields. Pin the full known report prefix, not every "production" boolean.
REPORT_PREFIX = ('J report={{"backend_requested","typed72-integrated"},'
                 '{"backend_actual","typed72-probe-composition-e1"},'
                 '{"production_composition",false},{"fallback_count",0},')
APP_REPORT_PREFIX = REPORT_PREFIX.replace('typed72-probe-composition-e1', 'typed72-app-composition-e2').replace(
    '{"production_composition",false}', '{"production_composition",true}')
DRIVER_PATCHES = (
    ('release_fixture_retention',
     'bool release_fixtures=std::getenv("MATCH_RELEASE_FIXTURES")!=nullptr;',
     'bool release_fixtures=true;  // app composition: no fixture retention'),
    ('report_app_composition', REPORT_PREFIX, APP_REPORT_PREFIX),
)


def transform_driver(text):
    records = []
    for name, old, new in DRIVER_PATCHES:
        if text.count(old) != 1:
            raise ObserverContractError(f'match_probe.cpp: expected one {name} source')
        text = text.replace(old, new, 1)
        records.append({'transform': name, 'expected_count': 1,
                        'source_text_sha256': digest(old.encode('utf8')),
                        'source': old, 'replacement': new})
    return text, records


def build_outputs(driver=DRIVER):
    """Read/validate ALL sources and return deterministic UTF-8 output bytes."""
    strip = load_legacy_strip(driver / 'make_stripped.py')
    sources = {}
    for src in sorted((driver / 'probes').iterdir()):
        if not src.is_file() or src.is_symlink() or is_reparse_point(src):
            raise ObserverContractError('unexpected probe source entry: ' + str(src))
        sources['probes/' + src.name] = src
    for name in ('match_probe.cpp', 'frame_layer.inc', 'snapshot_layer.inc'):
        sources[name] = driver / name
    missing = set(RULES) - set(sources)
    if missing:
        raise ObserverContractError('missing reviewed probe sources: ' + ', '.join(sorted(missing)))
    outputs = {}
    manifest = {
        'source': 'build/typed72-match-v1',
        'production_observers_version': 1,
        'body_sha256_encoding': 'UTF-8, CRLF normalized to LF, including body braces',
        'legacy_strip': {'source_sha256': STRIP_SHA256, 'replacement': 'null C++ statement'},
        'files': {},
    }
    for name, src in sources.items():
        raw = src.read_bytes()
        original = raw.decode('utf8').replace('\r\n', '\n')
        new, observers = transform(name, original)
        new, removed = strip(new) if src.suffix in ('.cpp', '.inc') else (new, [])
        driver_changes = []
        if name == 'match_probe.cpp':
            new, driver_changes = transform_driver(new)
        validate_observers(name, new, after_legacy=True)
        outputs[name] = new.encode('utf8')
        manifest['files'][name] = {
            'source_sha256': digest(raw),
            'generated_sha256': digest(outputs[name]),
            'removed': removed,
            'production_observers': observers,
            'production_changes': driver_changes,
        }
    outputs['MANIFEST.json'] = (json.dumps(manifest, ensure_ascii=False, indent=1) + '\n').encode('utf8')
    validate_output_names(outputs)
    return outputs


def is_reparse_point(path):
    """Reject all Windows reparse points, including junctions on Python 3.8."""
    try:
        info = path.lstat()
    except FileNotFoundError:
        return False
    return bool(getattr(info, 'st_file_attributes', 0)
                & getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 0x400))


def validate_output_names(outputs):
    """Reject traversal and Windows case collisions even for a custom --out."""
    seen = set()
    for name, data in outputs.items():
        path = PurePosixPath(name)
        if (not name or path.is_absolute() or '..' in path.parts or '.' in path.parts
                or '\\' in name or ':' in name or path.as_posix() != name
                or name.casefold() in seen or not isinstance(data, bytes)):
            raise ObserverContractError('invalid generated output entry: ' + name)
        seen.add(name.casefold())
    for name in outputs:
        for parent in PurePosixPath(name).parents:
            if str(parent).casefold() in seen:
                raise ObserverContractError('generated file/directory collision: ' + name)


def inventory_output(out, outputs):
    """Preflight the COMPLETE tree before any mkdir/write; never follow links."""
    validate_output_names(outputs)
    allowed_dirs = {str(parent) for name in outputs for parent in PurePosixPath(name).parents if str(parent) != '.'}
    # A linked ancestor could redirect even an otherwise ordinary output path.
    for ancestor in (out, *out.parents):
        if ancestor.is_symlink() or is_reparse_point(ancestor):
            raise ObserverContractError('linked output path is not allowed: ' + str(ancestor))
    if not out.exists():
        return {}
    if not out.is_dir():
        raise ObserverContractError('output is not a directory: ' + str(out))
    existing = {}

    def visit(directory, prefix=''):
        for child in sorted(directory.iterdir()):
            name = prefix + child.name
            if child.is_symlink() or is_reparse_point(child):
                raise ObserverContractError('linked output entry is not allowed: ' + name)
            if child.is_dir():
                if name not in allowed_dirs:
                    raise ObserverContractError('unexpected output directory (not deleted): ' + name)
                visit(child, name + '/')
            elif not child.is_file() or name not in outputs:
                raise ObserverContractError('unexpected output file (not deleted): ' + name)
            else:
                existing[name] = child.read_bytes()
    visit(out)
    return existing


def output_changes(outputs, existing):
    """Pure comparison, shared by check and write modes."""
    validate_output_names(outputs)
    extra = set(existing) - set(outputs)
    if extra:
        raise ObserverContractError('unexpected output files (not deleted): ' + ', '.join(sorted(extra)))
    return sorted(name for name, data in outputs.items() if existing.get(name) != data)


def sync_output(outputs, out, check=False):
    existing = inventory_output(out, outputs)
    changed = output_changes(outputs, existing)
    if not check:
        # Reaching here means every input AND existing output was validated.
        # Do not rmtree/unlink/prune: all writes have an explicit generated name.
        for name in changed:
            target = out / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(outputs[name])
    return changed


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='compare expected bytes without writing')
    parser.add_argument('--out', type=Path, default=OUT, help='composition directory (default: app composition)')
    args = parser.parse_args(argv)
    try:
        outputs = build_outputs()
        changed = sync_output(outputs, args.out.absolute(), check=args.check)
    except (ObserverContractError, OSError, UnicodeError) as error:
        print('composition refused: ' + str(error), file=sys.stderr)
        return 2
    if args.check and changed:
        print('composition differs: ' + ', '.join(changed), file=sys.stderr)
        return 1
    print('composition', args.out, 'checked' if args.check else 'updated', len(changed), 'files')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
