#include "sim/typed72_app/ai/layers19.h"
#include "core/pymath.h"
#include <algorithm>
#include <cmath>

namespace pvz::typed72app::ai {
namespace {
double pmod(double a,double b){return py::mod(a,b);}
bool one_of(const std::string& s,std::initializer_list<const char*> set){for(const char* v:set)if(s==v)return true;return false;}
std::vector<std::string> role_get(const std::map<std::string,std::vector<std::string>>& m,const std::string& k){auto f=m.find(k);return f==m.end()?std::vector<std::string>{}:f->second;}
bool flag(const typed72::Field<bool>& f){return f.present()&&!f.is_null()&&f.get();}
int psgn(double v){return v>=0?1:-1;}
double dist(Ctx& c,double ax,double ay,double bx,double by){return std::hypot(wrap_delta(ax,bx,c.width),by-ay);}
bool fire_role(const std::string& r){return r=="shoot"||r=="lob";}
double deploy_count(const Log& log){double s=0;for(const auto& [k,v]:log.v)if(k.rfind("deploy:",0)==0)s+=v;return s;}
const std::vector<std::vector<Cell>>& tiles_of(Ctx& c){return c.b.tiles;}
bool solid_at(Ctx& c,int64_t col,int64_t row,int64_t cols){   // rv_air66._solid
    const auto& t=tiles_of(c);if(row<0||row>=int64_t(t.size()))return true;return t[size_t(row)][size_t(pmod(double(col),double(cols)))].solid;
}
}

// ================================================================ firing66
bool ballistic(const ColdCard& card){
    return !card.producer&&(card.behavior=="shoot"||flag(card.lob))&&!(flag(card.star)||flag(card.homing)||card.name=="香蒲"||card.name=="猫尾草");
}
namespace {
FiringCache& cache(Ctx& c){if(!c.firing_cache)c.firing_cache=std::make_shared<FiringCache>();return *std::static_pointer_cast<FiringCache>(c.firing_cache);}
std::vector<FiringTarget> targets_of(Ctx& c){
    std::vector<FiringTarget> out;
    for(const auto* u:c.enemy)if(u->hp>0)out.push_back({u->x,u->y,u->h});
    for(const auto& p:c.b.players)if(p.key.rfind("zombie",0)==0&&!p.absent&&p.hp>0)out.push_back({p.x,p.y,c.tile*1.8});
    if(c.b.players.empty()&&c.foe.hp>0)out.push_back({c.foe.x,c.foe.y,c.tile*1.8});
    return out;
}
bool clear_segment(Ctx& c,double x0,double y0,double x1,double y1){
    const auto& tiles=tiles_of(c);const double dx=wrap_delta(x0,x1,c.width),dy=y1-y0;
    const int64_t steps=std::max<int64_t>(1,int64_t(std::hypot(dx,dy)/(c.tile*.2))+1);
    const auto cols=int64_t(tiles[0].size()),rows=int64_t(tiles.size());
    for(int64_t i=0;i<=steps;++i){
        const auto row=int64_t(std::floor((y0+dy*double(i)/double(steps))/c.tile));
        const auto col=int64_t(pmod(std::floor(pmod(x0+dx*double(i)/double(steps),c.width)/c.tile),double(cols)));
        if(row>=rows||(row>=0&&tiles[size_t(row)][size_t(col)].solid))return false;
    }
    return true;
}
struct Arc{double t,vx,vy;};
std::optional<Arc> arc_solution(double dx,double dy,double speed,double gravity,bool high){
    const double b=gravity*dy-speed*speed;const double disc=b*b-gravity*gravity*(dx*dx+dy*dy);
    if(disc<0)return std::nullopt;
    std::vector<double> roots;for(double v:{(-b-std::sqrt(disc))/(.5*gravity*gravity),(-b+std::sqrt(disc))/(.5*gravity*gravity)})if(v>1e-8)roots.push_back(v);
    if(roots.empty())return std::nullopt;
    const double t=std::sqrt(high?*std::max_element(roots.begin(),roots.end()):*std::min_element(roots.begin(),roots.end()));
    return Arc{t,dx/t,(dy-.5*gravity*t*t)/t};
}
std::optional<double> body_entry(double x0,double y0,double x1,double y1,double tx,double foot,double height,double half_width){
    double low=0.,high=1.;
    const std::array<std::array<double,4>,2> axes{{{x0,x1,tx-half_width,tx+half_width},{y0,y1,foot-height,foot}}};
    for(const auto& [start,end,lo,hi]:axes){
        const double delta=end-start;
        if(std::abs(delta)<1e-9){if(!(lo<=start&&start<=hi))return std::nullopt;}
        else{double a=(lo-start)/delta,b=(hi-start)/delta;if(a>b)std::swap(a,b);low=std::max(low,a);high=std::min(high,b);if(low>high)return std::nullopt;}
    }
    return low;
}
bool clear_guided_arc(Ctx& c,double x,double y,double tx,double foot,double height,double speed,double gravity){
    if(!clear_segment(c,x,y,x,y-.05*c.tile))return false;
    const double ty=foot-.35*height;const double target=x+wrap_delta(x,tx,c.width);
    const auto solution=arc_solution(target-x,ty-y,speed,gravity,false);
    if(!solution)return false;
    double vx=solution->vx,vy=solution->vy;
    const int64_t limit=std::min<int64_t>(600,std::max<int64_t>(40,int64_t(solution->t*1.8)));
    for(int64_t tick=0;tick<limit;tick+=4){
        if(tick&&tick%20==0){
            const double keep=std::max(speed,std::hypot(vx,vy));
            if(const auto aimed=arc_solution(target-x,ty-y,keep,gravity,false)){
                const double ax=vx*.74+aimed->vx*.26,ay=vy*.74+aimed->vy*.26;const double norm=std::hypot(ax,ay);
                if(norm>1e-9){vx=ax/norm*keep;vy=ay/norm*keep;}
            }
        }
        const double nx=x+4*std::copysign(std::max(0.,std::abs(vx)-gravity),vx);
        const double ny=y+4*vy+gravity*20;vy+=gravity*8;
        if(const auto entry=body_entry(x,y,nx,ny,target,foot,height,c.tile*.35))return clear_segment(c,x,y,x+(nx-x)**entry,y+(ny-y)**entry);
        if(!clear_segment(c,x,y,nx,ny))return false;
        x=nx;y=ny;
    }
    return false;
}
bool clear_arc(Ctx& c,double x0,double y0,double tx,double ty,const ColdCard& card,std::optional<double> foot,std::optional<double> height){
    const double dx=wrap_delta(x0,tx,c.width),dy=ty-y0;
    const bool mortar=card.behavior=="mortar";const bool high=mortar||card.name=="甜椒投手";
    const double speed=c.tile*(mortar?.08:high?7./80.:7./120.);
    const double gravity=c.tile/(high?2500.:5000.);
    if(!high&&foot)return clear_guided_arc(c,x0,y0,tx,*foot,(height&&*height!=0.)?*height:1.5*c.tile,speed,gravity);
    const auto solution=arc_solution(dx,dy,speed,gravity,high);
    if(!solution)return false;
    const double t=solution->t,vx=solution->vx,vy=solution->vy;
    const int64_t steps=std::max<int64_t>(2,int64_t(t*(std::abs(vx)+std::abs(vy)+gravity*t)/(c.tile*.2))+1);
    double ox=x0,oy=y0;
    for(int64_t i=1;i<=steps;++i){
        const double clock=t*double(i)/double(steps);
        const double x=x0+vx*clock,y=y0+vy*clock+.5*gravity*clock*clock;
        if(!clear_segment(c,ox,oy,x,y))return false;
        ox=x;oy=y;
    }
    return true;
}
FiringAssessment check(Ctx& c,const ColdCard& card,int64_t col,int64_t row,int facing){
    facing=facing>=0?1:-1;
    const auto& name=card.name;const bool lob=flag(card.lob);
    double x=(double(col)+.5)*c.tile,y=(double(row)+.5)*c.tile;
    if(lob){y=double(row)*c.tile;if(card.behavior=="mortar"){x+=facing*.28*c.tile;y+=.25*c.tile;}}
    else x+=facing*.3*c.tile;
    std::vector<int> directions{facing};if(name=="裂荚射手")directions.push_back(-facing);
    std::vector<double> offsets{0.};if(name=="三向射手")offsets={-c.tile,0.,c.tile};
    double reach=std::min(32*c.tile,card.range!=0.?card.range:12*c.tile);
    if(reach<32)reach*=c.tile;
    std::vector<FiringTarget> targets;
    for(const auto& u:targets_of(c)){
        const double w=wrap_delta(x,u.x,c.width);bool ahead=false;for(int d:directions)if(w*d>0)ahead=true;
        if(ahead&&std::abs(w)<=reach&&std::abs(u.y-y)<6*c.tile)targets.push_back(u);
    }
    stable_sort_by(targets,[&](const FiringTarget& u){return std::abs(wrap_delta(x,u.x,c.width));});
    for(const auto& target:targets){
        const double dx=wrap_delta(x,target.x,c.width);
        if(lob){
            const double ty=target.y-c.tile*(card.behavior=="mortar"?1.:.7);
            if(clear_arc(c,x,y,x+dx,ty,card,target.y,target.h!=0.?target.h:1.5*c.tile))return {true,"target",std::abs(dx)};
        }else{
            const double h=target.h!=0.?target.h:1.5*c.tile;
            for(double off:offsets){const double sy=y+off;if(target.y-h<=sy&&sy<=target.y&&clear_segment(c,x,sy,x+dx,sy))return {true,"target",std::abs(dx)};}
        }
    }
    if(!targets.empty())return {false,"unreachable_targets",0.};
    bool allowed=false;
    if(lob){for(int d:directions)if(clear_arc(c,x,y,x+d*std::min(reach,4*c.tile),y+.3*c.tile,card,y+c.tile,1.5*c.tile)){allowed=true;break;}}
    else for(int d:directions)for(double off:offsets)if(!allowed&&clear_segment(c,x,y+off,x+d*std::min(reach,3*c.tile),y+off))allowed=true;
    return {allowed,allowed?"open_corridor":"blocked_corridor",0.};
}
}
std::shared_ptr<const FiringSignature> geometry_signature(Ctx& c){
    auto& fc=cache(c);
    if(!fc.signature){
        auto s=std::make_shared<FiringSignature>();s->width=c.width;s->tile=c.tile;
        for(const auto& row:tiles_of(c)){std::vector<bool> r;for(const auto& cell:row)r.push_back(cell.solid);s->solid.push_back(std::move(r));}
        for(const auto& u:targets_of(c))s->targets.push_back({py::roundn(u.x,2),py::roundn(u.y,2),py::roundn(u.h!=0.?u.h:1.5*c.tile,2)});
        std::sort(s->targets.begin(),s->targets.end());
        fc.signature=s;
    }
    return fc.signature;
}
FiringAssessment firing_assessment(Ctx& c,const std::string& key,double x,double y,int facing){
    const auto& card=c.card(key);
    if(!ballistic(card))return {true,"own_mechanics",0.};
    if(tiles_of(c).empty())return {true,"unknown_terrain",0.};
    auto& fc=cache(c);
    const auto row=int64_t(std::floor(y/c.tile)),col=int64_t(std::floor(pmod(x,c.width)/c.tile));
    const auto k=std::make_tuple(key,row,col,facing>=0?1:-1);
    auto f=fc.memo.find(k);if(f!=fc.memo.end())return f->second;
    const auto r=check(c,card,col,row,facing);fc.memo.emplace(k,r);return r;
}
std::optional<int> firing_direction(Ctx& c,const std::string& key,double x,double y,int facing){
    facing=facing>=0?1:-1;
    const auto chosen=firing_assessment(c,key,x,y,facing);
    if(chosen.allowed&&chosen.reason!="open_corridor")return facing;
    const auto other=firing_assessment(c,key,x,y,-facing);
    if(other.allowed&&other.reason=="target"&&other.distance<=4*c.tile)return -facing;
    if(chosen.allowed)return facing;return std::nullopt;
}

// =========================================================== team_support66
namespace {
constexpr double START_HP=.70,ABORT_HP=.55,MAX_TRIP=20.,MAX_SECONDS=12.,COOLDOWN=8.,NEAR=3.,HOME_RADIUS=5.,MATE_RADIUS=7.,STANDOFF=4.;
double power(const Unit& u){
    if(card_producer(u)||one_of(u.behavior,{"pot","lily","grave"}))return 0.;
    const double maximum=std::max(1.,u.max_hp);
    return (card_cost(u,25.)+25)*std::max(.2,std::min(1.,u.hp/maximum));
}
}
SupportDecision TeamSupport::finish(Ctx& c,std::pair<double,double> home,const std::string& reason){
    if(active)cooldown_until=c.t+COOLDOWN;
    const bool returning=active||(last&&last->state=="return");
    active=false;quiet_since.reset();
    const std::string state=returning&&std::abs(wrap_delta(c.me.x,home.first,c.width))>c.tile?"return":"home";
    last=SupportDecision{state,reason,home.first,0.,{},0.,0.};
    return *last;
}
std::optional<SupportDecision> TeamSupport::decide(Ctx& c,std::pair<double,double> home){
    const auto& b=c.b;
    if(!b.mode||(*b.mode!="duo"&&*b.mode!="coop")){active=false;last.reset();return std::nullopt;}
    const std::string mate_key=c.side_name+"2";
    const Player* mate=b.player(mate_key);
    const std::string real=b.local_seat==std::optional<std::string>(mate_key)?c.side_name:mate_key;
    if(!mate||mate->absent)return finish(c,home,"no_mate");
    const bool fallen=std::find(b.fallen.begin(),b.fallen.end(),real)!=b.fallen.end();
    if(mate->hp<=0&&!fallen)return finish(c,home,"mate_unavailable");
    const double life=c.me.hp/std::max(1.,c.me.max_hp);
    if(life<(active?ABORT_HP:START_HP))return finish(c,home,"health");
    std::vector<const Unit*> dangerous;for(const auto* u:c.enemy)if(u->hp>0&&power(*u)!=0.)dangerous.push_back(u);
    for(const auto* u:dangerous)if(dist(c,c.me.x,c.me.y,u->x,u->y)<=NEAR*c.tile)return finish(c,home,"local_danger");
    for(const auto* u:dangerous)if(dist(c,home.first,home.second,u->x,u->y)<=HOME_RADIUS*c.tile)return finish(c,home,"home_danger");
    for(const auto& t:c.obs.threats)if(t.projectile&&t.eta_ms<700)return finish(c,home,"projectile");
    static const std::array<const char*,2> zombie_keys{"zombie","zombie2"},plant_keys{"plant","plant2"};
    for(const char* key:c.side==Seat::plant?zombie_keys:plant_keys){
        const Player* e=b.player(key);if(!e||e->absent||e->hp<=0)continue;
        if(dist(c,c.me.x,c.me.y,e->x,e->y)<5*c.tile||dist(c,home.first,home.second,e->x,e->y)<6*c.tile)return finish(c,home,"enemy_hero");
    }
    std::vector<double> combat;double support_cost=0;
    static const std::set<std::string> non_combat{"pot","lily","coffee","grave","produce","gold_bloom","lantern","support"};
    for(const auto& key:c.me.deck){
        if(key.rfind("secret:",0)==0||key.rfind("zsecret:",0)==0)continue;
        const auto& card=c.card(key);
        if(card.behavior=="pot"||card.behavior=="lily")support_cost=std::max(support_cost,card.cost);
        else if(!card.producer&&!non_combat.count(card.behavior)&&c.ready(key,0.))combat.push_back(card.cost);
    }
    if(combat.empty())return finish(c,home,"no_ready_response");
    const double response=std::max(25.,*std::min_element(combat.begin(),combat.end())+support_cost);
    const double reserve=std::max(75.,response*1.5);
    if(c.me.resource<reserve+response)return finish(c,home,"reserve");
    const std::string seat=b.local_seat.value_or(c.side_name);
    std::vector<const Unit*> own_home;
    for(const auto* u:c.own)if(u->seat.value_or(c.side_name)==seat&&dist(c,home.first,home.second,u->x,u->y)<=8*c.tile)own_home.push_back(u);
    double home_power=0;for(const auto* u:own_home)home_power+=power(*u);
    if(home_power<75.)return finish(c,home,"unguarded_home");
    bool econ=false;for(const auto* u:own_home)if(card_producer(*u))econ=true;
    if(!c.deathmatch&&!econ)return finish(c,home,"economy");
    if(dist(c,home.first,home.second,mate->x,mate->y)>MAX_TRIP*c.tile)return finish(c,home,"too_far");
    if(std::abs(mate->y-c.me.y)>6*c.tile)return finish(c,home,"vertical_route");
    double strength=0;for(const auto* u:dangerous)if(dist(c,mate->x,mate->y,u->x,u->y)<=MATE_RADIUS*c.tile)strength+=power(*u);
    double allied=0;for(const auto* u:c.own)if(dist(c,mate->x,mate->y,u->x,u->y)<6*c.tile)allied+=power(*u);
    const bool needs_help=fallen||(strength>=75&&(strength>allied*.8||mate->hp<.65*mate->max_hp));
    if(!needs_help){
        if(active){if(!quiet_since)quiet_since=c.t;if(c.t-*quiet_since<2.)return last;}
        return finish(c,home,"cleared");
    }
    quiet_since.reset();
    if(strength>allied+2.5*(c.me.resource-reserve))return finish(c,home,"overwhelming");
    if(fallen){for(const auto* u:dangerous)if(dist(c,mate->x,mate->y,u->x,u->y)<4*c.tile)return finish(c,home,"body_guarded");}
    const int direction=wrap_delta(mate->x,home.first,c.width)>=0?1:-1;
    const double post=fallen?mate->x:pmod(mate->x+direction*STANDOFF*c.tile,c.width);
    const double delta=wrap_delta(c.me.x,post,c.width);
    for(const auto* u:dangerous){
        const double dx=wrap_delta(c.me.x,u->x,c.width);
        if(std::min(0.,delta)-c.tile<=dx&&dx<=std::max(0.,delta)+c.tile&&std::abs(u->y-c.me.y)<3*c.tile)return finish(c,home,"route");
    }
    if(active&&c.t>=until)return finish(c,home,"time_limit");
    if(!active){
        if(c.t<cooldown_until)return finish(c,home,"cooldown");
        active=true;until=c.t+MAX_SECONDS;
    }
    last=SupportDecision{fallen?"rescue":"assist","mate_pressure",post,reserve,real,mate->x,mate->y};
    return last;
}

// ================================================================== Plant14
std::vector<const Unit*> Plant14::invaders(Ctx& c){
    std::vector<const Unit*> out;const auto sb_1=*anchor;const auto ax=std::get<0>(sb_1);const auto ay=std::get<1>(sb_1);
    for(const auto* u:c.enemy){
        if(!u->mobile||u->hp<=0)continue;
        for(const auto& [px,py]:{std::pair<double,double>{c.me.x,c.me.y},std::pair<double,double>{ax,ay}})
            if(std::abs(wrap_delta(px,u->x,c.width))<=7*c.tile&&std::abs(u->y-py)<=3*c.tile){out.push_back(u);break;}
    }
    return out;
}
int Plant14::invasion_dir(Ctx& c,const std::vector<const Unit*>& inv){
    double w1=0,wm=0;
    for(const auto* u:inv){const double d=wrap_delta(anchor->first,u->x,c.width);(psgn(d)==1?w1:wm)+=(card_cost(*u,25.)+25)/(40.+std::abs(d));}
    return wm>w1?-1:1;   // dict order 1, -1: first max
}
int Plant14::facing_for(Ctx& c,double x){
    const Unit* best=nullptr;double bd=0;
    for(const auto* u:c.enemy)if(u->mobile&&std::abs(wrap_delta(x,u->x,c.width))<8*c.tile&&std::abs(u->y-anchor->second)<3*c.tile){
        const double d=std::abs(wrap_delta(x,u->x,c.width));if(!best||d<bd){best=u;bd=d;}
    }
    if(best)return psgn(wrap_delta(x,best->x,c.width));
    return Plant11::facing_for(c,x);
}
void Plant14::deploy_logic(Ctx& c,const PlanDict& plan){
    const auto inv=invaders(c);
    if(!inv.empty()&&mode!="siege"&&repel(c,plan,inv))return;
    const auto gate=economy_gate(c,plan,inv);
    if(!gate){Plant11::deploy_logic(c,plan);return;}
    auto ready=c.ready;const std::string g=*gate;
    c.ready=[this,&c,ready,g](const std::string& key,double reserve){
        const auto& card=c.card(key);
        if(one_of(card.behavior,{"pot","lily","coffee","gold_bloom"})||card.category=="tool")return ready(key,reserve);
        if(card.producer||(fire_role(role(c,key))&&g=="guns"))return ready(key,reserve);
        const auto r=role(c,key);if(r=="instant"||r=="freeze")return ready(key,reserve);
        return false;
    };
    log["econ_gate"]+=1;
    struct Restore{Ctx& c;std::function<bool(const std::string&,double)> r;~Restore(){c.ready=r;}} restore{c,ready};
    Plant11::deploy_logic(c,plan);
}
std::optional<std::string> Plant14::economy_gate(Ctx& c,const PlanDict& plan,const std::vector<const Unit*>& inv){
    if(c.deathmatch||mode=="siege"||!inv.empty()||pressure(c)>plan.num("rush_pressure",175))return std::nullopt;
    bool any=false;for(const auto& k:deck(c))if(c.card(k).producer)any=true;
    if(!any)return std::nullopt;
    double producers=0;for(const auto* u:c.own)if(card_producer(*u))++producers;
    const double goal=std::min(plan.num("econ_goal",4),c.t<90?plan.num("opening_econ",4):99.);
    if(producers>=goal)return std::nullopt;
    double fire=0;for(const auto* u:c.own)if(fire_role(role(c,u->card_id)))++fire;
    return std::string(fire<2?"guns":"econ");
}
bool Plant14::repel(Ctx& c,const PlanDict& plan,const std::vector<const Unit*>& inv){
    const int side=invasion_dir(c,inv);const int saved=front;front=side;
    struct Restore{int& f;int v;~Restore(){f=v;}} restore{front,saved};
    log["invasion"]+=1;
    std::map<std::string,std::vector<std::string>> by_role;for(const auto& k:deck(c))by_role[role(c,k)].push_back(k);
    if(emergency(c,by_role,plan))return true;
    double value=0;for(const auto* u:inv)value+=card_cost(*u,25.);
    const std::vector<std::string> order=value<300?std::vector<std::string>{"shoot","lob","wall"}:std::vector<std::string>{"wall","shoot","lob"};
    for(const auto& r:order)for(const auto& k:rank_cards(c,role_get(by_role,r),r))if(c.ready(k,0.)&&place(c,k,r,plan)){log["repel:"+r]+=1;return true;}
    return false;
}
bool Plant14::place(Ctx& c,const std::string& key,const std::string& r,const PlanDict& plan){
    if(r=="support"&&!support_allowed(c,key,plan))return false;
    return Plant11::place(c,key,r,plan);
}
bool Plant14::support_allowed(Ctx& c,const std::string& key,const PlanDict& plan){
    int64_t fire=0;for(const auto* u:c.own)if(fire_role(role(c,u->card_id)))++fire;
    double mine=0;for(const auto* u:c.own)if(u->card_id==key&&u->hp>0)++mine;
    const double cap=std::min(plan.num("support_max",3),double(1+fire/3));
    if(mine>=cap){log["_support_cap"]+=1;return false;}
    double producers=0;for(const auto* u:c.own)if(card_producer(*u))++producers;
    if(producers<std::min(plan.num("econ_goal",4),4.)&&pressure(c)<150)return false;
    return true;
}
bool Plant14::place_(Ctx& c,const std::string& key,const std::string& r,const PlanDict& plan,double ax,double ay,double h){
    if(place_air(c,key,plan,ax,ay,h))return true;
    if(r=="support")return place_support(c,key,plan,ax,ay,h);
    if(r=="shoot"&&c.has_secret("secret:密植")&&place_dense(c,key,plan,ax,ay,h))return true;
    return Plant11::place_(c,key,r,plan,ax,ay,h);
}
bool Plant14::place_support(Ctx& c,const std::string& key,const PlanDict&,double,double ay,double h){
    std::vector<const Unit*> others;for(const auto* u:c.own)if(u->card_id==key&&u->hp>0)others.push_back(u);
    std::vector<Spot> spots;
    for(const auto& p:c.spots(true)){
        if(along(c,p.x)>h)continue;
        bool close=false;for(const auto* u:others)if(std::abs(wrap_delta(p.x,u->x,c.width))<3.*c.tile&&std::abs(p.y-u->y)<2*c.tile)close=true;
        if(!close)spots.push_back(p);
    }
    std::vector<const Unit*> guns;for(const auto* u:c.own)if(fire_role(role(c,u->card_id)))guns.push_back(u);
    stable_sort_by(spots,[&](const Spot& p){
        double cover=0;for(const auto* g:guns)if(std::abs(wrap_delta(p.x,g->x,c.width))<3*c.tile&&std::abs(p.y-g->y)<2*c.tile)++cover;
        return -cover*3+std::abs(along(c,p.x)-(h-2))+std::abs(p.y-ay)/c.tile;
    });
    for(size_t i=0;i<spots.size()&&i<4;++i)if(place_at(c,key,spots[i].x,spots[i].y,facing_for(c,spots[i].x)).empty()){log["support"]+=1;return true;}
    return false;
}
bool Plant14::place_dense(Ctx& c,const std::string& key,const PlanDict&,double,double,double h){
    std::vector<std::pair<std::pair<int64_t,int64_t>,std::vector<const Unit*>>> cells;   // dict, insertion order
    for(const auto* u:c.own){
        if(!fire_role(role(c,u->card_id))||u->mobile)continue;
        const double a=along(c,u->x);if(!(-2<=a&&a<=h))continue;
        const std::pair<int64_t,int64_t> k{int64_t(std::floor(pmod(u->x,c.width)/c.tile)),int64_t(std::floor(u->y/c.tile))};
        bool found=false;for(auto& [ck,v]:cells)if(ck==k){v.push_back(u);found=true;}
        if(!found)cells.push_back({k,{u}});
    }
    std::map<std::pair<int64_t,int64_t>,std::pair<double,double>> free;
    for(const auto& s:c.spots(true))free[{int64_t(std::floor(pmod(s.x,c.width)/c.tile)),int64_t(std::floor((s.y+2)/c.tile))}]={s.x,s.y};
    struct Best{double neg;double off;std::pair<double,double> spot;};std::optional<Best> best;
    for(const auto& [cell,units]:cells){
        if(units.size()>=3)continue;
        auto f=free.find(cell);if(f==free.end())f=free.find({cell.first,cell.second+1});
        if(f==free.end())continue;
        const Best k{-double(units.size()),std::abs(along(c,f->second.first)-(h-2)),f->second};
        if(!best||std::tie(k.neg,k.off)<std::tie(best->neg,best->off))best=k;
    }
    if(!best)return false;
    const auto sb_2=best->spot;const auto x=std::get<0>(sb_2);const auto y=std::get<1>(sb_2);
    if(place_at(c,key,x,y,facing_for(c,x)).empty()){log["dense_stack"]+=1;return true;}
    return false;
}
bool Plant14::place_air(Ctx& c,const std::string& key,const PlanDict&,double,double,double h){
    const auto& card=c.card(key);
    std::string name=card.name;if(name.empty()){const auto a=key.find(':');const auto b2=key.find(':',a+1);name=key.substr(a+1,b2==std::string::npos?std::string::npos:b2-a-1);}
    std::string kind;
    if(name=="幽灵辣椒"||card.behavior=="ghost")return false;
    if(name=="旋转芜菁")kind="turnip";else if(name=="芦笋战机")kind="asparagus";else if(name=="海蘑菇"&&flag(card.allow_air))kind="sea";else return false;
    const auto& tiles=tiles_of(c);if(tiles.empty())return false;
    {auto f=air_retry.find(key);if((f==air_retry.end()?-1.:f->second)>c.t)return false;}
    const auto cols=int64_t(tiles[0].size());
    // threat_points
    std::vector<std::array<double,3>> points;
    for(const auto* u:c.enemy)if(u->mobile||u->flying)points.push_back({u->x,u->y-c.tile*.6,1.});
    if(c.foe.hp>0)points.push_back({c.foe.x,c.foe.y-c.tile,1.5});
    std::vector<Spot> lane;for(const auto& p:c.spots(false)){const double a=along(c,p.x);if(h-1<=a&&a<=h+8)lane.push_back(p);}
    for(size_t i=0;i<lane.size()&&i<24;++i)points.push_back({lane[i].x,lane[i].y-c.tile*.6,.4});
    if(points.empty())return false;
    std::set<std::pair<int64_t,int64_t>> occupied;
    for(const auto* group:{&c.own,&c.enemy})for(const auto* u:*group)if(!u->mobile)
        occupied.insert({int64_t(pmod(std::floor(u->x/c.tile),double(cols))),int64_t(std::floor((u->y-c.tile*.5)/c.tile))});
    const auto hero_col=int64_t(std::floor(c.me.x/c.tile)),hero_row=int64_t(std::floor(c.me.y/c.tile));
    const int max_height=kind=="turnip"?6:kind=="asparagus"?5:0;
    const auto clear_line=[&](double x0,double y0,double x1,double y1){
        const double dx=wrap_delta(x0,x1,c.width),dy=y1-y0;
        const int64_t steps=std::max<int64_t>(1,int64_t(std::hypot(dx,dy)/(c.tile*.25)));
        for(int64_t i=1;i<steps;++i){
            const double x=pmod(x0+dx*double(i)/double(steps),c.width),y=y0+dy*double(i)/double(steps);
            if(solid_at(c,int64_t(std::floor(x/c.tile)),int64_t(std::floor(y/c.tile)),cols))return false;
        }
        return true;
    };
    struct Cand{double s,x,y;int facing;};std::vector<Cand> cand;
    for(int64_t drow=-7;drow<2;++drow)for(int64_t dcol=-9;dcol<10;++dcol){
        const auto col=int64_t(pmod(double(hero_col+dcol),double(cols))),row=hero_row+drow;
        if(solid_at(c,col,row,cols)||occupied.count({col,row}))continue;
        const double x=(double(col)+.5)*c.tile,y=(double(row)+.5)*c.tile;
        const double a=along(c,x);if(!(-6<=a&&a<=h+1))continue;
        int height=9;for(int hh=0;hh<9;++hh)if(solid_at(c,col,row+1+hh,cols)){height=hh;break;}
        if(height>max_height)continue;
        double sum=0;for(const auto& p:points)sum+=wrap_delta(x,p[0],c.width)*p[2];
        const int facing=sum>=0?1:-1;
        double total=0.;
        for(const auto& [px,py,w]:points){
            const double dx=wrap_delta(x,px,c.width),dy=py-y;const double d=std::hypot(dx,dy)/c.tile;
            if(kind=="turnip"){if(d>12.||std::abs(std::abs(dx)-std::abs(dy))>c.tile*.6)continue;}
            else if(kind=="asparagus"){
                if(d>16.||dx*facing<=0)continue;
                const double angle=std::atan2(std::abs(dy),std::abs(dx))/(3.141592653589793/180.);if(angle>40.)continue;
            }else if(std::abs(dy)>c.tile*.6||std::abs(dx)>4.*c.tile)continue;
            if(clear_line(x,y,px,py))total+=w*(kind!="asparagus"?1.:1.+.02*(16.-d));
        }
        double s=total;if(s<=0)continue;
        s+=kind!="sea"?.3*std::min(3,height):0.;
        cand.push_back({s,x,y,facing});
    }
    stable_sort_by(cand,[](const Cand& k){return -k.s;});
    for(size_t i=0;i<cand.size()&&i<4;++i)if(deploy_(c,key,cand[i].x,cand[i].y,{},cand[i].facing).empty()){log["air:"+kind]+=1;return true;}
    log["air_none:"+kind]+=1;
    air_retry[key]=c.t+2.;
    return false;
}
void Plant14::tools(Ctx& c,const PlanDict& plan){
    if(c.has_secret("secret:转向"))turn_guns(c);
    const bool saved=c.hide_turn_secret;c.hide_turn_secret=true;
    struct Restore{Ctx& c;bool v;~Restore(){c.hide_turn_secret=v;}} restore{c,saved};
    Plant11::tools(c,plan);
}
void Plant14::turn_guns(Ctx& c){
    if(c.t<turn_at.value_or(0.))return;
    turn_at=c.t+.2;
    std::vector<const Unit*> enemies;for(const auto* u:c.enemy)if(u->mobile||u->behavior=="grave")enemies.push_back(u);
    for(const auto* unit:c.own){
        if(!one_of(card_behavior(*unit),{"shoot","reed61","flying56","mortar"}))continue;
        if(!in_view(c.me.x,c.me.y,unit->x,unit->y,c.width))continue;
        double wm=0,w1=0;
        for(const auto* u:enemies){
            const double d=wrap_delta(unit->x,u->x,c.width);
            if(std::abs(d)>600||std::abs(unit->y-u->y)>250)continue;
            const double w=(50+card_cost(*u,25.))/(60+std::abs(d));
            (psgn(d)==1?w1:wm)+=w*(u->mobile?1.:.3);
        }
        if(wm==0&&w1==0)continue;
        const double old=unit->facing;const int nw=w1>wm?1:-1;
        const double old_w=old==1.?w1:old==-1.?wm:0.;
        if(double(nw)!=old&&(nw==1?w1:wm)>old_w*1.3+.1){
            if(send_("turn",{{"target",unit->id},{"facing",double(nw)}}).empty()){log["turn"]+=1;return;}
        }
    }
}
int Plant14::route_dir(Ctx& c,double frm,double bx){
    const int choice0=Plant11::route_dir(c,frm,bx);int choice=choice0;
    if(last_siege_dir&&choice==*last_siege_dir){
        const int last=*last_siege_dir,other=-last;
        const double long_way=pmod((bx-frm)*other,c.width),way=pmod((bx-frm)*last,c.width);
        if(long_way<=way*1.35+4*c.tile){choice=other;log["siege_flip"]+=1;}
    }
    return choice;
}
void Plant14::step(const View& v,const typed72::AiObservation& o,const PlanDict& plan,const Field& f,Services& s){
    const auto before=siege_dir;
    Plant11::step(v,o,plan,f,s);
    if(before&&!siege_dir)last_siege_dir=*before;
}

// ================================================================== Plant15
void Plant15::deploy_logic(Ctx& c,const PlanDict& plan){
    if(c.me.resource>=plan.num("overflow",700)&&invaders(c).empty()){
        if(spend_overflow(c,plan)){idle_bank.reset();return;}
        reroute_if_stuck(c,plan);
    }else idle_bank.reset();
    Plant14::deploy_logic(c,plan);
}
void Plant15::reroute_if_stuck(Ctx& c,const PlanDict& plan){
    if(!idle_bank){idle_bank=c.t;return;}
    if(c.t-*idle_bank<8||mode!="siege"||!siege_anchor)return;
    const auto target=far_anchor(c,plan);
    idle_bank=c.t;
    if(!target){log["overflow_no_route"]+=1;return;}
    siege_dir=target->first;last_siege_dir=target->first;
    siege_anchor=anchor=target->second;
    checkpoint_started=c.t;platform.reset();
    log["overflow_reroute"]+=1;
}
std::optional<std::pair<int,std::pair<double,double>>> Plant15::far_anchor(Ctx& c,const PlanDict&){
    const auto sb_3=enemy_base(c);const auto bx=std::get<0>(sb_3);const auto by=std::get<1>(sb_3);(void)by;
    const auto cur=siege_anchor?*siege_anchor:*anchor;
    struct Best{double score;int d;std::pair<double,double> p;};std::optional<Best> best;
    const int sd=siege_dir&&*siege_dir?*siege_dir:1;
    for(int d:{sd,-sd}){
        for(const auto& bucket:c.field.spots)for(const auto& s:bucket){
            const double progress=d*wrap_delta(cur.first,s.x,c.width);
            if(s.water||!(6*c.tile<=progress&&progress<=14*c.tile))continue;
            bool tried=false;for(const auto& [tx,ty]:tried_anchors)if(std::abs(wrap_delta(s.x,tx,c.width))<2*c.tile&&std::abs(s.y-ty)<2*c.tile)tried=true;
            if(tried)continue;
            if(!landing(c,s.x,s.y+2,false))continue;
            const double left=pmod((bx-s.x)*d,c.width);
            const double score=left/c.tile+risk(c,s.x,s.y+2)*.3+std::abs(s.y-cur.second)/c.tile*.5;
            if(!best||score<best->score)best=Best{score,d,{s.x,s.y}};
        }
        if(best)break;
    }
    if(!best)return std::nullopt;
    tried_anchors.push_back(best->p);if(tried_anchors.size()>6)tried_anchors.erase(tried_anchors.begin(),tried_anchors.end()-6);
    return std::pair<int,std::pair<double,double>>{best->d,best->p};
}
bool Plant15::spend_overflow(Ctx& c,const PlanDict&){
    std::vector<std::string> keys;
    for(const auto& k:deck(c)){const auto& cd=c.card(k);if(!cd.producer&&(fire_role(role(c,k))||one_of(cd.behavior,{"shoot","lob","flying56","mortar","reed61","spike"})))keys.push_back(k);}
    std::vector<std::string> ready;for(const auto& k:keys)if(c.ready(k,0.))ready.push_back(k);keys=ready;
    if(keys.empty())return false;
    stable_sort_by(keys,[&](const std::string& k){return -c.card(k).cost;});
    const int fr=front?front:1;
    auto spots=c.spots(true);
    stable_sort_by(spots,[&](const Spot& p){return -fr*wrap_delta(c.me.x,p.x,c.width)/c.tile+std::abs(p.y-c.me.y)/c.tile*.5;});
    for(size_t ki=0;ki<keys.size()&&ki<3;++ki){
        const auto& key=keys[ki];const auto& card=c.card(key);
        for(size_t i=0;i<spots.size()&&i<10;++i){
            if(spots[i].water&&!flag(card.aquatic))continue;
            const int facing=facing_for(c,spots[i].x);
            if(place_at(c,key,spots[i].x,spots[i].y,facing).empty()){log["overflow:"+role(c,key)]+=1;return true;}
        }
    }
    return false;
}

// ================================================================== Plant18
std::string Plant18::place_at(Ctx& c,const std::string& key,double x,double y,int facing){
    const auto err=Plant17::place_at(c,key,x,y,facing);
    if(!err.empty()&&err.find("此处不符合原版种植条件")!=std::string::npos&&!one_of(c.card(key).behavior,{"pot","lily"})){
        if(c.me.in_deck("plant:花盆")&&c.ready("plant:花盆",0.)){
            if(deploy_(c,"plant:花盆",x,y,{},facing).empty()){log["pot_for_native_rule"]+=1;return "";}
        }
    }
    return err;
}
void Plant18::step(const View& v,const typed72::AiObservation& o,const PlanDict& plan,const Field& f,Services& s){
    snap_=v.mode&&one_of(*v.mode,{"coop","pve","duo"})?&v:nullptr;
    if(v.mode&&one_of(*v.mode,{"coop","pve"})){
        log["_mark_at"]=v.time+1.;
        PlanDict p=plan;p.set("mode",std::string("defend"));p.set("anchor_timeout",std::max(25.,plan.num("anchor_timeout",8.)));
        if(!front_set){front_set=true;pick_front(v,o,p,f,s);}
        Plant17::step(v,o,p,f,s);return;
    }
    Plant17::step(v,o,plan,f,s);
}
void Plant18::pick_front(const View& v,const typed72::AiObservation& o,const PlanDict& plan,const Field& f,Services& s){
    Ctx c(Seat::plant,v,o,f,s);
    const Player* mate=v.player("plant2");if(mate&&mate->absent)mate=nullptr;
    const auto& points=v.zombie_points;const double me_x=c.me.x;
    int direction;
    if(!points.empty()){
        auto mine=points;stable_sort_by(mine,[&](double x){return std::abs(wrap_delta(me_x,x,c.width));});
        std::optional<double> theirs;
        if(mate){double best=points[0];double bd=std::abs(wrap_delta(mate->x,best,c.width));for(double x:points){const double d=std::abs(wrap_delta(mate->x,x,c.width));if(d<bd){bd=d;best=x;}}theirs=best;}
        double target=mine[0];
        for(double x:mine)if(!theirs||points.size()==1||x!=*theirs){target=x;break;}
        direction=psgn(wrap_delta(me_x,target,c.width));
    }else if(mate)direction=-psgn(wrap_delta(me_x,mate->x,c.width));
    else return;
    const double around=pmod(me_x+direction*8.*c.tile,c.width);
    std::optional<std::pair<double,double>> a;
    try{a=find_platform(c,plan,around);}catch(const std::exception&){a.reset();}
    if(a){anchor=home_anchor=*a;siege_anchor.reset();log["coop_front"]+=1;}
}
int Plant18::drive(Ctx& c,double post,bool jump_wish,double tolerance){
    if(snap_)post=rescue_post(c,*snap_,post);
    return Plant17::drive(c,post,jump_wish,tolerance);
}
double Plant18::rescue_post(Ctx& c,const View& b,double post){
    const Player* mate=b.player("plant2");if(!mate||mate->absent)return post;
    const std::string real=b.local_seat==std::optional<std::string>("plant2")?"plant":"plant2";
    if(std::find(b.fallen.begin(),b.fallen.end(),real)==b.fallen.end())return post;
    if(c.me.hp<.4*std::max(1.,c.me.max_hp))return post;
    for(const auto* u:c.enemy)if(u->mobile&&std::abs(wrap_delta(mate->x,u->x,c.width))<3*c.tile&&std::abs(u->y-mate->y)<3*c.tile){log["coop_rescue_wait"]+=1;return post;}
    log["coop_rescue"]+=1;
    return mate->x;
}

// ================================================================= Zombie14
void Zombie14::deploy_logic(Ctx& c,const PlanDict& in,const std::vector<const Unit*>& graves,double foe_home_d){
    PlanDict plan=in;
    // anti_air_plan
    const auto& tiles=c.b.tiles;std::vector<const Unit*> air;
    const auto cols=tiles.empty()?int64_t(1):int64_t(tiles[0].size());
    for(const auto* u:c.living){
        if(u->side==c.side||u->hp<=0||!u->card||u->card->side!="plant")continue;
        if(u->card->name=="幽灵辣椒"||u->card->behavior=="ghost")continue;
        const auto col=int64_t(pmod(std::floor(u->x/c.tile),double(cols))),row=int64_t(std::floor((u->y-c.tile*.5)/c.tile));
        const auto below=row+1;
        const bool grounded=below>=0&&below<int64_t(tiles.size())&&(tiles[size_t(below)][size_t(col)].solid||tiles[size_t(below)][size_t(col)].water);
        if(u->card->behavior=="flying56"||(flag(u->card->allow_air)&&!grounded))air.push_back(u);
    }
    if(!air.empty()){
        static const std::set<std::string> flyers{"zombie:乌鸦","zombie:海盗鹦鹉","zombie:飞贼僵尸"},climbers{"zombie:梯子僵尸","zombie:传送带僵尸"};
        const auto* priority=plan.list("priority");
        std::vector<std::string> counter;
        for(const auto& k:c.me.deck){
            if(k.rfind("secret:",0)==0||k.rfind("zsecret:",0)==0)continue;
            const auto& cd=c.card(k);
            if(!(flyers.count(k)||climbers.count(k)||cd.behavior=="shoot"||cd.behavior=="lob"))continue;
            const auto& pool=priority?*priority:c.me.deck;
            if(std::find(pool.begin(),pool.end(),k)!=pool.end())counter.push_back(k);
        }
        if(!counter.empty()){
            std::vector<std::string> next=counter;
            if(priority)for(const auto& k:*priority)if(std::find(counter.begin(),counter.end(),k)==counter.end())next.push_back(k);
            plan.set("priority",next);
        }
        log["antiair_ticks"]+=1;
        // rally_under
        bool has_climber=false;for(const auto& k:c.me.deck)if(climbers.count(k))has_climber=true;
        if(has_climber){
            double crowd=0;for(const auto* u:c.own)if(u->mobile)++crowd;
            if(!(crowd<4||c.t<antiair_rally_at.value_or(-1.))){
                const Unit* target=nullptr;
                for(const auto* u:air)if(!target||std::make_tuple(std::abs(wrap_delta(c.me.x,u->x,c.width)),u->id)<std::make_tuple(std::abs(wrap_delta(c.me.x,target->x,c.width)),target->id))target=u;
                antiair_rally_at=c.t+15.;
                if(send_("rally",{{"x",target->x},{"y",target->y-c.tile*.5}}).empty())log["antiair_rally"]+=1;
            }
        }
    }
    Zombie11::deploy_logic(c,plan,graves,foe_home_d);
}
void Zombie14::command_logic(Ctx& c,const PlanDict& plan,double foe_home_d,int foe_dir){
    const bool flank=releases%2==1&&plan.flag("flank",true)&&!c.deathmatch;
    if(!flank){Zombie11::command_logic(c,plan,foe_home_d,foe_dir);return;}
    auto prev=send;
    send=[this,&c,prev,foe_dir](const std::string& kind,const Args& data){
        bool has_x=false;for(const auto& [k,v]:data)if(k=="x")has_x=true;
        if(kind=="rally"&&has_x){
            if(const auto point=flank_point(c,foe_dir)){
                Args d=data;for(auto& [k,v]:d){if(k=="x")v=point->first;if(k=="y")v=point->second;}
                log["flank_rally"]+=1;return prev(kind,d);
            }
        }
        return prev(kind,data);
    };
    struct Restore{Controller& s;decltype(prev) p;~Restore(){s.send=p;}} restore{*this,prev};
    Zombie11::command_logic(c,plan,foe_home_d,foe_dir);
}
std::optional<std::pair<double,double>> Zombie14::flank_point(Ctx& c,int foe_dir){
    const auto& tiles=c.b.tiles;const auto cols=int64_t(tiles[0].size());
    const double home_x=home->first;
    const double shrt=std::abs(wrap_delta(home_x,c.foe.x,c.width));const double long_way=c.width-shrt;
    if(long_way<14*c.tile)return std::nullopt;
    const double x=pmod(home_x-foe_dir*long_way*.62,c.width);
    const auto col=int64_t(pmod(std::floor(x/c.tile),double(cols)));
    struct Best{double a,b;std::pair<double,double> p;};std::optional<Best> best;
    for(int dc:{0,1,-1,2,-2,3,-3}){
        const auto cc=int64_t(pmod(double(col+dc),double(cols)));
        for(size_t row=2;row<tiles.size();++row){
            const auto& cell=tiles[row][size_t(cc)];const auto& above=tiles[row-1][size_t(cc)];
            if(cell.solid&&!above.solid&&!tiles[row-2][size_t(cc)].solid&&!above.water){
                const Best k{std::abs(double(row)*c.tile-home->second),double(std::abs(dc)),{(double(cc)+.5)*c.tile,(double(row)-.5)*c.tile}};
                if(!best||std::tie(k.a,k.b)<std::tie(best->a,best->b))best=k;
            }
        }
    }
    if(!best)return std::nullopt;return best->p;
}

// ============================================================ SecretExecutor
bool SecretExecutor::due(const std::string& key,double t,double every){
    auto f=ready.find(key);if(t<(f==ready.end()?-1.:f->second))return false;ready[key]=t+every;return true;
}
void SecretExecutor::count(const std::string& key){for(auto& [k,v]:log)if(k==key){v+=1;return;}log.emplace_back(key,1.);}
void SecretExecutor::run(const std::function<std::string(const std::string&,const Args&)>& send,Ctx& c){
    const auto& b=c.b;const Player* mep=b.player(c.side_name);
    std::set<std::string> secrets;if(mep)for(const auto& s:mep->secrets)secrets.insert(s);
    bool any=false;for(const auto& s:secrets)if(s.rfind("zsecret:",0)==0)any=true;
    if(c.side!=Seat::zombie||!any||!mep||mep->hp<=0)return;
    const auto& me=*mep;const double t=b.time,tile=b.tile;
    const std::string seat=b.local_seat.value_or(c.side_name);
    const auto& units=b.units;
    if(secrets.count("zsecret:自爆")&&due("blast",t,.5)){
        struct Best{double hits,hp;const Unit* u;};std::optional<Best> best;
        for(const auto& u:units){
            if(u.side!=c.side||!u.mobile||u.hp<=0)continue;
            if(u.seat.value_or(seat)!=seat)continue;
            const double cx=u.x,cy=u.y-tile*.5;
            double hits=0;
            for(const auto& o:units)if(o.side!=c.side&&o.hp>0&&dist(c,cx,cy,o.x,o.y-tile*.5)<=2.4*tile)++hits;
            for(const char* key:{"plant","plant2"}){const Player* foe=b.player(key);if(foe&&!foe->absent&&foe->hp>0&&dist(c,cx,cy,foe->x,foe->y-tile)<=2.4*tile)hits+=2;}
            const double blast=std::ceil(u.hp/25.);
            if(((hits>=2&&blast>=3)||hits>=3)&&(!best||std::tie(hits,u.hp)>std::tie(best->hits,best->hp)))best=Best{hits,u.hp,&u};
        }
        if(best&&send("detonate",{{"target",best->u->id}}).empty()){ready["blast"]=t+2.;count("blast");}
    }
    if(secrets.count("zsecret:起床！")&&me.teleport_ready_at.value_or(0.)<=t&&due("wake",t,1.)){
        bool safe=me.hp>=.6*std::max(1.,me.max_hp);
        if(safe)for(const auto& o:units){
            if(!(o.mobile||(o.card&&o.card->side=="plant")))continue;
            if(o.side!=c.side&&o.hp>0&&dist(c,me.x,me.y,o.x,o.y)<4*tile){safe=false;break;}
        }
        std::vector<const Unit*> graves;for(const auto& u:units)if(u.side==c.side&&u.behavior=="grave"&&u.hp>0)graves.push_back(&u);
        if(safe&&!graves.empty()){
            const auto score=[&](const Unit* g){double n=0;for(const auto* o:graves)if(o->drowsy&&dist(c,g->x,g->y,o->x,o->y)<=2.4*tile)++n;return n;};
            const Unit* target=graves[0];
            for(const auto* g:graves)if(std::make_tuple(score(g),g->id)>std::make_tuple(score(target),target->id))target=g;
            if(score(target)>=2&&send("teleport",{{"target",target->id}}).empty()){ready["wake"]=t+20.;count("wake");}
        }
    }
    if(secrets.count("zsecret:解除封印")&&due("shield",t,1.)){
        std::vector<const Unit*> graves;for(const auto& u:units)if(u.side==c.side&&u.behavior=="grave"&&u.hp>0)graves.push_back(&u);
        if(!graves.empty()){
            const auto pressure=[&](const Unit* g){
                double near=0;for(const auto& o:units)if(o.side!=c.side&&o.hp>0&&dist(c,g->x,g->y,o.x,o.y)<=4*tile)++near;
                return std::make_tuple(near,-g->hp/std::max(1.,g->max_hp),g->id);
            };
            const Unit* target=graves[0];for(const auto* g:graves)if(pressure(g)>pressure(target))target=g;
            if(std::get<0>(pressure(target))!=0.&&me.selected_grave!=std::optional<std::string>(target->id))
                if(send("select_grave",{{"grave",target->id}}).empty())count("shield");
        }
    }
    if(std::find(b.last_stand.begin(),b.last_stand.end(),seat)!=b.last_stand.end()&&b.command=="follow"&&due("stand",t,1.))
        if(send("command",{}).empty())count("last_stand_attack");
}
void Zombie17::step(const View& v,const typed72::AiObservation& o,const PlanDict& plan,const Field& f,Services& s){
    Zombie15::step(v,o,plan,f,s);
    if(send){
        Ctx c(Seat::zombie,v,o,f,s);
        secrets.run(send,c);
        for(const auto& [k,n]:secrets.log)log["zsecret:"+k]=n;
    }
}

// ================================================================= Zombie18
namespace { const std::map<std::string,double> HEAD_VALUE{{"铁桶",3},{"黑铁桶",3},{"橄榄球头盔",3},{"黑橄榄球头盔",3},{"路障",2},{"黑路障",2}};
const std::vector<std::string> ARMOURLESS{"zombie:普通僵尸","zombie:黑普通僵尸","zombie:鸭子普通僵尸","zombie:伴舞僵尸","zombie:小鬼僵尸"}; }
void Zombie18::deploy_logic(Ctx& c,const PlanDict& plan,const std::vector<const Unit*>& graves,double foe_home_d){
    if(c.has_secret("zsecret:遗骸")&&relic_deploy(c,plan,graves))return;
    if(c.has_secret("zsecret:二手")&&secondhand_deploy(c,plan,graves))return;
    // PvP73 (待办 A2): 解除封印 makes every grave an exit, as rv_tactics18 intends by patching
    // ztactics61.in_view to True around the inherited deployment (the generated V code bound it
    // statically, so the shipped 72 AI ignored the secret).
    struct Restore{bool& flag;bool old;~Restore(){flag=old;}} restore{unrestricted_exits,unrestricted_exits};
    if(c.has_secret("zsecret:解除封印"))unrestricted_exits=true;
    Zombie17::deploy_logic(c,plan,graves,foe_home_d);
}
std::vector<std::string> Zombie18::walkers(Ctx& c,const PlanDict& plan,const std::vector<std::string>* keys){
    std::vector<std::string> units;
    for(const auto& k:c.me.deck){
        if(k.rfind("secret:",0)==0||k.rfind("zsecret:",0)==0)continue;
        if(c.card(k).behavior=="grave")continue;
        if(keys&&std::find(keys->begin(),keys->end(),k)==keys->end())continue;
        units.push_back(k);
    }
    return unit_order(c,units,plan);
}
bool Zombie18::relic_deploy(Ctx& c,const PlanDict& plan,const std::vector<const Unit*>& graves){
    std::vector<const Unit*> relics;for(const auto* g:graves)if(g->hp>0&&g->hp<=std::max(1.,g->max_hp)*.02)relics.push_back(g);
    if(relics.empty())return false;
    const Unit* relic=relics[0];
    for(const auto* g:relics)if(std::make_tuple(std::abs(wrap_delta(g->x,c.foe.x,c.width)),g->id)<std::make_tuple(std::abs(wrap_delta(relic->x,c.foe.x,c.width)),relic->id))relic=g;
    const int facing=psgn(wrap_delta(relic->x,c.foe.x,c.width));
    for(const auto& key:walkers(c,plan)){
        if(!c.ready(key,0.))continue;
        if(deploy_(c,key,relic->x,relic->y-24,relic->id,facing).empty()){log["zs_relic_deploy"]+=1;return true;}
    }
    return false;
}
bool Zombie18::secondhand_deploy(Ctx& c,const PlanDict& plan,const std::vector<const Unit*>& graves){
    struct Best{double neg,d;const Pickup* item;const Unit* grave;};std::optional<Best> best;
    for(const auto& item:c.b.pickups){
        const auto v=HEAD_VALUE.find(item.name);if(v==HEAD_VALUE.end()||pickups_served.count(item.id))continue;
        for(const auto* g:graves){
            const double d=dist(c,g->x,g->y,item.x,item.y);
            if(d<=16.*c.tile&&(!best||std::make_tuple(-v->second,d)<std::make_tuple(best->neg,best->d)))best=Best{-v->second,d,&item,g};
        }
    }
    if(!best)return false;
    const int facing=psgn(wrap_delta(best->grave->x,best->item->x,c.width));
    auto ws=walkers(c,plan,&ARMOURLESS);
    stable_sort_by(ws,[&](const std::string& k){return c.card(k).cost;});
    for(const auto& key:ws){
        if(!c.ready(key,0.))continue;
        if(deploy_(c,key,best->grave->x,best->grave->y-24,best->grave->id,facing).empty()){pickups_served.insert(best->item->id);log["zs_secondhand_deploy"]+=1;return true;}
    }
    return false;
}
void Zombie18::command_logic(Ctx& c,const PlanDict& plan,double foe_home_d,int foe_dir){
    const bool confluence=c.has_secret("zsecret:汇流"),secondhand=c.has_secret("zsecret:二手");
    if(confluence&&confluence_defence(c))return;
    if(!confluence&&!secondhand){Zombie17::command_logic(c,plan,foe_home_d,foe_dir);return;}
    auto prev=send;
    send=[this,&c,prev,confluence,secondhand](const std::string& kind,const Args& data){
        std::optional<double> x,y;for(const auto& [k,v]:data){if(k=="x")x=std::get<double>(v);if(k=="y")y=std::get<double>(v);}
        if(kind=="rally"&&x){
            std::optional<std::pair<double,double>> point;
            if(secondhand)point=pickup_rally(c,*x,*y);
            if(!point&&confluence)point=kill_zone(c,*x,*y);
            if(point){Args d=data;for(auto& [k,v]:d){if(k=="x")v=point->first;if(k=="y")v=point->second;}return prev(kind,d);}
        }
        return prev(kind,data);
    };
    struct Restore{Controller& s;decltype(prev) p;~Restore(){s.send=p;}} restore{*this,prev};
    Zombie17::command_logic(c,plan,foe_home_d,foe_dir);
}
std::optional<std::pair<double,double>> Zombie18::pickup_rally(Ctx& c,double x,double y){
    for(const auto& item:c.b.pickups)
        if(HEAD_VALUE.count(item.name)&&dist(c,x,y,item.x,item.y)<=3.*c.tile){log["zs_secondhand_rally"]+=1;return std::pair<double,double>{item.x,item.y};}
    return std::nullopt;
}
bool Zombie18::confluence_defence(Ctx& c){
    if(!home)return false;
    const bool near=c.foe.hp>0&&std::abs(wrap_delta(home->first,c.foe.x,c.width))<=12.*c.tile;
    double defenders=0;for(const auto* u:c.own)if(u->mobile&&dist(c,home->first,home->second,u->x,u->y)<=8*c.tile)++defenders;
    const auto holding=defence_flag;
    if(near&&defenders>=3){
        if(!holding||c.t>=*holding){
            const auto point=kill_zone(c,home->first,home->second);
            if(point&&send_("rally",{{"x",point->first},{"y",point->second}}).empty()){defence_flag=c.t+4.;rally=point->first;log["zs_rally_defend_flag"]+=1;}
        }
        return true;
    }
    if(holding){
        defence_flag.reset();
        if(send_("rally",{{"clear",true}}).empty()){rally.reset();log["zs_rally_defend_clear"]+=1;}
    }
    return false;
}
std::optional<std::pair<double,double>> Zombie18::kill_zone(Ctx& c,double,double){
    if(!home||c.foe.hp<=0)return std::nullopt;
    const double gap=wrap_delta(home->first,c.foe.x,c.width);
    if(std::abs(gap)>12.*c.tile)return std::nullopt;
    log["zs_rally_defend"]+=1;
    return std::pair<double,double>{pmod(home->first+psgn(gap)*3.*c.tile,c.width),home->second-c.tile};
}
int Zombie18::drive(Ctx& c,double post,bool jump_wish,double tolerance){
    return Zombie17::drive(c,aura_post(c,post),jump_wish,tolerance);
}
double Zombie18::aura_post(Ctx& c,double post){
    const bool heal=c.has_secret("zsecret:生生不息"),press=c.has_secret("zsecret:威压");
    if(!(heal||press)||c.me.hp<.55*std::max(1.,c.me.max_hp))return post;
    for(const auto* u:c.enemy)if(u->mobile&&dist(c,c.me.x,c.me.y,u->x,u->y)<3*c.tile)return post;
    std::vector<const Unit*> army;for(const auto* u:c.own)if(u->mobile&&u->hp>0&&dist(c,c.me.x,c.me.y,u->x,u->y)<14*c.tile)army.push_back(u);
    if(army.size()<3)return post;
    if(press){
        std::vector<const Unit*> plants;
        for(const auto* u:c.enemy){
            if(!(u->card&&u->card->side=="plant")||u->hp<=0)continue;
            double n=0;for(const auto* a:army)if(dist(c,a->x,a->y,u->x,u->y)<6*c.tile)++n;
            if(n>=2)plants.push_back(u);
        }
        if(!plants.empty()){
            const Unit* target=plants[0];
            for(const auto* u:plants)if(std::make_tuple(dist(c,c.me.x,c.me.y,u->x,u->y),u->id)<std::make_tuple(dist(c,c.me.x,c.me.y,target->x,target->y),target->id))target=u;
            const int side=psgn(wrap_delta(target->x,c.me.x,c.width));
            const double spot=pmod(target->x+side*5.*c.tile,c.width);
            double guards=0;for(const auto* u:c.enemy)if(u->card&&u->card->side=="plant"&&u->hp>0&&dist(c,target->x,target->y,u->x,u->y)<=4*c.tile)++guards;
            if(guards<=3){log["zs_pressure_post"]+=1;return spot;}
            log["zs_pressure_skip_guarded"]+=1;
        }
    }
    if(heal){
        const double ref=army[0]->x;double s=0;for(const auto* a:army)s+=wrap_delta(ref,a->x,c.width);
        log["zs_heal_post"]+=1;
        return pmod(ref+s/double(army.size()),c.width);
    }
    return post;
}

// ========================================================= TeamSupportMixin
template<class Base> int TeamSupportMixin<Base>::drive(Ctx& c,double post,bool jump_wish,double tolerance){
    std::pair<double,double> home=this->home_point().value_or(std::pair<double,double>{c.me.x,c.me.y});
    const auto previous=support_decision;
    const auto decision=support.decide(c,home);
    support_decision=decision;
    if(!decision){
        const auto anchor=this->anchor_point().value_or(home);
        const double goal_y=std::abs(wrap_delta(post,anchor.first,c.width))<4*c.tile?anchor.second:c.me.y;
        if(const auto routed=ladder_drive(c,post,goal_y))return *routed;
        return Base::drive(c,post,jump_wish,tolerance);
    }
    if(!previous||std::tie(previous->state,previous->reason)!=std::tie(decision->state,decision->reason))
        this->log["team_support:"+decision->state+":"+decision->reason]+=1;
    static const std::set<std::string> hold{"local_danger","projectile","enemy_hero","health"};
    if(decision->state=="assist"||decision->state=="rescue"){
        post=decision->post;
        if(c.side==Seat::plant)this->set_anchor({post,c.me.y});
    }else if(decision->state=="return"&&!hold.count(decision->reason))post=home.first;
    else if(c.side==Seat::zombie&&decision->state=="home"&&one_of(decision->reason,{"cleared","cooldown","no_mate"})){
        const double goal_y=std::abs(wrap_delta(post,home.first,c.width))<4*c.tile?home.second:c.me.y;
        if(const auto routed=ladder_drive(c,post,goal_y))return *routed;
        return Base::drive(c,post,jump_wish,tolerance);
    }
    const double goal_y=(decision->state=="assist"||decision->state=="rescue")?decision->mate_y:home.second;
    if(const auto routed=ladder_drive(c,post,goal_y))return *routed;
    return this->controller_drive(c,post,jump_wish,tolerance);
}
template<class Base> std::optional<int> TeamSupportMixin<Base>::ladder_drive(Ctx& c,double post,double goal_y){
    if(!c.b.mode||!one_of(*c.b.mode,{"coop","duo","pve"}))return std::nullopt;
    static const std::set<std::string> hold{"local_danger","projectile","enemy_hero","health"};
    bool abort=c.deathmatch||this->recovering||(this->hold_refuge&&c.t<(*this->hold_refuge)[2])
        ||(support_decision&&hold.count(support_decision->reason))||c.me.hp<.4*std::max(1.,c.me.max_hp);
    if(!abort)for(const auto& t:c.obs.threats)if(t.projectile&&t.eta_ms<350)abort=true;
    if(!abort)for(const auto* u:c.enemy)if(u->mobile&&std::abs(wrap_delta(c.me.x,u->x,c.width))<2*c.tile&&std::abs(u->y-c.me.y)<2*c.tile)abort=true;
    if(abort){ladder_route.reset();return std::nullopt;}
    auto& route=ladder_route;
    if(route&&route->engaged&&std::abs(goal_y-c.me.y)<=c.tile*.8&&std::abs(route->goal_y-c.me.y)>c.tile*.8)goal_y=route->goal_y;
    const double dy=goal_y-c.me.y;
    if(route&&(std::abs(route->goal_y-goal_y)>c.tile*.5||c.t>route->until))route.reset();
    if(route&&(route->up?dy>=-c.tile*.08:dy<=c.tile*.08)){route.reset();return std::nullopt;}
    if(!route&&std::abs(dy)<=c.tile*.8)return std::nullopt;
    if(c.t<ladder_backoff_until)return std::nullopt;
    const auto& tiles=c.b.tiles;
    if(tiles.empty()||tiles[0].empty())return std::nullopt;
    const auto rows=int64_t(tiles.size()),cols=int64_t(tiles[0].size());
    const auto first=std::max<int64_t>(0,std::min<int64_t>(rows-1,int64_t(std::floor((std::min(c.me.y,goal_y)+2.)/c.tile))));
    const auto last=std::max<int64_t>(0,std::min<int64_t>(rows-1,int64_t(std::floor((std::max(c.me.y,goal_y)-2.)/c.tile))));
    const auto ladder=[&](int64_t row,int64_t col){const auto& cell=tiles[size_t(row)][size_t(col)];return !cell.solid&&(cell.ladder||one_of(cell.kind,{"梯子块","梯子","扶梯"}));};
    const auto column_ok=[&](int64_t col){for(auto row=first;row<=last;++row)if(!ladder(row,col))return false;return true;};
    if(!route){
        std::optional<std::tuple<double,int64_t,double>> best;
        for(int64_t col=0;col<cols;++col){
            const double x=(double(col)+.5)*c.tile;const double dxv=std::abs(wrap_delta(c.me.x,x,c.width));
            if(dxv>9*c.tile||!column_ok(col))continue;
            bool threat=false;
            for(const auto* u:c.enemy)if(u->mobile&&std::abs(wrap_delta(x,u->x,c.width))<2*c.tile&&std::min(c.me.y,goal_y)-c.tile<u->y&&u->y<std::max(c.me.y,goal_y)+c.tile){threat=true;break;}
            if(threat)continue;
            const auto cand=std::make_tuple(dxv+.15*std::abs(wrap_delta(x,post,c.width)),col,x);
            if(!best||cand<*best)best=cand;
        }
        if(!best)return std::nullopt;
        route=LadderRoute{std::get<1>(*best),std::get<2>(*best),goal_y,dy<0,c.t+12.,c.t,c.me.y,false};
        this->log[route->up?"route:ladder_up":"route:ladder_down"]+=1;
    }else if(!column_ok(route->col)){route.reset();return std::nullopt;}
    const double dx=wrap_delta(c.me.x,route->x,c.width);
    const bool on_column=int64_t(pmod(std::floor(c.me.x/c.tile),double(cols)))==route->col;
    if(on_column)route->engaged=true;
    if(!on_column||std::abs(dx)>c.tile*.23){
        route->progress_at=c.t;
        if(route->engaged){
            this->jump_down=false;const int move=dx>0?1:-1;
            this->send_("move",{{"move",double(move)},{"jump",route->up},{"edge",false}});
            return move;
        }
        return this->controller_drive(c,route->x,false,c.tile*.14);
    }
    if(std::abs(c.me.y-route->y)>c.tile*.2){route->progress_at=c.t;route->y=c.me.y;}
    else if(c.t-route->progress_at>2.){ladder_route.reset();ladder_backoff_until=c.t+2.;return std::nullopt;}
    this->jump_down=false;
    this->send_("move",{{"move",0.},{"jump",route->up},{"edge",false}});
    return 0;
}
template class TeamSupportMixin<Plant18>;
template class TeamSupportMixin<Zombie18>;

// ================================================================== Plant19
std::string Plant19::role(Ctx& c,const std::string& key){
    if(key=="plant:抓人草")return "shoot";if(key=="plant:冰冻生菜")return "freeze";if(key=="plant:水盆")return "tool";
    return TeamSupportMixin<Plant18>::role(c,key);
}
bool Plant19::counter_tools(Ctx& c,const std::map<std::string,std::vector<std::string>>& by_role,const PlanDict& plan){
    const std::string key="plant:冰冻生菜";
    if(c.me.in_deck(key)&&c.ready(key,0.)){
        std::vector<const Unit*> enemies;for(const auto* u:c.enemy)if(u->mobile&&u->hp>0&&std::abs(wrap_delta(c.me.x,u->x,c.width))<8*c.tile)enemies.push_back(u);
        if(!enemies.empty()){
            const auto distance=[&](const Spot& p){double m=INFINITY;for(const auto* u:enemies)m=std::min(m,std::abs(wrap_delta(p.x,u->x,c.width))+std::abs(p.y+c.tile*.5-u->y));return m;};
            auto spots=c.spots(true);stable_sort_by(spots,distance);
            for(size_t i=0;i<spots.size()&&i<5;++i){
                if(distance(spots[i])>2*c.tile)continue;
                if(deploy_(c,key,spots[i].x,spots[i].y,{},front).empty()){log["lettuce70"]+=1;return true;}
            }
        }
    }
    return TeamSupportMixin<Plant18>::counter_tools(c,by_role,plan);
}
std::optional<int> Plant19::lane_direction(Ctx& c,const std::string& key,double x,double y,int facing){
    if(!ballistic(c.card(key)))return facing;
    const auto cell=std::make_tuple(key,int64_t(std::floor(pmod(x,c.width)/(c.tile*.5))),int64_t(std::floor(y/(c.tile*.5))),facing>=0?1:-1);
    const auto signature=geometry_signature(c);
    Failure* previous=nullptr;for(auto& [k,f]:lane_failures)if(k==cell)previous=&f;
    std::optional<int> direction;
    if(previous&&*previous->signature==*signature&&previous->until>c.t)direction.reset();
    else{
        direction=firing_direction(c,key,x,y,facing);
        if(!direction){
            const int64_t repeats=previous&&*previous->signature==*signature?previous->repeats+1:1;
            const Failure f{signature,c.t+std::min(2.,.5*double(repeats)),repeats};
            if(previous)*previous=f;else lane_failures.emplace_back(cell,f);
            log["skip:blocked_firing_lane"]+=1;
            if(lane_failures.size()>128){
                std::vector<size_t> order(lane_failures.size());for(size_t i=0;i<order.size();++i)order[i]=i;
                std::stable_sort(order.begin(),order.end(),[&](size_t a,size_t b){return lane_failures[a].second.until<lane_failures[b].second.until;});
                std::set<size_t> drop(order.begin(),order.begin()+32);
                decltype(lane_failures) kept;for(size_t i=0;i<lane_failures.size();++i)if(!drop.count(i))kept.push_back(lane_failures[i]);
                lane_failures.swap(kept);
            }
        }else{
            for(auto i=lane_failures.begin();i!=lane_failures.end();++i)if(i->first==cell){lane_failures.erase(i);break;}
        }
    }
    if(!direction){lane_blocked=true;last_blocked_card=key;}
    else if(*direction!=facing)log["route_replan:turn"]+=1;
    return direction;
}
std::string Plant19::place_at(Ctx& c,const std::string& key,double x,double y,int facing){
    if(flag(c.card(key).aquatic)&&c.me.in_deck("plant:水盆")){
        for(const auto* u:c.own)if(u->card_id=="plant:水盆"&&std::abs(wrap_delta(u->x,x,c.width))<c.tile*.6&&std::abs(u->y-y)<c.tile)
            return deploy_(c,key,u->x,u->y-c.tile*.5,{},facing);
        if(c.ready("plant:水盆",0.)&&!ground(c,x,y).water){
            if(deploy_(c,"plant:水盆",x,y,{},facing).empty()){log["basin70"]+=1;return "";}
        }
    }
    const auto direction=lane_direction(c,key,x,y,facing);
    if(!direction)return "blocked firing lane";
    return TeamSupportMixin<Plant18>::place_at(c,key,x,y,*direction);
}
std::string Plant19::try_deploy(Ctx& c,const std::string& key,double x,double y,const std::optional<std::string>& grave,int facing){
    const auto direction=lane_direction(c,key,x,y,facing);
    if(!direction)return "blocked firing lane";
    return TeamSupportMixin<Plant18>::try_deploy(c,key,x,y,grave,*direction);
}
bool Plant19::place_(Ctx& c,const std::string& key,const std::string& r,const PlanDict& plan,double ax,double ay,double h){
    if(flag(c.card(key).aquatic)&&c.me.in_deck("plant:水盆")){
        for(const auto* u:c.own)if(u->card_id=="plant:水盆"&&deploy_(c,key,u->x,u->y-c.tile*.5,{},front).empty())return true;
        bool water=false;for(const auto& p:c.spots(true))if(p.water)water=true;
        if(c.ready("plant:水盆",0.)&&!water){
            const auto spots=c.spots(true);
            for(size_t i=0;i<spots.size()&&i<5;++i)if(deploy_(c,"plant:水盆",spots[i].x,spots[i].y,{},front).empty()){log["basin70"]+=1;return true;}
        }
    }
    if(!ballistic(c.card(key)))return TeamSupportMixin<Plant18>::place_(c,key,r,plan,ax,ay,h);
    auto spots=c.spots;std::map<bool,std::vector<Spot>> filtered;
    c.spots=[this,&c,spots,key,filtered](bool free) mutable{
        auto f=filtered.find(free);
        if(f==filtered.end()){
            std::vector<Spot> v;for(const auto& p:spots(free))if(lane_direction(c,key,p.x,p.y,facing_for(c,p.x)))v.push_back(p);
            f=filtered.emplace(free,v).first;
        }
        return f->second;
    };
    struct Restore{Ctx& c;decltype(spots) s;~Restore(){c.spots=s;}} restore{c,spots};
    const bool result=TeamSupportMixin<Plant18>::place_(c,key,r,plan,ax,ay,h);
    if(result&&lane_blocked)log["route_replan:position"]+=1;
    return result;
}
bool Plant19::replan_firing(Ctx& c,const PlanDict& plan){
    const auto inv=invaders(c);
    if(economy_gate(c,plan,inv)==std::optional<std::string>("econ"))return false;
    const double reserve=income_floor(c,plan);
    std::vector<std::string> keys;for(const auto& k:deck(c))if(fire_role(role(c,k))&&c.ready(k,reserve))keys.push_back(k);
    stable_sort_by(keys,[&](const std::string& k){const auto& cd=c.card(k);return std::make_tuple(ballistic(cd)&&!flag(cd.lob)?2:flag(cd.lob)?1:0,cd.cost);});
    std::vector<const Unit*> targets;for(const auto* u:c.enemy)if(u->hp>0)targets.push_back(u);
    auto spots=c.spots(true);
    stable_sort_by(spots,[&](const Spot& p){
        double near=6.;if(!targets.empty()){near=INFINITY;for(const auto* u:targets)near=std::min(near,std::abs(wrap_delta(p.x,u->x,c.width))/c.tile+std::abs(p.y-u->y)/c.tile);}
        return near+std::abs(wrap_delta(c.me.x,p.x,c.width))/c.tile*.35+std::abs(p.y-c.me.y)/c.tile*.5;
    });
    for(size_t ki=0;ki<keys.size()&&ki<4;++ki){
        const auto& key=keys[ki];int tries=0;const auto& card=c.card(key);
        for(size_t i=0;i<spots.size()&&i<48;++i){
            const auto& p=spots[i];
            const auto facing=lane_direction(c,key,p.x,p.y,facing_for(c,p.x));
            if(!facing)continue;
            const auto assessment=firing_assessment(c,key,p.x,p.y,*facing);
            if(!targets.empty()&&assessment.reason=="open_corridor")continue;
            double reach=card.range!=0.?card.range:8*c.tile;if(reach<32)reach*=c.tile;
            if(!ballistic(card)&&!targets.empty()){
                bool any=false;for(const auto* u:targets)if(std::abs(wrap_delta(p.x,u->x,c.width))<=std::min(8*c.tile,reach)&&std::abs(p.y-u->y)<3*c.tile)any=true;
                if(!any)continue;
            }
            const auto err=place_at(c,key,p.x,p.y,*facing);
            if(err.empty()){
                log[key!=last_blocked_card.value_or(key)?"route_replan:switch_card":"route_replan:position"]+=1;
                lane_wait_signature.reset();
                return true;
            }
            if(err!="memo")++tries;
            if(tries>=4)break;
        }
    }
    const auto signature=geometry_signature(c);
    const bool same=lane_wait_signature&&*lane_wait_signature==*signature;
    if(!same)log["route_replan:wait_for_change"]+=1;
    lane_wait_signature=signature;
    return false;
}
void Plant19::step(const View& v,const typed72::AiObservation& o,const PlanDict& plan,const Field& f,Services& s){
    if(support.active&&v.mode&&one_of(*v.mode,{"coop","duo"})){PlanDict p=plan;p.set("mode",std::string("defend"));TeamSupportMixin<Plant18>::step(v,o,p,f,s);return;}
    TeamSupportMixin<Plant18>::step(v,o,plan,f,s);
}
void Plant19::deploy_logic(Ctx& c,const PlanDict& plan){
    lane_blocked=false;
    const double before0=deploy_count(log);
    if(!assisting()){
        TeamSupportMixin<Plant18>::deploy_logic(c,plan);
        if(lane_blocked&&deploy_count(log)==before0)replan_firing(c,plan);
        return;
    }
    const auto decision=*support_decision;
    auto ready=c.ready;const auto saved_anchor=anchor;const int saved_front=front;const auto saved_mode=mode;
    c.ready=[&c,ready,decision](const std::string& key,double reserve){
        if(key.rfind("secret:",0)==0||key.rfind("zsecret:",0)==0)return false;
        return !c.card(key).producer&&ready(key,std::max(reserve,decision.reserve));
    };
    anchor=std::pair<double,double>{c.me.x,c.me.y};
    front=wrap_delta(c.me.x,decision.mate_x,c.width)>=0?1:-1;
    mode="defend";
    struct Restore{Plant19& s;Ctx& c;decltype(ready) r;decltype(saved_anchor) a;int f;std::string m;~Restore(){c.ready=r;s.anchor=a;s.front=f;s.mode=m;}} restore{*this,c,ready,saved_anchor,saved_front,saved_mode};
    const double before=deploy_count(log);
    std::vector<const Unit*> threats;for(const auto* u:c.enemy)if(std::abs(wrap_delta(c.me.x,u->x,c.width))<10*c.tile)threats.push_back(u);
    if(!threats.empty())repel(c,plan,threats);
    double after=deploy_count(log);
    if(after==before&&lane_blocked){replan_firing(c,plan);after=deploy_count(log);}
    if(after>before)log[std::abs(wrap_delta(c.me.x,decision.mate_x,c.width))<8*c.tile?"team_support_deploy":"team_support_route_clear"]+=after-before;
}

// ================================================================= Zombie19
void Zombie19::command_logic(Ctx& c,const PlanDict& plan,double foe_home_d,int foe_dir){
    if(!assisting()){
        if(support_rally){
            if(!send_("rally",{{"clear",true}}).empty())return;
            support_rally=false;rally.reset();
        }
        TeamSupportMixin<Zombie18>::command_logic(c,plan,foe_home_d,foe_dir);return;
    }
    const auto& decision=*support_decision;
    const auto point=c.b.rally_point;
    const double flag_y=decision.mate_y-c.tile*.5;
    if(!point||std::abs(wrap_delta(point->first,decision.post,c.width))>c.tile||std::abs(point->second-flag_y)>c.tile*.5){
        if(send_("rally",{{"x",decision.post},{"y",flag_y}}).empty()){rally=decision.post;support_rally=true;log["team_support_own_rally"]+=1;}
    }
}
void Zombie19::deploy_logic(Ctx& c,const PlanDict& plan,const std::vector<const Unit*>& graves,double foe_home_d){
    if(!assisting()){TeamSupportMixin<Zombie18>::deploy_logic(c,plan,graves,foe_home_d);return;}
    const auto& decision=*support_decision;
    const std::string seat=c.b.local_seat.value_or(c.side_name);
    std::vector<const Unit*> exits;
    const bool unrestricted=c.has_secret("zsecret:解除封印");
    for(const auto* g:graves)if(g->seat.value_or(c.side_name)==seat&&std::abs(wrap_delta(g->x,decision.mate_x,c.width))<=12*c.tile&&(unrestricted||in_view(c.me.x,c.me.y,g->x,g->y,c.width)))exits.push_back(g);
    stable_sort_by(exits,[&](const Unit* g){return std::abs(wrap_delta(g->x,decision.mate_x,c.width));});
    std::vector<std::string> keys;
    for(const auto& k:c.me.deck){
        if(k.rfind("secret:",0)==0||k.rfind("zsecret:",0)==0)continue;
        const auto& cd=c.card(k);if(one_of(cd.behavior,{"grave","scarecrow","flag"})||cd.producer)continue;
        keys.push_back(k);
    }
    for(const auto& key:unit_order(c,keys,plan)){
        if(!c.ready(key,decision.reserve))continue;
        for(size_t i=0;i<exits.size()&&i<3;++i){
            const int facing=wrap_delta(exits[i]->x,decision.mate_x,c.width)>=0?1:-1;
            if(deploy_(c,key,exits[i]->x,exits[i]->y-24,exits[i]->id,facing).empty()){log["team_support_deploy"]+=1;return;}
        }
    }
}
} // namespace pvz::typed72app::ai
