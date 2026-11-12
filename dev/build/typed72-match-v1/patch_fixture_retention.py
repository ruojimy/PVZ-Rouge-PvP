"""Report the size of every fixture container of the probe chain at the end of a match. Containers that
hold unit/plant/entity references would extend lifetimes beyond a production composition; if all stay
empty, the probe composition is lifetime-equivalent to a production one on these scenarios."""
from pathlib import Path
p=Path(__file__).with_name('match_probe.cpp');t=p.read_text(encoding='utf8')
if 'fixture_retention' in t:raise SystemExit('already patched')
a='    static void scripted_result_fields(J& row,const RoomResult& r){'
assert t.count(a)==1
t=t.replace(a,'''    J fixture_retention()const{
        return {{"units",units.size()},{"ids",ids.size()},{"all_plants",all_plants.size()},{"held",held.size()},{"births",births.size()},
                {"held_hits",held_hits.size()},{"flights",flights.size()},{"chili_keys",chili_keys.size()},{"sources",sources.size()},
                {"positions",positions.size()},{"held_proxy_sources",held_proxy_sources.size()},{"flight_records",flight_records.size()},
                {"calls",calls.size()},{"render_log",render_log.size()},{"states",states.size()}};
    }
'''+a)
b='{"unsupported_operations",match.unsupported},'
assert t.count(b)==1
t=t.replace(b,b+'{"fixture_retention",match.fixture_retention()},')
p.write_text(t,encoding='utf8');print('ok')
