// Bounded native deque for actual profiling samples and serial queues.
#include "sim/pvp/pvprt.h"
#include <deque>
#include <optional>
#include <limits>
#include <algorithm>
#include <cmath>
namespace pvz::py {
namespace {
struct NativeDeque : PyObj {
    std::deque<V> values;
    std::optional<size_t> maximum;
    const char* type_name() const override { return "deque"; }
    bool isa(const char* name) const override { return std::string(name)=="deque" || std::string(name)=="object"; }
    size_t length() override { return values.size(); }
    bool truth() override { return !values.empty(); }
    V iterate() override { return V::list(std::vector<V>(values.begin(),values.end())); }
    size_t index(const V& key) const {
        if (!key.is_num() || !std::isfinite(key.num()) || key.num()!=std::trunc(key.num())) throw PyError("TypeError","sequence index must be integer");
        if(key.num() < -double(values.size()) || key.num() >= double(values.size()))throw PyError("IndexError","deque index out of range");
        int64_t n=int64_t(key.num());if(n<0)n+=int64_t(values.size());
        if(n<0 || size_t(n)>=values.size())throw PyError("IndexError","deque index out of range");
        return size_t(n);
    }
    V getitem(const V& key) override { return values[index(key)]; }
    void setitem(const V& key,const V& value) override { values[index(key)]=value; }
    void delitem(const V& key) override { values.erase(values.begin()+index(key)); }
    bool contains(const V& value) override { return std::any_of(values.begin(),values.end(),[&](const V& x){return py_eq(x,value);}); }
    V property(Sym name,bool& found) override {
        if(name==Sym("maxlen")){found=true;return maximum?V(double(*maximum)):V::none();}
        found=false;return V();
    }
    void append(const V& value,bool left) {
        if(maximum && *maximum==0)return;
        if(maximum && values.size()==*maximum){if(left)values.pop_back();else values.pop_front();}
        if(left)values.push_front(value);else values.push_back(value);
    }
    bool call_method(Sym name,const Args& a,V& out) override {
        const std::string& n=name.str();
        if(n=="append" || n=="appendleft"){append(a.get(0,Sym("value"),nullptr,n.c_str()),n=="appendleft");out=V::none();return true;}
        if(n=="pop" || n=="popleft"){
            if(values.empty())throw PyError("IndexError","pop from an empty deque");
            if(n=="pop"){out=values.back();values.pop_back();}else{out=values.front();values.pop_front();}return true;
        }
        if(n=="extend" || n=="extendleft"){
            V input=iter_list(a.get(0,Sym("iterable"),nullptr,n.c_str()));for(const V& value:input.items())append(value,n=="extendleft");
            out=V::none();return true;
        }
        if(n=="clear"){values.clear();out=V::none();return true;}
        if(n=="reverse"){std::reverse(values.begin(),values.end());out=V::none();return true;}
        if(n=="rotate"){
            static const V one(1);V amount=a.get(0,Sym("n"),&one);
            if(!amount.is_num() || !std::isfinite(amount.num()) || amount.num()!=std::trunc(amount.num()))throw PyError("TypeError","integer required");
            if(amount.num()>=double(std::numeric_limits<int64_t>::max()) || amount.num()<double(std::numeric_limits<int64_t>::min()))throw PyError("OverflowError","rotate count is too large");
            if(!values.empty()){
                int64_t count=int64_t(amount.num())%int64_t(values.size());if(count<0)count+=int64_t(values.size());
                std::rotate(values.begin(),values.end()-count,values.end());
            }
            out=V::none();return true;
        }
        if(n=="copy" || n=="__copy__"){
            auto copy=std::make_shared<NativeDeque>();copy->values=values;copy->maximum=maximum;out=V::inst(copy);return true;
        }
        if(n=="count"){
            size_t count=0;for(const V& value:values)if(py_eq(value,a.pos.at(0)))++count;
            out=V(double(count));return true;
        }
        if(n=="remove"){
            auto i=std::find_if(values.begin(),values.end(),[&](const V& v){return py_eq(v,a.pos.at(0));});
            if(i==values.end())throw PyError("ValueError","deque.remove(x): x not in deque");
            values.erase(i);out=V::none();return true;
        }
        if(n=="__eq__" || n=="__ne__"){
            auto* other=a.pos.empty()?nullptr:as<NativeDeque>(a.pos[0]);bool equal=other && values.size()==other->values.size();
            if(equal)for(size_t i=0;i<values.size();++i)if(!py_eq(values[i],other->values[i])){equal=false;break;}
            out=V(n=="__eq__"?equal:!equal);return true;
        }
        return false;
    }
    V method(Sym name) override {
        static const SymIndex supported({Sym("append"),Sym("appendleft"),Sym("pop"),Sym("popleft"),Sym("extend"),Sym("extendleft"),Sym("clear"),Sym("reverse"),Sym("rotate"),Sym("copy"),Sym("__copy__"),Sym("count"),Sym("remove"),Sym("__eq__"),Sym("__ne__")});
        if(supported.find(name)<0)return V();
        auto owner=std::static_pointer_cast<NativeDeque>(shared_from_this());
        return V::func([owner,name](const Args& a){V out;owner->call_method(name,a,out);return out;});
    }
};
}
V native_deque_type();
V make_native_deque(const Args& a) {
    auto object=std::make_shared<NativeDeque>();
    static const V none=V::none();V maximum=a.get(1,Sym("maxlen"),&none);
    if(!maximum.is_none()){
        if(!maximum.is_num() || !std::isfinite(maximum.num()) || maximum.num()!=std::trunc(maximum.num()))throw PyError("TypeError","an integer is required");
        if(maximum.num()<0)throw PyError("ValueError","maxlen must be non-negative");
        if(maximum.num()>=double(std::numeric_limits<int64_t>::max()))throw PyError("OverflowError","maxlen is too large");
        object->maximum=size_t(maximum.num());
    }
    static const V absent;
    V input=a.get(0,Sym("iterable"),&absent);
    if(input.has())for(V sequence=iter_list(input);const V& value:sequence.items())object->append(value,false);
    V value=V::inst(object);
    return value;
}
V native_deque_type(){static V type=class_value(V("deque"),make_native_deque);return type;}
} // namespace pvz::py
