    std::vector<double> initial_deck;
    void inspect_deck(const Board& b,ai::Services& svc){
        if(!initial_deck.empty())return;
        double count=0.,graves=0.,producers=0.,min_grave=1000.,min_unit=1000.,sum_cost=0.,max_speed=0.,max_range=0.,max_attack=0.;
        for(const auto& k:b.me.deck)if(k.starts_with("zombie:")){
            const auto& c=svc.card(k);count+=1.;sum_cost+=c.cost;producers+=c.producer;
            if(c.behavior=="grave"){graves+=1.;min_grave=std::min(min_grave,double(c.cost));}
            else{min_unit=std::min(min_unit,double(c.cost));max_speed=std::max(max_speed,double(c.speed));
                max_range=std::max(max_range,double(c.range));max_attack=std::max(max_attack,c.damage/std::max(.1,c.interval));}
        }
        initial_deck={count/10.,graves/std::max(1.,count),producers/std::max(1.,count),std::tanh(min_grave/150.),
            std::tanh(min_unit/150.),std::tanh(sum_cost/std::max(1.,count)/200.),std::tanh(max_speed/60.),
            std::tanh(max_range/400.),std::tanh(max_attack/60.)};
    }
    double contextual(const std::vector<double>& state,const std::vector<double>& site)const{
        std::vector<double> x;
        for(int k:{6,13,14,15,16,17,18,20,21,22,23,24,25,26,27,28,29})x.push_back(state[k]);
        for(int k:{3,4,5,6,11,12,13,19})x.push_back(site[k]);
        x.insert(x.end(),initial_deck.begin(),initial_deck.end());
        const auto& m=switch_policy.at("context");
        double mass=m.at("prior"),value=0.;
        for(const auto& center:m.at("centers")){
            double d=0.;for(size_t i=0;i<x.size();++i){
                double delta=(x[i]-center.at("x").at(i).get<double>())*m.at("scale").at(i).get<double>();
                d+=delta*delta;
            }
            double w=center.at("weight").get<double>()*std::exp(-d*m.at("inverse_width").get<double>());
            mass+=w;value+=w*center.at("target").get<double>();
        }
        return value/mass;
    }
