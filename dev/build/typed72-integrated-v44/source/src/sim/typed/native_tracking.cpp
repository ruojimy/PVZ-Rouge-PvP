#include "sim/typed/native_tracking.h"
#include "sim/typed/projectile_rules.h"
#include "core/pymath.h"
#include <algorithm>
#include <cmath>
#include <tuple>

namespace pvz::typed72 {
namespace {
Point player_center(const HeroPlayer& p){return {p.position.x,p.position.y-p.height/2.};}
bool truth(const Field<bool>& f){return f.present()&&!f.is_null()&&f.get();}
bool named(const Field<std::string>& f,std::string_view name){return f.present()&&!f.is_null()&&f.get()==name;}
}
TrackingSource TrackingSource::from(const EntityRef& e){
    const auto& p=e->motion.get();
    return {source_ref(e),{},Point{p.x,p.y}};
}
TrackingSource TrackingSource::from(const PlantRef& p){return {source_ref(p),p->cell,{}};}
bool TargetSight::water_at(Point p,double tile,double width)const{
    const double row=std::floor(p.y/tile);
    if(row<0. || row>=double(water.size()))return false;
    const auto& cells=water.at(size_t(row));
    if(cells.empty())throw std::logic_error("empty published water row");
    const auto col=size_t(std::floor(py::mod(p.x,width)/tile));
    return cells.at(col%cells.size())!=0;
}
std::shared_ptr<Motion> NativeTracking::position(const CombatTarget& t)const {
    return t.is_hero()?world_.heroes.cached_proxy(t.hero).position:t.unit->body.motion.retain();
}
void NativeTracking::begin(const TrackingSource& s) {
    if(!s.record || world_.heroes.owner(s.record)!=Seat::plant)return;
    const double tile=world_.runtime.tile,width=world_.world_width.get();
    double x;
    if(s.plant_cell)x=(s.plant_cell->x+.5)*tile;
    else if(s.position && s.record->projectile.present())x=s.position->x;
    else return;
    active_=true;
    for(const auto& target:*world_.targets) {
        const double hp=target.is_hero()?world_.heroes.cached_proxy(target.hero).hp:target.unit->body.hp;
        if(hp<=0.)continue;
        const auto p=position(target);
        const double nearest=x+wrap_delta(x,p->x,width);
        if(std::abs(nearest-p->x)>width*.5) {
            shifted_.emplace_back(target,p);
            p->x+=nearest>p->x?width:-width;
        }
    }
    const int64_t count=int64_t(width/tile);
    const double origin=x/tile;
    const auto column=[&](int64_t col){
        if(col-origin < -count/2.)return col+count;
        if(col-origin >= count/2.)return col-count;
        return col;
    };
    const auto needs_chart=[&](const auto& row){
        return std::any_of(row.second.begin(),row.second.end(),[&](int64_t c){return column(c)!=c;});
    };
    if(std::none_of(indexes_.rows->begin(),indexes_.rows->end(),needs_chart))return;
    auto rows=std::make_shared<TargetBuckets>(*indexes_.rows);
    for(auto& row:*rows)for(auto& c:row.second)c=column(c);
    auto cols=std::make_shared<TargetBuckets>();
    for(const auto& [c,values]:*indexes_.columns) {
        const auto key=column(c);
        const auto it=std::find_if(cols->begin(),cols->end(),[&](const auto& pair){return pair.first==key;});
        if(it==cols->end())cols->emplace_back(key,values);
        else it->second.insert(it->second.end(),values.begin(),values.end());
    }
    saved_rows_=std::exchange(indexes_.rows,std::move(rows));
    saved_columns_=std::exchange(indexes_.columns,std::move(cols));
}
void NativeTracking::restore() {
    for(const auto& [target,old]:shifted_) {
        const auto width=world_.world_width.get();
        old->x=py::mod(old->x,width);
        const auto current=position(target);
        if(current!=old)current->x=py::mod(current->x,width);
    }
    shifted_.clear();
    if(saved_rows_){indexes_.rows=std::move(saved_rows_);indexes_.columns=std::move(saved_columns_);}
    active_=false;
}
bool NativeTracking::within_sight(Point a,Point b,double radius)const {
    const auto tile=world_.runtime.tile,width=world_.world_width.get();
    const double dx=wrap_delta(a.x,b.x,width),dy=b.y-a.y;
    const double distance=std::hypot(dx,dy);
    if(distance>radius)return false;
    const int64_t steps=std::max<int64_t>(1,int64_t(distance/12.));
    for(int64_t i=1;i<steps;++i) {
        const int64_t row=int64_t(std::floor((a.y+dy*i/steps)/tile));
        if(row<0)continue;
        if(uint64_t(row)>=sight_.solid.size())return false;
        const auto& line=sight_.solid.at(size_t(row));
        if(line.empty())throw std::logic_error("empty published target map row");
        const size_t col=size_t(std::floor(py::mod(a.x+dx*i/steps,width)/tile))%line.size();
        if(line[col])return false;
    }
    return true;
}
bool NativeTracking::hero_lock(const TrackingSource& source,Seat side)const {
    if(team_of(side)!=Seat::zombie)return false;
    const auto& heroes=world_.heroes;
    const auto& target=heroes.players.at(seat_index(side)).value();
    auto origin=player_center(heroes.players.at(seat_index(Seat::plant)).value());
    const auto tile=world_.runtime.tile;
    if(source.record) {
        if(named(source.record->owner,"zombie"))return false;
        if(source.plant_cell)origin={(source.plant_cell->x+.5)*tile,(source.plant_cell->y+1)*tile-tile/2.};
        else if(source.position)origin={source.position->x,source.position->y-tile/2.};
    }
    const auto point=player_center(target);
    bool marked=heroes.time<target.marked_until;
    if(!marked)for(const auto& p:*world_.plant_roster) {
        if(p->kind=="路灯花" && p->hp.present() && !p->hp.is_null() && p->hp.get()>0. &&
           within_sight({(p->cell.x+.5)*tile,(p->cell.y+1)*tile-tile/2.},point,220.)){marked=true;break;}
    }
    if(!marked)for(const auto seat:seats_for(world_.mode)) {
        if(team_of(seat)!=Seat::plant)continue;
        const auto& player=heroes.players.at(seat_index(seat)).value();
        const auto& down=heroes.heroes.at(seat_index(seat)).value().frame.down;
        if(player.hp>0. && (!down.present() || down.is_null() || down.get()==0.) &&
           within_sight(player_center(player),point,220.)){marked=true;break;}
    }
    return marked && within_sight(origin,point,sight_.hero_lock_range);
}
void NativeTracking::target_index(const TrackingSource& s) {
    auto& heroes=world_.heroes;const auto tile=world_.runtime.tile;
    std::array<bool,4> hidden{};
    for(size_t i=0;i<heroes.proxies.size();++i)if(heroes.proxies[i])hidden[i]=!hero_lock(s,Seat(i));
    const auto get_body=[&](const CombatTarget& t)->const ZombieRecordFields&{
        if(t.is_hero())return heroes.cached_proxy(t.hero);
        return t.unit->body;
    };
    const auto native=[&](const CombatTarget& t)->const ZombieNativeState&{
        return t.is_hero()?heroes.cached_proxy(t.hero).native:t.unit->native;
    };
    const auto source=[&](const CombatTarget& t){return t.is_hero()?heroes.proxy_source(t.hero):source_ref(t.unit);};
    const auto eligible=[&](const CombatTarget& t){
        const auto& n=native(t);const auto& b=get_body(t);
        return b.hp>0. && !b.ash.present() && !n.emerged.present() && n.entry.present() &&
               !n.entry.is_null() && n.entry.get()==500. && !(t.is_hero()&&hidden[seat_index(t.hero)]);
    };
    indexes_.ladders.clear();indexes_.nearest.reset();
    for(size_t i=world_.targets->size();i-- >0;) {
        heroes.source_index=int64_t(i);
        const auto& t=world_.targets->at(i);const auto p=position(t);
        if(get_body(t).hand=="梯子" && native(t).split.present())indexes_.ladders.push_back(int64_t(py::floordiv(p->x,tile)));
        const double distance=std::abs(p->x-heroes.globals.position.get()->x);
        if(eligible(t) && !source(t)->charmed.present() && (!indexes_.nearest || distance<indexes_.nearest_distance)){
            indexes_.nearest=i;indexes_.nearest_distance=distance;
        }
    }
    if(!s.record)return;
    const auto& id=s.record->id;
    if(!named(s.record->plant,"香蒲") && !truth(s.record->cattail) && !(id.present()&&!id.is_null()&&id.get().starts_with("hero:plant")))return;
    const auto& fallback=heroes.globals.position;
    const Point origin=s.plant_cell?Point{(s.plant_cell->x+.5)*tile,(s.plant_cell->y+.5)*tile}:
        s.position?Point{s.position->x,s.position->y-tile}:Point{fallback.get()->x,fallback.get()->y-tile};
    const double width=world_.terrain.cols()*tile;
    std::optional<std::tuple<double,std::string,size_t>> best;
    for(size_t i=0;i<world_.targets->size();++i) {
        const auto& t=world_.targets->at(i);const auto target=source(t);
        if(!eligible(t) || heroes.owner(target)==heroes.owner(s.record))continue;
        const auto p=position(t);const double dx=wrap_delta(origin.x,p->x,width),dy=p->y-tile-origin.y;
        auto key=std::tuple{dx*dx+dy*dy,heroes.source_id(target),i};
        if(!best||key<*best)best=std::move(key);
    }
    indexes_.nearest=best?std::optional<size_t>(std::get<2>(*best)):std::nullopt;
}
void NativeTracking::tracking_index(const TrackingSource& source){
    auto& index=world_.heroes.source_index;
    struct Restore {std::optional<int64_t>& dst;std::optional<int64_t> saved;~Restore(){dst=saved;}} restore{index,index};
    target_index(source);
}
} // namespace pvz::typed72
