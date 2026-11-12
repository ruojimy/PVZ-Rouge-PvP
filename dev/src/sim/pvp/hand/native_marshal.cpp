// Data-only marshal subset for immutable native snapshot inputs. This does not
// construct or execute Python code. Integer/float identity follows the existing
// V numeric model. Opaque/custom types and recursive graphs are unsupported.
#include "sim/pvp/pvprt.h"
#include <cmath>
#include <cstdint>
#include <cstring>
#include <limits>
#include <unordered_map>
#include <unordered_set>
namespace pvz {bool is_ordered_dict(const V&);}
namespace pvz::py {
namespace {
constexpr size_t byte_limit=32u*1024u*1024u,item_limit=1024u*1024u;
constexpr int depth_limit=128;
bool utf8(const std::string& s) {
    for(size_t i=0;i<s.size();) {
        unsigned c=(unsigned char)s[i++],need=0,min=0,value=0;
        if(c<128)continue;
        if(c>=0xc2 && c<=0xdf){need=1;min=0x80;value=c&31;}
        else if(c>=0xe0 && c<=0xef){need=2;min=0x800;value=c&15;}
        else if(c>=0xf0 && c<=0xf4){need=3;min=0x10000;value=c&7;}
        else return false;
        if(need>s.size()-i)return false;
        for(unsigned n=0;n<need;++n){unsigned next=(unsigned char)s[i++];if((next&0xc0)!=0x80)return false;value=(value<<6)|(next&63);}
        if(value<min || value>0x10ffff || (value>=0xd800 && value<=0xdfff))return false;
    }return true;
}
struct Encode {
    std::string bytes;std::unordered_map<const Box*,uint32_t> refs;std::unordered_set<const Box*> active;
    void u8(unsigned n){if(bytes.size()>=byte_limit)throw PyError("ValueError","native marshal input exceeds byte budget");bytes.push_back(char(n));}
    void raw(const std::string& s){if(s.size()>byte_limit-bytes.size())throw PyError("ValueError","native marshal input exceeds byte budget");bytes+=s;}
    void u32(uint32_t n){for(int i=0;i<4;++i)u8((n>>(8*i))&255);}
    void length(size_t n){if(n>item_limit)throw PyError("ValueError","native marshal collection exceeds item budget");u32(uint32_t(n));}
    bool map_key(const V& v){return v.is_none() || (v.is_num() && std::isfinite(v.num())) || (v.t==V::STR && !v.byt);}
    bool begin(const V& value,unsigned kind) {
        const Box* box=value.box.get();
        if(active.count(box))throw PyError("ValueError","recursive native snapshot input is unsupported");
        auto found=refs.find(box);if(found!=refs.end()){u8('r');u32(found->second);return false;}
        if(refs.size()>=item_limit)throw PyError("ValueError","native marshal reference budget exceeded");
        refs.emplace(box,uint32_t(refs.size()));active.insert(box);u8(kind|0x80);return true;
    }
    void value(const V& v,int depth=0) {
        if(depth>depth_limit)throw PyError("ValueError","native marshal nesting limit exceeded");
        if(v.is_none()){u8('N');return;}
        if(v.t==V::BOOL){u8(v.b?'T':'F');return;}
        if(v.t==V::NUM) {
            double n=v.num();
            if(std::isfinite(n) && std::floor(n)==n && std::fabs(n)<9007199254740992.0 && !(n==0 && std::signbit(n))) {
                int64_t integer=int64_t(n);
                if(integer>=INT32_MIN && integer<=INT32_MAX){u8('i');u32(uint32_t(int32_t(integer)));return;}
                uint64_t magnitude=integer<0?uint64_t(-integer):uint64_t(integer),rest=magnitude;int32_t count=0;
                do{++count;rest>>=15;}while(rest);u8('l');u32(uint32_t(integer<0?-count:count));
                for(int32_t i=0;i<count;++i){unsigned digit=unsigned(magnitude&32767);u8(digit&255);u8(digit>>8);magnitude>>=15;}return;
            }
            u8('g');uint64_t bits;static_assert(sizeof(bits)==sizeof(n));std::memcpy(&bits,&n,8);for(int i=0;i<8;++i)u8(unsigned((bits>>(8*i))&255));return;
        }
        if(v.t==V::STR) {
            if(!v.byt && !utf8(v.str()))throw PyError("UnicodeEncodeError","invalid UTF-8 native marshal string");
            if(v.str().size()>byte_limit)throw PyError("ValueError","native marshal string exceeds byte budget");
            u8(v.byt?'s':'u');u32(uint32_t(v.str().size()));raw(v.str());return;
        }
        if(v.t==V::LIST || v.t==V::TUPLE) {
            if(!begin(v,v.t==V::LIST?'[':'('))return;
            length(v.items().size());for(const V& item:v.items())value(item,depth+1);active.erase(v.box.get());return;
        }
        if(v.t==V::DICT || v.t==V::OBJ) {
            if((v.t==V::DICT && (is_ordered_dict(v) || v.box->missing)) || (v.t==V::OBJ && v.o()->hook))
                throw PyError("ValueError","custom mapping is not a supported marshal input");
            if(!begin(v,'{'))return;
            if(v.len()>item_limit)throw PyError("ValueError","native marshal mapping exceeds item budget");
            if(v.t==V::DICT)for(const auto& item:v.kv()){if(!map_key(item.first))throw PyError("ValueError","unsupported native snapshot mapping key");value(item.first,depth+1);value(item.second,depth+1);}
            else v.o()->each([&](const V& key,const V& item){value(key,depth+1);value(item,depth+1);});
            u8('0');active.erase(v.box.get());return;
        }
        throw PyError("ValueError","unmarshallable native object: "+v.type_name());
    }
};
struct Decode {
    const std::string& bytes;size_t cursor=0;std::vector<V> refs;std::vector<bool> ready;
    uint8_t u8(){if(cursor>=bytes.size())throw PyError("EOFError","marshal input is truncated");return uint8_t(bytes[cursor++]);}
    uint32_t u32(){uint32_t n=0;for(int i=0;i<4;++i)n|=uint32_t(u8())<<(8*i);return n;}
    int32_t i32(){return int32_t(u32());}
    size_t length(size_t maximum){int32_t n=i32();if(n<0 || size_t(n)>maximum)throw PyError("ValueError","invalid native marshal size");return size_t(n);}
    std::string raw(size_t count){if(count>bytes.size()-cursor)throw PyError("EOFError","marshal input is truncated");std::string s=bytes.substr(cursor,count);cursor+=count;return s;}
    bool key(const V& v){return v.is_none() || (v.is_num() && std::isfinite(v.num())) || (v.t==V::STR && !v.byt);}
    V value(int depth=0) {
        if(depth>depth_limit)throw PyError("ValueError","native marshal nesting limit exceeded");
        unsigned tag=u8();bool flag=(tag&0x80)!=0;tag&=0x7f;
        size_t slot=refs.size();
        if(flag){if(slot>=item_limit)throw PyError("ValueError","native marshal reference budget exceeded");refs.push_back(V());ready.push_back(false);}
        auto finish=[&](V v){if(flag){refs[slot]=v;ready[slot]=true;}return v;};
        if(tag=='0'){if(flag)throw PyError("ValueError","invalid marshal null reference");return V();}
        if(tag=='N')return finish(V::none());if(tag=='T')return finish(V(true));if(tag=='F')return finish(V(false));
        if(tag=='i')return finish(V(double(i32())));
        if(tag=='l') {
            int32_t signed_count=i32();int64_t count=signed_count<0?-int64_t(signed_count):int64_t(signed_count);
            if(count>4)throw PyError("ValueError","marshal integer exceeds exact native numeric range");
            uint64_t magnitude=0;
            for(int64_t i=0;i<count;++i){unsigned digit=u8();digit|=unsigned(u8())<<8;if(digit>32767)throw PyError("ValueError","invalid marshal integer digit");magnitude|=uint64_t(digit)<<(15*i);}
            if(magnitude>=9007199254740992ull)throw PyError("ValueError","marshal integer exceeds exact native numeric range");
            return finish(V(signed_count<0?-double(magnitude):double(magnitude)));
        }
        if(tag=='g') {uint64_t bits=0;for(int i=0;i<8;++i)bits|=uint64_t(u8())<<(8*i);double n;std::memcpy(&n,&bits,8);return finish(V(n));}
        if(tag=='s' || tag=='u' || tag=='t' || tag=='a' || tag=='A' || tag=='z' || tag=='Z') {
            size_t count=(tag=='z' || tag=='Z')?size_t(u8()):length(byte_limit);std::string s=raw(count);
            if(tag=='s')return finish(V::bytes(std::move(s)));
            if(!utf8(s))throw PyError("UnicodeDecodeError","invalid UTF-8 native marshal string");return finish(V(std::move(s)));
        }
        if(tag=='r') {
            if(flag)throw PyError("ValueError","invalid flagged marshal reference");int32_t n=i32();
            if(n<0 || size_t(n)>=refs.size() || !ready[size_t(n)])throw PyError("ValueError","invalid or recursive marshal reference");return refs[size_t(n)];
        }
        if(tag=='[' || tag=='(' || tag==')') {
            size_t count=tag==')'?size_t(u8()):length(item_limit);std::vector<V> items;items.reserve(count);
            for(size_t i=0;i<count;++i){V item=value(depth+1);if(!item.has())throw PyError("ValueError","invalid marshal null item");items.push_back(item);}
            return finish(tag=='['?V::list(std::move(items)):V::tuple(std::move(items)));
        }
        if(tag=='{') {
            V dictionary=V::dict();size_t count=0;
            for(;;){V k=value(depth+1);if(!k.has())break;if(!key(k))throw PyError("TypeError","unsupported native snapshot mapping key");V item=value(depth+1);if(!item.has())throw PyError("ValueError","invalid marshal null value");if(++count>item_limit)throw PyError("ValueError","native marshal mapping exceeds item budget");dictionary.at(k)=item;}
            return finish(dictionary);
        }
        if(tag=='c')throw PyError("NotImplementedError","Python code objects are not supported by the native data marshal codec");
        throw PyError("ValueError","unsupported native marshal tag: "+std::to_string(tag));
    }
};
}
V native_marshal_dumps(const Args& a) {
    if(a.pos.empty() || a.pos.size()>2 || !a.kw.empty())throw PyError("TypeError","native marshal.dumps expects data and optional version");
    if(a.pos.size()>1 && (!a.pos[1].is_num() || (a.pos[1].num()!=3 && a.pos[1].num()!=4)))throw PyError("NotImplementedError","native marshal supports protocol 3/4 only");
    Encode encoder;encoder.value(a.pos[0]);return V::bytes(std::move(encoder.bytes));
}
V native_marshal_loads(const Args& a) {
    if(a.pos.size()!=1 || !a.kw.empty())throw PyError("TypeError","native marshal.loads expects one payload");
    std::string bytes=bytes_data(a.pos[0]);if(bytes.size()>byte_limit)throw PyError("ValueError","native marshal input exceeds byte budget");
    Decode decoder{bytes};V result=decoder.value();if(!result.has() || decoder.cursor!=bytes.size())throw PyError("ValueError","native marshal input not completely consumed");return result;
}
V native_marshal_module() {
    struct Module final:PyObj {
        const char* type_name() const override{return "module";}
        V property(Sym name,bool& found) override {
            found=true;if(name==Sym("__name__"))return V("marshal");
            if(name==Sym("native_capabilities"))return py_dict({{V("protocols"),V::tuple({V(3),V(4)})},{V("code_objects"),V(false)},{V("recursive_graphs"),V(false)},{V("strict_consumption"),V(true)},{V("byte_limit"),V(double(byte_limit))},{V("numeric_model"),V("existing dynamic V")}});
            found=false;return V();
        }
        V method(Sym name) override {if(name==Sym("dumps"))return V::func(native_marshal_dumps);if(name==Sym("loads"))return V::func(native_marshal_loads);return V();}
    };
    static V module=V::inst(std::make_shared<Module>());return module;
}
}
