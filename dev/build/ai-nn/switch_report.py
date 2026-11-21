"""Summarize a completed and verified home continuation study."""
from collections import Counter
import gzip,json
from pathlib import Path
from switch_study import OUT,R,read,sha,size

NAME={1:'胜',0:'超时',-1:'负'}
def load(key):
    with gzip.open(OUT/'games'/(key+'.jsonl.gz'),'rt',encoding='utf8') as f:
        f.readline();return json.loads(f.readline())
def report():
    audit=read(OUT/'final-audit.json');test=read(OUT/'test.json');reg=read(OUT/'regression.json')['rows']
    review=read(OUT/'review.json')['rows'];front=read(OUT/'front.json');walk=read(OUT/'walk.json')
    z=read(OUT/'final-zombie.json');plant=read(OUT/'final-plant.json');disk=read(OUT/'disk.json')
    split=read(OUT/'splits.json')
    doc=R/'docs/ai-nn/家院首次分歧与前移建墓训练_20261118.md'
    L=[];add=L.append
    base='../../test_results/ai-nn-home-options-20261118/switch/'
    def ref(title,file):return f'[{title}]({base}{file})'
    def wdl(rows,key):return ' / '.join(str(sum(r[key]==n for r in rows)) for n in (1,0,-1))
    add('# 家院首次分歧与前移建墓训练')
    add('## 陌生开局的真胜与回退')
    add(f"正式版本为 {audit['official']}。两批各 12 个家院开局，每批 6 昼、6 夜，各自对 r22、历史 H、历史 B。每个阵营或权重对照共 72 个配对。24 套植物牌组与 24 套僵尸牌组分别互异，并排除了此前查到的 {split['excluded'][0]} 套植物牌组、{split['excluded'][1]} 套僵尸牌组和此次开发牌组。双方共用开局、牌组和原生随机初态。"+ref('开局与分组','splits.json'))
    table=['| 对照 | 旧胜 / 超时 / 负 | 新胜 / 超时 / 负 | 保住旧胜 | 旧败转真胜 | 旧败转超时 | 两批真胜增量 | 真胜率差的 95% 区间 |',
           '|---|---:|---:|---:|---:|---:|---:|---:|']
    names={'z16':'保胜候选对 z16','active':'主动换招候选对 z16','previous_event':'保胜候选对上轮事件头','plant':'新植物对 plant-1p'}
    for k in ('z16','active','previous_event','plant'):
        if k not in test['results']:continue
        r=test['results'][k];rows=r['all']['rows'];assert r['ordinary_draws']==[0,0]
        kept=sum(x['old']==x['new']==1 for x in rows);old=sum(x['old']==1 for x in rows)
        gains=sum(x['old']==-1 and x['new']==1 for x in rows);timeouts=sum(x['old']==-1 and x['new']==0 for x in rows)
        ab=[sum(int(x['new']==1)-int(x['old']==1) for x in r[j]['rows']) for j in ('a','b')]
        lo,hi=r['all']['true_win_rate_delta95']
        table.append(f"| {names[k]} | {wdl(rows,'old')} | {wdl(rows,'new')} | {kept}/{old} | {gains} | {timeouts} | {ab[0]:+d}、{ab[1]:+d} | {100*lo:.1f} 至 {100*hi:.1f} 个百分点 |")
    add('\n'.join(table))
    t=['| 对手（每格 24 局） | z16 | 上轮事件头 | 保胜候选 | 主动换招候选 | plant-1p | 新植物 |','|---|---:|---:|---:|---:|---:|---:|']
    for opponent in 'rhb':
        rr=test['results']
        def col(k,side):
            return ' / '.join(map(str,rr[k]['all']['per_opponent'][opponent][side])) if k in rr else '同保胜候选'
        cols=[col('z16','before'),col('previous_event','before'),col('z16','after'),col('active','after'),col('plant','before'),col('plant','after')]
        t.append('| '+('r22' if opponent=='r' else opponent.upper())+' | '+' | '.join(cols)+' |')
    add('各格依次为胜、超时、负，前三个僵尸模型和主动换招候选按僵尸视角，植物两列按植物视角。')
    add('\n'.join(t))
    add('区间以开局为抽样单位，同一开局的三个对手一起重采样。常规时限为 600 游戏秒。以下按相同观察窗口统计每分钟原生成功部署次数。'+ref('盲测逐局结果和节奏','test.json'))
    for k in ('z16','active','plant'):
        if k not in test['results']:continue
        r=test['results'][k];tp=r['all']['tempo'];a,b=[tp[j] for j in ('parent','candidate')]
        fmt=lambda team:f"{a['common_window_deploys_per_min'][team]:.2f} → {b['common_window_deploys_per_min'][team]:.2f}"
        ex=[v for v in test['extensions'] if v['comparison']==k];side='plant' if k=='plant' else 'zombie'
        counts=Counter('win' if v['winner']==side else 'timeout' if v['timeout'] else 'loss' for v in ex)
        detail=f"败转超时 {len(ex)} 局，延长后 {counts['win']} 胜、{counts['loss']} 负、{counts['timeout']} 仍超时。" if ex else "本组没有从旧败变为超时的配对。"
        add(f"{names[k]}的共同窗口内，每分钟部署次数为植物 {fmt('plant')}、僵尸 {fmt('zombie')}。平均封顶局长 {a['mean_capped_seconds']:.1f} → {b['mean_capped_seconds']:.1f} 秒。"+detail)
    hz=read(OUT/'blind-horizons.json')['rows']
    for label in ('active','plant','active_previous_event'):
        subset=[e for e in hz if e['comparison']==label]
        if not subset:continue
        name=names.get(label,'主动换招候选对上轮事件头')
        for old,opening in [(1,'旧胜'),(-1,'旧败')]:
            group=[e for e in subset if e['old']==old]
            if group:add(f"{name}，{opening}转超时共 {len(group)} 局，延长后 {sum(e['late']==1 for e in group)} 胜、{sum(e['late']==-1 for e in group)} 负、{sum(e['timeout'] for e in group)} 仍超时。"+ref('延长赛逐局收据','blind-horizons.json'))
    add('## 原来丢掉的 11 个旧胜局')
    add('按 30 Hz 逻辑帧比较僵尸实发命令的完整有序参数，包括移动、起跳、部署、来源、朝向和旗帜。两条自然路线都复现了原始整局日志哈希。分歧帧前的战场快照、原生 RNG 和此前日志摘要相同，另从 z16 控制器的内部状态当场交棒给上轮事件头。下表按僵尸视角计分。'+ref('首次分歧的全部命令与前缀哈希','review.json'))
    lookup={(r['id'],r['opponent']):r for r in reg}
    data=z['regression_training'].get(z['active_tag']) or read(OUT/'zombie.json')['regression_training']['responsive']
    active_hist={(r['id'],r['opponent']):r['new'] for r in data['rows']}
    t=['| 旧开局 | 对手 | 首个分歧 | z16 / 原事件头 / 当场换头 | 本轮保胜 / 主动换招 |','|---|---|---|---|---|']
    for r in review:
        x,y=r['commands'][:2];actions=[[q for q in cs if q['kind']=='deploy'] for cs in (x,y)]
        if all(actions):
            a,b=actions[0][0],actions[1][0];reason=f"同一墓碑的横坐标 {a['x']} → {b['x']}，朝向 {a['facing']} → {b['facing']}"
        elif actions[1]:
            b=actions[1][0];reason=f"新头从 {b.get('grave','')} 部署{b['card'].split(':')[-1]}，z16 当帧未部署"
        else:reason='同方向移动，z16 起跳，事件头平移'
        v=lookup[r['id'],r['opponent']]
        t.append(f"| {r['id']} | {'r22' if r['opponent']=='r' else r['opponent'].upper()} | {r['tick']} 帧，{r['seconds']:.3f} 秒。{reason} | {NAME[r['old']]} / {NAME[r['event']]} / {NAME[r['switched']]} | {NAME[v['new']]} / {NAME[active_hist[r['id'],r['opponent']]]} |")
    add('\n'.join(t))
    add('11 个配对来自 4 个开局。首次分歧后两条路线各自由对应策略继续，表中胜负衡量从该时刻起的整条路线。用此前 8 个 z16 败、事件头胜的配对作反向训练，另在 8 个开发家院开局对固定 plant-1p、历史 O 和 r22 取样。'+ref('反向案例','positive.json')+' · '+ref('原配对回归','regression.json'))
    add('## 前移、到位与建墓')
    rows=front['rows'];built=sum(any(e['phase']=='grave' for e in r['phases'][1]) for r in rows)
    add(f"上轮 643 次记录到移动候选，620 次至少有一个候选确实朝敌方超过 1.25 格。按对手、时刻和距离取了 {len(rows)} 个局面，覆盖 {len(set(r['id'] for r in rows))} 个开局。每组比较原打法、先走到目标再尝试建墓、在同一坐标直接建墓。三路共享完整前缀，按真实胜负训练，前移距离、建墓次数不计奖励。先走的分支实际建出并观察到 {built} 座新墓，直接建的分支建成 47 座。"+ref('47 组三路对照','front.json'))
    for r in walk['rows']:
        if r['id']=='027' and r['results'][:3]==[0,1,0]:
            tr=load(r['keys'][3]);ev=r['arrival'];card,x,y=r['target'][1],*r['target'][3:]
            nxt=next(c for c in tr['accepted_commands'] if c['kind']=='deploy' and c['accepted'] and c['time']>=ev['t'] and (c['card'],c['x'],c['y'])==(card,x,y))
            add(f"开局 027 对历史 H，第 {r['t']:.1f} 秒出现前移目标。僵尸实走 {ev['move_tiles']:.2f} 格，在 {ev['t']:.1f} 秒建墓，取得真胜；原打法和直接建墓均超时。跳过到位时的建墓后，网络在 {nxt['time']:.2f} 秒自行选回同一坐标，又取得真胜。".replace('；','。'))
    add('开局 020 对 r22，先前移的一路把败局打成真胜，十秒动作窗口内没有建成墓。开局 017 对 r22 和 019 对 B，到位立即建墓均败，跳过这次建墓均胜。031 对 B 则是立即建胜、跳过败。33 个实际到位建成的局面均做了跳过当次建墓的配对，另验了 1 个未到位的轨迹完全等价。'+ref('到位建或延迟的逐局结果','walk.json'))
    add('## 训练与策略选择')
    add('正式模拟以 30 Hz 无头推进，控制器以 15 Hz 观察。固定植物先练僵尸，保留建墓、失墓、冷却结束和资源够用的事件入口。网络可保留 z16、换到事件策略、或尝试前移。行进中的新事件可让网络续走或改变主意，到位判定还可推迟当次建墓。僵尸兵种、来源墓、落点和旗帜继续由已有评分头选择。实际价格、冷却、合法性和移动上限由原生规则及动作执行层处理。')
    h=read(OUT/'zombie.json')
    add(f"第一轮用回到实际换招点的同局面对照复训。换招读出使用 {h['gate']['unique']} 条去重状态和回报，来自 {h['gate']['openings']} 个开局。低门槛在验证中 24 局都换，高门槛 24 局都保留 z16。进一步把九项开局手牌属性和当前前移提案的位置、风险、费用接入径向基价值读出，共 {z['centers']} 个训练中心。它按已观察的续局差值评分。权重和特征均不含开局编号或卡名规则。"+ref('训练门槛与回报','zombie.json')+' · '+ref('上下文模型选择','final-zombie.json'))
    for label,path in [('保胜',Path(z['path'])),('主动换招',Path(z['active'])),('植物',Path(plant['path']))]:
        add(f"{label}权重为 {ref(path.name,str(path.relative_to(OUT)).replace(chr(92),'/'))}，SHA-256 前 16 位为 `{sha(path)[:16]}`。")
    add('两个僵尸候选均在盲测前冻结。植物再对冻结的僵尸候选和 r22 训练，按独立验证选择空间权重扰动；随后双方分别对 r22、历史 H 和 B 换一侧复测。'.replace('；','。')+ref('植物选择','final-plant.json')+' · '+ref('固定植物同局部署差异','plant-styles.json'))
    for k in ('z16','active'):
        ds=[d for d in test['decisions'] if d['comparison']==k]
        if not ds:continue
        silent=[d for d in ds if d['legacy_triggers']==0]
        arrived=sum(d['arrival_choices'] for d in ds);deferred=sum(d['arrival_deferred'] for d in ds)
        detail=f"共 {arrived} 次到位建墓决策，推迟 {deferred} 次。" if arrived else ""
        add(f"{names[k]}，72 个盲测配对中有 {sum(d['active_transfer']!=0 for d in ds)} 局交棒后改变了实际轨迹，主动前移 {sum(d['new_trips']+(d['choice']==2) for d in ds)} 次。"+detail+f"旧路线从未触发的 {len(silent)} 局中，僵尸胜局 {sum(d['old']==1 for d in silent)} → {sum(d['new']==1 for d in silent)}。")
    add('主动换招的 7 个败转胜来自新开局 017、026、033，11 个旧胜回退来自 021、024、026、029。相同的 026 对 r22 由败变胜，对 H 和 B 却从常规时限内取胜变为约 640 秒才获胜。交给事件头的决定持续到终局，其间仍可在公共事件上改变出兵或前移。由此得到的是整条续打路线的收益。')
    sealed=read(OUT/'sealed-routes.json')
    rr=sealed['rows']
    exact=sum(r['travel']==1 and r['ordinary']!=1 for r in rr)
    adverse=sum(r['ordinary']==1 and r['travel']!=1 for r in rr)
    add(f"预先按对手取最多 2 个不同盲测开局，取最接近 90 秒的主动前移事件。共找到 {sealed['eligible']} 个候选事件、复演 {len(rr)} 个同局面配对。保留前移和当次改由常规事件头选择的整局轨迹有 {sum(r['distinct'] for r in rr)} 对不同。前移独胜 {exact} 局，常规选择独胜 {adverse} 局。"+ref('盲测主动前移的续局核验','sealed-routes.json'))
    status='、'.join(names[k] for k in ('z16','active','plant') if k in test['results'] and test['results'][k]['stable'])
    add('晋级要求包括保住旧胜、两批真胜都增加、各对手净分不降、按开局重采样的真胜率增量下界为正，以及节奏检查通过。'+('通过的对照为'+status+'。' if status else '本轮三个候选均未达到这组条件。')+'正式游戏仍运行 r22，两个僵尸头和植物权重均可在研究程序独立复测。')
    a=audit['limits'];usage=size(OUT)
    add(f"共核验 {a.get('600',0)} 场常规时限运行、{a.get('1200',0)} 场延长运行，以及 {a.get('1',0)} 次 1 秒属性采集。延长运行逐项核对 600 秒内的活动、命令、空间动作和策略记录。并发最多 6 场。清除本轮可重建目标文件 {read(OUT/'disk-cleanup.json')['bytes']/2**20:.1f} MiB。本轮目录 {usage/2**20:.1f} MiB，本轮及前序受控训练目录合计 {disk['current']/2**30:.3f} GiB，按文件长度采样峰值 {disk['peak']/2**30:.3f} GiB。结束时逐文件读取 NTFS 分配量并按文件身份去重，实占 {read(OUT/'final-allocation.json')['after_cleanup']/2**30:.3f} GiB，上限 4 GiB。正式启动目标另核对了 SHA-256。"+ref('完整审计','final-audit.json')+' · '+ref('磁盘记录','disk.json'))
    doc.write_text('\n\n'.join(L)+'\n','utf8');return doc

if __name__=='__main__':print(report())
