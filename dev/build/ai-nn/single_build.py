"""Build the one-action controller against the kernel used for the reference matches."""
from single_study import *
def build():
    dest=OUT/'native-src';dest.mkdir(exist_ok=True);receipt=read(LAST/'context-build.json')
    if (OUT/'build.json').exists():
        assert sha(NATIVE)==read(OUT/'build.json')['binary'];return
    for name,h in receipt['sources'].items():
        p=LAST/'context-src'/name;assert sha(p)==h;shutil.copyfile(p,dest/name)
    for name,h in receipt['libraries'].items():assert sha(BUILD/'Release'/name)==h
    shutil.copyfile(H/'single_control.inc',dest/'single_control.inc')
    def edit(file,reps):
        p=dest/file;s=p.read_text('utf8')
        for a,b in reps:s=replace_once(s,a,b)
        p.write_text(s,'utf8')
    edit('switch_control.inc',[
        ('    // Compare the best legal forward','    #include "single_control.inc"\n    // Compare the best legal forward'),
        ('return forced(t)||(mask', 'return !review_old&&((!stamped_mode()&&forced(t))||(mask'),
        ('switch_policy.value("adaptive",false)));}', 'switch_policy.value("adaptive",false))));}'),
        ('const bool fork=forced(b.v.time);','const bool fork=!stamped_mode()&&forced(b.v.time);'),
        ('const bool place=gain>=-switch_policy.at("arrival_margin").get<double>();','''auto live=arrival_features(b,a);
                    const double live_gain=switch_policy.contains("arrival_live")?predict(live,switch_policy.at("arrival_live")):gain;
                    bool place=live_gain>=-switch_policy.at("arrival_margin").get<double>();
                    if(mode()=="arrival_pair"&&std::llround(b.v.time*30)==std::llround(switch_after*30))place=switch_force==1;'''),
        ('{"gain",gain},{"target"', '{"gain",live_gain},{"x",live},{"target"'),
        ('        if(!route||a.kind!=build)return;', '        if(a.kind==build||a.kind==spawn)last_deploy=b.v.time;\n        if(!route||a.kind!=build)return;')])
    edit('position_head.h',[
        ('        const bool examine=wrapped&&switching.examine(v.time,observed);','        switching.observed_mask=observed;\n        bool examine=wrapped&&switching.examine(v.time,observed);'),
        ('        if(at_order||flag_due||examine||switching.traveling()){','''        if(wrapped&&switching.finish_slice(v.time,observed,at_order)){
            target_card.clear();move_until=0.;options=Options{};examine=false;
            at_order=v.time>=next_action||(!hint.card.empty()&&v.time>=next_action-.65);
        }
        const bool probe=wrapped&&switching.stamped_mode()&&switching.forced(v.time);
        const bool lease=wrapped&&switching.leased();
        if(lease)examine=observed||at_order||switching.forced(v.time);
        if(at_order||flag_due||examine||probe||switching.traveling()){'''),
        ('            if(at_order||examine||switching.traveling()){','            if(at_order||examine||probe||switching.traveling()){'),
        ('                const int choice=examine?switching.decide(list,b,service,observed):-1;', '''                if(probe)switching.observe_tick(b,service,observed,list);
                int choice=-1;
                if(lease&&examine&&!switching.arriving(b,service)){
                    choice=switching.lease_decide(list,b,service,observed);
                    if(was_event&&!event_enabled){target_card.clear();move_until=0.;options=Options{};}
                }else if(!lease&&examine)choice=switching.decide(list,b,service,observed);'''),
        ('                if(at_order||(!was_event&&event_enabled)||switching.traveling()){','                if(at_order||(!was_event&&event_enabled)||(lease&&was_event&&!event_enabled)||switching.traveling()){')])
    cmake=re.search('^CMAKE_COMMAND:INTERNAL=(.+)$',(BUILD/'CMakeCache.txt').read_text('utf8'),re.M).group(1)
    cmd(cmake,'-S',dest,'-B',OUT/'native','-G','Visual Studio 17 2022','-A','x64')
    cmd(cmake,'--build',OUT/'native','--config','Release','--parallel',2)
    shutil.copyfile(BUILD/'Release/SDL2.dll',NATIVE.parent/'SDL2.dll')
    fixed(OUT/'build.json',dict(binary=sha(NATIVE),libraries=receipt['libraries'],sources={p.name:sha(p) for p in dest.iterdir()}))
def build_arrival_probe():
    dest=OUT/'probe-src';dest.mkdir(exist_ok=True);receipt=read(OUT/'build.json')
    for name,h in receipt['sources'].items():
        p=OUT/'native-src'/name;assert sha(p)==h
        shutil.copyfile(p,dest/name)
    for name,h in receipt['libraries'].items():assert sha(BUILD/'Release'/name)==h
    p=dest/'single_control.inc';s=p.read_text('utf8')
    s=replace_once(s,'return m=="review"||m=="arrival_pair";','return m=="review"||m=="arrival_pair"||switch_policy.value("arrival_probe",false);')
    p.write_text(s,'utf8')
    p=dest/'switch_control.inc';s=p.read_text('utf8')
    s=replace_once(s,'if(mode()=="arrival_pair"&&','if((mode()=="arrival_pair"||switch_policy.value("arrival_probe",false))&&')
    p.write_text(s,'utf8')
    cmake=re.search('^CMAKE_COMMAND:INTERNAL=(.+)$',(BUILD/'CMakeCache.txt').read_text('utf8'),re.M).group(1)
    cmd(cmake,'-S',dest,'-B',OUT/'probe','-G','Visual Studio 17 2022','-A','x64')
    cmd(cmake,'--build',OUT/'probe','--config','Release','--parallel',2)
    exe=OUT/'probe/Release/position_match.exe'
    shutil.copyfile(BUILD/'Release/SDL2.dll',exe.parent/'SDL2.dll')
    fixed(OUT/'probe-build.json',dict(binary=sha(exe),libraries=receipt['libraries'],sources={p.name:sha(p) for p in dest.iterdir()}))
def build_live():
    dest=OUT/'live-src';dest.mkdir(exist_ok=True);receipt=read(OUT/'probe-build.json')
    for name,h in receipt['sources'].items():
        p=OUT/'probe-src'/name;assert sha(p)==h;shutil.copyfile(p,dest/name)
    shutil.copyfile(H/'single_dense.inc',dest/'single_dense.inc')
    p=dest/'switch_control.inc';s=p.read_text('utf8')
    s=replace_once(s,'    static double predict(', '    #include "single_dense.inc"\n    static double predict(')
    s=replace_once(s,'?predict(live,switch_policy.at("arrival_live"))','?cached(live,switch_policy.at("arrival_live"))')
    p.write_text(s,'utf8')
    p=dest/'single_control.inc';s=p.read_text('utf8')
    for key in ('one_head','trip_head'):
        s=replace_once(s,'predict(x,switch_policy.at("'+key+'"))','cached(x,switch_policy.at("'+key+'"))')
    p.write_text(s,'utf8')
    p=dest/'position_head.h';s=p.read_text('utf8')
    s=replace_once(s,'if(lease&&examine&&!switching.arriving(b,service)){\n                    choice=switching.lease_decide(list,b,service,observed);','''if(lease&&examine&&((observed&15)||!switching.arriving(b,service))){
                    const bool requote=!was_event&&std::any_of(me.deck.begin(),me.deck.end(),[&](const std::string& k){
                        if(!k.starts_with("zombie:"))return false;
                        auto cost=service.card(k).cost;return event_choices.price(k,cost)!=cost;
                    });
                    if(requote){
                        event_enabled=true;
                        auto priced=candidates();
                        event_enabled=false;
                        choice=switching.lease_decide(priced,b,service,observed);
                    }else choice=switching.lease_decide(list,b,service,observed);''')
    p.write_text(s,'utf8')
    cmake=re.search('^CMAKE_COMMAND:INTERNAL=(.+)$',(BUILD/'CMakeCache.txt').read_text('utf8'),re.M).group(1)
    cmd(cmake,'-S',dest,'-B',OUT/'live','-G','Visual Studio 17 2022','-A','x64')
    cmd(cmake,'--build',OUT/'live','--config','Release','--parallel',2)
    exe=OUT/'live/Release/position_match.exe';shutil.copyfile(BUILD/'Release/SDL2.dll',exe.parent/'SDL2.dll')
    fixed(OUT/'live-build.json',dict(binary=sha(exe),libraries=receipt['libraries'],sources={p.name:sha(p) for p in dest.iterdir()}))
