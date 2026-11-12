"""Differential stage verification against original CPython bytecode and source.

Damage and shooter references execute ORIGINAL marshalled Python 3.8 code.
Sound calls and particle draw calls are captured presentation boundaries.
Particle generation and its RNG run in BOTH implementations when enabled.
This does not validate PvP wrappers, production assets, or a battle tick.
"""
import argparse
import ast
import builtins
import copy
import dis
import hashlib
import json
import marshal
import random
import shutil
import subprocess
import sys
import types
from pathlib import Path
import evidence_store
import evidence_archive

ROOT = Path(__file__).resolve().parents[2]
REF = ROOT.parent / 'PVZ-Rouge-v1.4.8/next-pvp71'
RAW = REF / 'reverse_engineered/raw/pvzrouge.pyc'
FLOOD = REF / 'modkit/pvp/native_flood.py'


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def raw_slice(code, start, end):
    # Keep absolute offsets intact, but validate that this stage is self-contained.
    # Never patch escaping control flow into a success path.
    for i in dis.get_instructions(code):
        if start <= i.offset < end and (i.opcode in dis.hasjabs or i.opcode in dis.hasjrel):
            if not start <= i.argval <= end:
                raise ValueError('Bytecode branch escapes stage: ' + repr(i))
    none = next(i for i, c in enumerate(code.co_consts) if c is None)
    if none > 255:
        raise ValueError('Unexpected None constant index')
    body = bytes([dis.opmap['NOP'], 0]) * (start // 2) + code.co_code[start:end]
    body += bytes([dis.opmap['LOAD_CONST'], none, dis.opmap['RETURN_VALUE'], 0])
    return code.replace(co_code=body, co_lnotab=b'', co_name='original_shooter_block')


class Sprite:
    def __init__(self, data):self.data=data
    def get_size(self):return self.data['width'],self.data['height']
    def get_at(self, xy):
        x,y=xy;return self.data['pixels'][y*self.data['width']+x]


def combat_reference(case, raw_code, shooter_code, particle_code):
    rng = random.Random(case.get('seed', 1))
    sounds, particles, rectangles = [], [], []
    presentation=case.get('presentation',{})
    g = {'__builtins__': builtins.__dict__, '僵尸': copy.deepcopy(case.get('zombies', [])), '实体': [],
         '比': case.get('tile', 48.), 'plk': case.get('plk', case.get('tile',48.)/10000.), '随': rng.randint,
         'c': copy.deepcopy, 'jdz': abs,
         '沉浸播音': lambda name, pos: sounds.append([name, copy.deepcopy(pos)]),
         '设置':{'粒子效果':presentation.get('enabled',False)},
         '摄像机':presentation.get('camera',[0.,0.]),'总宽':presentation.get('screen_width',1152.),
         '图集':{name:Sprite(data) for name,data in presentation.get('atlas',{}).items()},
         '粒子':copy.deepcopy(case.get('state',[]))}
    for c in raw_code.co_consts:
        if isinstance(c, types.CodeType) and c.co_name in ('新增实体', '伤害僵尸', '表面伤害僵尸', '增粒子', '无墙位移处理'):
            g[c.co_name] = types.FunctionType(c, g)
    original_particles=g['增粒子']
    def emit(name,pos,count):
        particles.append([name,copy.deepcopy(pos),count]);return original_particles(name,pos,count)
    g['增粒子']=emit

    def snapshot():
        return copy.deepcopy({'zombies': g['僵尸'] if case['mode'] == 'damage' else [],
            'entities': g['实体'], 'sounds': sounds, 'particles': particles,
            'particle_state':g['粒子'],'particle_rects':rectangles,
            'rng_index': rng.getstate()[1][-1]})
    states = []
    if case['mode'] == 'damage':
        for op in case['operations']:
            fn = g['表面伤害僵尸' if op.get('surface', False) else '伤害僵尸']
            result = fn(op['index'], op['facing'], op['amount'])
            row = snapshot(); row['return'] = result; states.append(row)
    elif case['mode']=='shooter':
        p = copy.deepcopy(case['plant'])
        g.update(植物=[p], l=0, y=p['坐标'][0], name=p['植物'])
        for step in case['inputs']:
            g['僵尸'] = [None] * step.get('zombie_count', 0)
            g['秘籍'] = ['大帝'] if step.get('emperor') else []
            row = step.get('row_targets')
            g['同横尸'] = {} if row is None else {p['坐标'][0]: row}
            exec(shooter_code, g)
            snap = snapshot(); snap['plant'] = copy.deepcopy(p); states.append(snap)
    else:
        terrain=case['terrain'];rows=terrain['rows'];cols=terrain['cols']
        class PeriodicRow(list):
            def __getitem__(self,key):return super().__getitem__(key%len(self))
        grid=[PeriodicRow([{'方块':'水' if terrain['water'][y*cols+x] else '空' if terrain['empty'][y*cols+x] else '石'}
                           for x in range(cols)]) for y in range(rows)]
        # Source flags must agree: water cells in these fixtures are passable.
        for i,water in enumerate(terrain['water']):
            if water and not terrain['empty'][i]:raise ValueError('fixture water is not passable')
        g.update(ditu=grid,kong=('空','水'),出界=lambda y,x:not(0<=y<rows and terrain['valid'][y]),
            screen=None,pygame=types.SimpleNamespace(draw=types.SimpleNamespace(
                rect=lambda screen,color,rect,width:rectangles.append([copy.deepcopy(color),copy.deepcopy(rect)]))))
        for step in case['inputs']:
            rectangles.clear()
            for name,pos,count in step.get('emit',[]):emit(name,pos,count)
            g['补帧']=0 if step.get('draw',True) else 1
            g['抖屏']=[0]+step.get('shake',[0.,0.])
            exec(particle_code,g)
            states.append(snapshot())
    return {'states': states, 'rng': list(rng.getstate()[1])}


class Rows:
    def __init__(self, rows):
        self.rows = rows


def flood_reference(case, advance):
    rows, cols = case['rows'], case['cols']
    valid = list(case['valid'])
    grid = [[{'方块': '空' if case['empty'][y*cols+x] else '石'} for x in range(cols)] for y in range(rows)]
    field = [case['field'][y*cols:(y+1)*cols] for y in range(rows)]
    state = dict(cd=case.get('cooldown', 0), sign=case.get('sign', 1),
                 queue=copy.deepcopy(case['queue']), frontier=[], seed_scratch=None, last_scratch=None)
    # Every call executes the unmodified Python implementation, with the exact
    # current geometry. No reference results come from C++ output.
    namespace = {'ditu': Rows(grid), 'kong': ('空',),
                 '出界': lambda y, x: not (0 <= y < rows and valid[y])}
    result = []
    for step in case['inputs']:
        for y, x, empty in step.get('changes', []):
            grid[y][x % cols]['方块'] = '空' if empty else '石'
        for y, value in step.get('valid_changes', []):
            valid[y] = value
        plants = step.get('plants', False)
        prefix = '植' if plants else '人'
        namespace.update({prefix+'洪水cd': state['cd'], prefix+'洪水覆盖': state['sign'],
            prefix+'洪水圈': state['queue'], prefix+'洪水圈x': state['frontier'],
            prefix+'洪水': Rows(field), '目标植物': 0 if step.get('has_target') else -1,
            '水平面': step.get('surface', 23.)})
        if 'player_position' in step:
            if plants:
                raise ValueError('player_position test must use player flood')
            namespace.update(玩家位置=step['player_position'], 比=step['tile'])
        else:
            y, x = step['seed']
            namespace.update(目标位置=[y, x], 比=1., 玩家位置=[float(x), y+.5])
        advance(namespace, plants)
        state.update(cd=namespace[prefix+'洪水cd'], sign=namespace[prefix+'洪水覆盖'],
                     queue=namespace[prefix+'洪水圈'], frontier=namespace[prefix+'洪水圈x'])
        if 'wx' in namespace:
            state['seed_scratch'] = [namespace['wy'], namespace['wx']]
        if 'l' in namespace:
            state['last_scratch'] = namespace['l']
        result.append(copy.deepcopy(dict(field=[x for row in field for x in row],
            queue=state['queue'], frontier=state['frontier'], cooldown=state['cd'], sign=state['sign'],
            seed_scratch=state['seed_scratch'], last_scratch=state['last_scratch'])))
    return {'states': result}


def physics_reference(case,code):
    t=case['terrain'];rows,cols=t['rows'],t['cols']
    periodic=case.get('periodic',True)
    class Row(list):
        def __getitem__(self,i):return super().__getitem__(i%len(self) if periodic else i)
    grid=[Row([{'方块':'空' if t['empty'][y*cols+x] else '石'} for x in range(cols)]) for y in range(rows)]
    g=dict(__builtins__=builtins.__dict__,ditu=grid,kong=('空',),c=copy.deepcopy,jdz=abs,
        比=case.get('tile',48.),plk=case.get('plk',case.get('tile',48.)/10000.),
        出界=lambda y,x:y<0 or y>=rows or (not periodic and (x<0 or x>=cols)),
        不封顶出界=lambda y,x:y>=rows or (not periodic and (x<0 or x>=cols)))
    f=types.FunctionType(next(c for c in code.co_consts if isinstance(c,types.CodeType) and c.co_name=='位移处理'),g)
    position=copy.deepcopy(case['state']);states=[]
    for step in case['inputs']:
        if 'velocity' in step:position[2:]=step['velocity']
        if 'position' in step:position[:2]=step['position']
        for y,x,empty in step.get('changes',[]):grid[y][x%cols]['方块']='空' if empty else '石'
        collision=f(position,step['size'])
        states.append(dict(motion=copy.deepcopy(position),collision=collision))
    return {'states':states}


def make_cases():
    cases = []
    def base():
        return {'僵尸': '普通僵尸', '防具': '', '手持': '', '血量': 100., '防具血量': 0.,
                '手持血量': 0., '方向': -1., '位置': [140., 400., .13, -.27], '受伤': 0., '手持受伤': 0.}
    # Exact armor+HP boundary, no spill on armor break, secondary armor, ash
    # presence (including None), repeated death, negative/fractional packets.
    for seed in range(8):
        roster = []
        for kind in ('普通僵尸', '巨人僵尸', '投篮车僵尸', '雪橇车僵尸'):
            for armor in ('', '路障', '铁桶', '橄榄球头盔', '黑橄榄球头盔'):
                z = base(); z.update(僵尸=kind, 防具=armor, 防具血量=40. if armor else 0.)
                roster.append(z)
        for hand in ('报纸', '气球', '钢门', '梯子', '玩偶匣', 'other'):
            z = base(); z.update(手持=hand, 手持血量=20.); roster.append(z)
        for value in (0, None):
            z = base(); z['灰烬'] = value; roster.append(z)
        z = base(); z['手持'] = '玩偶匣'; roster.append(z)
        for amount in (0., -.25, .5, 20., 40., 100., 139.999999999, 140., 160.):
            operations = []
            for surface in (True, False, True):
                for i in range(len(roster)):
                    operations.append(dict(index=i, surface=surface, facing=1 if seed % 2 else -1, amount=amount))
            cases.append(dict(mode='damage', seed=seed, zombies=roster, operations=operations, instrument=True))
    for i, kind in enumerate(('豌豆射手','寒冰射手','双发射手','杨桃','仙人掌','机枪射手')):
        for facing in (-1, 1):
            for cd in (-1., 0., .5):
                plant = {'植物': kind, '坐标': [8, 10], '方向': facing, '射cd': cd, '射': 0.}
                if kind == '双发射手': plant['双发'] = 0.
                if kind == '机枪射手': plant['机枪'] = 0.
                inputs = []
                for tick in range(1350):
                    targets = None if tick % 263 < 7 else [] if tick % 263 < 12 else [10+facing*24, 10+facing*72]
                    inputs.append(dict(row_targets=targets, zombie_count=30 if tick > 400 else 3,
                                       emperor=(tick // 100) % 2 == 0))
                cases.append(dict(mode='shooter', seed=400+i, plant=plant, inputs=inputs, instrument=True))
    rng = random.Random(72004)
    for i in range(36):
        rows, cols = 24, (1, 2, 7, 19, 60, 93)[i % 6]
        empty = [int(rng.random() > .25) for _ in range(rows*cols)]
        valid = [int(y != 0 and y != 23) for y in range(rows)] if i % 3 else [1]*rows
        initial = [rng.choice((0, 0, -1, 1, -4, 4)) for _ in empty]
        inputs = []
        for tick in range(160):
            step = dict(seed=[rng.randrange(-1,25), rng.randrange(-3*cols,3*cols)],
                plants=i%2 == 0, has_target=tick%37 > 5, surface=20 if tick<80 else 23,
                changes=[[rng.randrange(rows),rng.randrange(-cols,cols),rng.randrange(2)]] if tick%9==0 else [])
            if i%2 and tick%5==0:
                step.pop('seed');step.update(player_position=[-48.0000001, 24.-1e-9],tile=48.)
            inputs.append(step)
        cases.append(dict(mode='flood', rows=rows, cols=cols, empty=empty, valid=valid, field=initial,
            queue=[] if i%3 else [[12, -cols-1],[12,-cols-1]], cooldown=-1 if i==0 else i%4,
            sign=-1 if i%2 else 1, inputs=inputs))
    for i in range(12):
        pixels=[[20,70,150,255] if (x+i)%7==0 else [0,0,0,255] if x%2 else [0,50,100,0] for x in range(64)]
        if i==0:pixels=[[0,0,0,0]]*64
        if i==1:pixels=[[20,70,150,255]]*64
        presentation=dict(enabled=i!=2,camera=[0.,0.],screen_width=100.,atlas={'气球':dict(width=8,height=8,pixels=pixels)})
        z=base();z.update(手持='气球',手持血量=1.)
        cases.append(dict(mode='damage',seed=100+i,zombies=[z],presentation=presentation,
            operations=[dict(index=0,surface=True,facing=1,amount=20),dict(index=0,surface=False,facing=-1,amount=200)]))
        empty=[1]*(24*7);water=[0]*len(empty)
        for x in range(7):empty[19*7+x]=0;water[18*7+x]=1
        initial=[]
        for age in (0,249,250,298,299,300,299.5):
            for vx in (-1.,-.001,0.,.001,1.):
                initial.append([[140,20,30,255],[48.*(i%8)-1e-12,18*48.-1e-12,vx,.4],age])
        steps=[]
        for tick in range(320):
            emit=[]
            if tick==0:emit=[['气球',[24.,18*48.-.1],30],['气球',[-49.,30.],12],['missing',[0.,0.],5]]
            if tick==4:emit=[['气球',[148.,23.],5]]
            steps.append(dict(emit=emit,draw=tick%3!=0,shake=[.25,-.5]))
        cases.append(dict(mode='particles',seed=100+i,presentation=presentation,
            terrain=dict(rows=24,cols=7,empty=empty,water=water,valid=[1]*24),state=initial,inputs=steps))
    for i in range(48):
        tile=(24.,48.,63.5)[i%3];cols=13
        empty=[int(rng.random()>.18) for _ in range(24*cols)]
        steps=[]
        for tick in range(180):
            step=dict(size=(0.,.5,1.,2.,3.)[(tick//30)%5])
            if tick%17==0:
                step.update(position=[rng.choice((-tile*2,-1e-12,0.,tile*3-1e-12,tile*13,tile*15)),
                                      rng.choice((-tile,0.,tile*5-1e-12,tile*24,tile*25))],
                            velocity=[rng.choice((-tile,-.001,0.,.001,tile)),rng.choice((-tile,-.001,0.,.001,tile))])
            if tick%23==0:step['changes']=[[rng.randrange(24),rng.randrange(cols),rng.randrange(2)]]
            steps.append(step)
        cases.append(dict(mode='physics',tile=tile,periodic=bool(i%2),
            terrain=dict(rows=24,cols=cols,empty=empty,valid=[1]*24),state=[tile*4,tile*5,0.,0.],inputs=steps))
    return cases


def difference(a, b, path=''):
    if isinstance(a, dict) and isinstance(b, dict):
        if set(a) != set(b): return dict(path=path, expected_keys=sorted(a), actual_keys=sorted(b))
        for key in a:
            found = difference(a[key], b[key], path+'/'+key)
            if found: return found
    elif isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b): return dict(path=path, expected_length=len(a), actual_length=len(b))
        for i, (x, y) in enumerate(zip(a, b)):
            found = difference(x, y, path+'/'+str(i))
            if found: return found
    elif isinstance(a, bool) or isinstance(b, bool) or a is None or b is None:
        if type(a) is not type(b) or a != b: return dict(path=path, expected=a, actual=b)
    elif isinstance(a, (float,int)) and isinstance(b, (float,int)):
        if abs(a-b) > 1e-9: return dict(path=path, expected=a, actual=b)
    elif a != b:
        return dict(path=path, expected=a, actual=b)
    return None


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--exe', required=True); ap.add_argument('--out', required=True)
    ap.add_argument('--mode', action='append', choices=('damage','shooter','flood','particles','physics'))
    args = ap.parse_args()
    out = Path(args.out); out.mkdir(parents=True, exist_ok=False)
    exe = Path(args.exe).resolve()
    pin_paths = [RAW, FLOOD, exe, Path(__file__).resolve(), ROOT/'tools/typed72/kernel_probe.cpp',
                 ROOT/'src/core/pyrandom.h',ROOT/'src/core/pymath.h',ROOT/'third_party/nlohmann/json.hpp',
                 ROOT/'CMakeLists.txt']
    pin_paths.extend((ROOT/'src/sim/typed').glob('*.*'))
    pin_paths.extend((Path(evidence_store.__file__).resolve(),Path(evidence_archive.__file__).resolve()));pinned = {str(p):sha(p) for p in pin_paths if p.is_file()}
    (out/'pinned.json').write_text(json.dumps(pinned,indent=2),encoding='utf8')
    # Keep the exact runner and candidate sources, not only hashes of mutable
    # workspace files. Subsequent edits must not destroy reproducibility.
    for p in pin_paths:
        if not p.is_file():continue
        try:relative=p.relative_to(ROOT)
        except ValueError:relative=Path('external')/p.name
        destination=out/'frozen'/relative;destination.parent.mkdir(parents=True,exist_ok=True)
        evidence_store.freeze_file(p,destination,expected_sha256=pinned[str(p)])
    code = marshal.loads(RAW.read_bytes())
    shooter = raw_slice(code,128324,130014)
    particle_code=raw_slice(code,108808,109352)
    ns = {}; exec(compile(FLOOD.read_text(encoding='utf8'),str(FLOOD),'exec'),ns)
    cases = make_cases()
    if args.mode:cases=[case for case in cases if case['mode'] in args.mode]
    with (out/'inputs.jsonl').open('w',encoding='utf8') as stream:
        for c in cases:stream.write(json.dumps(c,ensure_ascii=False,separators=(',',':'))+'\n')
    with (out/'actual.jsonl').open('wb') as actual, (out/'stderr.log').open('wb') as err:
        run = subprocess.run([str(exe),str((out/'inputs.jsonl').resolve())],stdout=actual,stderr=err,timeout=240)
    results=[]; branch_counts=[]
    with (out/'actual.jsonl').open(encoding='utf8') as actual, (out/'expected.jsonl').open('w',encoding='utf8') as expected:
        for i, case in enumerate(cases):
            row=dict(case=i,mode=case['mode'],passed=False)
            try:
                got=json.loads(next(actual))
                if case['mode']=='flood':reference=flood_reference(case,ns['advance'])
                elif case['mode']=='physics':reference=physics_reference(case,code)
                else:reference=combat_reference(case,code,shooter,particle_code)
                expected.write(json.dumps(reference,ensure_ascii=False,separators=(',',':'))+'\n')
                if got.get('backend_actual')!='typed72-stages' or got.get('fallback_count')!=0:
                    raise ValueError('backend mismatch or fallback')
                found=difference(reference,{k:got[k] for k in reference})
                row.update(passed=found is None, first_difference=found, steps=len(reference['states']))
                for index,count in enumerate(got.get('branches',[])):
                    while len(branch_counts)<=index:branch_counts.append(0)
                    branch_counts[index]+=count
            except Exception as exc:
                row['error']=repr(exc)
            results.append(row)
            if not row['passed']:
                (out/('failure-%03d.json'%i)).write_text(json.dumps(dict(input=case,result=row),ensure_ascii=False,indent=2),encoding='utf8')
            if i%12==0 or not row['passed']:print(i,case['mode'],'PASS' if row['passed'] else 'FAIL',flush=True)
        extra=next(actual,None)
    changed=[str(p) for p in pin_paths if p.is_file() and sha(p)!=pinned[str(p)]]
    summary=dict(schema=1,passed=run.returncode==0 and all(r['passed'] for r in results) and not changed and extra is None,
        process_exit_code=run.returncode,cases=len(results),passed_cases=sum(r['passed'] for r in results),
        selected_modes=args.mode or ['damage','shooter','flood','particles','physics'],
        compared_stage_steps=sum(r.get('steps',0) for r in results),tolerance=1e-9,changed_inputs=changed,
        backend_actual='typed72-stages',full_battle_acceptance=False,results=results,branch_outcomes=branch_counts,
        reference=dict(damage='Original CPython3.8 bytecode functions',shooter='Original raw module offsets128324..130014',
                       flood=str(FLOOD),particles='Original emit/movement functions and raw region108808..109352',
                       presentation_boundary='Sound events and particle rectangles captured; production assets/UI not validated'),
        full_product_claim=False)
    (out/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps({k:v for k,v in summary.items() if k not in ('results','branch_outcomes','reference')},ensure_ascii=True))
    return evidence_archive.finish_verification(out,producer=run,closed_streams=(actual,expected),behavior_passed=summary['passed'])


if __name__=='__main__':sys.exit(main())
