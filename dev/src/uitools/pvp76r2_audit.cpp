// PvP76 r2 focused mechanics on the production match composition (same kernel and
// composition as the shipped Session).
//   pvp76r2_audit <out-folder>          (PVP76R2_AUDIT_CASE=<name> runs one group)
#define content_phase_unused_main pvp76r2_audit_content_phase_main
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
            J sc={{"fixture_flat",true},{"durable_heroes",true},{"seed",76201},{"rules",{{"local_test_mode",false}}},{"decks",d}};
            for(const auto& [k,v]:extra.items())sc[k]=v;
            auto handle=battle_from_scenario(sc);
            found=colds.emplace(cache_key,typed72app::export_cold(handle.battle,76201)).first;
            callm(handle.battle,SY("close"),Args{});
        }
        const auto& cold=found->second;const auto& c=cold.cold;
        match=std::make_unique<MatchProbe>(76201,c.at("battle").at("width").get<double>(),c.at("battle").at("rules").at("melon_splash_damage").get<double>());
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

J catalog(){
    J rows=J::array();
    rows.push_back(scenario("servant.cooldown_24",[](){
        Fixture f(decks({"plant:向日葵"},{"zombie:脑光墓碑","zombie:克苏鲁之仆"}));auto& m=*f.match;
        const auto plain=m.catalog.resolve("zombie:克苏鲁之仆",{},{},false);
        const std::vector<std::string> rush{"zsecret:加急"};const auto fast=m.catalog.resolve("zombie:克苏鲁之仆",rush,{},false);
        near(plain.cooldown,24.,"servant cooldown");near(fast.cooldown,18.,"servant cooldown with 加急");
        const V card=rd(pm_catalog::CARDS,V("zombie:克苏鲁之仆"));near(rd(card,V("cooldown")).num(),24.,"V servant cooldown");
        return J{{"typed",plain.cooldown},{"rush",fast.cooldown}};
    }));
    rows.push_back(scenario("sprint.carts_cost",[](){
        Fixture f(decks({"plant:向日葵"},{"zombie:脑光墓碑","zombie:投篮车僵尸"}));auto& m=*f.match;J out;
        for(const char* key:{"zombie:投篮车僵尸","zombie:小鬼炮","zombie:雪橇车僵尸","zombie:滚桶僵尸"}){
            const double base=m.catalog.resolve(key,{},{},false).cost;
            const std::vector<std::string> sprint{"zsecret:大运！小子"};const double with=m.catalog.resolve(key,sprint,{},false).cost;
            near(with-base,50.,std::string(key)+" 大运 surcharge");out[key]={base,with};
        }
        const std::vector<std::string> both{"zsecret:大运！小子","zsecret:坤坤"};
        near(m.catalog.resolve("zombie:投篮车僵尸",both,{},false).cost,400.,"坤坤 350 + 大运 50");
        // V (UI) catalogue agrees.
        const V secrets=V::list({V("zsecret:大运！小子")});
        for(const char* key:{"zombie:投篮车僵尸","zombie:小鬼炮"})
            near(rd(pm_catalog::f_actual_card(Args{V(key),secrets}),V("cost")).num(),out[key][1].get<double>(),std::string("V ")+key);
        return out;
    }));
    rows.push_back(scenario("rush.every_zombie_card",[](){
        Fixture f(decks({"plant:向日葵"},{"zombie:脑光墓碑","zombie:普通僵尸"}));auto& m=*f.match;
        J covered=J::array(),graves=J::array();const std::vector<std::string> rush{"zsecret:加急"};
        for(const auto& card:m.catalog.data().cards){
            if(card.side!="zombie"||card.category=="secret"||!card.selectable||card.id!=card.base_id)continue;
            if(!m.catalog.allowed(card.id,{},false,{}))continue;
            const auto plain=m.catalog.resolve(card.id,{},{},false),fast=m.catalog.resolve(card.id,rush,{},false);
            if(card.behavior=="grave"){near(fast.cooldown,plain.cooldown,card.id+" grave unaffected");graves.push_back(card.id);continue;}
            if(plain.cooldown<=0.)continue;
            near(fast.cooldown,plain.cooldown*.75,card.id+" 加急",1e-9);covered.push_back(card.id);
        }
        for(const char* key:{"zombie:盾卫僵尸","zombie:克苏鲁之仆"})expect(std::find(covered.begin(),covered.end(),J(key))!=covered.end(),std::string("加急 misses ")+key);
        return J{{"covered",covered.size()},{"graves_exempt",graves.size()},{"cards",covered}};
    }));
    return rows;
}

J carts(){
    J rows=J::array();
    // Cart vx while advancing toward the zombie Dave (follow command, Dave far to the left).
    auto speed=[](const char* key,bool sprint){
        J zombies={"zombie:脑光墓碑",std::string("zombie:")+key};if(sprint)zombies.push_back("zsecret:大运！小子");
        Fixture f(decks({"plant:向日葵"},zombies));auto& m=*f.match;f.hero_at(Seat::zombie,700.);f.hero_at(Seat::plant,6000.);
        auto z=f.zombie(key,2600.,-1.);double vx=0.;
        for(int i=0;i<60;++i){f.run(5);vx=std::max(vx,std::abs(z->body.motion.get().vx));}
        return std::pair<double,double>(vx,m.battle.runtime.plk);
    };
    rows.push_back(scenario("carts.half_speed_and_sprint",[&](){
        const auto [basket,plk]=speed("投篮车僵尸",false);const auto [basket2,plk2]=speed("投篮车僵尸",true);
        const auto [cannon,plk3]=speed("小鬼炮",false);const auto [cannon2,plk4]=speed("小鬼炮",true);
        J out={{"plk",plk},{"basket",basket},{"basket_sprint",basket2},{"cannon",cannon},{"cannon_sprint",cannon2}};
        near(basket,plk*20.,"投篮车 vx (was plk*40) "+out.dump(),1e-9);near(basket2,plk*40.,"投篮车 with 大运 "+out.dump(),1e-9);
        expect(cannon>0.,"小鬼炮 did not move "+out.dump());near(cannon2,cannon*2.,"小鬼炮 with 大运 "+out.dump(),1e-9);
        (void)plk2;(void)plk3;(void)plk4;return out;
    }));
    rows.push_back(scenario("carts.cannon_template_half",[](){
        Fixture f(decks({"plant:向日葵"},{"zombie:脑光墓碑","zombie:小鬼炮","zombie:撑杆跳僵尸"}));
        auto pole=f.zombie("撑杆跳僵尸",2000.,-1.);auto cannon=f.zombie("小鬼炮",2400.,-1.);
        const double a=pole->native.move_speed.or_missing(0.),b=cannon->native.move_speed.or_missing(0.);
        J out={{"pole_speed",a},{"cannon",b}};expect(a>0.&&std::abs(b-a*.5)<=std::abs(a)*.15,"cannon speed not about half the pole template "+out.dump());
        return out;
    }));
    return rows;
}

J kunkun(){
    J rows=J::array();
    // A cart left of four wall-nuts, the zombie Dave far right. order: 0 attack, 1 follow, 2 rally (far right).
    auto run=[](bool kun,int order){
        J zombies={"zombie:脑光墓碑","zombie:投篮车僵尸"};if(kun)zombies.push_back("zsecret:坤坤");
        Fixture f(decks({"plant:坚果"},zombies));auto& m=*f.match;const double tile=f.tile();
        f.hero_at(Seat::zombie,1200.+30.*tile);f.hero_at(Seat::plant,1200.-30.*tile);
        for(int i=0;i<4;++i)f.plant("坚果",1200.+double(i)*tile,1.);
        m.commands.shared=order==1?PathMode::follow_hero:PathMode::attack_plants;
        if(order==2)m.hero_flags.shared=Point{(std::trunc((1200.+40.*tile)/tile)+.5)*tile,(std::trunc(940./tile)+.5)*tile};
        auto z=f.zombie("投篮车僵尸",1200.+12.*tile,-1.);J trace=J::array();
        for(int i=0;i<16;++i){f.run(250);f.hero_at(Seat::zombie,1200.+30.*tile);trace.push_back({std::round(z->body.motion.get().x*1000.)/1000.,z->body.facing,z->native.basketball_total.or_missing(-1.)});}
        return J{{"x",z->body.motion.get().x},{"thrown",48.-z->native.basketball_total.or_missing(48.)},{"trace",trace},{"tile",tile}};
    };
    rows.push_back(scenario("cart.plain_obeys_orders",[&](){
        const J attack=run(false,0),follow=run(false,1),rally=run(false,2);const double tile=attack["tile"];
        J out={{"attack",attack},{"follow",follow},{"rally",rally}};
        expect(attack["thrown"].get<double>()>0.,"plain cart did not attack "+out.dump());
        for(const auto* k:{"follow","rally"}){
            expect(out[k]["x"].get<double>()>1200.+16.*tile,std::string("plain cart ignored ")+k+" "+out.dump());
            expect(out[k]["thrown"].get<double>()==0.,std::string("plain cart threw under ")+k+" "+out.dump());
        }
        return out;
    }));
    rows.push_back(scenario("cart.kunkun_ignores_orders",[&](){
        const J attack=run(true,0),follow=run(true,1),rally=run(true,2);
        J out={{"attack",attack},{"follow",follow},{"rally",rally}};
        expect(attack["thrown"].get<double>()>0.,"坤坤 cart did not attack "+out.dump());
        // Same seed and inputs: under follow or a rally flag it behaves exactly as under attack.
        expect(follow["trace"]==attack["trace"],"坤坤 cart obeyed follow "+out.dump());
        expect(rally["trace"]==attack["trace"],"坤坤 cart obeyed the rally flag "+out.dump());
        return out;
    }));
    return rows;
}
J grenade(){
    J rows=J::array();
    rows.push_back(scenario("grenadier.most_expensive",[](){
        Fixture f(decks({"plant:向日葵","plant:激光豆"},{"zombie:脑光墓碑","zombie:掷弹兵僵尸"}));auto& m=*f.match;const double tile=f.tile();
        f.hero_at(Seat::plant,6000.);f.hero_at(Seat::zombie,9000.);
        auto near_plant=f.plant("向日葵",1512.+tile,1.);auto bean=f.plant("激光豆",1512.-3.*tile,1.);
        auto z=f.zombie("掷弹兵僵尸",1512.+2.*tile,-1.);z->native.move_speed.set(.001);
        f.run(3);z->body.hp-=1.;std::string target;
        for(int i=0;i<80&&target.empty();++i){f.run(5);if(!m.grenadiers.grenades->empty())target=m.grenadiers.grenades->back()->target;}
        J out={{"target",target},{"sunflower",near_plant->source.id.get()},{"bean",bean->source.id.get()}};
        expect(target==bean->source.id.get(),"grenade did not pick the 200-sun bean "+out.dump());
        return out;
    }));
    return rows;
}

J wind(){
    J rows=J::array();
    // x after the run, with or without a right-facing blover just left of the flyer.
    auto drift=[](const char* flyer,bool blover){
        Fixture f(decks({"plant:三叶草"},{"zombie:脑光墓碑",std::string("zombie:")+flyer}));auto& m=*f.match;const double tile=f.tile();
        f.hero_at(Seat::plant,1512.-10.*tile);f.hero_at(Seat::zombie,9000.);
        auto z=f.zombie(flyer,1512.+2.*tile,-1.,800.);if(!z->terraria)z->native.move_speed.set(.001);
        if(blover)f.plant("三叶草",1512.,1.);
        const double start=z->body.motion.get().x;f.run(400);(void)m;
        return J{{"start",start},{"end",z->body.motion.get().x},{"hp",z->body.hp}};
    };
    rows.push_back(scenario("servant.blover",[&](){
        const J calm=drift("克苏鲁之仆",false),blown=drift("克苏鲁之仆",true);
        const J parrot_calm=drift("海盗鹦鹉",false),parrot_blown=drift("海盗鹦鹉",true);
        J out={{"servant",{calm,blown}},{"parrot",{parrot_calm,parrot_blown}}};
        const double servant_push=blown["end"].get<double>()-calm["end"].get<double>();
        const double parrot_push=parrot_blown["end"].get<double>()-parrot_calm["end"].get<double>();
        out["servant_push"]=servant_push;out["parrot_push"]=parrot_push;
        expect(servant_push>48.,"blover did not move the servant "+out.dump());
        return out;
    }));
    rows.push_back(scenario("servant.blover_zombie",[&](){
        // A charmed-side check is not needed: the 三叶草僵尸 wind pushes every target but itself.
        auto run=[](bool wind){
            J zombies={"zombie:脑光墓碑","zombie:克苏鲁之仆","zombie:三叶草僵尸"};
            Fixture f(decks({"plant:向日葵"},zombies));const double tile=f.tile();
            // The servant chases the plant Dave to the right, i.e. downwind of the blover zombie.
            f.hero_at(Seat::plant,1512.+24.*tile);f.hero_at(Seat::zombie,9000.);
            ZombieRef b;if(wind){b=f.zombie("三叶草僵尸",1512.,1.);b->native.move_speed.set(.001);}
            auto s=f.zombie("克苏鲁之仆",1512.+1.*tile,1.,800.);const double start=s->body.motion.get().x;int fired=0;
            J debug=J::array();
            for(int i=0;i<60;++i){f.run(1);if(b&&b->patch.fire_animation.or_missing(0.)>0.)++fired;
                if(i<60&&i%6==0)debug.push_back({i,std::round(s->body.motion.get().x),s->terraria->vx,b?b->patch.fire_animation.or_missing(0.):-1.});}
            return J{{"start",start},{"end",s->body.motion.get().x},{"fire_ticks",fired},{"debug",debug}};
        };
        const J calm=run(false),blown=run(true);double gain=0.;
        for(size_t i=0;i<calm["debug"].size();++i)gain=std::max(gain,blown["debug"][i][2].get<double>()-calm["debug"][i][2].get<double>());
        J out={{"calm",calm},{"blown",blown},{"velocity_gain",gain}};
        expect(gain>.3,"三叶草僵尸 wind did not speed the servant downwind "+out.dump());
        return out;
    }));
    return rows;
}

J frost(){
    J rows=J::array();
    rows.push_back(scenario("lettuce.water_chills_plant_dave",[](){
        Fixture f(decks({"plant:冰冻生菜","plant:向日葵"},{"zombie:脑光墓碑","zombie:普通僵尸"}));auto& m=*f.match;const double tile=f.tile();
        for(int r=16;r<=21;++r)for(int c=26;c<=42;++c)m.battle.terrain.native_at(r,c).block.set("水");
        m.sync_terrain();f.hero_at(Seat::zombie,9000.);f.hero_at(Seat::plant,34.*tile,20.*tile);f.run(400);
        auto& hero=m.battle.heroes.hero(Seat::plant);const auto& pos=*hero.frame.position.get();J out={{"dave",{pos.x,pos.y}}};
        f.plant("冰冻生菜",30.*tile+tile*.5,1.,18.*tile);const auto tick=m.battle.heroes.tick;f.run(5);
        out["cold_until_minus_tick"]=hero.cold_until.or_missing(0.)-double(tick);out["water_ice"]=hero.frame.water_ice.or_missing(0.);
        out["global_water_ice"]=m.battle.heroes.water_ice;out["slowed_view"]=m.published.heroes[seat_index(Seat::plant)]->visible.slowed;
        expect(hero.cold_until.or_missing(0.)-double(tick)>=1490.,"plant Dave in the lettuce water was not chilled "+out.dump());
        expect(hero.frame.water_ice.or_missing(0.)>1400.,"chill did not reach the hero physics "+out.dump());
        return out;
    }));
    rows.push_back(scenario("sun_secret.first_80s",[](){
        Fixture f(decks({"plant:向日葵","secret:阳光"},{"zombie:脑光墓碑","zombie:普通僵尸"}));auto& m=*f.match;const double tile=f.tile();
        f.hero_at(Seat::zombie,9000.);f.hero_at(Seat::plant,1512.+20.*tile);f.plant("向日葵",1512.,1.);
        J early=J::array();double max_left=0.;
        while(m.battle.heroes.time<79.){f.run(25);auto& hero=m.battle.heroes.hero(Seat::plant);
            max_left=std::max(max_left,hero.cold_until.or_missing(0.)-double(m.battle.heroes.tick));}
        const auto at80=m.resources.sun_chills;const double earned=m.resources.accounts[seat_index(Seat::plant)].earned;
        f.run(250*60);const double earned_late=m.resources.accounts[seat_index(Seat::plant)].earned;
        J out={{"chills_by_80s",at80},{"chills_after",m.resources.sun_chills},{"max_left_ticks",max_left},{"earned_80",earned},{"earned_140",earned_late}};
        expect(at80>0,"no automatic pickup chilled Dave in the first 80 s "+out.dump());
        expect(max_left<=500.+1e-9&&max_left>400.,"chill length is not 2 s "+out.dump());
        expect(m.resources.sun_chills==at80,"pickups after 80 s still chill "+out.dump());
        expect(earned_late>earned,"no sun collected after 80 s (test inconclusive) "+out.dump());
        return out;
    }));
    return rows;
}

J hook(){
    J rows=J::array();
    // Hook zombie 11 tiles right of a wall-nut; an umbrella (optional) 3 tiles in front of
    // the nut and a sunflower on the path. Returns each plant's lost health.
    auto shot=[](bool anchor,bool umbrella){
        J zombies={"zombie:脑光墓碑","zombie:钩索僵尸"};if(anchor)zombies.push_back("zsecret:船锚");
        Fixture f(decks({"plant:坚果","plant:萝卜伞"},zombies));auto& m=*f.match;const double tile=f.tile();
        f.hero_at(Seat::plant,1512.-20.*tile);f.hero_at(Seat::zombie,9000.);
        auto nut=f.plant("坚果",1512.,1.);auto sun=f.plant("坚果",1512.+6.*tile,1.);PlantRef shield;
        if(umbrella)shield=f.plant("萝卜伞",1512.+3.*tile,1.);
        auto z=f.zombie("钩索僵尸",1512.+11.*tile,-1.);z->native.move_speed.set(.001);
        const double nut0=nut->hp.get(),sun0=sun->hp.get(),shield0=shield?shield->hp.get():0.;
        bool landed=false;double nut_hit=0.,sun_hit=0.;
        // Sample the moment the first hook resolves: it lands (pull starts) or the target is hit.
        for(int i=0;i<1800;++i){f.run(1);landed=z->content70.hook_pull.present();
            if(landed||nut->hp.get()<nut0||sun->hp.get()<sun0){nut_hit=nut0-nut->hp.get();sun_hit=sun0-sun->hp.get();break;}}
        (void)m;return J{{"nut",nut_hit},{"sun",sun_hit},{"umbrella",shield?shield0-shield->hp.get():0.},{"landed",landed},{"zx",z->body.motion.get().x}};
    };
    rows.push_back(scenario("hook.umbrella_block",[&](){
        const J plain=shot(false,false),anchor=shot(true,false),plain_blocked=shot(false,true),anchor_blocked=shot(true,true);
        J out={{"plain",plain},{"anchor",anchor},{"plain_blocked",plain_blocked},{"anchor_blocked",anchor_blocked}};
        near(plain["nut"],3.,"unblocked hook "+out.dump(),1e-6);near(plain["sun"],0.,"unblocked hook path "+out.dump(),1e-6);
        near(anchor["nut"],6.,"anchor target total "+out.dump(),1e-6);near(anchor["sun"],3.,"anchor path "+out.dump(),1e-6);
        // Blocked by the umbrella (with or without 船锚): no damage at all.
        for(const auto* key:{"plain_blocked","anchor_blocked"})for(const auto* p:{"nut","sun","umbrella"})
            near(out[key][p].get<double>(),0.,std::string(key)+" "+p+" "+out.dump(),1e-6);
        return out;
    }));
    return rows;
}

J coop(){
    J rows=J::array();
    rows.push_back(scenario("coop.zombie_seat_secrets",[](){
        auto armor=[](const J& secrets){
            J d={{"plant",{"plant:向日葵"}},{"plant2",{"plant:向日葵"}},{"zombie",secrets}};
            Fixture f(d,J{{"mode","coop"}});auto& m=*f.match;
            auto bucket=f.zombie("铁桶僵尸",2400.,-1.);auto pole=f.zombie("撑杆跳僵尸",2600.,-1.);
            return J{{"bucket_armor",bucket->body.armor_hp},{"pole_hp",pole->body.hp},{"king",m.zsecrets.has("僵王出品")},{"shield_first",m.damage.shield_first}};
        };
        const J none=armor(J::array()),with=armor(J{"zsecret:僵王出品","zsecret:体育生"});
        J out={{"none",none},{"with",with}};
        expect(with["king"].get<bool>()&&with["shield_first"].get<bool>(),"co-op zombie seat secret not active "+out.dump());
        near(with["bucket_armor"].get<double>(),none["bucket_armor"].get<double>()*1.25,"僵王出品 armour in co-op "+out.dump());
        near(with["pole_hp"].get<double>(),none["pole_hp"].get<double>()*1.25,"体育生 in co-op "+out.dump());
        return out;
    }));
    rows.push_back(scenario("coop.secret_schedule",[](){
        // One new secret per cleared day, only once a precursor is in the day's pool; a run
        // with a later counting start counts only the clears after it.
        J out;const std::string run="audit-run";
        const V a=pvp76r2::coop_zombie_secrets(V(run),V(1.),V(1.)),b=pvp76r2::coop_zombie_secrets(V(run),V(1.),V(8.));
        const V c=pvp76r2::coop_zombie_secrets(V(run),V(1.),V(40.)),late=pvp76r2::coop_zombie_secrets(V(run),V(22.),V(25.));
        const auto names=[](const V& v){J l=J::array();const V s=py::iter_list(v);for(size_t i=0;i<s.len();++i)l.push_back(py_str(s.idx(int64_t(i))));return l;};
                const J dump={{"day8",names(b)},{"day40",names(c)},{"late",names(late)},{"precursor",pvp76r2::precursor_in_pool("zsecret:专注啃咬",2)}};
        expect(py::len(a).num()==0.,"day 1 has no secret");expect(py::len(b).num()==7.,"seven clears give seven secrets "+dump.dump());
        expect(py::len(late).num()==3.,"an old run counts only clears after the upgrade "+dump.dump());
        J list=names(c);
        std::set<std::string> unique(list.begin(),list.end());expect(unique.size()==list.size(),"repeated secret "+list.dump());
        for(const auto& k:list)expect(pvp76r2::coop_secret_allowed(k.get<std::string>()),"excluded secret "+k.get<std::string>());
        // Precursor check: every secret picked for clear d had a precursor in day d+1's pool.
        for(int day=1;day<40;++day){const V upto=pvp76r2::coop_zombie_secrets(V(run),V(1.),V(double(day+1)));
            if(py::len(upto).num()==0.)continue;const auto last=names(upto).back().get<std::string>();
            expect(pvp76r2::precursor_in_pool(last,day+1),"secret "+last+" picked without precursor on day "+std::to_string(day+1));}
        // Deterministic.
        expect(py_str(py::repr(c))==py_str(py::repr(pvp76r2::coop_zombie_secrets(V(run),V(1.),V(40.)))),"schedule not deterministic");
        out["day8"]=names(b);
        out["day40"]=list;return out;
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
    const char* only=std::getenv("PVP76R2_AUDIT_CASE");
    for(auto [name,fn]:std::vector<std::pair<std::string,J(*)()>>{{"卡表",catalog},{"车速",carts},{"坤坤",kunkun},{"掷弹兵",grenade},{"风",wind},{"感冒",frost},{"钩索",hook},{"合作",coop}}){
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
