"""Full NativeTick calls with the actual NativeContent zombie controller chain.

Other phase dependencies are named by the inherited boundary ledger. This is
an integration step and deliberately does not claim the full game is ready.
"""
import copy
import importlib.util
from pathlib import Path
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('content_cycle_controllers',HERE/'verify_content_controllers.py')
base=importlib.util.module_from_spec(spec);spec.loader.exec_module(base)
shooting=base.shooting

def cases():
    source=base.cases();result=[]
    for index in (0,2,8,10,16,17,24,25):
        label,original=source[index];case=copy.deepcopy(original)
        operations=case['operations']
        for operation in operations:
            if operation['op']=='content_zombies_setup':operation['installed']=True
        start=next(i for i,operation in enumerate(operations) if operation['op']=='content_gate')
        # NativeTick also advances the producer economy. The isolated gate
        # fixtures only needed the plant body; admit its card for that phase.
        case['operations']=operations[:start]+[dict(op='producer_card',id='plant:向日葵',fields={'period':5.,'producer':True})]+[dict(op='native_tick',draw=False) for unused in range(3)]
        result.append(('native-content-cycle-'+label,case))
    return result

def paths():return base.paths()+[Path(__file__).resolve()]

if __name__=='__main__':
    raise SystemExit(shooting.main(paths(),base.reference,cases,base.ContentControllersExtension,
        'typed72-native-content-cycle',probe_timeout=600))
