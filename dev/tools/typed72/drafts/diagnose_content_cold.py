import importlib.util
import json
import sys
import traceback
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT/'tools/typed72'))
reference=ROOT/'build/typed72-content-controller-v7/reference/verify_content_phase.py'
spec=importlib.util.spec_from_file_location('cold_diagnostic',reference);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
reference_hero=m.hero.load_reference();pref=m.shooting.plants.protection.reference();ref=m.native_reference();case=m.cases()[19][1]
class Spy(m.ContentPhaseExtension):
    def install_damage(self):
        super().install_damage()
        original=self.phase_damage_env['cold_flame'];key=m.shooting.P+'chili_fire_hit_one_zombie'
        print('namespaces',self.ns is self.env,self.phase_damage_env['flame_hit'].__globals__ is self.ns,flush=True)
        def cold(*args,**kwargs):
            try:return original(*args,**kwargs)
            except Exception:
                traceback.print_exc();raise
        self.ns[key]=cold
got=m.hero.oracle(case,reference_hero,lambda ctx:Spy(ctx,case,pref,ref))
print('completed',len(got),flush=True)
