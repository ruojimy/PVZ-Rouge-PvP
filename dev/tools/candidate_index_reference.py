"""Record exact CandidateIndex expectations from the original Python kernel."""
import array
import json
import os
from pathlib import Path
import random
import sys

ROOT=Path(__file__).resolve().parents[1]
REFERENCE=ROOT.parent/'PVZ-Rouge-v1.4.8'/'next-pvp71'
sys.dont_write_bytecode=True
sys.path.insert(0,str(REFERENCE/'modkit'))
from pvp import native_multiworker as original


def main():
    rng=random.Random(71071)
    cases=[]
    for wrap in (False,True):
        for width in (1.,96.,100.,1536.):
            for cell in (1.,31.,96.,500.):
                for count in (0,1,7,32):
                    points=[(rng.uniform(-2*width,3*width),rng.uniform(-200,200)) for _ in range(count)]
                    points += [(0.,0.),(width,0.),(-width,0.),(width/2,0.)]
                    boxes=[(0.,0.,0.,0.,0.,0.),(width,0.,width/2,width/2,0.,0.),
                           (0.,0.,2*width,2*width,400.,400.)]
                    boxes += [(rng.uniform(-width,2*width),rng.uniform(-200,200),
                               rng.uniform(0,width),rng.uniform(0,width),
                               rng.uniform(0,200),rng.uniform(0,200)) for _ in range(9)]
                    payload=(width,wrap,cell,original.pack_targets(points),original.pack_queries(boxes),0,len(boxes))
                    packed=original._box_candidates_python(*payload)
                    expected=original.merge_candidates([packed],len(boxes))
                    cases.append(dict(width=width,wrap=wrap,cell=cell,targets=points,boxes=boxes,expected=expected))
    cases.append(dict(width=1.,wrap=False,cell=96.,targets=[],boxes=[],expected=[]))
    cases.append(dict(width=1.,wrap=True,cell=96.,targets=[],boxes=[],expected=[]))
    Path(sys.argv[1]).write_text(json.dumps(cases,separators=(',',':')),encoding='utf-8')
    print('Recorded',len(cases),'cases from original _box_candidates_python')


if __name__=='__main__':main()
