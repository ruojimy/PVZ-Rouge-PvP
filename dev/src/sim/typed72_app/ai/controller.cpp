// rv_field.Field, rv_tactics_v6 (Ctx, Controller, PlantTactics helpers) and
// rv_ztactics61 (ZombieTactics61 helpers). Line-for-line semantics: Python's
// stable sorts, first-wins max/min, floor division and modulo are kept.
#include "sim/typed72_app/ai/controller.h"
#include "core/pymath.h"
#include <algorithm>
#include <cmath>
#include <cstdio>
#include <stdexcept>
#include <tuple>

namespace pvz::typed72app::ai {
namespace {
double pmod(double a,double b){return py::mod(a,b);}
double fdiv(double a,double b){return std::floor(a/b);}
bool one_of(const std::string& s,std::initializer_list<const char*> set){for(const char* v:set)if(s==v)return true;return false;}
std::string after_colon(const std::string& key){const auto a=key.find(':');if(a==std::string::npos)throw std::invalid_argument("card key: "+key);const auto b=key.find(':',a+1);return key.substr(a+1,b==std::string::npos?std::string::npos:b-a-1);}
// Python str[:n] on UTF-8 text: n code points.
std::string prefix_chars(const std::string& s,size_t n){size_t i=0,count=0;while(i<s.size()&&count<n){const unsigned char c=s[i];i+=c<0x80?1:c<0xE0?2:c<0xF0?3:4;++count;}return s.substr(0,std::min(i,s.size()));}
const std::set<std::string> LOBBERS{"plant:卷心菜投手","plant:玉米投手","plant:西瓜投手","plant:冰瓜投手","plant:甜椒投手"};
const std::set<std::string> CONE{"plant:闪电芦苇","plant:超载芦苇"};
const std::map<std::string,std::string> SHELL_VINES{{"plant:阳光藤蔓","econ"},{"plant:忧郁藤蔓","shoot"}};
const std::map<std::string,double> HERO_KILLERS{{"plant:卷心菜投手",12},{"plant:西瓜投手",16},{"plant:冰瓜投手",16},{"plant:杨桃",30},{"plant:甜椒投手",15},{"plant:原始豌豆射手",15},{"plant:超载芦苇",9},{"plant:闪电芦苇",6}};
const std::map<std::string,std::string>& plant_roles(){
    static const std::map<std::string,std::string> r{{"produce","econ"},{"shoot","shoot"},{"wall","wall"},{"ash","instant"},{"squash","instant"},
        {"chomp","instant"},{"chili","instant"},{"doom","instant"},{"freeze","freeze"},{"mine","mine"},{"pot","pot"},{"lily","lily"},{"coffee","coffee"},
        {"gravebuster","gravebuster"},{"spike","spike"},{"torch","torch"},{"umbrella","support"},{"lantern","support"},{"support","support"},{"garlic","wall"},
        {"magnet","magnet"},{"wind","wind"},{"charm","charm"},{"cannon","cannon"},{"copy","copy"},{"stone","stone"},
        {"reed61","shoot"},{"flying56","shoot"},{"ghost","instant"},{"gold_bloom","bloom"},{"grass","tool"}};
    return r;
}
const std::vector<std::string>* role_list(const std::map<std::string,std::vector<std::string>>& m,const std::string& k){auto f=m.find(k);return f==m.end()?nullptr:&f->second;}
std::vector<std::string> role_get(const std::map<std::string,std::vector<std::string>>& m,const std::string& k){auto f=m.find(k);return f==m.end()?std::vector<std::string>{}:f->second;}
bool flag(const typed72::Field<bool>& f){return f.present()&&!f.is_null()&&f.get();}
}

double wrap_delta(double a,double b,double width){const double d=pmod(b-a,width);return d>width/2.?d-width:d;}
bool in_view(double hx,double hy,double x,double y,double width){
    return std::abs(wrap_delta(hx,x,width))<=VIEW_HALF_WIDTH-8.&&-VIEW_ABOVE+8.<=y-hy&&y-hy<=VIEW_BELOW-8.;
}
const std::string& card_behavior(const Unit& u){static const std::string none;return u.card?u.card->behavior:none;}
double card_cost(const Unit& u,double fallback){return u.card?u.card->cost:fallback;}
bool card_producer(const Unit& u){return u.card&&u.card->producer;}
std::string card_name(const Unit& u){return u.card?u.card->name:std::string{};}

// ------------------------------------------------------------------ Field
Field::Field(const std::vector<std::vector<Cell>>& tiles,double w,double h,double t):width(w),height(h),tile(t){
    const size_t rows=tiles.size(),cols=rows?tiles[0].size():0;
    for(size_t col=0;col<cols;++col)for(size_t row=1;row<rows;++row){
        const auto& cell=tiles[row][col];const auto& above=tiles[row-1][col];
        if(!(cell.solid||cell.water))continue;if(above.solid)continue;
        const double x=(double(col)+.5)*tile,y=double(row)*tile-2.;
        const int zone=int(int64_t(pmod(x,width)/width*ZONES)%ZONES);
        spots[size_t(zone)].push_back({x,y,cell.water});
    }
    for(auto& bucket:spots)std::sort(bucket.begin(),bucket.end(),[](const Spot& a,const Spot& b){return std::tie(a.x,a.y,a.water)<std::tie(b.x,b.y,b.water);});
}
std::vector<Spot> Field::candidates(int zone,double hero_x,std::optional<double> hero_y,int64_t limit)const{
    if(zone<0||zone>=ZONES)return {};
    std::vector<std::tuple<double,double,double,bool>> chosen;
    for(const auto& s:spots[size_t(zone)]){
        const double offset=wrap_delta(hero_x,s.x,width);
        if(std::abs(offset)>VIEW_HALF_WIDTH)continue;
        if(hero_y&&!(-VIEW_ABOVE<=s.y-*hero_y&&s.y-*hero_y<=VIEW_BELOW))continue;
        chosen.emplace_back(std::abs(offset),s.x,s.y,s.water);
    }
    std::sort(chosen.begin(),chosen.end());
    std::vector<Spot> out;for(size_t i=0;i<chosen.size()&&int64_t(i)<limit;++i)out.push_back({std::get<1>(chosen[i]),std::get<2>(chosen[i]),std::get<3>(chosen[i])});
    return out;
}

// -------------------------------------------------------------------- Ctx
static const Player& seat_player(const View& v,const std::string& key){
    const auto* p=v.player(key);if(!p)throw std::out_of_range("snapshot has no player "+key);return *p;
}
Ctx::Ctx(Seat s,const View& view,const typed72::AiObservation& o,const Field& f,Services& sv)
    :side(s),side_name(s==Seat::plant?"plant":"zombie"),b(view),obs(o),field(f),services(sv),t(view.time),width(view.width),tile(view.tile),
     me(seat_player(view,s==Seat::plant?"plant":"zombie")),foe(seat_player(view,s==Seat::plant?"zombie":"plant")),
     night(view.map_night),deathmatch(view.deathmatch){
    for(const auto& u:view.units)if(u.hp>0.){living.push_back(&u);(u.side==side?own:enemy).push_back(&u);}
    ready=[this](const std::string& k,double r){return base_ready(k,r);};
    spots=[this](bool free){return spots_impl(free);};
}
bool Ctx::base_ready(const std::string& key,double reserve)const{
    const auto& c=card(key);
    if(me.cooldown(key,0.)>t)return false;
    if(deathmatch&&c.producer)return false;
    return me.resource>=c.cost+reserve;
}
std::vector<Spot> Ctx::spots_impl(bool free){
    auto f=spot_cache.find(free);if(f!=spot_cache.end())return f->second;
    std::vector<Spot> out;std::vector<const Unit*> statics;
    if(free)for(const auto* u:living)if(!u->mobile)statics.push_back(u);
    for(int zone=0;zone<Field::ZONES;++zone)for(const auto& s:field.candidates(zone,me.x,me.y,40)){
        if(!in_view(me.x,me.y,s.x,s.y,width))continue;
        if(free&&std::any_of(statics.begin(),statics.end(),[&](const Unit* u){return std::abs(wrap_delta(s.x,u->x,width))<tile*.6&&std::abs(u->y-s.y)<tile*1.1&&u->behavior!="pot"&&u->behavior!="lily";}))continue;
        out.push_back(s);
    }
    spot_cache[free]=out;return out;
}
std::vector<Spot> CtxV7::spots_impl(bool free){
    if(!free||side!=Seat::plant||!has_secret("secret:密植"))return Ctx::spots_impl(free);
    std::vector<Spot> out;
    for(const auto& s:Ctx::spots_impl(false)){
        size_t n=0;bool foreign=false;
        for(const auto* u:living){
            if(u->mobile||one_of(u->behavior,{"pot","lily","vine"})||u->card_id=="plant:南瓜头")continue;
            if(!(std::abs(wrap_delta(s.x,u->x,width))<tile*.6&&std::abs(u->y-s.y)<tile*.7))continue;
            ++n;if(u->side!=side)foreign=true;
        }
        if(foreign||n>=3)continue;out.push_back(s);
    }
    return out;
}

// -------------------------------------------------------------- Controller
int Controller::drive(Ctx& c,double target_x,bool jump_wish,double tolerance){
    const double delta=wrap_delta(c.me.x,target_x,c.width);
    int move=std::abs(delta)<=tolerance?0:sgn(delta);
    const double t=c.t;
    if(move&&std::abs(delta)>900.){
        if(blocked){
            if(!stuck_since||*stuck_since==0.)stuck_since=t;   // getattr(...) or t
            if(t-*stuck_since>2.5){detour_until=t+10.;stuck_since.reset();}
        }else stuck_since.reset();
        if(t<detour_until)move=-move;
    }else stuck_since.reset();
    if(!last_pos||t-last_pos->second>=.35){
        blocked=move&&last_pos&&std::abs(wrap_delta(last_pos->first,c.me.x,c.width))<8.;
        last_pos={c.me.x,t};
    }
    bool wall=false;
    if(move){
        const auto row=int64_t(fdiv(c.me.y-24.,c.tile));const auto col=int64_t(fdiv(pmod(c.me.x+move*36.,c.width),c.tile));
        if(row>=0&&row<int64_t(c.b.tiles.size()))wall=c.b.tiles[size_t(row)].at(size_t(col)).solid;
    }
    const bool want=jump_wish||(move&&(wall||blocked));
    bool jump=false;
    if(jump_down)jump_down=false;
    else if(want&&t>=next_jump){jump=true;jump_down=true;next_jump=t+.3;}
    send_("move",{{"move",double(move)},{"jump",jump},{"edge",jump}});
    return move;
}
std::string Controller::try_deploy(Ctx& c,const std::string& key,double x,double y,const std::optional<std::string>& grave,int facing){
    char buf[64];std::snprintf(buf,sizeof buf,"|%lld|%lld|",(long long)fdiv(x,8.),(long long)fdiv(y,8.));
    const std::string memo=key+buf+(grave?*grave:std::string("None"));
    auto f=failed.find(memo);if((f==failed.end()?-1.:f->second)>c.t)return "memo";
    const std::string err=c.services.preview(key,x,y,grave,false);
    if(!err.empty()){
        failed[memo]=c.t+3.;
        log["fail:"+after_colon(key)+":"+prefix_chars(err,12)]+=1;
        return err;
    }
    Args a{{"card",key},{"x",x},{"y",y}};
    a.emplace_back("grave",grave?PlanValue(*grave):PlanValue(std::monostate{}));
    a.emplace_back("facing",double(facing));
    const std::string sent=send_("deploy",a);
    if(sent.empty())log["deploy:"+key]+=1;
    return sent;
}

// ================================================================== PLANT v6
int PlantV6::update_sides(Ctx& c){
    if(!side_threat){side_threat=std::map<int,double>{{1,0.},{-1,0.}};st_time=c.t;main_front=sgn(wrap_delta(anchor->first,c.foe.x,c.width));}
    auto& st=*side_threat;
    const double dt=std::max(0.,c.t-st_time);st_time=c.t;const double k=std::exp(-dt/60.);
    for(int sd:{1,-1})st[sd]*=k;
    const double ax=anchor->first;
    for(const auto* u:c.enemy)if(u->mobile&&!u->flying){
        const double d=wrap_delta(ax,u->x,c.width);
        if(std::abs(d)<12*c.tile&&std::abs(u->y-anchor->second)<5*c.tile)st[sgn(d)]+=(card_cost(*u,25.)+25.)*dt;
    }
    if(st[-main_front]>2*st[main_front]+200){main_front=-main_front;log["front_flip"]+=1;}
    return main_front;
}
double PlantV6::back_share()const{
    if(!side_threat)return 0.;const auto& st=*side_threat;const double tot=st.at(1)+st.at(-1);
    return tot>0?st.at(-main_front)/tot:0.;
}
bool PlantV6::siege_established(Ctx& c,const PlanDict& plan){
    const auto sb_1=*siege_anchor;const auto ax=std::get<0>(sb_1);const auto ay=std::get<1>(sb_1);
    if(std::abs(wrap_delta(c.me.x,ax,c.width))>120){arrived_at.reset();return false;}
    if(!arrived_at)arrived_at=c.t;
    if(c.t-*arrived_at>plan.num("siege_dwell",10)){arrived_at.reset();return true;}
    double lobs=0,walls=0;
    for(const auto* u:c.own)if(std::abs(wrap_delta(ax,u->x,c.width))<6*c.tile){
        if(LOBBERS.count(u->card_id))++lobs;
        if(card_behavior(*u)=="wall"&&along(c,u->x)>0)++walls;
    }
    return lobs>=plan.num("siege_lobs",2)&&(walls>=1||lobs>=3);
}
int PlantV6::route_dir(Ctx& c,double frm,double bx){
    std::optional<std::pair<double,int>> best;
    for(int d:{1,-1}){
        const double length=pmod((bx-frm)*d,c.width);double danger=0.;
        for(const auto* u:c.enemy)if(u->mobile){const double pos=pmod((u->x-frm)*d,c.width);if(pos<length+200)danger+=card_cost(*u,25.);}
        const double score=length/c.tile*8+danger;
        if(!best||score<best->first)best={score,d};
    }
    return best->second;
}
std::pair<double,double> PlantV6::next_siege_anchor(Ctx& c,const PlanDict& plan){
    const auto cur=siege_anchor?*siege_anchor:*home_anchor;
    const auto sb_2=enemy_base(c);const auto bx=std::get<0>(sb_2);const auto by=std::get<1>(sb_2);(void)by;
    if(!siege_anchor||!siege_dir){
        siege_dir=route_dir(c,cur.first,bx);
        log[std::string("route_")+(*siege_dir==sgn(wrap_delta(cur.first,bx,c.width))?"short":"long")]+=1;
    }
    const int d=*siege_dir;
    const double dist=pmod((bx-cur.first)*d,c.width);
    const double stop=plan.num("siege_gap",380);
    const double step=std::min(plan.num("siege_step",6)*c.tile,dist-stop);
    if(step<c.tile)return cur;
    const double tx=pmod(cur.first+d*step,c.width);
    PlanDict wider=plan;wider.set("platform_reach",3*c.tile);
    const auto best=find_platform(c,wider,tx,2);
    log["siege_step"]+=1;
    return best?*best:std::pair<double,double>{tx,cur.second};
}
std::optional<std::pair<double,double>> PlantV6::find_platform(Ctx& c,const PlanDict& plan,std::optional<double> around,int min_len){
    const double center=around?*around:c.me.x;const double tile=c.tile;
    std::map<int64_t,std::set<int64_t>> by_y_set;std::vector<int64_t> y_order;   // dict insertion order
    for(const auto& bucket:c.field.spots)for(const auto& s:bucket)if(!s.water){
        const auto y=int64_t(std::nearbyint(s.y));   // round() ties to even
        if(!by_y_set.count(y))y_order.push_back(y);
        by_y_set[y].insert(int64_t(fdiv(s.x,tile)));
    }
    struct Best{double score,cx,y,a,b;};std::optional<Best> best;
    const double reach=plan.num("platform_reach",420);
    for(const auto y:y_order){
        const auto& cols=by_y_set[y];
        std::vector<std::pair<int64_t,int64_t>> runs;std::optional<int64_t> start,prev;
        for(const auto col:cols){
            if(!start){start=prev=col;}
            else if(col==*prev+1)prev=col;
            else{runs.emplace_back(*start,*prev);start=prev=col;}
        }
        if(start)runs.emplace_back(*start,*prev);
        for(const auto& [a,bb]:runs){
            const auto length=bb-a+1;if(length<min_len)continue;
            const double cx=double(a+bb+1)/2.*tile;
            const double dist=std::abs(wrap_delta(center,cx,c.width));if(dist>reach)continue;
            if(std::abs(double(y)-c.me.y)>plan.num("platform_dy",2.2)*tile&&!around)continue;
            const double score=double(std::min<int64_t>(length,14))*tile*1.5-dist*.5-std::abs(double(y)-c.me.y)*1.;
            if(!best||score>best->score)best=Best{score,cx,double(y),double(a)*tile,double(bb+1)*tile};
        }
    }
    if(!best)return around?std::nullopt:std::optional<std::pair<double,double>>({c.me.x,c.me.y});
    platform=std::array<double,2>{best->a,best->b};
    log["platform_len"]=double(int64_t((best->b-best->a)/tile));
    return std::pair<double,double>{pmod(best->cx,c.width),best->y};
}
std::pair<double,bool> PlantV6::kite_target(Ctx& c,double post,const PlanDict& plan){
    const double tile=c.tile;const auto& me=c.me;
    const double radius=plan.num("kite_radius",4.)*tile;
    std::vector<const Unit*> zs;
    for(const auto* u:c.enemy)if(u->mobile&&!u->flying&&std::abs(c.dx(u->x))<12*tile&&std::abs(u->y-me.y)<4*tile)zs.push_back(u);
    if(zs.empty())return {post,false};
    const auto danger=[&](double x,double y){
        double total=0.;
        for(const auto* u:zs){
            const double d=std::hypot(wrap_delta(x,u->x,c.width),(u->y-y)*1.5);
            if(d<radius)total+=std::pow(1-d/radius,2)*(card_name(*u).find("黑")!=std::string::npos?3:1);
        }
        return total;
    };
    const double here=danger(me.x,me.y);
    if(here<.02&&danger(post,me.y)<.02)return {post,false};
    std::optional<std::pair<double,double>> best;std::optional<double> best_score;
    for(const auto& bucket:c.field.spots)for(const auto& s:bucket){
        const double dx=wrap_delta(me.x,s.x,c.width);
        if(std::abs(dx)>9*tile||std::abs(s.y-me.y)>2.5*tile||s.water)continue;
        double score=danger(s.x,s.y)*10;
        score+=std::abs(wrap_delta(post,s.x,c.width))/tile*plan.num("kite_home_w",.12);
        score+=std::abs(dx)/tile*.05+std::abs(s.y-me.y)/tile*.3;
        for(const auto* u:zs){
            const double ux=wrap_delta(me.x,u->x,c.width);
            if(std::abs(u->y-me.y)<1.5*tile&&0<ux*sgn(dx)&&ux*sgn(dx)<std::abs(dx))score+=6;
        }
        if(!best_score||score<*best_score){best={s.x,s.y};best_score=score;}
    }
    if(!best)return {post,false};
    double close=INFINITY;for(const auto* u:zs)close=std::min(close,std::hypot(c.dx(u->x),u->y-me.y));
    const double bdx=wrap_delta(me.x,best->first,c.width);
    bool crossing=false;
    for(const auto* u:zs){const double v=wrap_delta(me.x,u->x,c.width)*sgn(bdx);if(std::abs(u->y-me.y)<1.5*tile&&0<v&&v<std::abs(bdx)){crossing=true;break;}}
    log["_kiting"]=1;
    return {best->first,close<1.2*tile||crossing};
}
std::pair<double,double> PlantV6::enemy_base(Ctx& c){
    std::vector<const Unit*> graves;for(const auto* u:c.enemy)if(u->behavior=="grave")graves.push_back(u);
    if(graves.empty())return {c.foe.x,c.foe.y};
    const double g0=graves[0]->x;double sx=0.,sy=0.;
    for(const auto* g:graves){sx+=wrap_delta(g0,g->x,c.width);sy+=g->y;}
    return {pmod(g0+sx/double(graves.size()),c.width),sy/double(graves.size())};
}
std::vector<const Unit*> PlantV6::nearby(Ctx& c,double radius,std::optional<double> x,std::optional<double> y){
    const double px=x?*x:c.me.x,py=y?*y:c.me.y;std::vector<const Unit*> out;
    for(const auto* u:c.enemy)if(u->mobile&&std::abs(wrap_delta(px,u->x,c.width))<radius&&std::abs(u->y-py)<110)out.push_back(u);
    return out;
}
std::vector<std::string> PlantV6::deck(Ctx& c){
    std::vector<std::string> out;for(const auto& k:c.me.deck)if(k.rfind("secret:",0)!=0&&k.rfind("zsecret:",0)!=0)out.push_back(k);return out;
}
std::string PlantV6::role(Ctx& c,const std::string& key){
    if(LOBBERS.count(key)||CONE.count(key))return "lob";
    if(SHELL_VINES.count(key))return "vine";
    const auto& r=plant_roles();const auto f=r.find(c.card(key).behavior);return f==r.end()?"other":f->second;
}
double PlantV6::along(Ctx& c,double x){return front*wrap_delta(anchor->first,x,c.width)/c.tile;}
double PlantV6::half(Ctx& c){
    if(!platform)return 2.5;
    return std::max(2.5,((*platform)[1]-(*platform)[0])/2./c.tile);
}
double PlantV6::pressure(Ctx& c){
    double total=0;for(const auto* u:c.enemy)if(u->mobile&&std::abs(wrap_delta(anchor->first,u->x,c.width))<900)total+=card_cost(*u,25.);return total;
}
size_t PlantV6::front_walls(Ctx& c,const std::map<std::string,std::string>& roles){
    size_t n=0;
    for(const auto* u:c.own){auto f=roles.find(u->card_id);if(f!=roles.end()&&f->second=="wall"){const double a=along(c,u->x);if(0<a&&a<half(c)+1.5)++n;}}
    return n;
}
void PlantV6::deploy_logic(Ctx& c,const PlanDict& plan){
    const auto d=deck(c);
    std::map<std::string,std::string> roles;for(const auto& k:d)roles[k]=role(c,k);
    std::map<std::string,std::vector<std::string>> by_role;for(const auto& k:d)by_role[roles[k]].push_back(k);
    if(!c.night&&by_role.count("coffee")){
        for(const auto& s:c.obs.sleeping_plants){
            const auto& k=by_role["coffee"][0];
            if(c.ready(k,0.)&&deploy_(c,k,s.position.x,s.position.y-24).empty())return;
        }
    }
    if(emergency(c,by_role,plan))return;
    if(bomb_cluster(c,by_role,plan))return;
    if(mode=="siege"){
        if(in_view(c.me.x,c.me.y,c.foe.x,c.foe.y,c.width)&&strike(c,by_role))return;
        if(grave_bomb(c,by_role,plan))return;
        const auto sb_3=enemy_base(c);const auto bx=std::get<0>(sb_3);const auto by=std::get<1>(sb_3);
        if(siege_lobbers(c,by_role,bx,by))return;
        if(std::abs(wrap_delta(anchor->first,c.me.x,c.width))>150)return;
    }
    for(const auto& k:role_get(by_role,"gravebuster")){
        if(c.ready(k,0.)){
            std::vector<const Unit*> graves;for(const auto* u:c.enemy)if(u->behavior=="grave"&&in_view(c.me.x,c.me.y,u->x,u->y,c.width))graves.push_back(u);
            stable_sort_by(graves,[&](const Unit* u){return std::abs(c.dx(u->x));});
            for(size_t i=0;i<graves.size()&&i<3;++i)if(deploy_(c,k,graves[i]->x,graves[i]->y-24).empty())return;
        }
    }
    if(bloom_and_vines(c,by_role,plan))return;
    double producers=0,shooters=0;
    for(const auto* u:c.own){if(card_producer(*u))++producers;auto f=roles.find(u->card_id);if(f!=roles.end()&&(f->second=="shoot"||f->second=="lob"))++shooters;}
    const double walls=double(front_walls(c,roles));
    double econ_goal=plan.num("econ_goal",5);
    const double pres=pressure(c);
    std::vector<std::string> order;
    if(mode=="siege")econ_goal=0;
    else if(c.me.resource>plan.num("rich",400))econ_goal+=3;
    if(producers<econ_goal&&!c.deathmatch){
        if(pres>150&&shooters<2)order.insert(order.end(),{"lob","shoot","econ"});
        else order.insert(order.end(),{"econ","lob","shoot"});
    }
    if(walls<plan.num("wall_goal",2)&&(shooters>=2||pres>0))order.insert(pres>100?order.begin():order.end(),"wall");
    order.insert(order.end(),{"lob","shoot","spike","wall","torch","support","magnet","mine"});
    double reserve=plan.num("reserve",0);
    double army=0;for(const auto* u:c.enemy)if(u->mobile)army+=card_cost(*u,25.);
    std::vector<std::string> bombs;for(const auto& k:role_get(by_role,"instant"))if(one_of(c.card(k).behavior,{"ash","doom","chili"}))bombs.push_back(k);
    if(!bombs.empty()&&army>=plan.num("bomb_reserve_army",300)){
        const auto k=*std::min_element(bombs.begin(),bombs.end(),[&](const auto& a,const auto& b2){return c.card(a).cost<c.card(b2).cost;});
        if(c.me.cooldown(k,0.)<=c.t+8){reserve=std::max(reserve,c.card(k).cost);log["_reserving"]=1;}
    }
    std::set<std::string> seen;
    for(const auto& r:order){
        if(!seen.insert(r).second)continue;
        for(const auto& k:rank_cards(c,role_get(by_role,r),r)){
            if(!c.ready(k,(r!="econ"||army>=500)?reserve:0.))continue;
            if(place(c,k,r,plan))return;
        }
    }
}
bool PlantV6::bloom_and_vines(Ctx& c,std::map<std::string,std::vector<std::string>> by_role,const PlanDict& plan){
    for(const auto& k:role_get(by_role,"bloom"))if(c.ready(k,0.)&&place(c,k,"econ",plan)){log["bloom"]+=1;return true;}
    std::vector<std::string> vines;for(const auto& k:role_get(by_role,"vine"))if(c.ready(k,plan.num("vine_reserve",50)))vines.push_back(k);
    if(vines.empty())return false;
    std::vector<std::pair<double,double>> shelled;
    for(const auto* u:c.own)if(SHELL_VINES.count(u->card_id)||u->card_id=="plant:南瓜头")shelled.emplace_back(u->x,u->y);
    std::vector<const Unit*> hosts;
    for(const auto* u:c.own){
        if(u->mobile||one_of(u->behavior,{"pot","lily","vine"})||SHELL_VINES.count(u->card_id)||u->card_id=="plant:南瓜头")continue;
        if(!in_view(c.me.x,c.me.y,u->x,u->y,c.width))continue;
        if(std::any_of(shelled.begin(),shelled.end(),[&](const auto& p){return std::abs(wrap_delta(p.first,u->x,c.width))<c.tile*.5&&std::abs(p.second-u->y)<c.tile*.5;}))continue;
        hosts.push_back(u);
    }
    double producers=0;for(const auto* u:c.own)if(card_producer(*u))++producers;
    for(const auto& k:vines){
        std::vector<const Unit*> pool=hosts;
        if(SHELL_VINES.at(k)=="econ"){
            if(producers>=plan.num("econ_goal",5)+3||mode=="siege")continue;
            stable_sort_by(pool,[&](const Unit* u){return along(c,u->x);});
        }else{
            if(c.me.resource<plan.num("gloom_vine_bank",150))continue;
            stable_sort_by(pool,[&](const Unit* u){return -along(c,u->x);});
        }
        for(size_t i=0;i<pool.size()&&i<4;++i){
            const auto* u=pool[i];
            if(deploy_(c,k,u->x,u->y-24,{},facing_for(c,u->x)).empty()){log["vine:"+after_colon(k)]+=1;return true;}
        }
    }
    return false;
}
std::vector<std::string> PlantV6::rank_cards(Ctx& c,const std::vector<std::string>& keys,const std::string&){
    auto out=keys;stable_sort_by(out,[&](const std::string& k){return -(LOBBERS.count(k)?1.:0.)*50-c.card(k).cost;});return out;
}
bool PlantV6::emergency(Ctx& c,const std::map<std::string,std::vector<std::string>>& by_role,const PlanDict& plan){
    auto instants=role_get(by_role,"instant");for(const auto& k:role_get(by_role,"freeze"))instants.push_back(k);
    if(instants.empty())return false;
    const auto sb_4=*anchor;const auto ax=std::get<0>(sb_4);const auto ay=std::get<1>(sb_4);
    const double reach=(half(c)+plan.num("panic_reach",5))*c.tile;
    std::vector<const Unit*> blob;for(const auto* u:c.enemy)if(u->mobile&&std::abs(wrap_delta(ax,u->x,c.width))<reach&&std::abs(u->y-ay)<220)blob.push_back(u);
    double value=0;for(const auto* u:blob)value+=card_cost(*u,25.);
    const auto biting=nearby(c,70);
    if(value<plan.num("panic_value",200)&&biting.empty())return false;
    stable_sort_by(blob,[&](const Unit* u){return std::abs(wrap_delta(ax,u->x,c.width));});
    const Unit* focus=!biting.empty()?biting[0]:blob[0];
    std::vector<const Unit*> pool=blob.empty()?std::vector<const Unit*>{focus}:blob;
    const auto neighbours=[&](const Unit* u){size_t n=0;for(const auto* v:blob)if(std::abs(wrap_delta(u->x,v->x,c.width))<1.5*c.tile&&std::abs(u->y-v->y)<60)++n;return n;};
    const Unit* center=pool[0];size_t best=neighbours(center);
    for(const auto* u:pool){const auto n=neighbours(u);if(n>best){best=n;center=u;}}
    auto sorted=instants;stable_sort_by(sorted,[&](const std::string& k){return c.card(k).cost;});
    for(const auto& k:sorted){
        if(!c.ready(k,0.))continue;
        const auto beh=c.card(k).behavior;const Unit* tgt;std::vector<Spot> cand;
        if(one_of(beh,{"squash","chomp"})){tgt=focus;cand=spots_near(c,tgt->x-sgn(wrap_delta(ax,tgt->x,c.width))*c.tile,tgt->y,3);}
        else if(beh=="freeze"){if(value<plan.num("freeze_value",400))continue;cand=spots_near(c,c.me.x,c.me.y,4);tgt=center;}
        else{if(value<plan.num("bomb_value",250)&&biting.empty())continue;tgt=center;cand=spots_near(c,tgt->x,tgt->y,4);}
        for(const auto& s:cand)if(place_at(c,k,s.x,s.y,sgn(wrap_delta(s.x,tgt->x,c.width))).empty()){log["panic:"+beh]+=1;return true;}
    }
    return false;
}
bool PlantV6::bomb_cluster(Ctx& c,const std::map<std::string,std::vector<std::string>>& by_role,const PlanDict& plan){
    std::vector<std::string> bombs;for(const auto& k:role_get(by_role,"instant"))if(one_of(c.card(k).behavior,{"ash","doom"})&&c.ready(k,0.))bombs.push_back(k);
    if(bombs.empty())return false;
    const bool rich=c.me.resource>=plan.num("rich",400);
    const double need=!rich?plan.num("cluster_value",300):plan.num("cluster_value_rich",200);
    std::vector<const Unit*> zs;for(const auto* u:c.enemy)if(u->mobile&&in_view(c.me.x,c.me.y,u->x,u->y,c.width))zs.push_back(u);
    if(zs.empty())return false;
    const auto spots=c.spots(true);
    stable_sort_by(bombs,[&](const std::string& k){return c.card(k).cost;});
    for(const auto& k:bombs){
        const double r=(c.card(k).behavior=="ash"?1.5:3.3)*c.tile;
        std::optional<std::pair<double,double>> best;double best_v=0;
        for(const auto& s:spots){
            double v=0;for(const auto* u:zs)if(std::abs(wrap_delta(s.x,u->x,c.width))<r&&std::abs(u->y-s.y)<r)v+=card_cost(*u,25.);
            if(v>best_v){best={s.x,s.y};best_v=v;}
        }
        if(best&&best_v>=need&&place_at(c,k,best->first,best->second,front).empty()){log["cluster_bomb"]+=1;log["cluster_value"]+=best_v;return true;}
    }
    return false;
}
bool PlantV6::grave_bomb(Ctx& c,const std::map<std::string,std::vector<std::string>>& by_role,const PlanDict& plan){
    std::vector<const Unit*> graves;for(const auto* u:c.enemy)if(u->behavior=="grave"&&in_view(c.me.x,c.me.y,u->x,u->y,c.width))graves.push_back(u);
    if(graves.empty())return false;
    std::vector<std::string> bombs;for(const auto& k:role_get(by_role,"instant"))if(one_of(c.card(k).behavior,{"ash","doom"})&&c.ready(k,0.))bombs.push_back(k);
    for(const auto& k:bombs){
        const double r=(c.card(k).behavior=="ash"?1.6:3.5)*c.tile;
        const auto hits=[&](const Unit* g){size_t n=0;for(const auto* h:graves)if(std::abs(wrap_delta(g->x,h->x,c.width))<r&&std::abs(g->y-h->y)<r)++n;return n;};
        const Unit* best=graves[0];size_t bn=hits(best);for(const auto* g:graves){const auto n=hits(g);if(n>bn){bn=n;best=g;}}
        if(double(bn)<plan.num("grave_bomb_min",2))continue;
        for(const auto& s:spots_near(c,best->x,best->y,3))if(place_at(c,k,s.x,s.y,sgn(wrap_delta(s.x,best->x,c.width))).empty()){log["grave_bomb"]+=1;return true;}
    }
    return false;
}
bool PlantV6::strike(Ctx& c,const std::map<std::string,std::vector<std::string>>& by_role){
    const auto& foe=c.foe;const double fdx=c.dx(foe.x);
    for(const auto& k:role_get(by_role,"instant")){
        if(!c.ready(k,0.))continue;
        const auto beh=c.card(k).behavior;std::vector<Spot> cand;
        if(one_of(beh,{"squash","chomp"})&&std::abs(fdx)<3.5*c.tile)cand=spots_near(c,foe.x-sgn(fdx)*c.tile,foe.y,3);
        else if(one_of(beh,{"ash","doom","chili"})&&std::abs(fdx)<4*c.tile)cand=spots_near(c,foe.x,foe.y,3);
        else continue;
        for(const auto& s:cand)if(place_at(c,k,s.x,s.y,sgn(wrap_delta(s.x,foe.x,c.width))).empty()){log["strike"]+=1;return true;}
    }
    return false;
}
bool PlantV6::siege_lobbers(Ctx& c,const std::map<std::string,std::vector<std::string>>& by_role,double bx,double){
    if(std::abs(c.dx(bx))>900)return false;
    const int d=sgn(c.dx(bx));
    auto keys=role_get(by_role,"lob");
    stable_sort_by(keys,[&](const std::string& k){auto f=HERO_KILLERS.find(k);return -(f==HERO_KILLERS.end()?5.:f->second);});
    for(const auto& k:keys){
        if(!c.ready(k,0.))continue;
        std::vector<Spot> cand;for(const auto& s:c.spots(true)){const double v=d*wrap_delta(s.x,bx,c.width);if(150<v&&v<480)cand.push_back(s);}
        stable_sort_by(cand,[&](const Spot& s){return std::abs(c.dx(s.x))+std::abs(s.y-c.me.y)*.7;});
        for(size_t i=0;i<cand.size()&&i<5;++i)if(place_at(c,k,cand[i].x,cand[i].y,d).empty()){log["siege_lob"]+=1;return true;}
    }
    for(const auto& k:role_get(by_role,"wall")){
        if(!c.ready(k,0.))continue;
        std::vector<Spot> cand;for(const auto& s:c.spots(true)){const double v=d*c.dx(s.x);if(60<v&&v<200&&std::abs(s.y-c.me.y)<60)cand.push_back(s);}
        stable_sort_by(cand,[&](const Spot& s){return std::abs(c.dx(s.x));});
        for(size_t i=0;i<cand.size()&&i<3;++i)if(place_at(c,k,cand[i].x,cand[i].y,d).empty()){log["siege_wall"]+=1;return true;}
    }
    return false;
}
std::vector<Spot> PlantV6::spots_near(Ctx& c,double x,double y,size_t n){
    auto s=c.spots(true);
    stable_sort_by(s,[&](const Spot& p){return std::abs(wrap_delta(x,p.x,c.width))+std::abs(p.y-y)*.8;});
    if(s.size()>n)s.resize(n);return s;
}
int PlantV6::wall_side(Ctx& c){
    const double h=half(c);std::map<int,double> counts;
    for(int sd:{front,-front}){
        double n=0;for(const auto* u:c.own){if(card_behavior(*u)!="wall")continue;const double v=sd*wrap_delta(anchor->first,u->x,c.width)/c.tile;if(h-2.5<=v&&v<=h+1.5)++n;}
        counts[sd]=n;
    }
    if(counts[front]==0)return front;
    if(mode=="defend"&&back_share()>=.2&&counts[-front]<counts[front])return -front;
    return front;
}
int PlantV6::facing_for(Ctx& c,double x){
    if(mode=="defend"&&along(c,x)<-.5&&back_share()>=.3)return -front;
    return front;
}
bool PlantV6::place(Ctx& c,const std::string& key,const std::string& r,const PlanDict& plan){
    const auto sb_5=*anchor;const auto ax=std::get<0>(sb_5);const auto ay=std::get<1>(sb_5);const double h=half(c);
    if(r=="wall"){
        const int saved=front;front=wall_side(c);
        struct Restore{int& f;int v;~Restore(){f=v;}} restore{front,saved};
        return place_(c,key,r,plan,ax,ay,h);
    }
    return place_(c,key,r,plan,ax,ay,h);
}
bool PlantV6::place_(Ctx& c,const std::string& key,const std::string& r,const PlanDict& plan,double ax,double ay,double h){
    const auto spots=c.spots(true);
    std::vector<Spot> row;for(const auto& p:spots)if(std::abs(p.y-ay)<12)row.push_back(p);
    std::optional<std::array<double,3>> band;
    if(r=="wall"){band=std::array<double,3>{h-1.5,h+.5,h-.3};if(c.me.resource>plan.num("rich",400))band=std::array<double,3>{h-2.5,h+1.5,h-.3};}
    else if(r=="shoot")band=std::array<double,3>{-h-2,h-1.5,h-2};
    else if(r=="spike")band=std::array<double,3>{h+.5,h+4,h+1};
    else if(r=="mine")band=std::array<double,3>{h+1,h+6,h+3};
    else if(r=="torch")band=std::array<double,3>{-1,h-1.5,h-2.5};
    std::vector<Spot> cand;
    if(band){
        const auto sb_6=*band;const auto lo=std::get<0>(sb_6);const auto hi=std::get<1>(sb_6);const auto want=std::get<2>(sb_6);
        for(const auto& p:row){const double a=along(c,p.x);if(lo<=a&&a<=hi)cand.push_back(p);}
        stable_sort_by(cand,[&](const Spot& p){return std::abs(along(c,p.x)-want);});
    }else if(r=="lob"){
        double back=c.me.resource>plan.num("rich",400)?-9:-6;double front_lim=h-1.5;
        if(c.me.resource>plan.num("very_rich",800)){back=-12;front_lim=h+1;}
        for(const auto& p:spots){const double a=along(c,p.x);if(back<=a&&a<=front_lim)cand.push_back(p);}
        stable_sort_by(cand,[&](const Spot& p){return (std::abs(p.y-ay)<12?3.:0.)+std::abs(along(c,p.x)+1)+std::abs(p.y-ay)/c.tile*.5;});
    }else{
        for(const auto& p:spots)if(along(c,p.x)<=1)cand.push_back(p);
        const double econ_back=plan.num("econ_back",4);
        stable_sort_by(cand,[&](const Spot& p){return (std::abs(p.y-ay)<12?4.:0.)+std::abs(along(c,p.x)+econ_back)+std::abs(p.y-ay)/c.tile*.5;});
    }
    int tries=0;
    for(const auto& p:cand){
        const int facing=r=="wall"?front:facing_for(c,p.x);
        const auto err=place_at(c,key,p.x,p.y,facing);
        if(err.empty())return true;
        if(err!="memo")++tries;
        if(tries>=4)break;
    }
    return false;
}
Cell PlantV6::ground(Ctx& c,double x,double y){
    const auto& tiles=c.b.tiles;const auto row=int64_t(fdiv(y+2,c.tile));const auto col=int64_t(fdiv(pmod(x,c.width),c.tile));
    if(row>=0&&row<int64_t(tiles.size()))return tiles[size_t(row)].at(size_t(col));
    return Cell{};
}
std::string PlantV6::place_at(Ctx& c,const std::string& key,double x,double y,int facing){
    const auto& deck=c.me.deck;(void)deck;
    const auto beh=c.card(key).behavior;
    for(const auto& s:c.obs.empty_supports)
        if(std::abs(wrap_delta(s.position.x,x,c.width))<c.tile*.6&&std::abs(s.position.y-y)<c.tile&&!one_of(beh,{"pot","lily","spike"}))
            return deploy_(c,key,s.position.x,s.plant_y,{},facing);
    if(!one_of(beh,{"pot","lily","gravebuster","coffee","flying56","ghost","vine"})){
        const auto cell=ground(c,x,y);
        const bool water=cell.water;
        const bool natural=one_of(cell.kind,{"土","草","沙","沙土","沙草","雪","空","水"});
        const bool aquatic=flag(c.card(key).aquatic);
        if(water&&!aquatic){
            if(c.me.in_deck("plant:睡莲")&&c.ready("plant:睡莲",0.))return deploy_(c,"plant:睡莲",x,y,{},facing);
            return "need lily";
        }
        if(!water&&!natural&&!c.has_secret("secret:无土栽培")){
            if(beh=="spike")return "spike needs soil";
            if(c.me.in_deck("plant:花盆")&&c.ready("plant:花盆",0.))return deploy_(c,"plant:花盆",x,y,{},facing);
            return "need pot";
        }
    }
    return deploy_(c,key,x,y,{},facing);
}
void PlantV6::step(const View& v,const typed72::AiObservation& o,const PlanDict& plan,const Field& f,Services& s){
    auto c=make_ctx(Seat::plant,v,o,f,s);step_ctx(*c,plan);
}
void PlantV6::step_ctx(Ctx&,const PlanDict&){throw std::logic_error("rv_tactics_v6.PlantTactics.step is not part of the r22 chain");}

// ================================================================= ZOMBIE 61
namespace { const std::set<std::string> FLAGS{"zombie:旗帜僵尸","zombie:黑旗帜僵尸"}; const std::string SCARECROW="zombie:稻草人"; }
void ZombieT61::step(const View& v,const typed72::AiObservation& o,const PlanDict& plan,const Field& f,Services& s){
    auto c=make_ctx(Seat::zombie,v,o,f,s);step_ctx(*c,plan);
}
void ZombieT61::step_ctx(Ctx&,const PlanDict&){throw std::logic_error("rv_ztactics61.ZombieTactics61.step is not part of the r22 chain");}
std::vector<std::string> ZombieT61::deck(Ctx& c){
    std::vector<std::string> out;for(const auto& k:c.me.deck)if(k.rfind("secret:",0)!=0&&k.rfind("zsecret:",0)!=0)out.push_back(k);return out;
}
std::vector<const Unit*> ZombieT61::army(Ctx& c){std::vector<const Unit*> out;for(const auto* u:c.own)if(u->mobile&&u->card_id!=SCARECROW)out.push_back(u);return out;}
double ZombieT61::value(const std::vector<const Unit*>& units){double s=0;for(const auto* u:units)s+=card_cost(*u,25.);return s;}
double ZombieT61::income(Ctx&,const std::vector<const Unit*>& graves){
    double per=0.;
    for(const auto* g:graves){
        if(!card_producer(*g))continue;const auto& card=*g->card;
        const auto get=[](const typed72::Field<double>& f,std::optional<double> d)->std::optional<double>{if(!f.present())return d;if(f.is_null())return std::nullopt;return f.get();};
        const auto mature_yield=get(card.mature_yield,std::nullopt);
        std::optional<double> amount=(g->mature&&mature_yield&&*mature_yield!=0.)?mature_yield:get(card.yield_amount,25.);
        const auto period=get(card.period,16.);
        per+=(amount&&*amount!=0.?*amount:25.)/((period&&*period!=0.)?*period:16.);
    }
    return per;
}
double ZombieT61::wave_goal(Ctx& c,const PlanDict& plan){
    const double base=plan.num("wave_base",300);return std::min(plan.num("wave_cap",1600),base+plan.num("wave_growth",2.5)*c.t);
}
const Unit* ZombieT61::tend(Ctx&,const std::vector<const Unit*>&,const PlanDict&){throw std::logic_error("ZombieTactics61.tend is overridden in r22");}
void ZombieT61::command_logic(Ctx& c,const PlanDict& plan,double foe_home_d,int foe_dir){
    if(c.b.command!="attack"&&!rally){send_("command");return;}
    if(!plan.flag("waves",true))return;
    const auto a=army(c);const double v=value(a);const double goal=wave_goal(c,plan);
    const bool defend=foe_home_d<plan.num("threat_dist",700)+250;
    if(!rally){
        if(!defend&&v<goal*plan.num("regroup_frac",.3)&&c.t-wave_released_at>plan.num("wave_min_gap",15)){
            const double x=pmod(home->first+foe_dir*plan.num("rally_ahead",4)*c.tile,c.width);
            if(send_("rally",{{"x",x},{"y",home->second-c.tile}}).empty()){rally=x;log["rally"]+=1;}
        }
    }else if(v>=goal||defend||c.deathmatch){
        if(send_("rally",{{"clear",true}}).empty()){rally.reset();wave_released_at=c.t;++releases;log["release"]+=1;log["_last_wave"]=double(int64_t(v));}
    }
}
void ZombieT61::deploy_logic(Ctx& c,const PlanDict& plan,const std::vector<const Unit*>& graves,double foe_home_d){
    const auto d=deck(c);
    std::vector<std::string> grave_keys,units;
    for(const auto& k:d)if(c.card(k).behavior=="grave")grave_keys.push_back(k);
    for(const auto& k:d)if(std::find(grave_keys.begin(),grave_keys.end(),k)==grave_keys.end())units.push_back(k);
    std::vector<const Unit*> econ,exits;
    for(const auto* g:graves){if(card_producer(*g))econ.push_back(g);if(z61_in_view(c.me.x,c.me.y,g->x,g->y,c.width))exits.push_back(g);}
    const double target=std::min(plan.num("grave_max",8),plan.num("grave_start",3)+std::trunc(c.t/plan.num("grave_every",35)));
    const bool threatened=foe_home_d<plan.num("threat_dist",700)+300;
    double grave_reserve;
    if(!c.deathmatch&&((double(econ.size())<target&&!threatened)||exits.empty())){
        for(const auto& k:grave_order(c,grave_keys,plan))if(c.ready(k,0.)&&place_grave(c,k,graves))return;
        if(double(econ.size())<plan.num("grave_min",2))return;
        std::optional<double> m;for(const auto& k:grave_keys)if(c.card(k).producer){const double v=c.card(k).cost;if(!m||v<*m)m=v;}
        grave_reserve=m.value_or(0.);
    }else grave_reserve=0;
    if(exits.empty())return;
    std::map<std::string,int64_t> counts;for(const auto* u:c.own)++counts[u->card_id];
    if(std::find(units.begin(),units.end(),SCARECROW)!=units.end()){
        units.erase(std::remove(units.begin(),units.end(),SCARECROW),units.end());
        const double want=std::min(plan.num("scarecrow_max",3),double(1+int64_t(econ.size())/3));
        if(!c.deathmatch&&double(counts[SCARECROW])<want&&c.ready(SCARECROW,grave_reserve)){
            auto ex=exits;stable_sort_by(ex,[&](const Unit* g){return std::abs(wrap_delta(g->x,home->first,c.width));});
            for(size_t i=0;i<ex.size()&&i<3;++i)if(deploy_(c,SCARECROW,ex[i]->x,ex[i]->y-24,ex[i]->id,1).empty()){log["scarecrow"]+=1;return;}
        }
    }
    const auto order=unit_order(c,units,plan);
    const double inc=income(c,graves);
    std::optional<std::string> save;
    for(const auto& k:order){
        const double cost=c.card(k).cost;
        if(double(counts[k])>=plan.quota(k,99))continue;
        const double cd=c.me.cooldown(k,0.)-c.t;
        if(cd<=2&&cost<=c.me.resource+inc*plan.num("save_horizon",6)){save=k;break;}
    }
    const double reserve=grave_reserve;
    for(const auto& k:order){
        if(double(counts[k])>=plan.quota(k,99))continue;
        double need;
        if(save&&k!=*save&&plan.flag("save",true))need=reserve+c.card(*save).cost;else need=reserve;
        if(FLAGS.count(k)&&(exits.size()<3||(!rally&&!threatened)))continue;
        if(!c.ready(k,(save&&k==*save)?reserve:need))continue;
        auto ex=exits;stable_sort_by(ex,[&](const Unit* g){return std::abs(wrap_delta(g->x,c.foe.x,c.width));});
        for(size_t i=0;i<ex.size()&&i<4;++i)
            if(deploy_(c,k,ex[i]->x,ex[i]->y-24,ex[i]->id,sgn(wrap_delta(ex[i]->x,c.foe.x,c.width))).empty())return;
    }
}
std::vector<std::string> ZombieT61::grave_order(Ctx& c,const std::vector<std::string>& keys,const PlanDict&){
    const bool rich=c.me.resource>=200;
    const auto num=[](const typed72::Field<double>& f,std::optional<double> d)->std::optional<double>{if(!f.present())return d;if(f.is_null())return std::nullopt;return f.get();};
    const auto score=[&](const std::string& k){
        const auto& card=c.card(k);
        if(!card.producer)return 9;
        const auto my=num(card.mature_yield,std::nullopt);if(my&&*my!=0.)return c.t<300?0:2;
        const auto ya=num(card.yield_amount,25.);if(!ya)throw std::invalid_argument("yield_amount None");if(*ya>=50)return rich?1:5;
        const auto hp=num(card.hp,75.);if(!hp)throw std::invalid_argument("hp None");if(*hp>=400)return 3;
        return 1;
    };
    auto out=keys;stable_sort_by(out,score);return out;
}
std::vector<std::string> ZombieT61::unit_order(Ctx& c,const std::vector<std::string>& units,const PlanDict& plan){
    double walls=0,lobs=0;for(const auto* u:c.enemy){if(card_behavior(*u)=="wall")++walls;if(card_behavior(*u)=="shoot")++lobs;}
    (void)plan;   // plan.get('unit_bias', {}) is never set by r22
    const auto score=[&](const std::string& k){
        const auto& card=c.card(k);double s=card.cost;const auto& name=card.name;
        const auto has=[&](const char* t){return name.find(t)!=std::string::npos;};
        if(walls>=2&&(has("撑杆")||has("气球")||has("矿工")))s+=150;
        if(lobs>=4&&(has("铁桶")||has("坚果")||has("橄榄")))s+=100;
        return -s;
    };
    auto out=units;stable_sort_by(out,score);return out;
}
bool ZombieT61::place_grave(Ctx& c,const std::string& key,const std::vector<const Unit*>& graves){
    if(key=="zombie:石化藤蔓"){
        std::vector<const Unit*> vined;for(const auto* u:c.own)if(u->card_id==key)vined.push_back(u);
        std::vector<const Unit*> hosts;
        for(const auto* g:graves){
            if(g->card_id==key||!z61_in_view(c.me.x,c.me.y,g->x,g->y,c.width))continue;
            if(std::any_of(vined.begin(),vined.end(),[&](const Unit* v){return std::abs(wrap_delta(v->x,g->x,c.width))<c.tile*.5&&std::abs(v->y-g->y)<c.tile*.5;}))continue;
            hosts.push_back(g);
        }
        stable_sort_by(hosts,[&](const Unit* g){return std::abs(c.dx(g->x));});
        for(size_t i=0;i<hosts.size()&&i<4;++i)if(deploy_(c,key,hosts[i]->x,hosts[i]->y-24).empty())return true;
    }
    const int foe_dir=sgn(wrap_delta(home->first,c.foe.x,c.width));
    const double tx=home->first;
    auto spots=c.spots(true);
    stable_sort_by(spots,[&](const Spot& p){return std::abs(wrap_delta(tx,p.x,c.width))+std::abs(p.y-home->second)*1.5+(foe_dir*wrap_delta(tx,p.x,c.width)>3*c.tile?60.:0.);});
    const bool aquatic=c.card(key).name.rfind("水上",0)==0;
    std::vector<Spot> kept;for(const auto& p:spots)if(p.water==aquatic)kept.push_back(p);
    for(size_t i=0;i<kept.size()&&i<16;++i){
        const auto& p=kept[i];
        if(std::any_of(graves.begin(),graves.end(),[&](const Unit* g){return std::abs(wrap_delta(g->x,p.x,c.width))<1.6*c.tile&&std::abs(g->y-p.y)<c.tile*1.5;}))continue;
        if(deploy_(c,key,p.x,p.y-24).empty())return true;
    }
    return false;
}
} // namespace pvz::typed72app::ai
