"""Complete the frozen-anchor mesh with last round's strongest pooled zombie and tied strongest plant."""
from position_train import OUT, BASE, HOME, read, write, sha, group, report_comparison


def run():
    plan=read(OUT/'plan.json')
    current=read(OUT/'complete.json')
    from pathlib import Path
    z=Path(read(OUT/'zombie-frozen.json')['model']);p=Path(read(OUT/'plant-frozen.json')['model'])
    assert sha(z)==current['zombie'] and sha(p)==current['plant']
    ids=plan['test']
    before=group('home-joint-parent',ids,BASE,BASE)
    comparisons={}
    for side,plant,sp in [('plant',p,None),('zombie',BASE,z)]:
        name='home-'+side+'-b-candidate'
        after=group(name,ids,plant,BASE,sp)
        comparisons[side]=report_comparison('home',side+'-b',side,before,after,plant,BASE,sp,HOME)
    write(OUT/'historical-b.json',comparisons)


if __name__=='__main__':run()

