#include "sim/typed/projectile.h"

namespace pvz::typed72 {
namespace {
std::string_view name(const Field<std::string>& f){return f.present()&&!f.is_null()?f.get():std::string_view{};}
bool pea(std::string_view n){return n=="豌豆"||n=="冰豆"||n=="火豆"||n=="蓝火豆"||n=="僵尸豌豆";}
bool flag(const Field<bool>& f){return f.present()&&!f.is_null()&&f.get();}
template<class T> void set_default(Field<T>& target,const Field<T>& value){if(!target.present())target=value;}
template<class T> void set_default(Field<T>& target,T value){if(!target.present())target.set(std::move(value));}
}
void begin_flight(AttackSource& entity,ProjectileFlight& flight,const Motion* position,const AttackSource* source) {
    const auto n=name(entity.projectile);
    if(n=="篮球"&&position)set_default(flight.basket_last,Point{position->x,position->y});
    if(!(pea(n)||n=="泡泡"||n=="海泡泡"||n=="尖刺"||n=="星星")||flag(entity.cattail)||!position)return;
    double fallback=pea(n)||n=="星星"?32.:64.;
    if(source) {
        const auto plant=name(source->plant);
        if(plant=="杨桃")fallback=32.;else if(plant=="胆小菇")fallback=16.;else if(plant=="小喷菇")fallback=8.;
    }
    const Field<double> limit=source&&source->flight_limit_tiles.present()?source->flight_limit_tiles:Field<double>(fallback);
    if(limit.is_null()||limit.get()!=64.)set_default(entity.flight_limit_tiles,limit);
    set_default(flight.last,Point{position->x,position->y});set_default(flight.distance,0.);
    if(pea(n))set_default(flight.form,ProjectileForm{std::string(n),entity.fire_lit.present(),std::string(name(entity.zombie_fire))});
}
void HeroCombat::tag_entity(const std::shared_ptr<AttackSource>& entity,const Motion* position,ProjectileFlight& flight,
                           std::optional<Seat> explicit_owner,const std::shared_ptr<AttackSource>& explicit_source) {
    if(!entity)throw std::invalid_argument("null typed entity");
    const auto parent=explicit_source?explicit_source:source();
    const auto allegiance=explicit_owner?explicit_owner:owner(parent);
    if(!allegiance||!contains(*allegiance))throw std::invalid_argument("native entity has no explicit source allegiance");
    source_id(entity);set_default(entity->owner,std::string(seat_name(*allegiance)));
    Field<std::string> original_owner{std::string(seat_name(*allegiance))};
    if(parent&&parent->owner.present())original_owner=parent->owner;
    if(parent&&parent->original_owner.present())original_owner=parent->original_owner;
    set_default(entity->original_owner,original_owner);
    // Preserve eager evaluation of Python setdefault/get defaults: even an
    // existing destination field still gives an unnamed parent its source ID.
    set_default(entity->source_entity,source_id(parent));
    const auto fallback_root=source_id(parent);
    const auto root=parent&&parent->root_source.present()?parent->root_source:Field<std::string>(fallback_root);
    set_default(entity->root_source,root);
    if(name(entity->projectile)=="尖刺"&&parent)
        entity->cattail.set(name(parent->plant)=="香蒲"||name(parent->id).starts_with("hero:plant"));
    begin_flight(*entity,flight,position,parent.get());
    const auto default_attack=AttackIdentity::native(source_id(parent?parent:entity),tick);
    const auto attack=parent&&parent->instant_attack?*parent->instant_attack:default_attack;
    if(!entity->instant_attack)entity->instant_attack=attack;
}
} // namespace pvz::typed72
