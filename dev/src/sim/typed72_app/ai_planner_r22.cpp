// Typed r22 planner. Each block names the Python method it reproduces
// (modkit/pvp/rv_*.py); semantics, including defaults of missing card fields
// and Python's operator precedence, are kept line for line.
#include "sim/typed72_app/ai_planner_r22.h"
#include "sim/typed/ai_geometry.h"
#include <algorithm>
#include <cmath>
#include <stdexcept>

namespace pvz::typed72app {
using typed72::Seat;
using typed72::AiUnitView;
namespace {
constexpr double LATE=405.;   // rv_r10.LATE
bool alive(const AiUnitView& u){return u.hp>0.;}
// (u.get('card') or {}).get('cost', fallback)
double cost(const AiUnitView& u,double fallback){return u.card_info.cost?*u.card_info.cost:fallback;}
bool behavior_in(const AiUnitView& u,std::initializer_list<const char*> set){
    for(const char* b:set)if(u.card_info.behavior==b)return true;return false;
}
// k.split(":")[1]
std::string card_name(const std::string& key){
    const auto a=key.find(':');if(a==std::string::npos)throw std::invalid_argument("card key without side: "+key);
    const auto b=key.find(':',a+1);return key.substr(a+1,b==std::string::npos?std::string::npos:b-a-1);
}
bool starts(const std::string& s,const char* prefix){return s.rfind(prefix,0)==0;}
std::vector<std::string> playable(std::span<const std::string> deck){
    std::vector<std::string> out;for(const auto& k:deck)if(!starts(k,"secret:")&&!starts(k,"zsecret:"))out.push_back(k);return out;
}
double plant_quota(const std::string& name){   // rv_r2.PLANT_QUOTA, default 30
    static const std::map<std::string,double> q{{"向日葵",6},{"双子向日葵",4},{"阳光菇",6},{"坚果",3},{"高坚果",2},{"窝瓜",3},{"樱桃炸弹",2},{"土豆地雷",3}};
    const auto f=q.find(name);return f==q.end()?30.:f->second;
}
double zombie_quota(const std::string& name){  // rv_r3.ZOMBIE_QUOTA (shadows r2's), default 60
    static const std::map<std::string,double> q{{"海盗船长",3},{"橄榄球僵尸",4},{"旗帜僵尸",1},{"黑旗帜僵尸",1}};
    const auto f=q.find(name);return f==q.end()?60.:f->second;
}
// rv_rules65.balloon_hp(side, player) -> pvp.balance.balloon_hp(side, deck)
double balloon_hp(Seat side,std::span<const std::string> deck){
    return side==Seat::zombie&&std::find(deck.begin(),deck.end(),"zombie:坚固脑光墓碑")!=deck.end()?12.:10.;
}
// r7/r8 pressure: enemy mobile value within 350 px and 200 px vertically.
double pressure(const AiPlannerInput& in,double reach_x,double reach_y){
    double sum=0.;
    for(const auto& u:in.units)if(u.side!=in.side&&alive(u)&&u.mobile&&
        std::abs(typed72::ai_wrap_delta(in.me.x,u.position.x,in.width))<reach_x&&std::abs(u.position.y-in.me.y)<reach_y)sum+=cost(u,25.);
    return sum;
}
size_t own_count(const AiPlannerInput& in,std::initializer_list<const char*> behaviors){
    size_t n=0;for(const auto& u:in.units)if(u.side==in.side&&alive(u)&&behavior_in(u,behaviors))++n;return n;
}
size_t own_producers(const AiPlannerInput& in){
    size_t n=0;for(const auto& u:in.units)if(u.side==in.side&&alive(u)&&u.card_info.producer)++n;return n;
}
}

AiPlannerR22::AiPlannerR22(Seat side):side_(side){
    if(side!=Seat::plant&&side!=Seat::zombie)throw std::invalid_argument("AI planner side must be a team");
}

// rv_r10.Agent.ahead / army
bool AiPlannerR22::ahead(const AiPlannerInput& in)const{
    const auto army=[&](Seat side){double s=0.;for(const auto& u:in.units)if(u.side==side&&alive(u)&&!u.card_info.producer)s+=cost(u,0.);return s;};
    const Seat foe=side_==Seat::plant?Seat::zombie:Seat::plant;
    const double mine=army(side_),theirs=army(foe);
    return mine>=1.3*theirs+100.&&in.me.hp>=in.foe.hp-5.&&in.me.hp>.5*in.me.max_hp;
}

// rv_r10.Agent.econ_goal over rv_r9.Agent.econ_goal
int64_t AiPlannerR22::econ_goal(const AiPlannerInput& in){
    const double t=in.time;
    int64_t goal;
    {   // r9
        const auto fire=int64_t(own_count(in,{"shoot","reed61","flying56","mortar"}));
        const double p=pressure(in,500.,250.);
        if(p>250.&&fire<2){goal=2;hit("econ_emergency");}
        else{
            goal=t<60.?4:t<150.?5:6;
            if(in.me.resource>600.)++goal;
            goal=std::min<int64_t>(goal,2+2*fire);
        }
    }
    const auto prods=int64_t(own_producers(in));
    const auto fire=int64_t(own_count(in,{"shoot","reed61","flying56","mortar"}));
    peak_econ_=std::max(peak_econ_,prods);
    if(goal<=2)return goal;
    const int64_t cap=3+2*fire;
    if(t<LATE){
        goal=std::max(goal,std::min(peak_econ_,cap));
        if(ahead(in)||in.me.resource>=450.){
            goal=std::min<int64_t>({goal+(in.me.resource>=450.?3:2),cap,10});hit("econ_expand");
        }
    }
    return goal;
}

// rv_r10.Agent.grave_plan
void AiPlannerR22::grave_plan(const AiPlannerInput& in,AiPlanR22& plan){
    const double t=in.time;
    const auto graves=int64_t(own_producers(in));
    peak_graves_=std::max(peak_graves_,graves);
    const double start=plan.grave_start,cap=plan.grave_max,every=plan.grave_every;
    const double ramp=std::min(cap,start+std::trunc(t/every));
    double target=std::max(ramp,std::min(double(peak_graves_),cap));
    if(t<LATE&&(ahead(in)||in.me.resource>=500.)&&cap>=7.){target=std::min(10.,std::max(target,double(graves+1)));hit("grave_expand");}
    if(t>=LATE){target=std::min(target,ramp);hit("grave_late");}
    plan.grave_start=target;plan.grave_max=target;plan.grave_every=1e9;
    notes_["grave_target"]=int64_t(target);
}

AiPlanR22 AiPlannerR22::plan(const AiPlannerInput& in){
    if(in.side!=side_)throw std::invalid_argument("AI planner input is for the other team");
    if(!(in.width>0.))throw std::invalid_argument("AI planner needs the map width");
    const double t=in.time;
    AiPlanR22 plan;plan.side=side_;
    // ---- rv_r7.Agent.plan (prefix shared by both sides)
    const double press=pressure(in,350.,200.);
    if(in.foe.hp<last_enemy_hp_)last_attack_at_=t;
    last_enemy_hp_=in.foe.hp;
    if(side_==Seat::plant){
        const auto fire=own_count(in,{"shoot","reed61","flying56"});
        if(press>=160.)last_pressure_at_=t;
        const double hp=in.me.hp/std::max(1.,in.me.max_hp);
        const bool stalled=t-last_attack_at_>90.;
        const bool start=t>=55.&&fire>=2&&in.me.resource>=75.&&press<120.&&hp>.75&&t-last_pressure_at_>6.;
        if(start||(stalled&&fire>=3&&in.me.resource>=600.&&press<160.&&hp>.8)){
            if(mode_!="siege")hit("pushes");
            mode_="siege";push_until_=t+15.;
        }
        if(mode_=="siege"&&(hp<.5||press>350.)){mode_="defend";last_pressure_at_=t;hit("retreats");}
        if(in.recovering||in.me.hp<=10.){mode_="defend";hit("recovering_or_low");}
        // rv_r2.Agent.plan, plant branch, with forced_mode = mode (its own pressure
        // census only feeds the non-forced mode logic and so cannot change the plan).
        plan.priority=playable(in.deck);
        for(const auto& k:plan.priority)plan.quotas.emplace_back(k,plant_quota(card_name(k)));
        plan.mode=mode_;
        // r7 update (r2's econ_goal 5 / reserve 0 / siege_gap 420 ... are all overwritten or kept as below)
        int64_t goal=fire<2||press>180.||hp<.65?2:4;
        if(in.me.resource>700.&&fire>=4&&press<120.)goal=5;
        plan.econ_goal=double(goal);plan.wall_goal=1.;plan.reserve=0.;plan.siege_gap=240.;plan.teleport_hp=.7;
        plan.panic_value=120.;plan.bomb_value=150.;plan.siege_step=3.;plan.siege_dwell=8.;plan.siege_lobs=2.;
        plan.rich=99999.;plan.vine_reserve=75.;plan.global_collect=true;
        // ---- rv_r8.Agent.plan
        {
            const auto fire64=own_count(in,{"shoot","reed61","flying56","mortar","spring"});
            if(fire64>=2&&t>65.&&in.me.hp>30.&&in.me.resource>150.&&press<120.&&!in.recovering){mode_="siege";plan.mode=mode_;hit("r8_siege");}
            plan.wall_goal=1.;
        }
        // ---- rv_r9.Agent.plan (r10 econ_goal)
        plan.econ_goal=double(econ_goal(in));
    }else{
        // rv_r3.Agent.plan zombie branch (reached through r7 -> r4 -> r3)
        const auto deck=playable(in.deck);
        for(const auto& k:deck)plan.quotas.emplace_back(k,zombie_quota(card_name(k)));
        for(const auto& k:deck)if(k.find("墓碑")==std::string::npos)plan.priority.push_back(k);
        plan.grave_start=3.;plan.grave_max=7.;plan.grave_every=45.;plan.save_horizon=3.;plan.wave_base=300.;
        plan.wave_growth=1.5;plan.wave_cap=1000.;plan.wave_hold_max=32.;plan.teleport_hp=.7;plan.tend_every=12.;plan.detonate_value=200.;
        if(press>250.){plan.grave_start=2.;plan.grave_max=4.;plan.save=false;hit("zombie_pressure");}
        if(in.me.resource>=700.){
            hit("zombie_rich_quotas");
            for(const auto& key:plan.priority){
                if(key.find("旗帜")!=std::string::npos||key.find("稻草")!=std::string::npos)continue;
                auto q=std::find_if(plan.quotas.begin(),plan.quotas.end(),[&](const auto& e){return e.first==key;});
                if(q==plan.quotas.end())plan.quotas.emplace_back(key,16.);else q->second=std::max(q->second,16.);
            }
        }
    }
    // ---- rv_r9.Agent.plan balloon guard (both sides)
    if(in.me.hp<=balloon_hp(side_,in.deck)){
        if(side_==Seat::plant)mode_="defend";
        else mode_=plan.mode.value_or("defend");
        plan.mode=mode_;hit(side_==Seat::plant?"balloon_defend":"zombie_balloon_defend");
    }
    // ---- rv_r10.Agent.plan
    if(side_==Seat::zombie)grave_plan(in,plan);
    // ---- rv_r12.Agent.plan: siege_guard is 0 in r13+, so the veto never runs.
    // ---- rv_r15.Agent.plan: economy-first siege gate
    if(side_==Seat::plant&&plan.mode==std::optional<std::string>("siege")){
        const auto producers=int64_t(own_producers(in));
        const double econ=plan.econ_goal==0.?4.:plan.econ_goal;   // plan.get('econ_goal', 4) or 4
        const double goal=std::min(4.,econ);
        const bool rich=in.me.resource>=600.;
        if(double(producers)<goal&&t<150.&&!rich&&!ahead(in)){mode_="defend";plan.mode=mode_;hit("siege_wait_econ");}
    }
    return plan;
}

} // namespace pvz::typed72app
