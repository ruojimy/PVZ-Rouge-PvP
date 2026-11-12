# Inventory of the Python release's full suite (next-pvp71/tests/test_pvp_*.py) for the C++ coverage map.
#   python38 tools/old_suite_inventory.py <out.json>
# Per module: test count (from the pvp71 suite summary + an AST count), imported pvp/modkit modules, and
# feature flags (subprocess/EXE/APK/packaging/cpp_port/multiworker/network/app/battle ...).
import ast, json, os, re, sys

ROOT = os.path.join('C:' + os.sep, 'Users', 'xiech', 'Downloads', 'PVZ-Rouge-v1.4.8', 'next-pvp71')
TESTS = os.path.join(ROOT, 'tests')
SUMMARY = os.path.join(ROOT, '对战', '测试结果', 'pvp71-suite-groups', 'summary.json')

counts = {m['module']: m['tests'] for m in json.load(open(SUMMARY, encoding='utf-8'))['modules']}
FLAGS = {
    'subprocess': r'\bsubprocess\b|Popen\(',
    'exe': r'\.exe\b|build_pvp_exe|verify_pvp_exe|pyinstaller|frozen',
    'android': r'android|\.apk\b|p4a|jnius|platform_android',
    'packaging': r'package_pvp|deliver|manifest|sha256|update_pvp|updater|zipfile|sign_pvp',
    'cpp_port': r'cpp_port|_pvpcore|pvpcore|cpp_gate|native_kernels?\b',
    'multiworker': r'multiworker|JobSystem|ProcessPool|SnapshotPackWorker',
    'network': r'ServerTransport|ClientTransport|Relay\w*Transport|socket\b|LobbyQuery|relay\b',
    'server': r'server[./]|relay_server|lobby_server',
    'app': r'Application\(|app\.run|\bfrom pvp\.app\b|import app\b|render\(|Renderer',
    'battle': r'NativeBattle|Simulation|step\(|battle\.',
    'room': r'\bRoom\(',
    'ai': r'rv_|ai_room|AIRoom|lobby_room|agent',
    'replay': r'replay|Recording|Playback',
    'audit': r'audit_log|AuditLog',
    'pygame': r'pygame',
    'source_scan': r'read_text\(|open\(.*\.py|ast\.parse|inspect\.getsource',
}

out = []
for fn in sorted(os.listdir(TESTS)):
    if not (fn.startswith('test_pvp_') and fn.endswith('.py')):
        continue
    mod = fn[:-3]
    src = open(os.path.join(TESTS, fn), encoding='utf-8').read()
    try:
        tree = ast.parse(src)
    except SyntaxError:
        tree = None
    imports, ast_tests = set(), 0
    if tree:
        for n in ast.walk(tree):
            if isinstance(n, ast.ImportFrom) and n.module:
                if n.module.startswith(('pvp', 'modkit', 'server', 'cpp_port', 'tests')):
                    imports.add(n.module if n.module not in ('pvp', 'modkit.pvp') else n.module + ':' + ','.join(a.name for a in n.names))
            elif isinstance(n, ast.Import):
                for a in n.names:
                    if a.name.startswith(('pvp', 'modkit', 'server', 'cpp_port')):
                        imports.add(a.name)
            elif isinstance(n, ast.FunctionDef) and n.name.startswith('test'):
                ast_tests += 1
    doc = ast.get_docstring(tree) if tree else ''
    out.append(dict(module=mod, tests=counts.get(mod, ast_tests), ast_tests=ast_tests,
                    in_pvp71_summary=mod in counts, imports=sorted(imports),
                    flags=[k for k, p in FLAGS.items() if re.search(p, src)],
                    doc=(doc or '').strip().splitlines()[0][:160] if doc else '', lines=src.count('\n')))
json.dump(out, open(sys.argv[1], 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('modules', len(out), 'tests', sum(m['tests'] for m in out), 'not in pvp71 summary', [m['module'] for m in out if not m['in_pvp71_summary']])
