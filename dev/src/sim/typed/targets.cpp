#include "sim/typed/targets.h"
#include <algorithm>
#include <exception>

namespace pvz::typed72 {
namespace {
std::string_view name(const Field<std::string>& f){return f.present()&&!f.is_null()?f.get():std::string_view{};}
bool chili(const std::shared_ptr<AttackSource>& s){return s&&(name(s->plant)=="火爆辣椒"||s->zombie_name()=="辣椒僵尸"||name(s->projectile)=="火");}
double positive_or(const Field<double>& f,double fallback){return f.present()&&!f.is_null()&&f.get()!=0.?f.get():fallback;}
}
FullTargetsScope::FullTargetsScope(std::shared_ptr<TargetRoster>& roster,std::optional<std::span<const CombatTarget>> extras,std::shared_ptr<TargetRoster> original) {
    if(!extras)return;
    if(!roster)throw std::invalid_argument("null target roster");
    current_=&roster;original_=original?std::move(original):roster;
    for(const auto& target:*extras)if(std::find(original_->begin(),original_->end(),target)==original_->end()) {
        original_->push_back(target);inserted_.push_back(target);
    }
}
void FullTargetsScope::close() {
    if(!current_)return;if(!*current_)throw std::logic_error("null replacement roster");
    TargetRoster keep;keep.reserve((*current_)->size());
    for(const auto& target:**current_)if(std::find(inserted_.begin(),inserted_.end(),target)==inserted_.end())keep.push_back(target);
    *original_=std::move(keep);*current_=original_;current_=nullptr;
}
FullTargetsScope::~FullTargetsScope() noexcept{if(current_)try{close();}catch(...){std::terminate();}}
void TargetDamage::record_melon(const CombatTarget& target) {
    auto source=heroes_.source();if(!source)return;const auto projectile=name(source->projectile);
    if(projectile!="西瓜"&&projectile!="冰瓜"&&projectile!="火豆"&&projectile!="蓝火豆")return;
    if(!source->melon_hits.present())source->melon_hits.set({});
    auto& hits=source->melon_hits.get();
    const auto id=target.is_hero()?"hero:"+std::string(seat_name(target.hero)):heroes_.source_id(source_ref(target.unit));
    if(std::find(hits.begin(),hits.end(),id)==hits.end())hits.push_back(id);
}
HitResult TargetDamage::ordinary(CombatTarget target,double facing,double amount) {
    record_melon(target);auto source=heroes_.source();
    if((target.is_hero()||!has_packet(target.unit))&&source&&name(source->projectile)=="星星")amount=30.;
    if(!target.is_hero())return unit_damage(Callback::ordinary,target.unit,facing,amount);
    if(const auto override=heroes_.source_amount(target.hero))amount=*override;
    return HitResult::hero(heroes_.damage(target.hero,amount,heroes_.damage_kind));
}
HitResult TargetDamage::surface(CombatTarget target,double facing,double amount) {
    record_melon(target);auto source=heroes_.source();
    if((target.is_hero()||!has_packet(target.unit))&&source&&name(source->projectile)=="星星")amount=30.;
    if(!target.is_hero())return unit_damage(Callback::surface,target.unit,facing,amount);
    ordinary(target,facing,amount);return HitResult::flag(false);
}
HitResult TargetDamage::shielded(Callback callback,const ZombieRef& target,double facing,double amount) {
    if(callback==Callback::ordinary&&shield_first&&protection_.shield_first(target->damage_target(),target->body.hand_hp)) {
        raw_.surface(target,facing,amount);return {};
    }
    return callback==Callback::ordinary?raw_.ordinary(target,facing,amount):raw_.surface(target,facing,amount);
}
HitResult TargetDamage::unit_damage(Callback callback,const ZombieRef& target,double facing,double amount) {
    if(has_packet(target))return callback==Callback::ordinary?raw_.ordinary(target,facing,amount):raw_.surface(target,facing,amount);
    if(adjust_amount)amount=protection_.amount(target->damage_target(),amount);
    packets_.insert(target.get());
    struct PacketGuard {std::unordered_set<const CombatZombie*>& packets;const CombatZombie* unit;~PacketGuard(){packets.erase(unit);}} guard{packets_,target.get()};
    const auto head=target->body.armor,hand=target->body.hand;
    const double head_hp=target->body.armor_hp,hand_hp=target->body.hand_hp;
    HitResult result;std::exception_ptr failure;
    try{result=shielded(callback,target,facing,amount);}catch(...){failure=std::current_exception();}
    if(watch_armor) {
        if(!head.empty()&&head_hp>0&&target->body.armor_hp<=0)raw_.armor_broken(target,ArmorSlot::head,head,positive_or(target->armor_max,head_hp));
        if(!hand.empty()&&hand_hp>0&&target->body.hand_hp<=0)raw_.armor_broken(target,ArmorSlot::hand,hand,positive_or(target->hand_max,hand_hp));
    }
    if(failure)std::rethrow_exception(failure);return result;
}
HitResult TargetDamage::ash(CombatTarget target) {
    auto source=heroes_.source();
    if(target.is_hero())return HitResult::hero(heroes_.damage(target.hero,chili(source)?16.:40.,HeroHit::ash));
    auto& unit=*target.unit;auto& body=unit.body;
    if(chili(source)) {
        const auto key=heroes_.chili_attack_key();
        if(!unit.chili_ash_hits.present())unit.chili_ash_hits.set({});
        auto& seen=unit.chili_ash_hits.get();if(std::find(seen.begin(),seen.end(),key)!=seen.end())return {};
        seen.push_back(key);
    }
    if(source&&(name(source->content)=="原始土豆地雷"||chili(source))) {
        const double scaled=adjust_amount?protection_.amount(unit.damage_target(),750.):750.;
        if(!body.ash.present()&&body.hp+body.armor_hp>scaled)return unit_damage(Callback::ordinary,target.unit,1.,750.);
        body.ash.set(0.);return {};
    }
    const double scaled=adjust_amount?protection_.amount(unit.damage_target(),500.):500.;
    if(scaled<500.&&!body.ash.present()&&body.hp+body.armor_hp>scaled)return unit_damage(Callback::ordinary,target.unit,1.,500.);
    return raw_.ash(target.unit);
}
} // namespace pvz::typed72
