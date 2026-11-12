#include "sim/typed/barrel_projectiles.h"
#include "sim/typed/bonus_projectiles.h"
#include "sim/typed/content_entity_state.h"
#include "core/pymath.h"
#include <array>
namespace pvz::typed72 {
namespace {
bool yes(const Field<bool>& value){return value.present()&&!value.is_null()&&value.get();}
bool smart(const Field<SmartProjectile>& field) {
    if(!field.present()||field.is_null())return false;
    const auto& value=field.get();
    return value.target_index.present()||value.target_id.present()||value.initial_speed.present()||
        value.gravity.present()||value.hit_time.present()||value.lead_scale.present()||value.created.present();
}
std::optional<double> base_impact(std::string_view name) {
    static constexpr std::array<std::pair<std::string_view,double>,10> amounts{{
        {"豌豆",20.},{"冰豆",20.},{"卷心菜",30.},{"玉米粒",5.},{"黄油",10.},
        {"西瓜",150.},{"冰瓜",150.},{"尖刺",10.},{"火豆",20.},{"蓝火豆",30.}}};
    for(const auto& [kind,amount]:amounts)if(name==kind)return amount;return {};
}
}
void BarrelProjectiles::record_melon(size_t index) {
    const auto source=world_.heroes.source();if(!source)return;
    const auto name=source->projectile.or_missing("");
    if(name!="西瓜"&&name!="冰瓜"&&name!="火豆"&&name!="蓝火豆")return;
    const auto target=world_.targets->at(index);
    const auto id=target.is_hero()?"hero:"+std::string(seat_name(target.hero)):world_.heroes.source_id(source_ref(target.unit));
    if(!source->melon_hits.present())source->melon_hits.set({});
    auto& hits=source->melon_hits.get();if(std::find(hits.begin(),hits.end(),id)==hits.end())hits.push_back(id);
}
void BarrelProjectiles::step() {
    std::vector<ZombieRef> barrels;
    for(const auto& target:*world_.targets)if(target.unit&&NativeBarrels::active(*target.unit))barrels.push_back(target.unit);
    if(barrels.empty())return;
    const auto entities=world_.runtime.entities.list();auto kept=std::make_shared<EntityRoster>();
    const double tile=world_.runtime.tile,width=world_.world_width.get();
    for(size_t e_index=0;e_index<entities->size();++e_index) {
        const auto entity=entities->at(e_index);const auto amount=base_impact(entity->kind);
        if(!amount||yes(entity->content_state.dart)||entity->expires.or_missing(0.)>0.){kept->push_back(entity);continue;}
        // Source holds the selected position list through synchronous callbacks.
        const auto position=entity->motion.retain();ZombieRef hit;
        for(const auto& candidate:barrels) {
            if(!NativeBarrels::active(*candidate)||world_.heroes.owner(source_ref(candidate))==world_.heroes.owner(source_ref(entity)))continue;
            if((entity->kind=="火豆"||entity->kind=="蓝火豆")&&!candidate->orphan_barrel)continue;
            const auto barrel=*candidate->barrel_position.get();
            const double dx=wrap_delta(position->x,barrel.x,width),dy=barrel.y-tile*.6-position->y;
            const double length=position->vx*position->vx+position->vy*position->vy;
            const double t=length!=0.?std::max(0.,std::min(1.,(dx*position->vx+dy*position->vy)/length)):0.;
            const double x=dx-position->vx*t,y=dy-position->vy*t,radius=tile*.68;
            if(x*x+y*y<=radius*radius){hit=candidate;break;}
        }
        if(!hit){kept->push_back(entity);continue;}
        entity->content_state.barrel_contact.set(true);
        const auto owner=world_.heroes.owner(source_ref(entity));if(!owner)throw std::logic_error("barrel projectile has no allegiance");
        {
            HeroContext context(world_.heroes,{*owner==Seat::plant?Seat::zombie:Seat::plant,*owner,CombatPhase::entities,source_ref(entity),{}});
            const auto found=std::find(world_.targets->begin(),world_.targets->end(),CombatTarget::zombie(hit));
            if(found==world_.targets->end())throw std::logic_error("barrel target removed before impact");
            const auto index=size_t(found-world_.targets->begin());double damage=*amount;
            if(entity->kind=="火豆") {
                const auto& secret_list=world_.heroes.globals.secrets;
                if(secret_list.present()&&!secret_list.is_null()) {
                    const auto& secrets=*secret_list.get();
                    if(std::find(secrets.begin(),secrets.end(),"蓝火")!=secrets.end())damage=30.;
                }
            }
            if(hit->orphan_barrel&&(entity->kind=="豌豆"||entity->kind=="冰豆"))damage=10.;
            services_.surface_zombie(index,entity->facing,damage);
            if(hit->orphan_barrel&&hit->body.hp>0.) {
                if(entity->kind=="冰豆")hit->body.ice.set(1200.);
                else if(entity->kind=="黄油")hit->body.butter.set(3000.);
                else if(entity->kind=="火豆"||entity->kind=="蓝火豆")hit->body.ice.erase();
            }
            if(smart(entity->service.smart)&&!yes(entity->bonus.damage_done)) {
                const double base=BonusProjectiles::base_damage(entity),speed=py::hypot(position->vx,position->vy);
                const double initial=std::max(1.,entity->service.smart.get().initial_speed.or_missing(speed));
                const double extra=base*.45*std::max(0.,speed/initial-1.);entity->bonus.damage_done.set(true);
                if(extra>.5){ContentDamageDepth depth(state_);services_.damage_zombie(index,entity->facing,extra);}
            }
            record_melon(index);
            const auto original=world_.targets;const auto extras=services_.extra_targets();
            FullTargetsScope full(world_.targets,extras?std::optional<std::span<const CombatTarget>>(*extras):std::nullopt,original);
            rules_.impact(entity,&services_);
        }
        // Deliberately not a guard: the original pop is not in a finally block.
        entity->content_state.barrel_contact.erase();
    }
    world_.runtime.entities.replace(std::move(kept));
}
} // namespace pvz::typed72
