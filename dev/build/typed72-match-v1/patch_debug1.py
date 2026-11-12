from pathlib import Path
root=Path(r'C:\Users\xiech\Downloads\PVZ_rougePvP_native')
p=root/'tools/typed72/drafts/cold_native_factory.cpp';t=p.read_bytes().decode('utf8')
a='for(double angle:facing>=0.?std::initializer_list<double>{-15.,0.,15.}:std::initializer_list<double>{195.,180.,165.}){Field<double> a;a.set(angle);values.push_back(a);}'
assert t.count(a)==1
# A conditional over initializer_lists leaves the range over a dead backing array.
b='const std::array<double,3> tripea_angles=facing>=0.?std::array<double,3>{-15.,0.,15.}:std::array<double,3>{195.,180.,165.};for(double angle:tripea_angles){Field<double> a;a.set(angle);values.push_back(a);}'
t=t.replace(a,b);p.write_bytes(t.encode('utf8'))
p=root/'tools/typed72/integrate_stage.py';t=p.read_text(encoding='utf8')
p=root/'build/typed72-match-v1/match_probe.cpp';t=p.read_text(encoding='utf8')
a='{"events",match.events},{"failure",failure}};';assert t.count(a)==1
t=t.replace(a,'{"events",match.events},{"failure",failure},{"bonus",{{"tick_calls",match.bonus_scan.tick_calls},{"last_scan",match.bonus_scan.last_scan},{"last_maintenance",match.bonus_scan.last_maintenance},{"now",match.bonus_scan.now},{"star_shots",match.bonus_plants.star_shots}}}};')
p.write_text(t,encoding='utf8')
