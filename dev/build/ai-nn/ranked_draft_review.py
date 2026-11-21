"""Audit frozen draft choices and compare each seat to its own initial weights on new ranked seeds."""
from collections import Counter
import sqlite3
from ranked_draft_train import DRAFT, META, RULES, SIDES, Room, DraftNet, check_game, read, rows, sha, write
import numpy as np

def review():
    report=read(DRAFT/'results.json')
    clock=read(DRAFT/'clock.json')
    assert sha(DRAFT/'frozen.npz')==report['frozen'] and sha(DRAFT/'initial.npz')==clock['initial']
    room=Room()
    try:
        start=DraftNet(room.catalog).load(DRAFT/'initial.npz');final=DraftNet(room.catalog).load(DRAFT/'frozen.npz')
    finally:room.close()
    with sqlite3.connect((DRAFT/'draft.sqlite').as_uri()+'?mode=ro',uri=True) as db:
        assert db.execute('pragma quick_check').fetchone()==('ok',)
        training,test=rows(db,'train'),rows(db,'blind')
    assert {d['setup']['seed'] for d in training}.isdisjoint(d['setup']['seed'] for d in test)
    for d in training+test:
        for sc in d['drafts']:check_game({'rules':RULES,**sc})
        if 'arms' in d:
            for arm in d['arms']:
                assert arm['timeout']==('extension' in arm)
        if d['phase']=='train':
            j=d['step']-1;a,b=d['drafts']
            assert a['draft_history'][:j]==b['draft_history'][:j]
            assert [s['draft_history'][j]['card'] for s in (a,b)]==d['alternatives']
    weight_shift={s:round(float(np.linalg.norm(final.w[j]-start.w[j])),5) for j,s in enumerate(SIDES)}
    def count_patterns(sc):
        chosen={s:set() for s in SIDES};out=Counter()
        for a in sc['draft_history']:
            k=a['card'];s=a['side'];other=SIDES[1-SIDES.index(s)]
            if k is None:continue
            c=final.cards[k]
            if a['kind']=='pick':
                if a['stage']=='opening_pick' and final.parents[k] and not final.parents[k]&chosen[s]:out[s,'开局先取带前体秘籍']+=1
                if k in ('plant:花盆','plant:睡莲','plant:咖啡豆'):out[s,'选取指定环境工具']+=1
                chosen[s].add(k)
            elif c['category']=='secret':
                if final.parents[k]&chosen[other]:out[s,'对手已亮前体时禁其秘籍']+=1
                if (final.mentions[k]-final.parents[k])&chosen[other]:out[s,'禁用目标或公开说明涉及对手已选单位的秘籍']+=1
        return out
    lines=['# 胜率七卡槽选卡复测','',
           f"双方各有独立权重，同一原生房间内按轮次选、禁。训练时段为 {report['started']} 至 {report['freeze']}。",'',
           f"训练尝试 {len(training)} 组同前缀分叉，打了 {report['training_games']} 场常规实战。两端都能进入实战的分叉有 {len(training)-report['unstartable']} 组。常规时限 600 秒，遇超时续至 1,200 秒。",'',
           '| 轮选方 | 独立开局有效/尝试 | 初始真胜 | 冻结真胜 | 保住旧胜 | 旧败变真胜 | 旧败变超时 | 共同窗口每分钟部署 |',
           '|---|---:|---:|---:|---:|---:|---:|---|']
    coverage={};diversity={};examples=[]
    for s in SIDES:
        t=report['blind'][s];w=t['transitions'];n0=sum(n for k,n in w.items() if k.startswith('W'))
        n1=sum(n for k,n in w.items() if k.endswith('W'));freq=t['deployments_per_minute']
        own=[d for d in test if d['seat']==s];name='植物' if s=='plant' else '僵尸'
        normalized=lambda deck:tuple(sorted(deck))
        observed={normalized(a['decks'][s]) for d in training for a in d['drafts']}
        tested={normalized(d['drafts'][1]['decks'][s]) for d in own}
        diversity[s]=dict(unique=len(tested),present_in_training=len(tested&observed))
        lines.append(f"| {name} | {t['pairs']}/{len(own)} | {n0} | {n1} | {w.get('WW',0)}/{n0} | {w.get('LW',0)} | {w.get('LT',0)} | {freq[0]:.2f} → {freq[1]:.2f} |")
        a,b=Counter(),Counter()
        for d in own:
            if 'arms' not in d:continue
            a.update(count_patterns(d['drafts'][0]));b.update(count_patterns(d['drafts'][1]))
        coverage[s]={key:[a[s,key],b[s,key]] for seat,key in a.keys()|b.keys() if seat==s}
    lines+=['','双方局内对手固定为纯 r22 镜像，或历史植物对 r22 僵尸、历史植物对历史僵尸。终测每次只替换一方选卡权重。每分钟部署包括墓碑。','',
            '| 轮选方 | 公开轮选行为 | 初始次数 | 冻结次数 |','|---|---|---:|---:|']
    for s,patterns in coverage.items():
        for k,(a,b) in patterns.items():lines.append(f"| {'植物' if s=='plant' else '僵尸'} | {k} | {a} | {b} |")
    lines+=['','上表记录实际选择次数。提前抢选带来的威慑、跨牌组的稳定反制能力，还需用同前缀实战反复检验。','',
            '## 同前缀实战例子','']
    for s in SIDES:
        trials=[d for d in training if d['seat']==s and d.get('update')]
        def genuine(d):return set(d['utility'])=={-1,1}
        for kind in ('pick','ban'):
            sample=next(iter(sorted((d for d in trials if d['kind']==kind),key=genuine,reverse=True)),None)
            if not sample:continue
            d=sample;xs=d['alternatives'];outs=[]
            for arm in d['arms']:
                outs.append('超时' if arm['timeout'] else '胜' if arm['winner']==s else '负')
            examples.append(dict(seed=d['setup']['seed'],seat=s,step=d['step'],choices=xs,outcomes=outs,stage=d['stage']))
            lines.append(f"- 种子 {d['setup']['seed']}，{'植物' if s=='plant' else '僵尸'}第 {d['step']} 手{'选' if kind=='pick' else '禁'}。{xs[0] or '跳过'}续打为{outs[0]}，{xs[1] or '跳过'}续打为{outs[1]}。")
    if not examples:lines.append('本轮没有取得改变胜负并更新策略的同前缀对照。')
    lines+=['','## 开局覆盖与出兵节奏','',
            f"按七张牌的无序集合去重，冻结植物在盲测中选出 {diversity['plant']['unique']} 副牌，僵尸选出 {diversity['zombie']['unique']} 副。其中出现在训练分叉里的牌组分别有 {diversity['plant']['present_in_training']}、{diversity['zombie']['present_in_training']} 副。",
            f"只替换僵尸选卡头时，共同时窗内每分钟实际出兵从 {report['blind']['zombie']['troops_per_minute'][0]:.2f} 变为 {report['blind']['zombie']['troops_per_minute'][1]:.2f}，已排除墓碑。"]
    joint=DRAFT/'joint.json'
    if joint.exists():
        m=read(joint);assert m['frozen']==report['frozen']
        lines+=['','## 双方权重交叉复测','',
                '| 植物选卡 | 僵尸选卡 | 植物胜 | 僵尸胜 | 超时 | 平均秒数 |','|---|---|---:|---:|---:|---:|']
        for role,p,z in [('initial','初始','初始'),('plant_only','冻结','初始'),('zombie_only','初始','冻结'),('both','冻结','冻结')]:
            v=m['summary'][role];c=v['outcomes']
            lines.append(f"| {p} | {z} | {c.get('plant',0)} | {c.get('zombie',0)} | {c.get('timeout',0)} | {v['mean_seconds']:.1f} |")
    probes=[DRAFT/n for n in ('diagnostics.json','additional-diagnostics.json') if (DRAFT/n).exists()]
    if probes:
        names=dict(opening_secret='先秘籍或先前体',visible_parent_ban='见到前体后禁秘籍',visible_multi_target_ban='禁用多个单位可受益的秘籍',
                   environment_tool='环境工具与其他选择',broad_effect_ban='禁用广泛生效的秘籍')
        lines+=['','## 独立局面的一手对照','',
                '每行比较同一公开前缀下的两手合法行动，续打使用同一局内控制器。另记录网络在全体合法行动上的首选。第一组取自贪心轮选，补充组用随机采样产生可达前缀，之后恢复贪心轮选。广泛生效按至少半数本方单位的原生卡牌属性发生变化识别。','',
                '| 测项 | 种子 | 手数 | 全部合法行动首选 | 两个备选 | 行动方续打结果 |','|---|---:|---:|---|---|---|']
        for path in probes:
            p=read(path);assert p['frozen']==report['frozen']
            for d in p['cases']:
                ks=[k or '跳过' for k in d['alternatives']]
                ys=['超时' if arm['timeout'] else ('胜' if arm['winner']==d['side'] else '负') for arm in d['arms']]
                lines.append(f"| {names[d['test']]} | {d['seed']} | {d['step']} | {d['global_choice'] or '跳过'} | {' / '.join(ks)} | {' / '.join(ys)} |")
    write(DRAFT/'review.json',dict(initial=clock['initial'],frozen=report['frozen'],weight_shift=weight_shift,patterns=coverage,deck_diversity=diversity,examples=examples))
    (DRAFT/'选卡复盘.md').write_text('\n'.join(lines)+'\n','utf8')

if __name__=='__main__':review()
