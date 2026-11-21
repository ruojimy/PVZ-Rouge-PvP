"""Verify native runs, opening isolation, tempo features and extended matches."""
import re
from tempo_train import *
from option_audit import verify_games
from switch_fit import allocated

def audit():
    index,limits=verify_games(OUT,expected_map='家院')
    split=read(OUT/'split.json');screen=read(OUT/'screen.json');test=read(OUT/'test.json')
    locked=read(OUT/'sealed.json');design=read(OUT/'design.json')
    release=read(R/'dist/latest-native-release.json');assert design['release']==sha(Path(release['target']))==release['exe_sha256']
    assert sha(CARDS)==design['catalog']
    night=read(CARDS)['night']
    assert all(v['behavior']==night[k]['behavior'] for k,v in CATALOG.items() if k.startswith('zombie:'))
    config=read(OUT/'build.json');assert config['binary']==sha(EXE)
    assert sha(EXE.parent/'SDL2.dll')==sha(LIVE.parent/'SDL2.dll')
    assert all(sha(OUT/'native-src'/k)==v for k,v in config['sources'].items())
    assert all(sha(BUILD/'Release'/k)==v for k,v in config['libraries'].items())
    for side in ('plant','zombie'):
        m=read(OUT/(side+'.json'))
        assert sha(Path(m['path']))==m['sha256']==locked[side]==test[side]
    assert read(OUT/'plant.json')['zombie']==locked['zombie']
    assert sha(Path(read(OUT/'contrast.json')['path']))==locked['secondary']
    assert sha(OUT/'models/fixed-troop-history.json')==locked['history_control']
    assert sha(CORPUS/'index.json')==split['corpus']==locked['corpus'] and locked['ids']==split['a']+split['b']
    entries=read(CORPUS/'index.json')['entries'];new={r['id']:r for r in entries}
    assert len(entries)==len({r['seed'] for r in entries})==120 and all(r['map']=='家院' for r in entries)
    history=[r for f in split['indexes'] for r in read(R/f)['entries'] if r.get('map')=='家院' and 'decks' in r]
    assert not {r['seed'] for r in entries}&{r['seed'] for r in history}
    for seat in (0,1):
        assert len({deck(r)[seat] for r in entries})==120
        assert not {deck(new[i])[seat] for i in locked['ids']}&{deck(r)[seat] for r in history}
    assert all(sum(new[i]['night'] for i in split[k])==6 for k in ('a','b'))
    coverage={}
    for group in ('train','val'):
        rows=screen[group];wins=[r for r in rows if r['result']==1];loss=[r for r in rows if r['result']==-1]
        assert {r['id'] for r in rows}<=set(split[group+'_pool']) and len({r['id'] for r in rows})==len(rows)
        assert all(index[r['key']]['parameters']['policy']==sha(PARENT) for r in rows)
        coverage[group]=dict(wins=len(wins),losses=len(loss),winning_signatures=len({json.dumps(r['signature']) for r in wins}),
             winning_command_counts=[[r['id'],r['opponent'],r['troops'],r['graves']] for r in wins])
    assert set(read(OUT/'zombie.json')['ordinary']).isdisjoint({r['id'] for r in screen['val']})
    z=read(OUT/'zombie.json')
    val_rows=z['validation'][z['selected']]['enriched']['rows']
    style={}
    for i in z['enriched']:
        traces={r['opponent']:receipt(OUT,r['baseline'])[1] for r in val_rows if r['id']==i}
        for a,b in (('p','o'),('p','h'),('o','h')):
            window=min(traces[a]['time'],traces[b]['time'],120.)
            def actions(teacher):
                return [(v['time'],v['card']) for v in traces[teacher]['activity']
                        if v['kind']=='deploy' and v['side']=='plant' and v['time']<window]
            style[a+b]=style.get(a+b,0)+int(actions(a)!=actions(b))
    expected={(i,o) for i in locked['ids'] for o in 'rhb'}
    for name,result in test['results'].items():
        rows=result['all']['rows'];assert len(rows)==72 and {(r['id'],r['opponent']) for r in rows}==expected
        side='plant' if name.startswith('plant') else 'zombie'
        for r in rows:
            a,b=[index[r[k]]['parameters'] for k in ('baseline','candidate')]
            assert a['corpus']==b['corpus']==split['corpus'] and a['binary']==b['binary']==config['binary']
            assert a['opening']==b['opening']==r['id']
            assert b['plant' if side=='plant' else 'policy']==locked['secondary' if name=='secondary_z16' else side]
            assert a['zombie' if side=='plant' else 'plant']==b['zombie' if side=='plant' else 'plant']
        required={(r['baseline'],r['candidate']) for r in rows if r['old'] and index[r['candidate']]['timeout']}
        assert required=={(e['base'],e['candidate']) for e in test['extensions'] if e['comparison']==name}
    unique=set()
    for label in ('rollouts','zombie','plant','regression','test'):
        doc=read(OUT/(label+'.json'))
        for e in doc['extensions']:
            a,b=[index[e[k]] for k in ('candidate','extended')]
            assert a['timeout'] and index[e['base']]['winner']!=e['side']
            assert {**a['parameters'],'limit':1200}==b['parameters'] and e['winner']==b['winner']
            if e['extended'] not in unique:
                ts=[receipt(OUT,e[k])[1] for k in ('candidate','extended')]
                assert [v for v in ts[0]['switches'] if v['t']<600]==[v for v in ts[1]['switches'] if v['t']<600]
                unique.add(e['extended'])
    assert unique=={k for k in index if index[k]['parameters']['limit']==1200}
    cfg=read(Path(read(OUT/'zombie.json')['path']))['switch'];count=Counter();held_checks=[]
    for row in test['results']['z16']['all']['rows']:
        t=receipt(OUT,row['candidate'])[1]
        for e in t['switches']:
            if e['phase']=='arrival_vote':
                assert np.allclose(e['x'][-6:],history_features(t,round(e['t']*30)),rtol=0,atol=1e-8)
                value=prediction(e['x'],cfg['arrival_live'])
                assert abs(value-e['gain'])<1e-8 and e['place']==(value>=-cfg['arrival_margin']);count['arrival']+=1
        if len(held_checks)<3 and row['opponent'] not in {o for o,_ in held_checks}:
            sampled=read(Path(read(OUT/'zombie.json')['path']));sampled['switch']['sample']=True
            g=live(row['id'],MODELS[row['opponent']],policy('sealed-readout',sampled));held_checks.append((row['opponent'],(row,g)))
    batch('final score reproduction with logging', [g for _,(_,g) in held_checks])
    for _,(r,g) in held_checks:
        tr=trace(g);assert tr['log_sha256']==index[r['candidate']]['battle']
        for e in tr['switches']:
            if e['phase']!='lease' or 'x' not in e:continue
            assert np.allclose(e['x'][-6:],history_features(tr,round(e['t']*30)),rtol=0,atol=1e-8)
            q=prediction(e['x'],cfg['one_head']);v=prediction(e['x'],cfg['trip_head']) if e['offered'] else -100.
            choice=2 if e['offered'] and v>cfg['trip_margin'] and v>q else int(q>cfg['one_margin'])
            assert e['choice']==choice and abs(q-e['v'])<1e-8 and abs(v-e['trip'])<1e-8;count['lease']+=1
    index,limits=verify_games(OUT,expected_map='家院')
    assert read(OUT/'parity.json')['checks']['lease']>0
    gates={}
    for label in ('z16','secondary_z16'):
        if label not in test['results']:continue
        totals=Counter()
        for r in test['results'][label]['all']['rows']:
            tr=receipt(OUT,r['candidate'])[1]
            choices=[e for e in tr['switches'] if e['phase']=='lease']
            taken=sum(e['choice']!=0 for e in choices)
            totals['decisions']+=len(choices);totals['alternate']+=taken;totals['games_active']+=int(taken>0)
            totals['public_returns']+=sum(e['from']==1 and e['choice']==0 and bool(e['mask']&15) for e in choices)
        gates[label]=dict(totals)
    removed=0
    for folder in (OUT/'native/position_match.dir/Release',OUT/'home-draft/deck73_corpus.dir/Release'):
        assert folder.resolve().is_relative_to(OUT.resolve())
        for p in folder.glob('*.obj'):
            removed+=p.stat().st_size;p.unlink()
    for attempt in range(3):
        try:
            physical=allocated((ROOT,PREV,NIGHT,BUILD,PRIOR_HOME,PRIOR))
            break
        except FileNotFoundError as e:
            if attempt==2 or '.tmp' not in str(e.filename):raise
    assert physical<CAP and not list((OUT/'temp').glob('*.jsonl')) and not list((OUT/'games').glob('*.partial'))
    measurement=dict(storage=physical,run_bytes=size(OUT),removed_objects=removed)
    if (OUT/'audit.json').exists():
        # Keep the first storage measurement after cleanup when verifying a completed run.
        previous=read(OUT/'audit.json')
        assert removed==0
        measurement={k:previous[k] for k in measurement}
    fixed(OUT/'audit.json',dict(games=len(index),full=limits[600],extended=limits[1200],short=sum(n for k,n in limits.items() if k<600),
        completed_extensions=len(unique),coverage=coverage,plant_style_differences=style,gates=gates,scores=dict(count),**measurement))
    report()

def secondary_arrivals(t):
    comparison=t['results'].get('secondary_z16')
    if not comparison:return None
    model=read(Path(read(OUT/'contrast.json')['path']))['switch']
    rows=[]
    for r in comparison['all']['rows']:
        tr=receipt(OUT,r['candidate'])[1]
        for e in tr['switches']:
            if e['phase']!='arrival_vote':continue
            tick=round(30*e['t']);q=prediction(e['x'],model['arrival_live'])
            assert np.allclose(e['x'][-6:],history_features(tr,tick),atol=1e-8,rtol=0)
            assert abs(q-e['gain'])<1e-8 and e['place']==(q>=-model['arrival_margin'])
            card=e['target'][1];x,y=e['target'][3:5]
            accepted=any(c['tick']==tick and c['kind']=='deploy' and c['accepted'] and
                         (c.get('card'),c.get('x'),c.get('y'))==(card,x,y) for c in tr['accepted_commands'])
            assert accepted==e['place']
            rows.append(dict(id=r['id'],opponent=r['opponent'],time=e['t'],place=e['place'],value=q,site=e['target'],key=r['candidate']))
    fixed(OUT/'secondary-arrivals.json',dict(model=read(OUT/'contrast.json')['sha256'],rows=rows))
    return rows

def report():
    a=read(OUT/'audit.json');t=read(OUT/'test.json');z=read(OUT/'zombie.json');p=read(OUT/'plant.json')
    data=read(OUT/'rollouts.json');hist=read(OUT/'regression.json')['rows'];names={'z16':'z16','single':'上轮单招僵尸','persistent':'持续换头僵尸','history_fixed':'六项新输入固定为训练均值','plant_latest':'上轮植物','plant_anchor':'上轮之前的植物','secondary_z16':'z16 与保胜后优先翻盘的副候选'}
    path='../../test_results/ai-nn-home-options-20261118/troop-tempo/'
    link=lambda n,k:f'[{n}]({path}{k})'
    fmt=lambda n:' / '.join(map(str,n))
    lines=['# 家院实际出兵与多开局保胜训练']
    add=lines.append
    add('本轮于 11 月 18 日晚开始，19 日凌晨完成。所有对局使用 PvP74.4 r3 无头原生内核。首先固定三种植物策略训练僵尸，再冻结入选僵尸权重，训练植物。每次换头仍只借一招，后续公共事件可以交回 z16。')
    primary=t['results']['z16']['all'];counts=primary['counts'];gates=a['gates']['z16']
    add(f"新开局主候选保住 {counts['kept']}/{counts['old'][0]} 个 z16 旧胜，赢下 {counts['gain']}/{counts['old'][2]} 个 z16 旧败。在 {gates['decisions']:,} 次决策中，实际选用事件头或前移 {gates['alternate']} 次。")
    add('## 独立家院复测')
    add('两批各 12 个未参与训练与选模的开局，各含 6 个白天和 6 个夜晚。每个开局分别对 r22、历史 H 和 B。双方牌组按卡牌集合与开发集和已登记的历史家院牌组核对。每行有 72 个配对。'+link('封存清单','sealed.json'))
    tab=['| 参考策略 | 参考胜 / 未决 / 负 | 新头胜 / 未决 / 负 | 保住旧胜 | 旧败转胜 | 两批真胜增量 | 同窗本方频率（次/分） | 95% 真胜率增量 |','|---|---:|---:|---:|---:|---:|---:|---:|']
    for k,v in t['results'].items():
        s=v['all'];c=s['counts'];delta=[v[j]['counts']['new'][0]-v[j]['counts']['old'][0] for j in ('a','b')]
        freq=s['troops']['all']['troops_per_min'] if not k.startswith('plant') else [s['tempo'][j]['common_window_deploys_per_min']['plant'] for j in ('parent','candidate')]
        ci=s['win_delta95'];tab.append(f"| {names[k]} | {fmt(c['old'])} | {fmt(c['new'])} | {c['kept']}/{c['old'][0]} | {c['gain']}/{c['old'][2]} | {delta[0]:+d}、{delta[1]:+d} | {freq[0]:.2f} → {freq[1]:.2f} | {ci[0]*100:.1f} 至 {ci[1]*100:.1f} 个百分点 |")
    add('\n'.join(tab))
    add('僵尸频率只计实发兵种，植物频率计有效部署。每对取两条路线中较短的时长。置信区间按开局成组重采样。'+link('逐场常规结果、频率和延长赛','test.json'))
    ablation=t['results']['history_fixed']['all']
    add(f"六项输入对照使用同一组已冻结权重、相同门槛及其余实时局面特征。将新增的出兵和建墓历史固定为训练开局的等权均值后，72 个配对中有 {ablation['different']} 个整局实发轨迹改变。这个对照仅覆盖本轮主候选。")
    passed=[names[k] for k,r in t['results'].items() if r['stable']]
    add('稳定提升要求保住旧胜，两批的真胜都增加，按开局重采样的增量下界为正，且本方节奏达标。'+('达标的对照为'+'、'.join(passed)+'。' if passed else '本轮各项对照均未同时达到这些条件。')+'候选权重保存在训练目录。')
    tab=['| 对手（各 24 局） | z16 | 上轮单招僵尸 | 新僵尸 | 上轮植物 | 新植物 |','|---|---:|---:|---:|---:|---:|']
    for o in 'rhb':
        cells=[t['results'][k]['all']['per_opponent'][o][arm] for k,arm in [('z16','before'),('single','before'),('z16','after'),('plant_latest','before'),('plant_latest','after')]]
        tab.append('| '+('r22' if o=='r' else o.upper())+' | '+' | '.join(map(fmt,cells))+' |')
    add('\n'.join(tab))
    tab=['| z16 → 新僵尸 | 配对 | 同窗出兵数 | 每分钟出兵 | 同期建墓数 |','|---|---:|---:|---:|---:|']
    terms={'1':'胜','0':'未决','-1':'负'}
    for k,v in t['results']['z16']['by_transition'].items():
        old,new=k.split('/');x,y=v['troops_per_min']
        tab.append(f"| {terms[old]} → {terms[new]} | {v['pairs']} | {v['troops'][0]} → {v['troops'][1]} | {x:.2f} → {y:.2f} | {v['graves'][0]} → {v['graves'][1]} |")
    add('\n'.join(tab))
    for k,r in t['results'].items():
        v=r['all'];tempo=v['tempo'];x,y=[tempo[arm] for arm in ('parent','candidate')]
        exp=v['troops']['all']
        add(f"与{names[k]}对照，平均封顶局长 {x['mean_capped_seconds']:.1f} → {y['mean_capped_seconds']:.1f} 秒。共同观察窗口内，僵尸实际出兵 {exp['troops'][0]} → {exp['troops'][1]}，建墓 {exp['graves'][0]} → {exp['graves'][1]}，植物每分钟部署 {x['common_window_deploys_per_min']['plant']:.2f} → {y['common_window_deploys_per_min']['plant']:.2f}。")
        wins=[row for row in v['rows'] if row['old']==-1 and row['new']==1]
        if wins:
            w=v['troops']['old_loss_to_win']
            rates=[60*sum(row['tempo']['plant'][j]['deploys'] for row in wins)/w['seconds'] for j in (0,1)]
            add(f"其中 {len(wins)} 个旧败转真胜的配对里，僵尸每分钟出兵 {w['troops_per_min'][0]:.2f} → {w['troops_per_min'][1]:.2f}，植物每分钟部署 {rates[0]:.2f} → {rates[1]:.2f}。")
        for v in (-1,1):
            ex=[e for e in t['extensions'] if e['comparison']==k and e['old']==v]
            if ex:add(f"与{names[k]}对照，有 {len(ex)} 个旧{'败' if v<0 else '胜'}转超时。延至终局或 1,200 秒后为 {sum(e['late']==1 for e in ex)} 胜、{sum(e['late']==-1 for e in ex)} 负、{sum(e['timeout'] for e in ex)} 仍超时。")
    add('## 独立胜局覆盖与单招训练')
    cov=a['coverage'];add('先划开训练与验证的开局池，再根据 z16 实际打出的首分钟出兵、建墓时间、墓位和来源选择赢法不同的开局。'+link('实发命令和各开局筛选结果','screen.json'))
    for k,title in [('train','训练'),('val','验证')]:
        d=cov[k];add(f"{title}选入 {d['wins']} 个 z16 胜局和 {d['losses']} 个败局，各来自不同种子。胜局中有 {d['winning_signatures']} 种不同的前六条部署序列，包含卡牌、实际时间、墓源与位置。")
    ds=data['probes'];candidates=sum(len(r['hashes'])-1 for r in ds);retained=sum(len(r['full']) for r in ds)
    checks=[r for k in NAMES[:2] for r in data['rows'][k] if not r['short_distinct']]
    add(f"在 {len(ds)} 个实际决策点先从同一状态短跑 6 秒左右，比较 {candidates} 个备选动作，把其中 {retained} 对纳入终局训练。保留的 {len(checks)} 个短期轨迹相同的对照里，有 {sum(r['full_distinct'] for r in checks)} 个在后续才出现轨迹差异。到位建墓和等一招另做 {len(data['rows']['arrival_live'])} 组配对。"+link('同局面分支与训练目标','rollouts.json'))
    add('网络额外观察实发兵和建墓分别距今多久、15 秒和 60 秒内各有几次。三个决策读出沿用上一轮权重，再拟合配对收益的残差。实际出兵下降单独扣分；建墓只进入状态和统计，靠造成的终局结果获得收益。')
    add(f"僵尸采用 {z['selected']} 候选。验证时除多种赢法与败局外，还从验证池剩余开局按编号取 {len(z['ordinary'])} 个，各跑三个对手。冻结后再训练植物，入选方向为 {p['selected']}。"+link('僵尸选模记录','zombie.json')+' · '+link('植物选模记录','plant.json'))
    tab=['| 僵尸权重 | 验证组 | 配对 | 保住旧胜 | 旧败打赢 | 参考胜 → 候选胜 | 实际出兵/分 |','|---|---|---:|---:|---:|---:|---:|']
    for name,v in z['validation'].items():
        for subset,gr in v.items():
            c=gr['counts'];x,y=gr['troops']['all']['troops_per_min']
            tab.append(f"| {name} | {'多种胜败开局' if subset=='enriched' else '验证池余下抽取'} | {len(gr['rows'])} | {c['kept']}/{c['old'][0]} | {c['gain']}/{c['old'][2]} | {c['old'][0]} → {c['new'][0]} | {x:.2f} → {y:.2f} |")
    add('\n'.join(tab))
    for title,subset in [('上一轮 z16 的旧胜',[r for r in hist if r['z16']==1]),('上一轮单招头新赢的 z16 旧败',[r for r in hist if r['z16']==-1 and r['previous']==1]),('上一轮单招头丢掉的 z16 旧胜',[r for r in hist if r['z16']==1 and r['previous']!=1])]:
        add(f"{title}共 {len(subset)} 个配对，主候选取得 {sum(r['new']==1 for r in subset)} 胜、{sum(r['new']==0 for r in subset)} 未决、{sum(r['new']==-1 for r in subset)} 负。副候选取得 {sum(r['secondary']==1 for r in subset)} 胜、{sum(r['secondary']==0 for r in subset)} 未决、{sum(r['secondary']==-1 for r in subset)} 负。"+link('冻结后的旧局回归','regression.json'))
    dy=t['dynamics'];add(f"新开局自然对局中，{sum(r['changed'] for r in dy)}/72 局与 z16 的整局轨迹不同。切回 z16 共 {sum(r['returns'] for r in dy)} 次，其中 {sum(r['public_returns'] for r in dy)} 次发生在公共事件。前移到位 {sum(r['arrivals'] for r in dy)} 次，选择等待 {sum(r['defer'] for r in dy)} 次。")
    sites=secondary_arrivals(t)
    if sites is not None:
        add(f"副候选到位 {len(sites)} 次，其中立即建墓 {sum(r['place'] for r in sites)} 次，等一招 {sum(not r['place'] for r in sites)} 次。每处均复算六项实时输入与网络打分，并逐条核对该刻实际成功的建墓命令。"+link('副候选到位逐条记录','secondary-arrivals.json'))
    for k,v in a['gates'].items():
        changed=t['results'][k]['all']['different']
        add(f"{'主' if k=='z16' else '副'}候选在 {v['decisions']} 个决策机会中采用事件头或前移 {v['alternate']} 次，涉及 {v['games_active']}/72 局，其中整局实发轨迹与 z16 不同的有 {changed} 局。")
    for side,doc in [('僵尸主候选',z),('僵尸副候选',read(OUT/'contrast.json')),('植物',p)]:
        model=Path(doc['path']);add(side+'权重为 '+link(model.name,'models/'+model.name)+f"，SHA-256 为 `{sha(model)}`。")
    peak=max(read(f)['peak'] for f in OUT.glob('disk-*.json'))
    add(f"共核验 {a['games']} 份原生收据，包括 {a['full']} 场 600 秒常规赛、{a['extended']} 场 1,200 秒上限的延长赛和 {a['short']} 场短分支。相同模型在新旧程序的整局哈希以及原生输入、打分均已复核。受控训练目录文件长度采样峰值 {peak/2**30:.3f} GiB，NTFS 去重后实际占用 {a['storage']/2**30:.3f} GiB。"+link('核验与磁盘记录','audit.json'))
    dest=R/'docs/ai-nn/家院实际出兵与多开局保胜训练_20261119.md'
    dest.write_text('\n\n'.join(lines)+'\n','utf8')
    assert all((dest.parent/s).is_file() for s in re.findall(r'\[[^\]]+\]\(([^)]+)\)',dest.read_text('utf8')))
