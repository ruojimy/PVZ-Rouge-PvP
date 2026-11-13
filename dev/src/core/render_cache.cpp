#include "core/render_cache.h"
#include "core/function_profile.h"
#include "sim/pvp/pvprt.h"
#include <list>
#include <unordered_map>
#include <cstring>
namespace pvz { namespace {
uint64_t hash_key(const V& key){
    switch(key.t){
    case V::STR:return std::hash<std::string_view>{}(key.str())^0x51ull;
    case V::NUM:case V::BOOL:{double d=key.num();if(d==0.)d=0.;uint64_t h;std::memcpy(&h,&d,8);return h^2ull;}
    case V::NONE:return 0x9e37ull;
    case V::TUPLE:{uint64_t h=0x84222325cbf29ce4ull;for(const auto& v:key.items())h=(h^hash_key(v))*0x100000001b3ull;return h;}
    default:throw PyError("TypeError","unsupported render cache key");
    }
}
struct Hash {size_t operator()(const V& key)const{return size_t(hash_key(key));}};
struct Eq {bool operator()(const V& a,const V& b)const{return py_eq(a,b);}};
struct RenderLRU final:PyObj {
    using Row=std::pair<V,V>;std::list<Row> rows;
    std::unordered_map<V,std::list<Row>::iterator,Hash,Eq> index;
    const char* type_name()const override{return "RenderLRU";}
    size_t length()override{return rows.size();}
    bool truth()override{return !rows.empty();}
    bool contains(const V& k)override{return index.contains(k);}
    V getitem(const V& k)override{const auto i=index.find(k);if(i==index.end())throw PyError("KeyError",py_str(k));return i->second->second;}
    void setitem(const V& k,const V& value)override{const auto i=index.find(k);if(i!=index.end()){i->second->second=value;return;}rows.emplace_back(k,value);index.emplace(k,std::prev(rows.end()));}
    void delitem(const V& k)override{const auto i=index.find(k);if(i==index.end())throw PyError("KeyError",py_str(k));rows.erase(i->second);index.erase(i);}
    V iterate()override{V out=V::list();for(const auto& row:rows)out.append(row.first);return out;}
    V method(Sym name)override{
        static const SymIndex supported({SY("get"),SY("clear"),SY("move_to_end"),SY("popitem"),SY("keys"),SY("items"),SY("values")});
        if(supported.find(name)<0)return V();
        auto cache=std::static_pointer_cast<RenderLRU>(shared_from_this());
        return V::func([cache,name](const Args& a){V out;cache->call_method(name,a,out);return out;});
    }
    bool call_method(Sym name,const Args& a,V& out)override{
        if(name==SY("get")){PVP_PROFILE_SCOPE("RenderLRU::get");const auto i=index.find(a.get(0,SY("key"),nullptr));out=i==index.end()?(a.size()>1?a.pos[1]:V::none()):i->second->second;return true;}
        if(name==SY("clear")){rows.clear();index.clear();out=V::none();return true;}
        if(name==SY("move_to_end")){PVP_PROFILE_SCOPE("RenderLRU::move_to_end");const V key=a.get(0,SY("key"),nullptr);const auto i=index.find(key);if(i==index.end())throw PyError("KeyError",py_str(key));static const V yes(true);rows.splice(a.get(1,SY("last"),&yes).truthy()?rows.end():rows.begin(),rows,i->second);out=V::none();return true;}
        if(name==SY("popitem")){if(rows.empty())throw PyError("KeyError","popitem(): dictionary is empty");static const V yes(true);const auto i=a.get(0,SY("last"),&yes).truthy()?std::prev(rows.end()):rows.begin();out=V::tuple({i->first,i->second});index.erase(i->first);rows.erase(i);return true;}
        if(name==SY("keys")){out=iterate();return true;}
        if(name==SY("items")||name==SY("values")){out=V::list();for(const auto& row:rows)out.append(name==SY("items")?V::tuple({row.first,row.second}):row.second);return true;}
        return false;
    }
};
}
V native_render_cache(){
    const auto legacy=std::getenv("PVP741_RENDER_LRU");
    if(legacy&&std::string(legacy)=="0")return py::stdlib_call(V("collections.OrderedDict"),Args{});
    return V::inst(std::make_shared<RenderLRU>());
}
}
