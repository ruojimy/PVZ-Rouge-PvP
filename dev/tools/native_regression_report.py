"""Validate named combat coverage and compare native full-suite evidence."""
from collections import Counter
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TRIAGE = ROOT / 'docs/coverage/native-failure-triage.json'
DENSE = '密植_啃咬_僵尸豌豆_红火_蓝火_大喷'
BOSSES = '索敌_Boss各部位实弹'
ARMOR = '魅惑_双方防御与Boss'
IMPACT = '索敌_七种植物实弹与世界吞噬者'
SMALL = '索敌_小体型中心'
LANES = '索敌_Boss与召唤物行列'
GROUPS = {DENSE, BOSSES, ARMOR, IMPACT, SMALL, LANES, '体香_真实啃咬',
          '安卓调速_高负载转少量僵尸', '测试卡槽_跳关_石块_雪橇车', '合作_取消确认与过期配置'}
DENSE_IDS = {kind + '.' + order for kind in ('pea','fire','blue','fume','bite')
             for order in ('weak-first','weak-last')} | {
                 'three.pumpkin-middle','three.fume-middle-death-next-hit','three.two-hits-one-tick'}
BOSS_TYPES = {'eye.body':4, 'eye.servant':5, 'worm.segment':14, 'skeleton.head':35, 'skeleton.hand':36}


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1048576), b''):
            h.update(block)
    return h.hexdigest()


def combat_errors(report):
    errors = []
    def inventory(label, rows, expected, key, valid):
        actual = Counter(key(r) for r in rows)
        if actual != Counter(expected):
            errors.append(label + ' missing/duplicate/extra: ' + repr(actual - Counter(expected))
                          + ' missing=' + repr(Counter(expected) - actual))
        for r in rows:
            if not valid(r):
                errors.append(label + ' failed: ' + str(key(r)))
    try:
        if report['failures'] != 0:
            errors.append('audit failures: ' + str(report['failures']))
        checks = report['checks']
        inventory('groups', checks, GROUPS, lambda r:r['name'], lambda r:r['passed'] is True)
        groups = {r['name']:r['evidence'] for r in checks if 'evidence' in r}
        inventory(DENSE, groups[DENSE], DENSE_IDS, lambda r:r['id'], lambda r:r['passed'] is True)
        inventory(BOSSES, groups[BOSSES], BOSS_TYPES.keys(), lambda r:r['id'],
                  lambda r:r['passed'] is True and r['fired'] is True and r['hp_lost'] > 0
                  and r['room_steps'] > 0 and r['type'] == BOSS_TYPES.get(r['id']))
        small = {'小鬼僵尸','小型史莱姆','海盗鹦鹉'}
        plants = {'玉米投手','卷心菜投手','西瓜投手','冰瓜投手','甜椒投手','豌豆迫击炮','香蒲'}
        inventory(IMPACT, groups[IMPACT], {(p,t) for p in plants for t in small} | {('豌豆射手','世界吞噬者')},
                  lambda r:(r['plant'],r['target']), lambda r:r['hit'] is True and r['room_steps'] > 0)
        inventory(SMALL, groups[SMALL], small | {'中型史莱姆'}, lambda r:r['target'],
                  lambda r:all(isinstance(r[k],(int,float)) for k in ('x','y')))
        inventory(LANES, groups[LANES], {4,5,13,14,15,35,36}, lambda r:r['type'], lambda r:'fired' in r)
        normal = {'黑普通僵尸':1,'黑路障僵尸':1,'黑铁桶僵尸':1,'橄榄球僵尸':4,'黑橄榄僵尸':4}
        boss = {'克苏鲁之眼':12,'世界吞噬者':2,'骷髅王':10}
        expected = {(n,c):v for n,v in normal.items() for c in (False,True)}
        expected.update({(n,False):v for n,v in boss.items()})
        inventory(ARMOR, groups[ARMOR], expected.keys(), lambda r:(r['target'],r['charmed']),
                  lambda r:r['defense'] == expected.get((r['target'],r['charmed'])) and r['loss']==100-5*r['defense'])
        for name in ('体香_真实啃咬','测试卡槽_跳关_石块_雪橇车','合作_取消确认与过期配置'):
            if groups[name] is not True: errors.append(name + ' evidence missing')
        pacing = groups['安卓调速_高负载转少量僵尸']
        if not (pacing['overloaded_scale'] < .9 and pacing['final_scale'] == 1 and 1 <= pacing['living'] <= 6):
            errors.append('pacing recovery evidence missing')
    except (KeyError, TypeError, ValueError) as err:
        errors.append('missing or malformed combat evidence: ' + str(err))
    return errors


def full_inventory(summary, folder):
    collection = read(folder/'collection.json')
    modules = summary['modules']
    if (not collection or summary.get('scope','full') != 'full' or summary['collection_mismatch']
            or summary.get('source_changed_during_run') or summary.get('fixture_changed_during_run')
            or summary.get('exe_changed_during_run') or summary.get('changed_binaries')
            or Counter(m['module'] for m in modules) != Counter(collection.keys())):
        raise ValueError('Full module collection missing or inconsistent')
    identities = set()
    counts = Counter()
    failures = {}
    for m in modules:
        expected = collection[m['module']]
        rows = read(folder/(m['module']+'.json'))
        actual = ['.'.join((r['module'],r['class'],r['test'])) for r in rows]
        if (not expected or len(set(expected)) != len(expected) or Counter(actual) != Counter(expected)
                or identities.intersection(expected) or m['infrastructure_errors']
                or Counter(r['outcome'] for r in rows) != +Counter(m['counts'])):
            raise ValueError('Incomplete or inconsistent raw module: '+m['module'])
        identities.update(expected)
        counts.update(r['outcome'] for r in rows)
        for case,r in zip(actual,rows):
            if r['outcome'] != 'PASS':
                failures[case] = (r['outcome'], hashlib.sha256(r['detail'].encode('utf-8')).hexdigest())
    if counts != +Counter(summary['counts']):
        raise ValueError('Raw totals disagree with summary')
    if failures != nonpass(summary):
        raise ValueError('Raw failure detail differs from summary')
    return identities


def fire_errors(report):
    plants = ('plant:豌豆射手','plant:原始豌豆射手')
    shooters = ('zombie:豌豆僵尸','zombie:机枪僵尸')
    expected = {(unit,charm,fire) for unit in plants+shooters for charm in (False,True)
                for fire in range(3) if not (charm and unit in plants)}
    try:
        rows=report['cases']
        actual=Counter((r['source'],r['charmed'],r['fire']) for r in rows)
        if (report['passed'] is not True or report['failures']!=0 or actual!=Counter(expected)
                or any(r['passed'] is not True or r['ignited']!=bool(r['fire'])
                       or r['damage']<=0 or r['ally_damage']!=0 for r in rows)):
            return ['Incomplete or failed projectile damage/torch matrix']
    except (KeyError,TypeError) as error:
        return [str(error)]
    return []


def nonpass(summary):
    rows = summary['waivers']['applied'] + summary['waivers']['unexpected_nonpass']
    result = {r['id']:(r['outcome'], r['detail_sha256']) for r in rows}
    if len(result) != len(rows) or len(rows) != sum(summary['counts'][k] for k in ('FAIL','ERROR','SKIP')):
        raise ValueError('Failure signatures disagree with raw totals')
    return result


def classify(case, signature, rules):
    row = rules.get(case, {})
    if (row.get('outcome'), row.get('detail_sha256')) == signature:
        return {k:row[k] for k in ('category','reason','evidence','follow_up') if k in row}
    return dict(category='investigate', reason='新增或变化的失败签名，须重新复核', evidence=case.split('.')[0]+'.json')


def compare(current, previous, current_ids, previous_ids):
    now, old = nonpass(current), nonpass(previous)
    common = current_ids & previous_ids
    return dict(new=sorted((now.keys()-old.keys()) & common | (now.keys()-previous_ids)),
                same=sorted(i for i in now.keys() & old.keys() if now[i] == old[i]),
                changed=sorted(i for i in now.keys() & old.keys() if now[i] != old[i]),
                resolved=sorted((old.keys()-now.keys()) & common),
                added_cases=sorted(current_ids-previous_ids), retired_cases=sorted(previous_ids-current_ids))


def report_failures(summary, folder, baseline):
    rules = read(TRIAGE)
    raw = nonpass(summary)
    waived = {r['id'] for r in summary['waivers']['applied']}
    rows = [dict(id=k, outcome=v[0], detail_sha256=v[1], waived=k in waived, **classify(k,v,rules))
            for k,v in sorted(raw.items())]
    report = dict(cases=rows, counts=dict(Counter(r['category'] for r in rows)),
                  unwaived_counts=dict(Counter(r['category'] for r in rows if not r['waived'])))
    if summary['scope'] == 'full':
        ids = full_inventory(summary, folder)
        if baseline:
            previous = read(baseline)
            before = full_inventory(previous, baseline.parent)
            delta=compare(summary, previous, ids, before)
            old_failures=nonpass(previous)
            previous_findings=[dict(id=k, status=status, **classify(k,old_failures[k],rules))
                               for status in ('resolved','changed') for k in delta[status]]
            report.update(baseline=str(baseline), baseline_sha256=digest(baseline),
                          comparison=delta, previous_findings=previous_findings)
        else:
            report['baseline_missing'] = True
    return report
