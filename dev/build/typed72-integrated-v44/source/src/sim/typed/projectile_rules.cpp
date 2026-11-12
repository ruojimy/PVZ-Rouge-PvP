#include "sim/typed/projectile_rules.h"
#include "sim/typed/projectile.h"
#include "sim/typed/content_target.h"
#include "core/pymath.h"
#include <algorithm>
#include <cmath>
namespace pvz::typed72 {
namespace {
// Exact binary64 math.pi; NDK r25's libc++ has no <numbers> header.
constexpr double pi=0x1.921fb54442d18p+1;
bool yes(const Field<bool>& f){return f.present()&&!f.is_null()&&f.get();}
std::string_view name(const Field<std::string>& f){return f.present()&&!f.is_null()?f.get():std::string_view{};}
std::optional<std::string> optional_name(const Field<std::string>& f){return f.present()&&!f.is_null()?std::optional<std::string>(f.get()):std::nullopt;}
double number(const Field<double>& f,double fallback){return f.present()&&!f.is_null()?f.get():fallback;}
}
double unit_scale_factor(const AttackSource& source,const CollisionCatalog& catalog) {
    const auto content=name(source.content),variant=name(source.variant);
    const auto root=!content.empty()?content:!variant.empty()?variant:source.zombie_name();
    const auto found=catalog.unit_scale.find(std::string(root));
    return found==catalog.unit_scale.end()?1.:found->second;
}
double wrap_delta(double from,double to,double width) {
    if(width==0.)throw std::domain_error("zero wrapped width");return py::mod(to-from+width/2.,width)-width/2.;
}
bool segment_hits_ellipse(Point a,Point b,const Ellipse& e) {
    const double rx=std::max(1.,e.rx),ry=std::max(1.,e.ry);
    a={(a.x-e.center.x)/rx,(a.y-e.center.y)/ry};b={(b.x-e.center.x)/rx,(b.y-e.center.y)/ry};
    const Point delta{b.x-a.x,b.y-a.y};const double denom=delta.x*delta.x+delta.y*delta.y;Point closest=b;
    if(denom>.000001) {const double t=std::max(0.,std::min(1.,-(a.x*delta.x+a.y*delta.y)/denom));closest={a.x+delta.x*t,a.y+delta.y*t};}
    return closest.x*closest.x+closest.y*closest.y<=1.;
}
static Ellipse raw_plant_zombie_head_geometry(const CombatZombie& u,double tile,const CollisionCatalog& catalog) {
    PlantHeadGeometry cfg;cfg.fire_frames=catalog.default_fire_frames;
    if(const auto i=catalog.plant_heads.find(std::string(name(u.patch.plant_name)));i!=catalog.plant_heads.end())cfg=i->second;
    const bool duck=yes(u.patch.duck);const double direction=u.body.facing<0.?-1.:1.;
    const double animation=number(u.patch.fire_animation,0.),frames=std::max(1.,cfg.fire_frames);
    const double elapsed=std::max(0.,frames-animation),window=std::max(1.,frames*.75);
    const double phase=animation>0.?std::sin(pi*std::min(window,elapsed)/window):0.;
    const double recoil=cfg.fumeshroom?0.:std::max(0.,phase)*tile*.05;
    return Ellipse{{u.body.motion.get().x+direction*tile*(duck?cfg.duck_head_x:cfg.head_x)-direction*recoil,
        u.body.motion.get().y-tile*(duck?cfg.duck_head_y:cfg.head_y)},std::max(tile*.20,tile*cfg.head_scale*.46),std::max(tile*.20,tile*cfg.head_scale*.50)};
}
std::optional<Ellipse> plant_zombie_head(const CombatZombie& u,double tile,const CollisionCatalog& catalog) {
    if(!yes(u.patch.plant_zombie))return std::nullopt;return raw_plant_zombie_head_geometry(u,tile,catalog);
}
Point native_plant_zombie_head_center(const CombatZombie& u,double tile,const CollisionCatalog& catalog) {
    return raw_plant_zombie_head_geometry(u,tile,catalog).center;
}
Point content_target_point(const CombatZombie& u,double tile,const CollisionCatalog& catalog) {
    const auto content=name(u.source.content);if(content=="抓人草触手")return u.head_point.get();
    if(content=="海盗鹦鹉"||content=="乌鸦") {
        const auto image=catalog.flyer_image_height.find(std::string(content));
        return {u.body.motion.get().x,u.body.motion.get().y-(image==catalog.flyer_image_height.end()?tile*.4:image->second/2.)};
    }
    return {u.body.motion.get().x,u.body.motion.get().y-tile};
}
bool flying_target_contact(const CombatZombie& u,Point start,Point delta,double tile,double width,const CollisionCatalog& catalog) {
    const auto point=content_target_point(u,tile,catalog);const double scale=unit_scale_factor(u.source,catalog);
    if(segment_hits_ellipse({0.,start.y},{delta.x,start.y+delta.y},{{wrap_delta(start.x,point.x,width),point.y},tile*.5*scale,tile*.8*scale}))return true;
    if(auto head=plant_zombie_head(u,tile,catalog)) {head->center.x=wrap_delta(start.x,head->center.x,width);return segment_hits_ellipse({0.,start.y},{delta.x,start.y+delta.y},*head);}
    return false;
}
bool head_overlaps_area(const CombatZombie& u,Point center,double rx,double ry,double tile,double width,const CollisionCatalog& catalog) {
    const auto head=plant_zombie_head(u,tile,catalog);if(!head)return false;
    const double dx=std::max(0.,std::abs(wrap_delta(center.x,head->center.x,width))-rx),dy=std::max(0.,std::abs(center.y-head->center.y)-ry);
    return std::pow(dx/std::max(1.,head->rx),2.)+std::pow(dy/std::max(1.,head->ry),2.)<=1.;
}
bool ProjectileRules::basketball(const EntityRef& entity,Point previous) {
    auto& heroes=world_.heroes;const double tile=world_.runtime.tile;const auto& p=entity->motion.get();
    entity->flight.basket_last.set({p.x,p.y});const Point delta{wrap_delta(previous.x,p.x,width_),p.y-previous.y};
    const auto source=source_ref(entity);const auto owner=heroes.owner(source);
    struct Candidate {ZombieRef unit;double distance;std::string id;};std::vector<Candidate> candidates;
    for(const auto& target:*world_.targets)if(!target.is_hero()) {
        const auto& u=target.unit;
        if(u->protection.hero||u->protection.grave||u->orphan_barrel||u->body.hp<=0.||heroes.owner(source_ref(u))==owner)continue;
        const double dx=wrap_delta(p.x,u->body.motion.get().x,width_),dy=u->body.motion.get().y-tile-p.y;
        candidates.push_back({u,std::pow(dx,2.)+std::pow(dy,2.),heroes.source_id(source_ref(u))});
    }
    std::stable_sort(candidates.begin(),candidates.end(),[](const Candidate& a,const Candidate& b){return a.distance<b.distance||(a.distance==b.distance&&a.id<b.id);});
    for(const auto& candidate:candidates)if(flying_target_contact(*candidate.unit,previous,delta,tile,width_,catalog_)) {
        ContentTargets(world_,damage_,catalog_,width_).damage(source,CombatTarget::zombie(candidate.unit),20.,entity->facing,true);
        events.push_back(BasketballHitEvent{optional_name(entity->source.source_entity),heroes.source_id(source_ref(candidate.unit))});return true;
    }
    return false;
}
bool ProjectileRules::expired(const EntityRef& entity) {
    if(!entity)throw std::invalid_argument("null projectile");
    auto& source=entity->source;auto& flight=entity->flight;const auto& p=entity->motion.get();
    begin_flight(source,flight,&p);
    if(entity->kind=="篮球"&&name(source.original_owner)=="zombie")return basketball(entity,flight.basket_last.get());
    if(!flight.last.present()||flight.last.is_null())return false;
    if(flight.form.present()&&!flight.form.is_null()) {
        const ProjectileForm now{entity->kind,source.fire_lit.present(),std::string(name(source.zombie_fire))};
        if(now!=flight.form.get()){flight.form.set(now);flight.distance.set(0.);flight.last.set({p.x,p.y});return false;}
    }
    const auto previous=flight.last.get();const double distance=flight.distance.get()+std::hypot(wrap_delta(previous.x,p.x,width_),p.y-previous.y);
    flight.distance.set(distance);flight.last.set({p.x,p.y});return distance>world_.runtime.tile*source.flight_limit_tiles.or_missing(64.);
}
void ProjectileRules::cull_flight() {
    const auto incoming=world_.runtime.entities.list();auto kept=std::make_shared<EntityRoster>();kept->reserve(incoming->size());
    // Copy only the current reference. Calls can append/reallocate the same
    // list, remove its members, or replace the world's current list entirely.
    for(size_t i=0;i<incoming->size();++i){auto entity=(*incoming)[i];if(!expired(entity))kept->push_back(std::move(entity));}
    world_.runtime.entities.replace(std::move(kept));
}
void ProjectileRules::impact(const EntityRef& entity,ProjectileImpactDamage* installed) {
    if(!entity)throw std::invalid_argument("null impact entity");auto& s=entity->source;const auto& n=entity->kind;
    if((n!="西瓜"&&n!="冰瓜"&&n!="火豆"&&n!="蓝火豆")||yes(s.splash_done))return;
    const std::vector<std::string> empty_hits;
    const auto* hits=s.melon_hits.present()&&!s.melon_hits.is_null()?&s.melon_hits.get():&empty_hits;
    if((n=="火豆"||n=="蓝火豆")&&hits->empty())return;
    s.splash_done.set(true);const Point p{entity->motion.get().x,entity->motion.get().y};auto& heroes=world_.heroes;
    const auto owner=heroes.owner(source_ref(entity));const double tile=world_.runtime.tile;
    const double splash=n=="西瓜"||n=="冰瓜"?(name(s.content)=="甜椒投手"?60.:melon_splash_damage_):projectile_fire_color(s,heroes.globals)=="blue"?10.:20./3.;
    s.melon_splash.set(true);
    {
        struct SplashGuard {AttackSource& source;~SplashGuard(){source.melon_splash.erase();}} guard{s};
        const auto roster=world_.targets;
        for(size_t i=0;i<roster->size();++i) {
            const auto target=(*roster)[i];
            const auto* proxy=target.is_hero()?&heroes.cached_proxy(target.hero):nullptr;
            const double hp=proxy?proxy->hp:target.unit->body.hp;
            if(hp<=0.||(target.is_hero()?std::optional<Seat>(team_of(target.hero)):heroes.owner(source_ref(target.unit)))==owner)continue;
            const auto id=target.is_hero()?"hero:"+std::string(seat_name(target.hero)):heroes.source_id(source_ref(target.unit));
            // An explicit None list fails at the original membership test,
            // after setting splash_done and entering the cleanup scope.
            if(s.melon_hits.present()&&s.melon_hits.is_null())throw std::logic_error("None melon hit list");
            if(std::find(hits->begin(),hits->end(),id)!=hits->end())continue;
            const auto& position=proxy?*proxy->position:target.unit->body.motion.get();
            const bool body=std::abs(wrap_delta(p.x,position.x,width_))<tile*1.3&&position.y-tile*2.7<p.y&&p.y<position.y+tile;
            if(!body&&(target.is_hero()||!head_overlaps_area(*target.unit,p,tile*1.3,tile,tile,width_,catalog_)))continue;
            // Native callbacks receive a numeric index; if an earlier hook
            // replaced the active roster, lookup uses that new roster.
            if(installed)installed->damage_zombie(i,entity->facing,splash);
            else damage_.ordinary(world_.targets->at(i),entity->facing,splash);
        }
    }
    events.push_back(MelonSplashEvent{p,owner,optional_name(s.source_entity)});
}
} // namespace pvz::typed72
