#pragma once
// Typed port of the r22 controller chain (modkit/pvp/rv_tactics*.py & co).
// Python MRO is linearised into single inheritance; mixins (Safety, Recovery,
// Balloon65, TeamSupportMixin) are templates over their MRO successor.
// This file: Ctx, Controller (rv_tactics_v6), PlantV6, ZombieT61.
#include "sim/typed72_app/ai/view.h"
#include <functional>
#include <set>
#include <tuple>

namespace pvz::typed72app::ai {

double wrap_delta(double a,double b,double width);           // rv_observation.wrap_delta
inline int sgn(double v){return v>=0.?1:-1;}
bool in_view(double hx,double hy,double x,double y,double width);
constexpr double VIEW_HALF_WIDTH=480.,VIEW_ABOVE=384.,VIEW_BELOW=256.;

// Python Counter/dict log: numeric values, also read back for control.
struct Log {
    std::map<std::string,double> v;
    double& operator[](const std::string& k){return v[k];}
    double get(const std::string& k,double d=0.)const{auto f=v.find(k);return f==v.end()?d:f->second;}
};


struct Ctx {
    Ctx(Seat side,const View& view,const typed72::AiObservation& obs,const Field& field,Services& services);
    Seat side;std::string side_name;
    const View& b;const typed72::AiObservation& obs;const Field& field;Services& services;
    double t,width,tile;
    const Player& me;const Player& foe;
    std::vector<const Unit*> living,own,enemy;
    bool night,deathmatch;
    double dx(double x)const{return wrap_delta(me.x,x,width);}
    const ColdCard& card(const std::string& key)const{return services.card(key);}
    // c.ready may be replaced for a call (income floor / economy gate / team support).
    std::function<bool(const std::string&,double)> ready;
    bool base_ready(const std::string& key,double reserve)const;
    // c.spots may be replaced (dead grave spots, firing lanes); spots_impl is Ctx/v7 Ctx.
    std::function<std::vector<Spot>(bool)> spots;
    virtual std::vector<Spot> spots_impl(bool free);
    virtual ~Ctx()=default;
    std::map<bool,std::vector<Spot>> spot_cache;
    // tactics14.tools temporarily hides 转向 from c.me['secrets'].
    bool hide_turn_secret=false;
    bool has_secret(const std::string& s)const{return !(hide_turn_secret&&s=="secret:转向")&&me.has_secret(s);}
    // firing66 per-observation memo/signature live on the Ctx (attached lazily in V).
    std::shared_ptr<void> firing_cache;
};
// rv_tactics_v7.Ctx: 密植 spots.
struct CtxV7:Ctx {
    using Ctx::Ctx;
    std::vector<Spot> spots_impl(bool free)override;
};

class Controller {
public:
    virtual ~Controller()=default;
    void bind(std::function<std::string(const std::string&,const Args&)> send){native_send_=std::move(send);bound_send();}
    // The entry AISeat calls: controller.step(side, snap, obs, plan, field).
    virtual void step(const View&,const typed72::AiObservation&,const PlanDict&,const Field&,Services&)=0;
    Log log;
    // ---- Controller state (rv_tactics_v6.Controller.__init__) ----
    double next_deploy=0.,next_jump=0.;bool jump_down=false;
    std::optional<std::pair<double,double>> last_pos;bool blocked=false;
    std::map<std::string,double> failed;
    std::optional<double> stuck_since;double detour_until=0.;   // getattr(..., None/0.)
    // self.send: replaceable for one call (flanking / placed rally wrappers).
    std::function<std::string(const std::string&,const Args&)> send;
    std::string send_(const std::string& kind,Args data={}){return send(kind,data);}
    virtual int drive(Ctx&,double target_x,bool jump_wish=false,double tolerance=20.);
    int controller_drive(Ctx& c,double target_x,bool jump_wish=false,double tolerance=20.){return Controller::drive(c,target_x,jump_wish,tolerance);}
    virtual std::string try_deploy(Ctx&,const std::string& key,double x,double y,const std::optional<std::string>& grave={},int facing=1);
    // self.try_deploy may be shadowed for one call (tactics11 dead grave spots).
    std::function<std::string(Ctx&,const std::string&,double,double,const std::optional<std::string>&,int)> try_deploy_hook;
    std::string deploy_(Ctx& c,const std::string& key,double x,double y,const std::optional<std::string>& grave={},int facing=1){
        return try_deploy_hook?try_deploy_hook(c,key,x,y,grave,facing):try_deploy(c,key,x,y,grave,facing);
    }
    // Safety hooks (no-ops below Safety).
    virtual void observe_health(Ctx&){}
    virtual bool escape(Ctx&,const PlanDict&){return false;}
    virtual std::unique_ptr<Ctx> make_ctx(Seat side,const View& v,const typed72::AiObservation& o,const Field& f,Services& s){return std::make_unique<Ctx>(side,v,o,f,s);}
    // getattr(self,'home_anchor'/'home'/'anchor', None) for team-support mixins.
    virtual std::optional<std::pair<double,double>> home_point()const{return std::nullopt;}
    virtual std::optional<std::pair<double,double>> anchor_point()const{return std::nullopt;}
    virtual void set_anchor(std::pair<double,double>){}
    virtual bool is_recovering()const{return false;}   // getattr(controller,'recovering',False)
protected:
    std::function<std::string(const std::string&,const Args&)> native_send_;
    virtual void bound_send(){send=native_send_;}
};

// ===================================================================== PLANT
class PlantV6:public Controller {
public:
    // state (PlantTactics.__init__ and lazily created attributes)
    std::optional<std::pair<double,double>> anchor,home_anchor,siege_anchor;
    int front=0;                        // None until the first step
    std::string mode="defend";
    std::set<std::string> collected;
    std::optional<double> arrived_at;
    std::optional<std::array<double,2>> platform,home_platform;   // (start_x, end_x)
    bool home_reached=false;
    std::optional<int> siege_dir;
    std::optional<std::map<int,double>> side_threat;double st_time=0.;int main_front=1;

    void step(const View&,const typed72::AiObservation&,const PlanDict&,const Field&,Services&)override;
    virtual void step_ctx(Ctx&,const PlanDict&);
    int update_sides(Ctx&);
    double back_share()const;
    virtual bool siege_established(Ctx&,const PlanDict&);
    virtual int route_dir(Ctx&,double frm,double bx);
    virtual std::pair<double,double> next_siege_anchor(Ctx&,const PlanDict&);
    std::optional<std::pair<double,double>> find_platform(Ctx&,const PlanDict&,std::optional<double> around={},int min_len=4);
    std::pair<double,bool> kite_target(Ctx&,double post,const PlanDict&);
    std::pair<double,double> enemy_base(Ctx&);
    std::vector<const Unit*> nearby(Ctx&,double radius,std::optional<double> x={},std::optional<double> y={});
    std::vector<std::string> deck(Ctx&);
    virtual std::string role(Ctx&,const std::string& key);
    double along(Ctx&,double x);
    virtual double half(Ctx&);
    virtual void deploy_logic(Ctx&,const PlanDict&);
    virtual bool bloom_and_vines(Ctx&,std::map<std::string,std::vector<std::string>> by_role,const PlanDict&);
    virtual std::vector<std::string> rank_cards(Ctx&,const std::vector<std::string>& keys,const std::string& role);
    double pressure(Ctx&);
    size_t front_walls(Ctx&,const std::map<std::string,std::string>& roles);
    virtual bool emergency(Ctx&,const std::map<std::string,std::vector<std::string>>& by_role,const PlanDict&);
    virtual bool bomb_cluster(Ctx&,const std::map<std::string,std::vector<std::string>>& by_role,const PlanDict&);
    bool grave_bomb(Ctx&,const std::map<std::string,std::vector<std::string>>& by_role,const PlanDict&);
    virtual bool strike(Ctx&,const std::map<std::string,std::vector<std::string>>& by_role);
    bool siege_lobbers(Ctx&,const std::map<std::string,std::vector<std::string>>& by_role,double bx,double by);
    std::vector<Spot> spots_near(Ctx&,double x,double y,size_t n);
    int wall_side(Ctx&);
    virtual int facing_for(Ctx&,double x);
    virtual bool place(Ctx&,const std::string& key,const std::string& role,const PlanDict&);
    virtual bool place_(Ctx&,const std::string& key,const std::string& role,const PlanDict&,double ax,double ay,double half);
    Cell ground(Ctx&,double x,double y);
    virtual std::string place_at(Ctx&,const std::string& key,double x,double y,int facing);
    // v7 additions, declared here so mixin layers can dispatch them.
    virtual void tools(Ctx&,const PlanDict&){}
    virtual bool counter_tools(Ctx&,const std::map<std::string,std::vector<std::string>>&,const PlanDict&){return false;}
    // Python's `getattr(self,'recovering',False)` (Recovery layer state).
    bool recovering=false;
    std::optional<std::pair<double,double>> home_point()const override{return home_anchor;}
    std::optional<std::pair<double,double>> anchor_point()const override{return anchor;}
    void set_anchor(std::pair<double,double> a)override{anchor=a;}
    bool is_recovering()const override{return recovering;}
};

// ==================================================================== ZOMBIE
class ZombieT61:public Controller {
public:
    std::optional<std::pair<double,double>> home;
    std::optional<double> rally;
    double wave_released_at=-999.;int64_t releases=0;
    std::vector<std::pair<std::string,double>> tended;   // dict, insertion order
    // ztactics61.in_view as seen by functions defined in rv_ztactics61 (tactics18 解除封印 patches it).
    bool unrestricted_exits=false;
    bool z61_in_view(double hx,double hy,double x,double y,double width)const{return unrestricted_exits||in_view(hx,hy,x,y,width);}

    void step(const View&,const typed72::AiObservation&,const PlanDict&,const Field&,Services&)override;
    virtual void step_ctx(Ctx&,const PlanDict&);
    virtual std::vector<std::string> deck(Ctx&);
    std::vector<const Unit*> army(Ctx&);
    static double value(const std::vector<const Unit*>&);
    virtual double income(Ctx&,const std::vector<const Unit*>& graves);
    double wave_goal(Ctx&,const PlanDict&);
    virtual const Unit* tend(Ctx&,const std::vector<const Unit*>& graves,const PlanDict&);
    virtual void command_logic(Ctx&,const PlanDict&,double foe_home_d,int foe_dir);
    virtual void deploy_logic(Ctx&,const PlanDict&,const std::vector<const Unit*>& graves,double foe_home_d);
    std::vector<std::string> grave_order(Ctx&,const std::vector<std::string>& keys,const PlanDict&);
    virtual std::vector<std::string> unit_order(Ctx&,const std::vector<std::string>& units,const PlanDict&);
    virtual bool place_grave(Ctx&,const std::string& key,const std::vector<const Unit*>& graves);
    virtual void detonate(Ctx&,const PlanDict&){}
    bool recovering=false;
    std::optional<std::pair<double,double>> home_point()const override{return home;}
    bool is_recovering()const override{return recovering;}
    double* tended_at(const std::string& id){for(auto& [k,v]:tended)if(k==id)return &v;return nullptr;}
};

// Helpers shared by layers.
const std::string& card_behavior(const Unit&);           // (u.get('card') or {}).get('behavior') or ""
double card_cost(const Unit&,double fallback);           // (u.get('card') or {}).get('cost', fallback)
bool card_producer(const Unit&);
std::string card_name(const Unit&);                      // (u.get('card') or {}).get('name','')
template<class T,class K> void stable_sort_by(std::vector<T>& v,K key){std::stable_sort(v.begin(),v.end(),[&](const T& a,const T& b){return key(a)<key(b);});}
} // namespace pvz::typed72app::ai
