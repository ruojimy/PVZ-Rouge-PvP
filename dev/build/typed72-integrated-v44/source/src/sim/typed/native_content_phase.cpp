#include "sim/typed/native_content_phase.h"
#include "core/pymath.h"
namespace pvz::typed72 {
namespace {
constexpr double pi=0x1.921fb54442d18p+1;
bool yes(const Field<bool>& value){return value.present()&&!value.is_null()&&value.get();}
std::string_view name(const Field<std::string>& value){return value.present()&&!value.is_null()?value.get():std::string_view{};}
}
bool NativeContentPhases::custom(const Field<std::string>& name)const {
    return name.present()&&!name.is_null()&&std::find(custom_plants_.begin(),custom_plants_.end(),name.get())!=custom_plants_.end();
}
void NativeContentPhases::before_tick() {
    systems_.plants70.before_tick();systems_.mortar.before_entities();systems_.zombies64.landed();
    systems_.zombies56.before_tick();systems_.flying.before_tick();systems_.barrels.tick();
    systems_.barrel_projectiles.step();systems_.darts.separate();
}
void NativeContentPhases::projectiles() {
    const auto grenades=systems_.grenadiers.grenades;
    for(size_t index=0;index<grenades->size();++index){const auto shot=grenades->at(index);systems_.zombies70.wind(shot);systems_.zombies70.reflect(shot);}
    systems_.grenadiers.update();systems_.zombies70.projectiles();draw_projectiles();
    systems_.flying.projectiles();systems_.sea.bubbles();systems_.frost.apply();systems_.darts.projectiles();
}
void NativeContentPhases::plant_gate(PlantRef plant) {
    systems_.sea.gate(plant);systems_.september.advance(plant);systems_.flying.advance(plant);
    systems_.reeds.advance(plant);systems_.mortar.advance(plant);systems_.plants70.plant_tick(plant);
    if(custom(plant->source.content)){plant->content_state.before_shot.set(plant->shooting.or_missing(0.));plant->content_state.before_cd.set(plant->shoot_cd.or_missing(0.));}
}
void NativeContentPhases::after_plants() {
    systems_.lantern.pulses();systems_.vines.tick();systems_.frost.apply();draw_effects();systems_.darts.clover_blow();
    const auto plants=world_.plant_roster;for(size_t i=0;i<plants->size();++i) {
        const auto plant=plants->at(i);if(!custom(plant->source.content))continue;
        if(plant->shoot_cd.or_missing(0.)>plant->content_state.before_cd.or_missing(0.)+2.)plant->shoot_cd.set(std::max(0.,plant->content_state.interval.get()-1.));
    }
    const auto entities=world_.runtime.entities.list();for(size_t i=0;i<entities->size();++i) {
        const auto entity=entities->at(i);const auto& kind=entity->kind;
        if(yes(entity->content_state.ready)||!custom(entity->source.content)||(kind!="豌豆"&&kind!="冰豆"&&kind!="火豆"&&kind!="蓝火豆"&&kind!="西瓜"))continue;
        entity->content_state.ready.set(true);const auto content=name(entity->source.content);
        if(content=="甜椒投手")entity->art_name.set("甜椒弹");else if(ContentDarts::content(content))ContentDarts::prepare(entity);
        else if(content=="原始豌豆射手")entity->art_name.set("原始豌豆弹");
    }
}
void NativeContentPhases::after_birth(const std::shared_ptr<AttackSource>& source,size_t first) {
    if(!source)return;const auto roster=world_.runtime.entities.list();const EntityRoster born(first<roster->size()?roster->begin()+first:roster->end(),roster->end());
    for(const auto& entity:born) {
        const auto content=name(source->content);if(!content.empty())entity->source.content.set(std::string(content));
        const auto& kind=source->plant.present()?source->plant:source->plant_kind;
        if(kind.present())entity->source.plant_kind=kind;else entity->source.plant_kind.set_null();
        if(ContentDarts::content(content)&&entity->kind=="豌豆")ContentDarts::prepare(entity);
        if(content=="寒冰辣椒"&&entity->kind=="火")entity->art_name.set("寒冰地火");
        if(name(source->plant)=="裂荚射手")systems_.mortar.split_pea_blue(entity);
    }
}
void NativeContentPhases::entity_gate(const EntityRef& entity) {
    const auto content=name(entity->source.content);
    if(content=="原始豌豆射手"&&(entity->kind=="火豆"||entity->kind=="蓝火豆")) {
        presentation_.restore_content_art();const bool blue=projectile_fire_color(entity->source,world_.heroes.globals)=="blue";
        presentation_.alias_content_art(entity->kind,blue?"原始蓝火豆":"原始火豆");
        if(blue&&entity->kind=="火豆")presentation_.alias_content_art("蓝火豆","原始蓝火豆");
    }
    if(content=="寒冰辣椒")for(const std::string key:{"火1.1","火1.2","火1.3","火2","火3","火尾1","火尾2","火尾3"})
        if(presentation_.has_content_sprite(key))presentation_.alias_content_art(key,"寒冰-"+key);
}
void NativeContentPhases::draw_projectiles() {
    if(!drawing_)return;const auto roster=world_.runtime.entities.list();for(size_t i=0;i<roster->size();++i) {
        const auto entity=roster->at(i);if((!yes(entity->mortar.mortar)&&!yes(entity->mortar.multi_red))||entity->expires.or_missing(0.)>0.)continue;
        const auto p=entity->motion.get();const double angle=p.vx!=0.||p.vy!=0.?-std::atan2(p.vy,p.vx)*180./pi:0.;
        std::optional<Point> trail;std::string tail;
        if(entity->kind=="火豆"||entity->kind=="蓝火豆") {
            const bool blue=projectile_fire_color(entity->source,world_.heroes.globals)=="blue";tail=std::string(blue?"蓝火尾":"火尾")+std::to_string(1+int(py::mod(double(world_.heroes.tick/10),3.)));
            const double length=std::max(1e-9,std::hypot(p.vx,p.vy));trail=Point{p.x-p.vx/length*world_.runtime.tile*.4,p.y-p.vy/length*world_.runtime.tile*.4};
        }
        presentation_.draw_mortar_projectile(entity,angle,trail,tail);
    }
}
void NativeContentPhases::draw_effects() {
    const auto tick=world_.heroes.tick;
    std::erase_if(systems_.september.effects,[&](const auto& effect){return tick-effect.tick>=100;});
    if(drawing_)for(const auto& effect:systems_.september.effects)presentation_.draw_ghost_effect(effect);
    std::erase_if(systems_.reeds.bolts,[&](const auto& effect){return tick-effect.tick>=70;});
    if(drawing_)for(const auto& effect:systems_.reeds.bolts)presentation_.draw_reed_effect(effect);
    std::erase_if(systems_.mortar.swipes,[&](const auto& effect){return tick-effect.tick>=60;});
    std::erase_if(systems_.grenadiers.blasts,[&](const auto& effect){return tick-effect.tick>=45;});
    if(drawing_){
        for(const auto& effect:systems_.mortar.swipes)presentation_.draw_spring_effect(effect);
        for(const auto& effect:systems_.grenadiers.blasts)presentation_.draw_grenade_effect(effect);
        for(const auto& shot:*systems_.grenadiers.grenades)
            presentation_.draw_grenade_projectile(shot,py::mod(double(tick)*9.,360.),shot->defused?std::max(60.,255.-double(shot->age)):255.);
    }
}
void NativeContentPhases::draw_zombie70_effects() {
    if(!drawing_)return;
    const double tile=world_.runtime.tile,width=world_.world_width.get();
    for(const auto& shot:world_.content_projectiles.shots) {
        const bool bone=name(shot->kind)=="bone",hook=name(shot->kind)=="hook",defused=yes(shot->defused);
        if(hook&&!defused)if(const auto source=world_.native_objects.get(shot->source.get())) {
            const auto target=std::visit([](const auto& object)->ContentTarget {
                using Object=std::decay_t<decltype(object)>;
                if constexpr(std::is_same_v<Object,PlantRef>)return object;
                else return CombatTarget::zombie(object);
            },*source);
            const auto point=systems_.targets.point(target);
            const double dx=wrap_delta(point.x,shot->motion.x,width),dy=shot->motion.y-point.y;
            const auto count=std::max<int64_t>(1,int64_t(std::hypot(dx,dy)/(tile*.15)));
            for(int64_t i=0;i<count;++i) {
                const double f=double(i)/double(count);presentation_.draw_hook_rope({point.x+dx*f,point.y+dy*f});
            }
        }
        presentation_.draw_zombie_projectile(shot,bone?"死神骨头":"钩索钩头",bone?shot->age*5.:0.,defused?std::max(20.,255.-shot->age*2.):255.);
    }
    std::erase_if(systems_.plants70.flashes,[&](const auto& flash){return world_.heroes.tick-flash.tick>=100;});
    for(const auto& flash:systems_.plants70.flashes)presentation_.draw_lettuce_flash(flash);
}
} // namespace pvz::typed72
