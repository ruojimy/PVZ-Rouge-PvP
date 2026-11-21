    // An active event policy can choose a new trip or interrupt a previous trip
    // at any public trigger. Rerank the original site while it remains feasible.
    int reconsider(std::vector<Action>& list,const Board& b,ai::Services& svc,int mask){
        const auto& m=switch_policy.at("front");
        const double threshold=switch_policy.at("front_margin");
        const bool ongoing=bool(route);
        const Action* best=nullptr;
        double value=-1e9;
        if(route){
            auto goal=*route;
            const bool near=std::abs(b.dx(b.me.x,goal.x))<=1.25;
            if(near)goal.kind=build;
            if(b.me.cooldown(goal.card,0.)<=b.v.time&&b.me.resource>=goal.cost&&EventChoices::legal(goal,b,svc)){
                best=&*route;value=predict(features(b,mask,best),m);
            }
        }else{
            // The existing spatial readout ranks sites. The continuation head
            // compares this forward proposal against immediate play at this event.
            for(const auto& a:list)if(a.kind==approach&&b.direction*b.dx(b.me.x,a.x)>1.25&&EventChoices::legal(a,b,svc)){
                best=&a;value=predict(features(b,mask,best),m);break;
            }
        }
        if(best&&value>threshold){
            if(!ongoing){
                route=*best;deadline=b.v.time+10.;origin=b.me.x;
                switch_events.push_back({{"phase","start_trip"},{"t",b.v.time},{"mask",mask},{"target",EventChoices::identity(*route)},{"f",value}});
            }else switch_events.push_back({{"phase","keep_trip"},{"t",b.v.time},{"mask",mask}});
            return 2;
        }
        if(ongoing){
            switch_events.push_back({{"phase","cancel_trip"},{"t",b.v.time},{"mask",mask},{"f",value}});
            route.reset();
        }
        return 1;
    }
