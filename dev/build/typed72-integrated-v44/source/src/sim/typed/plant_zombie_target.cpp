#include "sim/typed/plant_lookup.h"
#include "sim/typed/plant_zombie_target.h"
#include "core/pymath.h"
#include "core/function_profile.h"
#include "sim/typed/spatial_mode.h"
#include <algorithm>
#include <cmath>
#include <limits>
namespace pvz::typed72 {
namespace {
template<class Entries,class Bound,class Consider> void near_x(const Entries& entries,double x,Bound bound,Consider consider){
    auto right=std::lower_bound(entries.begin(),entries.end(),x,[](const auto& e,double p){return e.x<p;});auto left=right;
    while(left!=entries.begin()||right!=entries.end()){
        const double a=left==entries.begin()?std::numeric_limits<double>::infinity():x-std::prev(left)->x;
        const double b=right==entries.end()?std::numeric_limits<double>::infinity():right->x-x;
        const double d=std::min(a,b),limit=bound();if(d>limit+1.e-7*std::max(1.,limit))break;
        if(a<=b){--left;consider(left->index);}else{consider(right->index);++right;}
    }
}
double number(const Field<double>& f,double fallback=0.){return f.present()&&!f.is_null()?f.get():fallback;}
double sign(double n){return n<0.?-1.:1.;}
double angle(Point from,Point to){return py::mod(std::atan2(to.y-from.y,to.x-from.x)*(180./0x1.921fb54442d18p+1)+360.,360.);}
}
void PlantZombieTargeting::prepare_plants()const{
    const auto& all=*world_.plant_roster;if(plant_data_==all.data()&&plant_count_==all.size())return;
    plant_data_=all.data();plant_count_=all.size();plant_search_.clear();plant_search_.reserve(all.size());
    for(size_t i=0;i<all.size();++i)plant_search_.push_back({(all[i]->cell.x+.5)*world_.runtime.tile,i});
    std::stable_sort(plant_search_.begin(),plant_search_.end(),[](const auto& a,const auto& b){return a.x<b.x;});
}
void PlantZombieTargeting::prepare_zombies(const TargetRoster& all)const{
    if(zombie_data_==all.data()&&zombie_count_==all.size())return;
    zombie_data_=all.data();zombie_count_=all.size();zombie_search_.clear();zombie_search_.reserve(all.size());
    for(size_t i=0;i<all.size();++i)if(!all[i].is_hero())zombie_search_.push_back({all[i].unit->body.motion.get().x,i});
    std::stable_sort(zombie_search_.begin(),zombie_search_.end(),[](const auto& a,const auto& b){return a.x<b.x;});
}
const TargetRoster& PlantZombieTargeting::enemy_view(const ZombieRef& source)const{
    const auto& all=*world_.targets;if(enemy_data_!=all.data()||enemy_count_!=all.size()){
        enemy_view_=plant_zombie_enemy_view(world_,source);enemy_data_=all.data();enemy_count_=all.size();zombie_data_=nullptr;
    }return enemy_view_;
}
double native_direction_angle(double direction){return sign(direction)>0.?0.:180.;}
double native_direction_angle_diff(double a,double direction){return py::mod(a-native_direction_angle(direction)+180.,360.)-180.;}
bool native_angle_in_direction(double a,double direction,double limit){return std::abs(native_direction_angle_diff(a,direction))<=limit;}
std::pair<double,double> sync_native_head_angle(CombatZombie& u) {
    const double direction=sign(u.body.facing);double a=number(u.patch.aim_angle,native_direction_angle(direction));
    if(!native_angle_in_direction(a,direction)){a=native_direction_angle(direction);u.patch.aim_angle.set(a);}return {direction,a};
}
Point PlantZombieTargeting::zombie_point(const CombatTarget& target)const {
    const double tile=world_.runtime.tile;
    if(target.is_hero()) {
        const auto& p=world_.heroes.cached_proxy(target.hero);
        return {p.position->x,p.position->y-tile*.65*std::max(.35,number(p.size,1.))};
    }
    const auto& u=*target.unit;if(auto h=plant_zombie_head(u,tile,catalog_))return h->center;
    return {u.body.motion.get().x,u.body.motion.get().y-tile*.65*std::max(.35,number(u.body.size,1.))};
}
std::optional<Point> PlantZombieTargeting::plant_aim(const CombatPlant& p,Point center)const {
    const double tile=world_.runtime.tile;
    const auto base=patch_plant_point(world_,p);
    if(!base)return {};
    return Point{base->x,std::max(base->y-tile*.60,std::min(base->y+tile*.60,center.y))};
}
std::optional<Point> PlantZombieTargeting::player_point()const {
    const auto& p=world_.heroes.globals.position;if(!p.present()||p.is_null())return {};
    return Point{p.get()->x,p.get()->y-world_.runtime.tile};
}
TargetRoster plant_zombie_enemy_view(TypedBattleState& w,const ZombieRef& source) {
    const auto enemy=w.heroes.owner(source_ref(source))==Seat::plant?Seat::zombie:Seat::plant;
    const auto seats=seats_for(w.mode);
    TargetRoster view;view.reserve(w.targets->size()+2);
    for(const auto& t:*w.targets) {
        if(!t.is_hero() || (team_of(t.hero)==enemy && std::find(seats.begin(),seats.end(),t.hero)!=seats.end()))view.push_back(t);
    }
    for(const auto side:seats)if(team_of(side)==enemy) {
        const auto t=CombatTarget::player(side);
        if(w.heroes.proxy(side).hp>0. && std::find(view.begin(),view.end(),t)==view.end())view.push_back(t);
    }
    return view;
}
void PlantZombieTargeting::consider_zombies(const TargetRoster& roster,const ZombieRef& source,Point center,bool charmed_targets,
    std::optional<NativeAimTarget>& best,std::optional<double>& best_score)const {
    const double direction=sign(source->body.facing);
    // These fixed geometry helpers cannot mutate rosters. Reading the same
    // ordered references avoids the source's temporary shallow list copy.
    ++aim_queries;aim_full_scan+=roster.size();
    const auto consider=[&](size_t i){try {
        ++aim_candidates;
        const auto target=roster.at(i);if(target.unit==source)return;
        const bool charmed=!target.is_hero()&&target.unit->source.charmed.present();
        if(charmed!=charmed_targets)return;
        const auto& fields=target.is_hero()?static_cast<const ZombieRecordFields&>(world_.heroes.cached_proxy(target.hero)):
            static_cast<const ZombieRecordFields&>(target.unit->body);
        if(fields.ash.present()||fields.hp<=0.)return;
        // Unlike doom, the actual target selector does not filter "死".
        const auto p=zombie_point(target);const double a=angle(center,p);if(!native_angle_in_direction(a,direction))return;
        const double score=std::abs(p.y-center.y)*(charmed_targets?2.2:2.)+std::abs(p.x-center.x)*(charmed_targets?.45:.35);
        const bool earlier=best&&std::holds_alternative<CombatTarget>(best->object)&&i<best->index;
        if(!best_score||score<*best_score||(score==*best_score&&earlier)){best=NativeAimTarget{target,i,p,direction,a};best_score=score;}
    }catch(const std::exception&){} };
    if(phase_&&spatial741_enabled()){
        prepare_zombies(roster);double padding=0.;for(const auto& [name,g]:catalog_.plant_heads)padding=std::max(padding,std::max(std::abs(g.head_x),std::abs(g.duck_head_x))+.05);
        for(size_t i=0;i<roster.size();++i)if(roster[i].is_hero())consider(i);
        near_x(zombie_search_,center.x,[&]{return best_score?*best_score/(charmed_targets?.45:.35)+padding*world_.runtime.tile:std::numeric_limits<double>::infinity();},consider);
    }else for(size_t i=0;i<roster.size();++i)consider(i);
}
std::optional<NativeAimTarget> PlantZombieTargeting::pick(const ZombieRef& source)const {
    PVP_PROFILE_SCOPE("PlantZombieTargeting::pick");
    if(!source)throw std::invalid_argument("missing native aim source");
    const Point center=native_plant_zombie_head_center(*source,world_.runtime.tile,catalog_);
    std::optional<NativeAimTarget> best;std::optional<double> best_score;
    if(source->source.charmed.present()){
        if(world_.native_plant_zombies_installed){if(phase_&&spatial741_enabled())consider_zombies(enemy_view(source),source,center,false,best,best_score);else consider_zombies(plant_zombie_enemy_view(world_,source),source,center,false,best,best_score);}
        else consider_zombies(*world_.targets,source,center,false,best,best_score);
        return best;
    }
    const double direction=sign(source->body.facing);const auto plants=world_.plant_roster;
    ++aim_queries;aim_full_scan+=plants->size();
    const auto consider=[&](size_t i){try {
        ++aim_candidates;
        const auto plant=plants->at(i);if(plant->dead.present()||plant->shovel_dead.present()||number(plant->hp,1.)<=0.)return;
        const auto aim=plant_aim(*plant,center);if(!aim)return;const Point p=*aim;const double a=angle(center,p);if(!native_angle_in_direction(a,direction))return;
        const double score=std::abs(p.y-center.y)*2.2+std::abs(p.x-center.x)*.45;
        if(!best_score||score<*best_score||(score==*best_score&&best&&i<best->index)){best=NativeAimTarget{plant,i,p,direction,a};best_score=score;}
    }catch(const std::exception&){} };
    if(phase_&&spatial741_enabled()){prepare_plants();near_x(plant_search_,center.x,[&]{return best_score?*best_score/.45:std::numeric_limits<double>::infinity();},consider);}
    else for(size_t i=0;i<plants->size();++i)consider(i);
    consider_zombies(*world_.targets,source,center,true,best,best_score);if(best)return best;
    // legacy_fixes._target_wrapper removes only the allied native player in
    // I-Z mode. The sourced PvP entry establishes normal mode before calling.
    const auto& mode=world_.heroes.globals.mode;
    if(mode.present()&&!mode.is_null()&&mode.get()=="我是僵尸")return {};
    if(const auto p=player_point()){const double a=angle(center,*p);if(native_angle_in_direction(a,direction))return NativeAimTarget{std::monostate{},0,*p,direction,a};}
    return {};
}
std::optional<Point> PlantZombieTargeting::point(const NativeAimTarget& target,Point center)const {
    if(const auto* plant=std::get_if<PlantRef>(&target.object))return plant_aim(**plant,center);
    if(const auto* zombie=std::get_if<CombatTarget>(&target.object))return zombie_point(*zombie);
    return player_point();
}
NativeAim PlantZombieTargeting::raw_update(const ZombieRef& source) {
    if(!source)throw std::invalid_argument("missing native aim source");
    NativeAim result{pick(source),native_plant_zombie_head_center(*source,world_.runtime.tile,catalog_)};
    const double direction=sign(source->body.facing);double a=native_direction_angle(direction);
    if(result.target)if(const auto p=point(*result.target,result.center)){a=angle(result.center,*p);if(!native_angle_in_direction(a,direction))a=native_direction_angle(direction);}
    source->patch.aim_angle.set(a);return result;
}
NativeAim PlantZombieTargeting::update(const ZombieRef& source) {
    SourcedContext scope(world_,source_ref(source),CombatPhase::zombies);auto result=raw_update(source);scope.finish();return result;
}
} // namespace pvz::typed72
