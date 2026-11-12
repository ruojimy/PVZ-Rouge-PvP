#pragma once
// rv_tactics14 (+ rv_air66, rv_antiair66), rv_tactics15, rv_tactics17 (SecretExecutor),
// rv_tactics18, rv_tactics19 (TeamSupportMixin + rv_team_support66, rv_firing66).
// Final r22 controllers: Plant19 / Zombie19.
#include "sim/typed72_app/ai/layers11.h"

namespace pvz::typed72app::ai {

// ------------------------------------------------------------ rv_firing66
struct FiringTarget{double x,y,h;};
struct FiringSignature{
    double width=0,tile=0;std::vector<std::vector<bool>> solid;std::vector<std::array<double,3>> targets;
    bool operator==(const FiringSignature&)const=default;
};
struct FiringAssessment{bool allowed=false;std::string reason;double distance=0.;};
struct FiringCache{   // per-Ctx memo (c._firing_memo / c._firing_signature)
    std::map<std::tuple<std::string,int64_t,int64_t,int>,FiringAssessment> memo;
    std::shared_ptr<const FiringSignature> signature;
};
bool ballistic(const ColdCard&);
std::shared_ptr<const FiringSignature> geometry_signature(Ctx&);
FiringAssessment firing_assessment(Ctx&,const std::string& key,double x,double y,int facing);
std::optional<int> firing_direction(Ctx&,const std::string& key,double x,double y,int facing);

// ------------------------------------------------------- rv_team_support66
struct SupportDecision{
    std::string state,reason;double post=0.,reserve=0.;
    std::optional<std::string> mate;double mate_x=0.,mate_y=0.;
};
class TeamSupport {
public:
    bool active=false;double until=0.,cooldown_until=0.;std::optional<double> quiet_since;std::optional<SupportDecision> last;
    std::optional<SupportDecision> decide(Ctx&,std::pair<double,double> home);
private:
    SupportDecision finish(Ctx&,std::pair<double,double> home,const std::string& reason);
};

// ------------------------------------------------------------------ plants
class Plant14:public Plant11 {
public:
    std::optional<int> last_siege_dir;std::optional<double> turn_at;
    std::map<std::string,double> air_retry;   // tactics.__dict__['_air_retry']
    std::vector<const Unit*> invaders(Ctx&);
    int invasion_dir(Ctx&,const std::vector<const Unit*>&);
    int facing_for(Ctx&,double x)override;
    void deploy_logic(Ctx&,const PlanDict&)override;
    std::optional<std::string> economy_gate(Ctx&,const PlanDict&,const std::vector<const Unit*>&);
    bool repel(Ctx&,const PlanDict&,const std::vector<const Unit*>&);
    bool place(Ctx&,const std::string&,const std::string&,const PlanDict&)override;
    bool support_allowed(Ctx&,const std::string&,const PlanDict&);
    bool place_(Ctx&,const std::string&,const std::string&,const PlanDict&,double,double,double)override;
    bool place_support(Ctx&,const std::string&,const PlanDict&,double,double,double);
    bool place_dense(Ctx&,const std::string&,const PlanDict&,double,double,double);
    bool place_air(Ctx&,const std::string&,const PlanDict&,double,double,double);
    void tools(Ctx&,const PlanDict&)override;
    void turn_guns(Ctx&);
    int route_dir(Ctx&,double frm,double bx)override;
    void step(const View&,const typed72::AiObservation&,const PlanDict&,const Field&,Services&)override;
};
class Plant15:public Plant14 {
public:
    std::optional<double> idle_bank;std::vector<std::pair<double,double>> tried_anchors;
    void deploy_logic(Ctx&,const PlanDict&)override;
    void reroute_if_stuck(Ctx&,const PlanDict&);
    std::optional<std::pair<int,std::pair<double,double>>> far_anchor(Ctx&,const PlanDict&);
    bool spend_overflow(Ctx&,const PlanDict&);
};
using Plant17=Plant15;
class Plant18:public Plant17 {
public:
    const View* snap_=nullptr;bool front_set=false;   // self._snap (coop/pve/duo), self._front_set
    std::string place_at(Ctx&,const std::string&,double,double,int)override;
    void step(const View&,const typed72::AiObservation&,const PlanDict&,const Field&,Services&)override;
    void pick_front(const View&,const typed72::AiObservation&,const PlanDict&,const Field&,Services&);
    int drive(Ctx&,double post,bool jump_wish=false,double tolerance=20.)override;
    double rescue_post(Ctx&,const View&,double post);
};

// ----------------------------------------------------------------- zombies
class Zombie14:public Zombie11 {
public:
    std::optional<double> antiair_rally_at;
    void deploy_logic(Ctx&,const PlanDict&,const std::vector<const Unit*>&,double)override;
    void command_logic(Ctx&,const PlanDict&,double,int)override;
    std::optional<std::pair<double,double>> flank_point(Ctx&,int foe_dir);
};
using Zombie15=Zombie14;
class SecretExecutor {
public:
    std::map<std::string,double> ready;std::vector<std::pair<std::string,double>> log;   // log: insertion order
    bool due(const std::string& key,double t,double every);
    void count(const std::string& key);
    void run(const std::function<std::string(const std::string&,const Args&)>& send,Ctx& c);
};
class Zombie17:public Zombie15 {
public:
    SecretExecutor secrets;
    void step(const View&,const typed72::AiObservation&,const PlanDict&,const Field&,Services&)override;
};
class Zombie18:public Zombie17 {
public:
    std::set<std::string> pickups_served;std::optional<double> defence_flag;
    void deploy_logic(Ctx&,const PlanDict&,const std::vector<const Unit*>&,double)override;
    std::vector<std::string> walkers(Ctx&,const PlanDict&,const std::vector<std::string>* keys=nullptr);
    bool relic_deploy(Ctx&,const PlanDict&,const std::vector<const Unit*>&);
    bool secondhand_deploy(Ctx&,const PlanDict&,const std::vector<const Unit*>&);
    void command_logic(Ctx&,const PlanDict&,double,int)override;
    std::optional<std::pair<double,double>> pickup_rally(Ctx&,double x,double y);
    bool confluence_defence(Ctx&);
    std::optional<std::pair<double,double>> kill_zone(Ctx&,double x,double y);
    int drive(Ctx&,double post,bool jump_wish=false,double tolerance=20.)override;
    double aura_post(Ctx&,double post);
};

// ------------------------------------------------------- TeamSupportMixin
template<class Base> class TeamSupportMixin:public Base {
public:
    TeamSupport support;std::optional<SupportDecision> support_decision;
    struct LadderRoute{int64_t col=0;double x=0.,goal_y=0.;bool up=false;double until=0.,progress_at=0.,y=0.;bool engaged=false;};
    std::optional<LadderRoute> ladder_route;double ladder_backoff_until=0.;
    bool assisting()const{return support_decision&&(support_decision->state=="assist"||support_decision->state=="rescue");}
    int drive(Ctx& c,double post,bool jump_wish=false,double tolerance=20.)override;
    std::optional<int> ladder_drive(Ctx& c,double post,double goal_y);
};

class Plant19:public TeamSupportMixin<Plant18> {
public:
    struct Failure{std::shared_ptr<const FiringSignature> signature;double until;int64_t repeats;};
    std::vector<std::pair<std::tuple<std::string,int64_t,int64_t,int>,Failure>> lane_failures;   // dict, insertion order
    bool lane_blocked=false;std::optional<std::string> last_blocked_card;
    std::shared_ptr<const FiringSignature> lane_wait_signature;   // nullptr = None
    std::string role(Ctx&,const std::string&)override;
    bool counter_tools(Ctx&,const std::map<std::string,std::vector<std::string>>&,const PlanDict&)override;
    std::optional<int> lane_direction(Ctx&,const std::string&,double x,double y,int facing);
    std::string place_at(Ctx&,const std::string&,double,double,int)override;
    std::string try_deploy(Ctx&,const std::string&,double,double,const std::optional<std::string>& grave={},int facing=1)override;
    bool place_(Ctx&,const std::string&,const std::string&,const PlanDict&,double,double,double)override;
    bool replan_firing(Ctx&,const PlanDict&);
    void step(const View&,const typed72::AiObservation&,const PlanDict&,const Field&,Services&)override;
    void deploy_logic(Ctx&,const PlanDict&)override;
};
class Zombie19:public TeamSupportMixin<Zombie18> {
public:
    bool support_rally=false;
    void command_logic(Ctx&,const PlanDict&,double,int)override;
    void deploy_logic(Ctx&,const PlanDict&,const std::vector<const Unit*>&,double)override;
};
} // namespace pvz::typed72app::ai
