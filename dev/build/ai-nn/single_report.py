"""Make the Chinese training report from verified native receipts."""
from collections import Counter
import gzip
import json
from pathlib import Path
from single_study import OUT,R,read,sha

def spawn_breakdown(rows):
    card_file=Path(read(R/'dist/latest-native-release.json')['target']).parent/'extract/data/_resolved_cards.json'
    cards=read(card_file)['day']
    totals={}
    for row in rows:
        key=(row['old'],row['new'])
        entry=totals.setdefault(key,dict(pairs=0,seconds=0.,troops=[0,0],graves=[0,0]))
        entry['pairs']+=1
        entry['seconds']+=row['window']
        for j,arm in enumerate(('baseline','candidate')):
            with gzip.open(OUT/'games'/(row[arm]+'.jsonl.gz'),'rt',encoding='utf8') as stream:
                stream.readline()
                actions=json.loads(stream.readline())['activity']
            for e in actions:
                if e['time']>row['window'] or e['kind']!='deploy' or e['side']!='zombie' or not e['card'].startswith('zombie:'):continue
                column='graves' if cards[e['card']]['behavior']=='grave' else 'troops'
                entry[column][j]+=1
    return totals
def report():
    whole=read(OUT/'audit.json');test=read(OUT/'test.json');zl=read(OUT/'zombie.json');pl=read(OUT/'plant.json')
    review=read(OUT/'review.json');split=read(OUT/'splits.json');dyn=test['dynamics']
    base='../../test_results/ai-nn-home-options-20261118/single/'
    ref=lambda t,k:f'[{t}]({base}{k})'
    lab={-1:'负',0:'超时',1:'胜'}
    labels={'z16':'单招僵尸对 z16','persistent':'单招僵尸对持续换头','alternate':'另一组单招门槛对 z16','plant':'新植物对上轮植物'}
    l=[];add=l.append;add('# 家院单招换头与到位决策')
    add(f"正式模拟版本为 {whole['official']}。一轮选择只控制一次战术动作。墓碑变化、冷却完成、资源够用或常规动作时钟到期时重新评分，网络可以再选事件头，也可以交回 z16。移动中的公共事件可以中断前移。到位且放置合法时，另一个价值读出比较马上建墓和推迟一次，下一次仍可选回同一坐标。实际卡牌费用、地形和来源墓碑由原生模拟校验。"+ref('最终原生源码指纹','live-build.json'))
    add('## 新开局与牌组')
    add(f"两批各 12 个家院开局，每批 6 昼、6 夜。24 套植物牌组和 24 套僵尸牌组分别互异，排除了开发牌组、已用种子及 {split['excluded'][0]} 套历史植物牌组和 {split['excluded'][1]} 套历史僵尸牌组。冻结两侧权重后分别对 r22、历史 H 和 B 进行单侧替换，每项 72 个配对。"+ref('开局与分组','splits.json')+' · '+ref('冻结后的复测设计','sealed-design.json'))
    unresolved='超时' if all(r['native_draws']==[0,0] for r in test['results'].values()) else '平或超时'
    table=[f'| 对照 | 基线胜 / {unresolved} / 负 | 候选胜 / {unresolved} / 负 | 保住旧胜 | 旧败转真胜 | 两批真胜增量 | 真胜率增量的 95% 区间 |','|---|---:|---:|---:|---:|---:|---:|']
    fmt=lambda x:' / '.join(map(str,x))
    for k,r in test['results'].items():
        c=r['all']['counts'];diff=[r[j]['counts']['new'][0]-r[j]['counts']['old'][0] for j in ('a','b')];ci=r['all']['true_win_delta95']
        table.append(f"| {labels[k]} | {fmt(c['old'])} | {fmt(c['new'])} | {c['kept']}/{c['old'][0]} | {c['gain']}/{c['old'][2]} | {diff[0]:+d}、{diff[1]:+d} | {ci[0]*100:.1f} 至 {ci[1]*100:.1f} 个百分点 |")
    add('\n'.join(table));add('区间按开局重采样，同一开局的三个对手一起保留。单局常规时限为 600 游戏秒。'+ref('逐局结果及双方活动','test.json'))
    for k,r in test['results'].items():
        rows=r['all']['rows']
        losses=sum(v['old']==1 and v['new']==-1 for v in rows)
        unresolved_wins=sum(v['old']==1 and v['new']==0 for v in rows)
        add(f"{labels[k]}有 {losses} 个旧胜直接变负，另有 {unresolved_wins} 个旧胜变为{unresolved}。")
    table=['| 对手（每格 24 局） | z16 | 持续换头 | 单招僵尸 | 上轮植物 | 新植物 |','|---|---|---|---|---|---|']
    for o in 'rhb':
        def col(k,side):return fmt(test['results'][k]['all']['per_opponent'][o][side])
        table.append('| '+('r22' if o=='r' else o.upper())+' | '+' | '.join([col('z16','before'),col('persistent','before'),col('z16','after'),col('plant','before'),col('plant','after')])+' |')
    add('\n'.join(table))
    for k in ('z16','persistent','plant'):
        r=test['results'][k]['all'];x,y=[r['tempo'][j] for j in ('parent','candidate')]
        def rate(s):return f"{x['common_window_deploys_per_min'][s]:.2f} → {y['common_window_deploys_per_min'][s]:.2f}"
        add(f"{labels[k]}的共同观察窗口内，植物每分钟部署 {rate('plant')}，僵尸 {rate('zombie')}。平均封顶局长 {x['mean_capped_seconds']:.1f} → {y['mean_capped_seconds']:.1f} 秒。")
        troops=test['results'][k]['troop_tempo']
        for name,title in [('all','全部配对'),('old_loss_to_win','旧败转真胜的配对')]:
            if name not in troops:continue
            t=troops[name];before,after=t['troops_per_min']
            add(f"{title}（{t['pairs']} 局）中，按正式卡表区分实际部署的僵尸兵和墓碑，僵尸每分钟出兵 {before:.2f} → {after:.2f}，同期出兵总数 {t['troops'][0]} → {t['troops'][1]}，建墓 {t['graves'][0]} → {t['graves'][1]}。")
    hz=test['extensions']
    root=test['results']['z16']
    totals=spawn_breakdown(root['all']['rows'])
    assert all(sum(s['troops'][arm] for s in totals.values())==root['troop_tempo']['all']['troops'][arm] for arm in (0,1))
    table=['| z16 → 单招僵尸 | 配对 | 实际出兵数 | 每分钟出兵 | 同期建墓数 |','|---|---:|---:|---:|---:|']
    for (before,after),s in sorted(totals.items(),reverse=True):
        troops=s['troops'];graves=s['graves'];secs=s['seconds']
        table.append(f"| {lab[before]} → {lab[after]} | {s['pairs']} | {troops[0]} → {troops[1]} | {60*troops[0]/secs:.2f} → {60*troops[1]/secs:.2f} | {graves[0]} → {graves[1]} |")
    add('\n'.join(table))
    add('各组按常规终局结果回看，给两条路线保留一样长的观察窗口；分组数字描述实际节奏，无法单独断定某次减兵造成了败局。')
    for k in test['results']:
        for old in (-1,1):
            rs=[v for v in hz if v['comparison']==k and v['old']==old]
            if rs:add(f"{labels[k]}有 {len(rs)} 个旧{lab[old]}转超时，延长至结束或 1,200 秒后为 {sum(v['late']==1 for v in rs)} 胜、{sum(v['late']==-1 for v in rs)} 负、{sum(v['timeout'] for v in rs)} 仍超时。")
    add('## 上轮的 7 个旧败和 11 个旧胜')
    add('这 18 个配对来自 6 个开局。逐帧比较全部僵尸实发命令，三个分支在分歧前共享原生战场、随机状态和日志前缀。单招分支在分歧帧复现了持续换头的完整命令，到下一次动作机会或公共事件清除未完成的路线，交回 z16。两条自然路线另核对上一轮整局日志哈希。'+ref('三路命令、归还时刻与分支结果','review.json'))
    hist=zl['regressions'][zl['selected']];trained={(r['id'],r['opponent']):r['new'] for r in hist}
    tab=['| 上轮开局 | 对手 | 首次分歧（秒） | z16 | 只换一招 | 持续换头 | 单招后归还（秒） | 训练后整局 |','|---|---|---:|---|---|---|---:|---|']
    for r in sorted(review['rows'],key=lambda r:(r['results'][0],r['id'],r['opponent'])):
        i,o=r['id'],r['opponent'];opp='r22' if o=='r' else o.upper()
        tab.append(f"| {i} | {opp} | {r['tick']/30:.3f} | "+' | '.join(lab[v] for v in r['results'])+f" | {r['release']:.3f} | {lab[trained[i,o]]} |")
    add('\n'.join(tab))
    old_wins=[r for r in hist if r['old']==1]
    old_losses=[r for r in hist if r['old']==-1]
    add(f"训练后的整局策略在这 18 个已知配对中，保住 {sum(r['new']==1 for r in old_wins)}/{len(old_wins)} 个 z16 旧胜，赢下 {sum(r['new']==1 for r in old_losses)}/{len(old_losses)} 个 z16 旧败。独立的新开局结果列在首表。")
    add('在原有 7 个败转胜配对里，只借第一招取得 5 胜，另外 2 局到了 600 秒仍超时，延长后均负。在原先被持续换头丢掉的 11 个旧胜里，只借第一招保住 3 胜，其余 6 负、2 超时。训练后整局一列包含反复换招，属于开发回归。')
    add('## 到位时建墓或等待')
    for file,title in [('arrivals','上一轮盲测的全部实际到位点'),('earlier-arrivals','更早的建墓干预'),('visited-arrivals','本轮临时策略的训练点'),('sealed-arrivals','新开局中冻结策略的到位点')]:
        d=read(OUT/(file+'.json'));rs=d['rows'];pairs=Counter(tuple(r['results']) for r in rs)
        add(f"{title}共复演 {len(rs)} 组。到位等待独胜 {sum(n for (a,b),n in pairs.items() if a==1 and b!=1)} 组，立即建墓独胜 {sum(n for (a,b),n in pairs.items() if b==1 and a!=1)} 组，常规胜负或超时相同 {sum(n for (a,b),n in pairs.items() if a==b)} 组。"+ref('同局面证据',file+'.json'))
    add(f"72 个冻结单招头对局中，有 {sum(r['changed'] for r in dyn)} 局与 z16 的完整战斗轨迹不同。在 {sum(r['returns']>0 for r in dyn)} 局实际交回过 z16，总计 {sum(r['returns'] for r in dyn)} 次，其中 {sum(r['public_returns'] for r in dyn)} 次发生在墓碑、资源或冷却事件。冻结策略实际到位 {sum(r['arrivals'] for r in dyn)} 次，其中选择等待 {sum(r['defer'] for r in dyn)} 次。")
    ds=read(OUT/'sealed-choices.json');rs=ds['rows']
    add(f"独立抽查了 {len(rs)} 个新开局公共事件，在同一事件上强制交回 z16 或续用一招，再交还给同一冻结网络。{sum(r['distinct'] for r in rs)} 组实际整局轨迹不同，{sum(r['results'][0]!=r['results'][1] for r in rs)} 组常规结果不同。"+ref('交回与续招对照','sealed-choices.json'))
    visited=read(OUT/'visited.json')['rows']
    differing=0
    for r in visited:
        hashes=[read(OUT/'games'/(key+'.jsonl.receipt.json'))['battle'] for key in r['keys'][:2]]
        differing+=hashes[0]!=hashes[1]
    add(f"训练时也对临时网络走到的 {len(visited)} 个决策点做过相同干预。交回与续招产生不同整局实发轨迹的有 {differing} 组；续招把交回后的失败改成真胜 {sum(r['results'][:2]==[-1,1] for r in visited)} 组，反向把胜改成负 {sum(r['results'][:2]==[1,-1] for r in visited)} 组。"+ref('训练期的交回与续招配对','visited.json'))
    for filename,title in [('sealed-choices','交回 z16 或续招'),('sealed-arrivals','到位建墓或等一招')]:
        study=read(OUT/(filename+'.json'))
        interventions=study['rows']
        changed=[r for r in interventions if r['results'][0]!=r['results'][1]]
        if changed:
            better=sum(r['results'][r['choice']]==max(r['results']) for r in changed)
            add(f"在{title}的 {len(changed)} 个常规结局有差别的盲测干预中，冻结网络选中了结局较好的一招 {better} 次。胜、超时、负按此顺序比较。")
        if study['extensions']:
            tails={v['extended']:v for v in study['extensions']}.values()
            add(f"上述{title}干预中有 {len(tails)} 条旧败转超时的路线，延长后僵尸 {sum(v['winner']=='zombie' for v in tails)} 胜、{sum(v['winner']=='plant' for v in tails)} 负、{sum(v['timeout'] for v in tails)} 仍超时。")
    add('## 训练与核验')
    add('先冻结 plant-1p、上轮植物候选和历史 H 练僵尸，用整局胜负拟合一次选招的收益，同一来源与开局内分摊样本权重。同一观察窗口内减少本方部署会扣减训练目标，训练时这项包含建墓和出兵，盲测时另核实际出兵。对旧败转超时的分支，延长后能赢且通过活动检查才给部分收益。再冻结单招僵尸，植物沿上轮更新方向及其正交方向搜索权重，分别对单招僵尸、持续换头僵尸和 r22 复核。'+ref('僵尸权重选择','zombie.json')+' · '+ref('植物权重选择','plant.json'))
    add('三个判断各用线性项和 12 个固定的 tanh 隐藏特征，以配对收益拟合输出权重。下表中的正收益指备选动作相对参考动作获得正的训练目标，包含部署节奏和延长赛的影响。')
    fits=['| 备选动作 | 原始训练对 | 去重后 | 开局权重组 | 正收益 | 负收益 |','|---|---:|---:|---:|---:|---:|']
    for title,info in zip(('借用事件头一招','选择前移','到位后立即建墓'),zl['training']):
        fits.append(f"| {title} | {info['input']} | {info['unique']} | {info['openings']} | {info['positive']} | {info['negative']} |")
    add('\n'.join(fits))
    prior_sites={r['id'] for r in read(OUT/'arrivals.json')['rows']}
    revisited={r['id'] for r in read(OUT/'visited-arrivals.json')['rows'] if r['set']=='history'}
    add(f"到位训练中有 {len(prior_sites & revisited)} 个历史开局既在原策略下取样，也在本轮临时策略下取样。它们在两种来源中分别获得权重。")
    validation=zl['validation'][zl['selected']]['rows']
    oldwins=[r for r in validation if r['old']==1]
    checks=list(spawn_breakdown(validation).values())
    seconds=sum(s['seconds'] for s in checks)
    rates=[sum(s['troops'][j] for s in checks)*60/seconds for j in (0,1)]
    add(f"冻结前的 {len(validation)} 个验证配对覆盖 {len({r['id'] for r in validation})} 个开局，但 z16 的 {len(oldwins)} 胜只来自 {len({r['id'] for r in oldwins})} 个开局。入选头在验证上的实际出兵从每分钟 {rates[0]:.2f} 增到 {rates[1]:.2f}。新开局上的趋势相反。下一轮应增加 z16 能赢且起手打法不同的独立验证开局，同时覆盖主动出兵能逆转的旧败。")
    for k,p in [('僵尸',Path(zl['path'])),('植物',Path(pl['path']))]:add(f"{k}权重为 "+ref(p.name,str(p.relative_to(OUT)).replace(chr(92),'/'))+f"，SHA-256 前 16 位为 `{sha(p)[:16]}`。")
    passed=[labels[k] for k,r in test['results'].items() if r['stable']]
    add('稳定提升要求保住旧胜、两批真胜都增加、按开局计算的真胜率增量下界为正，并维持本方共同窗口的部署频率。僵尸还需维持实际出兵频率。'+('通过的对照为'+'、'.join(passed)+'。' if passed else '本轮没有对照同时达到这些条件。')+'本轮权重保存在研究程序中。')
    peak=max(read(p)['peak'] for p in OUT.glob('disk-*.json'))
    add(f"共核验 {whole['limits'].get('600',0)} 场常规运行、{whole['limits'].get('1200',0)} 场延长运行。采用无头模拟、30 Hz 逻辑步、15 Hz 控制和最多 8 场并发。所有延长局均核对前 600 秒的动作记录，磁盘上限设为 5 GiB。含既有受控训练目录，文件长度采样峰值为 {peak/2**30:.3f} GiB，结束时按文件身份去重后读取的 NTFS 实际分配量为 {whole['allocated_after_cleanup']/2**30:.3f} GiB。本轮产物约 {whole['run_bytes']/2**20:.1f} MiB，已清理 {whole['removed_objects']/2**20:.1f} MiB 本轮可重建的编译目标。"+ref('完整审计','audit.json')+' · '+ref('原生读出复算','readout-parity.json'))
    path=R/'docs/ai-nn/家院单招换头与到位决策_20261118.md';path.write_text('\n\n'.join(l)+'\n','utf8');return path
if __name__=='__main__':print(report())
