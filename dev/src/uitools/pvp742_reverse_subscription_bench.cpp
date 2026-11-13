// Evaluation only: shares the production MovingCoverageGrid, but is not connected
// to game logic. Exact synthetic geometry, ordering, health and lifecycle events
// are identical for both strategies. No rendering, SDL window or user data access.
#include "sim/typed/moving_coverage_grid.h"
#include <nlohmann/json.hpp>
#include <algorithm>
#include <chrono>
#include <cmath>
#include <fstream>
#include <iostream>
#include <numeric>
#include <string>
#include <vector>
using namespace pvz::typed72;using J=nlohmann::json;using Clock=std::chrono::steady_clock;
namespace {
constexpr double tile=48.,width=96*tile,height=32*tile,cell=tile;
constexpr int cols=96,rows=32;
double milliseconds(Clock::time_point start){return std::chrono::duration<double,std::milli>(Clock::now()-start).count();}
void require(bool b,const std::string& s){if(!b)throw std::runtime_error(s);}
uint64_t random_word(uint64_t& s){s^=s<<13;s^=s>>7;s^=s<<17;return s;}
double wrapped(double x){x=std::fmod(x,width);return x<0?x+width:x;}
double delta(double a,double b){const double d=b-a;return d-width*std::floor(d/width+.5);}
int column(int x){const int v=x%cols;return v<0?v+cols:v;}
struct Body {double x,y,hx,hy,hp;bool alive=true;};
struct Plant {double x,y,radius;int shape,priority,facing;};
CoverageBox box(const Body& b){return {b.x-b.hx,b.y-b.hy,b.x+b.hx,b.y+b.hy};}
CoverageBox region(const Plant& p){return {p.x-p.radius,p.y-p.radius,p.x+p.radius,p.y+p.radius};}
template<class F>void cells(CoverageBox b,F fn){
 const int left=int(std::floor(b.left/cell)),right=int(std::floor(b.right/cell));
 const int top=std::max(0,int(std::floor(b.top/cell))),bottom=std::min(rows-1,int(std::floor(b.bottom/cell)));
 for(int y=top;y<=bottom;++y)for(int i=0;i<std::min(cols,right-left+1);++i)fn(size_t(y*cols+column(left+i)));
}
bool same_cells(CoverageBox a,CoverageBox b){
 return int(std::floor(a.left/cell))==int(std::floor(b.left/cell))&&int(std::floor(a.right/cell))==int(std::floor(b.right/cell))&&
        int(std::floor(a.top/cell))==int(std::floor(b.top/cell))&&int(std::floor(a.bottom/cell))==int(std::floor(b.bottom/cell));
}
// Exact benchmark shapes: circle/AABB, annulus/AABB, rectangle/AABB,
// and forward semicircle/AABB (clip the target rectangle to the forward half-plane).
bool exact(const Plant& p,const Body& b){
 if(!b.alive)return false;
 double x=delta(p.x,b.x)*p.facing,y=b.y-p.y;
 double left=x-b.hx,right=x+b.hx,top=y-b.hy,bottom=y+b.hy;
 if(p.shape==2)return left<=p.radius&&right>=-p.radius&&top<=p.radius*.5&&bottom>=-p.radius*.5;
 if(p.shape==3){left=std::max(0.,left);if(right<left)return false;}
 const double nx=std::max({left,0.,-right}),ny=std::max({top,0.,-bottom});
 if(nx*nx+ny*ny>p.radius*p.radius)return false;
 if(p.shape==1){const double fx=std::max(std::abs(left),std::abs(right)),fy=std::max(std::abs(top),std::abs(bottom));return fx*fx+fy*fy>=p.radius*p.radius*.1225;}
 return true;
}
struct Result {std::vector<size_t> hits;int64_t best=-1;};
struct Counts {uint64_t queries=0,candidates=0,exact_tests=0,notifications=0,raw_subscriber_visits=0,dirty_transitions=0,
 swept_cells=0,same_cell_moves=0,same_cell_notifications=0,cached_results=0;};
void choose(MovingCoverageGrid& grid,const std::vector<Body>& bodies,const Plant& p,Result& result,Counts& count){
 ++count.queries;result.hits.clear();result.best=-1;double best_score=-1.e300;
 const auto candidates=grid.rectangle(region(p));count.candidates+=candidates.size();
 for(const size_t id:candidates){const auto& b=bodies[id];if(!b.alive)continue;++count.exact_tests;if(!exact(p,b))continue;
  result.hits.push_back(id);const double dx=delta(p.x,b.x),dy=b.y-p.y;
  const double score=p.priority==0?b.hp:p.priority==1?-(dx*dx+dy*dy):-double(id);
  if(result.best<0||score>best_score){result.best=int64_t(id);best_score=score;}
 }
}
struct Change {size_t id;Body after;CoverageBox swept;bool moved=false,same_cell=false;};
struct Input {std::vector<Plant> plants;std::vector<Body> initial;std::vector<std::vector<Change>> frames;};
Input input(int plants,int zombies,int radius,int percent,int ticks){
 Input out;uint64_t rng=742;
 for(int i=0;i<plants;++i)out.plants.push_back({tile+double(random_word(rng)%uint64_t(width-2*tile)),tile+double(random_word(rng)%uint64_t(height-2*tile)),radius*tile,i%4,i%3,i%2?1:-1});
 out.plants[0]={20.37*tile,8.41*tile,radius*tile,0,0,1};
 for(int i=0;i<zombies;++i)out.initial.push_back({2*tile+double(random_word(rng)%uint64_t(width-4*tile)),2*tile+double(random_word(rng)%uint64_t(height-4*tile)),
    i%7==0?tile*1.1:tile*.15,i%7==0?tile*1.5:tile*.3,1000.+double(random_word(rng)%500),true});
 // Target 0 crosses the exact circular boundary inside unchanged covered cells.
 out.initial[0]={out.plants[0].x+out.plants[0].radius+6.,out.plants[0].y,4.,5.,2000.,true};
 auto bodies=out.initial;const int movers=std::max(1,zombies*percent/100);
 for(int tick=0;tick<ticks;++tick){auto& changes=out.frames.emplace_back();
  for(int i=0;i<movers;++i){size_t id=size_t((tick*movers+i)%zombies);if(tick<4){if(i==0)id=0;else if(id==0)id=size_t(zombies-1);}
   const Body before=bodies[id];Body after=before;double dx=double(int(random_word(rng)%15)-7),dy=double(int(random_word(rng)%7)-3);
   if(id==0&&tick<4){dx=tick%2?4.:-4.;dy=0.;}else if(i==0&&tick%53==0)dx=tile*5.;
   const double unwrapped=before.x+dx;after.x=wrapped(unwrapped);after.y=std::clamp(before.y+dy,2*tile,height-2*tile);
   const auto old_box=box(before);auto new_box=box(after);new_box.left+=unwrapped-after.x;new_box.right+=unwrapped-after.x;
   CoverageBox sweep{std::min(old_box.left,new_box.left),std::min(old_box.top,new_box.top),std::max(old_box.right,new_box.right),std::max(old_box.bottom,new_box.bottom)};
   changes.push_back({id,after,sweep,true,same_cells(old_box,new_box)});bodies[id]=after;
  }
  // Priority and liveness changes must notify even when positions do not change.
  const size_t changed=size_t(tick*37)%bodies.size();bodies[changed].hp=1000.+double(random_word(rng)%500);
  if(tick%47==0&&changed!=0)bodies[changed].alive=!bodies[changed].alive;
  changes.push_back({changed,bodies[changed],box(bodies[changed]),false,false});
 }
 return out;
}
struct Reverse {
 std::vector<std::vector<size_t>> subscribers;std::vector<uint8_t> dirty;std::vector<uint64_t> seen;uint64_t stamp=0;
 explicit Reverse(const std::vector<Plant>& plants):subscribers(cols*rows),dirty(plants.size(),1),seen(plants.size(),0){
  for(size_t id=0;id<plants.size();++id)cells(region(plants[id]),[&](size_t key){subscribers[key].push_back(id);});
 }
 void notify(const Change& change,Counts& count){
  if(++stamp==0){std::fill(seen.begin(),seen.end(),0);++stamp;}if(change.same_cell)++count.same_cell_moves;
  cells(change.swept,[&](size_t key){++count.swept_cells;for(const auto id:subscribers[key]){++count.raw_subscriber_visits;if(seen[id]==stamp)continue;seen[id]=stamp;++count.notifications;
    if(change.same_cell)++count.same_cell_notifications;if(!dirty[id]){dirty[id]=1;++count.dirty_transitions;}}});
 }
 size_t storage()const{size_t bytes=subscribers.capacity()*sizeof(std::vector<size_t>)+dirty.capacity()+seen.capacity()*sizeof(uint64_t);for(const auto& v:subscribers)bytes+=v.capacity()*sizeof(size_t);return bytes;}
 size_t registrations()const{size_t n=0;for(const auto& v:subscribers)n+=v.size();return n;}
};
J counts(const Counts& c){return {{"queries",c.queries},{"candidates",c.candidates},{"exact_tests",c.exact_tests},{"notifications",c.notifications},
 {"raw_subscriber_visits",c.raw_subscriber_visits},{"dirty_transitions",c.dirty_transitions},{"swept_cells",c.swept_cells},{"same_cell_moves",c.same_cell_moves},
 {"same_cell_notifications",c.same_cell_notifications},{"cached_results",c.cached_results}};}
J benchmark(const Input& in,int cadence,bool reverse_first){
 const size_t p=in.plants.size(),z=in.initial.size();MovingCoverageGrid active_grid,reverse_grid;
 active_grid.reset(cell,width,z);reverse_grid.reset(cell,width,z);auto bodies=in.initial;
 for(size_t id=0;id<z;++id){active_grid.cover(id,box(bodies[id]));reverse_grid.cover(id,box(bodies[id]));}
 const auto sub_started=Clock::now();Reverse reverse(in.plants);const double setup_ms=milliseconds(sub_started);
 std::vector<Result> expected(p),cached(p);std::vector<size_t> due;Counts ac,rc;
 double active_maintenance=0.,reverse_maintenance=0.,active_queries=0.,reverse_queries=0.;size_t active_peak=active_grid.storage_bytes(),reverse_peak=reverse_grid.storage_bytes();
 uint64_t digest=1469598103934665603ULL;uint64_t compared=0;
 for(size_t tick=0;tick<in.frames.size();++tick){const auto& changes=in.frames[tick];for(const auto& change:changes)bodies[change.id]=change.after;
  auto active_update=[&]{const auto start=Clock::now();for(const auto& change:changes)if(change.moved)active_grid.cover(change.id,box(change.after));active_maintenance+=milliseconds(start);};
  auto reverse_update=[&]{const auto start=Clock::now();for(const auto& change:changes){if(change.moved)reverse_grid.cover(change.id,box(change.after));reverse.notify(change,rc);}reverse_maintenance+=milliseconds(start);};
  if(reverse_first){reverse_update();active_update();}else{active_update();reverse_update();}
  due.clear();for(size_t id=0;id<p;++id)if(cadence==1||int(tick%size_t(cadence))==int(id%size_t(cadence)))due.push_back(id);
  auto active_work=[&]{const auto start=Clock::now();for(const auto id:due)choose(active_grid,bodies,in.plants[id],expected[id],ac);active_queries+=milliseconds(start);};
  auto reverse_work=[&]{const auto start=Clock::now();for(const auto id:due){if(reverse.dirty[id]){choose(reverse_grid,bodies,in.plants[id],cached[id],rc);reverse.dirty[id]=0;}else ++rc.cached_results;}reverse_queries+=milliseconds(start);};
  if(reverse_first){reverse_work();active_work();}else{active_work();reverse_work();}
  for(const auto id:due){require(expected[id].best==cached[id].best&&expected[id].hits==cached[id].hits,"exact result/order mismatch at tick "+std::to_string(tick)+" plant "+std::to_string(id));
   digest^=uint64_t(expected[id].best+1)+tick*31+id;digest*=1099511628211ULL;for(const auto target:expected[id].hits){digest^=target;digest*=1099511628211ULL;}++compared;
  }
  active_peak=std::max(active_peak,active_grid.storage_bytes());reverse_peak=std::max(reverse_peak,reverse_grid.storage_bytes());
 }
 size_t result_cache_bytes=cached.capacity()*sizeof(Result);for(const auto& r:cached)result_cache_bytes+=r.hits.capacity()*sizeof(size_t);
 return {{"passed",true},{"strictly_compared_queries",compared},{"result_digest",std::to_string(digest)},
  {"active",{{"maintenance_ms",active_maintenance},{"query_ms",active_queries},{"total_ms",active_maintenance+active_queries},{"counts",counts(ac)},
    {"grid_cache_hits",active_grid.cache_hits},{"grid_raw_candidates",active_grid.raw_candidates},{"grid_cell_changes",active_grid.cell_changes},{"peak_grid_buffer_bytes",active_peak}}},
  {"reverse",{{"maintenance_ms",reverse_maintenance},{"query_ms",reverse_queries},{"total_ms",reverse_maintenance+reverse_queries},{"subscription_build_ms",setup_ms},{"counts",counts(rc)},
    {"grid_cache_hits",reverse_grid.cache_hits},{"grid_raw_candidates",reverse_grid.raw_candidates},{"grid_cell_changes",reverse_grid.cell_changes},{"peak_grid_buffer_bytes",reverse_peak},
    {"subscription_buffer_bytes",reverse.storage()},{"subscription_registrations",reverse.registrations()},{"result_cache_buffer_bytes",result_cache_bytes},
    {"peak_owned_buffer_bytes",reverse_peak+reverse.storage()+result_cache_bytes}}}};
}
double median(std::vector<double> v){std::sort(v.begin(),v.end());return v[v.size()/2];}
}
int main(int argc,char** argv){
 if(argc<2)return 2;try{const int ticks=argc>2?std::stoi(argv[2]):120,repeats=argc>3?std::stoi(argv[3]):3;require(ticks>=60&&repeats>=1,"use at least 60 ticks and one repeat");
  J cases=J::array();int wins=0,losses=0;
  for(int p:{100,500})for(int z:{100,1000})for(int radius:{4,16})for(int moving:{1,100})for(int cadence:{30,1}){
   const Input in=input(p,z,radius,moving,ticks);J samples=J::array();std::vector<double> active,reverse;
   for(int repeat=0;repeat<repeats;++repeat){J sample=benchmark(in,cadence,repeat%2!=0);active.push_back(sample["active"]["total_ms"].get<double>());reverse.push_back(sample["reverse"]["total_ms"].get<double>());samples.push_back(std::move(sample));}
   for(size_t i=1;i<samples.size();++i)require(samples[i]["result_digest"]==samples[0]["result_digest"],"repeat input/results changed");
   const double a=median(active),r=median(reverse);if(r<a)++wins;else ++losses;
   J row={{"plants",p},{"zombies",z},{"radius_tiles",radius},{"moving_percent",moving},{"query_interval_ticks",cadence},{"ticks",ticks},{"repeats",repeats},
    {"active_median_ms",a},{"reverse_median_ms",r},{"reverse_over_active",r/a},{"samples",samples}};cases.push_back(row);
   row.erase("samples");std::cout<<row.dump()<<std::endl;
  }
  J report={{"passed",true},{"seed",742},{"cases",cases},{"reverse_faster_cases",wins},{"active_faster_cases",losses},
   {"scope","Evaluation prototype only, not connected to game. Production MovingCoverageGrid, 48px grid cells, periodic 96x32 tile world. Exact synthetic circle/annulus/rectangle/semicircle predicates, mixed AABB sizes, deterministic ordering and highest-HP/nearest/ordinal priorities. Identical precomputed movement, HP/liveness events and staggered query schedules. Every moved target notifies its swept volume even inside unchanged cells. Each scheduled result is compared by full ordered ID vector and chosen target, not only a hash."},
   {"measurement","Wall-clock work durations, not OS CPU accounting. Setup/input generation/strict comparison/telemetry excluded from maintenance/query timers. Repeats alternate algorithm order. Memory reports owned buffer capacity; allocator and map-node overhead, shared immutable inputs and validation output buffers are excluded; not process RSS or GC. Reverse includes persistent result cache and static subscriptions; active reuses the production region-candidate cache. No multithreading or GPU."}};
  std::ofstream(argv[1])<<report.dump(2);return 0;
 }catch(const std::exception& e){std::cerr<<e.what()<<std::endl;return 1;}
}
