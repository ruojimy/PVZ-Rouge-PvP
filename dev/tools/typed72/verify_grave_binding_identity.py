"""Replace a bound grave with a different live object in the same valid cell."""
import copy
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import verify_grave_binding as binding
shooting=binding.shooting
reference=binding.reference
GraveBindingExtension=binding.GraveBindingExtension


def cases():
    output=[]
    for label,case in binding.cases():
        if not label.startswith('grave-binding-cancellation-'):
            continue
        number=int(label.rsplit('-',1)[1])
        if number%12!=1:
            continue
        case=copy.deepcopy(case)
        operations=case['operations']
        index=next(i for i,op in enumerate(operations) if op['op']=='binding_attach')
        # Every validity predicate besides object identity still succeeds.
        # The alternate X coordinates also cover equivalent periodic cells.
        operations.insert(index,dict(op='plant_unit',unit=1,fields={
            '位置':[(264.,-696.,1224.,2184.)[(number//12)%4],432.,0.,0.]}))
        output.append(('grave-binding-valid-object-replacement-'+str(number),case))
    return output


def paths():
    return binding.paths()+[Path(__file__).resolve(),Path(binding.__file__)]


if __name__=='__main__':
    sys.exit(shooting.main(paths(),reference,cases,GraveBindingExtension,'typed72-grave-binding-identity'))
