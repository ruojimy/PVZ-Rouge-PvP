"""Publish local evidence for a finished study, without promoting its weights."""
import datetime
import hashlib
import json
import shutil
from pathlib import Path

R=Path(__file__).resolve().parents[2]
B=R/'test_results/ai-nn-dagger-20261117'
read=lambda p:json.loads(p.read_text('utf-8'))
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
link=lambda label,p:f'[{label}]({p.as_posix()})'


def main():
    a=read(B/'analysis.json');run=read(B/'run.json');plan=read(B/'plan.json')
    assert run['completed'] and a['completed_games']==288
    assert not a['eligible_for_dual_nn_diagnostic'], 'Passing candidate needs its interaction diagnostic before publication'
    assert not (B/'completion.json').exists()
    neutral=read(B/'residual-neutral-comparison.json')
    assert neutral['passed']
    assert all(sha(Path(p))==h for p,h in run['frozen'].items())
    assert all(sha(R/p)==h for p,h in plan['source_sha256'].items())
    assert sha(R/'PVZ_rougePvP_native/PvZPvPNative.exe')==plan['release_sha256']
    assert sha(R/'dist/PvZ-PvP-Native-20261117-pvp744-r3/PvZPvPNative.exe')==plan['release_sha256']
    t0=read(B/'training-0/report.json');t1=read(B/'training-1/report.json')
    epochs=sum(len(c['history']) for t in [t0,t1] for c in t['candidates'])
    model=B/'training-1/selected/model.json';m=read(model)
    params=sum(len(row) for k in ['unit','body','heads'] for row in m[k]['weight'])+sum(len(m[k]['bias']) for k in ['unit','body','heads'])
    source_files={R/p for p in plan['source_sha256']}
    source_files|={Path(p) for p in run['frozen'] if not p.endswith('.exe')}
    source_files|={R/'build/ai-nn'/p for p in ['train.py','eval.py','compare.py','fit_imitation.py','run-research.ps1','dagger_analysis.py','dagger_report.py','check_features_v2.py','residual_seed.py','dagger_neutral_check.py']}
    snap=B/'source-snapshot';manifest={}
    for p in sorted(source_files):
        rel=p.relative_to(R);target=snap/rel;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,target)
        manifest[rel.as_posix()]=sha(target)
    (B/'source-snapshot.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),'utf-8')
    timing=[read(p) for p in B.glob('*/timing.json')]
    aggregate=sum(x['game_seconds'] for x in timing)/sum(x['wall_seconds'] for x in timing)
    forward=[read(B/f'forward-stage{i}/report.json') for i in [0,1]]
    assert all(v['passed'] for v in forward)
    receipt=dict(completed_at=datetime.datetime.now().astimezone().isoformat(),game_revision=plan['game_revision'],
        study_completed=True,promoted=False,reason='Failed predeclared outcome and/or activity gates',
        games=288,neutral_equivalence_games=2,launcher_smoke_games=2,supervised_runs=3,supervised_epochs=epochs,continuation_smoke_epochs=2,
        training_method='r22 imitation with one student-state dataset aggregation iteration; no reinforcement learning',
        model=str(model),model_sha256=sha(model),parameters=params,feature_version=2,
        forward_samples=sum(v['samples'] for v in forward),forward_class_mismatches=sum(v['class_mismatches'] for v in forward),
        source_binary_data_hashes_verified=True,formal_launcher_sha256=plan['release_sha256'],
        source_snapshot_sha256=sha(B/'source-snapshot.json'),four_job_aggregate_speed=aggregate,
        activity_flag_count=a['activity_flag_count'],outcome_gate_passed=a['outcome_gate_passed'])
    (B/'completion.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),'utf-8')
    text=['# PvP74.4 r3：状态摘要与学生轨迹补训',
        '',f'本轮完成 3 组、{epochs} epoch 监督训练与 288 场按 600 秒上限运行的对战评测，超时单列。新模型没有通过预先固定的替换门槛，未替换研究实战默认权重；正式游戏继续使用 r22。实验于 2026-11-17 启动，完成时间见收据。',
        '',f'基准是最新正式 PvP74.4 r3，生产源、编译程序、数据及模型均有哈希收据；正式启动器目标与发布 EXE 仍为 `{plan["release_sha256"]}`。本轮没有改生产战斗规则或用户存档。',
        '',link('完整收据',B/'completion.json')+'；'+link('训练与测试计划',B/'plan.json')+'；'+link('冻结执行记录',B/'run.json')+'；'+link('源码快照清单',B/'source-snapshot.json')+'。',
        '', '## 训练方法与架构',
        '', '仍是 r22 行为克隆，增加一轮学生轨迹回收：先微调两个已有起点，按验证损失选出一个；让它分别控制植物、僵尸对 r22 共打 24 场训练局；在学生实际走到的状态上重新询问当前 r22，再补训。没有胜负奖励反传，也没有双方自对弈强化学习。',
        '',f'保留单位编码 8、隐藏层 64、三个启用的战略输出头。全局特征从 20 增至 28，新增经济单位数、三类火力数量、两档近身压力及双方军力价值；参数从 5,659 增至 {params:,}。新增的是输入状态摘要，不是 r22 输出。移动、出牌位置、卡牌顺序及其余控制仍由 r22 负责。',
        '', '训练损失只统计启用的经济目标、植物模式、墓碑目标三个头；模式损失乘 2，真实攻守切换样本额外乘 3。旧教师轨迹权重 0.5、学生状态 2、新轨迹 1、增强行 0.25。旧轨迹按当前 r22 重标，但仍保留旧模拟产生的状态分布，不能混称最新游戏实战数据。',
        '',f'72 个最新游戏导出开局，训练／验证／测试各 24，覆盖 12 地图×昼夜，种子组分离。历史教师轨迹 168 场、历史学生轨迹 7 场作为补充；第一阶段有效训练 {t0["train_rows"]:,} 行，第二阶段 {t1["train_rows"]:,} 行，分别剔除 {t0["removed_overlap"]}／{t1["removed_overlap"]} 行与验证特征完全重合的数据。验证样本 {t1["validation_rows"]:,} 行。',
        '', '## 实战结果',
        '', '每行的网络只控制所列阵营，对手固定 r22。每个结果均包含 24 局，超时上限为游戏内 600 秒。平均时长包含超时，不能用更快输掉来冒充节奏提升。',
        '', '| 数据组／控制方 | 植物胜 | 僵尸胜 | 超时 | 含超时平均秒数 |', '| --- | ---: | ---: | ---: | ---: |']
    labels={'r22':'双方 r22','old-plant':'旧权重植物','new-plant':'新权重植物','old-zombie':'旧权重僵尸','new-zombie':'新权重僵尸'}
    for part,title in [('validation','验证'),('test','封存测试')]:
        for arm,label in labels.items():
            v=a['outcomes'][part+'-'+arm]
            text.append(f'| {title}／{label} | {v["plant_wins"]} | {v["zombie_wins"]} | {v["timeouts"]} | {v["capped_mean_seconds"]:.1f} |')
    text += ['', '验证集僵尸侧相对旧权重的胜局保持 6/24，超时 10→7；但仍少于 r22 的 7 胜，且相对 r22 新增了超时开局。植物侧与旧权重同为 11 胜、8 超时，但旧权重能结束的两个开局在新模型下超时。局部改善没有抵消未通过的门槛。',
             '', '门槛同时要求：相对 r22 及旧权重都不减少胜局、不增加超时总数、不新增超时开局，含超时平均时长增长不超过 5%；另外审查共同时间窗口里的成功部署、资源与高资源空闲。该门槛是保守筛选，不是显著性或泛化证明。',
             '',f'本轮有效行动审查出现 {a["activity_flag_count"]} 个“阵营／参照／开局”告警；同一开局对两个参照可能重复计数。资源与空闲按约 1.5 秒的重规划采样，告警不等于已证明当时存在合法出牌。全部逐局数据见 '+link('analysis.json',B/'analysis.json')+'，胜负及节奏门槛见 '+link('strength.json',B/'strength.json')+'。',
             '', '植物验证的小镇 049 局：共同前 560.2 秒双方各成功部署 103 次，新模型仍由胜转超时；因此本轮新增超时并非都由少操作造成。木船 061 局共同 600 秒，高资源且至少 30 秒未部署的采样累计约 185.1→226.5 秒；r22 本身也有长空闲，需保留地形和合法放置限制的解释。',
             '', '四个植物验证失败／告警局的反事实重标只用于诊断，未进入本轮训练或选型；它们仍存在漏切进攻及过早进攻。见 '+link('诊断数据',B/'postmortem-validation.json')+'。',
             '', '## 拟合与实现核验',
             '', '以下是封存测试 r22 轨迹上的标签准确率，仅统计启用的三个头；经济标签仍存在下述上限截断，不能将该准确率等同完整复现 r22。',
             '', '| 权重 | 经济目标 | 植物模式 | 墓碑目标 | 攻守切换准确率 |', '| --- | ---: | ---: | ---: | ---: |']
    for key,label in [('warm-old','旧默认'),('warm-compact','上轮小网络'),('stage-0','第一阶段'),('stage-1','最终补训')]:
        s=a['heldout_teacher_scores'][key]
        text.append(f'| {label} | '+' | '.join(f'{v:.2%}' for v in s['accuracy'])+f' | {s["transition_accuracy"]:.2%}（{s["transition_count"]} 个切换样本） |')
    text += ['',f'两阶段模型的 C++／PyTorch 共核对 {receipt["forward_samples"]} 条状态、{sum(v["classes_checked"] for v in forward)} 个分类输出，分类不一致 0，最大 logit 误差 {max(v["max_absolute_logit_error"] for v in forward):.3g}；每阶段 5 个错误元数据负例均拒绝。新增特征独立核算 336 条状态，旧 20 项特征和单位数组未变、8 项新摘要误差 0。另做了两次 2 秒入口冒烟、两个 1 epoch 续训冒烟，它们不计入 288 场正式对战评测或 95 个正式训练 epoch。',
             '',f'采用 4 路无窗口全速逻辑，全部正式对局合计吞吐约 {aggregate:.1f} 倍实时；这是四路合计吞吐。未增大逻辑步长，仍保留有状态副作用的 draw 回调，不能直接删掉所有绘制路径。',
             '', '## 架构结论与续训入口',
             '', '当前证据不支持继续盲目加宽网络。本轮同时改了输入摘要、采样权重与数据回收，未做独立消融，不能把收益归因于其中单项。优先需要修正输出与时序决策结构：经济目标真实可能为 11，但现有绝对分类只能输出至 10；模式总体准确率很高时，少数攻守切换仍容易错。下一轮应先补齐目标表示，并单独采样、评估攻守切换，再考虑状态相关残差与奖励训练。',
             '', '当前教师轨迹中经济目标大于 10 的原始规划条数：`'+json.dumps(a['teacher_econ_goal_over_10_plan_counts'],ensure_ascii=False)+'`。这是尚未解决的表示缺口，未证实它是本轮新增超时的主因；已有“中性残差保留目标 11”契约不代表绝对分类器已经支持 11。',
             '', '这次是已知地图的新种子测试，每侧只有 24 局，不能宣称全地图泛化或显著增强。测试模型在读取测试战果前已冻结，测试后没有改动本轮权重。288 场均无崩溃或 AI 异常，但强度／节奏门槛未通过。',
             '',link('新训练模型',model)+'；'+link('可继续训练的 checkpoint',model.with_name('selected.pt'))+'；'+link('研究入口',R/'build/ai-nn/run-research.ps1')+'。',
             '', '另外保留本轮学到的编码层，将输出头初始化为对 r22 的零修正，生成 '+link('可训练残差起点',B/'residual-neutral/model.json')+'。64 条状态的合成梯度探针通过后已恢复中性权重；两场当前游戏回归（000、010）排除文件头及规划器名称标签后，全部规划与结果字段等于 r22，战斗日志逐字节一致，包含真实经济目标 11。初版比对器把 r22／nn 标签差异误计为失败，原始日志保留；修正只排除该标签，未重跑或改写战斗数据。该起点是 r22 等价策略，没有奖励训练、没有增强结论，也不替换默认权重。其 `residual-seed.pt` 使用独立参数键，不能交给绝对标签训练器。详见 '+link('等价回归收据',B/'residual-neutral-comparison.json')+'。',
             '', '研究入口默认 `-Build pvp744`；Play／Evaluate 保留当前游戏上的旧权重迁移基线，Train 默认从本轮新 checkpoint 权重继续监督训练。旧权重是输入映射后在新游戏上实测的迁移初始化，不能称为 r4 与 r3 战斗源码等价。`-Build r4`、`-Build legacy` 保留历史环境，`-Seat both` 才是双方网络。',
             '', '```powershell', r'.\build\ai-nn\run-research.ps1 -Mode Train -Output test_results/ai-nn-next-imitation', '```',
             '', '续训输出必须使用新目录。该命令不自动晋级；本轮测试开局已经观察过，后续只能用于回归，新选型需要另建封存开局。', '']
    target=R/'docs/ai-nn/PvP744状态摘要与学生轨迹补训_20261117.md'
    assert not target.exists()
    target.write_text('\n'.join(text),'utf-8')
    print(json.dumps(receipt,ensure_ascii=False))


if __name__=='__main__':main()
