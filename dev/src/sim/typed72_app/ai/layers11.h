#pragma once
// rv_front7 (Recovery, ForwardPlant, CoverageZombie), rv_tactics64, rv_tactics65
// (Balloon65), rv_tactics10, rv_tactics11. MRO order is preserved:
// P11 > P10 > P65 > Balloon65 > P64 > ForwardPlant > Recovery > P7 ...
// Z11 > Z10 > Z65 > Balloon65 > Z64 > CoverageZombie > Recovery > ZT7 ...
#include "sim/typed72_app/ai/layers7.h"
#include <unordered_map>

namespace pvz::typed72app::ai {

double balloon_hp(Seat side,const Player& me);   // rv_rules65.balloon_hp

template<class Base> class Recovery:public Base {
public:
    double recovery_started=0.;std::optional<double> recovery_landed;std::optional<std::pair<double,double>> recovery_target;
    void observe_health(Ctx& c)override{
        Base::observe_health(c);
        if(c.me.hp<=10&&!this->recovering){
            this->recovering=true;recovery_started=c.t;recovery_landed.reset();recovery_target.reset();this->log["critical_recovery"]+=1;
        }
        if(!this->recovering)return;
        if(c.me.grounded&&c.t-recovery_started>2&&!recovery_landed){recovery_landed=c.t;this->log["recovery_landed"]+=1;}
        if(c.me.hp>=24||(recovery_landed&&c.t-*recovery_landed>18&&this->recent_damage==0)){this->recovering=false;this->log["recovery_completed"]+=1;}
    }
    std::optional<std::pair<double,double>> recovery_post(Ctx& c){
        struct Cand{double score;std::pair<double,double> pos;};std::vector<Cand> cands;
        for(const auto& bucket:c.field.spots)for(const auto& s:bucket){
            if(s.water||std::abs(c.dx(s.x))>480)continue;
            const auto pos=landing(c,s.x,s.y+2,false);
            if(!pos||wet(c,pos->first,pos->second))continue;
            double protection=0;for(const auto* u:c.own)if(std::abs(wrap_delta(s.x,u->x,c.width))<150&&std::abs(s.y-u->y)<100)++protection;
            double score=risk(c,pos->first,pos->second)+std::abs(c.dx(s.x))*.03-protection*3;
            if(recovery_target)score+=std::abs(wrap_delta(s.x,recovery_target->first,c.width))*.02;
            cands.push_back({score,*pos});
        }
        if(!cands.empty()){
            const Cand* best=&cands[0];for(const auto& x:cands)if(x.score<best->score)best=&x;
            recovery_target=best->pos;
        }
        return recovery_target;
    }
    int drive(Ctx& c,double target_x,bool jump_wish=false,double tolerance=20.)override{
        if(this->recovering){
            if(const auto pos=recovery_post(c))target_x=pos->first;
            if(!c.me.grounded)jump_wish=false;
        }
        return Base::drive(c,target_x,jump_wish,tolerance);
    }
};

template<class Base> class Balloon65:public Base {
public:
    void observe_health(Ctx& c)override{
        Base::observe_health(c);
        if(c.me.hp<=balloon_hp(c.side,c.me)&&!this->recovering){
            this->recovering=true;this->recovery_started=c.t;this->recovery_landed.reset();this->recovery_target.reset();this->log["critical_recovery"]+=1;
        }
    }
    void step(const View& v,const typed72::AiObservation& o,const PlanDict& plan,const Field& f,Services& s)override{
        const auto* me=v.player(v.team==Seat::plant?"plant":"zombie");
        if(me&&me->hp<=balloon_hp(v.team,*me)){PlanDict p=plan;p.set("mode",std::string("defend"));return Base::step(v,o,p,f,s);}
        return Base::step(v,o,plan,f,s);
    }
};

// ------------------------------------------------------------------ plants
class ForwardPlant:public Recovery<PlantV7> {
public:
    std::unordered_map<std::string,std::array<double,3>> salvo_positions;
    std::unordered_map<std::string,double> salvo_velocity;
    std::optional<double> salvo_checked,checkpoint_started;
    void observe_health(Ctx&)override;
    double half(Ctx&)override;
    std::pair<double,double> next_siege_anchor(Ctx&,const PlanDict&)override;
    bool siege_established(Ctx&,const PlanDict&)override;
    void step(const View&,const typed72::AiObservation&,const PlanDict&,const Field&,Services&)override;
    bool salvo(Ctx&,const std::map<std::string,std::vector<std::string>>&,const PlanDict&);
    bool emergency(Ctx&,const std::map<std::string,std::vector<std::string>>&,const PlanDict&)override;
    bool bomb_cluster(Ctx&,const std::map<std::string,std::vector<std::string>>&,const PlanDict&)override{return false;}
    bool strike(Ctx&,const std::map<std::string,std::vector<std::string>>&)override;
    void deploy_logic(Ctx&,const PlanDict&)override;
    bool bloom_and_vines(Ctx&,std::map<std::string,std::vector<std::string>>,const PlanDict&)override;
};
class Plant64:public ForwardPlant {
public:
    std::string role(Ctx&,const std::string&)override;
    bool place(Ctx&,const std::string&,const std::string&,const PlanDict&)override;
    std::vector<std::string> rank_cards(Ctx&,const std::vector<std::string>&,const std::string&)override;
};
class Plant65:public Balloon65<Plant64> {
public:
    int siege_blocks=0;
    std::pair<double,double> next_siege_anchor(Ctx&,const PlanDict&)override;
    bool siege_established(Ctx&,const PlanDict&)override;
    std::string place_at(Ctx&,const std::string&,double,double,int)override;
};
class Plant10:public Plant65 {
public:
    void deploy_logic(Ctx&,const PlanDict&)override;
    bool rebuild_economy(Ctx&,const PlanDict&);
    std::vector<std::string> rank_cards(Ctx&,const std::vector<std::string>&,const std::string&)override;
    bool lobs_blocked(Ctx&);
    bool place_(Ctx&,const std::string&,const std::string&,const PlanDict&,double,double,double)override;
};
class Plant11:public Plant10 {
public:
    std::optional<std::map<std::pair<int64_t,int64_t>,double>> dead_spots;
    std::optional<std::vector<std::pair<std::pair<std::string,std::string>,double>>> bad_pot_ground;
    void deploy_logic(Ctx&,const PlanDict&)override;
    double income_floor(Ctx&,const PlanDict&);
    std::string place_at(Ctx&,const std::string&,double,double,int)override;
};

// ----------------------------------------------------------------- zombies
class CoverageZombie:public Recovery<ZombieT7> {
public:
    std::vector<std::string> deck(Ctx&)override;
    bool coverage_deploy(Ctx&,const PlanDict&,const std::vector<const Unit*>& graves);
    void deploy_logic(Ctx&,const PlanDict&,const std::vector<const Unit*>&,double)override;
    void step_ctx(Ctx&,const PlanDict&)override;
};
using Zombie64=CoverageZombie;
class Zombie65:public Balloon65<CoverageZombie> {
public:
    void deploy_logic(Ctx&,const PlanDict&,const std::vector<const Unit*>&,double)override;
};
using Zombie10=Zombie65;
class Zombie11:public Zombie65 {
public:
    std::optional<std::map<std::pair<int64_t,int64_t>,double>> dead_grave_spots;
    bool place_grave(Ctx&,const std::string&,const std::vector<const Unit*>&)override;
};
} // namespace pvz::typed72app::ai
