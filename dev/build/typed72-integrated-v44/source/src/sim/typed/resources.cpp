#include "sim/typed/resources.h"
#include "sim/typed/projectile_rules.h"
#include "core/pymath.h"
#include <algorithm>
#include <cmath>
#include <map>
#include <tuple>
#include <unordered_set>

namespace pvz::typed72 {
namespace {
bool secret(const HeroPlayer& p,std::string_view name){return std::find(p.secrets.begin(),p.secrets.end(),name)!=p.secrets.end();}
bool flag(const Field<bool>& f){return f.present()&&!f.is_null()&&f.get();}
// Numeric suffixes are compared by magnitude without overflow. Older saves
// may contain an unnumbered ID; it sorts with numeric zero and then by text.
std::string_view id_number(const std::string& id){
    if(id.size()<2)return {};
    const std::string_view digits(id.data()+1,id.size()-1);
    if(std::any_of(digits.begin(),digits.end(),[](char c){return c<'0'||c>'9';}))return {};
    const auto first=digits.find_first_not_of('0');return first==std::string_view::npos?std::string_view{}:digits.substr(first);
}
bool before(const MatchResource* a,const MatchResource* b){
    const auto x=id_number(a->id),y=id_number(b->id);
    return std::tuple{x.size(),x,a->id}<std::tuple{y.size(),y,b->id};
}
template<class T> bool same_field(const Field<T>& a,const Field<T>& b){
    const bool av=a.present()&&!a.is_null(),bv=b.present()&&!b.is_null();
    return av==bv && (!av || a.get()==b.get());
}
}
MatchResource* Resources::find(const std::string& id){const auto p=index_.find(id);return p==index_.end()?nullptr:&*p->second;}
NativeSun* Resources::motion(const std::string& id){const auto p=motion_index_.find(id);return p==motion_index_.end()?nullptr:&p->second->sun;}
void Resources::admit(MatchResource value){
    if(auto* old=find(value.id)){*old=std::move(value);return;}
    records_.push_back(std::move(value));const auto item=std::prev(records_.end());
    try{index_.emplace(item->id,item);}catch(...){records_.erase(item);throw;}
}
void Resources::set_motion(std::string id,NativeSun value){
    if(auto* old=motion(id)){*old=std::move(value);return;}
    motions_.push_back({std::move(id),std::move(value)});const auto item=std::prev(motions_.end());
    try{motion_index_.emplace(item->id,item);}catch(...){motions_.erase(item);throw;}
}
void Resources::expire(const std::string& id){
    const auto p=index_.find(id);if(p==index_.end())return;
    const auto record=p->second;index_.erase(p);records_.erase(record);
}
void Resources::remove_motion(const std::string& id){
    const auto p=motion_index_.find(id);if(p==motion_index_.end())return;
    const auto record=p->second;motion_index_.erase(p);motions_.erase(record);
}
void Resources::income(const MatchResource& r,Seat side,double amount,bool shared_auto){
    auto& account=accounts.at(seat_index(side));account.balance+=amount;account.earned+=amount;
    world_.runtime.events.emplace_back(ResourceIncomeEvent{side,amount,r.source,r.id,shared_auto,world_.runtime.sound_source?world_.runtime.sound_source():std::nullopt});
}
std::string Resources::create(Seat side,double amount,Point p,std::string source){
    if(source!="sky" && source!="day_income" && source!="petrified_torch" && source!="masochist")world_.runtime.sound("阳光菇",{p.x,p.y,0.,0.});
    const std::string id="r"+std::to_string(++sequence_);
    admit({id,side,amount,world_.heroes.time,{py::mod(p.x,world_.world_width.get()),p.y},std::move(source),{},{}});
    if(team_of(side)==Seat::zombie)collect(id);
    else set_motion(id,{0.,{p.x,p.y,0.,0.},0.,1.,{},{}});
    return id;
}
void Resources::collect(const std::string& id,std::optional<Seat> collector){
    auto* r=find(id);if(!r)return;
    const bool coin=r->coin.present()&&!r->coin.is_null()&&!r->coin.get().empty();
    if(coin){
        const auto copy=*r;expire(id);remove_motion(id);coins+=copy.amount;
        const auto side=collector.value_or(copy.side);
        if(world_.heroes.players.at(seat_index(side))){auto& count=accounts.at(seat_index(side)).coins;count.set(count.or_missing(0.)+copy.amount);}
        world_.runtime.events.emplace_back(CoinIncomeEvent{side,copy.amount,copy.id});
    }else{
        if(collector)r->side=*collector;
        const auto copy=*r;expire(id);income(copy,copy.side,copy.amount);
    }
}
std::string Resources::drop_coin(double amount,Point p,std::string kind){
    const auto id=create(Seat::plant,amount,p,"coin");auto& r=*find(id);
    r.shared.set(true);r.coin.set(std::move(kind));return id;
}
bool Resources::auto_shared_sky(const std::string& id){
    const auto* r=find(id);if(!r || r->source!="sky")return false;
    std::vector<Seat> seats;
    for(auto s:seats_for(world_.mode))if(team_of(s)==Seat::plant)seats.push_back(s);
    if(seats.size()!=2 || std::none_of(seats.begin(),seats.end(),[&](Seat s){return secret(world_.heroes.players.at(seat_index(s)).value(),"secret:阳光");}))return false;
    const auto copy=*r;expire(id);remove_motion(id);
    for(const auto seat:seats)income(copy,seat,15.,true);
    return true;
}
bool Resources::touching(const MatchResource& r,const HeroPlayer& p)const{
    const auto factor=r.amount<=25.?1.:std::min(2.4,std::sqrt(r.amount/25.));
    return std::hypot(wrap_delta(r.position.x,p.position.x,world_.world_width.get()),r.position.y-p.position.y+30.)<60.*factor;
}
std::optional<Seat> Resources::shared_collector(const MatchResource& r)const{
    for(const auto side:seats_for(world_.mode)){
        if(team_of(side)!=Seat::plant)continue;
        const auto& p=world_.heroes.players.at(seat_index(side)).value();
        if(p.hp>0. && (secret(p,"secret:阳光") || touching(r,p)))return side;
    }
    return {};
}
void Resources::settle(double lifetime){
    std::vector<std::string> ids;ids.reserve(records_.size());for(const auto& r:records_)ids.push_back(r.id);
    const bool team=world_.mode==MatchMode::duo||world_.mode==MatchMode::coop;
    for(const auto& id:ids){
        const auto* r=find(id);if(!r)throw std::logic_error("resource collection order changed");
        if(flag(r->shared)){
            if(auto_shared_sky(id))continue;
            if(const auto collector=shared_collector(*r))collect(id,collector);
            else if(world_.heroes.time-r->born>lifetime)expire(id);
            continue;
        }
        const auto& player=world_.heroes.players.at(seat_index(r->side)).value();
        if(team && player.hp<=0.){
            if(world_.mode==MatchMode::coop && team_of(r->side)==Seat::plant){
                if(const auto collector=shared_collector(*r)){collect(id,collector);continue;}
            }
            if(world_.heroes.time-r->born>lifetime)expire(id);
            continue;
        }
        if((team_of(r->side)==Seat::plant && secret(player,"secret:阳光")) || touching(*r,player))collect(id);
        else if(world_.heroes.time-r->born>lifetime)expire(id);
    }
}
void Resources::advance_suns(){
    auto& index=world_.heroes.source_index;
    struct Restore {std::optional<int64_t>& slot;int64_t old;~Restore(){slot=old;}} restore{index,index.value_or(0)};
    for(auto it=motions_.begin();it!=motions_.end();){
        const auto current=it++;auto* r=find(current->id);
        if(!r){remove_motion(current->id);continue;}
        index=0;regions_.sun_motion(current->sun);
        auto& m=current->sun.motion;m.x=py::mod(m.x,world_.world_width.get());r->position={m.x,m.y};
    }
}
void Resources::merge_suns(){
    std::vector<MatchResource*> suns;
    for(auto& r:records_)if(team_of(r.side)==Seat::plant && motion(r.id))suns.push_back(&r);
    if(suns.size()<2)return;
    std::sort(suns.begin(),suns.end(),before);
    const double reach=.6*world_.runtime.tile,width=world_.world_width.get();
    const int64_t cols=std::max<int64_t>(1,int64_t(std::ceil(width/reach)));
    const auto column=[&](double x){return int64_t(py::mod(py::floordiv(x,reach),double(cols)));};
    bool changed=true;
    while(changed){
        changed=false;
        std::map<std::pair<int64_t,int64_t>,std::vector<MatchResource*>> grid;
        for(auto* r:suns)grid[{column(r->position.x),int64_t(py::floordiv(r->position.y,reach))}].push_back(r);
        std::unordered_set<const MatchResource*> gone;
        for(auto* r:suns){
            if(gone.contains(r))continue;
            const auto gx=column(r->position.x),gy=int64_t(py::floordiv(r->position.y,reach));
            const auto m=motion(r->id)->motion;
            std::vector<MatchResource*> neighbours;
            for(int dx=-1;dx<=1;++dx)for(int dy=-1;dy<=1;++dy){
                auto found=grid.find({int64_t(py::mod(double(gx+dx),double(cols))),gy+dy});
                if(found==grid.end())continue;
                for(auto* other:found->second)if(other!=r && !gone.contains(other))neighbours.push_back(other);
            }
            std::sort(neighbours.begin(),neighbours.end(),before);
            for(auto* other:neighbours){
                if(gone.contains(other))continue;
                if(std::hypot(wrap_delta(r->position.x,other->position.x,width),other->position.y-r->position.y)>reach)continue;
                if(other->side!=r->side || !same_field(other->shared,r->shared) || !same_field(other->coin,r->coin))continue;
                const auto om=motion(other->id)->motion;
                if(std::abs(m.vx-om.vx)+std::abs(m.vy-om.vy)>.05)continue;
                auto* keep=r->amount>=other->amount?r:other;auto* drop=keep==r?other:r;
                keep->amount+=drop->amount;keep->born=std::max(keep->born,drop->born);
                // Defer physical erasure until all snapshot pointers from this
                // pass expire, preserving Python's captured list identities.
                gone.insert(drop);changed=true;if(drop==r)break;
            }
        }
        std::erase_if(suns,[&](const auto* r){return gone.contains(r);});
        for(const auto* r:gone){const auto id=r->id;expire(id);remove_motion(id);}
    }
}
} // namespace pvz::typed72
