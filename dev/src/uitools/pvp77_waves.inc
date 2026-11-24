// Count units which completed the authoritative wave spawn. Clear them between
// batches to measure the whole day independent of player damage or CPU pacing.
struct AuditedWaveSpawns final: PveDirectorServices {
    MatchProbe& match;
    const std::vector<Point>& origins;
    double tile;
    AuditedWaveSpawns(MatchProbe& m,const std::vector<Point>& points,double size):match(m),origins(points),tile(size){}
    void verify(Point p)const{
        const bool located=std::any_of(origins.begin(),origins.end(),[&](Point q){
            return std::abs(wrap_delta(p.x,q.x,match.battle.world_width.get()))<=.41*tile&&std::abs(p.y-q.y)<.001;
        });
        expect(located,"director passed a spawn outside the original map points");
    }
    std::optional<std::string> spawn_wave_zombie(const std::string& key,Point where,double facing,int64_t wave)override{
        verify(where);return match.spawn_wave_zombie(key,where,facing,wave);
    }
    std::optional<std::string> spawn_coop_boss(const std::string& key,Point where)override{
        verify(where);return match.spawn_coop_boss(key,where);
    }
    ZombieRef native_zombie(const std::string& id)override{return match.native_zombie(id);}
    PlantRef native_plant(const std::string& id)override{return match.native_plant(id);}
    void drop_coin(double amount,Point where,const std::string& kind)override{match.drop_coin(amount,where,kind);}
    ZombieRef spawn_remnant(Point where)override{return match.spawn_remnant(where);}
    std::optional<Point> grave_soldier_exit(const std::string& card,const std::string& grave)override{return match.grave_soldier_exit(card,grave);}
    void set_daylight(bool night)override{match.set_daylight(night);}
    void event(PveEvent e)override{match.event(std::move(e));}
};
J compare_solo_waves(){
    Fixture fixture(decks({"plant:向日葵"},J::array()),{{"mode","coop"},{"campaign_deck",true}});
    auto& m=*fixture.match;
    auto bridge=pm_native_bridge::C_NativeBridge::m_from_marshaled(Args{});
    constexpr std::array maps{"山地","沙城","家院","要塞","大桥","铁道","遗迹","绿洲","小镇","古堡","木船","大楼"};
    int all_coop=0,all_lottery=0;
    J days=J::array();
    for(int day=1;day<=24;++day){
        const auto name=maps[(day-1)%maps.size()];
        int coop=0,lottery=0;J runs=J::array();
        for(const int seed:{7,41,3,71,19,110}){
            const V map=pm_maps::f_build_snapshot(Args{bridge,V(name),V(seed)});
            const V data=callm(map,SY("to_dict"),Args{});
            const auto plan=pm_pve::f_wave_plan(Args{V(day),V(true)});
            const auto pool=pm_pve::f_zombie_pool(Args{V(day),data,V(true)});
            PveDirectorCold cold{};cold.day=day;cold.coop=true;cold.seed=seed;
            cold.rng=PyRandom((seed*1000003)^(day*7919)^0x66).state();cold.cycle_rng=cold.rng;
            const auto explicit_points=py::m_get(rd(data,V("environment")),V("zombie_points"));
            if(explicit_points.truthy()){
                for(const auto& point:explicit_points.items())cold.points.push_back({point.idx(0).num(),point.idx(1).num()});
            }else{
                const auto layout=pm_team_maps::f_derive_layout(Args{map});const auto points=rd(layout,V("zombie_points"));
                for(const auto& p:points.items())cold.points.push_back({(p.idx(0).num()+.5)*fixture.tile(),p.idx(1).num()*fixture.tile()});
            }
            expect(!cold.points.empty(),"original map missing spawn points");
            for(const auto& row:plan.items())cold.plan.push_back({rd(row,V("time")).num(),int64_t(rd(row,V("budget")).num()),rd(row,V("flag")).truthy()});
            for(const auto& row:pool.items())cold.pool.push_back({py_str(row.idx(0)),int(row.idx(1).num()),row.idx(2).num()});
            J run={{"seed",seed},{"map_points",cold.points.size()}};
            for(bool draw:{false,true}){
                m.battle.solo.mode=draw?SoloMode::lottery:SoloMode::none;
                m.battle.solo.wave_remainder=2;m.battle.heroes.time=0.;
                AuditedWaveSpawns admissions{m,cold.points,fixture.tile()};
                PveDirector director{m.battle,m.catalog,m.budget,m.navigation,m.published.terrain,admissions};
                director.bind(cold);
                int ladders=0,flags=0,bosses=0,ordinary=0;size_t logged=m.log.size();
                for(int steps=0;steps<500&&!director.cleared();++steps){
                    m.battle.heroes.time+=5.;
                    const size_t previous=director.spawned.size();
                    director.step();
                    for(size_t i=previous;i<director.spawned.size();++i){
                        const auto unit=m.native_zombie(director.spawned[i]);expect(bool(unit),"spawn id lacks live unit");
                        const auto card=unit->protection.card.or_missing("");
                        if(card=="zombie:梯子僵尸")++ladders;else if(card=="zombie:旗帜僵尸")++flags;else ++ordinary;
                    }
                    for(;logged<m.log.size();++logged)if(m.log[logged].value("event",std::string{})=="pve_boss")++bosses;
                    for(const auto& t:*m.battle.targets)if(t.unit){
                        t.unit->body.hp=0.;
                        const auto& id=t.unit->source.id;if(id.present()&&!id.is_null())m.battle.native_objects.erase(id.get());
                    }
                    std::erase_if(*m.battle.targets,[](const auto& t){return bool(t.unit);});
                }
                expect(director.cleared(),"director stalled on day "+std::to_string(day));
                expect(bosses==(day%8==0?1:0),"incorrect boss count on day "+std::to_string(day));
                const auto count=int(director.spawned.size());
                (draw?lottery:coop)+=count;
                run[draw?"lottery":"coop"]={{"total",count},{"ordinary",ordinary},{"flag",flags},{"ladder",ladders},{"boss",bosses}};
            }
            runs.push_back(std::move(run));
        }
        const double ratio=double(lottery)/std::max(1,coop);
        std::cerr<<"day "<<day<<" coop "<<coop<<" lottery "<<lottery<<" ratio "<<ratio<<"\n";
        days.push_back({{"day",day},{"map",name},{"ratio",ratio},{"runs",std::move(runs)}});all_coop+=coop;all_lottery+=lottery;
    }
    expect(double(all_lottery)/all_coop>=.22&&double(all_lottery)/all_coop<=.28,"wave ratio across all days");
    return J{{"days",std::move(days)},{"coop",all_coop},{"lottery",all_lottery},{"ratio",double(all_lottery)/all_coop}};
}
