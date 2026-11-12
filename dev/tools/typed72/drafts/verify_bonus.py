"""Literal post-frame combat scan and projectile/plant bonus controllers."""
import ast
import copy
import functools
import importlib.util
from pathlib import Path
import sys
import types

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('bonus_status_reference', HERE / 'verify_native_status.py')
status = importlib.util.module_from_spec(spec)
spec.loader.exec_module(status)
driver = status.driver
shared = status.shared
shooting = status.shooting
hero = status.hero
P = shooting.P
COUNTERS = ('patch_count', 'seen_thrower_count', 'guide_log_count', 'bonus_count',
            'cannon_patch_count', 'star_patch_count', 'starfruit_manual_count',
            'tri_shot_count', 'gravebuster_zombie_bite_damage_count')


def reference():
    ref = status.reference()
    patch_tree = ast.parse(shooting.patch.PATCH.read_text(encoding='utf8'))
    scan = next(node for node in patch_tree.body if isinstance(node, ast.FunctionDef) and node.name == P + 'bonus_scan')
    # Test the velocity-bonus subsection independently using its original AST.
    # The complete original bonus_scan is also exercised below.
    section = [copy.deepcopy(node) for node in scan.body if isinstance(node, ast.Assign)
               and any(isinstance(target, ast.Name) and target.id in ('entities', 'zombies', 'scale', 'damage_fn')
                       for target in node.targets)]
    section += [copy.deepcopy(node) for node in scan.body if isinstance(node, ast.For)]
    velocity = ast.parse('def bonus_velocity(g):\n    global ' + P + 'bonus_count\n').body[0]
    velocity.body += section
    ref['bonus_velocity'] = compile(ast.fix_missing_locations(ast.Module(body=[velocity], type_ignores=[])),
                                    str(shooting.patch.PATCH), 'exec')
    tree = ast.parse(shooting.projectiles.CONTENT.read_text(encoding='utf8'))
    base_damage, = [node for node in ast.walk(tree) if isinstance(node, ast.ClassDef) and node.name == 'ContentBaseDamage']
    red_tripea, = [node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name == 'red_tripea']
    ref['bonus_content'] = compile(ast.Module(body=[base_damage, red_tripea], type_ignores=[]),
                                   str(shooting.projectiles.CONTENT), 'exec')
    env = dict(sys=sys)
    hero.selected_class(shared.BATTLE, ['_install_star_damage'], 'BonusBattle', env)
    ref['bonus_star_install'] = env['BonusBattle']._install_star_damage
    tree = ast.parse(shooting.doom.NATIVE_PATCH.read_text(encoding='utf8'))
    bonus, = [node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name == 'bonus']
    ref['bonus_wrapper'] = compile(ast.Module(body=[bonus], type_ignores=[]), str(shooting.doom.NATIVE_PATCH), 'exec')
    return ref


class BonusExtension(status.NativeStatusExtension):
    def __init__(self, ctx, case, pref, ref):
        super().__init__(ctx, case, pref, ref)
        self.bonus_seen = False
        self.bonus_installed = False
        self.bonus_now = 0.
        self.bonus_ticks = 0
        self.blue_available = True
        ns, game = self.ns, self.g
        for name in COUNTERS:
            ns[P + name] = 0
        ns[P + 'pending_starbursts'] = []
        ns[P + 'gravebuster_zombie_bite_records'] = {}
        ns[P + 'last_bonus_scan'] = ns[P + 'last_maintenance_scan'] = 0.
        exec(ref['bonus_velocity'], ns)
        content = types.SimpleNamespace(pvp64=self.mortars)
        env = dict(sys=sys, self=content, g=game, ns=ns, tripea_spawn=ns[P + 'spawn_tripea_projectile'])
        exec(ref['bonus_content'], env)
        ns[P + 'BASE_DAMAGE'] = env['ContentBaseDamage'](ns[P + 'BASE_DAMAGE'])
        ns[P + 'spawn_tripea_projectile'] = env['red_tripea']
        ref['bonus_star_install'](types.SimpleNamespace(patch=ctx.constructor_patch, targets=self.c, g=game))

        def assets(name):
            self.calls.append([name])
            self.before(name)
            self.after(name)
        ns[P + 'patch_star_atlas'] = lambda game: assets('bonus_star_assets')
        ns[P + 'patch_tripea_assets'] = lambda game: assets('bonus_blue_assets')
        ns[P + 'ensure_blue_firepea_atlas'] = lambda game, atlas, scale: self.blue_available
        # Observe the explicitly required head-impact boundary. The controller
        # still executes the unchanged head collision and steel-door selection.
        scan_code = ns[P + 'plant_zombie_head_hit_scan'].__code__
        for key, surface in (('伤害僵尸', False), ('表面伤害僵尸', True)):
            original = game[key]
            def impact(index, facing, amount, original=original, surface=surface):
                frame = sys._getframe(1)
                entity = frame.f_locals.get('entity') if frame.f_code is scan_code else None
                if entity is None:
                    return original(index, facing, amount)
                label = next(i for i, value in enumerate(self.births) if value is entity)
                self.calls.append(['bonus_head', label, index, facing, amount, surface])
                self.before('bonus_head')
                result = original(index, facing, amount)
                self.after('bonus_head')
                return result
            game[key] = impact
        env = dict(self=ctx.constructor_patch, targets=self.c, PREFIX=P,
                   original_bonus=ns[P + 'bonus_scan'], wraps=functools.wraps)
        exec(ref['bonus_wrapper'], env)
        self.bonus_after = env['bonus']
        old_before, old_after = self.b.patch.before_native_tick, self.b.patch.after_native_tick
        def before(now):
            old_before(now)
            if self.bonus_installed:
                self.set_clock(now)
        def after(now):
            old_after(now)
            if self.bonus_installed:
                self.after_tick(now)
        self.b.patch.before_native_tick = before
        self.b.patch.after_native_tick = after

    def set_clock(self, now):
        self.ctx.constructor_patch._set_time(now)
        self.bonus_now = self.native_time = now

    def after_tick(self, now):
        self.set_clock(now)
        self.bonus_after(self.g)
        self.bonus_ticks += 1

    def bonus_fields(self, entity, fields):
        fields = copy.deepcopy(fields)
        for name in ('智能星命中', '植物僵尸头命中表'):
            if fields.get(name) is not None:
                fields[name] = [self.decode_key(value) for value in fields[name]]
        if isinstance(fields.get('智能弹道'), dict) and fields['智能弹道'].get('target_id') is not None:
            fields['智能弹道']['target_id'] = self.decode_key(fields['智能弹道']['target_id'])
        self.entity_fields(entity, fields)

    def operation(self, op):
        name = op['op']
        if name == 'bonus_setup':
            self.bonus_seen = True
            self.bonus_installed = op.get('installed', False)
            self.blue_available = op.get('blue', True)
        elif name == 'bonus_clock':
            self.set_clock(op['now'])
        elif name == 'bonus_entity':
            self.add_entity(op['name'], op.get('facing', 1.), list(op['position']))
            self.bonus_fields(self.births[-1], op.get('fields', {}))
        elif name == 'bonus_entity_fields':
            self.bonus_fields(self.births[op['entity']], op['fields'])
        elif name == 'bonus_plant_fields':
            self.all_plants[op['plant']].update(copy.deepcopy(op['fields']))
        elif name == 'bonus_call':
            action = op['action']
            entity = self.births[op['entity']] if 'entity' in op else None
            if action == 'after':
                self.after_tick(op['now'])
            elif action == 'record_star':
                self.ns[P + 'record_star'](self.g, entity, op.get('facing', entity['方向']))
            elif action == 'cannons':
                self.ns[P + 'fix_cannon_projectiles'](self.g)
                self.ns[P + 'patch_cannons'](self.g)
            elif action in ('patch', 'reload'):
                method = 'patch_projectile' if action == 'patch' else 'mark_cannon_reloading'
                self.ns[P + method](self.g, entity)
            else:
                methods = dict(guide='guide_projectiles', velocity='bonus_velocity', heads='plant_zombie_head_hit_scan',
                               finalize='finalize_starbursts', stars='patch_starfruit_targeting', star_damage='star_damage_scan',
                               tripea='patch_tripea_shooting', grave='update_gravebuster_zombie_plant_damage',
                               stones='cleanup_stone_placeholders', scan='bonus_scan')
                key = methods[action]
                self.ns[key if action == 'velocity' else P + key](self.g)
        else:
            return super().operation(op)

    def snapshot(self, row):
        super().snapshot(row)
        if not self.bonus_seen:
            return
        for name in ('entities', 'effect_births'):
            for entity in row[name]:
                for key in ('智能星命中', '植物僵尸头命中表'):
                    if entity.get(key) is not None:
                        entity[key] = [self.encode_key(value) for value in entity[key]]
                smart = entity.get('智能弹道')
                if isinstance(smart, dict) and 'target_id' in smart:
                    smart['target_id'] = self.encode_key(smart['target_id'])
        for name in ('plants', 'all_plants'):
            for plant in row[name]:
                if plant.get('三向目标') is not None:
                    plant['三向目标'] = [self.encode_key(value) for value in plant['三向目标']]
        pending = []
        for group in self.ns[P + 'pending_starbursts']:
            stars = [next(i for i, value in enumerate(self.births) if value is star) for star in group['stars']]
            pending.append([group['created'], group['x'], group['y'], group['speed'], group['direction'], stars, group['done']])
        bites = [[self.encode_key(key), value] for key, value in self.ns[P + 'gravebuster_zombie_bite_records'].items()]
        row['bonus'] = dict(time=self.bonus_now, scan=self.ns[P + 'last_bonus_scan'],
                            maintenance=self.ns[P + 'last_maintenance_scan'], tick_calls=self.bonus_ticks,
                            pending=pending, bites=bites, counts=[self.ns[P + name] for name in COUNTERS])


def cases():
    prototype = driver.cases()[0][1]
    output = []
    def setup(index):
        case = copy.deepcopy(prototype)
        case['seed'] = 1300000 + index
        ops = case['operations'] = case['operations'][:-4]
        ops += [dict(op='bonus_setup'), dict(op='roster_replace', targets=[0, 1, 2, 3])]
        for unit in range(4):
            ops.append(dict(op='plant_unit', unit=unit, fields={'血量':1000., '位置':[312. + 48. * unit,432.,0.,0.],
                                                               '大小':2., '_pvp_owner':'zombie'}, erase=['魅惑']))
        return case, ops
    def entity(name, point=(264., 400., 5., -2.), **fields):
        return dict(op='bonus_entity', name=name, position=list(point), fields=fields)
    def plant(ops, name, cell=(8, 5), **fields):
        index = sum(op['op'] == 'plant_original' for op in ops)
        ops += [dict(op='plant_original', name=name, cell=list(cell)),
                dict(op='plant_fields', plant=index, fields={'_pvp_owner':'plant'}),
                dict(op='bonus_plant_fields', plant=index, fields=fields)]
        return index
    def call(action, **args):
        return dict(op='bonus_call', action=action, **args)
    for i in range(16):
        case, ops = setup(i)
        ops += [entity(('卷心菜','西瓜','冰瓜','玉米粒','黄油','豌豆')[i % 6],
                       (264., 400., (0., 1., 5., 9.)[i % 4], -2.)), call('patch', entity=0)]
        for time in (.079, .08, .16, .48):
            ops += [dict(op='bonus_clock', now=time), call('guide')]
        ops += [dict(op='bonus_entity_fields', entity=0, fields={'位置':[312.,432.,20.,0.],
                     '智能弹道':{'target_index':0,'initial_speed':5.}, '_pvp_content':'甜椒投手' if i % 2 else ''}),
                call('velocity'), call('velocity')]
        output.append(('bonus-smart-guidance-and-velocity-' + str(i), case))
    for i in range(16):
        case, ops = setup(20 + i)
        p = plant(ops, '玉米加农炮', **{'发射cd':(0.,1.,7200.,9000.)[i % 4], '黑白':False,
                                     '发射动画':float(i % 2), '死':False})
        entity_fields = {'锁敌':None,'牛顿':None} if i % 3 == 0 else {}
        ops += [entity('玉米炮', (264.,408.,0.,-4.), **entity_fields), call('cannons'), call('reload', entity=0),
                call('cannons'), dict(op='bonus_plant_fields', plant=p, fields={'发射cd':0.,'发射动画':0.}), call('cannons')]
        output.append(('bonus-cannon-reload-presence-' + str(i), case))
    for i in range(16):
        case, ops = setup(40 + i)
        count = (1,3,5,7)[i % 4]
        for j in range(count):
            ops += [entity('星星', (264.,400.,(-1.,1.)[i % 2] * (j+1),0.)), call('record_star', entity=j)]
        for time in (.029, .03, .5):
            ops += [dict(op='bonus_clock', now=time), call('finalize')]
        ops += [dict(op='bonus_entity_fields', entity=0, fields={'位置':[312.,400.,1.,0.]}), call('star_damage'), call('star_damage')]
        output.append(('bonus-starburst-groups-and-hit-memory-' + str(i), case))
    for i in range(16):
        case, ops = setup(60 + i)
        kind = '三向射手' if i < 12 else '杨桃'
        p = plant(ops, kind, **{'射cd':(-1.,0.,1.,2.)[i % 4], '射':-1., '根动画':float(i * 3)})
        if i % 3 == 0:
            ops += [dict(op='bonus_plant_fields', plant=p, fields={'三向角':[None, 350., -190.]})]
        ops += [dict(op='write', target='globals', values={'秘籍':['三向蓝火'] if i % 2 == 0 else []}),
                dict(op='bonus_setup', blue=i % 4 != 0)]
        for unused in range(4):
            ops.append(call('tripea' if kind == '三向射手' else 'stars'))
        output.append(('bonus-tripea-and-starfruit-' + str(i), case))
    for i in range(16):
        case, ops = setup(80 + i)
        ops += [dict(op='service_unit', unit=0, values={'植物僵尸':True, '植物僵尸名':'豌豆僵尸',
                    '方向':-1.,'手持':'钢门','手持血量':80.}),
                entity(('豌豆','火豆','蓝火豆','星星','尖刺','大泡泡','卷心菜','泡泡')[i % 8],
                       (312.,360.,5.,0.), **{'消亡':True if i == 15 else 1. if i == 14 else -1000.}),
                call('heads'), call('heads')]
        output.append(('bonus-plant-head-hit-and-piercing-' + str(i), case))
    for i in range(16):
        case, ops = setup(100 + i)
        p = plant(ops, '向日葵', **{'植物血':(3.,6.,20.,100.)[i % 4]})
        ops += [dict(op='service_unit', unit=0, values={'植物僵尸':True,'植物僵尸名':'墓碑吞噬者僵尸',
                    '位置':[264.,432.,0.,0.]}), call('grave'),
                dict(op='bonus_plant_fields', plant=p, fields={'植物血':(2.,5.,19.,99.)[i % 4]}), call('grave'), call('grave')]
        plant(ops, '向日葵', (8, 7), **{'智能石块占位':True})
        ops += [call('stones')]
        output.append(('bonus-gravebite-and-placeholder-cleanup-' + str(i), case))
    for i in range(8):
        case, ops = setup(120 + i)
        if i % 2:
            ops.append(dict(op='roster_replace', targets=[]))
        plant(ops, '三向射手' if i % 3 else '杨桃', **{'射cd':0.})
        for time in (.004, .02, .10, .25, .50, 1.):
            ops.append(call('after', now=time))
        output.append(('bonus-composed-post-frame-scan-' + str(i), case))
    for i in range(8):
        case, ops = setup(140 + i)
        ops += [entity('装饰实体', (312.,360.,0.,0.), **{'穿墙':1.}), call('heads'),
                entity('豌豆', (312.,360.,1.,0.), **{'消亡':True}), call('heads'),
                dict(op='bonus_entity_fields', entity=1, fields={'消亡':1.}), call('heads')]
        if i % 2:
            ops += [dict(op='bonus_entity_fields', entity=1, fields={'消亡':True}), call('heads')]
        output.append(('bonus-head-empty-fastpath-and-expiry-type-' + str(i), case))
    return output


def paths():
    return status.paths() + [Path(__file__).resolve(), shared.ROOT / 'tools/typed72/bonus_probe.cpp']


if __name__ == '__main__':
    raise SystemExit(shooting.main(paths(), reference, cases, BonusExtension, 'typed72-native-bonus-scan'))
