// Included in position_ai after Board, Action, and the inherited position scorer.
using OptionState = std::array<double,22>;
inline ainn::J option_events, option_policy;
inline std::function<std::string()> option_prefix;
inline int forced_option=-1;
inline double fork_after=0.;
inline void configure_options(const std::string& file, int forced, double after) {
    option_events=ainn::J::array(); option_policy=nullptr; forced_option=forced; fork_after=after;
    if(file.empty())return;
    std::ifstream stream(file); stream>>option_policy;
    if(option_policy.at("format")!="pvz-native-option-value-1" ||
       option_policy.at("sim_fingerprint")!=AI_NN_SIM_FINGERPRINT)
        throw std::runtime_error("incompatible option value network");
    const auto matrix=[](const ainn::J& a,size_t n,size_t m){
        if(a.size()!=n)throw std::runtime_error("option matrix rows");
        for(const auto& row:a){
            if(row.size()!=m)throw std::runtime_error("option matrix columns");
            for(double x:row)if(!std::isfinite(x))throw std::runtime_error("option matrix weight");
        }
    };
    matrix(option_policy.at("hidden"),8,23);matrix(option_policy.at("head"),4,9);
    if(!std::isfinite(option_policy.at("margin").get<double>()))throw std::runtime_error("option threshold");
}
class Options {
    double next=0.,end=0.,tx=0.,ty=0.;
    int phase=0;
    std::string card,source;
    std::set<std::string> former;
    size_t event_id=0;
    static double clip(double x){return std::tanh(x);}
    static double hp(const ai::Player& p){return p.hp/std::max(1.,p.max_hp);}
    static double exposure(const Board& b,double x,double y){
        double threat=0.;
        for(const auto& u:b.v.units)if(u.hp>0. && u.side==pvz::typed72::Seat::plant){
            const double dist=std::hypot(b.dx(x,u.x),(y-u.y)/b.v.tile);
            const double reach=u.card?std::max(1.,u.card->range/b.v.tile):1.;
            const double rate=u.card?std::max(0.,u.card->damage)/std::max(.25,u.card->interval):0.;
            threat+=std::exp(-dist/reach)*std::min(3.,.2+rate/30.);
        }
        return clip(threat/3.);
    }
    static OptionState observe(const Board& b,const Action& now,const Action& front){
        double plants=0.,health=0.,near=1000.;
        for(const auto& u:b.v.units)if(u.hp>0. && u.side==pvz::typed72::Seat::plant)++plants;
        for(const auto* g:b.graves){
            health+=g->hp/std::max(1.,g->max_hp);
            near=std::min(near,std::hypot(b.dx(g->x,front.x),(g->y-front.y)/b.v.tile));
        }
        return {hp(b.me),hp(b.foe),clip(b.me.resource/250.),clip(b.foe.resource/250.),
                clip(b.graves.size()/4.),clip(b.army/6.),clip(plants/8.),health/std::max<size_t>(1,b.graves.size()),
                clip(b.v.time/150.),double(b.v.map_night),clip(std::abs(b.dx(b.me.x,b.foe.x))/14.),
                clip(std::abs(b.dx(b.me.x,front.x))/7.),clip((b.me.y-front.y)/(4.*b.v.tile)),
                clip(near/7.),exposure(b,front.x,front.y),exposure(b,now.x,now.y),
                now.source_health,clip(now.cost/180.),clip(front.cost/180.),
                clip((b.me.resource-now.cost-front.cost)/180.),now.mobility,now.damage};
    }
    static std::array<double,4> values(const OptionState& state){
        std::array<double,8> h{};
        for(size_t i=0;i<h.size();++i){
            const auto& w=option_policy["hidden"][i];double v=w[22];
            for(size_t j=0;j<state.size();++j)v+=state[j]*w[j].get<double>();
            h[i]=std::tanh(v);
        }
        std::array<double,4> scores{};
        for(size_t i=0;i<scores.size();++i){
            const auto& w=option_policy["head"][i];scores[i]=w[8];
            for(size_t j=0;j<h.size();++j)scores[i]+=h[j]*w[j].get<double>();
        }
        return scores;
    }
    void finish(std::string outcome,double time){
        option_events[event_id]["end"]=time;option_events[event_id]["status"]=std::move(outcome);phase=0;
    }
public:
    bool traveling()const{return phase==2;}
    void apply(std::vector<Action>& list,const Board& b,ai::Services& service){
        if(forced_option<0 && option_policy.is_null())return;
        const double t=b.v.time;
        if(phase && t>=end)finish(phase==3?"saved":"expired",t);
        if(!phase && t>=next && (forced_option<0 || (option_events.empty() && t>=fork_after))){
            next=t+1.;
            const Action *now=nullptr,*front=nullptr;
            for(const auto& a:list){
                if(!now && a.kind==spawn && service.preview(a.card,a.x,a.y,a.source,false).empty())now=&a;
                if(!front && a.kind==approach){
                    const double dx=b.dx(b.me.x,a.x)*b.direction;
                    if(dx<1.5 || dx>8. || std::abs(b.me.y-a.y)>4.*b.v.tile)continue;
                    if(std::abs(b.dx(a.x,b.foe.x))>=std::abs(b.dx(b.me.x,b.foe.x))-1.)continue;
                    if(std::any_of(b.graves.begin(),b.graves.end(),[&](const auto* g){
                        return std::abs(b.dx(g->x,a.x))<1. && std::abs(g->y-24.-a.y)<b.v.tile;
                    }))continue;
                    if(!service.preview(a.card,a.x,a.y,std::nullopt,false).empty())continue;
                    front=&a;
                }
                if(now && front)break;
            }
            if(now && front){
                const auto state=observe(b,*now,*front);
                auto q=std::array<double,4>{};
                int chosen=forced_option;
                if(chosen<0){
                    q=values(state);chosen=int(std::max_element(q.begin(),q.end())-q.begin());
                    if(q[chosen]-q[0]<option_policy["margin"].get<double>())chosen=0;
                }
                event_id=option_events.size();
                option_events.push_back({{"time",t},{"x",state},{"choice",chosen},{"values",q},
                    {"proposed_spawn",{now->card,now->source}},{"proposed_front",{front->card,front->x,front->y}},
                    {"status",chosen?"started":"continue"},{"origin",{b.me.x,b.me.y}}});
                if(forced_option>=0)option_events.back()["prefix"]=option_prefix();
                next=t+32.;phase=chosen;end=t+(chosen==3?6.:14.);
                if(chosen==1){source=now->source;card=now->card;}
                if(chosen==2){
                    card=front->card;tx=front->x;ty=front->y;source.clear();former.clear();
                    for(const auto* g:b.graves)former.insert(g->id);
                }
            }
        }
        if(!phase)return;
        const Action pause{wait,b.me.x,b.me.y};
        if(phase==3){list={pause};return;}
        if(phase==4 && source.empty()){
            const ai::Unit* closest=nullptr;double best=2.;
            for(const auto* g:b.graves)if(!former.count(g->id) && g->card_id==card){
                const double d=std::hypot(b.dx(g->x,tx),(g->y-24.-ty)/b.v.tile);
                if(d<best){closest=g;best=d;}
            }
            if(closest)source=closest->id;
        }
        if(phase==4 && !source.empty() && std::none_of(b.graves.begin(),b.graves.end(),[&](auto g){return g->id==source;})){
            finish("new grave lost",t);return;
        }
        std::vector<Action> choices;
        if(phase==2){
            Action a{approach,tx,ty,card};
            if(std::abs(b.dx(b.me.x,tx))<=1.25 && service.preview(card,tx,ty,std::nullopt,false).empty())a.kind=build;
            choices.push_back(a);
        }else{
            for(const auto& a:list)if(a.kind==spawn && a.source==source && (phase==4 || a.card==card))choices.push_back(a);
        }
        choices.push_back(pause);list=std::move(choices);
    }
    void accepted(const Board& b,const Action& a){
        if(!phase)return;
        if(phase==2 && a.kind==build){
            option_events[event_id]["built"]={{"time",b.v.time},{"card",a.card},{"target",{a.x,a.y}},{"hero",{b.me.x,b.me.y}}};
            phase=4;end=b.v.time+10.;
        }else if((phase==1 || phase==4) && a.kind==spawn){
            option_events[event_id]["spawn"]={{"time",b.v.time},{"source",a.source},{"card",a.card}};
            finish(phase==4?"front built and deployed":"deployed now",b.v.time);
        }
    }
};
