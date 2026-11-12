"""Conservative source census for typed migration. Unresolved reachability stays in the denominator.

This is an inventory, NOT a coverage or behavior-equivalence claim. AST line
ranges are never presented as raw bytecode offsets. Current hand C++ overrides
are separate obligations; Python source alone is not the effective PvP72 rule.
"""
import argparse
import ast
import collections
import dis
import hashlib
import json
import marshal
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REFERENCE = ROOT.parent / 'PVZ-Rouge-v1.4.8/next-pvp71'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def file_info(p):
    data = p.read_bytes()
    try:
        name = p.relative_to(ROOT).as_posix()
    except ValueError:
        name = str(p)
    return dict(path=name, sha256=digest(data), bytes=len(data))


def code_objects(code, path='<module>'):
    yield path, code
    for i, constant in enumerate(code.co_consts):
        if isinstance(constant, types.CodeType):
            yield from code_objects(constant, path + '/' + constant.co_name + ':' + str(i))


def source_name(n):
    if isinstance(n, ast.Name):
        return n.id
    if isinstance(n, ast.Attribute):
        return source_name(n.value) + '.' + n.attr
    return '<dynamic:' + type(n).__name__ + '>'


class Census(ast.NodeVisitor):
    def __init__(self, info, layer, lines):
        self.info, self.layer, self.lines = info, layer, lines
        self.scope = ['<module>']
        self.functions, self.branches = [], []

    def visit_ClassDef(self, n):
        self.scope.append(n.name)
        self.generic_visit(n)
        self.scope.pop()

    def visit_FunctionDef(self, n):
        self.scope.append(n.name)
        self.record_function(n)
        self.generic_visit(n)
        self.scope.pop()

    visit_AsyncFunctionDef = visit_FunctionDef

    def record_function(self, n):
        # Calls/read/write observations are syntactic. They do not establish reachability.
        calls, reads, writes = set(), set(), set()
        todo = [n]
        while todo:
            item = todo.pop()
            if item is not n and isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
                continue
            if isinstance(item, ast.Call):
                calls.add(source_name(item.func))
            if isinstance(item, ast.Subscript):
                key = item.slice.value if isinstance(item.slice, ast.Index) else item.slice
                if isinstance(key, ast.Constant) and isinstance(key.value, str):
                    (reads if isinstance(item.ctx, ast.Load) else writes).add(key.value)
            todo.extend(ast.iter_child_nodes(item))
        start = getattr(n, 'lineno', 1)
        end = getattr(n, 'end_lineno', len(self.lines))
        self.functions.append(dict(id=self.info['path'] + ':' + '.'.join(self.scope),
            source=self.info, layer=self.layer, recovered_lines=[start, end],
            recovered_body_sha256=digest(''.join(self.lines[start-1:end]).encode('utf8')),
            raw_bytecode_offsets=None, raw_offset_status='unmapped',
            calls=sorted(calls), literal_field_reads=sorted(reads), literal_field_writes=sorted(writes),
            typed_implementation=None, status='unmigrated', evidence=[],
            reachability='unresolved; retained in denominator'))

    def generic_visit(self, n):
        if isinstance(n, (ast.If, ast.IfExp, ast.For, ast.While, ast.Try, ast.BoolOp, ast.comprehension)):
            line = getattr(n, 'lineno', None)
            self.branches.append(dict(id=self.info['path'] + ':' + str(line) + ':' + str(len(self.branches)),
                function='.'.join(self.scope), kind=type(n).__name__, recovered_line=line,
                ast_sha256=digest(ast.dump(n, include_attributes=False).encode('utf8')),
                status='not_instrumented', execution_count=None, assertion_evidence=[]))
        super().generic_visit(n)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out', required=True)
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    sources = {}
    for p in (ROOT / 'extract/original').rglob('*.py'):
        sources[p] = 'recovered_original'
    modules = (ROOT / 'tools/sim_modules.txt').read_text(encoding='utf8').split()
    for module in modules:
        if module == 'patch1501':
            p = REFERENCE / 'modkit/pvzrouge_runtime_patch_source_20260904.py'
        else:
            choices = [ROOT / 'tools/pvp72_sources' / (module + '.py'),
                       ROOT / 'tools/testshim' / (module + '.py'),
                       REFERENCE / 'modkit/pvp' / (module + '.py')]
            p = next((x for x in choices if x.exists()), choices[-1])
        sources[p] = 'pvp_or_patch_input'
    # Include AI and UI-facing room/replay/snapshot adapters: they can mutate or
    # observe battle state even when omitted from sim_modules.txt.
    for directory in (ROOT / 'tools/pvp72_sources', REFERENCE / 'AI/brain'):
        for p in directory.rglob('*.py'):
            sources.setdefault(p, 'additional_state_owner_or_adapter')
    for module in ('room', 'replay', 'native_snapshot_worker', 'native_multiworker', 'rv_runtime', 'rv_snapshot', 'rv_worker'):
        p = ROOT / 'tools/pvp72_sources' / (module + '.py')
        if not p.exists():
            p = REFERENCE / 'modkit/pvp' / (module + '.py')
        if p.exists():
            sources.setdefault(p, 'additional_state_owner_or_adapter')
    functions, branches, errors = [], [], []
    for p, layer in sorted(sources.items()):
        try:
            raw = p.read_text(encoding='utf-8-sig')
            tree = ast.parse(raw)
            census = Census(file_info(p), layer, raw.splitlines(True))
            census.record_function(tree)
            census.visit(tree)
            functions.extend(census.functions)
            branches.extend(census.branches)
        except Exception as exc:
            errors.append(dict(path=str(p), error=repr(exc)))
    bytecode = REFERENCE / 'reverse_engineered/raw/pvzrouge.pyc'
    raw = bytecode.read_bytes()
    # This repository's .pyc is a raw marshal code object, without a pyc header.
    root_code = marshal.loads(raw)
    raw_objects = []
    for name, code in code_objects(root_code):
        instructions = list(dis.get_instructions(code))
        jumps = [dict(offset=i.offset, opcode=i.opname, target=i.argval)
                 for i in instructions if i.opcode in dis.hasjabs or i.opcode in dis.hasjrel]
        raw_objects.append(dict(id=name, name=code.co_name, first_line=code.co_firstlineno,
            source_sha256=digest(raw), code_sha256=digest(code.co_code),
            offsets=[0, len(code.co_code)], jumps=jumps, constants_code_count=sum(
                isinstance(x, types.CodeType) for x in code.co_consts), status='unmapped'))
    # Do not infer a C++ function boundary using a regex over nested lambdas.
    # File-level obligations make manual edits impossible to silently omit.
    cpp = [dict(source=file_info(p), status='requires_function_level_mapping', typed_implementation=None)
           for area in ('src/sim', 'src/core', 'src/ui', 'src/app')
           for p in sorted((ROOT / area).rglob('*.cpp'))]
    provenance = [file_info(p) for p in sorted((ROOT / 'extract/schema').glob('*provenance*.json'))]
    report = dict(schema=1, role='conservative migration inventory; not runtime coverage',
        source_files=len(sources), functions=functions, branches=branches,
        raw_code_objects=raw_objects, current_cpp_files=cpp, provenance_files=provenance,
        parse_errors=errors, unresolved_dynamic_calls=sorted(set(c for f in functions for c in f['calls']
            if c.startswith('<dynamic:'))),
        complete_product_inventory=False,
        unknowns=['Full transitive import closure and injected runtime code are not yet mapped.',
                  'AST and bytecode control-flow equivalence is not established.',
                  'Hand C++ overrides and Python generation patches require per-function reconciliation.',
                  'All unmapped and untriggered branches remain blocking for full typed acceptance.'])
    summary = dict(source_files=len(sources), functions=len(functions), branches=len(branches),
        raw_code_objects=len(raw_objects), raw_jumps=sum(len(x['jumps']) for x in raw_objects),
        cpp_files=len(cpp), parse_errors=errors, complete_product_inventory=False,
        migrated=0, verified=0, formal_typed_acceptance=False)
    (out / 'original-logic-map.json').write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding='utf8')
    (out / 'inventory-summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf8')
    print(json.dumps(summary, ensure_ascii=True))
    return bool(errors)


if __name__ == '__main__':
    sys.exit(main())
