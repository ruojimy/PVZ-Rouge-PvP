"""__pvz_sb_apply_blover_zombie_wind reads g['伤害实体'] (K_DAMAGE_ENTITIES) for the projectiles it blows.
WindEnvironment::damage_entities stayed the fixture's empty list in the match, so clover-zombie wind
never moved plant projectiles (coop_day10 t=7134)."""
from pathlib import Path
p=Path(__file__).with_name('match_probe.cpp');t=p.read_text(encoding='utf8')
a='rules.damaging=g.at("伤害实体").get<std::vector<std::string>>();'
assert t.count(a)==1
if 'wind_environment.damage_entities=' in t:raise SystemExit('already patched')
t=t.replace(a,a+'battle.wind_environment.damage_entities=std::make_shared<std::vector<std::string>>(rules.damaging);')
p.write_text(t,encoding='utf8');print('ok')
