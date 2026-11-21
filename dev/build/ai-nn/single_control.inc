    bool slice_pending=false,review_old=false;
    double slice_time=0.,last_deploy=-100.,last_sample=-100.;
    int observed_mask=0;
    std::string mode()const {return switch_policy.value("single_mode",std::string{});}
    bool leased()const {return !switch_policy.is_null()&&mode()=="lease";}
    bool stamped_mode()const {const auto m=mode();return m=="review"||m=="arrival_pair";}
    bool arriving(const Board& b,ai::Services& svc)const{
        if(!route||std::abs(b.dx(b.me.x,route->x))>1.25||std::abs(b.dx(origin,b.me.x))<=.15)return false;
        Action a=*route;a.kind=build;return EventChoices::legal(a,b,svc);
    }
    std::vector<double> one_features(const Board& b,ai::Services& svc,int mask,const Action* front,const std::vector<Action>& list){
        inspect_deck(b,svc);
        auto state=features(b,mask,nullptr),site=features(b,mask,front);
        std::vector<double> x;
        for(int k:{6,13,14,15,16,17,18,20,21,22,23,24,25,26,27,28,29})x.push_back(state[k]);
        for(int k:{3,4,5,6,11,12,13,19})x.push_back(site[k]);
        for(Kind kind:{spawn,build}){
            const Action* pick=nullptr;
            for(const auto& a:list)if(a.kind==kind&&EventChoices::legal(a,b,svc)){pick=&a;break;}
            x.push_back(pick?1.:0.);
            auto desc=features(b,mask,pick);
            for(int k:{4,5,6,7,8,9,10,11,13})x.push_back(desc[k]);
        }
        x.insert(x.end(),initial_deck.begin(),initial_deck.end());
        x.push_back(handed);x.push_back(bool(route));x.push_back(std::tanh((b.v.time-last_deploy)/8.));
        return x;
    }
    const Action* forward(const std::vector<Action>& list,const Board& b,ai::Services& svc)const{
        if(route&&EventChoices::legal(*route,b,svc))return &*route;
        for(const auto& a:list)if(a.kind==approach&&b.direction*b.dx(b.me.x,a.x)>1.25&&EventChoices::legal(a,b,svc))return &a;
        return nullptr;
    }
    void stamp(int n,const Board& b,int mask,const std::vector<double>& x){
        const auto prefix=option_prefix();marked=true;
        option_events.push_back({{"forked",true},{"time",b.v.time},{"choice",n},{"mask",mask},{"prefix",prefix}});
        switch_events.push_back({{"phase","probe"},{"t",b.v.time},{"choice",n},{"mask",mask},{"x",x},{"prefix",prefix}});
    }
    void observe_tick(const Board& b,ai::Services& svc,int mask,const std::vector<Action>& list){
        if(!stamped_mode()||!forced(b.v.time))return;
        const auto* f=forward(list,b,svc);
        stamp(switch_force,b,mask,one_features(b,svc,mask,f,list));
        if(mode()=="review"&&switch_force==1){slice_pending=true;slice_time=b.v.time;}
    }
    bool finish_slice(double t,int mask,bool due){
        if(!slice_pending||t<=slice_time||(!mask&&!due))return false;
        slice_pending=false;review_old=true;handed=false;event_enabled=false;route.reset();
        switch_events.push_back({{"phase","return_z16"},{"t",t},{"mask",mask}});
        return true;
    }
    int lease_decide(const std::vector<Action>& list,const Board& b,ai::Services& svc,int mask){
        const bool fork=forced(b.v.time);
        const auto* f=forward(list,b,svc);
        auto x=one_features(b,svc,mask,f,list);
        const bool was=handed;
        double v=0.,travel=-100.;
        int chosen=0;
        if(switch_policy.contains("one_head")){
            v=predict(x,switch_policy.at("one_head"));
            if(f)travel=predict(x,switch_policy.at("trip_head"));
            if(v>switch_policy.at("one_margin").get<double>())chosen=1;
            if(f&&travel>switch_policy.at("trip_margin").get<double>()&&travel>v)chosen=2;
        }
        if(fork){chosen=switch_force;stamp(chosen,b,mask,x);}
        if(chosen==2&&!f)throw std::runtime_error("unavailable trip");
        ainn::J ev={{"phase","lease"},{"t",b.v.time},{"mask",mask},{"from",int(was)},{"choice",chosen},{"v",v},{"trip",travel},{"offered",bool(f)}};
        if(fork||(switch_policy.value("sample",false)&&(mask||b.v.time-last_sample>=12.))){
            ev["x"]=x;last_sample=b.v.time;
        }
        if(chosen==2)ev["target"]=EventChoices::identity(*f);
        switch_events.push_back(std::move(ev));
        handed=chosen!=0;event_enabled=handed;
        if(chosen==2){
            if(!route||EventChoices::identity(*route)!=EventChoices::identity(*f)){
                route_features=features(b,mask,f);route_start=b.v.time;origin=b.me.x;deadline=b.v.time+10.;route=*f;
            }
        }else route.reset();
        return chosen;
    }
    std::vector<double> arrival_features(const Board& b,const Action& a){
        auto x=features(b,observed_mask,&a);
        x.insert(x.end(),initial_deck.begin(),initial_deck.end());
        x.push_back(std::tanh((b.v.time-route_start)/5.));
        x.push_back(std::tanh(std::abs(b.dx(origin,b.me.x))/8.));
        x.push_back(std::tanh((b.v.time-last_deploy)/8.));
        return x;
    }
