// The match driver can observe either frozen policy or enable the learned first switch.
class SwitchControl {
    bool initialized=false, handed=false, marked=false;
    double deadline=0.,origin=0.;
    std::optional<Action> route;
    std::set<std::string> prior_graves;
    std::optional<Action> pending;
    double pending_at=0.;
public:
    static std::vector<double> features(const Board& b, int mask,const Action* target) {
        Action a=target?*target:Action{wait,b.me.x,b.me.y};
        auto spatial=EventChoices::describe(a,b,mask);
        std::vector<double> x(spatial.begin(),spatial.end());
        x.push_back(std::tanh(std::abs(b.dx(b.me.x,b.foe.x))/10.));
        x.push_back(std::tanh(b.foe.resource/300.));
        x.push_back(double(b.v.map_night));
        x.push_back(double(b.v.deathmatch));
        x.push_back(std::tanh((b.foe.y-b.me.y)/(4.*b.v.tile)));
        int foe_count=0;
        for(const auto& u:b.v.units)if(u.hp>0.&&u.side==pvz::typed72::Seat::plant)++foe_count;
        x.push_back(std::tanh(foe_count/8.));
        return x;
    }
    static double predict(const std::vector<double>& x,const ainn::J& m){
        double value=m.at("bias");
        const auto& w=m.at("linear");
        for(size_t i=0;i<x.size();++i)value+=x[i]*w.at(i).get<double>();
        const auto& hidden=m.at("hidden");
        for(size_t j=0;j<hidden.size();++j){
            double u=m.at("hb").at(j);
            for(size_t i=0;i<x.size();++i)u+=x[i]*hidden.at(j).at(i).get<double>();
            value+=std::tanh(u)*m.at("head").at(j).get<double>();
        }
        return value;
    }
    void begin(const ai::View& v){
        if(!initialized){handed=switch_policy.at("start")=="event";initialized=true;}
        event_enabled=handed;
        if(route&&v.time>deadline){switch_events.push_back({{"t",v.time},{"phase","expired"}});route.reset();}
        if(!pending)return;
        for(const auto& u:v.units)if(u.hp>0.&&u.side==pvz::typed72::Seat::zombie&&u.behavior=="grave"&&!prior_graves.count(u.id)
            &&std::hypot(ai::wrap_delta(u.x,pending->x,v.width),u.y-pending->y)<2.*v.tile){
            switch_events.push_back({{"t",v.time},{"phase","grave"},{"id",u.id},{"x",u.x},{"y",u.y}});pending.reset();break;
        }
        if(pending&&v.time-pending_at>2.)pending.reset();
    }
    bool forced(double t) const {return !marked&&switch_force>=0&&std::llround(t*30)>=std::llround(switch_after*30);}
    bool examine(double t,int mask) const {return forced(t)||(!handed && mask && switch_policy.contains("gate"));}
    bool traveling() const {return route.has_value();}
    // Compare the best legal forward destination from the shared spatial head, or the
    // exact recorded destination during a historical intervention.
    int decide(std::vector<Action>& list,const Board& b,ai::Services& svc,int mask){
        const bool fork=forced(b.v.time);
        auto wanted=switch_policy.find("target");
        const Action* front=nullptr;
        for(const auto& a:list)if(a.kind==approach && b.direction*b.dx(b.me.x,a.x)>1.25
          && (wanted==switch_policy.end()||EventChoices::identity(a)==*wanted)&&EventChoices::legal(a,b,svc)){front=&a;break;}
        auto state=features(b,mask,nullptr),site=features(b,mask,front);
        int choice=handed?1:0;
        double q=0.,f=0.;
        if(fork)choice=switch_force;
        else if(switch_policy.contains("gate")){
            q=predict(state,switch_policy.at("gate"));
            f=front?predict(site,switch_policy.at("front")):-100.;
            double margin=switch_policy.at("margin"),front_margin=switch_policy.at("front_margin");
            choice=q>margin?1:0;
            if(front&&f>front_margin&&q+f>margin)choice=2;
        }
        if(fork||(choice!=0&&!handed)){
            ainn::J ev={{"t",b.v.time},{"phase","decision"},{"choice",choice},{"mask",mask},{"state",state},{"site",site},
                {"front",front?EventChoices::identity(*front):ainn::J(nullptr)},{"q",q},{"f",f}};
            if(fork){
                marked=true;
                auto prefix=option_prefix();ev["prefix"]=prefix;
                option_events.push_back({{"forked",true},{"time",b.v.time},{"choice",choice},{"mask",mask},{"prefix",prefix}});
            }
            switch_events.push_back(std::move(ev));
        }
        if(choice>0)handed=true;
        event_enabled=handed;
        if(choice>=2&&front){
            route=*front;deadline=b.v.time+10.;origin=b.me.x;
            if(choice==3)deadline=b.v.time; // direct placement at the same site, without travel
        }
        return choice;
    }
    Action next(const Board& b,ai::Services& svc,bool direct){
        Action a=*route;
        if(direct || (std::abs(b.dx(b.me.x,a.x))<=1.25 && std::abs(b.dx(origin,b.me.x))>.15)){
            a.kind=build;
            if(EventChoices::legal(a,b,svc)){
                prior_graves.clear();for(const auto* g:b.graves)prior_graves.insert(g->id);
                return a;
            }
            if(direct){route.reset();switch_events.push_back({{"t",b.v.time},{"phase","direct_illegal"}});return {wait,b.me.x,b.me.y};}
        }
        return a;
    }
    void accepted(const Board& b,const Action& a){
        if(!route||a.kind!=build)return;
        switch_events.push_back({{"t",b.v.time},{"phase","built"},{"move_tiles",std::abs(b.dx(origin,b.me.x))},{"target",EventChoices::identity(a)}});
        pending=a;pending_at=b.v.time;route.reset();
    }
};
