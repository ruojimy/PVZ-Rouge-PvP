// pve.WaveDirector and coop_cycle.CoopCycle, block by block. Constants and
// method names follow the source; line references are to pve.py / coop_cycle.py.
#include "sim/typed/pve_director.h"
#include "core/pymath.h"
#include <algorithm>
#include <cmath>
namespace pvz::typed72 {
namespace {
constexpr double STAGGER=4.,SPAWN_PRESSURE_RATIO=.7;
constexpr int64_t WAVE_CLEAR_PERCENT=80;
const std::string LADDER_SUPPORT="zombie:梯子僵尸",FLAG_ZOMBIE="zombie:旗帜僵尸";
// coop_cycle.py
constexpr double PHASE_SECONDS=120.,GRAVE_INTERVAL=20.,GRAVE_SHARE=.25,MAX_GRAVE_SHARE=.75,DAVE_CLEARANCE=8.,NEAR_BAND=2.;
constexpr size_t MAX_ACTIVE_GRAVES=3;
int64_t py_mod_index(int64_t a,int64_t n){const auto r=a%n;return r<0?r+n:r;}
std::string id_of(const AttackSource& s){return s.id.present()&&!s.id.is_null()?s.id.get():std::string{};}
bool truthy(const Field<bool>& f){return f.present()&&!f.is_null()&&f.get();}
// "血量" > 0 and neither "灰烬" nor "魅惑" keys present.
bool standing(const CombatZombie& z){return z.body.hp>0.&&!z.body.ash.present()&&!z.source.charmed.present();}
}
void PveDirector::bind(const PveDirectorCold& c){
    day_=c.day;seed_=c.seed;max_zombies_=c.max_zombies;coop_=c.coop;points_=c.points;pool_=c.pool;plan_=c.plan;rng_.set_state(c.rng);
    cycle_=c.cycle;initial_night_=c.initial_night;cycle_rng_.set_state(c.cycle_rng);phase_=-1;next_grave_=0.;
    ladders_.director_available=true;bound_=true;
}
double PveDirector::now()const{return world_.heroes.time;}
double PveDirector::cost(const std::string& key)const{const auto* card=catalog_.find(key);if(!card)throw std::out_of_range("pve card "+key);return card->cost;}
// _compose (pve.py:222)
std::vector<std::string> PveDirector::compose(double budget,bool flag){
    std::vector<std::string> chosen;
    if(flag&&catalog_.find(FLAG_ZOMBIE)){chosen.push_back(FLAG_ZOMBIE);budget-=cost(FLAG_ZOMBIE);}
    std::vector<std::pair<std::string,double>> pool;for(const auto& e:pool_)if(e.weight>0.)pool.emplace_back(e.key,e.weight);
    while(!pool.empty()){
        std::vector<std::pair<std::string,double>> affordable;for(const auto& e:pool)if(cost(e.first)<=budget)affordable.push_back(e);
        if(affordable.empty())break;
        double total=0.;for(const auto& e:affordable)total+=e.second;
        double pick=rng_.random()*total;const std::string* key=nullptr;
        for(const auto& e:affordable){key=&e.first;pick-=e.second;if(pick<=0.)break;}
        chosen.push_back(*key);budget-=cost(*key);
    }
    return chosen;
}
// CPython 3.8 Random.sample over range(n).
std::vector<int64_t> PveDirector::sample(int64_t n,int64_t k){
    if(k<0||k>n)throw std::invalid_argument("Sample larger than population or is negative");
    std::vector<int64_t> result(static_cast<size_t>(k),0);int64_t setsize=21;
    if(k>5)setsize+=int64_t(std::pow(4.,std::ceil(std::log(double(3*k))/std::log(4.))));
    if(n<=setsize){
        std::vector<int64_t> pool(static_cast<size_t>(n),0);for(int64_t i=0;i<n;++i)pool[size_t(i)]=i;
        for(int64_t i=0;i<k;++i){const auto j=int64_t(rng_.randbelow(uint64_t(n-i)));result[size_t(i)]=pool[size_t(j)];pool[size_t(j)]=pool[size_t(n-i-1)];}
    }else{
        std::set<int64_t> selected;
        for(int64_t i=0;i<k;++i){auto j=int64_t(rng_.randbelow(uint64_t(n)));while(selected.count(j))j=int64_t(rng_.randbelow(uint64_t(n)));selected.insert(j);result[size_t(i)]=j;}
    }
    return result;
}
// fronts (pve.py:346)
std::vector<int64_t> PveDirector::fronts(const PveWavePlan& wave){
    const auto count=int64_t(points_.size());if(!count)return {0};
    if(coop_){const auto start=rng_.randrange(count);std::vector<int64_t> out;for(int64_t i=0;i<count;++i)out.push_back((start+i)%count);return out;}
    const int64_t width=(day_>=6||wave.flag)&&count>1?2:1;return sample(count,width);
}
std::vector<Seat> PveDirector::alive_plant_seats()const{
    std::vector<Seat> out;
    for(size_t i=0;i<world_.heroes.players.size();++i){const auto seat=Seat(i);const auto& p=world_.heroes.players[i];if(p&&team_of(seat)==Seat::plant&&p->hp>0.)out.push_back(seat);}
    return out;
}
double PveDirector::health_scale()const{return std::min(1.8,1.+.08*double(std::max<int64_t>(0,day_-9)));}
// _spawn (pve.py:359)
bool PveDirector::spawn(const std::string& key,int64_t point,int64_t wave){
    if(points_.empty())return false;
    if(!budget_.can_spawn())return false;
    const auto n=int64_t(points_.size());const auto slot=py_mod_index(point,n);
    double x=points_[size_t(slot)].x,y=points_[size_t(slot)].y;const double width=world_.world_width.get(),tile=world_.runtime.tile;
    const auto found=cycle_?origin(slot,key,wave):std::nullopt;
    if(found){x=found->second.x;y=found->second.y;}
    else x=py::mod(x+(rng_.random()-.5)*tile*.8,width);
    auto seats=alive_plant_seats();if(seats.empty())seats.push_back(Seat::plant);
    Seat target=seats.front();double best=std::abs(world_.heroes.players.at(seat_index(target))->position.x-x);
    for(const auto seat:seats){const double d=std::abs(world_.heroes.players.at(seat_index(seat))->position.x-x);if(d<best){best=d;target=seat;}}
    const double tx=world_.heroes.players.at(seat_index(target))->position.x;
    const double facing=py::mod(tx-x+width/2.,width)-width/2.>=0.?1.:-1.;
    const auto id=services_.spawn_wave_zombie(key,{x,y},facing,wave);if(!id)return false;
    const auto native=services_.native_zombie(*id);
    wave_members[wave].insert(*id);
    if(native){
        native->source.wave_index.set(wave);
        if(found)native->pve.spawn_grave.set(found->first);
        const double scale=health_scale();
        if(scale>1.){native->body.hp*=scale;native->max_hp.set(native->body.hp);}
    }
    spawned.push_back(*id);alive_.push_back({*id,{key,std::nullopt}});last_spawn_time=now();
    return true;
}
// _observe_wave_members
void PveDirector::observe_wave_members(){
    for(const auto& t:*world_.targets){
        if(!t.unit)continue;const auto& w=t.unit->source.wave_index;const auto uid=id_of(t.unit->source);
        if(w.present()&&!w.is_null()&&!uid.empty())wave_members[w.get()].insert(uid);
    }
}
// _wave_progress (pve.py:304), with the scripted spawn budget always installed.
PveWaveProgress PveDirector::wave_progress(int64_t index){
    observe_wave_members();
    const auto& members=wave_members[index];const auto pending=int64_t(budget_.pending_count(index));int64_t live=0;
    for(const auto& uid:members){
        // A unit whose native record is gone is also gone from battle.units by the
        // time the room step runs (_sync_public prunes both), so it counts as not live.
        if(const auto z=services_.native_zombie(uid))live+=ScriptedSpawnBudget::live_enemy(CombatTarget::zombie(z));
    }
    PveWaveProgress p;p.total=int64_t(members.size())+pending;p.pending=pending;p.remaining=live+pending;
    p.cleared=std::max<int64_t>(0,p.total-live-pending);
    for(const auto& e:queue)if(e.wave==index)++p.queued;
    p.clear_percent=p.total?(100*p.cleared)/p.total:100;
    return p;
}
bool PveDirector::can_advance(){
    if(next_wave>=int64_t(plan_.size()))return false;
    if(next_wave==0)return now()+1e-9>=plan_[0].time;
    const auto p=wave_progress(next_wave-1);return p.queued==0&&p.clear_percent>=WAVE_CLEAR_PERCENT;
}
// coin_drop (pve.py:158)
std::pair<double,std::string> PveDirector::coin_drop(const std::string& key){
    const auto* card=catalog_.find(key);const double price=card?card->cost:25.;const double roll=rng_.random();
    if(key==FLAG_ZOMBIE||roll<.03)return {100.,"bag"};
    const double base=std::max(5.,py::round0(price/50.)*5.);
    if(roll<.18)return {base+25.,"gold"};
    return {base,"silver"};
}
// _pay_bounties (pve.py:399)
void PveDirector::pay_bounties(){
    for(size_t i=0;i<alive_.size();){
        auto& [uid,entry]=alive_[i];const auto z=services_.native_zombie(uid);
        if(z&&standing(*z)){
            const auto& m=z->body.motion.get();entry.second=Point{m.x,m.y-world_.runtime.tile};++i;continue;
        }
        const auto key=entry.first;const auto last=entry.second;alive_.erase(alive_.begin()+std::ptrdiff_t(i));
        if(!last)continue;
        const auto [amount,kind]=coin_drop(key);services_.drop_coin(amount,*last,kind);
    }
}
// step (pve.py:242)
void PveDirector::step(){
    const double t=now();
    observe_wave_members();pay_bounties();
    if(can_advance()){
        const auto wave_index=next_wave;const auto wave=plan_[size_t(next_wave)];last_flag=wave.flag;
        auto keys=compose(double(wave.budget),wave.flag);
        if(next_wave==0){
            keys.insert(keys.begin(),LADDER_SUPPORT);ladders_.ladder_count=std::max<int64_t>(0,ladders_.ladder_count-1);
            services_.event({"pve_ladder_support",{{"source",std::string("opening")},{"day",day_}}});
        }
        const auto front=fronts(wave);
        for(size_t i=0;i<keys.size();++i)
            queue.push_back({t+STAGGER*double(i)/double(std::max<size_t>(1,keys.size())),keys[i],front[i%front.size()],wave_index});
        wave_members[wave_index];wave_started[wave_index]=t;
        services_.event({"pve_wave",{{"day",day_},{"wave",next_wave+1},{"waves",int64_t(plan_.size())},{"flag",wave.flag},{"count",int64_t(keys.size())}}});
        ++next_wave;
    }
    for(const auto point:pending_ladders)queue.push_back({t,LADDER_SUPPORT,point,std::max<int64_t>(0,next_wave-1)});
    pending_ladders.clear();
    std::vector<PveQueued> due;for(const auto& e:queue)if(e.at<=t+1e-9)due.push_back(e);
    if(pressure>=SPAWN_PRESSURE_RATIO&&due.size()>1){paced+=int64_t(due.size())-1;due.resize(1);}
    if(budget_.pending_count())due.clear();
    for(const auto& e:due){
        if(budget_.available()<=0)break;
        if(!spawn(e.key,e.point,e.wave))break;
        queue.erase(std::find(queue.begin(),queue.end(),e));
    }
    if(pressure>=SPAWN_PRESSURE_RATIO)pressure_seconds+=1./30.;
}
// request_ladder (pve.py:334)
void PveDirector::request_ladder(const ZombieRef& z){
    if(points_.empty()||ladders_.ladder_count<=0||ladders_.ladder_cooldown>0)return;
    const auto& m=z->body.motion.get();const double width=world_.world_width.get();
    size_t best=0;double best_d=0.;
    for(size_t i=0;i<points_.size();++i){
        const double a=std::abs(points_[i].x-m.x),dx=std::min(a,width-a),dy=points_[i].y-m.y,d=dx*dx+dy*dy;
        if(i==0||d<best_d){best=i;best_d=d;}
    }
    pending_ladders.push_back(int64_t(best));--ladders_.ladder_count;ladders_.ladder_cooldown=last_flag?2000:10000;
    services_.event({"pve_ladder_support",{{"source",std::string("blocked")},{"point",int64_t(best)},{"day",day_}}});
}
bool PveDirector::cleared()const{
    return bound_&&next_wave>=int64_t(plan_.size())&&queue.empty()&&pending_ladders.empty()&&!budget_.pending_count()&&budget_.count()==0;
}

// ------------------------------------------------------------ CoopCycle
double PveDirector::distance(double x,double y,double tx,double ty)const{
    const double w=world_.world_width.get();return std::hypot(py::mod(tx-x+w/2.,w)-w/2.,ty-y);
}
// CoopCycle.step (coop_cycle.py:29)
void PveDirector::cycle_step(){
    if(!cycle_)return;
    const double t=now();const auto phase=int64_t(py::floordiv(t,PHASE_SECONDS));
    const bool night=initial_night_^bool(py::mod(double(phase),2.)!=0.);const bool changed=phase!=phase_;
    if(changed){
        phase_=phase;services_.set_daylight(night);next_grave_=t;
        services_.event({"coop_daylight",{{"night",night},{"phase",phase}}});
    }
    mushrooms(night,changed);
    if(night&&t+1e-9>=next_grave_){next_grave_=t+GRAVE_INTERVAL;grow();}
    rotate();
}
// CoopCycle.graves: every live diverting grave, by _pvp_id.
std::vector<ZombieRef> PveDirector::graves()const{
    std::vector<ZombieRef> out;
    for(const auto& t:*world_.targets)if(t.unit&&t.unit->protection.grave&&!truthy(t.unit->producer)&&standing(*t.unit))out.push_back(t.unit);
    std::stable_sort(out.begin(),out.end(),[](const ZombieRef& a,const ZombieRef& b){return id_of(a->source)<id_of(b->source);});
    return out;
}
// CoopCycle.rotate (coop_cycle.py:57)
void PveDirector::rotate(){
    const auto all=graves();std::set<int64_t> queued;for(const auto& e:queue)queued.insert(e.wave);
    for(const auto& [wave,ids]:emitted_){
        if(finished_.count(wave)||queued.count(wave)||wave>=next_wave)continue;
        finished_.insert(wave);last_finished_=wave;
        for(const auto& z:all)if(ids.count(id_of(z->source))){z->registration.coop_dormant.set(true);z->pve.just_slept.set(wave);}
        services_.event({"coop_graves_dormant",{{"wave",wave},{"graves",std::vector<std::string>(ids.begin(),ids.end())}}});
    }
    std::vector<ZombieRef> active;for(const auto& z:all)if(!truthy(z->registration.coop_dormant))active.push_back(z);
    for(size_t i=MAX_ACTIVE_GRAVES;i<active.size();++i)active[i]->registration.coop_dormant.set(true);
    if(active.size()>MAX_ACTIVE_GRAVES)active.resize(MAX_ACTIVE_GRAVES);
    std::vector<ZombieRef> dormant;for(const auto& z:all)if(truthy(z->registration.coop_dormant))dormant.push_back(z);
    while(active.size()<MAX_ACTIVE_GRAVES&&!dormant.empty()){
        // z.get('_pvp_coop_just_slept') != last, both None-able.
        std::vector<ZombieRef> rested;
        for(const auto& z:dormant){
            const auto& js=z->pve.just_slept;const std::optional<int64_t> mark=js.present()&&!js.is_null()?std::optional<int64_t>(js.get()):std::nullopt;
            if(mark!=last_finished_)rested.push_back(z);
        }
        if(rested.empty())rested=dormant;
        const auto z=rested[cycle_rng_.choice_index(rested.size())];
        z->registration.coop_dormant.erase();z->pve.just_slept.erase();
        dormant.erase(std::find(dormant.begin(),dormant.end(),z));active.push_back(z);
        services_.event({"coop_grave_woken",{{"entity",id_of(z->source)}}});
    }
}
// CoopCycle.grow (coop_cycle.py:84)
void PveDirector::grow(){
    const double tile=world_.runtime.tile;
    std::vector<Point> daves;
    // b.players order is ("plant","zombie")+others; only standing plant seats count.
    std::vector<Seat> order{Seat::plant,Seat::zombie};for(size_t i=0;i<world_.heroes.players.size();++i)if(Seat(i)!=Seat::plant&&Seat(i)!=Seat::zombie)order.push_back(Seat(i));
    for(const auto seat:order){const auto& p=world_.heroes.players.at(seat_index(seat));if(p&&team_of(seat)==Seat::plant&&p->hp>0.)daves.push_back(p->position);}
    if(daves.empty())return;
    struct Candidate{double d,x,y;};std::vector<Candidate> candidates;
    const auto& tiles=terrain_.tiles;
    for(size_t row=0;row+1<tiles.size();++row)for(size_t col=0;col<tiles[row].size();++col){
        const auto& cell=tiles[row][col];const double x=(double(col)+.5)*tile,y=double(row+1)*tile;
        // b.cell(x, y+1): row+1 exists because the last row is skipped.
        const auto& line=tiles[row+1];const auto& below=line[size_t(int64_t(std::floor(py::mod(x,world_.world_width.get())/tile))%int64_t(line.size()))];
        if(cell.solid||cell.water||!(below.solid||below.water))continue;
        bool taken=false;
        for(const auto& p:*world_.plant_roster)if(p->cell.y==int64_t(row)&&p->cell.x==int64_t(col)&&p->hp.or_missing(0.)>0.){taken=true;break;}
        if(taken)continue;
        for(const auto& t:*world_.targets)if(t.unit&&t.unit->protection.grave&&t.unit->body.hp>0.){
            const auto& m=t.unit->body.motion.get();if(distance(x,y,m.x,m.y)<tile){taken=true;break;}
        }
        if(taken)continue;
        double nearest=distance(x,y,daves.front().x,daves.front().y);for(const auto& d:daves)nearest=std::min(nearest,distance(x,y,d.x,d.y));
        if(nearest>=DAVE_CLEARANCE*tile)candidates.push_back({nearest,x,y});
    }
    if(candidates.empty())return;
    double closest=candidates.front().d;for(const auto& c:candidates)closest=std::min(closest,c.d);
    std::vector<Point> band;for(const auto& c:candidates)if(c.d<=closest+NEAR_BAND*tile)band.push_back({c.x,c.y});
    const auto spot=band[cycle_rng_.choice_index(band.size())];
    const auto grave=services_.spawn_remnant(spot);
    if(grave){grave->pve.night_grave.set(true);services_.event({"coop_grave",{{"entity",id_of(grave->source)},{"x",spot.x},{"y",spot.y}}});}
}
// CoopCycle.mushrooms (coop_cycle.py:122)
void PveDirector::mushrooms(bool night,bool changed){
    std::set<std::string> sleepers;
    for(const auto& plant:*world_.plant_roster){
        const auto& key=plant->protection.card;const auto* card=key.present()&&!key.is_null()?catalog_.find(key.get()):nullptr;
        if(!card||!truthy(card->mushroom)||plant->hp.or_missing(0.)<=0.)continue;
        const auto uid=id_of(plant->source);
        if(!night&&!changed&&sleepers_.count(uid)&&!plant->sleep.present())plant->pve.coop_coffee.set(true);
        if(night)plant->sleep.erase();
        else if(changed&&!truthy(plant->pve.coop_coffee))plant->sleep.set(0.);
        if(plant->sleep.present())sleepers.insert(uid);
    }
    sleepers_=std::move(sleepers);
}
// CoopCycle.groups: live, non-dormant graves serve their nearest point.
std::map<int64_t,std::vector<ZombieRef>> PveDirector::groups()const{
    std::map<int64_t,std::vector<ZombieRef>> out;for(size_t i=0;i<points_.size();++i)out[int64_t(i)];
    if(out.empty())return out;
    for(const auto& t:*world_.targets){
        if(!t.unit)continue;const auto& z=*t.unit;
        if(!z.protection.grave||truthy(z.producer)||!standing(z)||truthy(z.registration.coop_dormant))continue;
        const auto& m=z.body.motion.get();size_t best=0;double best_d=0.;
        for(size_t i=0;i<points_.size();++i){const double d=distance(m.x,m.y,points_[i].x,points_[i].y);if(i==0||d<best_d){best=i;best_d=d;}}
        out[int64_t(best)].push_back(t.unit);
    }
    for(auto& [point,list]:out)std::stable_sort(list.begin(),list.end(),[](const ZombieRef& a,const ZombieRef& b){return id_of(a->source)<id_of(b->source);});
    return out;
}
std::optional<std::pair<std::string,Point>> PveDirector::origin(int64_t point,const std::string& card,int64_t wave){
    auto found=origin_inner(point,card);if(found)emitted_[wave].insert(found->first);return found;
}
// CoopCycle._origin: fractional quota, never more than 75% of admitted spawns.
std::optional<std::pair<std::string,Point>> PveDirector::origin_inner(int64_t point,const std::string& card){
    const auto all=groups();std::vector<std::pair<std::string,Point>> available;
    if(const auto it=all.find(point);it!=all.end())for(const auto& grave:it->second){
        const auto id=id_of(grave->source);if(const auto exit=services_.grave_soldier_exit(card,id))available.push_back({id,*exit});
    }
    if(available.empty()){credit_[point]=0.;return std::nullopt;}
    const double share=std::min(MAX_GRAVE_SHARE,GRAVE_SHARE*double(available.size()));
    credit_[point]+=share;if(credit_[point]<1.-1e-9)return std::nullopt;
    credit_[point]-=1.;const auto turn=turn_[point];turn_[point]=turn+1;
    return available[size_t(turn%int64_t(available.size()))];
}
nlohmann::json PveDirector::waves_snapshot(double time){
    using J=nlohmann::json;
    const bool has_next=next_wave<int64_t(plan_.size());
    J next_in=nullptr;
    if(has_next&&next_wave==0)next_in=py::roundn(std::max(0.,plan_[size_t(next_wave)].time-time),1);
    std::optional<PveWaveProgress> progress;if(next_wave)progress=wave_progress(next_wave-1);
    return {{"day",day_},{"wave",next_wave},{"waves",plan_.size()},{"next_in",next_in},{"next_flag",has_next&&plan_[size_t(next_wave)].flag},
            {"remaining",budget_.count()},{"max_zombies",max_zombies_},{"clear_required",80},
            {"clear_percent",progress?progress->clear_percent:0},{"wave_remaining",progress?progress->remaining:0},
            {"spawn_queued",queue.size()},{"pending_summons",progress?progress->pending:0},
            {"waiting_for_clear",has_next&&next_wave!=0},{"engine_load",py::roundn(pressure,2)},{"paced",paced}};
}
nlohmann::json PveDirector::daylight_snapshot(double time,bool night)const{
    using J=nlohmann::json;
    J fronts=J::array();
    for(const auto& [point,graves]:groups()){
        const double total=std::min(.75,.25*double(graves.size()));
        J rows=J::array();
        for(const auto& z:graves)rows.push_back({{"id",z->source.id.present()&&!z->source.id.is_null()?J(z->source.id.get()):J(nullptr)},{"share",total/double(graves.size())}});
        fronts.push_back({{"point",point},{"original_share",1.-total},{"graves",rows}});
    }
    return {{"night",night},{"next_change",std::max(0.,(double(phase_)+1.)*120.-time)},{"fronts",fronts}};
}
} // namespace pvz::typed72
