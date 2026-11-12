"""Actual private PvP patch installation for the saved hero proxy factory.

Only used by independent CPython probes. The package has current PvP72 source
overlays first; cppcore is explicitly disabled in this reference process.
"""
import importlib
import os
import sys
import types
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
REF=ROOT.parent/'PVZ-Rouge-v1.4.8/next-pvp71'
PATCH=REF/'modkit/pvzrouge_runtime_patch_source_20260904.py'
PACKAGE='_typed72_proxy_reference'
_loaded=None


def load():
    global _loaded
    if _loaded is None:
        os.environ['PVP_CPP']='0'
        package=types.ModuleType(PACKAGE)
        package.__path__=[str(ROOT/'tools/pvp72_sources'),str(REF/'modkit/pvp')]
        package.__package__=PACKAGE
        sys.modules[PACKAGE]=package
        path=REF/'modkit/pvp/__init__.py'
        exec(compile(path.read_text(encoding='utf8'),str(path),'exec'),package.__dict__)
        module=importlib.import_module(PACKAGE+'.native_patch')
        _loaded=(module.NativeCombatPatch,PATCH.read_text(encoding='utf8'))
    return _loaded


def paths():
    load()
    result=[Path(__file__).resolve(),PATCH,REF/'modkit/pvp/__init__.py']
    result += [Path(module.__file__).resolve() for name,module in list(sys.modules.items())
               if name.startswith(PACKAGE+'.') and getattr(module,'__file__',None)]
    return list(dict.fromkeys(result))


def install(game,functions):
    patch_type,source=load()
    game['新增僵尸']=types.FunctionType(functions['新增僵尸'],game)
    return patch_type(game,source)
