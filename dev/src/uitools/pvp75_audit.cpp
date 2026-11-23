// PvP75 focused mechanics on the production match composition (same kernel and
// composition as the shipped Session): new cards, balance and interaction rules.
#define content_phase_unused_main pvp75_audit_content_phase_main
#define TYPED72_NO_MAIN
#include "match_probe.cpp"
#include "sim/typed72_app/cold_export.h"
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
struct Fixture {
    std::unique_ptr<MatchProbe> match;
    std::optional<NativeBirthScope> births;
    // variant "trinity": a 海陆空 zombie deck (land 普通, water 海豚, air 克苏鲁之仆).
    explicit Fixture(bool test_mode=true,const std::string& variant=""){
        static std::map<std::string,typed72app::ColdExport> colds;
        const auto cache_key=std::string(test_mode?"t":"f")+variant;
        auto found=colds.find(cache_key);
        if(found==colds.end()){
            auto handle=battle_from_scenario({{"fixture_flat",true},{"durable_heroes",true},{"seed",75001},
                {"rules",{{"local_test_mode",test_mode}}},
                {"decks",variant=="trinity"?J{{"plant",{"plant:向日葵","plant:豌豆射手"}},{"zombie",{"zombie:脑光墓碑","zombie:普通僵尸","zombie:海豚僵尸","zombie:克苏鲁之仆","zsecret:海陆空"}}}:J{{"plant",{"plant:激光豆","plant:巴豆","plant:杨桃","plant:向日葵","secret:大帝"}},{"zombie",{"zombie:脑光墓碑","zombie:盾卫僵尸","zombie:克苏鲁之仆","zombie:雪橇车小队"}}}}});
            found=colds.emplace(cache_key,typed72app::export_cold(handle.battle,75001)).first;
            callm(handle.battle,SY("close"),Args{});
        }
        const auto& cold=found->second;const auto& c=cold.cold;
        match=std::make_unique<MatchProbe>(75001,c.at("battle").at("width").get<double>(),c.at("battle").at("rules").at("melon_splash_damage").get<double>());
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
    ZombieRef zombie(std::string name,double x=1656.,double facing=-1.){
        auto& m=*match;auto id=m.spawn_unit("zombie:"+name,"zombie",x,960.,facing,false);
        expect(bool(id),"zombie spawn "+name);auto z=std::get<ZombieRef>(m.battle.native_objects.get(*id).value());
        z->native.entry.set(500.);z->body.motion.get()={x,960.,0.,0.};return z;
    }
    // Room steps until at least `ticks` native ticks have passed.
    void run(int64_t ticks){auto& m=*match;const auto end=m.battle.heroes.tick+ticks;int guard=0;while(m.battle.heroes.tick<end&&++guard<100000)m.scheduler.step();}
    std::string command(NativeCommandKind kind,std::optional<Point> p={},Seat seat=Seat::plant){
        NativeCommand c{kind};
        if(p){c.x={InputFieldState::value,p->x};c.y={InputFieldState::value,p->y};}
        return match->native_commands.apply(seat,c);
    }
    size_t index(const ZombieRef& z){auto& t=*match->battle.targets;for(size_t i=0;i<t.size();++i)if(t[i].unit==z)return i;throw std::runtime_error("unit not in roster");}
};
template<class F> J scenario(const std::string& id,F run){
    J row={{"id",id}};
    try{row.update(run());row["passed"]=true;}
    catch(const std::exception& e){row["passed"]=false;row["error"]=e.what();}
    return row;
}
J catalog(){
    J rows=J::array();
    rows.push_back(scenario("cold.costs_cooldowns",[](){
        Fixture f;auto& m=*f.match;J out;
        const std::vector<std::tuple<std::string,double,double>> want{
            {"plant:巴豆",40,36},{"plant:激光豆",200,32} /* PvP76: 32 s */,{"zombie:盾卫僵尸",150,12},{"zombie:克苏鲁之仆",0,32},
            {"zombie:小鬼僵尸",50,8},{"zombie:黑普通僵尸",50,-1},{"zombie:海豚僵尸",40,-1},{"zombie:撑杆跳僵尸",50,-1},{"plant:杨桃",300,-1}};
        for(const auto& [key,cost,cd]:want){
            const auto card=m.catalog.resolve(key,{},{},false);
            near(card.cost,cost,key+" cost");if(cd>=0.)near(card.cooldown,cd,key+" cooldown");
            out[key]={{"cost",card.cost},{"cooldown",card.cooldown}};
        }
        const std::vector<std::string> emperor{"secret:大帝"};
        near(m.catalog.resolve("plant:杨桃",emperor,{},false).cost,300.,"大帝 keeps the starfruit cost");
        near(m.catalog.at("zombie:盾卫僵尸").defense.get(),12.,"盾卫 defense (PvP76 r3: 12)");
        expect(m.catalog.at("plant:三叶草").allow_air.or_missing(false),"三叶草 allow_air");
        return out;
    }));
    rows.push_back(scenario("v.runtime_catalog",[](){
        J out;for(const char* key:{"plant:巴豆","plant:激光豆","zombie:盾卫僵尸","zombie:克苏鲁之仆"}){
            const V card=rd(pm_catalog::CARDS,V(key));expect(card.truthy(),std::string("V card ")+key);
            out[key]={{"cost",rd(card,V("cost")).num()},{"cooldown",rd(card,V("cooldown")).num()},{"behavior",py_str(rd(card,V("behavior")))}};
        }
        expect(py_str(rd(pm_catalog::RULES,V("ruleset")))=="pvp76","ruleset");  // PvP76 ruleset
        return out;
    }));
    return rows;
}
J croton(){
    J rows=J::array();
    rows.push_back(scenario("bite.consumes_and_poisons",[](){
        Fixture f;auto& m=*f.match;
        auto bean=f.plant("巴豆");const double x=1512.;
        auto biter=f.zombie("铁桶僵尸",x,-1.);biter->native.biting.set(0.);
        auto behind=f.zombie("普通僵尸",x+2.5*48.,-1.);auto front=f.zombie("普通僵尸",x-3.*48.,-1.);
        // 60 gas damage kills an ordinary zombie outright: give the one behind room to show damage + poison.
        behind->body.hp=1000.;behind->max_hp.set(1000.);
        const double before=total(biter),behind_before=total(behind);
        {HeroContext ctx(m.world,{Seat::plant,Seat::zombie,CombatPhase::zombies,source_ref(biter),{}});m.mobile.advance(f.index(biter));}
        expect(bean->dead.present(),"巴豆 not consumed by the first bite");
        expect(m.battle.pvp75.bites.size()==1,"bite not handed over");
        f.run(60);
        near(before-total(biter),150.,"biter damage");
        expect(biter->body.stun.or_missing(0.)>1300.,"biter stun "+std::to_string(biter->body.stun.or_missing(0.)));
        const auto& biter_poison=biter->poison.poison;
        expect(biter_poison.present()&&!biter_poison.is_null()&&biter_poison.get()&&biter_poison.get()->level.or_missing(0)==2,"biter level-2 poison");
        f.run(200);
        expect(behind->body.stun.or_missing(0.)>0.,"zombie behind the biter not stunned by gas");
        const auto& p2=behind->poison.poison;expect(p2.present()&&!p2.is_null()&&p2.get()&&p2.get()->level.or_missing(0)>=1,"gas poison: hp "+std::to_string(behind->body.hp)+" stun "+std::to_string(behind->body.stun.or_missing(0.))+" poison "+(p2.present()&&!p2.is_null()&&p2.get()?std::to_string(p2.get()->level.or_missing(-1)):std::string("none")));
        expect(front->body.stun.or_missing(0.)<=0.,"gas reached the biter's front");
        expect(behind_before-total(behind)>=59.9,"gas damage "+std::to_string(behind_before-total(behind)));
        return J{{"biter_stun",biter->body.stun.or_missing(0.)},{"behind_stun",behind->body.stun.or_missing(0.)},{"gas_damage",behind_before-total(behind)},{"gas",m.battle.pvp75.gases.size()}};
    }));
    rows.push_back(scenario("bite.asleep_is_ordinary_food",[](){
        Fixture f;auto& m=*f.match;auto bean=f.plant("巴豆");bean->sleep.set(1.);
        auto biter=f.zombie("普通僵尸",1512.,-1.);biter->native.biting.set(0.);
        {HeroContext ctx(m.world,{Seat::plant,Seat::zombie,CombatPhase::zombies,source_ref(biter),{}});m.mobile.advance(f.index(biter));}
        expect(m.battle.pvp75.bites.empty(),"sleeping 巴豆 triggered");return J{{"hp",bean->hp.get()}};
    }));
    return rows;
}
J laser(){
    J rows=J::array();
    rows.push_back(scenario("aim.fire.stop",[](){
        Fixture f;auto& m=*f.match;auto bean=f.plant("激光豆",1512.,1.);const double tile=m.battle.runtime.tile;
        auto target=f.zombie("铁桶僵尸",1512.+10.*tile,-1.);
        const auto click=Point{1512.,940.};
        expect(f.command(NativeCommandKind::laser,Point{1512.+10.*tile,940.}).size()>0,"point accepted without an aimed bean");
        expect(f.command(NativeCommandKind::laser,click).empty(),"aim rejected");
        expect(m.room.players[0].laser_aim.has_value()&&bean->pvp75.aimed,"aim state missing");
        const auto near_error=f.command(NativeCommandKind::laser,Point{1512.+4.*tile,940.});
        expect(!near_error.empty()&&!m.room.players[0].laser_aim,"too-close point must cancel: "+near_error);
        expect(f.command(NativeCommandKind::laser,click).empty(),"re-aim");
        expect(!f.command(NativeCommandKind::laser,Point{1512.-10.*tile,940.}).empty(),"behind the bean accepted");
        expect(f.command(NativeCommandKind::laser,click).empty(),"re-aim 2");
        const Point aim{1512.+15.*tile,925.};
        expect(f.command(NativeCommandKind::laser,aim).empty(),"fire rejected");
        expect(bean->pvp75.firing&&!m.room.players[0].laser_aim,"not firing");
        const double before=total(target);f.run(205);
        const auto eye=pvp75::laser_eye(*bean,tile);
        const double cells=std::hypot(aim.x-eye.x,aim.y-eye.y)/tile,pulse=30./cells;
        const double lost=before-total(target);
        expect(lost>pulse*1.5&&lost<pulse*3.5,"beam damage "+std::to_string(lost)+" pulse "+std::to_string(pulse));
        expect(f.command(NativeCommandKind::laser,click).empty()&&!bean->pvp75.firing,"click did not stop the beam");
        const double after=total(target);f.run(205);near(total(target),after,"damage after stop");
        // A sleeping bean drops its beam.
        expect(f.command(NativeCommandKind::laser,click).empty()&&f.command(NativeCommandKind::laser,aim).empty(),"refire");
        bean->sleep.set(1.);f.run(110);expect(!bean->pvp75.firing,"sleep kept the beam");
        return J{{"pulse",pulse},{"lost",lost},{"cells",cells}};
    }));
    rows.push_back(scenario("hero.one_point",[](){
        Fixture f;auto& m=*f.match;auto bean=f.plant("激光豆",1512.,1.);const double tile=m.battle.runtime.tile;
        auto& hero=m.battle.heroes.hero(Seat::zombie);auto& pos=*hero.frame.position.get();pos.x=1512.+12.*tile;pos.y=960.;pos.vx=pos.vy=0.;
        const double hp=hero.frame.hp.get();
        expect(f.command(NativeCommandKind::laser,Point{1512.,940.}).empty(),"aim");
        expect(f.command(NativeCommandKind::laser,Point{1512.+14.*tile,960.-tile*.8}).empty(),"fire at hero");
        pos.x=1512.+12.*tile;pos.y=960.;
        f.run(105);pos.x=1512.+12.*tile;pos.y=960.;
        const double lost=hp-hero.frame.hp.get();
        expect(lost==1.,"hero damage per pulse "+std::to_string(lost));
        expect(hero.frame.down.or_missing(0.)<=0.,"laser knocked the hero down");
        return J{{"lost",lost}};
    }));
    return rows;
}
J guard(){
    J rows=J::array();
    rows.push_back(scenario("poison.tints.shield.art",[](){
        // The content gate tints 普通僵尸-身/首 first; the 盾卫 aliases must not drop that tint.
        Fixture f;auto& m=*f.match;auto z=f.zombie("盾卫僵尸",1800.,-1.);
        m.poison.apply(CombatTarget::zombie(z),2,6.,Seat::plant);f.run(2);
        // What was drawn for this zombie in the last frame: shield art carrying the level-2 tint.
        const auto id=z->source.id.or_missing(std::string{});int drawn=0,tinted=0,shield=0,both=0;
        for(const auto& c:m.canvas.frames.frame().commands){
            if(!c.image||c.entity!=id)continue;++drawn;const auto text=m.canvas.describe(c.image).dump();
            const bool t=text.find("[170,70,230]")!=std::string::npos,s=text.find("盾卫僵尸")!=std::string::npos;tinted+=t;shield+=s;both+=t&&s;
        }
        J seen={{"drawn",drawn},{"tinted",tinted},{"shield",shield},{"shield_and_tinted",both}};
        expect(drawn>0&&shield>0,"guard not drawn with its shield art: "+seen.dump());
        expect(both>0,"guard art not poison-tinted: "+seen.dump());
        return J{{"art",seen}};
    }));
    rows.push_back(scenario("raise.guard.cooldown",[](){
        Fixture f;auto& m=*f.match;auto z=f.zombie("盾卫僵尸",1800.,-1.);
        near(z->body.defense.get(),12.,"base defense (PvP76 r3: 12)");near(z->body.hp,160.,"hp");
        const double speed=z->native.move_speed.get();
        f.run(3);z->body.hp-=1.;f.run(3);
        expect(z->pvp75.guard==GuardPhase::raising,"hit did not raise the shield");
        near(z->body.defense.get(),12.,"defense during the raise");
        f.run(160);
        expect(z->pvp75.guard==GuardPhase::guarding,"not guarding after 0.6 s");
        near(z->body.defense.get(),60.,"guard defense");near(z->native.move_speed.get(),speed*.6,"guard speed (-40%)");
        const auto vx=z->body.motion.get().vx;m.content_damage.knockback(f.index(z),500.);near(z->body.motion.get().vx,vx,"knockback while guarding");
        f.run(1500);
        expect(z->pvp75.guard==GuardPhase::cooldown,"guard did not end after 6 s");
        near(z->body.defense.get(),12.,"defense restored");near(z->native.move_speed.get(),speed,"speed restored");
        z->body.hp-=1.;f.run(20);expect(z->pvp75.guard==GuardPhase::cooldown,"raised during cooldown");
        f.run(880);expect(z->pvp75.guard==GuardPhase::cooldown,"cooldown ended before 4 s");
        f.run(150);expect(z->pvp75.guard==GuardPhase::ready,"cooldown did not end after 4 s");
        return J{{"speed",speed}};
    }));
    return rows;
}
J bosses(){
    J rows=J::array();
    rows.push_back(scenario("terraria.control_to_slow",[](){
        Fixture f;auto& m=*f.match;auto eye=m.terraria.summon(4,{1800.,600.});expect(bool(eye),"eye summon");
        eye->body.stun.set(500.);eye->body.butter.set(300.);eye->body.ice.set(2500.);
        m.terraria.advance();
        expect(eye->body.stun.or_missing(0.)<=0.&&eye->body.butter.or_missing(0.)<=0.,"control kept");
        expect(eye->body.ice.or_missing(0.)>0.&&eye->body.ice.or_missing(0.)<=1000.,"not slowed "+std::to_string(eye->body.ice.or_missing(0.)));
        const double held=eye->body.ice.or_missing(0.)+eye->pvp75.boss_slow;
        expect(held>=2400.,"slow shorter than the freeze: "+std::to_string(held));
        return J{{"ice",eye->body.ice.or_missing(0.)},{"boss_slow",eye->pvp75.boss_slow}};
    }));
    return rows;
}
J servant(){
    J rows=J::array();
    rows.push_back(scenario("pvp.deploy_any_point",[](){
        Fixture f(false);auto& m=*f.match;expect(!m.battle.local_test_mode,"fixture in test mode");
        auto id=m.spawn_unit("zombie:克苏鲁之仆","zombie",1700.,700.,-1.,false);
        expect(bool(id),"servant not summoned outside test mode");
        auto u=std::get<ZombieRef>(m.battle.native_objects.get(*id).value());
        expect(u->terraria&&u->terraria->type==5,"not a servant");near(u->body.hp,8.,"servant hp");
        const auto start=u->body.motion.get();f.run(250);
        expect(u->body.hp>0.,"servant died");const auto moved=std::hypot(u->body.motion.get().x-start.x,u->body.motion.get().y-start.y);
        expect(moved>1.,"servant did not move");
        return J{{"moved",moved}};
    }));
    rows.push_back(scenario("trinity.servant_is_air",[](){
        Fixture f(false,"trinity");auto& m=*f.match;
        auto id=m.spawn_unit("zombie:克苏鲁之仆","zombie",1700.,700.,-1.,false);expect(bool(id),"servant not summoned");
        auto u=std::get<ZombieRef>(m.battle.native_objects.get(*id).value());
        near(u->body.hp,12.,"servant hp with 海陆空 (8 x 1.5)");
        return J{{"hp",u->body.hp}};
    }));
    return rows;
}
J balance(){
    J rows=J::array();
    rows.push_back(scenario("sled_squad.one_per_second",[](){
        Fixture f;auto& m=*f.match;f.zombie("雪橇车小队",1800.,-1.);
        const auto count=[&]{size_t n=0;for(const auto& t:*m.battle.targets)if(t.unit&&t.unit->source.content.or_missing("")=="雪橇车小队僵尸")++n;return n;};
        J seen=J::array();for(int i=0;i<4;++i){seen.push_back(count());f.run(250);}
        expect(seen==J::array({0,1,2,3}),"stagger "+seen.dump());
        return J{{"counts",seen}};
    }));
    rows.push_back(scenario("starfruit.pierce",[](){
        J out;for(bool emperor:{false,true}){
            Fixture f;auto& m=*f.match;auto& secrets=m.battle.heroes.players.at(seat_index(Seat::plant))->secrets;
            if(emperor)secrets.push_back("secret:大帝");else std::erase(secrets,"secret:大帝");
            std::vector<ZombieRef> pile;for(int i=0;i<6;++i){auto z=f.zombie("铁桶僵尸",1800.,-1.);z->native.move_speed.set(0.);pile.push_back(z);}
            const double x=1800.,y=960.-48.*.8;
            {HeroContext ctx(m.world,{Seat::zombie,Seat::plant,CombatPhase::plants,{},{}});m.bonus_plants.spawn_stars({x,y},1.,1.);}
            auto star=m.battle.runtime.entities.list()->back();star->source.seat=Seat::plant;
            m.bonus_plants.star_damage();
            size_t hit=0;for(const auto& z:pile)if(total(z)<1000.-1e-9)++hit;
            const size_t want=emperor?4:3;
            expect(star->bonus.star_hits.get().size()==want,"star hits "+std::to_string(star->bonus.star_hits.get().size()));
            near(star->expires.or_missing(0.),1024.,"star not cleared");
            out[emperor?"emperor":"plain"]=star->bonus.star_hits.get().size();
        }
        return out;
    }));
    rows.push_back(scenario("blover.untargetable_air",[](){
        Fixture f;auto blover=f.plant("三叶草");
        expect(!september_targetable(*blover)&&untargetable_plant(*blover),"三叶草 targetable");
        return J{{"targetable",false}};
    }));
    rows.push_back(scenario("carts.health",[](){
        Fixture f;auto cart=f.zombie("投篮车僵尸",1900.,-1.),cannon=f.zombie("小鬼炮",2100.,-1.);
        near(cart->body.hp,225.,"投篮车 hp");near(cannon->body.hp,120.,"小鬼炮 hp");
        near(cart->max_hp.get(),225.,"投篮车 max");near(cannon->max_hp.get(),120.,"小鬼炮 max");
        return J{{"cart",cart->body.hp},{"cannon",cannon->body.hp}};
    }));
    rows.push_back(scenario("subsidy.six_second_bonus",[](){
        J out;for(bool crowded:{false,true}){
            Fixture f;auto& m=*f.match;m.economy_state.subsidy=true;
            if(crowded){auto z=f.zombie("普通僵尸",2400.,-1.);z->native.move_speed.set(.001);}
            std::optional<int64_t> day,bonus;J deltas=J::array();
            auto& account=m.resources.accounts[seat_index(Seat::zombie)];
            for(int i=0;i<4000&&!(day&&bonus);++i){
                const double before=account.earned;m.scheduler.step();const double delta=account.earned-before;
                if(delta>0.){deltas.push_back({m.battle.heroes.tick,delta});
                    if(std::fmod(delta,25.)==0.&&!day)day=m.battle.heroes.tick;else if(std::fmod(delta,15.)==0.&&!bonus)bonus=m.battle.heroes.tick;}
                if(day&&m.battle.heroes.tick>*day+2500)break;
            }
            out[crowded?"crowded_deltas":"empty_deltas"]=deltas;
            expect(bool(day),"no periodic brain payment");
            if(crowded)expect(!bonus,"subsidy paid with an own zombie on the field");
            else{expect(bool(bonus),"no subsidy bonus");expect(std::abs(double(*bonus-*day)-1500.)<=20.,"bonus delay "+std::to_string(*bonus-*day));}
            out[crowded?"crowded":"empty"]={{"day",*day},{"bonus",bonus?J(*bonus):J(nullptr)}};
        }
        return out;
    }));
    rows.push_back(scenario("cannon.reload_32s",[](){
        Fixture f;auto& m=*f.match;auto cannon=f.plant("玉米加农炮");cannon->cannon_cd.set(9000.);
        m.bonus_projectiles.patch_cannons();near(cannon->cannon_cd.get(),8000.,"reload ticks");return J{{"cd",8000}};
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
    const J packaged=data::module("catalog").at("CARDS");
    J runtime=J::parse(dump(pm_catalog::CARDS));
    for(auto it=runtime.begin();it!=runtime.end();){if(it.value().value("behavior",std::string{})=="terraria")it=runtime.erase(it);else ++it;}
    std::ofstream(out/"catalog-diff.json")<<J::diff(packaged,runtime).dump(2);
    J result={{"checks",J::array()},{"failures",0}};int failures=0;
    const char* only=std::getenv("PVP75_AUDIT_CASE");
    for(auto [name,fn]:std::vector<std::pair<std::string,J(*)()>>{{"卡表",catalog},{"巴豆",croton},{"激光豆",laser},{"盾卫僵尸",guard},{"Boss控制",bosses},{"克苏鲁之仆",servant},{"平衡",balance}}){
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
