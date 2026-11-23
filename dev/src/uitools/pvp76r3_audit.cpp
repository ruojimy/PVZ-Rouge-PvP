// PvP76 r3 focused mechanics on the production match composition (same kernel and
// composition as the shipped Session).
//   pvp76r3_audit <out-folder>
#define content_phase_unused_main pvp76r3_audit_content_phase_main
#define TYPED72_NO_MAIN
#include "match_probe.cpp"
#include "sim/typed72_app/cold_export.h"
#include "sim/pvp/battle_api.h"
#include "sim/pvp/gen/pm_catalog.h"
#include "sim/pvp/gen/pm_pve.h"
#include "core/fsutil.h"
#include "core/gil.h"
#include "pg/pg.h"
#include "data/datastore.h"
#include "sim/pvp/hand/pvp76r2_coop.h"

namespace {
using namespace pvz;
using namespace pvz::typed72;
void expect(bool ok,const std::string& message){if(!ok)throw std::runtime_error(message);}
void near(double actual,double wanted,const std::string& label,double eps=1e-6){
    expect(std::abs(actual-wanted)<eps,label+" expected "+std::to_string(wanted)+" observed "+std::to_string(actual));
}
J decks(J plants,J zombies){return J{{"plant",plants},{"zombie",zombies}};}
struct Fixture {
    std::unique_ptr<MatchProbe> match;
    std::optional<NativeBirthScope> births;
    // extra: additional battle_from_scenario keys (mode, decks for plant2 ...).
    explicit Fixture(const J& d,const J& extra=J::object()){
        static std::map<std::string,typed72app::ColdExport> colds;
        const auto cache_key=d.dump()+extra.dump();
        auto found=colds.find(cache_key);
        if(found==colds.end()){
            J sc={{"fixture_flat",true},{"durable_heroes",true},{"seed",76301},{"rules",{{"local_test_mode",false}}},{"decks",d}};
            for(const auto& [k,v]:extra.items())sc[k]=v;
            auto handle=battle_from_scenario(sc);
            found=colds.emplace(cache_key,typed72app::export_cold(handle.battle,76301)).first;
            callm(handle.battle,SY("close"),Args{});
        }
        const auto& cold=found->second;const auto& c=cold.cold;
        match=std::make_unique<MatchProbe>(76301,c.at("battle").at("width").get<double>(),c.at("battle").at("rules").at("melon_splash_damage").get<double>());
        auto& m=*match;m.no_trace=true;m.release_fixtures=true;
        for(const auto& [name,p]:cold.atlas){
            SpritePixels s;s.width=p.width;s.height=p.height;
            for(const auto& px:p.rgba)s.pixels.push_back(Color{px[0],px[1],px[2],px[3]});
            m.battle.runtime.presentation.atlas.emplace(name,std::move(s));
        }
        m.install_frames_json(cold.draw_atlas,c);m.setup(c,J::object());
        births.emplace(m.battle.runtime,static_cast<PlantRegionServices&>(m));
        m.scheduler.step();m.flush_journal();++m.current_room;
    }
    double tile()const{return match->battle.runtime.tile;}
    PlantRef plant(std::string name,double x=1512.,double facing=1.,double y=960.){
        auto& m=*match;auto id=m.spawn_unit("plant:"+name,"plant",x,y,facing,false);
        expect(bool(id),"plant spawn "+name);return std::get<PlantRef>(m.battle.native_objects.get(*id).value());
    }
    ZombieRef zombie(std::string name,double x=1656.,double facing=-1.,double y=960.){
        auto& m=*match;auto id=m.spawn_unit("zombie:"+name,"zombie",x,y,facing,false);
        expect(bool(id),"zombie spawn "+name);auto z=std::get<ZombieRef>(m.battle.native_objects.get(*id).value());
        if(!z->terraria){z->native.entry.set(500.);z->body.motion.get()={x,y,0.,0.};}return z;
    }
    void run(int64_t ticks){auto& m=*match;const auto end=m.battle.heroes.tick+ticks;int guard=0;while(m.battle.heroes.tick<end&&++guard<200000)m.scheduler.step();}
    void hero_at(Seat seat,double x,double y=960.){auto& hero=match->battle.heroes.hero(seat);auto& pos=*hero.frame.position.get();pos.x=x;pos.y=y;pos.vx=pos.vy=0.;}
    double hero_x(Seat seat){return match->battle.heroes.hero(seat).frame.position.get()->x;}
};
template<class F> J scenario(const std::string& id,F run){
    J row={{"id",id}};
    try{row.update(run());row["passed"]=true;}
    catch(const std::exception& e){row["passed"]=false;row["error"]=e.what();}
    return row;
}


InputField<std::string> sval(const std::string& s){InputField<std::string> f;f.state=InputFieldState::value;f.value=s;return f;}
InputField<double> dval(double v){InputField<double> f;f.state=InputFieldState::value;f.value=v;return f;}
std::string deploy(Fixture& f,Seat seat,const std::string& card,double x,double y,int64_t facing=-1){
    auto& m=*f.match;const auto i=seat_index(seat);m.battle.heroes.players[i]->cooldowns.clear();m.room.players[i].test_zero_cooldown=true;
    m.resources.accounts[i].balance=99999.;
    NativeCommand c{NativeCommandKind::deploy};c.card=sval(card);c.x=dval(x);c.y=dval(y);
    c.facing.state=InputFieldState::value;c.facing.value=facing;c.grave.state=InputFieldState::null;
    return f.match->native_commands.apply(seat,c);
}

J catalog(){
    J rows=J::array();
    rows.push_back(scenario("cold.numbers",[](){
        Fixture f(decks({"plant:三叶草"},{"zombie:脑光墓碑","zombie:倭瓜僵尸"}));auto& m=*f.match;J out;
        near(m.catalog.resolve("plant:三叶草",{},{},false).cost,50.,"三叶草 cost");
        near(m.catalog.resolve("zombie:倭瓜僵尸",{},{},false).cost,75.,"倭瓜僵尸 cost");
        near(m.catalog.resolve("zombie:克苏鲁之仆",{},{},false).cooldown,32.,"servant cooldown");
        for(const char* k:{"zombie:成长脑光墓碑","zombie:水上成长脑光墓碑"}) {
            const auto grave=m.catalog.resolve(k,{},{},false);
            near(grave.hp.get(),100.,std::string(k)+" hp");
            near(grave.mature_hp.get(),200.,std::string(k)+" mature hp");
            const V card=rd(pm_catalog::CARDS,V(k));
            near(rd(card,V("mature_hp")).num(),200.,std::string(k)+" V mature hp");
        }
        for(const char* k:{"plant:三叶草","zombie:倭瓜僵尸","zombie:克苏鲁之仆"}){const V c=rd(pm_catalog::CARDS,V(k));out[k]={rd(c,V("cost")).num(),rd(c,V("cooldown")).num()};}
        near(out["plant:三叶草"][0].get<double>(),50.,"V 三叶草");near(out["zombie:倭瓜僵尸"][0].get<double>(),75.,"V 倭瓜");near(out["zombie:克苏鲁之仆"][1].get<double>(),32.,"V servant cd");
        const std::string thief=py_str(rd(rd(pm_catalog::CARDS,V("zsecret:空输")),V("description")));expect(thief.find("75提高到100")!=std::string::npos,"空输 text");
        const std::string rally=py_str(rd(rd(pm_catalog::CARDS,V("zsecret:汇流")),V("description")));expect(rally.find("25 脑光")!=std::string::npos,"汇流 text");
        return out;
    }));
    rows.push_back(scenario("deployed.grave_and_cart_hp",[](){
        Fixture f(decks({"plant:向日葵"},{"zombie:成长脑光墓碑","zombie:投篮车僵尸"}));auto& m=*f.match;const double tile=f.tile();
        f.hero_at(Seat::zombie,1512.);J out;
        out["grave_error"]=deploy(f,Seat::zombie,"zombie:成长脑光墓碑",1512.+3.*tile,960.-tile*.5,-1);
        std::string grave;double ghp=0.;for(const auto& e:m.battle.native_objects.entries())if(const auto* u=std::get_if<ZombieRef>(&e.object))if((*u)->protection.grave){grave=e.key;ghp=(*u)->body.hp;}
        near(ghp,100.,"成长脑光墓碑 deployed hp "+out.dump());
        auto& mm=*f.match;const auto i=seat_index(Seat::zombie);mm.battle.heroes.players[i]->cooldowns.clear();
        NativeCommand c{NativeCommandKind::deploy};c.card=sval("zombie:投篮车僵尸");c.x=dval(1512.+3.*tile);c.y=dval(960.-tile*.5);c.facing.state=InputFieldState::value;c.facing.value=-1;c.grave=sval(grave);
        out["cart_error"]=mm.native_commands.apply(Seat::zombie,c);
        double chp=0.;for(const auto& t:*m.battle.targets)if(t.unit&&t.unit->body.kind=="投篮车僵尸")chp=t.unit->body.hp;
        near(chp,225.,"投篮车 deployed hp "+out.dump());out["grave_hp"]=ghp;out["cart_hp"]=chp;return out;
    }));
    return rows;
}
J heroes(){
    J rows=J::array();
    rows.push_back(scenario("servant.contact_knocks_dave_down",[](){
        Fixture f(decks({"plant:向日葵"},{"zombie:脑光墓碑","zombie:克苏鲁之仆"}));auto& m=*f.match;const double tile=f.tile();
        f.hero_at(Seat::zombie,9000.);f.hero_at(Seat::plant,1512.);auto& hero=m.battle.heroes.hero(Seat::plant);hero.frame.hp.get()=40.;
        deploy(f,Seat::zombie,"zombie:克苏鲁之仆",1512.+3.*tile,900.);double downs=0.;const double hp0=hero.frame.hp.get();
        for(int i=0;i<600;++i){f.run(1);f.hero_at(Seat::plant,1512.);downs=std::max(downs,hero.frame.down.or_missing(0.));}
        J out={{"hp_lost",hp0-hero.frame.hp.get()},{"max_down",downs}};
        expect(hp0-hero.frame.hp.get()>0.,"servant never hurt the plant Dave "+out.dump());
        expect(downs>0.,"plant Dave did not enter knockdown "+out.dump());return out;
    }));
    rows.push_back(scenario("croton.zombie_dave",[](){
        Fixture f(decks({"plant:巴豆"},{"zombie:脑光墓碑","zombie:普通僵尸"}));auto& m=*f.match;const double tile=f.tile();
        f.hero_at(Seat::plant,1512.-20.*tile);f.hero_at(Seat::zombie,1512.+3.*tile);auto& hero=m.battle.heroes.hero(Seat::zombie);
        m.commands.shared=PathMode::attack_plants;
        f.plant("巴豆",1512.,1.);auto z=f.zombie("普通僵尸",1512.+tile*.6,-1.);z->native.move_speed.set(.001);
        const double hp0=hero.frame.hp.get();double stun=0.;int poison=0;
        for(int i=0;i<300&&!m.pvp75.gas_hero_hits;++i){f.run(1);f.hero_at(Seat::zombie,1512.+3.*tile);}
        stun=hero.stun.or_missing(0.);if(hero.poison.present()&&!hero.poison.is_null()&&hero.poison.get())poison=int(hero.poison.get()->level.or_missing(0));
        J out={{"croton_triggers",m.pvp75.croton_triggers},{"gas_hits",m.pvp75.gas_hits},{"gas_hero_hits",m.pvp75.gas_hero_hits},{"stun",stun},{"poison",poison},{"hp_lost_immediate",hp0-hero.frame.hp.get()}};
        expect(m.pvp75.gas_hero_hits==1,"gas did not reach the zombie Dave "+out.dump());
        expect(stun>700.,"no 3 s stun "+out.dump());expect(poison==1,"no level-1 poison "+out.dump());
        expect(hp0-hero.frame.hp.get()<1e-9,"gas dealt direct damage "+out.dump());
        f.run(1000);out["hits_after"]=m.pvp75.gas_hero_hits;expect(m.pvp75.gas_hero_hits==1,"one cloud hit the Dave twice "+out.dump());
        return out;
    }));
    rows.push_back(scenario("bloom.ranked_cold",[](){
        J d=decks({"plant:黄金蓓蕾"},{"zombie:脑光墓碑"});
        Fixture f(d,J{{"rules",{{"local_test_mode",false},{"ranked",true}}}});auto& m=*f.match;const double tile=f.tile();
        f.hero_at(Seat::plant,1512.);const auto e=deploy(f,Seat::plant,"plant:黄金蓓蕾",1512.+8.*tile+tile*.5,960.-tile*.5,1);
        auto& hero=m.battle.heroes.hero(Seat::plant);const double left=hero.cold_until.or_missing(0.)-double(m.battle.heroes.tick);
        J out={{"deploy",e},{"cold_ticks",left},{"collect_lock",m.room.players[seat_index(Seat::plant)].collect_locked_until-m.battle.heroes.time}};
        expect(e.empty(),"bloom deploy "+out.dump());expect(left>2990.&&left<=3000.,"no 12 s cold "+out.dump());
        Fixture g(d);auto& n=*g.match;g.hero_at(Seat::plant,1512.);deploy(g,Seat::plant,"plant:黄金蓓蕾",1512.+8.*tile+tile*.5,960.-tile*.5,1);
        out["unranked_cold"]=n.battle.heroes.hero(Seat::plant).cold_until.or_missing(0.)-double(n.battle.heroes.tick);
        expect(out["unranked_cold"].get<double>()<=0.,"unranked bloom chilled "+out.dump());return out;
    }));
    rows.push_back(scenario("wind.hop_step",[](){
        Fixture f(decks({"plant:三叶草"},{"zombie:脑光墓碑"}));auto& m=*f.match;const double tile=f.tile();
        // One-tile step at column 36 (ground is row 20): the zombie Dave stands at column 33.
        m.battle.terrain.native_at(19,36).block.set("土");m.sync_terrain();
        f.hero_at(Seat::plant,9000.);f.hero_at(Seat::zombie,33.5*tile);f.run(50);
        f.plant("三叶草",31.5*tile,1.);double best=0.;
        for(int i=0;i<500;++i){f.run(1);best=std::max(best,m.battle.heroes.hero(Seat::zombie).frame.position.get()->x);}
        J out={{"hops",m.wind.wind_hops},{"max_x",best/tile}};
        expect(m.wind.wind_hops>0,"no hop "+out.dump());expect(best>37.*tile,"Dave did not get over the step "+out.dump());
        return out;
    }));
    return rows;
}
J zombies(){
    J rows=J::array();
    auto carts=[](const char* key,bool kun){
        J zs={"zombie:脑光墓碑",std::string("zombie:")+key};if(kun)zs.push_back("zsecret:坤坤");
        Fixture f(decks({"plant:坚果"},zs));auto& m=*f.match;const double tile=f.tile();
        f.hero_at(Seat::zombie,1200.+30.*tile);f.hero_at(Seat::plant,1200.-3.*tile);m.commands.shared=PathMode::attack_plants;
        for(int i=0;i<3;++i)f.plant("坚果",1200.+double(i)*tile,1.,960.);
        auto z=f.zombie(key,1200.+10.*tile,-1.);z->body.hp=1e5;
        J timeline=J::array();
        for(int s=0;s<30;++s){f.run(250);
            const double thrown=std::string(key)=="投篮车僵尸"?48.-z->native.basketball_total.or_missing(48.):double(std::count_if(m.battle.targets->begin(),m.battle.targets->end(),[](const auto& t){return t.unit&&t.unit->body.kind=="小鬼僵尸";}));
            timeline.push_back(thrown);
            if(s==20)m.battle.protection.amount(z->damage_target(),1.);  // a hit restarts the clock
        }
        return timeline;
    };
    rows.push_back(scenario("cart.idle_stop",[&](){
        const J basket=carts("投篮车僵尸",false),kun=carts("投篮车僵尸",true),cannon=carts("小鬼炮",false);
        J out={{"basket",basket},{"kunkun",kun},{"cannon",cannon}};
        expect(basket[11]==basket[19],"basket cart kept throwing while idle "+out.dump());
        expect(basket[29].get<double>()>basket[20].get<double>(),"basket cart did not resume after a hit "+out.dump());
        expect(kun[19].get<double>()>kun[11].get<double>(),"坤坤 cart stopped while idle "+out.dump());
        expect(cannon[17]==cannon[19],"cannon kept firing while idle "+out.dump());
        expect(cannon[29].get<double>()>cannon[20].get<double>(),"cannon did not resume after a hit "+out.dump());
        return out;
    }));
    auto chili=[](bool frozen){
        Fixture f(decks({"plant:向日葵"},{"zombie:脑光墓碑","zombie:辣椒僵尸"}));auto& m=*f.match;const double tile=f.tile();
        f.hero_at(Seat::plant,1512.-20.*tile);f.hero_at(Seat::zombie,9000.);
        auto z=f.zombie("辣椒僵尸",1512.+3.*tile,-1.);z->native.move_speed.set(.001);f.run(5);
        if(frozen)z->body.ice.set(600.);
        z->body.hp=0.;
        int fires=0;for(int i=0;i<60;++i){f.run(1);for(const auto& e:*m.battle.runtime.entities.list())if(e->kind=="火")++fires;}
        return J{{"fires",fires},{"exploded_flag",z->patch.chili_exploded.or_missing(false)}};
    };
    rows.push_back(scenario("chili.no_burst_when_chilled",[&](){
        const J plain=chili(false),cold=chili(true);J out={{"plain",plain},{"slowed",cold}};
        expect(plain["fires"].get<int>()>0,"plain chili zombie did not burst (test inconclusive) "+out.dump());
        expect(cold["fires"].get<int>()==0,"slowed chili zombie burst "+out.dump());return out;
    }));
    rows.push_back(scenario("guard.base_defense",[](){
        J out;for(bool secret:{false,true}){
            J zs={"zombie:脑光墓碑","zombie:盾卫僵尸"};if(secret)zs.push_back("zsecret:守卫");
            Fixture f(decks({"plant:向日葵"},zs));auto z=f.zombie("盾卫僵尸",1800.,-1.);z->native.move_speed.set(.001);f.run(5);
            const double base=z->body.defense.get();z->body.hp-=1.;double up=0.;for(int i=0;i<400&&up==0.;++i){f.run(1);if(z->pvp75.guard==GuardPhase::guarding)up=z->body.defense.get();}
            out[secret?"guard":"plain"]={{"base",base},{"raised",up}};
        }
        near(out["plain"]["base"],12.,"plain base "+out.dump());near(out["plain"]["raised"],60.,"plain raised "+out.dump());
        near(out["guard"]["base"],24.,"守卫 base "+out.dump());near(out["guard"]["raised"],600.,"守卫 raised "+out.dump());return out;
    }));
    rows.push_back(scenario("nuclear.charmed_doom_zombie",[](){
        auto blast=[](bool nuclear){
            J plants={"plant:毁灭菇"};if(nuclear)plants.push_back("secret:核平");
            Fixture f(decks(plants,{"zombie:脑光墓碑","zombie:毁灭菇僵尸","zombie:巨人僵尸"}));auto& m=*f.match;const double tile=f.tile();
            f.hero_at(Seat::plant,1512.-30.*tile);f.hero_at(Seat::zombie,9000.);
            auto doom=f.zombie("毁灭菇僵尸",1512.,1.);doom->source.charmed.set(200.);doom->native.move_speed.set(.001);
            auto giant=f.zombie("巨人僵尸",1512.+2.*tile,-1.);giant->native.move_speed.set(.001);giant->body.hp=5000.;f.run(3);
            doom->body.hp=0.;f.run(40);
            return J{{"charmed",doom->source.charmed.present()},{"giant_hp",giant->body.hp},{"giant_ash",giant->body.ash.present()}};
        };
        const J plain=blast(false),nuke=blast(true);J out={{"plain",plain},{"nuclear",nuke}};
        expect(nuke["charmed"].get<bool>(),"doom zombie not charmed "+out.dump());
        expect(!plain["giant_ash"].get<bool>(),"giant ashed without 核平 (test inconclusive) "+out.dump());
        expect(nuke["giant_ash"].get<bool>(),"核平 did not reach the charmed doom zombie blast "+out.dump());return out;
    }));
    return rows;
}
J plants(){
    J rows=J::array();
    rows.push_back(scenario("dense.laser_and_cob_alone",[](){
        Fixture f(decks({"plant:激光豆","plant:玉米加农炮","plant:豌豆射手","secret:密植"},{"zombie:脑光墓碑"}));const double tile=f.tile();
        f.hero_at(Seat::plant,1512.);J out;const double y=960.-tile*.5;
        const auto cell=[&](int c){return 1512.+double(c)*tile+tile*.5;};
        out["pea_pea"]={deploy(f,Seat::plant,"plant:豌豆射手",cell(2),y,1),deploy(f,Seat::plant,"plant:豌豆射手",cell(2),y,1)};
        out["laser_on_pea"]=deploy(f,Seat::plant,"plant:激光豆",cell(2),y,1);
        out["laser_alone"]=deploy(f,Seat::plant,"plant:激光豆",cell(4),y,1);
        out["pea_on_laser"]=deploy(f,Seat::plant,"plant:豌豆射手",cell(4),y,1);
        out["cob_on_pea"]=deploy(f,Seat::plant,"plant:玉米加农炮",cell(2),y,1);
        expect(out["pea_pea"][0]==""&&out["pea_pea"][1]=="","密植 itself broken "+out.dump());
        expect(out["laser_alone"]=="","laser on an empty cell "+out.dump());
        for(const char* k:{"laser_on_pea","pea_on_laser","cob_on_pea"})expect(!out[k].get<std::string>().empty(),std::string(k)+" accepted "+out.dump());
        return out;
    }));
    rows.push_back(scenario("testmode.clear_restores_terrain",[](){
        Fixture f(decks({"plant:花盆","plant:水盆","plant:豌豆射手"},{"zombie:脑光墓碑"}),J{{"rules",{{"local_test_mode",true}}}});auto& m=*f.match;const double tile=f.tile();
        f.hero_at(Seat::plant,1512.);J out;
        out["pot"]=deploy(f,Seat::plant,"plant:花盆",1512.+2.*tile+tile*.5,960.-tile*.5,1);
        out["basin"]=deploy(f,Seat::plant,"plant:水盆",1512.+4.*tile+tile*.5,960.-tile*.5,1);
        const int base=int(std::floor(1512./tile));
        const auto block=[&](int row,int c){const auto& b=m.battle.terrain.native_at(row,base+c).block;return b.present()&&!b.is_null()?b.get():std::string("?");};
        out["before"]={block(19,2),block(20,2),block(19,4),block(20,4)};
        const auto e=m.test_command(Seat::plant,J{{"seq",9},{"op","clear"},{"what","plants"}});out["clear"]=e;
        out["after"]={block(19,2),block(20,2),block(19,4),block(20,4)};
        out["plants_left"]=m.battle.plant_roster->size();
        expect(e.empty(),"clear failed "+out.dump());
        for(const auto& b:out["after"])expect(b!="花盆块"&&b!="水","terrain left behind "+out.dump());
        return out;
    }));
    return rows;
}
J probe(){
    J rows=J::array();
    rows.push_back(scenario("explore.servant_hp",[](){
        Fixture f(decks({"plant:豌豆射手"},{"zombie:脑光墓碑","zombie:克苏鲁之仆"}));auto& m=*f.match;const double tile=f.tile();
        f.hero_at(Seat::plant,1512.-20.*tile);f.hero_at(Seat::zombie,9000.);
        m.resources.accounts[seat_index(Seat::zombie)].balance=9999.;
        const auto before=m.battle.targets->size();const auto e=deploy(f,Seat::zombie,"zombie:克苏鲁之仆",1512.+6.*tile,800.);
        J out={{"deploy_error",e}};
        ZombieRef s;for(const auto& t:*m.battle.targets)if(t.unit&&t.unit->terraria)s=t.unit;
        if(s){out["hp"]=s->body.hp;out["max_hp"]=s->max_hp.or_missing(-1.);out["defense"]=s->body.defense.or_missing(-1.);
            // Pea fire at it: hp after each second.
            f.plant("豌豆射手",1512.+2.*tile,1.,800.+tile);J trace=J::array();for(int i=0;i<10&&s->body.hp>0.;++i){f.run(250);trace.push_back(s->body.hp);}out["trace"]=trace;}
        (void)before;return out;
    }));
    rows.push_back(scenario("explore.charmed_heads",[](){
        Fixture f(decks({"plant:豌豆射手","plant:大喷菇","secret:雷霆"},{"zombie:脑光墓碑","zombie:豌豆僵尸","zombie:大喷菇僵尸"}));auto& m=*f.match;
        m.canvas.patch_plant_zombie_assets();J out;
        // Raw RGBA dumps (w h then bytes) of the head sprites for a visual check.
        for(const auto& [name,s]:m.battle.runtime.presentation.atlas){
            const bool body=name.rfind("普通僵尸-首",0)==0||name.rfind("豌豆僵尸-身",0)==0;
            if(!body&&name.find("植头")==std::string::npos&&name.find("thunder_head")==std::string::npos)continue;
            if(!body&&name.find("豌豆僵尸")==std::string::npos&&name.find("大喷菇僵尸")==std::string::npos&&name.find("thunder")==std::string::npos)continue;
            std::ofstream o(std::filesystem::path("test_results/pvp76/r3/heads")/u8p(name+".rgba"),std::ios::binary);
            const int32_t w=s.width,h=s.height;o.write(reinterpret_cast<const char*>(&w),4);o.write(reinterpret_cast<const char*>(&h),4);
            for(const auto& px:s.pixels){const unsigned char c[4]={px[0],px[1],px[2],px[3]};o.write(reinterpret_cast<const char*>(c),4);}
        }
        for(const auto& [key,image]:m.canvas.atlas.atlas){
            if(key.find("-植头")==std::string::npos&&key.find("thunder_head")==std::string::npos)continue;
            if(key.find("豌豆僵尸")==std::string::npos&&key.find("大喷菇僵尸")==std::string::npos&&key.find("thunder")==std::string::npos)continue;
            out[key]=m.canvas.describe(image).dump(-1,' ',false,nlohmann::json::error_handler_t::replace).substr(0,600);
        }
        return out;
    }));
    rows.push_back(scenario("explore.pea_damage",[](){
        J out;
        for(const char* name:{"普通僵尸","克苏鲁之仆"}){
            Fixture f(decks({"plant:豌豆射手"},{"zombie:脑光墓碑","zombie:普通僵尸","zombie:克苏鲁之仆"}));auto& m=*f.match;const double tile=f.tile();
            f.hero_at(Seat::plant,1512.-20.*tile);f.hero_at(Seat::zombie,9000.);
            ZombieRef z;
            if(std::string(name)=="普通僵尸"){z=f.zombie(name,1512.+6.*tile,-1.);z->native.move_speed.set(.001);}
            else{deploy(f,Seat::zombie,"zombie:克苏鲁之仆",1512.+6.*tile,900.);for(const auto& t:*m.battle.targets)if(t.unit&&t.unit->terraria)z=t.unit;z->body.hp=1000.;z->max_hp.set(1000.);}
            const double hp0=z->body.hp;f.plant("豌豆射手",1512.,1.);J hits=J::array();double last=hp0;
            J fired=J::array();size_t peas=0;
            for(int i=0;i<3000&&hits.size()<6;++i){const auto before=m.battle.heroes.tick;
                while(m.battle.heroes.tick==before)m.scheduler.step();
                size_t n=0;for(const auto& e:*m.battle.runtime.entities.list())if(e->kind=="豌豆")++n;
                if(n>peas)fired.push_back(m.battle.heroes.tick);peas=n;
                if(z->body.hp<last-1e-9){hits.push_back({last-z->body.hp,m.battle.heroes.tick});last=z->body.hp;}}
            out[std::string(name)+"_fired"]=fired;
            J shots=J::array();for(const auto& e:*m.battle.runtime.entities.list())shots.push_back(e->kind);out[std::string(name)+"_entities"]=shots;
            out[name]={{"start_hp",hp0},{"per_hit",hits}};
        }
        return out;
    }));
    rows.push_back(scenario("explore.pea_damage_deployed",[](){
        // Both sides through the real deploy command: peashooter by the plant Dave, the zombie from a grave.
        Fixture f(decks({"plant:豌豆射手","plant:向日葵"},{"zombie:脑光墓碑","zombie:普通僵尸"}));auto& m=*f.match;const double tile=f.tile();
        f.hero_at(Seat::plant,1512.);f.hero_at(Seat::zombie,1512.+10.*tile);
        J out;out["plant_deploy"]=deploy(f,Seat::plant,"plant:豌豆射手",1512.+tile*.5,960.-tile*.5,1);
        out["grave_deploy"]=deploy(f,Seat::zombie,"zombie:脑光墓碑",1512.+9.*tile,960.-tile*.5,-1);
        std::string grave;for(const auto& e:m.battle.native_objects.entries())if(const auto* u=std::get_if<ZombieRef>(&e.object))if((*u)->protection.grave)grave=e.key;
        out["grave"]=grave;
        {auto& mm=*f.match;const auto i=seat_index(Seat::zombie);mm.battle.heroes.players[i]->cooldowns.clear();mm.room.players[i].test_zero_cooldown=true;mm.resources.accounts[i].balance=99999.;
         NativeCommand c{NativeCommandKind::deploy};c.card=sval("zombie:普通僵尸");c.x=dval(1512.+9.*tile);c.y=dval(960.-tile*.5);c.facing.state=InputFieldState::value;c.facing.value=-1;c.grave=sval(grave);
         out["zombie_deploy"]=mm.native_commands.apply(Seat::zombie,c);}
        ZombieRef z;for(const auto& t:*m.battle.targets)if(t.unit&&!t.unit->protection.grave&&!t.unit->protection.hero&&t.unit->body.kind.find("普通")!=std::string::npos)z=t.unit;
        expect(bool(z),"no deployed zombie "+out.dump());
        PlantRef pea;for(const auto& p:*m.battle.plant_roster)if(p->kind=="豌豆射手")pea=p;expect(bool(pea),"no deployed peashooter "+out.dump());
        out["zombie_hp"]=z->body.hp;out["zombie_kind"]=z->body.kind;J hits=J::array();double last=z->body.hp;
        for(int i=0;i<4000&&hits.size()<12&&z->body.hp>0.;++i){f.run(1);if(z->body.hp<last-1e-9){hits.push_back({last-z->body.hp,m.battle.heroes.tick});last=z->body.hp;}}
        out["per_hit"]=hits;out["mode"]=m.battle.heroes.globals.mode.or_missing("?");return out;
    }));
    return rows;
}
}
int main(int argc,char** argv){
    using namespace pvz;
    if(argc!=2)return 2;
    auto out=std::filesystem::absolute(u8p(argv[1]));std::filesystem::create_directories(out);
    env_set_u8("PVP_USERDATA",p8(out/"userdata"));env_set_u8("SDL_VIDEODRIVER","dummy");env_set_u8("SDL_AUDIODRIVER","dummy");
    SDL_SetMainReady();gil::init();data::set_data_dir("extract/data");pg::install_pygame();init_pvp_modules();
    J result={{"checks",J::array()},{"failures",0}};int failures=0;
    const char* only=std::getenv("PVP76R3_AUDIT_CASE");
    for(auto [name,fn]:std::vector<std::pair<std::string,J(*)()>>{{"catalog",catalog},{"heroes",heroes},{"zombies",zombies},{"plants",plants},{"probe",probe}}){
        if(only&&name!=only)continue;
        std::cerr<<"RUN "<<name<<std::endl;J check={{"name",name}};try{
            auto evidence=fn();bool passed=true;
            if(evidence.is_array())for(const auto& row:evidence)if(row.is_object()&&!row.value("passed",true))passed=false;
            check["evidence"]=std::move(evidence);check["passed"]=passed;if(!passed)++failures;
        }catch(const std::exception& e){check["error"]=e.what();check["passed"]=false;++failures;}
        result["checks"].push_back(check);std::cerr<<check.dump()<<std::endl;
    }
    result["failures"]=failures;std::ofstream(out/"results.json")<<result.dump(2);return failures?1:0;
}
