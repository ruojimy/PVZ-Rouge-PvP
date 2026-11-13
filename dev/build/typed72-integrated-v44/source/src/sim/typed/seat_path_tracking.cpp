#include "core/function_profile.h"
#include "sim/typed/spatial_mode.h"
#include "sim/typed/seat_path_tracking.h"
#include <tuple>
#include <unordered_map>

namespace pvz::typed72 {
namespace {
bool same(Point a,Point b){return a.x==b.x && a.y==b.y;}
}
ChaseSnapshot SeatPathTracking::capture_chase()const {
    const auto& n=navigation_;
    return {n.chase_fields,n.target_position,n.target_plant,n.running,n.output_plants};
}
void SeatPathTracking::restore_chase(const ChaseSnapshot& saved){
    auto& n=navigation_;
    n.chase_fields=saved.fields;n.target_position=saved.goal;
    n.target_plant=saved.target;n.running=saved.running;n.output_plants=saved.output;
}
PathSnapshot SeatPathTracking::capture()const {
    PathSnapshot saved;
    for(size_t i=0;i<saved.flood.size();++i){
        const auto& f=navigation_.flood[i];
        saved.flood[i]={f.field,f.queue,f.cooldown,f.sign};
    }
    saved.chase=capture_chase();saved.hero_cell=navigation_.hero_cell;
    saved.hold=navigation_.hold_plant;saved.initialized=navigation_.initialized;
    saved.wjx=world_.heroes.globals.wjx;saved.wjy=world_.heroes.globals.wjy;
    return saved;
}
void SeatPathTracking::restore(const PathSnapshot& saved){
    for(size_t i=0;i<saved.flood.size();++i){
        auto& f=navigation_.flood[i];const auto& s=saved.flood[i];
        f.field=s.field;f.queue=s.queue;f.cooldown=s.cooldown;f.sign=s.sign;
    }
    restore_chase(saved.chase);navigation_.hero_cell=saved.hero_cell;
    navigation_.hold_plant=saved.hold;navigation_.initialized=saved.initialized;
    world_.heroes.globals.wjx=saved.wjx;world_.heroes.globals.wjy=saved.wjy;
}
PathSnapshot SeatPathTracking::independent(const PathSnapshot& original)const {
    auto copy=original;
    std::unordered_map<const std::vector<int>*,std::shared_ptr<std::vector<int>>> matrices;
    const auto clone=[&](auto& field){
        auto [at,added]=matrices.try_emplace(field.get());
        if(added)at->second=std::make_shared<std::vector<int>>(*field);
        field=at->second;
    };
    for(auto& f:copy.flood){clone(f.field);f.queue=std::make_shared<std::vector<Cell>>(*f.queue);}
    for(auto& f:copy.chase.fields)clone(f);
    return copy;
}
std::span<const Seat> SeatPathTracking::team_seats(std::span<const Seat> present,Seat team,bool alive,std::array<Seat,4>& output)const {
    size_t count=0;
    for(const auto seat:present)
        if(team_of(seat)==team && (!alive || world_.heroes.players.at(seat_index(seat)).value().hp>0.))output.at(count++)=seat;
    return {output.data(),count};
}
Seat SeatPathTracking::advance_team(std::span<const Seat> present){
    PVP_PROFILE_SCOPE("SeatPathTracking::advance_team");
    const bool duo=world_.mode==MatchMode::duo;
    const auto team=commands_.shared==PathMode::follow_hero?Seat::zombie:Seat::plant;
    std::array<Seat,4> selected_team,selected_match;
    auto active=team_seats(present,duo?Seat::plant:team,true,selected_team);
    if(active.empty())active=team_seats(present,duo?Seat::plant:team,false,selected_team);
    if(duo){
        const auto zombies=team_seats(present,Seat::zombie,false,selected_match);
        std::copy(active.begin(),active.end(),selected_match.begin()+zombies.size());
        active={selected_match.data(),zombies.size()+active.size()};
    }
    if(active.empty()){selected_match[0]=team;active={selected_match.data(),1};}
    for(size_t i=0;i<seats_.size();++i)
        if(std::find(active.begin(),active.end(),Seat(i))==active.end())seats_[i].reset();
    for(auto at=active.rbegin();at!=active.rend();++at){
        const auto seat=*at;
        const auto& p=*world_.heroes.heroes.at(seat_index(seat)).value().frame.position.get();
        const Point hero{p.x,p.y};auto& bank=seats_[seat_index(seat)];
        if(bank)restore(*bank);else paths_.initialize(hero);
        if(navigation_.scripted && team_of(seat)==Seat::plant)
            navigation_.target_position=player_flood_seed(hero,world_.runtime.tile);
        const auto mode=duo?(team_of(seat)==Seat::zombie?PathMode::follow_hero:PathMode::attack_plants):
            (commands_.shared==PathMode::follow_hero || navigation_.scripted?PathMode::follow_hero:PathMode::attack_plants);
        paths_.advance(hero,mode);bank=capture();
    }
    return active.front();
}
std::optional<Point> SeatPathTracking::destination(std::optional<Seat> owner,uint64_t revision){
    PVP_PROFILE_SCOPE("SeatPathTracking::destination");
    const auto flag=flags_.for_owner(world_.mode,owner);
    if(!flag)return {};
    const auto matches=[&](const std::optional<DestinationCache>& cache){
        return cache && same(cache->flag,*flag) && cache->revision==revision;
    };
    auto& local=destinations_.at(seat_index(owner.value_or(Seat::zombie)));
    if(world_.mode==MatchMode::duo && matches(local))return local->goal;
    if(!matches(shared_destination_)){
        const auto requested=terrain_cell(*flag,world_.runtime.tile);
        Cell cell=requested;
        const bool in_grid=requested.y>=0&&size_t(requested.y)<published_.solid.size()&&requested.x>=0&&!published_.solid.empty()&&uint64_t(requested.x)<published_.solid.front().size();
        const bool indexed=spatial741_enabled()&&in_grid;
        if(indexed){if(const auto chosen=legal_destinations_.query(published_.solid,requested))cell=*chosen;}
        std::optional<std::tuple<int64_t,int,int64_t>> best;
        const auto columns=int64_t(published_.solid.at(0).size());
        if(!indexed)for(size_t y=0;y<published_.solid.size();++y){
            const auto& row=published_.solid[y];
            for(size_t x=0;x<row.size();++x){
                if(row[x])continue;
                const auto dx=std::abs(int64_t(x)-requested.x);
                const auto key=std::tuple{std::abs(int64_t(y)-requested.y)+std::min(dx,columns-dx),int(y),int64_t(x)};
                if(!best || key<*best){best=key;cell={int(y),int64_t(x)};}
            }
        }
        const Point goal{(cell.x+.5)*world_.runtime.tile,(cell.y+1.)*world_.runtime.tile};
        shared_destination_=DestinationCache{*flag,goal,revision};
    }
    if(world_.mode==MatchMode::duo)local=shared_destination_;
    return shared_destination_->goal;
}
void SeatPathTracking::advance_flag(RallyPathBank& bank,Point goal){
    if(!bank.goal || !same(*bank.goal,goal)){
        bank.path.flood[0].queue=std::make_shared<std::vector<Cell>>();
        bank.path.flood[0].cooldown=0;bank.goal=goal;
    }
    restore(bank.path);paths_.advance(goal,PathMode::follow_hero);bank.path=capture();
}
void SeatPathTracking::advance_rallies(std::span<const Seat> present,uint64_t revision){
    rally_base_.reset();
    if(world_.mode!=MatchMode::duo && !flags_.shared){shared_rally_.reset();return;}
    const auto baseline=capture();
    try{
        if(world_.mode==MatchMode::duo){
            std::array<std::optional<RallyPathBank>,4> active;
            std::array<Seat,4> selected;
            for(const auto seat:team_seats(present,Seat::zombie,false,selected)){
                const auto goal=destination(seat,revision);if(!goal)continue;
                const auto i=seat_index(seat);
                auto bank=rally_seats_[i].value_or(RallyPathBank{});
                if(!rally_seats_[i])bank.path=independent(baseline);
                advance_flag(bank,*goal);active[i]=std::move(bank);restore(baseline);
            }
            rally_seats_=std::move(active);
        }else{
            if(!shared_rally_)shared_rally_=RallyPathBank{independent(baseline),{}};
            advance_flag(*shared_rally_,destination({},revision).value());restore(baseline);
        }
    }catch(...){restore(baseline);throw;}
    rally_base_=baseline.chase;
}
void SeatPathTracking::restore_rally(){if(rally_base_)restore_chase(*rally_base_);}
void SeatPathTracking::begin_zombies(){
    if(phase_baseline_)throw std::logic_error("nested zombie tracking phase");
    phase_baseline_=capture();selected_.reset();
}
void SeatPathTracking::end_zombies(){
    if(!phase_baseline_)throw std::logic_error("missing zombie tracking phase");
    restore(*phase_baseline_);phase_baseline_.reset();selected_.reset();
}
void SeatPathTracking::switch_for(const CombatZombie& unit,std::span<const Seat> present){
    if(unit.source.charmed.present())return;
    if(std::none_of(seats_.begin(),seats_.end(),[](const auto& bank){return bank.has_value();}))return;
    Seat seat;
    if(commands_.for_owner(world_.mode,unit.source.seat)==PathMode::follow_hero){
        seat=unit.source.seat.value_or(Seat::zombie);
        if(std::find(present.begin(),present.end(),seat)==present.end())seat=Seat::zombie;
    }else seat=world_.heroes.hero(Seat::plant).actual_seat.value_or(Seat::plant);
    if(selected_==seat || !seats_[seat_index(seat)])return;
    if(!phase_baseline_)throw std::logic_error("tracking switch outside zombie phase");
    restore_rally();
    if(selected_)seats_[seat_index(*selected_)]=capture();
    restore(*seats_[seat_index(seat)]);
    if(rally_base_)rally_base_=capture_chase();
    selected_=seat;
}
void SeatPathTracking::select_rally(const CombatZombie& unit){
    restore_rally();
    if(unit.source.charmed.present() || !flags_.for_owner(world_.mode,unit.source.seat))return;
    const auto& bank=world_.mode==MatchMode::duo?rally_seats_[seat_index(unit.source.seat.value_or(Seat::zombie))]:shared_rally_;
    if(bank && rally_base_)restore_chase(bank->path.chase);
}
} // namespace pvz::typed72
