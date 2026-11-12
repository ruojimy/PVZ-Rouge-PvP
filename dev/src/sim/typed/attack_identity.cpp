#include "sim/typed/attack_identity.h"
#include <stdexcept>

namespace pvz::typed72 {
namespace {
std::string repr_string(const std::string& s) {
    const char quote=s.find('\'')!=std::string::npos&&s.find('"')==std::string::npos?'"':'\'';
    std::string out(1,quote);constexpr char hex[]="0123456789abcdef";
    for(unsigned char c:s) {
        if(c==quote||c=='\\'){out+='\\';out+=char(c);}
        else if(c=='\n')out+="\\n";else if(c=='\r')out+="\\r";else if(c=='\t')out+="\\t";
        else if(c<32||c==127){out+="\\x";out+=hex[c>>4];out+=hex[c&15];}
        else out+=char(c);
    }
    return out+quote;
}
std::string sized(const std::string& s){return std::to_string(s.size())+":"+s;}
}
AttackIdentity AttackIdentity::null(){return {"None","None","n",true,true,true,false};}
AttackIdentity AttackIdentity::literal(std::string text){return {text,repr_string(text),"s"+sized(text),true,true,false,!text.empty()};}
AttackIdentity AttackIdentity::integer(int64_t n){const auto text=std::to_string(n);return {text,text,"i"+text,true,true,false,n!=0};}
AttackIdentity AttackIdentity::boolean(bool n){const std::string text=n?"True":"False";return {text,text,n?"i1":"i0",true,true,false,n};}
AttackIdentity AttackIdentity::sequence(const std::vector<AttackIdentity>& values,bool list) {
    std::string text=list?"[":"(";std::string key="t"+std::to_string(values.size())+":";bool hashable=true;
    for(size_t i=0;i<values.size();++i){if(i)text+=", ";text+=values[i].repr_;key+=sized(values[i].key_);hashable=hashable&&values[i].hashable_;}
    if(!list&&values.size()==1)text+=",";text+=list?"]":")";
    return {text,text,key,!list&&hashable,hashable,false,!values.empty()};
}
AttackIdentity AttackIdentity::native(const std::string& source,int64_t tick){return sequence({literal(source),integer(tick)},false);}
AttackIdentity AttackIdentity::projectile(const std::string& source){return sequence({literal(source),null()},false);}
const std::string& AttackIdentity::unit_key() const {
    if(!normalized_hashable_)throw std::invalid_argument("unhashable nested attack identity");
    return key_;
}
} // namespace pvz::typed72
