#include "core/function_profile.h"
#include "sim/typed/native_tracking.h"
#include "sim/typed/projectile_rules.h"
#include "sim/typed/spatial_mode.h"
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
// Validate against live records even within a tick. Damage/transform callbacks
// may replace a Motion, and hero contexts may replace a proxy position pointer.
// Only the scalar x ordering is cached; selected entries resolve their live Motion.
void NativeTracking::prepare_chart(){
    const auto& roster=*world_.targets;
    bool valid=chart_roster_==world_.targets.get()&&chart_data_==roster.data()&&chart_count_==roster.size()&&chart_tick_==world_.heroes.tick;
    if(valid)for(const auto& entry:chart_entries_)if(entry.target.unit->body.motion.get().x!=entry.x || (entry.target.unit->body.hand=="梯子"&&entry.target.unit->native.split.present())!=entry.ladder){valid=false;break;}
    if(valid)return;
    chart_roster_=world_.targets.get();chart_data_=roster.data();chart_count_=roster.size();chart_tick_=world_.heroes.tick;
    chart_entries_.clear();chart_entries_.reserve(roster.size());search_entries_.clear();ladder_indices_.clear();search_ids_ready_=true;
    const double width=world_.world_width.get();
    for(size_t i=0;i<roster.size();++i){
        const auto& target=roster[i];
        const auto& id=target.is_hero()?world_.heroes.cached_proxy(target.hero).source.id:target.unit->source.id;
        if(!id.present()||id.is_null()||id.get().empty())search_ids_ready_=false;
        if(target.is_hero())continue;
        const double x=target.unit->body.motion.get().x;
        const bool ladder=target.unit->body.hand=="梯子"&&target.unit->native.split.present();
        chart_entries_.push_back({x,target,{},i,ladder});search_entries_.push_back({py::mod(x,width),i});
        if(ladder)ladder_indices_.push_back(i);
    }
    std::reverse(ladder_indices_.begin(),ladder_indices_.end());
    std::stable_sort(chart_entries_.begin(),chart_entries_.end(),[](const auto& a,const auto& b){return a.x<b.x;});
    std::stable_sort(search_entries_.begin(),search_entries_.end(),[](const auto& a,const auto& b){return a.x<b.x;});
    search_seen_.assign(roster.size(),0);search_stamp_=0;

}
void NativeTracking::begin(const TrackingSource& s) {
    PVP_PROFILE_SCOPE("NativeTracking::begin");
    if(!s.record || world_.heroes.owner(s.record)!=Seat::plant)return;
    const double tile=world_.runtime.tile,width=world_.world_width.get();
    double x;
    if(s.plant_cell)x=(s.plant_cell->x+.5)*tile;
    else if(s.position && s.record->projectile.present())x=s.position->x;
    else return;
    active_=true;
    const auto shift=[&](const ChartEntry& entry) {
        const auto& target=entry.target;
        const double hp=target.is_hero()?world_.heroes.cached_proxy(target.hero).hp:target.unit->body.hp;
        if(hp<=0.)return;
        const auto& p=entry.motion;
        const double nearest=x+wrap_delta(x,p->x,width);
        if(std::abs(nearest-p->x)>width*.5) {
            shifted_.emplace_back(target,p);
            p->x+=nearest>p->x?width:-width;
        }
    };
    if(spatial741_enabled()){
        prepare_chart();
        // A tiny conservative margin includes floating-point seam boundary ties;
        // shift() keeps the original exact predicate as the final decision.
        const double margin=1.e-9;
        const auto low=std::upper_bound(chart_entries_.begin(),chart_entries_.end(),x-width*.5+margin,[](double value,const auto& e){return value<e.x;});
        const auto high=std::lower_bound(chart_entries_.begin(),chart_entries_.end(),x+width*.5-margin,[](const auto& e,double value){return e.x<value;});
        const auto live_shift=[&](const ChartEntry& e){const auto p=position(e.target);shift({p->x,e.target,p});};
        for(auto i=chart_entries_.begin();i!=low;++i)live_shift(*i);
        for(auto i=high;i!=chart_entries_.end();++i)live_shift(*i);
        for(const auto& target:*world_.targets)if(target.is_hero()){const auto p=position(target);shift({p->x,target,p});}
    }else for(const auto& target:*world_.targets){const auto p=position(target);shift({p->x,target,p});}
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
    PVP_PROFILE_SCOPE("NativeTracking::restore");
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
    PVP_PROFILE_SCOPE("NativeTracking::hero_lock");
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
    PVP_PROFILE_SCOPE("NativeTracking::target_index");
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
    // Cattail's final choice replaces the ordinary horizontal choice. Resolve
    // both in one pass; preserve the ordinary distance and the reverse ladder
    // order, and use the original path for records needing lazy ID admission.
    const auto& homing_id=s.record?s.record->id:Field<std::string>{};
    const bool homing=s.record && (named(s.record->plant,"香蒲") || truth(s.record->cattail) ||
        (homing_id.present()&&!homing_id.is_null()&&homing_id.get().starts_with("hero:plant")));
    if(spatial741_enabled() && homing){
        const auto& fallback=heroes.globals.position;
        const Point origin=s.plant_cell?Point{(s.plant_cell->x+.5)*tile,(s.plant_cell->y+.5)*tile}:
            s.position?Point{s.position->x,s.position->y-tile}:Point{fallback.get()->x,fallback.get()->y-tile};
        const double width=world_.terrain.cols()*tile;
        const auto owner=heroes.owner(s.record);
        // begin() validated the canonical x ordering immediately before this
        // source's chart shift. Use distance lower bounds to visit only nearby
        // cells/positions; the exact legacy eligibility, owner and tie tests stay.
        if(active_&&search_ids_ready_&&chart_roster_==world_.targets.get()&&chart_count_==world_.targets->size()){
            ++nearest_queries;nearest_full_scan+=world_.targets->size();
            indexes_.ladders.clear();indexes_.nearest.reset();
            if(!world_.targets->empty())heroes.source_index=0;
            std::vector<std::pair<size_t,int64_t>> ladders;
            for(const auto i:ladder_indices_){const auto& t=world_.targets->at(i);if(get_body(t).hand=="梯子"&&native(t).split.present())ladders.emplace_back(i,int64_t(py::floordiv(position(t)->x,tile)));}
            for(size_t i=world_.targets->size();i-- >0;)if(world_.targets->at(i).is_hero()){
                const auto& t=world_.targets->at(i);if(get_body(t).hand=="梯子"&&native(t).split.present())ladders.emplace_back(i,int64_t(py::floordiv(position(t)->x,tile)));
            }
            std::sort(ladders.begin(),ladders.end(),std::greater<>{});for(const auto& pair:ladders)indexes_.ladders.push_back(pair.second);
            std::optional<size_t> horizontal,best;double horizontal_distance=0.,best_distance=0.;std::string_view best_id;
            bool complete=true;
            const auto scan=[&](double center,auto bound,auto consider){
                if(++search_stamp_==0){std::fill(search_seen_.begin(),search_seen_.end(),0);++search_stamp_;}
                const double canonical=py::mod(center,width);
                for(double at:{canonical,canonical-width,canonical+width}){
                    const auto mid=std::lower_bound(search_entries_.begin(),search_entries_.end(),at,[](const auto& e,double v){return e.x<v;});
                    const auto visit=[&](const SearchEntry& e){if(search_seen_[e.index]==search_stamp_)return;search_seen_[e.index]=search_stamp_;consider(e.index);};
                    const auto outside=[&](double delta){const auto limit=bound();return limit && delta*delta>*limit+1.e-7*std::max(1.,*limit);};
                    for(auto i=mid;i!=search_entries_.end();++i){if(outside(i->x-at))break;visit(*i);}
                    for(auto i=mid;i!=search_entries_.begin();){--i;if(outside(at-i->x))break;visit(*i);}
                }
            };
            const auto horizontal_test=[&](size_t i){
                const auto& t=world_.targets->at(i);++nearest_candidates;
                if(!eligible(t)||source(t)->charmed.present())return;
                const double d=std::abs(position(t)->x-heroes.globals.position.get()->x);
                if(!horizontal||d<horizontal_distance||(d==horizontal_distance&&i>*horizontal)){horizontal=i;horizontal_distance=d;}
            };
            const auto homing_test=[&](size_t i){
                const auto& t=world_.targets->at(i);++nearest_candidates;if(!eligible(t))return;
                const auto target=source(t);if(heroes.owner(target)==owner)return;
                const auto& id=target->id;if(!id.present()||id.is_null()||id.get().empty()){complete=false;return;}
                const auto p=position(t);const double dx=wrap_delta(origin.x,p->x,width),dy=p->y-tile-origin.y,d=dx*dx+dy*dy;const std::string_view key=id.get();
                if(!best||d<best_distance||(d==best_distance&&(key<best_id||(key==best_id&&i<*best)))){best=i;best_distance=d;best_id=key;}
            };
            for(size_t i=0;i<world_.targets->size();++i)if(world_.targets->at(i).is_hero()){horizontal_test(i);homing_test(i);}
            scan(heroes.globals.position.get()->x,[&]()->std::optional<double>{if(horizontal)return horizontal_distance*horizontal_distance;return {};},horizontal_test);
            scan(origin.x,[&]()->std::optional<double>{if(best)return best_distance;return {};},homing_test);
            if(complete){if(horizontal)indexes_.nearest_distance=horizontal_distance;indexes_.nearest=best;return;}
        }
        indexes_.ladders.clear();indexes_.nearest.reset();
        std::optional<size_t> horizontal,best;double best_distance=0.;std::string_view best_id;
        bool complete=true;
        // The old first pass leaves source_index at zero before owner lookups.
        if(!world_.targets->empty())heroes.source_index=0;
        for(size_t i=world_.targets->size();i-- >0;){
            const auto& t=world_.targets->at(i);const auto p=position(t);
            const auto& body=get_body(t);const auto& n=native(t);
            if(body.hand=="梯子" && n.split.present())indexes_.ladders.push_back(int64_t(py::floordiv(p->x,tile)));
            if(!eligible(t))continue;
            const auto target=source(t);
            const double horizontal_distance=std::abs(p->x-heroes.globals.position.get()->x);
            if(!target->charmed.present() && (!horizontal||horizontal_distance<indexes_.nearest_distance)){
                horizontal=i;indexes_.nearest_distance=horizontal_distance;
            }
            if(heroes.owner(target)==owner)continue;
            const auto& target_id=target->id;
            if(!target_id.present()||target_id.is_null()||target_id.get().empty()){complete=false;break;}
            const double dx=wrap_delta(origin.x,p->x,width),dy=p->y-tile-origin.y,distance=dx*dx+dy*dy;
            const std::string_view key=target_id.get();
            if(!best || distance<best_distance || (distance==best_distance && (key<best_id || (key==best_id && i<*best)))){
                best=i;best_distance=distance;best_id=key;
            }
        }
        if(complete){indexes_.nearest=best;return;}
    }
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
