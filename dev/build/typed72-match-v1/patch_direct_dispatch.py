"""The chili dispatch overrides (enemy_scan/player_hit/hit_zombies) and the content draw hooks of the
probe chain record a fixture label (entity_index over the fixture births list) before or instead of the
real work. In a composition without fixture containers that lookup throws; the match calls the typed
systems directly and drops draw recording, as the source draws without changing state."""
from pathlib import Path
p=Path(__file__).with_name('match_probe.cpp');t=p.read_text(encoding='utf8')
if 'direct chili dispatch' in t:raise SystemExit('already patched')
a='    J fixture_retention()const{'
assert t.count(a)==1
t=t.replace(a,'''    // direct chili dispatch: the typed ChiliEffects, without the fixture's dispatch_calls label.
    void enemy_scan(const EntityRef& e,FlameBox b,double s)override{chili.enemy_scan(e,b,s);}
    void player_hit(const EntityRef& e,FlameBox b,double s)override{chili.player_hit(e,b,s);}
    void hit_zombies(const EntityRef& e,FlameBox b,double s,bool charmed,const std::optional<FireRows>& r)override{chili.hit_zombies(e,b,s,charmed,r);}
    void draw_dart(const EntityRef&,Point,double)override{}
    void draw_mortar_projectile(const EntityRef&,double,const std::optional<Point>&,std::string_view)override{}
'''+a)
b='{"calls",calls.size()},{"render_log",render_log.size()},{"states",states.size()}};'
assert t.count(b)==1
t=t.replace(b,'{"calls",calls.size()},{"render_log",render_log.size()},{"states",states.size()},{"dispatch_calls",dispatch_calls.size()},{"phase_draws",phase_draws.size()},{"phase_events",phase_events.size()}};')
c='if(release_fixtures){units.clear();births.clear();render_log=J::array();calls=J::array();}'
assert t.count(c)==1
t=t.replace(c,'if(release_fixtures){units.clear();births.clear();render_log=J::array();calls=J::array();dispatch_calls=J::array();phase_draws=J::array();phase_events=J::array();}')
p.write_text(t,encoding='utf8');print('ok')
