"""NativeBattle._petrified_torch_reward (native_battle.py:439-453): each conversion pays the
zombie team PETRIFIED_TORCH_REWARD through battle.resource(..., "petrified_torch"); zombie-side
resources are collected at once (simulation.resource). The typed TorchRules keeps the brain cap
and sleep; the match previously used the fixture stub that only recorded the call."""
from pathlib import Path
p=Path(__file__).with_name('match_probe.cpp');t=p.read_text(encoding='utf8')
if 'petrified_resource' in t:raise SystemExit('already patched')
a='    void request_ladder(const ZombieRef& unit)override{director.request_ladder(unit);}\n'
assert t.count(a)==1
t=t.replace(a,a+'    void petrified_resource(double amount,Point point)override{resources.create(Seat::zombie,amount,point,"petrified_torch");}\n')
p.write_text(t,encoding='utf8');print('ok')
