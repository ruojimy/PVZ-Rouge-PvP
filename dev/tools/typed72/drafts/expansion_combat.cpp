#include "sim/typed/expansion_combat.h"
#include "sim/typed/projectile_rules.h"
#include "core/pymath.h"
#include <algorithm>
#include <cmath>
namespace pvz::typed72 {
namespace {
bool yes(const Field<bool>& value){return value.present()&&!value.is_null()&&value.get();}
std::string_view text(const Field<std::string>& value){return value.present()&&!value.is_null()?value.get():std::string_view{};}
bool black(std::string_view value){return value=="黑路障僵尸"||value=="黑铁桶僵尸";}
bool secret(const HeroPlayer& player,std::string_view value){return std::find(player.secrets.begin(),player.secrets.end(),value)!=player.secrets.end();}
constexpr std::array<const char*,5> suffixes{"","-受伤","-冰冻","-灰烬","-魅惑"};
}
void ExpansionCombat::configure_locked_secrets() {
    pea_hybrid=paralysis_secret=silence_secret=false;
    for(const auto seat:seats_for(world_.mode)) {
        const auto& player=world_.heroes.players.at(seat_index(seat)).value();
        if(team_of(seat)==Seat::plant) {
            pea_hybrid=pea_hybrid||secret(player,"secret:豌豆杂交");
            paralysis_secret=paralysis_secret||secret(player,"secret:麻痹");
        }else silence_secret=silence_secret||secret(player,"zsecret:沉默");
    }
}
void ExpansionCombat::configure(const ZombieRef& unit,const ExpansionVariantSetup& setup) {
    unit->body.hp=setup.hp;unit->body.armor=setup.armor;unit->body.armor_hp=setup.armor_hp;
    unit->source.variant.set(setup.name);
    if(!setup.riding.empty()){unit->poison.imp_armor.set(setup.riding);unit->poison.imp_armor_hp.set(setup.riding_hp);}
    auto& speed=unit->native.move_speed;
    if(setup.native_template=="旗帜僵尸")speed.set(speed.get()*(setup.name=="黑旗帜僵尸"?1.25:.5));
    if(setup.name=="黑橄榄僵尸")speed.set(speed.get()*1.25);
    unit->base_speed=speed;
}
std::optional<std::string> ExpansionCombat::worn_black_armor(const ZombieRef& unit) {
    const auto& marker=unit->expansion.black_armor;
    if(marker.present())return marker.is_null()?std::nullopt:std::optional<std::string>(marker.get());
    const auto name=text(unit->source.variant);
    return black(name)?std::optional<std::string>(name):std::nullopt;
}
void ExpansionCombat::armor_drop(const ZombieRef& unit) {
    if(yes(unit->poison.killed))return;
    const auto name=worn_black_armor(unit);
    if(!name||!black(*name)||yes(unit->poison.armor_triggered))return;
    unit->poison.armor_triggered.set(true);
    black_armor_blast(unit,*name);
}
void ExpansionCombat::black_armor_blast(const ZombieRef& unit,const std::string& variant) {
    const auto point=unit->body.motion.get();auto& heroes=world_.heroes;
    const auto owner=heroes.owner(source_ref(unit)).value();
    const auto opposing=owner==Seat::plant?Seat::zombie:Seat::plant;
    const double tile=world_.runtime.tile,width=world_.world_width.get();
    const double reach=(variant=="黑铁桶僵尸"?3.5:2.5)*tile*(silence_secret?2.:1.);
    const auto contains=[&](Point p){return std::abs(wrap_delta(point.x,p.x,width))<=reach&&std::abs(point.y-p.y)<=reach;};
    {
        const auto extras=world_.omitted_targets();
        FullTargetsScope full(world_.targets,std::span<const CombatTarget>(extras));
        HeroContext context(heroes,{opposing,owner,CombatPhase::status,source_ref(unit),{}});
        const auto targets=world_.targets;
        for(size_t i=0;i<targets->size();++i) {
            const auto target=targets->at(i);
            if(target.is_hero()||target.unit==unit||target.unit->body.hp<=0.||heroes.owner(source_ref(target.unit))==owner)continue;
            const auto p=target.unit->body.motion.get();if(!contains({p.x,p.y}))continue;
            if(variant=="黑路障僵尸")services_.expansion_outer_damage(i,unit->body.facing,60.);
            else target.unit->body.stun.set(std::max(target.unit->body.stun.or_missing(0.),1500.));
        }
        for(const auto seat:seats_for(world_.mode))if(team_of(seat)==opposing) {
            const auto& proxy=heroes.proxy(seat);const auto p=*proxy.position;
            if(proxy.hp<=0.||!contains({p.x,p.y}))continue;
            if(variant=="黑路障僵尸")heroes.damage(seat,6.,HeroHit::black_armor);
            else heroes.write_proxy_status(seat,HeroStatus::stun,std::max(proxy.stun.or_missing(0.),1500.));
        }
    }
    const auto plants=world_.plant_roster;
    for(size_t i=0;i<plants->size();++i) {
        const auto plant=plants->at(i);
        if(plant->hp.or_missing(0.)<=0.||heroes.owner(source_ref(plant))==heroes.owner(source_ref(unit)))continue;
        if(!contains({(plant->cell.x+.5)*tile,(plant->cell.y+1.)*tile}))continue;
        if(variant=="黑路障僵尸") {
            static const std::string hand;
            plant->hp.set(plant->hp.get()-world_.protection.amount({plant->hp.get(),hand,plant->source,plant->protection},6.));
            plant->hurt.set(1.);
            if(plant->hp.get()<=0.){plant->hp.set(0.);plant->dead.set(DeathMarker(0.));}
        }else if(plant->kind!="咖啡豆")plant->sleep.set(0.);
    }
    services_.black_armor_event(variant,{point.x,point.y});
}
HitResult ExpansionCombat::ordinary(size_t index,double facing,double amount) {
    const auto target=world_.targets->at(index);
    const auto unit=target.unit;
    const double before_armor=body(target).armor_hp;
    const size_t first=world_.runtime.entities.list()->size();
    const auto result=services_.expansion_inner_damage(index,facing,amount);
    const auto black=unit?worn_black_armor(unit):std::nullopt;
    const auto entities=world_.runtime.entities.list();
    for(size_t i=first;i<entities->size();++i) {
        const auto entity=entities->at(i);
        if(black&&!black->empty()&&(entity->kind=="路障"||entity->kind=="铁桶"))entity->art_name.set("黑"+entity->kind);
    }
    if(unit&&before_armor>0.&&unit->body.armor_hp<=0.)armor_drop(unit);
    const auto source=world_.heroes.source();
    if(amount>0.&&source&&text(source->plant)=="地刺王"&&paralysis_secret&&body(target).hp>0.)apply_paralysis(target);
    return result;
}
void ExpansionCombat::after_projectile(const std::shared_ptr<AttackSource>& source,const PlantRef& plant,
                                      size_t first,std::optional<int64_t> magnet_target) {
    if(source&&(text(source->plant)=="磁力菇"||text(source->plant)=="吸金磁")&&magnet_target&&
       *magnet_target>=0&&size_t(*magnet_target)<world_.targets->size()) {
        const auto target=world_.targets->at(size_t(*magnet_target));
        const auto black=target.unit?worn_black_armor(target.unit):std::nullopt;
        if(black&&*black=="黑铁桶僵尸") {
            const auto entities=world_.runtime.entities.list();
            for(size_t i=first;i<entities->size();++i)if(entities->at(i)->kind=="铁桶")entities->at(i)->art_name.set("黑铁桶");
        }
    }
    hybrid_.after_birth(plant,first);
}
ExpansionCombatState& ExpansionCombat::state(const CombatTarget& target)const {
    return target.unit?target.unit->expansion:world_.heroes.cached_proxy(target.hero).expansion;
}
ZombieRecordFields& ExpansionCombat::body(const CombatTarget& target)const {
    return target.unit?static_cast<ZombieRecordFields&>(target.unit->body):static_cast<ZombieRecordFields&>(world_.heroes.cached_proxy(target.hero));
}
ZombieNativeState& ExpansionCombat::native(const CombatTarget& target)const {
    return target.unit?target.unit->native:world_.heroes.cached_proxy(target.hero).native;
}
void ExpansionCombat::stun(const CombatTarget& target,double value) {
    if(target.unit)target.unit->body.stun.set(value);
    else world_.heroes.write_proxy_status(target.hero,HeroStatus::stun,value);
}
void ExpansionCombat::apply_paralysis(const ZombieRef& unit){apply_paralysis(CombatTarget::zombie(unit));}
void ExpansionCombat::apply_paralysis(const CombatTarget& target) {
    const double now=double(world_.heroes.tick),ticks=63.;
    auto& state=this->state(target);const auto& until=state.paralysis_until;
    const double previous=until.present()&&!until.is_null()&&until.get()!=0.?until.get():now;
    if(body(target).stun.or_missing(0.)>std::max(ticks,previous-now))return;
    if(!until.present()||until.is_null()) {
        state.paralysis_started.set(now);state.paralysis_garlic.set(native(target).garlic.or_missing(0.));
    }
    state.paralysis_until.set(now+ticks);stun(target,std::max(body(target).stun.or_missing(0.),ticks));
}
void ExpansionCombat::paralysis_recovery(const ZombieRef& unit){paralysis_recovery(CombatTarget::zombie(unit));}
void ExpansionCombat::paralysis_recovery(const CombatTarget& target) {
    auto& state=this->state(target);const double now=double(world_.heroes.tick);
    const double remaining=std::max(0.,state.paralysis_until.get()-now);
    const double garlic=std::max(0.,state.paralysis_garlic.or_missing(0.)-(now-state.paralysis_started.get()));
    const bool external=body(target).stun.or_missing(0.)>remaining+1.;
    if(external||body(target).stun.or_missing(0.)<=0.) {
        if(!external)native(target).garlic.set(std::max(garlic,native(target).garlic.or_missing(0.)>100.?native(target).garlic.get():0.));
        state.paralysis_until.erase();state.paralysis_started.erase();state.paralysis_garlic.erase();
    }else if(garlic>native(target).garlic.or_missing(0.))native(target).garlic.set(garlic);
}
bool ExpansionCombat::solid(Point point)const {
    const double tile=world_.runtime.tile;const auto row=int64_t(std::floor(point.y/tile));
    if(row<0)return false;if(size_t(row)>=published_.solid.size())return true;
    const auto& cells=published_.solid.at(size_t(row));if(cells.empty())throw std::domain_error("empty expansion map row");
    const auto col=int64_t(std::floor(py::mod(point.x,world_.world_width.get())/tile));
    return cells.at(size_t(col%int64_t(cells.size())))!=0;
}
void ExpansionCombat::charge(const ZombieRef& unit) {
    auto& state=unit->expansion;const double tick=double(world_.heroes.tick);
    bool active=state.charge_until.or_missing(0.)>tick;
    const auto p=unit->body.motion.get();const double facing=unit->body.facing,tile=world_.runtime.tile,width=world_.world_width.get();
    const bool blocked=std::any_of(world_.plant_roster->begin(),world_.plant_roster->end(),[&](const auto& plant) {
        const double dx=wrap_delta(p.x,(plant->cell.x+.5)*tile,width)*facing;
        return plant->hp.or_missing(0.)>0.&&!plant->dead.present()&&dx>=0.&&dx<=tile&&std::abs((plant->cell.y+1.)*tile-p.y)<tile;
    });
    if(active&&(blocked||unit->body.hp<=0.||unit->body.stun.or_missing(0.)>0.)){state.charge_until.set(tick);active=false;}
    if(!active&&yes(state.charging))state.charge_ready.set(tick+state.charge_cd.or_missing(1500.));
    if(!active&&!blocked&&unit->body.stun.or_missing(0.)<=0.&&unit->body.hp>0.&&unit->native.entry.or_missing(0.)>=500.&&tick>=state.charge_ready.or_missing(0.)) {
        state.charge_until.set(tick+1500.);active=true;
    }
    state.charging.set(active);unit->native.move_speed.set(unit->base_speed.get()*(active?2.:1.));
    if(!active||unit->body.ice.or_missing(0.)>1000.||unit->body.butter.or_missing(0.)>0.)return;
    const auto targets=world_.targets;
    for(size_t i=0;i<targets->size();++i) {
        const auto other=targets->at(i);
        if(other.is_hero()||other.unit==unit||other.unit->protection.grave||other.unit->body.hp<=0.)continue;
        if(world_.heroes.owner(source_ref(other.unit))!=world_.heroes.owner(source_ref(unit)))continue;
        auto& position=other.unit->body.motion.get();const double distance=wrap_delta(p.x,position.x,width)*facing;
        if(distance>=0.&&distance<tile&&std::abs(p.y-position.y)<tile) {
            const double target=py::mod(p.x+facing*tile,width);
            if(!solid({target,p.y-tile*.5})) {
                position.x=target;
                if(services_.expansion_barrel_active(other.unit)&&!other.unit->orphan_barrel)services_.expansion_correct_barrel(other.unit);
            }
        }
    }
}
void ExpansionCombat::finish_zombie() {
    services_.expansion_armor_clear();services_.expansion_restore_art();
    const auto unit=std::exchange(last_zombie,{});if(!unit)return;
    const auto name=text(unit->source.variant);auto& motion=unit->body.motion.get();
    if(name=="黑橄榄僵尸") {
        const double previous=unit->expansion.before_vy.or_missing(0.);unit->expansion.before_vy.erase();
        if(previous>=0.&&motion.vy<0.&&unit->body.hurt==0.)motion.vy*=1.25;
    }
    if(name=="黑撑杆僵尸"&&unit->body.hp>0.&&!unit->body.pole_vault.present()&&motion.vy>=0.&&solid({motion.x,motion.y+world_.runtime.tile*.25})) {
        unit->body.pole_vault.set(0.);unit->body.hand="撑杆";
    }
}
void ExpansionCombat::alias_art(const std::string& old,const std::string& replacement) {
    for(const auto suffix:suffixes)if(services_.expansion_has_art(old+suffix)&&services_.expansion_has_art(replacement+suffix))
        services_.expansion_alias_one(old+suffix,replacement+suffix);
}
void ExpansionCombat::zombie_gate(const ZombieRef& unit) {
    finish_zombie();last_zombie=unit;services_.expansion_armor_gate(unit);
    const auto name=text(unit->source.variant);const auto p=unit->body.motion.get();
    if(name=="黑撑杆僵尸"&&unit->body.hp>0.&&unit->body.pole_vault.or_missing(200.)>=100.&&drawing_)
        services_.expansion_draw_pole({p.x-world_.runtime.tile,p.y-world_.runtime.tile*1.5});
    if(unit->expansion.paralysis_until.present())paralysis_recovery(unit);
    const auto armor=unit->body.armor;const auto worn=worn_black_armor(unit);
    if(worn&&black(*worn)&&(armor=="路障"||armor=="铁桶"))alias_art(armor,"黑"+armor);
    if(name.empty())return;
    if(unit->body.kind=="旗帜僵尸"&&unit->body.hp>-800.&&unit->body.hp<=0.&&!unit->body.ash.present())
        unit->body.hp=std::min(0.,unit->body.hp+(name=="黑旗帜僵尸"?2./3.:.5));
    if(name=="黑橄榄僵尸"){unit->expansion.before_vy.set(p.vy);charge(unit);}
    for(const std::string part:{"-身","-首"})for(const auto suffix:suffixes) {
        const auto old=unit->body.kind+part+suffix;std::string replacement=std::string(name)+part+suffix;
        if(name=="黑橄榄僵尸"&&yes(unit->expansion.charging))replacement=std::string(name)+(part=="-身"?"-冲锋":"-冲锋-首")+suffix;
        if(services_.expansion_has_art(old)&&services_.expansion_has_art(replacement))services_.expansion_alias_one(old,replacement);
    }
    if(name=="黑橄榄僵尸"&&yes(unit->expansion.charging)&&armor=="黑橄榄球头盔")alias_art(armor,"黑橄榄僵尸-冲锋-头盔");
}
void ExpansionCombat::source_gate(const PlantRef& plant,const EntityRef& entity) {
    services_.expansion_restore_art();hybrid_.restore();
    if(entity&&entity->art_name.present()&&!entity->art_name.is_null()&&!entity->art_name.get().empty())alias_art(entity->kind,entity->art_name.get());
    hybrid_.gate(plant,pea_hybrid);
}
}
