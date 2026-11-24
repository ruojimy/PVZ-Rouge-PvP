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
#include "sim/pvp/gen/pm_maps.h"
#include "sim/pvp/gen/pm_native_bridge.h"
#include "sim/pvp/gen/pm_team_maps.h"
#include "core/fsutil.h"
#include "sim/pvp/hand/graphics.h"
#include "core/gil.h"
#include "pg/pg.h"
#include "ui/gen/pm_app.h"
#include "ui/hand/solo77.h"
#include "ui/hand/test_mode74.h"
#include "ui/hand/texture74_internal.h"
#include "ui/gen/pm_ui_data.h"
#include "sim/mapgen.h"
#include "sim/pvp/hand/solo_campaign77.h"
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

#include "pvp77_waves.inc"
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
J solo77_checks(){
    J rows=J::array();
    rows.push_back(scenario("catalog.current_cards",[](){
        pm_catalog::init();
        const auto& packaged=data::module("catalog").at("CARDS");
        J differences=J::array();
        for(const auto& [key,record]:packaged.items()){
            const V card=py::m_get(pm_catalog::CARDS,V(key));
            if(card.is_none()){differences.push_back(key+" missing");continue;}
            for(const char* field:{"name","hp","native_hp","description","native_description"}){
                const auto live=J::parse(dump(py::m_get(card,V(field))));
                if(live!=record.value(field,J(nullptr)))differences.push_back(key+" "+field);
            }
        }
        const auto text=[](const char* id,bool full){
            return py_str(pm_catalog::f_describe(Args({V(id)},{{SY("detailed"),V(full)}})));
        };
        const auto brief=text("plant:金盏花",false),detail=text("plant:金盏花",true);
        expect(brief.find("生命6")!=std::string::npos&&detail.find("生命 6")!=std::string::npos,"marigold almanac");
        Fixture f(decks({"plant:金盏花"},{"zombie:脑光墓碑","zombie:普通僵尸"}));
        const auto plant=f.plant("金盏花");near(plant->hp.get(),6,"PvP marigold HP");
        expect(text("zsecret:空输",false).find("100脑光")!=std::string::npos&&text("zsecret:船锚",false).find("钩中")!=std::string::npos,"compact secret rules");
        expect(text("plant:石块",false).find("生命180")==std::string::npos&&text("plant:模仿者",false).find("生命180")==std::string::npos,"template HP leaked");
        expect(differences.empty(),"packaged cards differ from executable: "+differences.dump());
        return J{{"cards",packaged.size()},{"fields",5},{"brief",brief},{"marigold_spawn_hp",plant->hp.get()}};
    }));
    rows.push_back(scenario("captain.hurt_window",[](){
        Fixture f(decks({"plant:坚果"},{"zombie:脑光墓碑","zombie:海盗船长"}));auto& m=*f.match;
        auto z=f.zombie("海盗船长");auto& clock=z->protection.reaper_hurt;
        f.run(10);expect(clock.present(),"captain has no activity clock");
        clock.set(double(m.battle.heroes.tick)-6250.);
        const auto before=z->content.summon_clock.get();f.run(200);
        near(z->content.summon_clock.get(),before,"idle clock");
        m.battle.protection.amount(z->damage_target(),0.);f.run(12);near(z->content.summon_clock.get(),before,"zero damage");
        m.battle.protection.amount(z->damage_target(),1.);f.run(40);
        expect(z->content.summon_clock.get()>before,"captain failed to resume");
        return J{{"idle",before},{"resumed",z->content.summon_clock.get()}};
    }));
    rows.push_back(scenario("spring.air_and_bungee",[](){
        J results=J::object();
        for(const char* key:{"海盗鹦鹉","乌鸦","气球僵尸","飞贼僵尸","克苏鲁之仆","普通僵尸"}){
            Fixture f(decks({"plant:弹簧草"},{"zombie:脑光墓碑"}));auto& m=*f.match;
            f.hero_at(Seat::zombie,3500.);auto p=f.plant("弹簧草",1512.,1.);
            auto z=f.zombie(key,1560.,-1.);z->body.hp=1000.;m.sync_public();
            expect(m.mortars.spring(p),"spring did not strike "+std::string(key));
            if(z->body.kind=="飞贼僵尸")expect(z->native.leaving.present(),"bungee not retracted");
            else if(std::string(key)!="普通僵尸")expect(z->body.blown.or_missing(false),"ordinary impulse "+std::string(key));
            else expect(!z->body.blown.or_missing(false),"ground unit wrongly classed air");
            results[key]={{"vx",z->body.motion.get().vx},{"leaving",z->native.leaving.present()}};
        }
        Fixture f(decks({"plant:三叶草"},{"zombie:脑光墓碑","zombie:飞贼僵尸"}));auto& m=*f.match;
        auto z=f.zombie("飞贼僵尸",1560.,-1.);f.plant("三叶草",1512.,1.);f.run(12);
        expect(z->native.leaving.present(),"blover failed to retract bungee");
        return results;
    }));
    for(const auto mode:{"lottery","izombie"})rows.push_back(scenario(mode,[=](){
        const bool iz=std::string(mode)=="izombie";
        Fixture f(decks(iz?J::array():J({"plant:模仿者","plant:向日葵"}),iz?J({"zombie:普通僵尸"}):J({"zombie:脑光墓碑","zombie:普通僵尸"})),J{{"rules",{{"pvp77_mode",mode},{"pvp77_stage",1},{"pvp77_plants",{"plant:豌豆射手"}},{"pvp77_zombies",{"zombie:普通僵尸"}}}}});
        auto& m=*f.match;expect(m.battle.protection.until==0,"early protection");
        if(m.battle.solo.izombie()){
            auto& solo=m.battle.solo;expect(solo.graves.size()==3&&solo.objectives.size()==3,"opening board "+std::to_string(solo.objectives.size()));
            near(m.resources.accounts[seat_index(Seat::zombie)].balance,150.,"opening brain");
            const auto objectives=solo.objectives;
            auto shooter=f.zombie("豌豆僵尸",1300.);
            const auto source=source_ref(shooter);
            for(const auto& p:objectives){
                const auto targets=m.queries.enemies(source);
                expect(std::find(targets.begin(),targets.end(),ContentTarget(p))!=targets.end(),"brain missing from ranged target list");
                m.target_dispatch.damage(source,ContentTarget(p),1000.);
            }
            m.scheduler.step();expect(m.room.result&&m.room.result->winner==RoomWinner::zombie,"objective victory");
            near(m.resources.coins,30.,"objective coins");
            return J{{"graves",solo.graves.size()},{"brains",solo.brains},{"coins",m.resources.coins}};
        }
        auto error=deploy(f,Seat::plant,"plant:模仿者",1512.,936.);expect(error.empty(),error);
        auto drawn=m.battle.plant_roster->back();expect(drawn->kind=="模仿者"&&drawn->copy_card.present(),"lottery did not draw at planting");
        const auto picked=drawn->copy_card.get();
        const auto& h=*m.battle.heroes.players[seat_index(Seat::plant)];
        const auto it=std::find_if(h.cooldowns.begin(),h.cooldowns.end(),[](const auto& p){return p.first=="plant:模仿者";});
        expect(it!=h.cooldowns.end(),"copy cd missing");near(it->second-m.battle.heroes.time,2.,"copy cd");
        f.run(305);expect(drawn->transform_succeeded.or_missing(false),"random transformation failed");
        expect(deploy(f,Seat::plant,"plant:向日葵",1595.,936.).empty(),"first single-use deployment");
        expect(!deploy(f,Seat::plant,"plant:向日葵",1704.,936.).empty(),"cooldown reset reused a spent card");
        return J{{"cooldown",2},{"draw",picked},{"plants",m.battle.plant_roster->size()}};
    }));
    rows.push_back(scenario("campaign.complete_saves",[](){
        solo77::Pools pool;
        for(int i=0;i<55;++i){
            auto plant="plant:测"+std::to_string(i),zombie="zombie:测"+std::to_string(i);
            pool.plants.push_back({plant,{},false,50});pool.zombies.push_back({zombie,{},false,50});pool.defenders.push_back(plant);
        }
        pool.zombies.push_back({"zombie:梯子僵尸",{},false,150});
        J report=J::object();
        for(const char* id:{"lottery","izombie"}){
            solo77::Campaign c;c.start(id,2323,pool);J stages=J::array();
            for(int i=1;i<=(c.zombie()?19:24);++i){
                expect(c.stage==i,"stage sequence");stages.push_back(c.map);
                const auto match=std::to_string(i);c.finish(pool,match,true,30,0);const auto coins=c.coins;
                c.finish(pool,match,true,30,0);expect(coins==c.coins,"settled twice");
                if(c.complete)break;
                if(c.zombie()&&i==1)expect(c.rewards.front()=="zombie:梯子僵尸","first zombie reward");
                nlohmann::json saved=c;c=saved.get<solo77::Campaign>();c.reward(pool,c.rewards.at(0));
            }
            expect(c.complete,"not completed");if(!c.zombie())for(size_t day=0;day<12;++day)expect(stages[day]==stages[day+12],"map rotation");
            report[id]={{"stages",stages},{"coins",c.coins}};
        }return report;
    }));
    rows.push_back(scenario("izombie.boss_bites",[](){
        Fixture f(decks(J::array(),{"zombie:普通僵尸"}),J{{"rules",{{"pvp77_mode","izombie"},{"pvp77_stage",19}}}});auto& m=*f.match;auto& s=m.battle.solo;
        expect(s.objectives.size()==1&&s.objectives[0]->kind=="黄金脑子","missing first golden brain");
        struct Payout {const char* card;int expected;bool mature;};
        for(auto row:std::vector<Payout>{{"向日葵",90,false},{"双子向日葵",150,false},{"阳光菇",50,false},{"阳光菇",75,true},{"黄金蓓蕾",200,false},{"金盏花",0,false}}){
            auto p=f.plant(row.card);if(row.mature)p->grown.set(200.);
            auto& account=m.resources.accounts[seat_index(Seat::zombie)];const double before=account.balance;
            p->hp.set(6.);
            if(p->kind=="黄金蓓蕾")expect(p->sleep.present(),"bloom was awake");
            for(int hp=6;hp>0;--hp){
                p->hp.set(hp-1.);s.plant_bitten(p,hp);settle_solo_board(m);
                if(p->kind=="黄金蓓蕾")expect(p->sleep.present(),"bloom woke on bite");
            }
            near(account.balance-before,row.expected,"bite income "+p->kind);
        }
        auto natural=f.plant("金盏花");const int natural_hp=int(natural->hp.get());
        expect(natural_hp==6,"unexpected PvP marigold health "+std::to_string(natural_hp));
        for(int hp=natural_hp;hp>0;--hp){natural->hp.set(hp-1.);s.plant_bitten(natural,hp);settle_solo_board(m);}
        auto bolt=f.plant("黄金蓓蕾");const auto balance=m.resources.accounts[seat_index(Seat::zombie)].balance;bolt->hp.set(0.);settle_solo_board(m);
        near(m.resources.accounts[seat_index(Seat::zombie)].balance,balance,"remote bloom");
        for(int n=0;n<3;++n){expect(s.objectives.size()==1,"missing replacement");s.objectives.front()->hp.set(0.);m.scheduler.step();if(n<2)m.scheduler.step();}
        expect(m.room.result&&m.room.result->winner==RoomWinner::zombie,"third gold brain did not finish");
        near(m.resources.coins,330.,"150 objective + 90 reference + 90 native marigold");
        return J{{"coins",m.resources.coins},{"reference_marigold",90},{"pvp_marigold",90},{"golden",s.brains}};
    }));
    rows.push_back(scenario("coop.expanded_secrets",[](){
        J deck={{"plant",{"plant:豌豆射手"}},{"plant2",{"plant:向日葵"}},{"zombie",{"zsecret:植物僵尸","zsecret:海陆空","zsecret:远离诱惑","zsecret:遗骸"}}};
        Fixture f(deck,{{"mode","coop"}});auto& m=*f.match;
        auto base=f.zombie("海盗船长",700.);const double base_hp=base->body.hp;
        m.zsecrets.scripted_roster={"zombie:普通僵尸","zombie:海盗船长","zombie:气球僵尸"};m.zsecrets.configure_locked();
        auto captain=f.zombie("海盗船长",800.);near(captain->body.hp,base_hp*1.5,"scripted land/sea/air");
        const auto full=f.zombie("豌豆僵尸",900.);const double full_hp=full->body.hp;
        auto pea=f.plant("豌豆射手",1500.);m.target_dispatch.damage(source_ref(full),ContentTarget(pea),1000.);
        f.run(20);ZombieRef converted;
        for(const auto& t:*m.battle.targets)if(t.unit&&t.unit->secret.converted.or_missing(false))converted=t.unit;
        expect(bool(converted),"scripted army did not convert killed peashooter");
        near(converted->max_hp.get(),full_hp*.5,"half health conversion");
        auto charmed=f.zombie("普通僵尸",1100.);charmed->source.charmed.set(true);m.zruntime.step(1./30.);
        expect(charmed->body.ice.or_missing(0.)>=100.,"charmed unit slow");
        auto remnant=m.spawn_remnant({1260.,960.});
        const auto amount=m.battle.protection.amount(remnant->damage_target(),remnant->body.hp+10.);
        expect(amount<remnant->body.hp&&remnant->protection.relic_until.or_missing(0.)>m.battle.heroes.tick,"relic grave immunity");
        const V old=pvp76r2::coop_zombie_secrets(V("migration77"),V(1),V(17),V(100));
        const V migrated=pvp76r2::coop_zombie_secrets(V("migration77"),V(1),V(17),V(17));
        expect(py_str(old)==py_str(migrated),"migration rerolled acquired secrets");
        const V all=pvp76r2::coop_zombie_secrets(V("migration77"),V(1),V(52),V(17));
        expect(pvp76r2::coop_secret_keys().size()==25,"whitelist count");
        for(const char* key:{"zsecret:植物僵尸","zsecret:海陆空","zsecret:远离诱惑","zsecret:遗骸"})expect(all.contains(V(key)),"schedule missing "+std::string(key));
        return J{{"whitelist",pvp76r2::coop_secret_keys().size()},{"eligible_draws",all.len()},{"converted_hp",converted->max_hp.get()},{"maritime_hp",captain->max_hp.get()}};
    }));
    rows.push_back(scenario("solo.producer_and_sleep",[](){
        J record;
        for(const char* mode:{"lottery","izombie"}){
            Fixture f(decks(std::string(mode)=="izombie"?J::array():J({"plant:向日葵"}),{"zombie:脑光墓碑","zombie:普通僵尸"}),{{"rules",{{"pvp77_mode",mode}}}});auto& m=*f.match;
            auto sun=f.plant("向日葵");static const std::string no_hand;
            for(int tick:{1,19999,20000,105001}){
                m.battle.heroes.tick=tick;
                const double hit=m.battle.protection.amount({sun->hp.get(),no_hand,sun->source,sun->protection},1.);
                near(hit,1.,std::string("producer damage at ")+std::to_string(tick));
            }
            if(m.battle.solo.izombie()){
                for(const char* name:{"寒冰辣椒","樱桃炸弹","毁灭菇","寒冰菇","火爆辣椒","三叶草","窝瓜","黄金蓓蕾","小喷菇","大喷菇","魅惑菇","幽灵辣椒"}){
                    auto p=f.plant(name);
                    const bool awake=std::string(name)=="小喷菇"||std::string(name)=="大喷菇"||std::string(name)=="魅惑菇"||std::string(name)=="幽灵辣椒";
                    expect(p->sleep.present()!=awake,std::string("sleep state: ")+name);
                    const double before=p->hp.get();p->hp.set(before-1.);m.battle.solo.plant_bitten(p,before);
                    expect(p->sleep.present()==(std::string(name)=="黄金蓓蕾"),std::string("first bite: ")+name);
                }
            }
            record[mode]="full producer damage";
        }
        return record;
    }));
    rows.push_back(scenario("wind.terrain_intervals",[](){
        Fixture f(decks({"plant:三叶草"},{"zombie:脑光墓碑"}));auto& m=*f.match;
        f.hero_at(Seat::zombie,1512.);const int col=int(1512./f.tile());auto& cell=m.battle.terrain.native_at(19,col);
        auto& h=m.battle.heroes.hero(Seat::zombie);const auto initial=h.frame.hp.get();
        auto first=f.plant("三叶草",1416.);cell.block.set("孤独梯子块");cell.belt.set(true);
        const auto tick=[&](int n){for(int i=0;i<n;++i){m.wind.before_plants();m.wind.after_plants();}};
        tick(49);auto second=f.plant("三叶草",1368.);tick(50);near(h.frame.hp.get(),initial,"before tick 100");
        tick(1);near(h.frame.hp.get(),initial-5,"first tick");tick(49);near(h.frame.hp.get(),initial-10,"second tick");
        expect(h.frame.down.or_missing(0.)==0.,"wind knocked Dave down");
        cell.block.set("空");cell.belt.erase();tick(1);cell.block.set("水");tick(99);near(h.frame.hp.get(),initial-10,"wind did not reset on dry ground");
        tick(1);near(h.frame.hp.get(),initial-20,"water exposure");
        return J{{"damage",initial-h.frame.hp.get()}};
    }));
    rows.push_back(scenario("wind.stairs_and_shores",[](){
        J paths=J::array();
        for(bool zombie_wind:{false,true})for(int dir:{-1,1})for(bool water:{false,true}){
            Fixture f(decks({"plant:三叶草"},{"zombie:脑光墓碑","zombie:三叶草僵尸"}));auto& m=*f.match;
            const auto seat=zombie_wind?Seat::plant:Seat::zombie;
            const double tile=f.tile();auto& terrain=m.battle.terrain;
            const int origin=dir>0?68:3;
            for(int offset=0;offset<24;++offset){
                const auto col=terrain.wrap(origin+dir*offset);
                const int level=std::clamp(1+(offset-3)/4,0,3);
                const int height=offset<3?0:level;
                for(int j=1;j<=height;++j)terrain.native_at(20-j,col).block.set("土");
                if(water&&offset<3)terrain.native_at(19,col).block.set("水");
            }
            m.sync_terrain();const double start=(origin+.5)*tile;
            f.hero_at(seat,start);f.hero_at(seat==Seat::plant?Seat::zombie:Seat::plant,32.5*tile);
            auto& avatar=m.battle.heroes.hero(seat);auto& pos=*avatar.frame.position.get();
            PlantRef clover;ZombieRef blower;
            if(zombie_wind)blower=f.zombie("三叶草僵尸",start-dir*tile,dir);
            else clover=f.plant("三叶草",start-dir*tile,dir);
            double best=0.;J track=J::array();int64_t hops=0;
            for(int frame=0;frame<950&&best<13.;++frame){
                if(clover)clover->expires.set(1.);
                if(blower){blower->body.motion.get()={pos.x-dir*1.8*tile,pos.y,0.,0.};blower->body.facing=dir;blower->patch.fire_animation.set(240.);}
                if(water&&best<2.9)avatar.frame.in_water.set(true);
                f.run(1);best=std::max(best,dir*wrap_delta(start,pos.x,m.battle.world_width.get())/tile);
                if(m.wind.wind_hops!=hops){
                    hops=m.wind.wind_hops;track.push_back({best,pos.y/tile});
                }
            }
            J row={{"source",zombie_wind?"zombie":"plant"},{"dir",dir},{"water",water},{"cells",best},{"hops",hops},{"trajectory",track}};
            expect(best>=12.5&&hops>=3,"incomplete staircase "+row.dump());paths.push_back(std::move(row));
        }
        return J{{"paths",paths}};
    }));
    rows.push_back(scenario("mark.and_deathmatch",[](){
        Fixture f(decks({"plant:路灯花"},{"zombie:脑光墓碑"}));auto& m=*f.match;
        auto& plant=m.battle.heroes.players[seat_index(Seat::plant)].value();
        auto& zombie=m.battle.heroes.players[seat_index(Seat::zombie)].value();
        zombie.position={1512.,960.};plant.position={1512.+8*f.tile(),960.};
        expect(m.chart.passive_mark(Seat::zombie).empty(),"unexpected distant mark");
        plant.position=zombie.position;expect(m.chart.passive_mark(Seat::zombie)=="戴夫","nearby Dave");
        f.hero_at(Seat::plant,1512.+8*f.tile());f.hero_at(Seat::zombie,1512.);
        auto lamp=f.plant("路灯花",1512.);
        plant.position={1512.+8*f.tile(),960.};zombie.position={1512.,960.};
        expect(m.chart.passive_mark(Seat::zombie)=="路灯花","lamp mark");
        lamp->hp.set(0.);expect(m.chart.passive_mark(Seat::zombie).empty(),"dead lamp mark");
        const std::array seats{Seat::plant,Seat::zombie};
        for(auto side:seats)f.hero_at(side,1512.);
        auto& contact=m.battle.terrain.native_at(19,int(1512./f.tile()));contact.block.set("梯子块");contact.belt.set(true);
        for(auto side:seats)m.battle.heroes.hero(side).frame.hp.set(4.);
        HeroRecovery recovery{m.battle,m.resources,m.sight};recovery.water_damage(seats,1.,false);
        for(auto side:seats)near(m.battle.heroes.hero(side).frame.hp.get(),4.,"before deathmatch");
        recovery.water_damage(seats,.99,true);
        for(auto side:seats)near(m.battle.heroes.hero(side).frame.hp.get(),4.,"before one second");
        recovery.water_damage(seats,.01,true);recovery.water_damage(seats,1.,true);
        for(auto side:seats){const auto& frame=m.battle.heroes.hero(side).frame;near(frame.hp.get(),2.,"overlapping hazards");near(frame.down.or_missing(0.),0.,"terrain knockdown");}
        return J{{"hp_after_two_seconds",2}};
    }));
    rows.push_back(scenario("lottery.daily_wave_counts",compare_solo_waves));
    rows.push_back(scenario("ui.entries",[](){
        auto h=battle_from_scenario({{"seed",77}});V pgmod=pg::pygame_module();
        auto screen=callm(pg::display_module(),SY("set_mode"),Args{V::tuple({V(1280),V(720)})});
        V app=pm_app::new_Application(Args{pgmod,screen,h.bridge});J report;
        auto action=[&](const char* op,const char* key=""){callm(app,SY("action"),Args{V::tuple({V("solo77"),V(op),V(key)})});};
        action("pool");callm(app,SY("render"),Args{});
        action("details","zombie:普通僵尸");callm(app,SY("render"),Args{});
        expect(py::m_get(getattr(app,SY("state")),V("screen"))==V("solo_pool_detail"),"co-op card detail");
        action("pool_list");action("pool","books");callm(app,SY("render"),Args{});
        report["coop_pool_detail"]=true;
        for(const auto mode:{"lottery","izombie"}){
            auto send=[&](const char* op,const char* key=""){callm(app,SY("action"),Args{V::tuple({V("solo77"),V(op),V(key)})});};
            send("modes");callm(app,SY("render"),Args{});send("open",mode);callm(app,SY("render"),Args{});send("start");
            auto room=getattr(app,SY("room"));auto state=getattr(app,SY("state"));
            expect(room.truthy(),"room missing "+py_str(py::m_get(state,V("message"))));
            auto phase=py_str(getattr(room,SY("phase")));expect(phase=="loading"||phase=="battle","start "+phase+" "+py_str(py::m_get(state,V("message"))));
            callm(app,SY("render"),Args{});
            callm(app,SY("refresh"),Args{});
            phase=py_str(getattr(room,SY("phase")));
            expect(phase=="battle","render did not acknowledge loading: "+phase);
            expect(py_str(py::m_get(state,V("active_side")))==(std::string(mode)=="izombie"?"zombie":"plant"),"wrong human seat");
            auto battle=getattr(room,SY("battle"));expect(battle.truthy(),"missing production session");
            callm(battle,SY("step"),Args{V(2)});
            callm(app,SY("render"),Args{});
            report[mode]=phase;callm(app,SY("close_room"),Args{});
        }
        return report;
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

J hotfix77(){
    using namespace pvz;
    using namespace pvz::typed72;
    J rows=J::array();
    for(const auto mode:{"lottery","izombie"})rows.push_back(scenario(std::string(mode)+".battle_rng",[=](){
        auto sample=[&](int seed){
            const bool zombie=std::string(mode)=="izombie";
            Fixture f(decks(zombie?J::array():J({"plant:模仿者"}),J({"zombie:脑光墓碑","zombie:普通僵尸"})),
                      J{{"rules",{{"pvp77_mode",mode},{"pvp77_battle_seed",seed},{"pvp77_stage",1},
                                  {"pvp77_plants",{"plant:豌豆射手","plant:向日葵","plant:金盏花","plant:土豆地雷"}},
                                  {"pvp77_zombies",{"zombie:普通僵尸","zombie:路障僵尸"}}}}});
            auto& m=*f.match;J result=J::object();
            if(zombie){
                for(const auto& g:m.battle.solo.graves)result["graves"].push_back({g.x,g.y});
                for(const auto& p:*m.battle.plant_roster){
                    const bool brain=p->kind.find("脑子")!=std::string::npos;
                    result[brain?"brains":"plants"].push_back({p->kind,p->cell.x,p->cell.y});
                }
                expect(result["brains"].size()==3&&result["graves"].size()==3&&!result["plants"].empty(),"incomplete board");
            }else{
                for(double x:{1512.,1595.,1704.}){
                    auto error=deploy(f,Seat::plant,"plant:模仿者",x,936.);expect(error.empty(),error);
                    result["draws"].push_back(m.battle.plant_roster->back()->copy_card.get());
                }
            }
            return result;
        };
        auto first=sample(117),second=sample(518),third=sample(930);
        expect(first==sample(117),"same injected seed diverged");
        for(auto& [key,value]:first.items())expect(value!=second.at(key)||value!=third.at(key),"seed left "+key+" fixed");
        return J{{"samples",{first,second,third}}};
    }));
    rows.push_back(scenario("coop.settlement_and_reload",[](){
        auto h=battle_from_scenario({{"seed",91}});
        auto screen=callm(pg::display_module(),SY("set_mode"),Args{V::tuple({V(1280),V(720)})});
        auto app=pm_app::new_Application(Args{pg::pygame_module(),screen,h.bridge});
        callm(app,SY("create_offline_host"),Args{});auto room=getattr(app,SY("room"));callm(room,SY("set_mode"),Args{V("coop")});
        auto progress=getattr(room,SY("coop_progress"));setitem(getattr(room,SY("members")),V("qa_guest"),V("plant2"));
        auto ledger=getattr(progress,SY("campaigns"));J report;
        auto encode=[](V data){return py_str(py::stdlib_call(SV("json.dumps"),Args{data}));};
        auto shops=[&](){J stocks=J::array();for(auto side:{"plant","plant2"})stocks.push_back(J::parse(encode(getattr(rd(ledger,V(side)),SY("shop")))));return stocks;};
        J prev=shops();
        for(int i=0;i<3;++i){
            setattr(room,SY("match_id"),V("hotfix-coop-"+std::to_string(i)));
            V result=py_dict({{V("winner"),V(i==2?"plant":"zombie")},{V("tick"),V(60)},{V("pve_day"),V(1)}});
            callm(progress,SY("finish"),Args{room,result});auto after=shops();
            for(int seat=0;seat<2;++seat)expect(after[seat]!=prev[seat],"no replacement for seated co-op player");
            callm(progress,SY("finish"),Args{room,result});expect(shops()==after,"duplicate settlement changed stock");
            if(i==2){
                for(auto side:{"plant","plant2"}){
                    auto campaign=rd(ledger,V(side));setattr(campaign,SY("coins"),V(5000));
                    expect(!callm(campaign,SY("buy"),Args{V(0)}).truthy(),"co-op purchase");
                    auto bought=encode(getattr(campaign,SY("shop")));
                    auto restored=pm_pve::C_Campaign::m_from_dict(Args{callm(campaign,SY("to_dict"),Args{})});
                    expect(encode(getattr(restored,SY("shop")))==bought,"saved bought stock changed");
                    callm(restored,SY("choose_reward"),Args{getattr(restored,SY("rewards")).idx(0)});
                    expect(encode(getattr(restored,SY("shop")))==bought,"co-op reward rerolled stock");
                }
            }
            report["batches"].push_back(after);prev=after;
        }
        callm(app,SY("close_room"),Args{});return report;
    }));
    rows.push_back(scenario("solo.normal_entries_shop_and_pages",[](){
        auto h=battle_from_scenario({{"seed",89}});auto pgmod=pg::pygame_module();
        V screen=callm(pg::display_module(),SY("set_mode"),Args{V::tuple({V(1280),V(720)})});
        V app=pm_app::new_Application(Args{pgmod,screen,h.bridge});J report;
        const auto folder=u8p(std::getenv("PVP_USERDATA")).parent_path();
        auto send=[&](const char* op,const std::string& key=""){callm(app,SY("action"),Args{V::tuple({V("solo77"),V(op),V(key)})});};
        auto capture=[&](std::string name){
            callm(app,SY("render"),Args{});
            callm(pg::image_module(),SY("save"),Args{screen,V(p8(folder/u8p(name+".png")))});
            if(name.ends_with("-shop")){
                auto car=callm(pg::image_module(),SY("load"),Args{V(gfx::atlas_file("背景图集","商店"))});
                int checked=0;
                for(const auto& [x,y]:std::array<std::pair<int,int>,4>{{{900,600},{765,673},{1010,340},{1120,580}}}){
                    auto expected=callm(car,SY("get_at"),Args{V::tuple({V(x*960/1280),V(y*768/720)})});
                    if(expected.idx(3).num()!=255.)continue;
                    auto actual=callm(screen,SY("get_at"),Args{V::tuple({V(x),V(y)})});
                    for(int channel=0;channel<3;++channel)expect(std::abs(expected.idx(channel).num()-actual.idx(channel).num())<=3,"missing shop car pixels");
                    ++checked;
                }
                expect(checked>=3,"no opaque car samples");
            }
        };
        send("modes");capture("modes");
        for(const auto mode:{"lottery","izombie"}){
            std::string id=mode;send("open",id);capture(id+"-deck");
            const auto file=u8p(py_str(callm(app,SY("campaign_path"),Args{}))).parent_path()/(id+"_v77.json");
            auto read=[&](){std::ifstream in(file);return J::parse(in);};
            auto before=read();std::set<int> seeds;
            send("open",id=="izombie"?"lottery":"izombie");send("open",id);
            expect(read()==before,"fresh unsold stock changed while switching modes");
            send("shop");capture(id+"-shop");send("run");
            if(id=="izombie"){
                send("defenders");capture("izombie-defenders");send("defenders","books");capture("izombie-defender-books");
                send("back_pool");expect(rd(getattr(app,SY("state")),V("screen"))==V("solo_run"),"prep pool back");
            }
            std::set<std::string> layouts;
            for(int i=0;i<3;++i){
                send("start");auto room=getattr(app,SY("room"));expect(room.truthy(),"missing room");
                int seed=int(getattr(room,SY("seed")).num());seeds.insert(seed);
                callm(app,SY("render"),Args{});callm(app,SY("refresh"),Args{});
                V battle=getattr(room,SY("battle"));expect(battle.truthy(),"missing battle");
                expect(rd(getattr(battle,SY("rules")),V("pvp77_battle_seed"))==V(seed),"lost battle seed");
                const auto snapshot=getattr(room,SY("map"));const V tiles=getattr(snapshot,SY("tiles"));
                layouts.insert(py_str(py::stdlib_call(SV("json.dumps"),Args{tiles})));
                if(id=="izombie"&&i==1)expect(rd(getattr(battle,SY("rules")),V("pvp77_start_brain"))==V(175),"starting brains from purchased upgrade");
                const bool iz=id=="izombie";
                const auto result=py_dict({{V("winner"),V((i==2)==iz?"zombie":"plant")},{V("coins"),V(2000)}});
                expect(solo77::result(app,result),"result did not reach campaign");auto settled=read();
                expect(settled.at("shop")!=before.at("shop"),"same solo shop after actual settlement");
                solo77::result(app,result);expect(read()==settled,"duplicate settlement paid or rerolled");
                callm(app,SY("close_room"),Args{});
                send("shop");capture(id+"-restock");
                size_t index=0;if(iz&&i==0){while(index<settled.at("shop").size()&&settled.at("shop")[index]["key"]!="brain")++index;}
                const auto key=settled.at("shop").at(index).at("key").get<std::string>();
                send("inspect_buy",key);expect(!read()["shop"][index]["sold"].get<bool>(),"first tap purchased");
                send("inspect_buy",key);const auto bought=read();expect(bought["shop"][index]["sold"].get<bool>(),"second tap did not purchase");
                send("open",iz?"lottery":"izombie");send("open",id);send("shop");expect(read()==bought,"reopen changed stock");send("run");
                if(i==2){capture(id+"-reward-entrance");SDL_Delay(850);capture(id+"-rewards");
                    send("inspect_reward",bought.at("rewards")[0].get<std::string>());capture(id+"-reward-detail");
                    send("inspect_reward",bought.at("rewards")[0].get<std::string>());expect(read()["shop"]==bought["shop"],"solo reward rerolled");
                }
                before=read();
            }
            expect(seeds.size()==3&&layouts.size()>1,"same real-entry seeds or tiles");report[id]=seeds;
        }
        return report;
    }));
    return rows;
}

J revision77(){
    using namespace pvz;using namespace pvz::typed72;
    auto rows=hotfix77();
    rows.push_back(scenario("campaign.real_pools_shop_rewards",[](){
        const auto& p=solo77::campaign_pools();auto contains=[](const auto& cards,const std::string& key){return std::any_of(cards.begin(),cards.end(),[&](const auto& c){return c.key==key;});};
        expect(!contains(p.plants,"secret:肆意模仿")&&!contains(p.plants,"plant:模仿者"),"ordinary copy in lottery rewards");
        expect(contains(p.zombies,"zombie:飞贼僵尸")&&!contains(p.zombies,"zombie:克苏鲁之仆"),"zombie roster");
        expect(std::find(p.defenders.begin(),p.defenders.end(),"plant:墓碑吞噬者")==p.defenders.end(),"defender gravebuster");
        const auto pre=pm_pve::f_reward_pool(Args{V::list(),V(true)}),post=pm_pve::f_reward_pool(Args{V::list({V("plant:模仿者")}),V(true)});
        expect(py::in(V("plant:模仿者"),pre)&&!py::in(V("secret:肆意模仿"),pre)&&py::in(V("secret:肆意模仿"),post),"coop imitation dependency");
        int shop=0,reward=0;
        for(int seed=0;seed<300;++seed){
            solo77::Campaign c;c.start("izombie",seed,p);c.coins=1000;
            expect(c.buy("brain").empty()&&c.sun_bought==1&&!c.buy("brain").empty(),"brain purchase");
            auto restored=nlohmann::json(c).get<solo77::Campaign>();expect(restored.sun_bought==1,"saved brain upgrade");
            c.finish(p,std::to_string(seed),true,0,0);
            expect(c.rewards.size()==3&&c.rewards.front()=="zombie:梯子僵尸","three choices / guaranteed ladder");
            shop+=contains(c.shop,"zombie:飞贼僵尸");reward+=std::count(c.rewards.begin(),c.rewards.end(),"zombie:飞贼僵尸");
        }
        expect(shop&&reward,"bungee never offered");return J{{"seeds",300},{"bungee_shop",shop},{"bungee_reward",reward}};
    }));
    rows.push_back(scenario("izombie.live_graves_commander_cooldowns",[](){
        Fixture f(decks(J::array(),{"zombie:普通僵尸","zombie:飞贼僵尸"}),J{{"rules",{{"pvp77_mode","izombie"},{"pvp77_start_brain",175}}}});
        auto& m=*f.match;auto& w=m.battle;const auto i=seat_index(Seat::zombie);
        near(m.resources.accounts[i].balance,175.,"brain upgrade ignored");expect(w.heroes.players[i]->cooldowns.empty(),"opening cooldown");
        m.resources.accounts[i].balance=2000.;const auto g=w.solo.graves.front();const auto tile=f.tile();
        auto spawn=[&](const char* card,Cell c){NativeCommand cmd{NativeCommandKind::deploy};cmd.card=sval(card);cmd.x=dval((c.x+.5)*tile);cmd.y=dval((c.y+.5)*tile);cmd.facing.state=InputFieldState::value;cmd.facing.value=-1;return m.native_commands.apply(Seat::zombie,cmd);};
        for(int n=0;n<2;++n)expect(spawn("zombie:普通僵尸",g).empty(),"instant redeployment");
        destroy_pvp_block(w,m,g);m.sync_terrain();
        const auto& cell=w.terrain.native_at(g.y,g.x);expect(!cell.grave_art.present()&&cell.block.get()!="坟墓"&&!spawn("zombie:普通僵尸",g).empty(),"destroyed map grave");
        const Cell other{19,31};auto buster=f.zombie("墓碑吞噬者僵尸",1050.);
        auto summoned=m.spawn_bone_grave(other,BoneSource{NativeObject(buster),source_ref(buster),-1.});expect(bool(summoned),"bone grave factory");m.sync_public();
        auto live=spawn("zombie:普通僵尸",other);expect(live.empty(),"live summoned grave "+live);summoned->body.hp=0.;
        expect(!spawn("zombie:普通僵尸",other).empty(),"dead summoned grave still accepted");
        const auto extras=w.omitted_targets();expect(std::none_of(extras.begin(),extras.end(),[](const auto& t){return t.is_hero();}),"commander in attack targets");
        Fixture duel(decks({"plant:豌豆射手"},{"zombie:脑光墓碑"}));auto normals=duel.match->battle.omitted_targets();
        expect(std::any_of(normals.begin(),normals.end(),[](const auto& t){return t.is_hero();}),"duel Dave lost collision");
        Fixture lane(decks(J::array(),{"zombie:普通僵尸"}),J{{"rules",{{"pvp77_mode","izombie"},{"pvp77_defenders",{"plant:向日葵"}}}}});
        auto& combat=*lane.match;const double hx=1608.,zx=hx+96.;lane.hero_at(Seat::zombie,hx);
        auto target=lane.zombie("普通僵尸",zx);target->native.move_speed.set(.001);
        const double hp=target->body.hp;const auto gun=lane.plant("豌豆射手",1512.);
        double furthest=0.;int shots=0;
        for(int n=0;n<1500&&target->body.hp==hp&&!combat.room.result;++n){
            lane.run(1);
            for(const auto& e:*combat.battle.runtime.entities.list())if(e->kind=="豌豆"){++shots;furthest=std::max(furthest,e->motion.get().x);}
        }
        expect(target->body.hp<hp&&shots>0&&furthest>hx,"pea flight: max x="+std::to_string(furthest)+" zombie="+std::to_string(target->body.motion.get().x)+" shots="+std::to_string(shots));
        return J{{"pea_damage_behind_commander",hp-target->body.hp},{"initial_brain",175},{"same_tick_deploys",2},{"destroyed_grave_rejected",true},{"duel_hero_collision",true}};
    }));
    rows.push_back(scenario("lottery.coffee_and_cannon_display",[](){
        J report;
        for(const bool lottery:{false,true}){
            J rules={{"pvp77_plants",{"plant:玉米加农炮"}},{"pvp77_stage",8}};if(lottery)rules["pvp77_mode"]="lottery";
            Fixture f(decks({"plant:模仿者","plant:咖啡豆","plant:玉米加农炮","plant:玉米投手"},{"zombie:脑光墓碑"}),J{{"rules",rules}});
            auto& m=*f.match;
            const auto pi=seat_index(Seat::plant);m.resources.accounts[pi].balance=10000.;m.battle.heroes.players[pi]->cooldowns.clear();
            NativeCommand plant{NativeCommandKind::deploy};plant.card=sval("plant:模仿者");plant.x=dval(1512.);plant.y=dval(936.);
            if(!lottery)plant.copy=sval("plant:玉米加农炮");
            auto deployed=m.native_commands.apply(Seat::plant,plant);expect(deployed.empty(),deployed);
            auto copy=m.battle.plant_roster->back();expect(copy->copy_card.or_missing("")=="plant:玉米加农炮","wrong copy target");f.run(310);
            bool grey=false;for(const auto& p:*m.battle.plant_roster)if(p->kind=="玉米加农炮"){grey=p->monochrome.present();p->cannon_cd.set(0.);}
            expect(grey,"cannon lost monochrome state");
            m.begin_frame(m.battle.heroes.tick);m.set_drawing(true);m.plant_draw.draw_all();
            const auto frame=m.canvas.frame_json(m.canvas.frames.frame()).dump();
            expect(frame.find("玉米加农炮-黑白")!=std::string::npos&&frame.find("玉米炮-黑白")!=std::string::npos&&frame.find("玉米加农炮-车-黑白")!=std::string::npos,"missing grey cannon recipe "+frame.substr(0,3000));
            if(lottery){
                const auto index=seat_index(Seat::plant);m.resources.accounts[index].balance=10000.;
                auto shoot=[&](double x){NativeCommand c{NativeCommandKind::deploy};c.card=sval("plant:咖啡豆");c.x=dval(x);c.y=dval(936.);return m.native_commands.apply(Seat::plant,c);};
                auto a=f.plant("大喷菇",1656.);a->sleep.set(0.);auto b=f.plant("大喷菇",1752.);b->sleep.set(0.);m.sync_public();
                auto err=shoot(1656.);expect(err.empty(),err);expect(!shoot(1752.).empty(),"coffee early reuse");
                const auto& cd=m.battle.heroes.players[index]->cooldowns;auto t=std::find_if(cd.begin(),cd.end(),[](const auto& v){return v.first=="plant:咖啡豆";});
                expect(t!=cd.end(),"coffee missing cooldown");near(t->second-m.battle.heroes.time,2.,"coffee cooldown");
                m.battle.heroes.time=t->second;err=shoot(1752.);expect(err.empty(),err);expect(!m.battle.solo.spent.contains("plant:咖啡豆"),"coffee spent");
            }
            report[lottery?"lottery":"duel"]="grey cannon";
        }return report;
    }));
    rows.push_back(scenario("test_mode.fill_from_reference_and_save",[](){
        auto h=battle_from_scenario({{"seed",58}});auto screen=callm(pg::display_module(),SY("set_mode"),Args{V::tuple({V(1280),V(720)})});
        auto app=pm_app::new_Application(Args{pg::pygame_module(),screen,h.bridge});callm(app,SY("create"),Args{V(true)});
        auto act=[&](const char* op,V v=V::none()){callm(app,SY("action"),Args{V::tuple({V("test74"),V(op),v})});};
        act("start");expect(getattr(getattr(app,SY("room")),SY("phase"))==V("battle"),"test entry "+dump(getattr(app,SY("state"))));act("open",V("cards"));
        auto deck=[&](const char* side){callm(app,SY("refresh"),Args{});return rd(rd(rd(rd(getattr(app,SY("view")),V("battle")),V("players")),V(side)),V("deck"));};
        act("slot",V(0));act("card",V("plant:豌豆射手"));act("reference");
        const auto plant=deck("plant");expect(plant.idx(0)==V("plant:豌豆射手")&&plant.idx(1).truthy(),"reference fill lost existing slot or added nothing");
        const auto path=getattr(getattr(app,SY("settings_path")),SY("parent"))/V("decks.json");
        pm_ui_data::f_save_decks(Args{path,py_dict({{V("zombie"),V::list({V("zombie:脑光墓碑"),V("zombie:普通僵尸")})}}),py_dict({{V("zombie_slots"),V(2)}})});
        act("side",V("zombie"));act("saved");const auto zombie=deck("zombie");
        expect(py::in(V("zombie:脑光墓碑"),zombie)&&py::in(V("zombie:普通僵尸"),zombie),"saved deck not applied");
        callm(app,SY("close_room"),Args{});return J{{"saved",2},{"reference",dump(plant)}};
    }));
    rows.push_back(scenario("workshop.mode_cover_pixels_and_hover",[](){
        namespace tx=pvz::texture74;
        auto h=battle_from_scenario({{"seed",81}});auto surface=callm(pg::display_module(),SY("set_mode"),Args{V::tuple({V(1280),V(720)})});
        auto app=pm_app::new_Application(Args{pg::pygame_module(),surface,h.bridge});auto renderer=getattr(app,SY("renderer"));
        const auto prior=tx::state().document;auto pack=prior;
        auto resource=tx::resource("ui:抽奖模式");expect(resource&&resource->campaign,"cover absent from workshop");
        auto pixels=tx::surface(resource->w,resource->h,std::vector<uint32_t>(resource->w*resource->h,0xef267dffu));
        pack["entries"][resource->key]={{"width",resource->w},{"height",resource->h},{"png",tx::b64(tx::png_encode(pixels))}};
        tx::activate(pack);callm(app,SY("action"),Args{V::tuple({V("solo77"),V("modes")})});
        callm(app,SY("render"),Args{});
        V box;for(const auto& item:getattr(renderer,SY("controls")).items()){
            const auto op=item.idx(1);if(op.len()==3&&op.idx(2)==V("lottery"))box=item.idx(0);
        }
        expect(box.has(),"missing selector hitbox");auto center=getattr(box,SY("center"));auto color=callm(surface,SY("get_at"),Args{center});tx::activate(prior);
        expect(color.idx(0)==V(239)&&color.idx(1)==V(38)&&color.idx(2)==V(125),"workshop override did not reach cover");
        callm(app,SY("render"),Args{});expect(callm(surface,SY("get_at"),Args{center})!=color,"disabled override still cached");
        const auto before=callm(surface,SY("copy"),Args{});
        auto pointer=V::func([center](const Args&){return center;});setattr(app,SY("_pointer"),pointer);SDL_Delay(180);callm(app,SY("render"),Args{});
        int changed=0;for(int x=int(center.idx(0).num())-60;x<int(center.idx(0).num())+60;x+=4)for(int y=int(center.idx(1).num())-130;y<int(center.idx(1).num())+80;y+=4){auto at=V::tuple({V(x),V(y)});if(callm(before,SY("get_at"),Args{at})!=callm(surface,SY("get_at"),Args{at}))++changed;}
        expect(changed>25,"hover produced no visible movement");return J{{"hover_pixels_sampled_changed",changed},{"override_rgb",{239,38,125}}};
    }));
    rows.push_back(scenario("terrain.all_twelve_original_maps",[](){
        J shapes;for(const char* name:MAP_NAMES){
            auto layout=[&](int seed){std::string s;for(const auto& row:generate_original_map(name,seed,true))for(const auto& c:row)s+=c.方块+"|"+c.里方块+";";return s;};
            std::set<std::string> unique;for(int seed:{7,35,82,619})unique.insert(layout(seed));expect(unique.size()>1,name);
            expect(layout(7)==layout(7),"seed unstable");shapes[name]=unique.size();
        }return shapes;
    }));
    return rows;
}
static std::filesystem::path armor_output;
J armor_cart77(){
    using namespace pvz;using namespace pvz::typed72;
    J rows=J::array();
    for(const std::string name:{"小鬼炮","投篮车僵尸"}){
        rows.push_back(scenario("cart."+name,[&](){
            J cases=J::array();
            for(bool rally:{false,true})for(bool left:{false,true})for(bool contact:{false,true}){
                Fixture f(decks({"plant:向日葵"},{"zombie:脑光墓碑","zombie:"+name}));auto& m=*f.match;
                const double dir=left?-1.:1.,x=1512.,tile=f.tile();m.commands.shared=PathMode::follow_hero;
                auto z=f.zombie(name,x,dir);auto& hero=m.battle.heroes.hero(Seat::plant);
                if(rally)m.hero_flags.shared=Point{x,960.};
                f.hero_at(Seat::zombie,x+dir*tile*.5);f.hero_at(Seat::plant,x+dir*(contact?.5:20.)*tile);
                hero.frame.hp.set(40.);hero.frame.down.set(0.);z->native.advance.set(2.);
                f.run(1);
                const double hp=hero.frame.hp.get(),down=hero.frame.down.or_missing(0.),vx=hero.frame.position.get()->vx;
                J result={{"rally",rally},{"left",left},{"contact",contact},{"hp",hp},{"down",down},{"vx",vx},{"advance",z->native.advance.get()},{"crash",z->native.crash.get()}};
                expect(z->native.advance.get()==0.,"cart failed to stop "+result.dump());
                if(contact)expect(hp<40.&&down>0.&&vx*dir>0.&&z->native.crash.get()>0.,"real contact "+result.dump());
                else{
                    expect(hp==40.&&down==0.&&vx==0.&&z->native.crash.get()==0.,"distant contact "+result.dump());
                    f.run(100);expect(hero.frame.hp.get()==40.&&hero.frame.down.or_missing(0.)==0.,"damage after parking");
                }
                cases.push_back(result);
            }
            return J{{"cases",cases}};
        }));
    }
    rows.push_back(scenario("armor.frames",[](){
        Fixture f(decks({"plant:向日葵"},{"zombie:脑光墓碑"}));auto& m=*f.match;
        J images=J::array();int pairs=0,broken=0;
        for(const std::string name:{"海盗鹦鹉","乌鸦","稻草人","滚桶僵尸","掷弹兵僵尸","史莱姆僵尸","中型史莱姆","小型史莱姆","小鬼炮"}){
            // The two smaller slimes are summon-only. All three use the production frame drawer.
            auto z=f.zombie(name=="中型史莱姆"||name=="小型史莱姆"?"史莱姆僵尸":name);z->source.content.set(name);
            for(const std::string armor:{"路障","铁桶","黑路障","黑铁桶","橄榄球头盔","黑橄榄球头盔","南瓜头防具"}){
                z->body.armor=armor;z->body.armor_hp=80.;
                for(int pose=0;pose<(name=="乌鸦"?7:name=="海盗鹦鹉"||name=="小鬼炮"?2:1);++pose){
                    m.battle.heroes.tick=name=="乌鸦"?(pose>=3?(pose-3)*12:pose*18):pose*35;
                    z->native.biting.set(pose>=3?30.:0.);
                    if(name=="小鬼炮"){z->content.cannon_loaded.set(pose!=0);z->content.summon_clock.set(900.);z->content.cannon_recoil.set(pose?45.:0.);}
                    for(double facing:{1.,-1.}){
                        z->body.facing=facing;
                        auto draw=[&](){
                            m.begin_frame(m.battle.heroes.tick);m.set_drawing(true);
                            if(name.find("史莱姆")!=std::string::npos||name=="掷弹兵僵尸")m.draw_zombie(z);else m.draw_content_zombie(z);
                            return m.canvas.frame_json(m.canvas.frames.frame()).at("commands");
                        };
                        auto cmd=draw();const NativeCanvas::Json* dressed=nullptr;
                        for(const auto& layer:cmd)if(layer.dump().find(armor)!=std::string::npos){
                            expect(!dressed,name+" duplicate "+armor);dressed=&layer;
                        }
                        expect(dressed,name+" missing "+armor+" "+cmd.dump().substr(0,400));
                        images.push_back({{"unit",name},{"armor",armor},{"pose",pose},{"dir",facing},{"command",*dressed}});
                        if(pose==0&&facing>0.){
                            z->body.armor_hp=0.;auto bare=draw();expect(bare.dump().find(armor)==std::string::npos,name+" broken "+armor);
                            z->body.armor_hp=80.;++broken;
                        }
                    }
                    ++pairs;
                }
            }
        }
        // Include the native template and patch overlays in one live frame to
        // catch the original duplicated or hidden helmet outside the custom drawer.
        for(const std::string wearer:{"海盗鹦鹉","乌鸦","豌豆僵尸","普通僵尸"}){
            Fixture live(decks({"plant:坚果"},{"zombie:脑光墓碑"}));auto z=live.zombie(wearer);
            for(const std::string armor:{"铁桶","黑橄榄球头盔","南瓜头防具"}){
                z->body.armor=armor;z->body.armor_hp=80.;live.match->driver.run(true);
                auto frame=live.match->canvas.frame_json(live.match->canvas.frames.frame());int visible=0;
                for(const auto& cmd:frame.at("commands"))if(cmd.value("entity",std::string{})==z->source.id.get()&&cmd.dump().find(armor)!=std::string::npos)++visible;
                expect(visible==1,wearer+" "+armor+" live helmet layers "+std::to_string(visible));
            }
        }
        std::ofstream(armor_output/"armor-frames.json")<<images.dump();
        return J{{"mirror_pairs",pairs},{"broken_armor",broken}};
    }));
    return rows;
}
int main(int argc,char** argv){
    using namespace pvz;
    if(argc!=2)return 2;
    auto out=std::filesystem::absolute(u8p(argv[1]));std::filesystem::create_directories(out);armor_output=out;
    env_set_u8("PVP_USERDATA",p8(out/"userdata"));env_set_u8("SDL_VIDEODRIVER","dummy");env_set_u8("SDL_AUDIODRIVER","dummy");
    SDL_SetMainReady();gil::init();data::set_data_dir("extract/data");pg::install_pygame();init_pvp_modules();
    J result={{"checks",J::array()},{"failures",0}};int failures=0;
    const char* only=std::getenv("PVP76R3_AUDIT_CASE");
    for(auto [name,fn]:std::vector<std::pair<std::string,J(*)()>>{{"catalog",catalog},{"heroes",heroes},{"zombies",zombies},{"plants",plants},{"probe",probe},{"pvp77",solo77_checks},{"pvp77r2",hotfix77},{"pvp77r3",revision77},{"pvp77r4",armor_cart77}}){
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
