#include "sim/typed72_app/ai/layers7.h"
#include "core/pymath.h"
#include <algorithm>
#include <cmath>

namespace pvz::typed72app::ai {
namespace {
double pmod(double a,double b){return py::mod(a,b);}
bool one_of(const std::string& s,std::initializer_list<const char*> set){for(const char* v:set)if(s==v)return true;return false;}
std::vector<std::string> role_get(const std::map<std::string,std::vector<std::string>>& m,const std::string& k){auto f=m.find(k);return f==m.end()?std::vector<std::string>{}:f->second;}
bool flag(const typed72::Field<bool>& f){return f.present()&&!f.is_null()&&f.get();}
}

// --------------------------------------------------------------- safety7
Cell safety_cell(const Ctx& c,double x,double y){
    const auto& rows=c.b.tiles;const auto row=int64_t(std::floor(y/c.tile));
    if(row<0)return Cell{};
    if(row>=int64_t(rows.size())){Cell solid;solid.solid=true;return solid;}
    const auto& line=rows[size_t(row)];
    const auto col=int64_t(std::floor(pmod(x,c.width)/c.tile));
    return line[size_t(pmod(double(col),double(line.size())))];
}
bool wet(const Ctx& c,double x,double y){
    for(double dx:{-.2*c.tile,0.,.2*c.tile})for(double dy:{.1,-.5*c.tile,-1.2*c.tile})if(safety_cell(c,x+dx,y+dy).water)return true;
    return false;
}
bool unit_air(const Ctx& c,const Unit& u){
    if(u.card&&flag(u.card->allow_air))return true;
    const std::string copy=u.copy_card_id.value_or("");
    return copy.size()>6&&c.services.air_plant(copy.substr(6));
}
std::optional<std::pair<double,double>> landing(const Ctx& c,double ux,double uy,bool air){
    std::optional<std::pair<double,double>> air_spot;
    for(int up=0;up<4;++up)for(int dxi:{0,-1,1,-2,2}){
        const double x=pmod(ux+dxi*c.tile,c.width);const double y=uy-up*c.tile;
        if(y<1.5*c.tile||y>=c.b.height)continue;
        bool blocked=false;
        const auto c0=int64_t(std::floor((x-.3*c.tile)/c.tile)),c1=int64_t(std::floor((x+.3*c.tile)/c.tile));
        const auto r0=int64_t(std::floor((y-1.5*c.tile)/c.tile)),r1=int64_t(std::floor((y-.01)/c.tile));
        for(auto col=c0;col<=c1&&!blocked;++col)for(auto row=r0;row<=r1&&!blocked;++row)
            if(safety_cell(c,(double(col)+.5)*c.tile,(double(row)+.5)*c.tile).solid)blocked=true;
        if(blocked)continue;
        bool supported=false;
        for(double off:{-.2*c.tile,0.,.2*c.tile}){const auto cell=safety_cell(c,x+off,y+1);if(cell.solid||cell.water){supported=true;break;}}
        if(supported)return std::pair<double,double>{x,y};
        if(air&&!air_spot)air_spot=std::pair<double,double>{x,y};
    }
    return air_spot;
}
double risk(const Ctx& c,double x,double y){
    double score=c.deathmatch&&wet(c,x,y)?1000.:0.;
    for(const auto* e:c.enemy){
        const double dx=std::abs(wrap_delta(x,e->x,c.width)),dy=std::abs(y-e->y);
        const double cost=card_cost(*e,25.);
        if(e->mobile&&dx<220&&dy<130)score+=(1-dx/220.)*(40+cost*.25);
        const auto& beh=card_behavior(*e);
        if(one_of(beh,{"shoot","reed61","flying56","lob"})){
            const double reach=(e->card&&e->card->range!=0.)?e->card->range:576.;
            const double toward=wrap_delta(e->x,x,c.width)*e->facing;
            if(0<=toward&&toward<reach&&dy<std::max(110.,reach*.65))score+=18+cost*.08;
        }
    }
    const double foe_d=std::hypot(wrap_delta(x,c.foe.x,c.width),y-c.foe.y);
    if(foe_d<280)score+=(280-foe_d)*.15;
    return score;
}

// --------------------------------------------------------------- PlantV7
void PlantV7::step_ctx(Ctx& c,const PlanDict& plan){
    observe_health(c);
    if(!anchor){anchor=home_anchor=find_platform(c,plan);home_platform=platform;siege_anchor.reset();}
    mode=plan.str("mode","defend");
    if(mode=="siege"){
        if(!siege_anchor||siege_established(c,plan))siege_anchor=next_siege_anchor(c,plan);
        anchor=siege_anchor;
        front=siege_dir&&*siege_dir?*siege_dir:sgn(wrap_delta(anchor->first,enemy_base(c).first,c.width));
    }else{
        if(siege_anchor){siege_anchor.reset();siege_dir.reset();platform=home_platform;}
        if(!home_reached){
            if(std::abs(wrap_delta(c.me.x,home_anchor->first,c.width))<40&&std::abs(c.me.y-home_anchor->second)<30)home_reached=true;
            else if(c.t>plan.num("anchor_timeout",8.)){home_anchor=std::pair<double,double>{c.me.x,c.me.y};home_platform.reset();platform.reset();home_reached=true;}
        }
        anchor=home_anchor;front=update_sides(c);
    }
    std::set<std::string> active;for(const auto& r:c.b.resources)active.insert(r.id);
    for(auto i=collected.begin();i!=collected.end();)if(!active.count(*i))i=collected.erase(i);else ++i;
    if(c.t>=(c.me.collect_locked_until&&*c.me.collect_locked_until!=0.?*c.me.collect_locked_until:0.)){
        if(!plan.flag("global_collect",true))throw std::logic_error("r22 plans always use global_collect");
        for(const auto& r:c.b.resources){
            if(c.b.mode&&(*c.b.mode=="coop"||*c.b.mode=="duo")&&r.shared.value_or(false))continue;
            if(r.side==c.side_name&&!r.id.empty()&&!collected.count(r.id)){
                if(send_("collect",{{"resource",r.id}}).empty()){collected.insert(r.id);log["_sun"]+=1;}
            }
        }
    }
    if(std::abs(c.dx(c.foe.x))<c.b.hero_lock_range.value_or(350.)&&std::abs(c.foe.y-c.me.y)<200&&c.t>=log.get("_mark_at",0)){
        const auto error=send_("mark");
        log["_mark_at"]=c.t+(error.empty()?2.5:1.);
        if(error.empty())log["mark"]+=1;
    }
    const bool escaped=escape(c,plan);
    if(!escaped){
        double target=anchor->first;
        if(mode=="defend")target=pmod(target-front*std::min(plan.num("hero_back",1.5),std::max(0.,half(c)-1))*c.tile,c.width);
        auto sb_1=kite_target(c,target,plan);auto t2=std::get<0>(sb_1);auto jump=std::get<1>(sb_1);
        for(const auto& x:c.obs.threats)if(x.projectile&&x.eta_ms<350)jump=true;
        drive(c,t2,jump);
    }
    if(c.t>=tools_at.value_or(0.)){tools_at=c.t+.4;tools(c,plan);}
    if(c.t<next_deploy)return;
    next_deploy=c.t+.3;
    deploy_logic(c,plan);
}
void PlantV7::tools(Ctx& c,const PlanDict& plan){
    std::vector<const Unit*> enemies;for(const auto* u:c.enemy)if(in_view(c.me.x,c.me.y,u->x,u->y,c.width))enemies.push_back(u);
    if(c.has_secret("secret:转向")){
        for(const auto* unit:c.own){
            if(!one_of(card_behavior(*unit),{"shoot","reed61","flying56"})||!in_view(c.me.x,c.me.y,unit->x,unit->y,c.width))continue;
            std::vector<const Unit*> targets;for(const auto* u:enemies)if(std::abs(wrap_delta(unit->x,u->x,c.width))<550&&std::abs(unit->y-u->y)<250)targets.push_back(u);
            if(targets.empty())continue;
            std::map<int,double> weights{{-1,0.},{1,0.}};
            for(const auto* u:targets){const double d=wrap_delta(unit->x,u->x,c.width);weights[sgn(d)]+=(50+card_cost(*u,25.))/(60+std::abs(d));}
            const double old=unit->facing;const int nw=weights[1]>weights[-1]?1:-1;   // dict order -1, 1: first max
            const double old_w=old==1.?weights[1]:old==-1.?weights[-1]:0.;
            if(double(nw)!=old&&weights[nw]>old_w*1.5+.2&&send_("turn",{{"target",unit->id},{"facing",double(nw)}}).empty()){log["turn"]+=1;break;}
        }
    }
    std::vector<const Unit*> cannons;for(const auto* u:c.own)if(u->behavior=="cannon"&&in_view(c.me.x,c.me.y,u->x,u->y,c.width))cannons.push_back(u);
    if(cannons.empty())return;
    std::vector<std::tuple<double,double,double>> clusters;
    for(const auto* u:enemies){
        double value=0;for(const auto* v:enemies)if(std::abs(wrap_delta(u->x,v->x,c.width))<100&&std::abs(u->y-v->y)<120)value+=card_cost(*v,25.);
        clusters.emplace_back(value,u->x,u->y-24);
    }
    if(in_view(c.me.x,c.me.y,c.foe.x,c.foe.y,c.width))clusters.emplace_back(200.,c.foe.x,c.foe.y-24);
    const bool aimed=c.me.cannon_aim_set;
    if(clusters.empty()||std::get<0>(*std::max_element(clusters.begin(),clusters.end()))<plan.num("cannon_value",180)){
        if(aimed)send_("cannon_cancel");
        return;
    }
    const auto sb_2=*std::max_element(clusters.begin(),clusters.end());const auto value=std::get<0>(sb_2);const auto x=std::get<1>(sb_2);const auto y=std::get<2>(sb_2);(void)value;
    if(aimed){if(send_("cannon",{{"x",x},{"y",std::max(0.,y)}}).empty())log["cannon_fire"]+=1;}
    else for(size_t i=0;i<cannons.size()&&i<3;++i)if(send_("cannon",{{"x",cannons[i]->x},{"y",cannons[i]->y-24}}).empty()){log["cannon_select"]+=1;break;}
}
void PlantV7::deploy_logic(Ctx& c,const PlanDict& in){
    PlanDict plan=in;plan.set("rich",99999.);plan.set("very_rich",550.);
    std::vector<std::pair<std::string,std::string>> roles;for(const auto& k:deck(c))roles.emplace_back(k,role(c,k));
    const auto role_of=[&](const std::string& id)->std::string{for(const auto& [k,r]:roles)if(k==id)return r;return "";};
    std::vector<const Unit*> fire,producers;
    for(const auto* u:c.own){const auto r=role_of(u->card_id);if(r=="shoot"||r=="lob")fire.push_back(u);if(card_producer(*u))producers.push_back(u);}
    std::map<std::string,std::vector<std::string>> by_role;for(const auto& [k,r]:roles)by_role[r].push_back(k);
    if((producers.size()>=2&&fire.empty())||(pressure(c)>100&&fire.size()<2)){
        auto guns=role_get(by_role,"lob");for(const auto& k:role_get(by_role,"shoot"))guns.push_back(k);
        stable_sort_by(guns,[&](const std::string& k){return c.card(k).cost;});
        for(const auto& k:guns)if(c.ready(k,0.)&&place(c,k,role_of(k),plan)){log["opening_fire"]+=1;return;}
    }
    if(counter_tools(c,by_role,plan))return;
    const auto cannon=role_get(by_role,"cannon");
    bool have_cannon=false;for(const auto* u:c.own)if(u->behavior=="cannon")have_cannon=true;
    if(fire.size()>=2&&!have_cannon&&c.me.resource>=plan.num("cannon_bank",600))
        for(const auto& k:cannon)if(c.ready(k,150.)&&place(c,k,"lob",plan)){log["cannon_deploy"]+=1;return;}
    PlantV6::deploy_logic(c,plan);
    if(role_get(by_role,"shoot").empty()&&role_get(by_role,"lob").empty()&&c.own.empty())
        for(const auto& k:role_get(by_role,"cannon"))if(c.ready(k,0.)&&place(c,k,"lob",plan))return;
}
bool PlantV7::counter_tools(Ctx& c,const std::map<std::string,std::vector<std::string>>& by_role,const PlanDict& plan){
    bool balloons=false;for(const auto* u:c.enemy)if(u->card_id.find("气球")!=std::string::npos&&in_view(c.me.x,c.me.y,u->x,u->y,c.width))balloons=true;
    bool own_wind=false;for(const auto* u:c.own)if(u->behavior=="wind")own_wind=true;
    if(balloons&&!role_get(by_role,"wind").empty()&&!own_wind)
        for(const auto& k:role_get(by_role,"wind"))if(c.ready(k,50.)&&place(c,k,"econ",plan)){log["wind_deploy"]+=1;return true;}
    auto guns=role_get(by_role,"shoot");for(const auto& k:role_get(by_role,"lob"))guns.push_back(k);
    for(const auto& k:guns)if(flag(c.card(k).aquatic)&&c.ready(k,plan.num("reserve",0))&&place(c,k,role(c,k),plan))return true;
    return false;
}
bool PlantV7::bloom_and_vines(Ctx& c,std::map<std::string,std::vector<std::string>> by_role,const PlanDict& plan){
    if(!c.deathmatch){
        for(const auto& k:role_get(by_role,"bloom")){
            if(!c.ready(k,0.))continue;
            std::vector<Spot> cand;
            for(const auto& p:c.spots(true)){
                if(p.water||risk(c,p.x,p.y+2)>=45)continue;
                bool threat=false;for(const auto* u:c.enemy)if(u->mobile&&std::abs(wrap_delta(p.x,u->x,c.width))<220&&std::abs(p.y-u->y)<150)threat=true;
                if(!threat)cand.push_back(p);
            }
            stable_sort_by(cand,[&](const Spot& p){return risk(c,p.x,p.y+2)+std::abs(c.dx(p.x))*.03;});
            for(size_t i=0;i<cand.size()&&i<6;++i)if(place_at(c,k,cand[i].x,cand[i].y,facing_for(c,cand[i].x)).empty()){log["bloom"]+=1;return true;}
        }
    }
    by_role["bloom"]={};
    return PlantV6::bloom_and_vines(c,by_role,plan);
}
bool PlantV7::place_(Ctx& c,const std::string& key,const std::string& r,const PlanDict& plan,double ax,double ay,double h){
    if(flag(c.card(key).aquatic)&&(r=="shoot"||r=="lob")){
        std::vector<Spot> cand;for(const auto& p:c.spots(true))if(p.water)cand.push_back(p);
        stable_sort_by(cand,[&](const Spot& p){return risk(c,p.x,p.y+2)+std::abs(c.dx(p.x))*.04;});
        for(size_t i=0;i<cand.size()&&i<8;++i)if(place_at(c,key,cand[i].x,cand[i].y,front).empty())return true;
        return false;
    }
    return PlantV6::place_(c,key,r,plan,ax,ay,h);
}
std::pair<double,double> PlantV7::next_siege_anchor(Ctx& c,const PlanDict& plan){
    const auto target=PlantV6::next_siege_anchor(c,plan);
    if(c.deathmatch&&wet(c,target.first,target.second+2))return *home_anchor;
    return target;
}

// -------------------------------------------------------------- ZombieT7
double ZombieT7::income(Ctx& c,const std::vector<const Unit*>& graves){
    double per=0.;
    const auto get=[](const typed72::Field<double>& f,std::optional<double> d)->std::optional<double>{if(!f.present())return d;if(f.is_null())return std::nullopt;return f.get();};
    for(const auto* g:graves){
        if(!card_producer(*g))continue;const auto& card=*g->card;
        const auto mature_yield=get(card.mature_yield,std::nullopt);
        const auto amount=(g->mature&&mature_yield&&*mature_yield!=0.)?mature_yield:get(card.yield_amount,25.);
        const double factor=c.deathmatch?1.:1.-.5*std::min(1.,std::max(0.,g->drowsy_level));
        const auto period=get(card.period,16.);
        per+=(amount&&*amount!=0.?*amount:25.)/((period&&*period!=0.)?*period:16.)*factor;
    }
    return per;
}
void ZombieT7::step_ctx(Ctx& c,const PlanDict& plan){
    observe_health(c);
    if(!home)home=std::pair<double,double>{c.me.x,c.me.y};
    std::vector<const Unit*> graves;for(const auto* u:c.own)if(u->behavior=="grave")graves.push_back(u);
    const double foe_home_d=std::abs(wrap_delta(home->first,c.foe.x,c.width));
    const int foe_dir=sgn(wrap_delta(home->first,c.foe.x,c.width));
    const bool escaped=escape(c,plan);
    const Unit* stale=tend(c,graves,plan);
    if(!escaped){
        double post=pmod(home->first-foe_dir*plan.num("post_back",2)*c.tile,c.width);
        if(foe_home_d<plan.num("threat_dist",650))post=pmod(home->first-foe_dir*6*c.tile,c.width);
        if(std::abs(c.dx(c.foe.x))<400)post=pmod(c.me.x-sgn(c.dx(c.foe.x))*250,c.width);
        std::vector<const Unit*> close;for(const auto* u:c.enemy)if(u->mobile&&std::abs(c.dx(u->x))<130&&std::abs(u->y-c.me.y)<130)close.push_back(u);
        if(!close.empty())post=pmod(c.me.x-sgn(c.dx(close[0]->x))*200,c.width);
        if(stale&&!c.deathmatch&&close.empty()&&risk(c,c.me.x,c.me.y)<30)post=stale->x;
        if(c.deathmatch){
            std::vector<const Unit*> dry;for(const auto* g:graves)if(!wet(c,g->x,g->y))dry.push_back(g);
            if(!dry.empty()){
                const auto key=[&](const Unit* g){return risk(c,g->x,g->y)+std::abs(c.dx(g->x))*.02;};
                const Unit* best=dry[0];double bk=key(best);for(const auto* g:dry){const double k=key(g);if(k<bk){bk=k;best=g;}}
                post=best->x;
            }
        }
        bool jump=false;for(const auto& x:c.obs.threats)if(x.projectile&&x.eta_ms<450)jump=true;
        drive(c,post,jump,25);
    }
    detonate(c,plan);
    command_logic(c,plan,foe_home_d,foe_dir);
    if(c.t<next_deploy)return;
    next_deploy=c.t+.3;
    ZombieT61::deploy_logic(c,plan,graves,foe_home_d);
}
void ZombieT7::command_logic(Ctx& c,const PlanDict& plan,double foe_home_d,int foe_dir){
    const auto before=rally;
    if(before&&c.t-rally_since.value_or(c.t)>plan.num("wave_hold_max",32.)){
        if(send_("rally",{{"clear",true}}).empty()){rally.reset();wave_released_at=c.t;++releases;log["release_timeout"]+=1;}
        return;
    }
    ZombieT61::command_logic(c,plan,foe_home_d,foe_dir);
    if(!before&&rally)rally_since=c.t;
}
std::vector<std::string> ZombieT7::unit_order(Ctx& c,const std::vector<std::string>& units,const PlanDict& plan){
    const auto order=ZombieT61::unit_order(c,units,plan);
    std::vector<const Unit*> exits;for(const auto* g:c.own)if(g->behavior=="grave"&&in_view(c.me.x,c.me.y,g->x,g->y,c.width))exits.push_back(g);
    std::vector<std::string> legal;
    for(const auto& key:order){
        if(!flag(c.card(key).aquatic)){legal.push_back(key);continue;}
        const bool unbounded=!c.ready(key,0.);
        bool can=false;for(const auto* g:exits)if(c.services.preview(key,g->x,g->y-24,g->id,unbounded).empty()){can=true;break;}
        if(can)legal.push_back(key);
    }
    return legal;
}
const Unit* ZombieT7::tend(Ctx& c,const std::vector<const Unit*>& graves,const PlanDict& plan){
    std::set<std::string> live;const Unit* stale=nullptr;
    std::vector<const Unit*> crows;for(const auto* u:c.own)if(u->card_id=="zombie:稻草人")crows.push_back(u);
    for(const auto* g:graves){
        if(!card_producer(*g))continue;
        const auto& gid=g->id;live.insert(gid);
        double* at=tended_at(gid);if(!at){tended.emplace_back(gid,c.t);at=&tended.back().second;}
        const double seen=*at;
        if(std::any_of(crows.begin(),crows.end(),[&](const Unit* s){return std::hypot(wrap_delta(s->x,g->x,c.width),s->y-g->y)<=6*c.tile;})){*tended_at(gid)=c.t;continue;}
        if((c.t-seen>=plan.num("tend_every",12.)||g->drowsy)&&in_view(c.me.x,c.me.y,g->x,g->y,c.width)){
            if(c.t>=log.get("_wake_at",0)&&send_("wake",{{"grave",gid}}).empty()){*tended_at(gid)=c.t;log["wake"]+=1;log["_wake_at"]=c.t+.2;}
        }else if(c.t-seen>=22&&!c.deathmatch&&(!stale||std::abs(c.dx(g->x))<std::abs(c.dx(stale->x))))stale=g;
    }
    std::vector<std::pair<std::string,double>> kept;for(const auto& e:tended)if(live.count(e.first))kept.push_back(e);tended.swap(kept);
    return stale;
}
void ZombieT7::detonate(Ctx& c,const PlanDict& plan){
    if(c.t<detonate_at.value_or(0.))return;
    detonate_at=c.t+.4;
    for(const auto* u:c.own){
        if(u->card_id!="zombie:小丑僵尸"||!in_view(c.me.x,c.me.y,u->x,u->y,c.width))continue;
        double value=0;
        for(const auto* e:c.enemy)if(in_view(c.me.x,c.me.y,e->x,e->y,c.width)&&std::abs(wrap_delta(u->x,e->x,c.width))<75&&std::abs(u->y-e->y)<90)value+=card_cost(*e,0.);
        const bool critical=u->hp<u->max_hp*.25;
        if(value>=plan.num("detonate_value",200)||(critical&&value>=75)){
            if(send_("detonate",{{"target",u->id}}).empty())log["detonate"]+=1;
            break;
        }
    }
}
} // namespace pvz::typed72app::ai
