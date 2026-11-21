// Production match composition, with fixture access to individual attack packets.
#define content_phase_unused_main r4_audit_content_phase_main
#define TYPED72_NO_MAIN
#include "match_probe.cpp"
#include "sim/typed72_app/cold_export.h"
#include "sim/pvp/battle_api.h"
#include "ui/gen/pm_hud.h"
#include "ui/gen/pm_app.h"
#include "ui/gen/pm_adaptive_pacing.h"
#include "ui/hand/pressure_pacing.h"
#include "sim/typed72_app/typed_battle.h"
#include "sim/pvp/gen/pm_pve.h"
#include "sim/pvp/gen/pm_catalog.h"
#include "core/fsutil.h"
#include "core/gil.h"
#include "pg/pg.h"
#include "data/datastore.h"

namespace {
using namespace pvz;
using namespace pvz::typed72;
void expect(bool ok,const std::string& message){if(!ok)throw std::runtime_error(message);}
void near(double actual,double wanted,const std::string& label){
    expect(std::abs(actual-wanted)<1e-6,label+" expected "+std::to_string(wanted)+" observed "+std::to_string(actual));
}
struct Fixture {
    std::unique_ptr<MatchProbe> match;
    std::optional<NativeBirthScope> births;
    Fixture(){
        static const auto cold=[] {
        auto handle=battle_from_scenario({{"fixture_flat",true},{"night",true},{"durable_heroes",true},{"seed",74404},
            {"rules",{{"local_test_mode",true}}},{"decks",{{"plant",{"plant:坚果","plant:向日葵","secret:密植","secret:体香"}},{"zombie",{"zombie:脑光墓碑","zombie:普通僵尸"}}}}});
        auto cold=typed72app::export_cold(handle.battle,74404);
        callm(handle.battle,SY("close"),Args{});
        return cold;
        }();
        const auto& c=cold.cold;
        match=std::make_unique<MatchProbe>(74404,c.at("battle").at("width").get<double>(),c.at("battle").at("rules").at("melon_splash_damage").get<double>());
        auto& m=*match;m.no_trace=true;m.release_fixtures=true;
        for(const auto& [name,p]:cold.atlas){
            SpritePixels s;s.width=p.width;s.height=p.height;
            for(const auto& px:p.rgba)s.pixels.push_back(Color{px[0],px[1],px[2],px[3]});
            m.battle.runtime.presentation.atlas.emplace(name,std::move(s));
        }
        m.install_frames_json(cold.draw_atlas,c);m.setup(c,J::object());
        births.emplace(m.battle.runtime,static_cast<PlantRegionServices&>(m));
        m.scheduler.step();m.flush_journal();++m.current_room;
        expect(m.battle.dense_planting,"dense secret not active");
    }
    PlantRef plant(std::string name,double x=1512.){
        auto& m=*match;auto id=m.spawn_unit("plant:"+name,"plant",x,960.,1.,false);
        expect(bool(id),"plant spawn "+name);return std::get<PlantRef>(m.battle.native_objects.get(*id).value());
    }
    ZombieRef zombie(std::string name,double x=1656.){
        auto& m=*match;auto id=m.spawn_unit("zombie:"+name,"zombie",x,960.,-1.,false);
        expect(bool(id),"zombie spawn "+name);auto z=std::get<ZombieRef>(m.battle.native_objects.get(*id).value());
        z->native.entry.set(500.);z->body.motion.get()={x,960.,0.,0.};return z;
    }
};

template<class F> J scenario(const std::string& id,F run){
    J row={{"id",id}};
    try{row.update(run());row["passed"]=true;}
    catch(const std::exception& e){row["passed"]=false;row["error"]=e.what();}
    return row;
}
void plain_pea(MatchProbe& m,Point center){
    auto shot=std::make_shared<Entity>("僵尸豌豆",-1.,Motion{});
    shot->source.projectile.set(shot->kind);shot->source.owner.set("zombie");
    shot->motion.get()={center.x,center.y,0.,0.};shot->facing=-1.;
    shot->pea.previous_x.set(center.x+12.);shot->pea.previous_y.set(center.y);
    expect(m.peas.hit(shot),"swept pea missed stack");
}
J stacked(){
    J rows=J::array();
    for(std::string fire:{"","fire","blue","fume","bite"})for(bool weak_last:{false,true}){
        const auto attack=fire.empty()?std::string("pea"):fire;
        rows.push_back(scenario(attack+(weak_last?".weak-last":".weak-first"),[&](){
        Fixture f;auto& m=*f.match;
        auto first=f.plant(weak_last?"坚果":"豌豆射手"),last=f.plant(weak_last?"豌豆射手":"坚果");
        auto weak=weak_last?last:first,strong=weak_last?first:last;
        weak->hp.set(1.);strong->hp.set(100.);
        const std::string label=(fire.empty()?std::string("pea"):fire)+(weak_last?" weak-last":" weak-first");
        expect(first!=last&&!first->dead.present()&&!last->dead.present(),label+" plants not individually alive before attack");
        const auto center=patch_plant_point(m.battle,*last).value();
        if(fire=="fume"){
            auto attacker=f.zombie("大喷菇僵尸");
            m.fume.line(attacker,{center.x+48.,center.y},180.,*native_plant_zombie_config("大喷菇僵尸"));
        }else if(fire=="bite"){
            auto attacker=f.zombie("普通僵尸",center.x);
            attacker->native.biting.set(0.);
            HeroContext ctx(m.world,{Seat::plant,Seat::zombie,CombatPhase::zombies,source_ref(attacker),{}});
            m.mobile.advance(m.battle.targets->size()-1);
        }else{
            auto shot=std::make_shared<Entity>("僵尸豌豆",-1.,Motion{});shot->source.projectile.set(shot->kind);
            shot->source.owner.set("zombie");shot->motion.get()={center.x,center.y,0.,0.};shot->facing=-1.;
            shot->pea.previous_x.set(center.x+12.);shot->pea.previous_y.set(center.y);
            if(!fire.empty()){
                f.plant("火炬树桩",center.x+96.);
                if(fire=="blue")m.world.globals.secrets.get()->push_back("蓝火");
                shot->pea.previous_x.set(center.x+120.);
                m.peas.torch_check(shot);
                expect(shot->source.zombie_fire.or_missing("")==fire,label+" torch conversion");
                shot->pea.previous_x.set(center.x+12.);
            }
            expect(m.peas.hit(shot),"swept pea missed stack");
        }
        const double direct=fire=="blue"?6.:fire=="fire"?4.:fire.empty()?2.:1.;
        const double splash=fire=="fume"?1.:fire=="blue"||fire=="fire"?direct/3.:0.;
        near(strong->hp.get(),100.-(weak_last?splash:direct),fire+" survivor");
        expect((weak->dead.present()||weak->hp.get()<=0.)==(weak_last||splash>=1.),fire+" wrong weak victim");
        expect(!strong->dead.present(),fire+" cleared the living stackmate");
        near(weak->hp.get(),1.-(weak_last?direct:splash),fire+" earlier/later damage");
        m.maintenance.run();
        expect(std::find(m.battle.plant_roster->begin(),m.battle.plant_roster->end(),strong)!=m.battle.plant_roster->end(),fire+" maintenance removed survivor");
        return J{{"attack",attack},{"weak_last",weak_last},{"earlier_hp",first->hp.get()},{"later_hp",last->hp.get()}};
        }));
    }
    rows.push_back(scenario("three.pumpkin-middle",[](){
        Fixture f;auto& m=*f.match;
        auto first=f.plant("豌豆射手"),shell=f.plant("南瓜头"),last=f.plant("向日葵");
        first->hp.set(30.);shell->hp.set(18.);last->hp.set(10.);
        const auto pos=patch_plant_point(m.battle,*last).value();
        auto attacker=f.zombie("普通僵尸",pos.x);attacker->native.biting.set(0.);
        HeroContext ctx(m.world,{Seat::plant,Seat::zombie,CombatPhase::zombies,source_ref(attacker),{}});
        m.mobile.advance(m.battle.targets->size()-1);
        near(first->hp.get(),30.,"oldest");near(shell->hp.get(),18.,"middle pumpkin");near(last->hp.get(),9.75,"exposed sunflower with producer protection");
        return J{{"hp",{first->hp.get(),shell->hp.get(),last->hp.get()}}};
    }));
    rows.push_back(scenario("three.fume-middle-death-next-hit",[](){
        Fixture f;auto& m=*f.match;
        auto a=f.plant("坚果"),b=f.plant("豌豆射手"),c=f.plant("卷心菜投手");
        a->hp.set(100.);b->hp.set(1.);c->hp.set(10.);
        auto pos=patch_plant_point(m.battle,*c).value();
        m.fume.line(f.zombie("大喷菇僵尸"),{pos.x+48.,pos.y},180.,*native_plant_zombie_config("大喷菇僵尸"));
        near(a->hp.get(),99.,"first after fume");near(b->hp.get(),0.,"middle after fume");near(c->hp.get(),9.,"newest after fume");
        m.maintenance.run();auto& roster=*m.battle.plant_roster;
        expect(roster.size()==2 && roster.front()==a && roster.back()==c,"middle death changed survivors or their order");
        plain_pea(m,pos);near(a->hp.get(),99.,"oldest after pea");near(c->hp.get(),7.,"newest after pea");
        return J{{"surviving_hp",{a->hp.get(),c->hp.get()}}};
    }));
    rows.push_back(scenario("three.two-hits-one-tick",[](){
        Fixture f;auto& m=*f.match;
        auto a=f.plant("向日葵"),b=f.plant("坚果"),c=f.plant("豌豆射手");
        a->hp.set(30.);b->hp.set(100.);c->hp.set(1.);
        auto pos=patch_plant_point(m.battle,*c).value();
        plain_pea(m,pos);near(c->hp.get(),-1.,"first direct");near(b->hp.get(),100.,"first hit spilled");
        plain_pea(m,pos);near(b->hp.get(),98.,"second hit missed newly exposed plant");near(a->hp.get(),30.,"second hit spilled");
        m.maintenance.run();auto& roster=*m.battle.plant_roster;
        expect(roster.size()==2 && roster.front()==a && roster.back()==b,"same-tick cleanup removed survivor");
        return J{{"surviving_hp",{a->hp.get(),b->hp.get()}}};
    }));
    return rows;
}
J armor(){
    J rows=J::array();
    for(auto [name,def]:std::vector<std::pair<std::string,int>>{{"黑普通僵尸",1},{"黑路障僵尸",1},{"黑铁桶僵尸",1},{"橄榄球僵尸",4},{"黑橄榄僵尸",4},{"世界吞噬者",2},{"克苏鲁之眼",12},{"骷髅王",10}}){
        Fixture f;auto& m=*f.match;auto attacker=f.zombie("普通僵尸"),target=f.zombie(name);
        near(target->body.defense.get(),def,name+" registered defense");
        for(bool target_charmed:{false,true}){
            if(target->terraria&&target_charmed)continue;
            if(target_charmed){target->source.charmed.set(350.);attacker->source.charmed.erase();}
            else{attacker->source.charmed.set(350.);target->source.charmed.erase();}
            auto owner=target_charmed?Seat::zombie:Seat::plant;
            HeroContext ctx(m.world,{owner==Seat::plant?Seat::zombie:Seat::plant,owner,CombatPhase::zombies,source_ref(attacker),{}});
            target->body.hp=1000.;target->body.armor_hp=target->body.hand_hp=0.;
            m.chain.damage.ordinary(CombatTarget::zombie(target),1.,100.);
            near(target->body.hp,1000.-std::max(1.,100.-5.*def),name+" inter-zombie hit");
            near(target->body.defense.get(),def,name+" persisted defense");
            rows.push_back({{"target",name},{"charmed",target_charmed},{"defense",def},{"loss",1000.-target->body.hp}});
        }
    }
    return rows;
}
J centers(){
    J rows=J::array();
    for(std::string name:{"小鬼僵尸","小型史莱姆","海盗鹦鹉","中型史莱姆"}){
        Fixture f;auto& m=*f.match;auto z=f.zombie(name);const auto t=CombatTarget::zombie(z);
        const auto expected_y=960.-48.*(name=="中型史莱姆"?.75:.5);
        auto shot=std::make_shared<Entity>("尖刺",1.,Motion{});shot->motion.get()={1512.,920.,0.,0.};
        NativeBallistics solver(m.battle);auto aimed=solver.pick(shot);
        expect(aimed.target.has_value(),"lobber missed "+name);near(aimed.target->point.x,1656.,"lobber x");near(aimed.target->point.y,expected_y,"lobber acquire "+name);
        near(solver.current(shot,aimed.target->index).target.value().point.y,expected_y,"lobber reaim "+name);
        shot->motion.get().x=1608.;shot->motion.get().y=960.;
        auto squash=solver.pick(shot,true);near(squash.target.value().point.y,expected_y,"squash acquire "+name);
        SquashLock lock;lock.target_index.set(squash.target.value().index);
        near(solver.squash_locked(shot,lock).target.value().point.y,expected_y,"squash reaim "+name);
        shot->motion.get().x=1512.;shot->motion.get().y=920.;
        auto point=m.target_dispatch.point(t);near(point.y,expected_y,"content aim "+name);
        auto mortar=f.plant("豌豆迫击炮");auto aim=m.mortars.aim(mortar,t);auto solution=aim.solution.value();
        near(aim.start.x+solution.vx*solution.time,point.x,"mortar x");
        near(aim.start.y+solution.vy*solution.time+.5*4.*m.battle.runtime.plk*solution.time*solution.time,expected_y,"mortar y");
        shot->tracking.set(2.);m.battle.runtime.entities.list()->push_back(shot);
        m.contacts.home(m.battle.runtime.entities.list()->size()-1,aimed.target->index);
        near(shot->rotation.get(),std::atan2(expected_y-920.,1656.-1512.)*180./std::acos(-1.),"cattail direction "+name);
        rows.push_back({{"target",name},{"x",point.x},{"y",point.y}});
    }
    return rows;
}
J impact(){
    J cases=J::array();int misses=0;
    for(const char* name:{"玉米投手","卷心菜投手","西瓜投手","冰瓜投手","甜椒投手","豌豆迫击炮","香蒲"}){
        for(const char* small:{"小鬼僵尸","小型史莱姆","海盗鹦鹉"}){
            Fixture f;auto& m=*f.match;auto p=f.plant(name);auto z=f.zombie(small);
            z->body.hp=10000.;z->body.butter.set(100000.);z->max_hp.set(10000.);
            int step=0;
            for(;step<270&&z->body.hp>=10000.;++step){m.scheduler.step();m.flush_journal();++m.current_room;}
            bool hit=z->body.hp<10000.;
            if(!hit)++misses;
            cases.push_back({{"plant",name},{"target",small},{"room_steps",step},{"hit",hit},{"loss",10000.-z->body.hp}});
            std::cerr<<cases.back().dump()<<std::endl;
        }
    }
    {Fixture f;auto& m=*f.match;auto p=f.plant("豌豆射手");
     m.spawn_unit("zombie:世界吞噬者","zombie",1752.,960.,-1.,false);
     bool damage=false;int step=0;
     for(;step<300&&!damage;++step){
         m.scheduler.step();m.flush_journal();++m.current_room;
         for(const auto& t:*m.battle.targets)if(!t.is_hero()&&t.unit->terraria&&t.unit->body.hp<t.unit->max_hp.or_missing(0.)){damage=true;break;}
     }
     cases.push_back({{"plant","豌豆射手"},{"target","世界吞噬者"},{"room_steps",step},{"hit",damage}});
     if(!damage)++misses;std::cerr<<cases.back().dump()<<std::endl;}
    expect(misses==0,std::to_string(misses)+" projectile/target pairs missed");
    return cases;
}
J boss_lanes(){
    J rows=J::array();
    for(int type:{4,5,13,14,15,35,36}){
        Fixture f;auto& m=*f.match;
        auto unit=m.make_terraria(type,{1656.,930.},{});expect(bool(unit),"NPC setup");
        m.indexes.rows=std::make_shared<TargetBuckets>();m.indexes.columns=std::make_shared<TargetBuckets>();
        m.mobile.register_stationary(m.battle.targets->size()-1);
        const auto has=[](const TargetBuckets& grid,int key,int val){for(auto& row:grid)if(row.first==key&&std::find(row.second.begin(),row.second.end(),val)!=row.second.end())return true;return false;};
        expect(has(*m.indexes.rows,19,34)&&has(*m.indexes.columns,34,19),"missing NPC row/column "+std::to_string(type));
        J fired=J::array();
        if(type==5||type==13){
            std::vector<std::pair<std::string,PlantRef>> plants;
            for(const char* name:{"豌豆射手","玉米投手","卷心菜投手","西瓜投手","冰瓜投手","甜椒投手"})
                plants.emplace_back(name,f.plant(name,1512.-48.*plants.size()));
            HeroContext phase(m.world,{Seat::zombie,Seat::plant,CombatPhase::plants,{},{}});
            m.plants.run();
            for(const auto& [name,plant]:plants){
                expect(plant->shooting.or_missing(0.)>0.,name+" failed to attack NPC "+std::to_string(type));fired.push_back(name);
            }
        }
        rows.push_back({{"type",type},{"fired",fired}});
    }
    return rows;
}
J boss_hits(){
    J rows=J::array();
    for(auto [id,name,type,mixed]:std::vector<std::tuple<std::string,std::string,int,bool>>{
        {"eye.body","克苏鲁之眼",4,true},{"eye.servant","克苏鲁之眼",5,false},
        {"worm.segment","世界吞噬者",14,false},{"skeleton.head","骷髅王",35,true},{"skeleton.hand","骷髅王",36,false}}){
        rows.push_back(scenario(id,[&](){
            Fixture f;auto& m=*f.match;
            m.fixture_set_avatar(Seat::plant,{{"玩家位置",{1920.,960.,0.,0.}}});
            m.fixture_set_avatar(Seat::zombie,{{"玩家位置",{3900.,960.,0.,0.}},{"_pvp_butter",1000000.}});
            std::vector<PlantRef> plants;
            if(mixed){
                for(const char* kind:{"香蒲","甜椒投手","玉米投手","卷心菜投手","豌豆射手"})
                    plants.push_back(f.plant(kind,1320.+96.*plants.size()));
            }else plants.push_back(f.plant("西瓜投手"));
            expect(bool(m.spawn_unit("zombie:"+name,"zombie",1848.,940.,-1.,false)),"boss spawn");
            if(!mixed)expect(bool(m.spawn_unit("zombie:普通僵尸","zombie",1752.,960.,-1.,false)),"nearby ordinary zombie");
            bool fired=false;double loss=0.;int step=0;
            for(;step<450 && !(fired && loss>0.);++step){
                std::vector<std::pair<ZombieRef,double>> observed;
                for(const auto& t:*m.battle.targets)
                    if(t.unit && t.unit->terraria && t.unit->terraria->type==type)
                        observed.emplace_back(t.unit,t.unit->body.hp);
                // Keep references to victims that can die and leave the roster in this step.
                m.scheduler.step();m.flush_journal();++m.current_room;
                for(const auto& p:plants)fired|=p->shooting.or_missing(0.)>0.;
                for(const auto& [unit,hp]:observed)loss=std::max(loss,hp-std::max(0.,unit->body.hp));
            }
            expect(fired && loss>0.,"no real launch/impact for "+id+" fired="+std::to_string(fired)+" loss="+std::to_string(loss));
            return J{{"type",type},{"fired",fired},{"hp_lost",loss},{"room_steps",step}};
        }));
    }
    return rows;
}
J fragrance(){
    Fixture f;auto& m=*f.match;auto z=f.zombie("普通僵尸",1800.);
    HeroContext ctx(m.world,{Seat::plant,Seat::zombie,CombatPhase::zombies,source_ref(z),{}});
    const auto pos=*m.world.globals.position.get();
    z->body.motion.get()={pos.x,pos.y,0.,0.};z->native.biting.set(0.);
    m.mobile.advance(m.battle.targets->size()-1);
    expect(z->poison.poison.present(),"fragrant hero bite missed poison");
    const auto state=z->poison.poison.get();
    near(state->level.get(),1.,"poison level");near(state->until.get()-m.world.tick,500.,"poison duration");
    return true;
}
J recovery(){
    auto h=battle_from_scenario({{"seed",74404},{"fixture_flat",true}});
    auto screen=callm(pg::display_module(),SY("set_mode"),Args{V::tuple({V(960),V(540)})});
    auto app=pm_app::new_Application(Args{pg::pygame_module(),screen,h.bridge});callm(app,SY("create"),Args{V(true)});
    auto room=getattr(app,SY("room")),pacing=pm_adaptive_pacing::new_AdaptivePacing(Args{});
    setattr(room,SY("pacing"),pacing);setattr(pacing,SY("ratio"),V(3.));
    auto view=py::json_loads(V(R"({"phase":"battle","mode":"coop","battle":{"native_frame":{"command_count":400},"units":[]}})"));
    setattr(app,SY("view"),view);
    for(int i=0;i<200;++i)pressure741::observe(app,.05,.045);
    double slow=getattr(pacing,SY("scale")).num();expect(slow<.9,"test did not reach slow motion");
    auto battle=typed72app::wrap_battle(h.battle);typed72app::start_battle_session(battle);
    callm(battle,SY("spawn"),Args{V("zombie:普通僵尸"),V("zombie"),V(2256.),V(960.),V(-1.)});
    callm(battle,SY("step"),Args{});setattr(room,SY("battle"),battle);
    auto alive=getattr(battle,SY("live_mobile_zombies")).num();expect(alive>=1.&&alive<=6.,"wrong live zombie count");
    for(int i=0;i<100;++i)pressure741::observe(app,.05,.045);
    double normal=getattr(pacing,SY("scale")).num();near(normal,1.,"end of wave recovery");
    callm(app,SY("close_room"),Args{});
    return {{"overloaded_scale",slow},{"living",alive},{"draw_commands",400},{"final_scale",normal}};
}
J coop_revision(){
    auto h=battle_from_scenario({{"seed",74404},{"fixture_flat",true}});
    auto screen=callm(pg::display_module(),SY("set_mode"),Args{V::tuple({V(960),V(540)})});
    auto app=pm_app::new_Application(Args{pg::pygame_module(),screen,h.bridge});
    callm(app,SY("create"),Args{V(true)});
    auto room=getattr(app,SY("room"));
    auto deck=py::json_loads(V(R"(["plant:花盆","plant:豌豆射手"])"));
    expect(!callm(room,SY("set_mode"),Args{V("coop")}).truthy(),"coop setup");
    expect(!callm(room,SY("connect"),Args{V("guest")}).truthy(),"guest join");
    expect(!callm(room,SY("set_pve"),Args{V(1),deck}).truthy(),"campaign setup");
    auto revision=[&](){return getattr(room,SY("revision"));};
    auto command=[&](const char* peer,const char* kind,V rev){
        auto payload=V::dict();setitem(payload,V("type"),V(kind));setitem(payload,V("revision"),rev);
        setitem(payload,V("terrain_hash"),getattr(getattr(room,SY("map")),SY("terrain_hash")));
        setitem(payload,V("deck"),deck);
        return callm(room,SY("command"),Args{V(peer),payload});
    };
    auto initial=revision();
    expect(!command("guest","pve_unready",initial).truthy()&&revision()==initial,"unready no-op consumed revision");
    auto open=[&](){
        expect(!command("guest","confirm_map",revision()).truthy(),"guest confirmation");
        auto ready=revision();
        expect(!command("guest","pve_unready",ready).truthy()&&revision()!=ready,"real unready transition missing");
        return ready;
    };
    auto prior=open();
    expect(command("host","pve_deck",prior).truthy(),"other peer used old revision");
    expect(!command("guest","pve_deck",prior).truthy(),"own immediately queued edit rejected");
    expect(command("guest","pve_deck",prior).truthy(),"replay accepted");
    prior=open();
    expect(!command("host","confirm_map",revision()).truthy(),"host confirmation");
    expect(command("guest","pve_deck",prior).truthy(),"intervening host revision ignored");
    callm(app,SY("close_room"),Args{});
    return true;
}
J rules(){
    Fixture f;auto& m=*f.match;
    near(m.catalog.at("plant:石块").cost,0.,"stone");
    for(auto side:{"plant","zombie"})for(int slots:{7,8,13}){
        auto rules=V::dict();setitem(rules,V("local_test_mode"),V(true));
        near(pm_hud::f_bank_page_size(Args{rules,V(side),V(slots),V(false)}).num(),slots,"test bank");
    }
    for(int d:{7,8,9,16,24,25})for(bool coop:{false,true})
        near(pm_pve::f_skip_price(Args{V(d),V(coop)}).num(),coop&&(d==8||d==16||d==24)?50000.:10000.,"skip");
    auto campaign=pm_pve::new_Campaign(Args{});
    setattr(campaign,SY("coins"),V(49999));
    expect(callm(campaign,SY("skip_day"),Args{V(true),V(50000)}).truthy(),"boss skip admitted short balance");
    near(getattr(campaign,SY("coins")).num(),49999.,"rejected skip charged coins");
    setattr(campaign,SY("coins"),V(50000));
    expect(!callm(campaign,SY("skip_day"),Args{V(true),V(50000)}).truthy(),"boss skip rejected exact balance");
    near(getattr(campaign,SY("coins")).num(),0.,"boss skip cost");
    auto sled=f.zombie("雪橇车僵尸"),team=f.zombie("雪橇车小队");
    near(sled->content.cart_deadline.get(),m.world.tick+20000.,"80 second clock");expect(!team->content.cart_deadline.present(),"team got cart timer");
    m.world.tick+=19999;m.carts.before(sled);expect(sled->body.hp>0.,"early expiry");++m.world.tick;m.carts.before(sled);expect(sled->body.hp==0.&&sled->content.cart_expired.get(),"missed expiry");
    return true;
}
}
int main(int argc,char** argv){
    using namespace pvz;
    if(argc!=2)return 2;
    auto out=std::filesystem::absolute(u8p(argv[1]));std::filesystem::create_directories(out);
    env_set_u8("PVP_USERDATA",p8(out/"userdata"));env_set_u8("SDL_VIDEODRIVER","dummy");env_set_u8("SDL_AUDIODRIVER","dummy");
    SDL_SetMainReady();gil::init();data::set_data_dir("extract/data");pg::install_pygame();init_pvp_modules();
    const J packaged=data::module("catalog").at("CARDS");
    J runtime=J::parse(dump(pm_catalog::CARDS));
    for(auto it=runtime.begin();it!=runtime.end();){
        if(it.value().value("behavior",std::string{})=="terraria")it=runtime.erase(it);else ++it;
    }
    std::ofstream(out/"catalog-diff.json")<<J::diff(packaged,runtime).dump(2);
    J result={{"checks",J::array()},{"failures",0}};int failures=0;
    for(auto [name,fn]:std::vector<std::pair<std::string,J(*)()>>{{"密植_啃咬_僵尸豌豆_红火_蓝火_大喷",stacked},{"魅惑_双方防御与Boss",armor},{"索敌_小体型中心",centers},{"索敌_七种植物实弹与世界吞噬者",impact},{"索敌_Boss与召唤物行列",boss_lanes},{"索敌_Boss各部位实弹",boss_hits},{"体香_真实啃咬",fragrance},{"安卓调速_高负载转少量僵尸",recovery},{"测试卡槽_跳关_石块_雪橇车",rules},{"合作_取消确认与过期配置",coop_revision}}){
        std::cerr<<"RUN "<<name<<std::endl;J check={{"name",name}};try{
            auto evidence=fn();bool passed=true;
            if(evidence.is_array())for(const auto& row:evidence)if(row.is_object() && !row.value("passed",true))passed=false;
            check["evidence"]=std::move(evidence);check["passed"]=passed;if(!passed)++failures;
        }catch(const std::exception& e){check["error"]=e.what();check["passed"]=false;++failures;}
        result["checks"].push_back(check);std::cerr<<check.dump()<<std::endl;
    }
    result["failures"]=failures;std::ofstream(out/"results.json")<<result.dump(2);return failures?1:0;
}

