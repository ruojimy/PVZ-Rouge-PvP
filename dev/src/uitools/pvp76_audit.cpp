// PvP76 focused mechanics on the production match composition (same kernel and
// composition as the shipped Session): balance, secrets and interaction rules.
//   pvp76_audit <out-folder>          (PVP76_AUDIT_CASE=<name> runs one group)
#define content_phase_unused_main pvp76_audit_content_phase_main
#define TYPED72_NO_MAIN
#include "match_probe.cpp"
#include "sim/typed72_app/cold_export.h"
#include "sim/typed/defense.h"
#include "sim/typed/plant_queries.h"
#include "sim/pvp/battle_api.h"
#include "sim/pvp/gen/pm_catalog.h"
#include "core/fsutil.h"
#include "core/gil.h"
#include "pg/pg.h"
#include "data/datastore.h"

namespace {
using namespace pvz;
using namespace pvz::typed72;
void expect(bool ok,const std::string& message){if(!ok)throw std::runtime_error(message);}
void near(double actual,double wanted,const std::string& label,double eps=1e-6){
    expect(std::abs(actual-wanted)<eps,label+" expected "+std::to_string(wanted)+" observed "+std::to_string(actual));
}
double total(const ZombieRef& z){return std::max(0.,z->body.hp)+std::max(0.,z->body.armor_hp)+std::max(0.,z->body.hand_hp);}
const J kPlants={"plant:激光豆","plant:金盏花","plant:大嘴花","plant:向日葵","secret:聚能"};
const J kZombies={"zombie:脑光墓碑","zombie:盾卫僵尸","zombie:雪橇车小队","zombie:巨人僵尸","zombie:克苏鲁之仆","zsecret:守卫"};
struct Fixture {
    std::unique_ptr<MatchProbe> match;
    std::optional<NativeBirthScope> births;
    // decks: {"plant":[...],"zombie":[...]}; test_mode enables the local test cheats (Terraria Bosses).
    explicit Fixture(const J& decks=J{{"plant",kPlants},{"zombie",kZombies}},bool test_mode=true){
        static std::map<std::string,typed72app::ColdExport> colds;
        const auto cache_key=decks.dump()+(test_mode?"t":"f");
        auto found=colds.find(cache_key);
        if(found==colds.end()){
            auto handle=battle_from_scenario({{"fixture_flat",true},{"durable_heroes",true},{"seed",76001},
                {"rules",{{"local_test_mode",test_mode}}},{"decks",decks}});
            found=colds.emplace(cache_key,typed72app::export_cold(handle.battle,76001)).first;
            callm(handle.battle,SY("close"),Args{});
        }
        const auto& cold=found->second;const auto& c=cold.cold;
        match=std::make_unique<MatchProbe>(76001,c.at("battle").at("width").get<double>(),c.at("battle").at("rules").at("melon_splash_damage").get<double>());
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
    PlantRef plant(std::string name,double x=1512.,double facing=1.){
        auto& m=*match;auto id=m.spawn_unit("plant:"+name,"plant",x,960.,facing,false);
        expect(bool(id),"plant spawn "+name);return std::get<PlantRef>(m.battle.native_objects.get(*id).value());
    }
    ZombieRef zombie(std::string name,double x=1656.,double facing=-1.,double y=960.){
        auto& m=*match;auto id=m.spawn_unit("zombie:"+name,"zombie",x,y,facing,false);
        expect(bool(id),"zombie spawn "+name);auto z=std::get<ZombieRef>(m.battle.native_objects.get(*id).value());
        if(!z->terraria){z->native.entry.set(500.);z->body.motion.get()={x,y,0.,0.};}return z;
    }
    void run(int64_t ticks){auto& m=*match;const auto end=m.battle.heroes.tick+ticks;int guard=0;while(m.battle.heroes.tick<end&&++guard<100000)m.scheduler.step();}
    std::string command(NativeCommandKind kind,std::optional<Point> p={},Seat seat=Seat::plant){
        NativeCommand c{kind};
        if(p){c.x={InputFieldState::value,p->x};c.y={InputFieldState::value,p->y};}
        return match->native_commands.apply(seat,c);
    }
    size_t index(const ZombieRef& z){auto& t=*match->battle.targets;for(size_t i=0;i<t.size();++i)if(t[i].unit==z)return i;throw std::runtime_error("unit not in roster");}
    // Aim and fire a bean at a world point (bean at 1512 facing right).
    void fire(Point at){expect(command(NativeCommandKind::laser,Point{1512.,940.}).empty(),"aim");expect(command(NativeCommandKind::laser,at).empty(),"fire");}
    void hero_at(Seat seat,double x){auto& hero=match->battle.heroes.hero(seat);auto& pos=*hero.frame.position.get();pos.x=x;pos.y=960.;pos.vx=pos.vy=0.;}
};
template<class F> J scenario(const std::string& id,F run){
    J row={{"id",id}};
    try{row.update(run());row["passed"]=true;}
    catch(const std::exception& e){row["passed"]=false;row["error"]=e.what();}
    return row;
}
J decks(J plants,J zombies){return J{{"plant",plants},{"zombie",zombies}};}

J catalog(){
    J rows=J::array();
    rows.push_back(scenario("cold.balance",[](){
        Fixture f;auto& m=*f.match;J out;
        const std::vector<std::tuple<std::string,double,double>> want{
            {"zombie:路灯花僵尸",125,-1},{"zombie:三叶草僵尸",175,-1},{"zombie:潜水僵尸",-1,6},{"plant:激光豆",200,32}};
        for(const auto& [key,cost,cd]:want){
            const auto card=m.catalog.resolve(key,{},{},false);
            if(cost>=0.)near(card.cost,cost,key+" cost");if(cd>=0.)near(card.cooldown,cd,key+" cooldown");
            out[key]={{"cost",card.cost},{"cooldown",card.cooldown}};
        }
        for(const char* key:{"zombie:雪橇车小队","zombie:雪橇车小队僵尸"})near(m.catalog.at(key).native_hp.get(),30.,std::string(key)+" native hp");
        for(const auto& [key,lock]:std::vector<std::pair<std::string,std::string>>{{"secret:聚能","plant:激光豆"},{"zsecret:守卫","zombie:盾卫僵尸"}}){
            const auto& card=m.catalog.at(key);expect(card.category=="secret","category "+key);
            expect(card.dependency.present()&&card.dependency.get()==lock,"precursor lock "+key);out[key]={{"asset",card.asset},{"lock",lock}};
        }
        return out;
    }));
    rows.push_back(scenario("v.runtime_catalog",[](){
        J out;for(const char* key:{"secret:聚能","zsecret:守卫","zombie:路灯花僵尸","plant:激光豆"}){
            const V card=rd(pm_catalog::CARDS,V(key));expect(card.truthy(),std::string("V card ")+key);
            out[key]={{"cost",rd(card,V("cost")).num()},{"cooldown",rd(card,V("cooldown")).num()},{"asset",py_str(rd(card,V("asset")))},{"dependency",py_str(py::m_get(card,V("dependency"),V("")))}};
        }
        expect(py_str(rd(pm_catalog::RULES,V("ruleset")))=="pvp76","ruleset");
        return out;
    }));
    rows.push_back(scenario("sled_squad.30_each",[](){
        Fixture f;auto& m=*f.match;f.zombie("雪橇车小队",1800.,-1.);f.run(1100);J hp=J::array();
        for(const auto& t:*m.battle.targets)if(t.unit&&t.unit->body.kind.find("雪橇车小队")!=std::string::npos)hp.push_back(t.unit->body.hp);
        expect(hp.size()==4,"squad members "+hp.dump());for(const auto& h:hp)near(h.get<double>(),30.,"member hp");
        return J{{"hp",hp}};
    }));
    return rows;
}
J combat(){
    J rows=J::array();
    rows.push_back(scenario("defense.floor_half",[](){
        Field<double> d;d.set(600.);near(defended_damage(1.,d),.5,"floor");near(defended_damage(400.,d),100.,"reduction");
        Field<double> none;near(defended_damage(1.,none),1.,"no defense");return J{{"floor",.5}};
    }));
    rows.push_back(scenario("chomper.inedible",[](){
        Fixture f;auto& m=*f.match;J out;
        auto edible=[&](const ZombieRef& z){return plant_edible_target(m.battle,f.index(z));};
        for(const char* name:{"巨人僵尸","红眼巨人","角斗士巨人"}){auto z=f.zombie(name,2400.);out[name]=edible(z);expect(!edible(z),std::string(name)+" edible");}
        for(const char* name:{"普通僵尸","克苏鲁之仆"}){auto z=f.zombie(name,2600.);out[name]=edible(z);expect(edible(z),std::string(name)+" not edible");}
        // Bosses and every Boss part (test mode summons).
        for(const char* key:{"克苏鲁之眼","世界吞噬者","骷髅王"}){
            auto id=m.spawn_unit(std::string("zombie:")+key,"zombie",1700.,700.,-1.,false);expect(bool(id),std::string("summon ")+key);
            int parts=0,eaten=0;for(size_t i=0;i<m.battle.targets->size();++i){const auto& t=m.battle.targets->at(i);if(!t.unit||!t.unit->terraria||t.unit->terraria->type==5)continue;++parts;eaten+=plant_edible_target(m.battle,i);}
            out[key]={{"parts_total",parts},{"edible",eaten}};expect(eaten==0,std::string(key)+" part edible");
        }
        // A real bite: the chomper deals the ordinary 50 instead of swallowing a giant.
        Fixture g;auto& n=*g.match;auto chomper=g.plant("大嘴花",1512.,1.);auto giant=g.zombie("巨人僵尸",1512.+48.,-1.);giant->native.move_speed.set(.001);
        const double before=giant->body.hp;g.run(400);
        expect(giant->body.hp>0.,"giant swallowed");expect(before-giant->body.hp>=49.9,"no bite damage "+std::to_string(before-giant->body.hp));
        out["bite"]=before-giant->body.hp;(void)n;(void)chomper;return out;
    }));
    rows.push_back(scenario("gloom_vine.hero_2_5",[](){
        Fixture f;auto& m=*f.match;AttackSource s;s.plant_kind.set("小喷菇");s.content.set("忧郁藤蔓");
        const auto v=balanced_hero_amount(&s,Seat::zombie,m.battle.heroes.globals);expect(bool(v),"no override");near(*v,2.5,"gloom vine vs Dave");
        return J{{"amount",*v}};
    }));
    return rows;
}
J laser(){
    J rows=J::array();
    auto pulses=[](const J& d,bool marigold,double hero_dx){
        Fixture f(d);auto& m=*f.match;auto bean=f.plant("激光豆",1512.,1.);const double tile=m.battle.runtime.tile;
        if(marigold)f.plant("金盏花",1512.-tile,1.);
        f.hero_at(Seat::zombie,hero_dx>0.?1512.+hero_dx*tile:9000.);
        f.run(5);f.fire(Point{1512.+15.*tile,925.});const auto before=m.pvp75.beam_pulses;f.run(2000);
        if(hero_dx>0.)f.hero_at(Seat::zombie,1512.+hero_dx*tile);
        return std::pair<double,double>(double(m.pvp75.beam_pulses-before),bean->aura_factor.or_missing(1.));
    };
    rows.push_back(scenario("pulse.marigold_pressure",[&](){
        const J base=decks({"plant:激光豆","plant:金盏花"},{"zombie:脑光墓碑","zombie:普通僵尸"});
        const J pressure=decks({"plant:激光豆","plant:金盏花"},{"zombie:脑光墓碑","zombie:普通僵尸","zsecret:威压"});
        const auto [plain,f0]=pulses(base,false,0.);const auto [gold,f1]=pulses(base,true,0.);const auto [slow,f2]=pulses(pressure,false,2.);
        J out={{"plain",plain},{"marigold",gold},{"pressure",slow},{"factors",{f0,f1,f2}}};
        expect(plain>=19.&&plain<=21.,"plain pulses "+out.dump());
        expect(gold>=23.&&gold<=26.,"marigold pulses (x0.8 interval) "+out.dump());
        expect(slow>=14.&&slow<=16.,"pressure pulses (x1.3 interval) "+out.dump());
        return out;
    }));
    auto door=[](const J& d){
        Fixture f(d);auto& m=*f.match;f.plant("激光豆",1512.,1.);const double tile=m.battle.runtime.tile;
        auto z=f.zombie("钢门普通僵尸",1512.+12.*tile,-1.);z->native.move_speed.set(.001);
        const double hand=z->body.hand_hp,body=z->body.hp;f.fire(Point{1512.+15.*tile,925.});f.run(305);
        return J{{"hand_lost",hand-z->body.hand_hp},{"body_lost",body-z->body.hp}};
    };
    rows.push_back(scenario("door.pierce_unless_king",[&](){
        const J plain=door(decks({"plant:激光豆"},{"zombie:脑光墓碑","zombie:钢门普通僵尸"}));
        const J king=door(decks({"plant:激光豆"},{"zombie:脑光墓碑","zombie:钢门普通僵尸","zsecret:僵王出品"}));
        expect(plain["hand_lost"].get<double>()<1e-9&&plain["body_lost"].get<double>()>0.,"laser did not pierce the door "+plain.dump());
        expect(king["hand_lost"].get<double>()>0.,"僵王出品 door did not block "+king.dump());
        return J{{"plain",plain},{"king",king}};
    }));
    auto reed=[](const J& d){
        Fixture f(d);auto& m=*f.match;f.plant("闪电芦苇",1512.,1.);const double tile=m.battle.runtime.tile;
        auto z=f.zombie("钢门普通僵尸",1512.+6.*tile,-1.);z->native.move_speed.set(.001);
        const double hand=z->body.hand_hp,body=z->body.hp;f.run(800);
        return J{{"hand_lost",hand-z->body.hand_hp},{"body_lost",body-z->body.hp}};
    };
    rows.push_back(scenario("reed.reference",[&](){
        // Reference only (not a PvP76 change): how the lightning reed treats the same door.
        const J plain=reed(decks({"plant:闪电芦苇"},{"zombie:脑光墓碑","zombie:钢门普通僵尸"}));
        const J king=reed(decks({"plant:闪电芦苇"},{"zombie:脑光墓碑","zombie:钢门普通僵尸","zsecret:僵王出品"}));
        return J{{"plain",plain},{"king",king}};
    }));
    auto focus=[](const J& d){
        Fixture f(d);auto& m=*f.match;f.plant("激光豆",1512.,1.);const double tile=m.battle.runtime.tile;
        auto z=f.zombie("铁桶僵尸",1512.+12.*tile,-1.);z->native.move_speed.set(.001);z->body.armor_hp=0.;z->body.armor.clear();
        z->max_hp.set(1000.);z->body.hp=500.;f.fire(Point{1512.+15.*tile,925.});
        const double before=z->body.hp;f.run(105);return before-z->body.hp;
    };
    rows.push_back(scenario("focus.missing_health",[&](){
        const double without=focus(decks({"plant:激光豆"},{"zombie:脑光墓碑","zombie:铁桶僵尸"}));
        const double with=focus(decks({"plant:激光豆","secret:聚能"},{"zombie:脑光墓碑","zombie:铁桶僵尸"}));
        // One pulse: 2% of the 500 missing = 10 extra.
        near(with-without,10.,"聚能 extra",0.6);
        // Zombie Dave keeps the fixed 1 point.
        Fixture f(decks({"plant:激光豆","secret:聚能"},{"zombie:脑光墓碑","zombie:普通僵尸"}));auto& m=*f.match;f.plant("激光豆",1512.,1.);const double tile=m.battle.runtime.tile;
        auto& hero=m.battle.heroes.hero(Seat::zombie);hero.frame.hp.get()=10.;f.hero_at(Seat::zombie,1512.+12.*tile);
        f.fire(Point{1512.+14.*tile,960.-tile*.8});f.hero_at(Seat::zombie,1512.+12.*tile);const double hp=hero.frame.hp.get();
        f.run(105);f.hero_at(Seat::zombie,1512.+12.*tile);near(hp-hero.frame.hp.get(),1.,"Dave per pulse with 聚能");
        return J{{"without",without},{"with",with},{"focus_hits",m.pvp75.focus_hits}};
    }));
    return rows;
}
J guard(){
    J rows=J::array();
    auto cycle=[](const J& d){
        Fixture f(d);auto& m=*f.match;auto z=f.zombie("盾卫僵尸",1800.,-1.);z->native.move_speed.set(.001);
        f.run(3);z->body.hp-=1.;J out;int64_t start=m.battle.heroes.tick,guarding=-1,cooldown=-1,ready=-1;double defense=0.;
        for(int i=0;i<4000&&ready<0;++i){f.run(1);const auto t=m.battle.heroes.tick-start;
            if(guarding<0&&z->pvp75.guard==GuardPhase::guarding){guarding=t;defense=z->body.defense.get();}
            if(guarding>=0&&cooldown<0&&z->pvp75.guard==GuardPhase::cooldown)cooldown=t;
            if(cooldown>=0&&z->pvp75.guard==GuardPhase::ready)ready=t;}
        return J{{"guarding_at",guarding},{"cooldown_at",cooldown},{"ready_at",ready},{"defense",defense},{"cooldown_ticks",ready-cooldown}};
    };
    rows.push_back(scenario("guard.secret",[&](){
        const J plain=cycle(decks({"plant:向日葵"},{"zombie:脑光墓碑","zombie:盾卫僵尸"}));
        const J secret=cycle(decks({"plant:向日葵"},{"zombie:脑光墓碑","zombie:盾卫僵尸","zsecret:守卫"}));
        near(plain["defense"].get<double>(),60.,"plain guard defense");near(secret["defense"].get<double>(),600.,"守卫 guard defense");
        expect(std::abs(plain["cooldown_ticks"].get<double>()-1000.)<=3.,"plain cooldown "+plain.dump());
        expect(std::abs(secret["cooldown_ticks"].get<double>()-500.)<=3.,"守卫 cooldown "+secret.dump());
        return J{{"plain",plain},{"secret",secret}};
    }));
    return rows;
}
J terraria(){
    J rows=J::array();
    rows.push_back(scenario("world_eater.enemy_cache_equivalence",[](){
        // Same seed and inputs with and without the per-frame enemy listing cache.
        auto run=[](bool cache){
            if(cache)env_set_u8("PVP76_TERRARIA_CACHE","1");else env_set_u8("PVP76_TERRARIA_CACHE","0");
            Fixture f;auto& m=*f.match;for(double x:{1400.,1500.,1600.,1700.})f.plant("向日葵",x,1.);
            auto id=m.spawn_unit("zombie:世界吞噬者","zombie",2000.,900.,-1.,false);expect(bool(id),"worm");f.run(3000);
            J digest=J::array();for(const auto& t:*m.battle.targets)if(t.unit){const auto& mo=t.unit->body.motion.get();digest.push_back({std::round(mo.x*1000.),std::round(mo.y*1000.),t.unit->body.hp});}
            for(const auto& p:*m.battle.plant_roster)digest.push_back({p->hp.or_missing(0.)});
            return digest;
        };
        const J a=run(true),b=run(false);env_set_u8("PVP76_TERRARIA_CACHE","1");
        expect(a==b,"cache changed the outcome");return J{{"entries",a.size()}};
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
    const char* only=std::getenv("PVP76_AUDIT_CASE");
    for(auto [name,fn]:std::vector<std::pair<std::string,J(*)()>>{{"卡表",catalog},{"战斗",combat},{"激光豆",laser},{"盾卫守卫",guard},{"泰拉",terraria}}){
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
