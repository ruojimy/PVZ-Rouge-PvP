"""Export changed native72 inputs only; never write into the 71 reference."""
import importlib,json,sys
from pathlib import Path
sys.dont_write_bytecode=True
root=Path(__file__).resolve().parents[1]
reference=Path(r'C:\Users\xiech\Downloads\PVZ-Rouge-v1.4.8\next-pvp71')
sys.path[:0]=[str(root/'tools'),str(reference/'modkit')]
import pvp
pvp.__path__.insert(0,str(root/'tools/pvp72_sources'))
pvp.BUILD='1.6.0.74.1-typed.20261113'
from export_data import plain,Skip
modules='balance catalog pvp58_catalog pvp71_catalog zombie_secret_catalog pvp66_secrets zombie_secrets'.split()
for name in modules:
    module=importlib.import_module('pvp.'+name)
    path=root/'extract/data'/(name+'.json')
    old=json.loads(path.read_text(encoding='utf8'))
    for key in list(old):
        if hasattr(module,key):
            try:old[key]=plain(getattr(module,key))
            except Skip:pass
    path.write_text(json.dumps(old,ensure_ascii=False,indent=1),encoding='utf8')
path=root/'extract/data/__init__.json'
old=json.loads(path.read_text(encoding='utf8'));old['BUILD']=pvp.BUILD
path.write_text(json.dumps(old,ensure_ascii=False,indent=1),encoding='utf8')
print('Updated native72 data, build',pvp.BUILD)
