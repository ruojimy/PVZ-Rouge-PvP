#pragma once
// rv_safety7 (Safety mixin + terrain helpers), rv_tactics_v7.PlantTactics,
// rv_ztactics7.ZombieTactics.
#include "sim/typed72_app/ai/controller.h"
#include <array>
#include <cstdio>

namespace pvz::typed72app::ai {

// rv_safety7 helpers
Cell safety_cell(const Ctx&,double x,double y);          // row<0 -> {}, row>=rows -> solid
bool wet(const Ctx&,double x,double y);
std::optional<std::pair<double,double>> landing(const Ctx&,double x,double y,bool air);   // landing(c, unit)
bool unit_air(const Ctx&,const Unit&);
double risk(const Ctx&,double x,double y);

template<class Base> class Safety:public Base {
public:
    std::map<std::string,double> action_backoff;double now=0.;
    std::vector<std::pair<double,double>> health_samples;std::optional<double> last_health;
    std::optional<std::array<double,3>> hold_refuge;double recent_damage=0.;
protected:
    void bound_send()override{this->send=[this](const std::string& k,const Args& a){return guarded_send(k,a);};}
public:
    static std::string identity(const std::string& kind,const Args& data){
        std::string out=kind;
        for(const char* key:{"target","x","y","resource"}){
            out+='\x1f';const PlanValue* v=nullptr;for(const auto& [k,val]:data)if(k==key)v=&val;
            if(!v||std::holds_alternative<std::monostate>(*v)){out+="N";continue;}
            if(const auto* d=std::get_if<double>(v)){char b[40];std::snprintf(b,sizeof b,"n%.17g",*d);out+=b;}
            else if(const auto* s=std::get_if<std::string>(v))out+="s"+*s;
            else if(const auto* f=std::get_if<bool>(v))out+=*f?"n1":"n0";
            else out+="?";
        }
        return out;
    }
    std::string guarded_send(const std::string& kind,const Args& data){
        static const std::set<std::string> guarded{"teleport","turn","detonate","cannon","mark","collect"};
        const auto id=identity(kind,data);
        if(guarded.count(kind)){auto f=action_backoff.find(id);if(f!=action_backoff.end()&&f->second>now)return "retry backoff";}
        const auto error=this->native_send_(kind,data);
        if(!error.empty()&&guarded.count(kind)){action_backoff[id]=now+(kind=="teleport"?5.:1.);this->log["reject:"+kind]+=1;}
        if(action_backoff.size()>512){std::map<std::string,double> kept;for(const auto& [k,v]:action_backoff)if(v>now)kept.emplace(k,v);action_backoff.swap(kept);}
        return error;
    }
    void observe_health(Ctx& c)override{
        now=c.t;const double hp=c.me.hp;
        if(last_health&&hp<*last_health)health_samples.emplace_back(c.t,*last_health-hp);
        last_health=hp;
        std::vector<std::pair<double,double>> kept;for(const auto& s:health_samples)if(s.first>=c.t-4.)kept.push_back(s);health_samples.swap(kept);
        recent_damage=0.;for(const auto& s:health_samples)recent_damage+=s.second;
    }
    bool escape(Ctx& c,const PlanDict& plan)override{
        if(c.t<c.me.teleport_ready_at.value_or(0.))return false;
        const double hp=c.me.hp/std::max(1.,c.me.max_hp);
        const bool water=c.deathmatch&&wet(c,c.me.x,c.me.y);
        bool shots=false;for(const auto& t:c.obs.threats)if(t.projectile&&t.eta_ms<450)shots=true;
        bool near=false;for(const auto* u:c.enemy)if(u->mobile&&std::abs(c.dx(u->x))<130&&std::abs(u->y-c.me.y)<130)near=true;
        const bool blink=c.side==Seat::plant&&c.has_secret("secret:闪现")&&c.me.hp<=c.me.max_hp-4;
        const bool danger=water||(hp<plan.num("teleport_hp",.65)&&(near||shots||recent_damage>=2));
        if(!danger&&!blink)return false;
        struct Cand{double score;const Unit* unit;std::pair<double,double> pos;};std::vector<Cand> cands;
        for(const auto* u:c.own){
            if(c.side==Seat::zombie&&u->behavior!="grave")continue;
            const auto pos=landing(c,u->x,u->y,unit_air(c,*u));
            if(!pos||(c.deathmatch&&wet(c,pos->first,pos->second)))continue;
            double score=risk(c,pos->first,pos->second);
            score+=std::abs(wrap_delta(c.me.x,pos->first,c.width))*.006;
            cands.push_back({score,u,*pos});
        }
        const double here=risk(c,c.me.x,c.me.y)+std::min(80.,recent_damage*10.);
        stable_sort_by(cands,[](const Cand& x){return x.score;});
        for(size_t i=0;i<cands.size()&&i<3;++i){
            const auto& cd=cands[i];
            if(!blink&&!water&&cd.score>=here-8)continue;
            if(blink&&cd.score>here+5)continue;
            if(this->send_("teleport",{{"target",cd.unit->id}}).empty()){
                this->log[std::string("escape:")+(water?"water":blink?"blink":"damage")]+=1;
                hold_refuge=std::array<double,3>{cd.pos.first,cd.pos.second,c.t+8.};
                this->send_("move",{{"move",0.},{"jump",false},{"edge",false}});
                return true;
            }
        }
        return false;
    }
    int drive(Ctx& c,double target_x,bool jump_wish=false,double tolerance=20.)override{
        if(hold_refuge&&c.t<(*hold_refuge)[2]&&risk(c,(*hold_refuge)[0],(*hold_refuge)[1])<60)target_x=(*hold_refuge)[0];
        if(c.deathmatch){
            const int direction=wrap_delta(c.me.x,target_x,c.width)>=0?1:-1;
            bool crossing=false;for(double off:{24.,48.,96.})if(wet(c,c.me.x+direction*off,c.me.y))crossing=true;
            if(wet(c,c.me.x,c.me.y)||crossing){
                std::vector<Spot> dry;
                for(const auto& bucket:c.field.spots)for(const auto& p:bucket)
                    if(!p.water&&std::abs(wrap_delta(c.me.x,p.x,c.width))<420&&-150<=p.y-c.me.y&&p.y-c.me.y<=72&&!wet(c,p.x,p.y+2))dry.push_back(p);
                if(!dry.empty()){
                    const auto key=[&](const Spot& p){return risk(c,p.x,p.y+2)+std::abs(c.dx(p.x))*.05+std::abs(p.y-c.me.y)*.12;};
                    const Spot* best=&dry[0];double bk=key(dry[0]);for(const auto& p:dry){const double k=key(p);if(k<bk){bk=k;best=&p;}}
                    target_x=best->x;jump_wish=jump_wish||best->y<c.me.y-30;
                }else if(!wet(c,c.me.x,c.me.y))target_x=c.me.x;
            }
        }
        return Base::drive(c,target_x,jump_wish,tolerance);
    }
};

class PlantV7:public Safety<PlantV6> {
public:
    std::optional<double> tools_at;
    std::unique_ptr<Ctx> make_ctx(Seat side,const View& v,const typed72::AiObservation& o,const Field& f,Services& s)override{return std::make_unique<CtxV7>(side,v,o,f,s);}
    void step_ctx(Ctx&,const PlanDict&)override;
    void tools(Ctx&,const PlanDict&)override;
    void deploy_logic(Ctx&,const PlanDict&)override;
    bool counter_tools(Ctx&,const std::map<std::string,std::vector<std::string>>&,const PlanDict&)override;
    bool bloom_and_vines(Ctx&,std::map<std::string,std::vector<std::string>>,const PlanDict&)override;
    bool place_(Ctx&,const std::string&,const std::string&,const PlanDict&,double,double,double)override;
    std::pair<double,double> next_siege_anchor(Ctx&,const PlanDict&)override;
};

class ZombieT7:public Safety<ZombieT61> {
public:
    std::optional<double> rally_since,detonate_at;
    double income(Ctx&,const std::vector<const Unit*>&)override;
    void step_ctx(Ctx&,const PlanDict&)override;
    void command_logic(Ctx&,const PlanDict&,double,int)override;
    std::vector<std::string> unit_order(Ctx&,const std::vector<std::string>&,const PlanDict&)override;
    const Unit* tend(Ctx&,const std::vector<const Unit*>&,const PlanDict&)override;
    void detonate(Ctx&,const PlanDict&)override;
};
} // namespace pvz::typed72app::ai
