// Chooses the controller for one event interval. Both branches use native command validation.
inline int special_tactic = -1;
class ZombieSpecialist {
    EventChoices observer;
    std::array<std::array<double,22>,2> linear{};
    std::array<std::array<double,22>,8> hidden{};
    std::array<std::array<double,8>,2> head{};
    std::array<double,8> hidden_bias{};
    std::array<double,2> bias{};
    std::array<std::vector<int>,2> deployments;
    bool initialized=false,record=false;
    int current=0,forced=-1;
    double next=0.;
public:
    int select(const ai::View& view,ai::Services& service){
        if(!initialized){
            const auto& gate=switch_policy.at("native_gate");
            linear=gate.at("linear").get<decltype(linear)>();hidden=gate.at("hidden").get<decltype(hidden)>();
            head=gate.at("head").get<decltype(head)>();bias=gate.at("bias").get<decltype(bias)>();
            hidden_bias=gate.at("hidden_bias").get<decltype(hidden_bias)>();
            record=gate.value("record",false);forced=switch_force;switch_force=-1;initialized=true;
        }
        const int mask=observer.changes(view,service);
        const int tick=static_cast<int>(std::llround(view.time*30));
        const bool fork=forced>=0&&tick>=std::llround(switch_after*30);
        if(!mask&&!fork&&view.time<next)return current;
        next=view.time+1.;
        Board board(view);
        double closest=20.,plant_count=0.,affordable=0.,ready=0.;
        for(const auto& u:view.units)if(u.hp>0.&&u.side==pvz::typed72::Seat::plant){
            ++plant_count;closest=std::min(closest,std::hypot(board.dx(board.me.x,u.x),(board.me.y-u.y)/view.tile));
        }
        for(const auto& k:board.me.deck)if(k.starts_with("zombie:")){
            if(board.me.cooldown(k,0.)<=view.time){
                ++ready;
                if(board.me.resource>=observer.price(k,service.card(k).cost))++affordable;
            }
        }
        std::array<double,22> x={std::tanh(view.time/200.),double(view.map_night),double(view.deathmatch),
            std::tanh(board.me.resource/260.),std::tanh(board.foe.resource/260.),
            board.me.hp/std::max(1.,board.me.max_hp),board.foe.hp/std::max(1.,board.foe.max_hp),
            std::tanh(board.graves.size()/4.),std::tanh(board.army/6.),std::tanh(plant_count/8.),
            std::exp(-closest/5.),std::tanh(std::abs(board.dx(board.me.x,board.foe.x))/10.),
            double(bool(mask&1)),double(bool(mask&2)),double(bool(mask&4)),double(bool(mask&8)),
            ready/8.,affordable/8.};
        for(size_t i=0;i<deployments.size();++i){
            const auto& v=deployments[i];
            x[18+2*i]=v.empty()?1.:std::min(1.,(tick-v.back())/1800.);
            x[19+2*i]=std::tanh((v.end()-std::lower_bound(v.begin(),v.end(),tick-450))/3.);
        }
        std::array<double,8> h{};
        for(size_t j=0;j<h.size();++j)h[j]=std::tanh(std::inner_product(x.begin(),x.end(),hidden[j].begin(),hidden_bias[j]));
        auto scores=bias;
        for(size_t j=0;j<2;++j){
            scores[j]+=std::inner_product(x.begin(),x.end(),linear[j].begin(),0.);
            scores[j]+=std::inner_product(h.begin(),h.end(),head[j].begin(),0.);
        }
        const int before=current;
        current=scores[0]>0.?1:0;
        if(scores[1]>std::max(0.,scores[0]))current=2;
        if(fork){
            current=forced;forced=-1;
            option_events.push_back({{"forked",true},{"time",view.time},{"choice",current},{"prefix",option_prefix()}});
        }
        special_tactic=current?current:-1;
        if(record||fork||current||before){
            ainn::J ev={{"phase","special"},{"t",view.time},{"mask",mask},{"choice",current},{"from",before}};
            if(record||fork)ev["x"]=x;
            if(fork)ev["prefix"]=option_events.back().at("prefix");
            switch_events.push_back(std::move(ev));
        }
        return current;
    }
    void accepted(const std::string& kind,const Args& args,const ai::View& view,ai::Services& service){
        if(kind!="deploy")return;
        const auto card=string_arg(args,"card");
        if(card.starts_with("zombie:"))
            deployments[service.card(card).behavior=="grave"?1:0].push_back(static_cast<int>(std::llround(view.time*30)));
    }
};
