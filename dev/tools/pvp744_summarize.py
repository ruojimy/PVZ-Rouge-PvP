"""Recompute the performance candidate assessment from completed raw runs."""
import argparse
import json
from pathlib import Path


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('directory');a=p.parse_args()
    root=Path(a.directory).resolve()
    read=lambda name:json.loads((root/name).read_text('utf8'))
    data={name:read(name+'/summary.json') for name in ('tick-ab','wall-ab','view-ab','view-wall','checks-final2')}
    assert all(d['completed'] for d in data.values()),'incomplete run'
    checks=data['checks-final2']['results'];assert all(r['exit_code']==0 and r['passed']==r['checks'] for r in checks)
    assert all(c['equal_state_rng'] for name in ('tick-ab','view-ab') for c in data[name]['comparisons'].values())
    scenes={'ordinary':'普通20','barrage':'高弹幕240','grabber':'抓人草120'}
    arms={'legacy':'旧策略','sliced':'仅8ms预算','adaptive':'预算与新慢放','view':'预算与新慢放及本地复用'}
    def table(rows):
        lines=['| 场景 | 设置 | 呈现循环/秒 | 服务间隔P95/P99 ms | 模拟/墙钟 | 最后倍率 | >100ms工作帧 |',
               '| --- | --- | ---: | ---: | ---: | ---: | ---: |']
        for r in rows:
            t=r['phases']['frame_interval_actual']
            lines.append(f"| {scenes[r['scene']]} | {arms[r['arm']]} | {r['fps']:.2f} | {t['p95']:.2f}/{t['p99']:.2f} | {r['ratio']:.3f} | {r['last_scale']:.3f} | {r['long_frames']['100']:.2f}% |")
        return '\n'.join(lines)
    cache=[]
    for r in data['view-ab']['results']:
        report=read('view-ab/'+r['scene']+'-'+r['arm']+'/report.json')
        old=report['pacing_lab']['counters_before'];new=report['backend_audit']
        cache.append(dict(scene=r['scene'],arm=r['arm'],idle_refresh_ms=r['phases']['refresh_idle']['mean'],
            builds=new.get('local_presentation_builds',0)-old.get('local_presentation_builds',0),
            hits=new.get('local_presentation_hits',0)-old.get('local_presentation_hits',0),
            projections=new['snapshot_projections']-old['snapshot_projections'],
            pure_sim_ms_per_native_tick=r['phases']['authority_sim']['total']/r['native_ticks']))
    cache_table=['| 场景 | 设置 | 无新tick刷新均值 ms | 本地帧构建/复用次数 | 世界投影次数 |',
                 '| --- | --- | ---: | ---: | ---: |']
    for r in cache:cache_table.append(f"| {scenes[r['scene']]} | {arms[r['arm']]} | {r['idle_refresh_ms']:.3f} | {r['builds']}/{r['hits']} | {r['projections']} |")
    profile=read('profile/grabber-adaptive/report.json')['backend_audit']['performance']['function_profile']
    effect=profile['NativeTick::effects_and_draw_plants']['total_ms'];draw=profile['NativeTick::effects::draw_plants']['total_ms']
    result=dict(automated_checks=sum(r['checks'] for r in checks),passed=sum(r['passed'] for r in checks),
        equal_tick_comparisons={name:data[name]['comparisons'] for name in ('tick-ab','view-ab')},
        local_frame_cache=cache,draw_plants_share_of_effects=draw/effect,
        product_acceptance_passed=False,human_input_acceptance='pending',android_candidate_test='no online ADB device')
    (root/'assessment.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),'utf8')
    text=f'''# 性能调度与本地呈现候选验收记录

日期：2026-11-16。已落实第一批可回退的调度、计时和本地呈现复用候选，定向自动检查 {result['passed']}/{result['automated_checks']} 通过。高负载稳定30FPS及低延迟目标仍未达到，T01/T02/T24保持开放。正式发布仍为 PvP74.3 r3；本轮交付独立实验入口。

## 已完成的改动

- Room在完整step结束后检查可选时间预算，并按实际tick增量扣除积压；提前终局也只扣已执行的step。一次step可以超过8ms，尚不支持native tick中途让出。
- App拆分纯Session模拟、Room额外工作和刷新计时，另记有/无新tick的刷新。原有网络冻结、后台编码与队列指标继续保留；父阶段与子阶段不能相加。
- 新慢放策略独立开启，默认0.15非零下限，可配置0至0.65的固定成本保护阈值；持续墙钟压力还需至少3个独立坏帧。开局保护、恢复迟滞及生命周期债务契约保留。
- 本地呈现按已有投影版本复用私有帧，Room元数据和鼠标/触控预览继续按服务循环更新。普通战斗、回放与网络快照保持复制契约；主客网络呈现未启用这个原型。
- 可选权威输入追踪记录适配器进入、Session命令派发开始与结束、席位、序列和逻辑tick，保留最近256条并计淘汰数。命令成功、后续运动物理、远端ACK和显示是不同阶段；未把这些记录当成物理触控延迟。
- 生产内核NativeTick细分setup与effects阶段，函数计时仍须显式开启 `PVP741_PROFILE=1`。本轮没有改250Hz规则、伤害或RNG顺序。

## 同逻辑工作对照

同一PC、两个逻辑核、BelowNormal、串行、SDL dummy完整软件绘制循环；高HP、固定seed与中性输入、原画/像素、关闭自动减绘。每组最终room tick=300，测量均1250 native tick。以下不能外推为物理显示FPS或Android收益。

{table(data['tick-ab']['results'])}

三场景各设置的最终状态与RNG分别一致。低倍率把相同工作摊到更长墙钟时间；呈现机会增加不等于模拟吞吐提高。原始证据：[第一轮对照](tick-ab/summary.json)。

## 固定墙钟的自动策略

每组5秒暖场后测量45秒，函数计时关闭。不同策略推进的逻辑tick不同，因此本表不要求终态哈希一致，也不作为等量工作加速证据。服务P95/P99统计相邻服务迭代；长帧百分比统计本帧工作耗时，二者分母不同。

{table(data['wall-ab']['results']+data['view-wall']['results'])}

旧策略与新慢放的高弹幕稳态基本没有改善；抓人草的呈现有所改善，同时战斗推进更慢。本地复用的自动策略稳态没有进一步改善，因此另设实验入口，主候选入口先不启用复用。均为单轮串行样本，不能作重复试验的稳定收益结论。[自动策略原始结果](wall-ab/summary.json)、[复用候选稳态](view-wall/summary.json)。

## 相同固定倍率的复用对照

以下两组都强制0.20，只切换本地帧复用。用于隔离复用效果，人工入口默认仍为自动倍率。

{table(data['view-ab']['results'])}

{chr(10).join(cache_table)}

三场景各组state/RNG一致。已有typed世界投影缓存继续复用；新增缓存减少的是本地快照副本构建，不宣称消除了全部Room刷新或JSON转换。[复用原始结果](view-ab/summary.json)。

## 定向回归与诊断

检查范围为调度/快照5项×两种配置、既有性能6项、机制17项、真实Application输入/网络队列/合作复活/生命周期11项×两种配置，共55次断言组执行。包括同tick多次跳跃边沿、终局、1.7秒债务守恒、后台前积压保留与后台时间排除。前一轮两个夹具假设已修正：未发布的测试血量不直接期待出现在视图中；分片后台恢复允许消化后台前的积压。[最终回归](checks-final2/summary.json)，初始失败证据留在checks-final。

单独的插桩抓人草样本中，effects阶段{effect:.2f}ms，draw_plants占{draw:.2f}ms（{draw/effect*100:.1f}%）；append_heroes、静态注册和hero effects很小。下一步先拆draw_plants的状态副作用与纯配方构建，再谈减少中间绘制；不能直接跳过全部draw。[函数计时](profile/grabber-adaptive/report.json)。

完整产品门禁沿用r3的2366项历史结果：2324 PASS、30 FAIL、12 ERROR，15精确豁免、27未豁免；本轮没有把55项定向检查替代它。混合120、独立芦笋战机、真实慢客机/公网、Android候选、物理输入采集到呈现、用户手感和长时内存仍待覆盖。当前ADB列表为空，尚无新Android实机结果。

## 独立体验入口与源码

根目录“体验性能候选.cmd”开启抓人草120、新慢放与8ms预算；“体验性能对照.cmd”开启旧策略；“体验刷新复用.cmd”在候选上另外开启本地帧复用。均为自动倍率、180秒独立诊断，双方提供100000资源，冷却与合法性仍生效；测试数据自动保存到新的 `test_results/pvp744/manual-*`。正式启动器与独立存档保持r3，本轮没有发布新正式EXE/APK。

冻结测试EXE、DLL、源码补丁归档和SHA清单见 [candidate目录](candidate/manifest.json)。回退文件位于根目录backup-latest/performance-before.zip；源码补丁归档需要现有工程及其冻结生产阶段，不是完整独立源码发布包。

backup-latest内的PC包、源码包和APK已更新为本轮前的r3并逐项核对SHA。包含旧目录清理的命令被自动审批以“blocked by policy”拒绝，没有给出更具体原因；旧t03-source目录因此保留，最近一组备份的清理约定尚未完全满足。

复跑入口：`tools/pvp744_verify_scheduler.py`、`tools/pvp744_scheduler_lab.py`、`tools/pvp744_summarize.py`。新调度/慢放/复用均为环境变量开关，默认关闭；具体运行开关和EXE SHA逐组记录在process.json，生效配置记在报告scheduling.configuration中。
'''
    (root/'assessment.md').write_text(text,'utf8')
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
