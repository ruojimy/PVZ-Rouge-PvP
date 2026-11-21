    struct DenseReadout {
        std::vector<double> linear,hb,head;
        std::vector<std::vector<double>> hidden;
        double bias=0.;
        explicit DenseReadout(const ainn::J& m):linear(m.at("linear").get<decltype(linear)>()),hb(m.at("hb").get<decltype(hb)>()),head(m.at("head").get<decltype(head)>()),hidden(m.at("hidden").get<decltype(hidden)>()),bias(m.at("bias")){
            if(hidden.size()!=head.size()||hb.size()!=head.size())throw std::runtime_error("bad one-action readout");
            for(const auto& h:hidden)if(h.size()!=linear.size())throw std::runtime_error("bad one-action width");
        }
        double eval(const std::vector<double>& x)const{
            if(linear.size()!=x.size())throw std::runtime_error("one-action input width");
            double v=std::inner_product(x.begin(),x.end(),linear.begin(),bias);
            for(size_t j=0;j<head.size();++j)v+=head[j]*std::tanh(std::inner_product(x.begin(),x.end(),hidden[j].begin(),hb[j]));
            return v;
        }
    };
    std::map<const ainn::J*,DenseReadout> readouts;
    double cached(const std::vector<double>& x,const ainn::J& m){return readouts.try_emplace(&m,m).first->second.eval(x);}
