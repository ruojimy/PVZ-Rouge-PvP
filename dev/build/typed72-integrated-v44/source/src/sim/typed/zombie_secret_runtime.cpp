// Port of tools/pvp72_sources/zombie_secrets.py ZombieSecrets.step and its
// state hooks. Each block names its source method; constants are the source's.
#include "sim/typed/zombie_secret_runtime.h"
#include "sim/typed/expansion_combat.h"
#include "sim/typed/projectile_rules.h"
#include "core/pymath.h"
#include <algorithm>
#include <cmath>
#include <set>
namespace pvz::typed72 {
namespace {
constexpr double CROWD_RADIUS=6.,CROWD_STEP=.15,CROWD_MAX=.75,HEAL_PERIOD=12.,HEAL_RADIUS=8.,HEAL_AMOUNT=40.,HEAL_DAVE=4.;
constexpr double TACO_PERIOD=20.,RALLY_RADIUS=6.,RALLY_REFUND=15.,RALLY_DAVE_SPEED=1.25,PICKUP_SECONDS=30.,PICKUP_REACH=.7;
constexpr double PEA_PERIOD=2.,POLE_REACH=2.,POLE_DAMAGE=4.;
const std::array<const char*,3> GIANTS{"zombie:巨人僵尸","zombie:红眼巨人","zombie:角斗士巨人"};
const std::array<const char*,6> HEAD_ARMORS{"路障","铁桶","黑路障","黑铁桶","橄榄球头盔","黑橄榄球头盔"};
const std::array<const char*,4> SHARED_HAND_ARMOR{"钢门","垃圾桶","梯子","传送带"};
template<class A>bool among(const A& list,std::string_view v){return std::find(list.begin(),list.end(),v)!=list.end();}
template<class T>bool truth(const Field<T>& f){return f.present()&&!f.is_null()&&bool(f.get());}
std::string text(const Field<std::string>& f){return f.present()&&!f.is_null()?f.get():std::string{};}
// zombie_secrets.hand_kind
std::string hand_kind(const CombatZombie& z){
    const auto kind=text(z.content64.hand_kind);if(!kind.empty())return kind;const auto content=text(z.source.content);
    if(content=="垃圾桶僵尸")return "垃圾桶";if(content=="传送带僵尸")return "传送带";return z.body.hand;
}
}
bool ZombieSecretRuntime::tick(const std::string& key,double dt,double period){
    const double value=clock_[key]+dt;const bool due=value+1e-9>=period;clock_[key]=due?value-period:value;return due;
}
// ZombieSecrets._zombie: a live, moving unit (not a grave, Dave, tentacle or loose barrel).
bool ZombieSecretRuntime::zombie(const CombatZombie& z)const{
    return !z.protection.grave&&!z.protection.hero&&text(z.source.content)!="抓人草触手"&&!z.orphan_barrel&&z.body.hp>0.;
}
bool ZombieSecretRuntime::own(const ZombieRef& z)const{return world_.heroes.owner(source_ref(z))==Seat::zombie;}
double ZombieSecretRuntime::distance(double ax,double ay,double bx,double by)const{return std::hypot(wrap_delta(ax,bx,world_.world_width.get()),by-ay);}
std::vector<Seat> ZombieSecretRuntime::holders(std::string_view name)const{
    std::vector<Seat> out;for(const auto seat:present)if(team_of(seat)==Seat::zombie&&secrets_.seat_has(seat,name))out.push_back(seat);
    std::sort(out.begin(),out.end(),[](Seat a,Seat b){return std::string_view(seat_name(a))<std::string_view(seat_name(b));});return out;
}
std::optional<Point> ZombieSecretRuntime::hero_spot(Seat seat)const{
    const auto& h=world_.heroes.hero(seat);if(h.frame.hp.or_missing(0.)<=0.)return std::nullopt;const auto& p=*h.frame.position.get();return Point{p.x,p.y};
}
bool ZombieSecretRuntime::berserk()const{return secrets_.has("狂暴")&&(world_.protection.deathmatch||!world_.heroes.last_stand_order.empty());}
// __init__: 豌豆 holders carry the pea head from the lock.
void ZombieSecretRuntime::lock(){for(const auto seat:holders("豌豆"))world_.heroes.hero(seat).secret.pea_head.set(true);}
void ZombieSecretRuntime::step(double dt){
    if(!secrets_.enabled())return;
    if(secrets_.has("三五成群"))crowd();
    if(secrets_.has("不可撼动"))steady_giants();
    if(secrets_.has("远离诱惑"))slow_charmed();
    if(secrets_.has("汇流"))rally_dave_speed();
    for(const auto seat:holders("生生不息"))if(tick(std::string(seat_name(seat))+":heal",dt,HEAL_PERIOD))heal(seat);
    for(const auto seat:holders("玉米卷"))if(tick(std::string(seat_name(seat))+":taco",dt,TACO_PERIOD))taco(seat);
    if(secrets_.has("狂暴")||secrets_.has("坤坤"))fast_shots();
    if(secrets_.has("坤坤"))basket_lock();
    if(secrets_.has("立棍！小子"))pole_smash();
    if(secrets_.has("遗骸"))relic_expiry();
    if(!deaths_.conversions.empty())convert();
    if(!world_.heroes.last_stand_order.empty())world_.heroes.step_last_stand();
    if(!pickups.empty())take_pickups();
    std::vector<Seat> enemies;for(const auto s:present)if(team_of(s)==Seat::plant)enemies.push_back(s);
    for(const auto seat:holders("豌豆"))if(tick(std::string(seat_name(seat))+":pea",dt,PEA_PERIOD)&&peas_.hero_pea(seat,enemies,world_.world_width.get()))services_.secret_event({"zsecret_hero_pea",seat});
}
// _crowd
void ZombieSecretRuntime::crowd(){
    const double width=world_.world_width.get(),reach=CROWD_RADIUS*world_.runtime.tile;
    const auto roster=*world_.targets;std::vector<ZombieRef> members;
    for(const auto& t:roster)if(t.unit&&truth(t.unit->registration.secret_crowd)&&zombie(*t.unit)&&own(t.unit))members.push_back(t.unit);
    const int64_t cols=std::max<int64_t>(1,int64_t(py::floordiv(width,reach)));const double cell=width/double(cols);
    std::map<std::pair<int64_t,int64_t>,std::vector<ZombieRef>> grid;
    const auto key=[&](const Motion& m){return std::pair{int64_t(py::mod(py::floordiv(m.x,cell),double(cols))),int64_t(py::floordiv(m.y,reach))};};
    for(const auto& z:members)grid[key(z->body.motion.get())].push_back(z);
    for(const auto& t:roster)if(t.unit&&t.unit->protection.crowd_factor.present())t.unit->protection.crowd_factor.erase();
    for(const auto& z:members){
        const auto& m=z->body.motion.get();const auto [gx,gy]=key(m);int64_t count=0;std::set<int64_t> columns;
        for(int dx=-1;dx<=1;++dx)columns.insert(int64_t(py::mod(double(gx+dx),double(cols))));
        for(const auto col:columns)for(int dy=-1;dy<=1;++dy){
            const auto found=grid.find({col,gy+dy});if(found==grid.end())continue;
            for(const auto& other:found->second)if(other!=z&&distance(m.x,m.y,other->body.motion.get().x,other->body.motion.get().y)<=reach)++count;
        }
        if(count)z->protection.crowd_factor.set(1.-std::min(CROWD_MAX,CROWD_STEP*double(count)));
    }
}
// _steady_giants: newly applied control on a giant lasts half as long.
void ZombieSecretRuntime::steady_giants(){
    for(const auto& t:*world_.targets){
        if(!t.unit||!among(GIANTS,text(t.unit->protection.card))||!zombie(*t.unit))continue;auto& z=*t.unit;
        for(auto [field,seen]:{std::pair{&z.body.ice,&z.secret.control_ice},std::pair{&z.body.butter,&z.secret.control_butter},std::pair{&z.body.stun,&z.secret.control_stun}}){
            double now=field->present()&&!field->is_null()?field->get():0.;const double before=seen->or_missing(0.);
            if(now>before+1.){
                if(field==&z.body.ice&&now>1000.)now=before<=1000.?1000.+(now-1000.)/2.:before+(now-before)/2.;
                else now=before+(now-before)/2.;
                field->set(now);
            }
            seen->set(now);
        }
    }
}
// _slow_charmed
void ZombieSecretRuntime::slow_charmed(){
    for(const auto& t:*world_.targets)if(t.unit&&t.unit->source.charmed.present()&&zombie(*t.unit)&&t.unit->body.ice.or_missing(0.)<100.)t.unit->body.ice.set(100.);
}
// _rally_dave_speed
void ZombieSecretRuntime::rally_dave_speed(){
    const double reach=RALLY_RADIUS*world_.runtime.tile;
    for(const auto seat:present){
        if(team_of(seat)!=Seat::zombie)continue;auto& h=world_.heroes.hero(seat);auto& base=h.secret.base_speedmax;
        if(!base.present())base=h.frame.speed_max;if(!base.present()||base.is_null())continue;
        const auto& point=rally_.for_owner(world_.mode,seat);const auto& spot=*h.frame.position.get();
        const bool near=point&&h.frame.hp.or_missing(0.)>0.&&distance(point->x,point->y,spot.x,spot.y)<=reach;
        h.frame.speed_max.set(near?base.get()*RALLY_DAVE_SPEED:base.get());
    }
}
// _heal
void ZombieSecretRuntime::heal(Seat seat){
    const auto spot=hero_spot(seat);if(!spot)return;const double reach=HEAL_RADIUS*world_.runtime.tile;int64_t healed=0;
    for(const auto& t:*world_.targets){
        if(!t.unit||!zombie(*t.unit)||!own(t.unit))continue;auto& b=t.unit->body;const auto& p=b.motion.get();
        if(distance(spot->x,spot->y,p.x,p.y)>reach)continue;const double top=t.unit->max_hp.or_missing(b.hp);
        if(b.hp<top){b.hp=std::min(top,b.hp+HEAL_AMOUNT);++healed;}
    }
    auto& h=world_.heroes.hero(seat);const double hp=h.frame.hp.get();const double top=h.max_hp.or_missing(world_.heroes.players.at(seat_index(seat))->max_hp);
    h.frame.hp.set(std::max(hp,std::min(top,hp+HEAL_DAVE)));
    if(h.frame.hp.get()>hp)services_.secret_event({"heal",seat,{},{},{},{},{},h.frame.hp.get()-hp});
    services_.secret_event({"zsecret_heal",seat,{},{},{},{},{},0.,healed});
}
// _taco: nearest own zombie (distance, then id) without the 玉米卷 bonus.
void ZombieSecretRuntime::taco(Seat seat){
    const auto spot=hero_spot(seat);if(!spot)return;ZombieRef best;double best_d=0.;std::string best_id;
    for(const auto& t:*world_.targets){
        if(!t.unit||!zombie(*t.unit)||!own(t.unit))continue;
        if(std::any_of(t.unit->patch.speed_factors.begin(),t.unit->patch.speed_factors.end(),[](const auto& f){return f.first=="玉米卷";}))continue;
        const auto& p=t.unit->body.motion.get();const double d=distance(spot->x,spot->y,p.x,p.y);const auto id=text(t.unit->source.id);
        if(!best||d<best_d||(d==best_d&&id<best_id)){best=t.unit;best_d=d;best_id=id;}
    }
    if(!best)return;ColdZombieSecrets::scale_speed(best,"玉米卷",.75);
    {const double now=world_.heroes.time,tile=world_.runtime.tile;const auto& p=best->body.motion.get();
     std::erase_if(effects,[&](const Effect& e){return !(e.until>now);});
     effects.push_back({"taco",seat,best_id,spot->x,spot->y-tile*1.2,p.x,p.y-tile,now,now+.8});}
    services_.secret_event({"zsecret_taco",seat,best_id});
}
// _fast_shots: the extra share of this frame's countdown, never the arming tick.
void ZombieSecretRuntime::fast_shots(){
    for(const auto& t:*world_.targets){
        if(!t.unit||!zombie(*t.unit)||!own(t.unit))continue;auto& z=*t.unit;
        z.secret.timer_tracked.set(true);
        double rate=1.;if(berserk())rate+=1.;if(secrets_.has("坤坤")&&text(z.protection.card)=="zombie:投篮车僵尸")rate+=1.;
        for(auto [field,seen]:{std::pair{&z.patch.shooting_cooldown,&z.secret.timer_shot},std::pair{&z.native.basketball_cd,&z.secret.timer_basket}}){
            if(!field->present())continue;double now=field->get();
            if(rate>1.&&seen->present()&&0.<now&&now<seen->get()){now=std::max(1.,now-(seen->get()-now)*(rate-1.));field->set(now);}
            seen->set(now);
        }
    }
}
// _basket_lock
void ZombieSecretRuntime::basket_lock(){
    for(const auto& t:*world_.targets)if(t.unit&&truth(t.unit->protection.locked)&&t.unit->protection.basketball.or_missing(0.)<=0.){
        t.unit->protection.locked.erase();t.unit->protection.lock_done=true;
    }
}
// _pole_smash
void ZombieSecretRuntime::pole_smash(){
    const auto roster=*world_.targets;
    for(const auto& t:roster){
        if(!t.unit)continue;auto& z=*t.unit;
        if(!truth(z.registration.secret_pole)){
            const auto card=text(z.protection.card);
            if((card=="zombie:撑杆跳僵尸"||card=="zombie:黑撑杆僵尸")&&z.body.hand=="撑杆")z.registration.secret_pole.set(true);
            continue;
        }
        if(z.body.hand=="撑杆"||!zombie(z))continue;
        z.registration.secret_pole.set(false);smash(t.unit);
    }
}
void ZombieSecretRuntime::smash(const ZombieRef& z){
    const auto& m=z->body.motion.get();const double x=m.x,y=m.y,facing=z->body.facing>=0.?1.:-1.,tile=world_.runtime.tile,width=world_.world_width.get();
    const auto owner=world_.heroes.owner(source_ref(z));
    const auto ahead=[&](double px,double py){const double dx=wrap_delta(x,px,width)*facing;return -tile*.3<=dx&&dx<=POLE_REACH*tile&&std::abs(py-y)<tile;};
    int64_t hit=0;static const std::string no_hand;
    for(const auto& plant:*world_.plant_roster){
        if(plant->hp.or_missing(0.)<=0.||world_.heroes.owner(source_ref(plant))==owner)continue;
        if(ahead((plant->cell.x+.5)*tile,(plant->cell.y+1.)*tile)){
            double hp=plant->hp.get();plant->hp.set(hp-world_.protection.amount({hp,no_hand,plant->source,plant->protection},POLE_DAMAGE));plant->hurt.set(1.);
            if(plant->hp.get()<=0.){plant->hp.set(0.);plant->dead.set(DeathMarker(0.));}
            ++hit;
        }
    }
    const auto foe=owner==Seat::zombie?Seat::plant:Seat::zombie;const auto extras=world_.omitted_targets();
    FullTargetsScope full(world_.targets,std::span<const CombatTarget>(extras));
    HeroContext context(world_.heroes,{foe,owner.value_or(Seat::zombie),CombatPhase::status,source_ref(z),{}});
    const auto roster=*world_.targets;
    for(size_t index=0;index<roster.size();++index){
        const auto& other=roster[index];if(!other.unit||other.unit==z||other.unit->protection.hero||other.unit->body.hp<=0.||world_.heroes.owner(source_ref(other.unit))==owner)continue;
        const auto& p=other.unit->body.motion.get();if(ahead(p.x,p.y)){services_.damage_zombie(index,facing,POLE_DAMAGE*10.);++hit;}
    }
    for(const auto seat:present){
        if(team_of(seat)!=foe)continue;world_.heroes.proxy(seat);const auto& proxy=world_.heroes.cached_proxy(seat);
        if(proxy.hp>0.&&ahead(proxy.position->x,proxy.position->y)){world_.heroes.damage(seat,POLE_DAMAGE,HeroHit::normal /* source kind "pole" has no special branch in damage_hero */);++hit;}
    }
    context.close();full.close();
    services_.secret_event({"zsecret_pole_smash",{},text(z->source.id),{},{},{},{},0.,hit});
}
// _relic_expiry
void ZombieSecretRuntime::relic_expiry(){
    const double tick=double(world_.heroes.tick);
    for(const auto& entry:world_.native_objects.entries())if(const auto* z=std::get_if<ZombieRef>(&entry.object)){
        const auto& until=(*z)->protection.relic_until;
        if(until.present()&&!until.is_null()&&tick>=until.get()&&(*z)->body.hp>0.)(*z)->body.hp=0.;
    }
}
// _convert: queued plant-zombie forms, spawned for their holder at half life.
void ZombieSecretRuntime::convert(){
    const auto queued=std::move(deaths_.conversions);deaths_.conversions.clear();
    for(const auto& c:queued){
        const auto card="zombie:"+c.name;const auto id=services_.spawn_zombie(card,c.position,c.facing,c.seat);if(!id)continue;
        if(const auto object=world_.native_objects.get(*id))if(const auto* z=std::get_if<ZombieRef>(&*object)){ColdZombieSecrets::scale_hp(*z,.5);(*z)->secret.converted.set(true);}
        services_.secret_event({"zsecret_plant_zombie",c.seat,*id,card});
    }
}
// on_armor_break (二手): a broken piece leaves a half-life second-hand copy.
void ZombieSecretRuntime::on_armor_break(const ZombieRef& z,ArmorSlot slot,const std::string& name,double top){
    if(!secrets_.has("二手")||name.empty()||z->protection.hero||z->protection.grave)return;
    if(team_of(parse_seat(z->source.owner.or_missing("zombie")))!=Seat::zombie)return;
    const bool head=slot==ArmorSlot::head;const auto& second=z->registration.secondhand;
    if(second.present()&&!second.is_null()&&truth(head?second.get().head:second.get().hand))return;
    if(top<=0.)return;
    ++pickup_serial;const auto& m=z->body.motion.get();ZombieSecretPickup item;
    item.id="zs"+std::to_string(pickup_serial);item.slot=head?"防具":"手持";item.name=name;item.hp=top/2.;
    if(!head){const auto kind=hand_kind(*z);item.kind=kind.empty()?name:kind;}else item.kind=name;
    item.dropper=z.get();item.position={m.x,m.y};item.until=world_.heroes.time+PICKUP_SECONDS;
    if(head){const auto black=ExpansionCombat::worn_black_armor(z);if(black&&(*black=="黑路障僵尸"||*black=="黑铁桶僵尸"))item.black=black;}
    pickups.push_back(std::move(item));
    services_.secret_event({"zsecret_armor_drop",{},{},{},name,head?"防具":"手持"});
}
bool ZombieSecretRuntime::wearer(const CombatZombie& z,const ZombieSecretPickup& item)const{
    if(z.source.charmed.present())return false;
    if(item.slot=="防具"){const bool worn=among(HEAD_ARMORS,z.body.armor)&&z.body.armor_hp>0.;return !worn&&z.body.hand!="撑杆";}
    if(among(SHARED_HAND_ARMOR,item.kind))return z.body.hand.empty()&&z.body.hand_hp<=0.;
    return z.body.hand.empty()&&text(z.registration.secret_hand)==item.name;
}
bool ZombieSecretRuntime::riding_wearer(const ZombieRef& z,const ZombieSecretPickup& item)const{
    return item.slot=="防具"&&zombie(*z)&&own(z)&&!z->source.charmed.present()&&z->body.kind.find("巨人")!=std::string::npos&&
        !z->native.throw_imp.present()&&text(z->poison.imp_armor).empty()&&z->poison.imp_armor_hp.or_missing(0.)<=0.;
}
// _pickups
void ZombieSecretRuntime::take_pickups(){
    std::vector<ZombieSecretPickup> keep;const double reach=PICKUP_REACH*world_.runtime.tile;
    for(auto& item:pickups){
        if(world_.heroes.time>=item.until)continue;
        ZombieRef taker;bool riding=false;
        for(const auto& t:*world_.targets){
            if(!t.unit||t.unit.get()==item.dropper||!zombie(*t.unit))continue;const auto& p=t.unit->body.motion.get();
            if(distance(item.position.x,item.position.y,p.x,p.y)>reach)continue;
            if(own(t.unit)&&wearer(*t.unit,item)){taker=t.unit;break;}
            if(riding_wearer(t.unit,item)){taker=t.unit;riding=true;break;}
        }
        if(!taker){keep.push_back(std::move(item));continue;}
        auto& second=taker->registration.secondhand;if(!second.present()||second.is_null())second.set(ColdSecondhandEquipment{});
        if(riding){
            const auto art=item.black==std::optional<std::string>("黑路障僵尸")?std::string("黑路障"):item.black==std::optional<std::string>("黑铁桶僵尸")?std::string("黑铁桶"):item.name;
            taker->poison.imp_armor.set(art);taker->poison.imp_armor_hp.set(item.hp);second.get().carried_imp.set(true);
            services_.secret_event({"zsecret_armor_pickup",{},text(taker->source.id),{},art,{},std::string("riding_imp")});continue;
        }
        if(item.slot=="防具"){
            taker->body.armor=item.name;taker->body.armor_hp=item.hp;second.get().head.set(true);
            if(item.black)taker->expansion.black_armor.set(*item.black);else taker->expansion.black_armor.set_null();
            taker->armor_max.set(item.hp);
            if(item.black&&(taker->body.kind=="普通僵尸"||taker->body.kind=="旗帜僵尸"||taker->body.kind=="鸭子普通僵尸")&&text(taker->source.variant).empty())taker->source.variant.set(*item.black);
            taker->poison.armor_triggered.erase();
        }else{
            taker->body.hand=item.name;taker->body.hand_hp=item.hp;taker->content64.hand_kind.set(item.kind.empty()?item.name:item.kind);taker->hand_max.set(item.hp);second.get().hand.set(true);
        }
        services_.secret_event({"zsecret_armor_pickup",{},text(taker->source.id),{},item.name});
    }
    pickups=std::move(keep);
}
void ZombieSecretRuntime::pay(Seat seat,double amount,Point point,const std::string& reason){
    resources_.create(seat,amount,point,reason);  // zombie-side resources are collected at once (simulation.resource)
}
// on_unit_gone (汇流): a zombie dying near the rally flag refunds its payer.
void ZombieSecretRuntime::on_unit_gone(const NativeObject& object){
    if(!secrets_.enabled()||!secrets_.has("汇流"))return;const auto* zp=std::get_if<ZombieRef>(&object);if(!zp)return;const auto& z=**zp;
    const auto seat=z.source.seat.value_or(Seat::zombie);const auto& point=rally_.for_owner(world_.mode,seat);
    if(!point||z.protection.grave||z.protection.hero)return;
    if(z.source.owner.or_missing("")!="zombie"||z.source.charmed.present()||z.body.hp>0.)return;
    const auto& m=z.body.motion.get();if(distance(point->x,point->y,m.x,m.y)>RALLY_RADIUS*world_.runtime.tile)return;
    const auto payer=world_.heroes.players.at(seat_index(seat))?seat:Seat::zombie;
    pay(payer,RALLY_REFUND,{m.x,m.y},"zsecret_rally");
}
} // namespace pvz::typed72
