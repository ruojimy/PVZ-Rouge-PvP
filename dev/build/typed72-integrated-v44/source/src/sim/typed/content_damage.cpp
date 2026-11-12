#include "sim/typed/content_damage.h"
#include "sim/typed/content_target_state.h"
#include "sim/typed/mortar_plants.h"
#include "core/pymath.h"
namespace pvz::typed72 {
namespace {
bool yes(const Field<bool>& field){return field.present()&&!field.is_null()&&field.get();}
std::string_view name(const Field<std::string>& field){return field.present()&&!field.is_null()?field.get():std::string_view{};}
bool pea(std::string_view name){return name=="豌豆"||name=="冰豆"||name=="火豆"||name=="蓝火豆";}
bool fire(std::string_view name){return name=="火豆"||name=="蓝火豆";}
bool gas(std::string_view name){return name=="小喷菇"||name=="胆小菇"||name=="大喷菇"||name=="忧郁蘑菇"||name=="忧郁菇"||name=="海蘑菇";}
}
void ContentTargetDamageLower::knock(size_t index,double amount) {
    const auto target=world_.targets->at(index);
    if(target.is_hero())world_.heroes.cached_proxy(target.hero).position->vx+=amount;
    else patch_.knockback(target.unit,amount);
}
ZombieRecordFields& NativeContentDamage::body(const CombatTarget& target)const {
    return target.is_hero()?static_cast<ZombieRecordFields&>(world_.heroes.cached_proxy(target.hero)):
        static_cast<ZombieRecordFields&>(target.unit->body);
}
Motion& NativeContentDamage::motion(const CombatTarget& target)const {
    return target.is_hero()?*world_.heroes.cached_proxy(target.hero).position:target.unit->body.motion.get();
}
std::shared_ptr<AttackSource> NativeContentDamage::source(const CombatTarget& target)const {
    return target.is_hero()?world_.heroes.proxy_source(target.hero):source_ref(target.unit);
}
bool NativeContentDamage::anchored(const CombatTarget& target)const {
    return target.unit&&world_.heroes.tick<target.unit->protection.anchor_until.or_missing(0.);
}
bool NativeContentDamage::multi_blue_direct(const EntityRef& entity) {
    return entity&&(yes(entity->mortar.tripea_blue)||yes(entity->mortar.multi_red))&&!yes(entity->source.melon_splash);
}
bool NativeContentDamage::content_projectile(const EntityRef& entity) {
    if(!entity)return false;
    const auto content=name(entity->source.content);
    return content=="原始豌豆射手"||content=="甜椒投手"||gas(name(entity->source.plant_kind))||entity->kind=="西瓜"||entity->kind=="冰瓜"||fire(entity->kind);
}
bool NativeContentDamage::allows_hit(const CombatTarget& target,const std::shared_ptr<AttackSource>& attack)const {
    if(!attack||!attack->projectile.present()||yes(attack->melon_splash)||yes(attack->area_damage))return true;
    const double scale=unit_scale_factor(*source(target),collision_);
    if(scale>=1.)return true;const auto entity=attack->entity.lock();
    return !entity||std::abs(motion(target).y-entity->motion.get().y)<=1.75*world_.runtime.tile*scale;
}
double NativeContentDamage::primal_damage(const EntityRef& entity)const {
    return projectile_fire_color(entity->source,world_.heroes.globals)=="blue"?90.:entity->kind=="火豆"?60.:30.;
}
void NativeContentDamage::gas_hit(const std::shared_ptr<AttackSource>& attack,const CombatTarget& target) {
    if(!gas_secret_||!attack)return;
    const auto plant=attack->plant.present()?name(attack->plant):name(attack->plant_kind);
    if(gas(plant)&&world_.heroes.owner(attack)==Seat::plant)status_.apply(target,1,4.,Seat::plant);
}
HitResult NativeContentDamage::hit(size_t index,double facing,double amount,const ContentHitOrigin& origin) {
    const auto attack=world_.heroes.source();const auto target=world_.targets->at(index);
    if(anchored(target))return HitResult::hero(0.);
    if(content_projectile(origin.head_entity))return head_impact(origin.head_entity,index,facing,amount,false);
    if(origin.reciprocal_bite) {
        const auto attacker=target.unit==origin.current?origin.other:origin.current;
        if(!attacker)throw std::invalid_argument("missing reciprocal bite source");
        amount=zombies_.bite_damage(attacker,target);const auto owner=world_.heroes.owner(source_ref(attacker)).value();
        HeroContext scope(world_.heroes,{owner==Seat::plant?Seat::zombie:Seat::plant,owner,CombatPhase::zombies,source_ref(attacker),{}});
        return lower_.hit(index,facing,amount);
    }
    if(!allows_hit(target,attack))return HitResult::hero(0.);
    const auto entity=attack?attack->entity.lock():EntityRef{};
    if(!state_.damage_depth&&entity) {
        const auto content=name(attack->content);
        if(content=="原始豌豆射手"&&pea(entity->kind))amount=primal_damage(entity)/(yes(attack->melon_splash)?3.:1.);
        else if(content=="甜椒投手"&&entity->kind=="西瓜")amount=60.;
        if(multi_blue_direct(entity))amount=name(attack->fire_color)=="fire"?20.:30.;
        if(content!="原始豌豆射手"&&fire(entity->kind)&&!yes(attack->melon_splash))amount=projectile_fire_color(*attack,world_.heroes.globals)=="blue"?30.:20.;
        if(yes(entity->mortar.mortar))amount=MortarPlants::projectile_damage(entity,target,amount);
        if(yes(entity->pea.charmed_pea)&&fire(entity->kind))amount=(projectile_fire_color(*attack,world_.heroes.globals)=="blue"?60.:40.)/(yes(attack->melon_splash)?3.:1.);
    }
    const double barrel_hp=body(target).hand_hp;HitResult result;
    {ContentDamageDepth guard(state_);result=lower_.hit(index,facing,amount);}
    if(target.unit&&target.unit->orphan_barrel) {
        auto& unit=*target.unit;unit.body.hand_hp=std::max(0.,unit.body.hp);unit.content.barrel_remaining.set(unit.body.hand_hp);
        if(unit.body.hand_hp<=0.)zombies_.barrel_break(target.unit);
    }
    if(target.unit&&body(target).hp<=0.)zombies_.barrel_detach(target.unit,barrel_hp);
    if(amount>0.)gas_hit(attack,target);
    if(entity&&name(attack->content)=="原始豌豆射手"&&pea(entity->kind)&&!yes(attack->melon_splash))
        primal_knockback(index,entity->facing*world_.runtime.plk*200.,entity);
    return result;
}
HitResult NativeContentDamage::surface_hit(size_t index,double facing,double amount,const ContentHitOrigin& origin) {
    if(anchored(world_.targets->at(index)))return HitResult::hero(0.);
    if(content_projectile(origin.head_entity))return head_impact(origin.head_entity,index,facing,amount,true);
    const auto attack=world_.heroes.source();if(!allows_hit(world_.targets->at(index),attack))return HitResult::hero(0.);
    const auto entity=attack?attack->entity.lock():EntityRef{};
    if(multi_blue_direct(entity)||(entity&&fire(entity->kind)&&!yes(attack->melon_splash))) {
        const auto& target=body(world_.targets->at(index));
        if((target.hand=="钢门"||target.hand=="梯子")&&target.hand_hp>0.&&!entity->tracking.present())lower_.knock(index,facing*world_.runtime.plk*200.);
        return hit(index,facing,amount);
    }
    if(entity) {
        if(name(attack->content)=="原始豌豆射手")amount=primal_damage(entity);
        else if(name(attack->content)=="甜椒投手")amount=60.;
        if(yes(entity->mortar.mortar))amount=MortarPlants::projectile_damage(entity,world_.targets->at(index),amount);
    }
    const auto target=world_.targets->at(index);
    if(target.unit&&target.unit->orphan_barrel)return hit(index,facing,amount);
    if(target.unit&&name(target.unit->source.content)=="滚桶僵尸"&&body(target).hand_hp>0.) {
        if(entity&&!yes(entity->content_state.barrel_contact)&&!barrels_.overlap(target.unit,{entity->motion.get().x,entity->motion.get().y}))return hit(index,facing,amount);
        auto& unit=*target.unit;unit.body.hand_hp=std::max(0.,unit.body.hand_hp-amount);unit.content.barrel_remaining.set(unit.body.hand_hp);
        if(unit.orphan_barrel)unit.body.hp=unit.body.hand_hp;unit.body.hand_hurt=1.;
        if(unit.body.hand_hp<=0.)zombies_.barrel_break(target.unit);return HitResult::flag(true);
    }
    HitResult result;{ContentDamageDepth guard(state_);result=lower_.surface_hit(index,facing,amount);}
    if(amount>0.)gas_hit(attack,world_.targets->at(index));
    if(entity&&name(attack->content)=="原始豌豆射手"&&pea(entity->kind))primal_knockback(index,entity->facing*world_.runtime.plk*200.,entity);
    return result;
}
HitResult NativeContentDamage::freeze_hit(size_t index) {
    const auto attack=world_.heroes.source();const auto target=world_.targets->at(index);if(anchored(target))return HitResult::hero(0.);
    const bool cold=attack&&name(attack->content)=="寒冰辣椒";
    if(target.unit&&target.unit->orphan_barrel&&!cold){zombies_.barrel_break(target.unit);return {};}
    if(cold) {
        const auto& id=attack->source_entity.present()?attack->source_entity:attack->id;
        const std::optional<std::string> key=id.present()&&!id.is_null()?std::optional<std::string>(id.get()):std::nullopt;
        auto& hits=body(target).content_target.ice_chili_hits;if(!hits.present())hits.set({});
        if(std::find(hits.get().begin(),hits.get().end(),key)!=hits.get().end())return {};hits.get().push_back(key);
        if(target.is_hero())world_.heroes.damage(target.hero,16.,HeroHit::chili);
        else {const auto entity=attack->entity.lock();hit(index,entity?entity->facing:1.,250.);}
        frost_.freeze(target,2250.);frost_.pending.push_back(target);return {};
    }
    const double barrel_hp=body(target).hand_hp;const auto result=lower_.ash(index);
    if(target.unit&&(body(target).hp<=0.||body(target).ash.present()))zombies_.barrel_detach(target.unit,barrel_hp);return result;
}
void NativeContentDamage::knockback(size_t index,double amount) {
    const auto attack=world_.heroes.source();const auto entity=attack?attack->entity.lock():EntityRef{};
    if(entity&&name(attack->content)=="原始豌豆射手")primal_knockback(index,amount,entity);else lower_.knock(index,amount);
}
std::optional<double> NativeContentDamage::player_damage(double amount,const ZombieRef& explicit_unit,bool native_bite) {
    const auto attack=world_.heroes.source();
    const auto unit=explicit_unit?explicit_unit:attack?attack->unit.lock():ZombieRef{};
    const bool bite=(amount==1.||native_bite)&&attack&&(name(attack->content)=="海盗鹦鹉"||name(attack->content)=="乌鸦");
    if(unit) {
        if(attack.get()!=source_ref(unit).get())throw std::logic_error("content hero damage source differs from explicit unit");
        if(yes(unit->patch.no_attack))return {};
        if(native_bite) {
            const auto target=world_.heroes.active.value().target;world_.heroes.proxy(target);
            amount=zombies_.bite_damage(unit,CombatTarget::player(target));
        }else if(amount==1.&&unit->patch.bite_plant.present()&&!unit->patch.bite_plant.is_null()&&unit->patch.bite_plant.get()!=0.)amount=unit->patch.bite_plant.get();
    }else if(attack&&attack->has_zombie_name())throw std::logic_error("content hero damage requires its explicit zombie source");
    if(attack&&name(attack->projectile)=="僵尸豌豆"&&!name(attack->zombie_fire).empty())amount=name(attack->zombie_fire)=="blue"?3.:2.;
    const auto result=lower_.player_damage(amount);
    if(bite&&result.value_or(0.)!=0.) {
        if(!unit)throw std::logic_error("flyer hero damage requires its explicit source");
        const auto target=world_.heroes.active.value().target;world_.heroes.proxy(target);
        const auto& secrets=world_.heroes.players.at(seat_index(target)).value().secrets;
        if(std::find(secrets.begin(),secrets.end(),"secret:体香")!=secrets.end())unit->body.stun.set(std::max(unit->body.stun.or_missing(0.),125.));
    }
    return result;
}
void NativeContentDamage::primal_knockback(size_t index,double speed,const EntityRef& entity) {
    if(yes(entity->source.melon_splash)||!pea(entity->kind))return;
    const bool blue=projectile_fire_color(entity->source,world_.heroes.globals)=="blue";
    const double radius=blue?1.:entity->kind=="火豆"?.75:.5,scale=blue?1.5:entity->kind=="火豆"?1.25:1.;
    const auto position=entity->motion.get();const auto roster=world_.targets;const auto owner=world_.heroes.owner(source_ref(entity));
    auto& seen=entity->content_state.primal_knock_hits;if(!seen.present())seen.set({});
    for(size_t candidate=0;candidate<roster->size();++candidate) {
        const auto target=roster->at(candidate);const auto& record=body(target);
        if(record.hp<=0.||world_.heroes.owner(source(target))==owner||(target.is_hero()&&candidate!=index)||(!record.hand.empty()&&record.hand_hp>0.))continue;
        const auto p=motion(target);
        if(candidate!=index&&std::hypot(wrap_delta(position.x,p.x,world_.world_width.get()),position.y-(p.y-world_.runtime.tile))>radius*world_.runtime.tile)continue;
        const auto key=world_.heroes.source_id(source(target));
        if(std::find(seen.get().begin(),seen.get().end(),key)!=seen.get().end())continue;seen.get().push_back(key);
        motion(target).vx+=entity->facing*world_.runtime.plk*200.*scale;lower_.knock(candidate,speed*scale);
    }
}
HitResult NativeContentDamage::head_impact(const EntityRef& entity,size_t index,double facing,double amount,bool surface) {
    const auto owner=world_.heroes.owner(source_ref(entity)).value();
    HeroContext scope(world_.heroes,{owner==Seat::plant?Seat::zombie:Seat::plant,owner,CombatPhase::entities,source_ref(entity),{}});
    const auto result=surface?surface_hit(index,facing,amount):hit(index,facing,amount);
    const auto content=name(entity->source.content);
    if(content=="原始豌豆射手"||content=="甜椒投手")knockback(index,facing*world_.runtime.plk*200.);
    projectiles_.impact(entity,this);return result;
}
void NativeContentDamage::head_damage(const EntityRef& entity,size_t index,double facing,double amount,bool surface) {
    const ContentHitOrigin origin{entity,{},{},false};
    if(surface)surface_hit(index,facing,amount,origin);else hit(index,facing,amount,origin);
}
} // namespace pvz::typed72
