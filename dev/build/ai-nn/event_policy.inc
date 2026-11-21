// Uses the same resolved cards, wrap geometry, and spatial network for every deck.
using EventFeatures=std::array<double,24>;
inline bool event_enabled=false;
inline std::array<EventFeatures,8> event_hidden{};
inline std::array<double,8> event_bias{},event_head{};
inline double event_scale=0.;
inline long long event_log_tick=-1;
inline void load_event(const ainn::J& j){
    event_enabled=true;
    if(j.at("sim_fingerprint")!=AI_NN_SIM_FINGERPRINT)throw std::runtime_error("event model fingerprint");
    event_hidden=j.at("event_hidden").get<decltype(event_hidden)>();
    event_bias=j.at("event_bias").get<decltype(event_bias)>();
    event_head=j.at("event_head").get<decltype(event_head)>();
    event_scale=j.at("scale").get<double>();
    const auto check=[](const auto& xs){for(double x:xs)if(!std::isfinite(x))throw std::runtime_error("event weights");};
    for(const auto& row:event_hidden)check(row);check(event_bias);check(event_head);
    if(!std::isfinite(event_scale))throw std::runtime_error("event scale");
}

class EventChoices {
    // Compare identities as a set: a destruction and a birth can occur in one observation.
    bool first=true;
    std::set<std::string> old_graves,old_ready,old_affordable;
    double next_probe=0.;
    struct Proposal {Action action;EventFeatures x;double base,value;};
public:
    int changes(const ai::View& v,ai::Services& service){
        std::set<std::string> graves,ready,affordable;
        for(const auto& u:v.units)if(u.hp>0.&&u.side==pvz::typed72::Seat::zombie&&u.behavior=="grave")graves.insert(u.id);
        const auto& me=*v.player("zombie");
        for(const auto& k:me.deck)if(k.starts_with("zombie:")){
            const auto& c=service.card(k);
            if(me.cooldown(k,0.)<=v.time)ready.insert(k);
            if(me.resource>=c.cost)affordable.insert(k);
        }
        int mask=first?16:0;
        if(!first){
            const auto gained=[](const auto& a,const auto& b){return !std::includes(b.begin(),b.end(),a.begin(),a.end());};
            if(gained(graves,old_graves))mask|=1;
            if(gained(old_graves,graves))mask|=2;
            if(gained(ready,old_ready))mask|=4;
            if(gained(affordable,old_affordable))mask|=8;
        }
        first=false;old_graves=std::move(graves);old_ready=std::move(ready);old_affordable=std::move(affordable);
        return mask;
    }
    static EventFeatures describe(const Action& a,const Board& b,int mask){
        double near=30.;
        for(const auto& u:b.v.units)if(u.hp>0.&&u.side==pvz::typed72::Seat::plant)
            near=std::min(near,std::hypot(b.dx(a.x,u.x),(a.y-u.y)/b.v.tile));
        return {double(a.kind==wait),double(a.kind==build),double(a.kind==spawn),double(a.kind==approach),
            std::tanh(a.score/4.),std::tanh(a.cost/180.),std::tanh((b.me.resource-a.cost)/200.),a.source_health,
            a.mobility,a.range,a.damage,std::tanh(b.direction*b.dx(b.me.x,a.x)/6.),std::tanh((b.me.y-a.y)/(4.*b.v.tile)),
            std::exp(-near/4.),std::tanh(b.graves.size()/4.),std::tanh(b.army/6.),std::tanh(b.v.time/160.),
            b.me.hp/std::max(1.,b.me.max_hp),b.foe.hp/std::max(1.,b.foe.max_hp),double(a.producer),
            double(bool(mask&1)),double(bool(mask&2)),double(bool(mask&4)),double(bool(mask&8))};
    }
    static bool legal(const Action& a,const Board& b,ai::Services& service){
        if(a.kind==wait)return true;
        if(a.kind==approach && std::abs(b.dx(b.me.x,a.x))<=1.25)return false;
        const std::optional<std::string> src=a.source.empty()?std::nullopt:std::optional(a.source);
        return service.preview(a.card,a.x,a.y,src,false).empty();
    }
    static ainn::J motion(const Action& a,const Board& b,const Hints& hint,double jump_at){
        if(a.kind==approach){
            const double dx=ai::wrap_delta(b.me.x,a.x,b.v.width);
            const bool jump=b.v.time>=jump_at&&(a.y<b.me.y-b.v.tile*.5||std::abs(dx)>b.v.tile);
            return {{"move",std::abs(dx)<8.?0.:dx>0?1.:-1.},{"jump",jump},{"edge",jump}};
        }
        ainn::J j=ainn::J::object();
        if(hint.has_move)for(const auto& [k,v]:hint.move){
            if(auto p=std::get_if<double>(&v))j[k]=*p;
            else if(auto p=std::get_if<bool>(&v))j[k]=*p;
            else if(auto p=std::get_if<std::string>(&v))j[k]=*p;
        }
        return j;
    }
    static ainn::J command(const Action& a,const Board& b,const Hints& h,double jump_at){
        if(a.kind==spawn||a.kind==build)return {"deploy",a.card,a.source,a.x,a.y,b.dx(a.x,b.foe.x)>=0?1.:-1.};
        return {"motion",motion(a,b,h,jump_at)};
    }
    static ainn::J identity(const Action& a){return {int(a.kind),a.card,a.source,a.x,a.y};}
    void choose(std::vector<Action>& list,const Board& b,ai::Services& service,const Hints& hint,
                int mask,double jump_at){
        // Keep the trained route readout as a prior only when both alternatives exist.
        const Action *now=nullptr,*front=nullptr;
        for(const auto& a:list){
            if(!now&&a.kind==spawn&&legal(a,b,service))now=&a;
            if(!front&&a.kind==approach&&b.dx(b.me.x,a.x)*b.direction>1.5&&legal(a,b,service))front=&a;
            if(now&&front)break;
        }
        std::array<double,4> prior{};
        if(now&&front)prior=Options::values(Options::observe(b,*now,*front));
        std::vector<Proposal> ranked;ranked.reserve(list.size());
        for(const auto& a:list){
            auto x=describe(a,b,mask);
            const int family=a.kind==spawn?1:a.kind==approach||a.kind==build?2:3;
            const double base=x[4]+.22*(prior[family]-prior[0]);double correction=0.;
            if(event_scale!=0.)for(size_t i=0;i<event_hidden.size();++i)
                correction+=event_head[i]*std::tanh(std::inner_product(x.begin(),x.end(),event_hidden[i].begin(),event_bias[i]));
            ranked.push_back({a,x,base,base+event_scale*correction});
        }
        std::stable_sort(ranked.begin(),ranked.end(),[](const auto& a,const auto& b){return a.value>b.value;});
        const auto tick=std::llround(30.*b.v.time);
        const bool fork=forced_option>=0 && tick==std::llround(30.*fork_after);
        const bool probe=mask && (b.v.time>=next_probe||fork);
        std::vector<size_t> picks;std::vector<ainn::J> cmds;
        std::vector<int> valid(ranked.size(),-1);
        const auto add=[&](auto wanted){
            for(size_t i=0;i<ranked.size();++i){
                const auto& a=ranked[i].action;if(!wanted(a))continue;
                if(valid[i]<0)valid[i]=legal(a,b,service);
                if(!valid[i])continue;
                auto sig=command(a,b,hint,jump_at);
                if(std::find(cmds.begin(),cmds.end(),sig)!=cmds.end())continue;
                cmds.push_back(std::move(sig));picks.push_back(i);return true;
            }
            return false;
        };
        add([](const Action&){return true;});if(picks.empty())throw std::runtime_error("missing wait");
        if(probe){
            next_probe=b.v.time+12.;
            const auto& first_action=ranked[picks[0]].action;
            const auto alternate_spawn=[&](const Action& a){return a.kind==spawn&&
                (first_action.kind!=spawn||a.source!=first_action.source);};
            add(alternate_spawn);
            if(picks.size()==1||tick%4==0)add([](const Action& a){return a.kind==spawn;});
            if(picks.size()<4)add([](const Action& a){return a.kind==approach||a.kind==build;});
            if(picks.size()<4)add([](const Action& a){return a.kind==wait;});
            while(picks.size()<4&&add([](const Action&){return true;})){}
        }
        const size_t chosen=fork?size_t(forced_option):0;
        if(chosen>=picks.size())throw std::runtime_error("unavailable event action");
        const auto& best=ranked[picks[chosen]];
        if(mask){
            event_log_tick=tick;
            ainn::J event={{"time",b.v.time},{"mask",mask},{"choice",chosen},{"action",identity(best.action)},
                          {"command",cmds[chosen]},{"legal_comparison",picks.size()}};
            if(probe){
                event["pool"]=ainn::J::array();
                for(size_t j=0;j<picks.size();++j){
                    const auto& p=ranked[picks[j]];
                    event["pool"].push_back({{"act",identity(p.action)},{"cmd",cmds[j]},{"x",p.x},{"base",p.base},{"v",p.value}});
                }
            }
            if(fork){event["forked"]=true;event["prefix"]=option_prefix();}
            option_events.push_back(std::move(event));
        }
        list={best.action};
    }
};
