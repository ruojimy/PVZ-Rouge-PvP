"""Execute only the three original server-side async integration fixtures.

The unchanged whole test sources are read as AST data, never imported/executed.
Both source bytes and the selected async AST must match the native caller.
Native clients and all test assertions remain in the native test process.
"""
import ast,hashlib,os
from pathlib import Path
from types import SimpleNamespace

OWNERS={
 ('test_pvp_66_room_admission_oct16','legacy_send'),
 ('test_pvp_spectators49','legacy_send'),
 ('test_pvp_network_memory67','inspect'),
}

def load(server,command):
 module,line,name=command['fixture'].split(':')
 if (module,name) not in OWNERS:raise ValueError('Unknown original server fixture')
 root=Path(os.environ['PVZ_TEST_ROOT']).resolve()
 source=root/'tests'/(module+'.py');raw=source.read_bytes()
 if hashlib.sha256(raw).hexdigest()!=command['source_sha256']:raise ValueError('Server fixture source fingerprint mismatch')
 tree=ast.parse(raw.decode('utf-8-sig'),filename=str(source))
 functions=[node for node in ast.walk(tree) if isinstance(node,ast.AsyncFunctionDef) and node.name==name and node.lineno==int(line)]
 if len(functions)!=1:raise ValueError('Original server async fixture is missing or ambiguous')
 node=functions[0]
 digest=hashlib.sha256(ast.dump(node,include_attributes=False).encode('utf-8')).hexdigest()
 if digest!=command['ast_sha256']:raise ValueError('Server fixture AST fingerprint mismatch')
 if node.decorator_list:raise ValueError('Unexpected decorated server fixture')
 namespace=dict(original_send=server.send,relay=SimpleNamespace(server=server))
 exec(compile(ast.Module(body=[node],type_ignores=[]),str(source),'exec'),namespace)
 return name,namespace[name]
