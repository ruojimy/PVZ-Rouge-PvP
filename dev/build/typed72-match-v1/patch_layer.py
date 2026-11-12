from pathlib import Path
p=Path('match_probe.cpp');t=p.read_text(encoding='utf8')
a='    void ordinary_damage(size_t i,double facing,double amount)override{expansion.ordinary(i,facing,amount);}\n'
assert t.count(a)==1
# Source install order: NativeExpansion then NativeContent, so content wraps expansion.
t=t.replace(a,'    HitResult content_lower_hit(size_t i,double facing,double amount)override{return expansion.ordinary(i,facing,amount);}\n')
p.write_text(t,encoding='utf8')
p=Path('probes/content_phase_probe.cpp');t=p.read_bytes().decode('utf8')
a='p.calls.push_back({"pea_damage",i,f,a});p.before("pea_damage");const auto result=actual.hit(i,f,a);p.after("pea_damage");return result;'
assert t.count(a)==1
t=t.replace(a,'p.calls.push_back({"pea_damage",i,f,a});p.before("pea_damage");const auto result=p.content_lower_hit(i,f,a);p.after("pea_damage");return result;')
a='    ContentCombatState combat_state;\n'
nl='\r\n' if '\r\n' in t else '\n'
a=a.replace('\n',nl);assert t.count(a)==1
t=t.replace(a,a+'    virtual HitResult content_lower_hit(size_t i,double f,double a){return lower.actual.hit(i,f,a);}'+nl)
p.write_bytes(t.encode('utf8'))
p=Path('probes/plants_probe.cpp');t=p.read_bytes().decode('utf8')
a='if(p.expansion_clock.delta.present())j["_pvp_clock_delta"]=J::object();'
assert t.count(a)==1
b='if(p.expansion_clock.delta.present()&&!p.expansion_clock.delta.is_null()){J d=J::object();constexpr std::array<const char*,10> names{"射cd","射","吃","发射cd","发射动画","埋藏","滚蛋","吸","爆了","路灯"};for(size_t i=0;i<names.size();++i)write(d,names[i],p.expansion_clock.delta.get()[i]);j["_pvp_clock_delta"]=d;}'
t=t.replace(a,b);p.write_bytes(t.encode('utf8'))
