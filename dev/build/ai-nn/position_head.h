#pragma once
// Shared state-action readout. The room validates the command selected by this policy.
#include "sim/typed72_app/ai/controller.h"
#include "common.h"
#include "ai_nn_build.h"
#include <algorithm>
#include <array>
#include <fstream>
#include <numeric>
#include <set>

namespace position_ai {
using namespace pvz::typed72app;
using Args=ai::Args;
using Send=std::function<std::string(const std::string&,const Args&)>;
using Weights=std::array<double,32>;
inline Weights weights{};
inline std::array<Weights,8> hidden{};
inline std::array<double,8> bias{},output{};
inline bool active=false;
inline ainn::J events=ainn::J::array();
inline void load(const std::string& path) {
    active=!path.empty();events=ainn::J::array();
    if(!active)return;
    std::ifstream input(path);const auto j=ainn::J::parse(input);
    if(j.at("format")!="pvz-legal-action-readout-1" || j.at("sim_fingerprint")!=AI_NN_SIM_FINGERPRINT ||
       j.at("weights").size()!=weights.size())throw std::runtime_error("Incompatible tactical model");
    weights=j.at("weights").get<Weights>();
    hidden=j.at("hidden").get<decltype(hidden)>();
    bias=j.at("bias").get<decltype(bias)>();output=j.at("output").get<decltype(output)>();
    const auto check=[](const auto& v){for(double w:v)if(!std::isfinite(w)||std::abs(w)>16.)throw std::runtime_error("Bad tactical weight");};
    check(weights);for(const auto& row:hidden)check(row);check(bias);check(output);
}
inline std::string string_arg(const Args& args,const char* key) {
    for(const auto& [k,v]:args)if(k==key&&std::holds_alternative<std::string>(v))return std::get<std::string>(v);
    return {};
}
enum Kind { wait, build, spawn, approach, hold, flag, release, order };
struct Action {
    Kind kind;double x=0.,y=0.;std::string card,source;double cost=0.,source_health=0.,score=0.;
    bool producer=false;double mobility=0.,range=0.,damage=0.;
};
struct Board {
    const ai::View& v;
    const ai::Player& me;
    const ai::Player& foe;
    std::vector<const ai::Unit*> graves;
    double direction,army=0.;
    explicit Board(const ai::View& view):v(view),me(*v.player("zombie")),foe(*v.player("plant")),
        direction(ai::wrap_delta(me.x,foe.x,v.width)>=0?1.:-1.) {
        for(const auto& u:v.units)if(u.hp>0&&u.side==pvz::typed72::Seat::zombie){
            if(u.behavior=="grave")graves.push_back(&u);
            if(u.mobile)army+=1.;
        }
    }
    double dx(double from,double to)const{return ai::wrap_delta(from,to,v.width)/v.tile;}
    void evaluate(Action& a,const std::string& hint,int flag_hint,bool order_hint)const {
        const double forward=std::tanh(direction*dx(me.x,a.x)/7.);
        const double height=std::tanh((me.y-a.y)/(v.tile*4.));
        const double near_me=std::exp(-std::hypot(dx(me.x,a.x),(me.y-a.y)/v.tile)/4.);
        double enemy=std::hypot(dx(foe.x,a.x),(foe.y-a.y)/v.tile),spacing=20.,support=0.;
        for(const auto& u:v.units)if(u.hp>0){
            const double d=std::hypot(dx(a.x,u.x),(a.y-u.y)/v.tile);
            if(u.side==pvz::typed72::Seat::plant)enemy=std::min(enemy,d);
            else if(u.mobile)support+=std::max(0.,1.-d/6.);
            else if(u.behavior=="grave"&&u.id!=a.source)spacing=std::min(spacing,d);
        }
        const double danger=std::exp(-enemy/4.);
        const double hurt=1.-me.hp/std::max(1.,me.max_hp);
        const double reserve=std::tanh((me.resource-a.cost)/250.);
        const bool field=a.kind==build||a.kind==spawn||a.kind==approach||a.kind==flag;
        Weights x={double(a.kind==wait),double(a.kind==build),double(a.kind==spawn),double(a.kind==approach),
            double(a.kind==hold),double(a.kind==flag),double(a.kind==release),
            double(!hint.empty()&&a.card==hint),double(hint.empty()&&a.kind==wait),
            double((a.kind==flag&&flag_hint==1)||(a.kind==release&&flag_hint==2)||(a.kind==hold&&!flag_hint)),
            field*forward,field*height,field*near_me,field*danger,field*std::tanh(spacing/5.),
            field*std::tanh(support/3.),a.source_health,a.cost/500.,double(a.producer),a.mobility,
            field*forward*(hurt+danger)*.5,field*forward*reserve,
            a.kind==build?1./(1.+graves.size()):0.,a.kind==approach?danger*hurt:0.,
            a.kind==release?std::tanh(army/5.):0.,a.kind==spawn?danger*a.mobility:0.,
            a.range,a.damage,danger*a.range,reserve*a.damage,double(a.kind==order&&order_hint),
            a.kind==order?(v.command=="follow"?1.:-1.):0.};
        a.score=std::inner_product(x.begin(),x.end(),weights.begin(),0.);
        for(size_t k=0;k<hidden.size();++k)
            a.score+=output[k]*std::tanh(std::inner_product(x.begin(),x.end(),hidden[k].begin(),bias[k]));
    }
};
struct Hints {
    std::string card,source;int rally=0;Args move;bool has_move=false,order_hint=false;
    std::string capture(const std::string& kind,const Args& args,const Send& send) {
        if(kind=="deploy"){if(card.empty()){card=string_arg(args,"card");source=string_arg(args,"grave");}return {};}
        if(kind=="rally"){rally=std::any_of(args.begin(),args.end(),[](const auto& v){return v.first=="clear";})?2:1;return {};}
        if(kind=="command"){order_hint=true;return {};}
        if(kind=="move"){move=args;has_move=true;return {};}
        return send(kind,args);
    }
};
class Tactics {
    double next_action=0.,next_flag=0.,move_until=0.,target_x=0.,target_y=0.,jump_at=-1.;
    std::string target_card;
    using Point=std::pair<double,double>;
    std::vector<ai::Spot> points(const Board& b,const ai::Field& f) const {
        std::vector<ai::Spot> out;std::set<Point> seen;
        for(int z=0;z<ai::Field::ZONES;++z)
            for(const auto* origin:{&b.me,&b.foe})
                for(const auto& s:f.candidates(z,origin->x,origin->y,3))
                    if(seen.emplace(s.x,s.y).second)out.push_back(s);
        return out;
    }
    void sort(std::vector<Action>& list,const Board& b,const Hints& h)const {
        for(auto& a:list)b.evaluate(a,h.card,h.rally,h.order_hint);
        std::stable_sort(list.begin(),list.end(),[](const auto& a,const auto& b){return a.score>b.score;});
    }
    void record(const Board& b,const Action& a,const Hints& h,size_t choices,size_t legal_exits=0) {
        static const char* names[]={"wait","build","spawn","approach","hold","flag","release","order"};
        events.push_back({{"t",b.v.time},{"kind",names[a.kind]},{"card",a.card},{"source",a.source},{"x",a.x},{"y",a.y},
            {"hero", {b.me.x,b.me.y}},{"foe",{b.foe.x,b.foe.y}},{"choices",choices},{"preview_legal_exits",legal_exits},
            {"native_card",h.card},{"native_source",h.source},{"score",a.score}});
    }
public:
    void step(const ai::View& v,const ai::Field& field,ai::Services& service,const Hints& hint,const Send& send){
        const auto& me=*v.player("zombie");
        const bool arrived=!target_card.empty()&&std::abs(ai::wrap_delta(me.x,target_x,v.width))<=1.25*v.tile;
        bool at_order=v.time>=next_action || arrived || (!hint.card.empty()&&v.time>=next_action-.65);
        const bool flag_due=v.time>=next_flag || (hint.rally&&v.time>=next_flag-2.);
        if(at_order||flag_due){
            Board b(v);const auto cells=points(b,field);
            if(at_order){
                next_action=v.time+1.;std::vector<Action> list{{wait,me.x,me.y}};
                for(const auto& key:me.deck){
                    if(key.rfind("zombie:",0)!=0)continue;
                    const auto& card=service.card(key);
                    if(card.cost>me.resource||me.cooldown(key,0.)>v.time||(v.deathmatch&&card.producer))continue;
                    auto add=[&](Kind kind,double x,double y,const std::string& grave="",double hp=0.){
                        Action a{kind,x,y,key,grave,card.cost,hp};a.producer=card.producer;
                        a.mobility=std::tanh(card.speed/60.);a.range=std::tanh(card.range/400.);
                        a.damage=std::tanh(card.damage/std::max(.1,card.interval)/60.);list.push_back(a);};
                    if(card.behavior=="grave"){
                        for(const auto& pos:cells){
                            const double y=pos.y-24.;
                            add(build,pos.x,y);
                            if(std::abs(b.dx(me.x,pos.x))>1.25)add(approach,pos.x,y);
                        }
                        // Keep a cached travel destination available after crossing a zone boundary.
                        if(arrived&&key==target_card)add(build,target_x,target_y);
                    }else for(const auto* g:b.graves)
                        add(spawn,g->x,g->y-24.,g->id,g->hp/std::max(1.,g->max_hp));
                }
                sort(list,b,hint);
                if(arrived){target_card.clear();move_until=0.;}
                for(const auto& a:list){
                    if(a.kind==wait){record(b,a,hint,list.size());break;}
                    if(a.kind==approach){
                        // Only pursue terrain that matches this grave's substrate.
                        const bool aquatic=service.card(a.card).name.rfind("水上",0)==0;
                        if(std::none_of(cells.begin(),cells.end(),[&](const ai::Spot& s){return s.x==a.x&&s.y-24.==a.y&&s.water==aquatic;}))continue;
                        target_card=a.card;target_x=a.x;target_y=a.y;move_until=v.time+2.5;
                        record(b,a,hint,list.size());break;
                    }
                    const std::optional<std::string> src=a.source.empty()?std::nullopt:std::optional(a.source);
                    if(!service.preview(a.card,a.x,a.y,src,false).empty())continue;
                    const double facing=b.dx(a.x,b.foe.x)>=0?1.:-1.;
                    Args args={{"card",a.card},{"x",a.x},{"y",a.y},{"facing",facing}};
                    if(src)args.emplace_back("grave",*src);
                    size_t legal=0;
                    if(a.kind==spawn)for(const auto* g:b.graves)
                        legal+=service.preview(a.card,g->x,g->y-24.,g->id,false).empty();
                    if(!send("deploy",args).empty())continue;
                    record(b,a,hint,list.size(),legal);target_card.clear();move_until=0.;break;
                }
            }
            if(flag_due){
                next_flag=v.time+3.;
                std::vector<Action> flags{{hold,me.x,me.y}};
                if(v.rally_point)flags.push_back({release,me.x,me.y});
                else flags.push_back({order,me.x,me.y});
                for(const auto& pos:cells)flags.push_back({flag,pos.x,pos.y-v.tile});
                sort(flags,b,hint);
                for(const auto& a:flags){
                    if(a.kind==hold)break;
                    if(a.kind==order){if(send("command",{}).empty()){record(b,a,hint,flags.size());break;}continue;}
                    if(a.kind==flag&&v.rally_point&&std::hypot(b.dx(v.rally_point->first,a.x),(v.rally_point->second-a.y)/v.tile)<.5)break;
                    Args args=a.kind==release?Args{{"clear",true}}:Args{{"x",a.x},{"y",a.y}};
                    if(send("rally",args).empty()){record(b,a,hint,flags.size());break;}
                }
            }
        }
        if(!target_card.empty()&&v.time<move_until){
            const double dx=ai::wrap_delta(me.x,target_x,v.width);
            const bool jump=v.time>=jump_at&&(target_y<me.y-v.tile*.5||std::abs(dx)>v.tile);
            if(jump)jump_at=v.time+.55;
            send("move",{{"move",std::abs(dx)<8.?0.:dx>0?1.:-1.},{"jump",jump},{"edge",jump}});
        }else if(hint.has_move)send("move",hint.move);
    }
};
}

