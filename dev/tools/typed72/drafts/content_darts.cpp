#include "sim/typed/content_darts.h"
#include "sim/typed/content_entity_state.h"
#include "sim/typed/projectile_rules.h"
#include "core/pymath.h"
namespace pvz::typed72 {
namespace {
bool yes(const Field<bool>& value){return value.present()&&!value.is_null()&&value.get();}
bool named(const Field<std::string>& value,std::string_view name){return value.present()&&!value.is_null()&&value.get()==name;}
// Native try/finally removes a marker even if it existed before this call.
struct RemoveMarker {Field<bool>& value;~RemoveMarker(){value.erase();}};
}
void ContentDarts::prepare(const EntityRef& entity) {
    auto& state=entity->content_state;
    const std::string art=named(entity->source.content,"毒镖射手")?"毒镖弹":"回旋镖弹";
    entity->kind=art;entity->art_name.set(art);state.ready.set(true);state.dart.set(true);
    state.distance.set(0.);state.leg_hits.set({});state.returning.set(false);state.turned.set(false);
    state.launch_direction.set(entity->facing);entity->motion.get().vy=0.;state.speed.set(std::abs(entity->motion.get().vx));
}
void ContentDarts::separate() {
    auto darts=std::make_shared<EntityRoster>(),native=std::make_shared<EntityRoster>();
    for(const auto& entity:*world_.runtime.entities.list())(yes(entity->content_state.dart)?*darts:*native).push_back(entity);
    pending=std::move(darts);world_.runtime.entities.replace(std::move(native));
}
ZombieRef ContentDarts::body(const ContentTarget& target) {
    if(const auto* body=std::get_if<CombatTarget>(&target))return body->unit;return {};
}
bool ContentDarts::same(const ContentTarget& first,const ContentTarget& second){return first==second;}
std::optional<Ellipse> ContentDarts::head(const ContentTarget& target)const {
    if(const auto unit=body(target))return plant_zombie_head(*unit,world_.runtime.tile,collision_);return {};
}
bool ContentDarts::head_overlaps(const ContentTarget& target,Point center,double radius)const {
    if(const auto unit=body(target))return head_overlaps_area(*unit,center,radius,radius,world_.runtime.tile,world_.world_width.get(),collision_);
    return false;
}
void ContentDarts::projectiles() {
    const auto captured=pending;EntityRoster survivors;const double tile=world_.runtime.tile,width=world_.world_width.get();
    for(size_t index=0;index<captured->size();++index) {
        const auto entity=captured->at(index);auto& state=entity->content_state;const auto position=entity->motion.retain();
        const double oldx=position->x,oldy=position->y,direction=state.launch_direction.get();
        if(state.returning.get())position->vx-=direction*state.speed.get()/125.;
        if(state.returning.get()&&!state.turned.get()&&position->vx*direction<=0.){state.turned.set(true);state.leg_hits.set({});}
        position->x=py::mod(oldx+position->vx,width);position->y+=position->vy;
        state.distance.get()+=std::hypot(position->vx,position->vy);if(state.distance.get()>=64.*tile)continue;
        std::optional<NativeObject> shooter;
        if(entity->source.source_entity.present()&&!entity->source.source_entity.is_null())shooter=world_.native_objects.get(entity->source.source_entity.get());
        if(state.turned.get()&&shooter)if(const auto* plant=std::get_if<PlantRef>(&*shooter);plant&&(*plant)->hp.or_missing(0.)>0.) {
            const auto point=damage_.point(*plant);
            if(std::abs(wrap_delta(point.x,position->x,width))<tile*.6&&std::abs(point.y-position->y)<tile)continue;
        }
        for(const auto& target:queries_.enemies(source_ref(entity))) {
            const auto id=world_.heroes.source_id(queries_.source(target));const auto& hits=state.leg_hits.get();
            if(std::find(hits.begin(),hits.end(),id)!=hits.end())continue;
            auto point=damage_.point(target);const double dx=wrap_delta(oldx,point.x,width);const auto unit=body(target);
            // Hero colliders are dict subclasses; the source fast path admits
            // only exact native dictionaries, never those proxy records.
            const bool ordinary=std::holds_alternative<PlantRef>(target)||bool(unit);
            const bool extended=unit&&(named(unit->source.content,"滚桶僵尸")||unit->orphan_barrel||yes(unit->patch.plant_zombie));
            if(broad_phase&&ordinary&&!extended&&(std::abs(dx)>std::abs(position->vx)+std::max(1.,tile*.5)+1e-6||
                std::abs(point.y-oldy)>std::abs(position->y-oldy)+std::max(1.,tile*.8)+1e-6))continue;
            const Point start{0.,oldy},end{position->vx,position->y};
            bool contact=segment_hits_ellipse(start,end,{{dx,point.y},tile*.5,tile*.8}),barrel_contact=false;
            if(unit&&NativeBarrels::active(*unit)) {
                const auto barrel=*unit->barrel_position.get();
                barrel_contact=segment_hits_ellipse(start,end,{{wrap_delta(oldx,barrel.x,width),barrel.y-tile*.6},tile*.65,tile*.65});
                if(unit->orphan_barrel)contact=barrel_contact;
                if(barrel_contact){contact=true;point={barrel.x,barrel.y-tile*.6};}
            }
            if(!contact)if(auto ellipse=head(target)) {
                const auto center=ellipse->center;ellipse->center.x=wrap_delta(oldx,center.x,width);
                contact=segment_hits_ellipse(start,end,*ellipse);if(contact)point=center;
            }
            if(!contact)continue;state.leg_hits.get().push_back(id);
            const bool poison=named(entity->source.content,"毒镖射手");
            if(barrel_contact)state.barrel_contact.set(true);
            {RemoveMarker clear{state.barrel_contact};damage_.damage(source_ref(entity),target,poison?8.:4.,entity->facing);}
            if(poison) {
                const auto owner=world_.heroes.owner(source_ref(entity));if(!owner)throw std::logic_error("dart has no allegiance");
                status_.apply(target,2,4.,*owner);
                for(const auto& other:queries_.enemies(source_ref(entity))) {
                    if(same(other,target))continue;const auto other_point=damage_.point(other);
                    if((std::abs(wrap_delta(point.x,other_point.x,width))<1.3*tile&&std::abs(point.y-other_point.y)<1.3*tile)||head_overlaps(other,point,1.3*tile)) {
                        entity->source.area_damage.set(true);
                        {RemoveMarker clear{entity->source.area_damage};damage_.damage(source_ref(entity),other,8.,entity->facing);}
                        const auto splash_owner=world_.heroes.owner(source_ref(entity));if(!splash_owner)throw std::logic_error("dart has no allegiance");
                        status_.apply(other,2,4.,*splash_owner);
                    }
                }
            }
            if(!state.returning.get()&&state.leg_hits.get().size()>=4){state.returning.set(true);break;}
        }
        if(state.distance.get()>20.*tile)state.returning.set(true);entity->facing=position->vx>=0.?1.:-1.;
        if(drawing_)presentation_.draw_dart(entity,{position->x,position->y},py::mod(double(world_.heroes.tick)*12.,360.));
        survivors.push_back(entity);
    }
    for(const auto& entity:survivors)world_.runtime.entities.emplace(entity);
    pending=std::make_shared<EntityRoster>();
}
void ContentDarts::clover_blow() {
    const auto plants=world_.plant_roster;
    bool found=false;for(const auto& plant:*plants)if(plant->kind=="三叶草"){found=true;break;}if(!found)return;
    const double plk=world_.runtime.plk!=0.?world_.runtime.plk:1.;
    const double limit=(world_.wind_environment.zombie_speed_max!=0.?world_.wind_environment.zombie_speed_max:10.)*10.;
    for(const auto& plant:*plants)if(plant->kind=="三叶草") {
        const double x=(plant->cell.x+.5)*world_.runtime.tile,direction=plant->facing>=0.?1.:-1.;
        for(const auto& target:*world_.targets)if(const auto unit=target.unit) {
            if((!named(unit->source.content,"海盗鹦鹉")&&!named(unit->source.content,"乌鸦"))||unit->body.hp<=0.)continue;
            auto& position=unit->body.motion.get();if((position.x-x)*direction<0.)continue;
            if(position.vx*direction<limit)position.vx=direction*limit;
            position.vy=std::min(position.vy,-14.*plk);unit->body.blown.set(true);
        }
    }
}
} // namespace pvz::typed72
