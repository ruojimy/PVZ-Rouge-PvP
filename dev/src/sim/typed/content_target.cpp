#include "sim/typed/content_target.h"
#include "sim/typed/projectile_rules.h"
#include <algorithm>
namespace pvz::typed72 {
Point ContentTargets::point(const ContentTarget& target)const {
    const double tile=world_.runtime.tile;
    if(const auto* plant=std::get_if<PlantRef>(&target)) {
        const auto& p=**plant;
        if(p.source.content.present()&&!p.source.content.is_null()&&p.source.content.get()=="抓人草触手")return p.head_point.get();
        return {(double(p.cell.x)+.5)*tile,(p.cell.y+.45)*tile};
    }
    const auto& t=std::get<CombatTarget>(target);
    if(!t.is_hero())return content_target_point(*t.unit,tile,catalog_);
    const auto& p=*world_.heroes.cached_proxy(t.hero).position;
    return {p.x,p.y-tile};
}
std::optional<Seat> ContentTargets::owner(const ContentTarget& target)const {
    if(const auto* p=std::get_if<PlantRef>(&target))return world_.heroes.owner(source_ref(*p));
    const auto& t=std::get<CombatTarget>(target);
    return t.is_hero()?std::optional<Seat>(team_of(t.hero)):world_.heroes.owner(source_ref(t.unit));
}
bool ContentTargets::contact(const ContentTarget& target,Point start,Point delta)const {
    if(const auto* t=std::get_if<CombatTarget>(&target);t&&!t->is_hero())
        return flying_target_contact(*t->unit,start,delta,world_.runtime.tile,width_,catalog_);
    const auto p=point(target);const double tile=world_.runtime.tile;
    const bool plant=std::holds_alternative<PlantRef>(target);
    const double scale=plant?1.:unit_scale_factor(*world_.heroes.proxy_source(std::get<CombatTarget>(target).hero),catalog_);
    return segment_hits_ellipse({0.,start.y},{delta.x,start.y+delta.y},
        {{wrap_delta(start.x,p.x,width_),p.y},tile*(plant?.45:.5*scale),tile*(plant?.45:.8*scale)});
}
void ContentTargets::damage(const std::shared_ptr<AttackSource>& source,const ContentTarget& target,
                            double amount,double facing,bool surface,HeroHit kind) {
    if(!source)throw std::invalid_argument("null content damage source");
    auto& heroes=world_.heroes;const auto attacker=heroes.owner(source);
    if(owner(target)==attacker)return;
    if(!attacker)throw std::invalid_argument("content attack has no allegiance");
    HeroContext context(heroes,{*attacker==Seat::plant?Seat::zombie:Seat::plant,*attacker,CombatPhase::content,source,{}});
    if(const auto* p=std::get_if<PlantRef>(&target)) {
        auto& plant=**p;
        if(plant.kind=="魅惑菇"&&!source->charmed.present())source->charmed.set(0.);
        const double old=plant.hp.get();
        static const std::string no_hand;
        const auto loss=world_.protection.amount({plant.hp.get(),no_hand,plant.source,plant.protection},amount);
        plant.hp.set(old-loss);plant.hurt.set(1.);
        if(plant.hp.get()<=0.)plant.dead.set(DeathMarker(0.));
    }else {
        const auto& t=std::get<CombatTarget>(target);
        if(t.is_hero())heroes.damage(t.hero,amount,kind);
        else {
            const auto found=std::find(world_.targets->begin(),world_.targets->end(),t);
            if(found==world_.targets->end())return;
            if(dispatch_) {
                const auto index=size_t(found-world_.targets->begin());
                if(surface)dispatch_->surface(index,facing,amount);else dispatch_->ordinary(index,facing,amount);
            }else {
                if(surface)damage_->surface(t,facing,amount);else damage_->ordinary(t,facing,amount);
            }
        }
    }
}
} // namespace pvz::typed72
