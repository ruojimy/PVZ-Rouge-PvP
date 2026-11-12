#include "cold_registration.h"
#include <algorithm>
namespace pvz::typed72 {
namespace {
bool has(std::span<const std::string> values,std::string_view key){return std::find(values.begin(),values.end(),key)!=values.end();}
bool yes(const Field<bool>& f){return f.present()&&!f.is_null()&&f.get();}
bool is(const Field<std::string>& f,std::string_view value){return f.present()&&!f.is_null()&&f.get()==value;}
std::shared_ptr<AttackSource> source(const NativeObject& object){return std::visit([](const auto& unit){if(!unit)throw std::invalid_argument("null registration object");return source_ref(unit);},object);}
}
std::shared_ptr<AttackSource> ColdRegistration::parent_source(const ColdParent& parent)const{
    if(parent.id)if(const auto object=world_.native_objects.get(*parent.id))return source(*object);
    return parent.fallback;
}
void ColdRegistration::register_unit(const NativeObject& object,const ColdCard& card,Seat side,bool temporary,
    const ColdRegistrationContext& context,const ColdParent* parent,std::optional<AttackIdentity> attack){
    if(team_of(side)!=side)throw std::invalid_argument("Registration requires a team, not a player seat");
    const auto identity=source(object);
    if(const auto* zombie=std::get_if<ZombieRef>(&object)){
        auto& z=**zombie;
        if(card.base_id=="zombie:墓碑吞噬者僵尸"&&!yes(z.registration.health72)){
            z.body.hp=300.;z.registration.health72.set(true);z.patch.observed_max_hp.set(300.);
        }
        if(side==Seat::zombie&&card.base_id=="zombie:伴舞僵尸")z.native.move_speed.set(60.);
    }
    if(!identity->id.present()||identity->id.is_null()||identity->id.get().empty())identity->id.set("u"+std::to_string(++sequence_));
    const auto uid=identity->id.get();
    std::visit([&](const auto& unit){
        unit->protection.card.set(card.id);
        unit->source.owner.set(std::string(seat_name(side)));
    },object);
    if(const auto* plant=std::get_if<PlantRef>(&object)){
        auto& p=**plant;p.temporary.set(temporary);
        if(p.hp.present())p.content_state.maximum_hp=p.hp;else p.content_state.maximum_hp.set(0.);
        p.registration.armor_max.set(0.);p.registration.born.set(world_.heroes.time);
    }else{
        auto& z=**std::get_if<ZombieRef>(&object);
        if(z.protection.grave){const auto& motion=z.body.motion.get();z.anchor.set({motion.x,motion.y});z.producer.set(card.producer);}
        z.registration.temporary.set(temporary);z.max_hp.set(z.body.hp);z.armor_max.set(z.body.armor_hp);z.born.set(world_.heroes.time);
    }
    const auto origin=parent?parent_source(*parent):std::shared_ptr<AttackSource>{};
    if(world_.mode!=MatchMode::duel){
        std::optional<Seat> seat=context.acting_seat&&team_of(*context.acting_seat)==side?context.acting_seat:std::nullopt;
        if(!seat&&origin)seat=origin->seat;
        identity->seat=seat.value_or(side);
    }
    if(parent)ScriptedSpawnBudget::inherit(*identity,origin.get());
    else if(context.budget_enabled&&context.scripted_wave)identity->wave_index.set(*context.scripted_wave);
    world_.native_objects.set(uid,object);
    events_.spawn({uid,card.id,side,parent?parent->id:std::nullopt,std::move(attack)});
}
void ColdRegistration::health(const PlantRef& plant,std::span<const std::string> secrets)const{
    if(!plant||plant->kind.empty())return;
    const auto found=catalog_.data().health.find("plant:"+plant->kind);
    if(found==catalog_.data().health.end()||is(plant->registration.health_form,plant->kind))return;
    double hp=found->second;
    if(has(secrets,"secret:硬化"))hp=hp>catalog_.data().hardening_min_base_hp?hp*catalog_.data().hardening_hp_factor:hp+3.;
    if(plant->kind=="路灯花"&&has(secrets,"secret:光疗"))hp*=2.;
    plant->max_hp.set(hp);plant->hp.set(hp);plant->registration.health_form.set(plant->kind);
}
void ColdRegistration::hardening(const PlantRef& plant,std::span<const std::string> secrets)const{
    if(!has(secrets,"secret:硬化")||!plant||plant->kind.empty()||is(plant->content_state.hardening_form,plant->kind))return;
    const auto key="plant:"+plant->kind;
    if(catalog_.data().health.contains(key))return;
    const auto* card=catalog_.find(key);
    if(!card||!card->native_hp.present()||card->native_hp.is_null()){plant->content_state.hardening_form.set(plant->kind);return;}
    double hp=card->native_hp.get();
    if(hp>catalog_.data().hardening_min_base_hp){hp*=catalog_.data().hardening_hp_factor;plant->max_hp.set(hp);plant->hp.set(hp);}
    else if(hp==catalog_.data().hardening_min_base_hp){hp+=3.;plant->max_hp.set(hp);plant->hp.set(hp);}
    plant->content_state.hardening_form.set(plant->kind);
}
void ColdRegistration::configure_plant(const PlantRef& plant,const ColdCard& card,std::span<const std::string> secrets)const{
    health(plant,secrets);hardening(plant,secrets);
    if(card.base_id=="plant:原始土豆地雷"){plant->hp=card.hp;plant->max_hp=card.hp;}
    if(card.base_id=="plant:土豆地雷"||card.base_id=="plant:原始土豆地雷"){
        double emergence=(card.base_id=="plant:原始土豆地雷"?24.:16.)*250.;
        if(card.native_secret_names.present()&&!card.native_secret_names.is_null()&&has(card.native_secret_names.get(),"地雷"))emergence/=2.;
        plant->buried.set(emergence);
    }
}
} // namespace pvz::typed72
