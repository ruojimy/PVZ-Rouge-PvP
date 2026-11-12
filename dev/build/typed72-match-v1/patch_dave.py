from pathlib import Path
root=Path(r'C:\Users\xiech\Downloads\PVZ_rougePvP_native')
p=root/'tools/typed72/drafts/native_tick.cpp';t=p.read_bytes().decode('utf8')
nl='\r\n' if '\r\n' in t else '\n'
a='    for(const auto seat:state_.present) {'+nl+'        presentation.entity_override(seat);'
assert t.count(a)==1
t=t.replace(a,'    for(const auto seat:state_.present) {'+nl+'        dave_state(world_.heroes.hero(seat));'+nl+'        presentation.entity_override(seat);')
a='void NativeTick::tracking() {';assert t.count(a)==1
t=t.replace(a,'''namespace {
// Original dave_state region 67018..67400, run for each avatar through
// _draw_dave on every native tick, drawn or not. Its alpha is presentation;
// the hurt clock it advances is authoritative state. HP is compared on the
// source's 20-point scale.
void dave_state(HeroState& hero) {
    auto& f=hero.frame;const double maximum=hero.max_hp.or_missing(20.);
    const double hp=maximum!=20.?f.hp.get()*20./maximum:f.hp.get();
    double hurt=f.hurt.or_missing(0.);
    if(hp<=0.)hurt=1.;
    if(hp<20.){
        if(hurt>0.)hurt+=1.;
        if(hurt==50.)hurt=0.;
    }
    f.hurt.set(hurt);
}
}
'''.replace('\n',nl)+a)
p.write_bytes(t.encode('utf8'))
s=root/'build/typed72-match-v1/match_probe.cpp';t=s.read_text(encoding='utf8')
a='write(j,"_pvp_producer",u.producer);';assert t.count(a)==1
t=t.replace(a,'write(j,"_pvp_producer",u.producer);write(j,"_pvp_produced",u.produced);write(j,"_pvp_mature",u.mature);')
s.write_text(t,encoding='utf8')
