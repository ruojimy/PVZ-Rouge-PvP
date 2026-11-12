#include "core/fsutil.h"
#include "core/native_closure.h"
#include "core/native_file.h"
#include "sim/pvp/hand/native_marshal.h"
#include <chrono>
#include "core/alloc.h"
#include "sim/pvp/pvprt.h"
namespace pvz { V native_current_function(); }
#include "sim/pvp/dynamic_bindings.h"
#include "data/datastore.h"
#include <nlohmann/json.hpp>
#include <algorithm>
#include <cstdio>
#include <cstdlib>
#include <cwctype>
#include <map>
#include <unordered_map>

namespace pvz { std::string python_repr_text(const V&); V local_class_member(const V&,Sym,int); bool is_ordered_dict(const V&); bool exception_matches(const std::string&, const std::vector<std::string>&, const char*); }
namespace pvz::py {
V native_exit_stack(const Args&);
V make_native_deque(const Args& a);
V native_deque_type();
V native_ordered_dict_type();
V native_gc_module();
V native_method_type();

V todo(const char* what) { throw PyError("NotImplementedError", std::string("untranslated: ") + what); }

// ---------------------------------------------------------------- sequences
V as_seq(const V& v) {
    if (v.is_list()) return v;
    return iter_list(v);
}
V list_it(const V& v) { V it = iter_list(v); return V::list(it.items()); }
V tuple_it(const V& v) { V it = iter_list(v); return V::tuple(it.items()); }
V set_it(const V& v) { return V::set(iter_list(v).items()); }
V set_it() { return V::set(); }
void set_add(V& s, const V& x) { if (!s.contains(x)) s.set_insert_new(x); }
V enumerate(const V& v) { return enumerate(v, V(0.0)); }
V enumerate(const V& v, const V& start) {
    V it = iter_list(v);
    std::vector<V> out;
    double i = start.num();
    for (auto& x : it.items()) out.push_back(V::tuple({V(i++), x}));
    return V::list(std::move(out));
}
V zip(const V& a, const V& b) {
    V x = iter_list(a), y = iter_list(b);
    std::vector<V> out;
    size_t n = std::min(x.len(), y.len());
    for (size_t i = 0; i < n; ++i) out.push_back(V::tuple({x.idx(int64_t(i)), y.idx(int64_t(i))}));
    return V::list(std::move(out));
}
V zip(const V& a, const V& b, const V& c) {
    V x = iter_list(a), y = iter_list(b), z = iter_list(c);
    std::vector<V> out;
    size_t n = std::min({x.len(), y.len(), z.len()});
    for (size_t i = 0; i < n; ++i) out.push_back(V::tuple({x.idx(int64_t(i)), y.idx(int64_t(i)), z.idx(int64_t(i))}));
    return V::list(std::move(out));
}
V any(const V& v) { for (V held_ = iter_list(v); auto& x : held_.items()) if (x.truthy()) return V(true); return V(false); }
V all(const V& v) { for (V held_ = iter_list(v); auto& x : held_.items()) if (!x.truthy()) return V(false); return V(true); }
V sum_it(const V& v) { return sum_it(v, V(0.0)); }
V sum_it(const V& v, const V& start) { V s = start; for (V held_ = iter_list(v); auto& x : held_.items()) s = s + x; return s; }

struct IterObj : PyObj {
    V items;
    size_t pos = 0;
    const char* type_name() const override { return "iterator"; }
    V iterate() override { std::vector<V> r(items.items().begin() + pos, items.items().end()); pos = items.len(); return V::list(r); }
};
V iter(const V& v) { auto p = std::make_shared<IterObj>(); p->items = iter_list(v); return V::inst(p); }
V iter2(const V& fn, const V& sentinel) {
    std::vector<V> out;
    for (;;) { V x = fn.call(Args{}); if (py_eq(x, sentinel)) break; out.push_back(x); }
    auto p = std::make_shared<IterObj>(); p->items = V::list(out); return V::inst(p);
}
// The factory owns its descriptor table; each instance keeps the actual factory alive.
// LocalClassInfo only holds a non-owning pointer, avoiding a factory -> closure -> factory cycle.
// The factory owns its descriptor table; each instance keeps the actual factory alive.
// LocalClassInfo only holds a non-owning pointer, avoiding a factory -> closure -> factory cycle.
struct NativeSlice : PyObj {
    V start,stop,step;
    const char* type_name()const override{return "slice";}
    bool isa(const char* name)const override{return std::string(name)=="slice" || std::string(name)=="object";}
    V property(Sym name,bool& found)override{found=true;if(name==Sym("start"))return start;if(name==Sym("stop"))return stop;if(name==Sym("step"))return step;found=false;return V();}
    bool set_property(Sym,const V&)override{throw PyError("AttributeError","slice attributes are read-only");}
    V method(Sym name)override{
        if(name!=Sym("indices"))return V();auto slice=std::static_pointer_cast<NativeSlice>(shared_from_this());
        return V::func([slice](const Args& args){
            if(args.pos.size()!=1 || !args.kw.empty())throw PyError("TypeError","indices requires one length");
            auto index=[](const V& value)->int64_t{if(!value.is_num() || !std::isfinite(value.num()) || std::trunc(value.num())!=value.num())throw PyError("TypeError","slice indices must be integers");if(std::fabs(value.num())>9007199254740991.0)throw PyError("OverflowError","slice index exceeds native exact integer range");return int64_t(value.num());};
            int64_t n=index(args.pos[0]);if(n<0)throw PyError("ValueError","length should not be negative");int64_t step=slice->step.is_none()?1:index(slice->step);if(!step)throw PyError("ValueError","slice step cannot be zero");
            int64_t low=step<0?-1:0,high=step<0?n-1:n;
            auto bound=[&](const V& value,int64_t fallback){if(value.is_none())return fallback;int64_t result=index(value);if(result<0)result+=n;return std::clamp(result,low,high);};
            return V::tuple({V(bound(slice->start,step<0?high:low)),V(bound(slice->stop,step<0?low:high)),V(step)});
        });
    }
};
V native_slice(const V& start,const V& stop,const V& step){auto value=std::make_shared<NativeSlice>();value->start=start.has()?start:V::none();value->stop=stop.has()?stop:V::none();value->step=step.has()?step:V::none();return V::inst(value);}
struct LocalClassInfo { std::string name; Box* factory = nullptr; };
struct LocalObj : PyObj {
    std::shared_ptr<LocalClassInfo> cls;
    V class_owner;
    const char* type_name() const override { return cls->name.c_str(); }
    bool isa(const char* c) const override { return cls->name == c || std::string(c) == "object"; }
    V member(Sym n) const { return pvz::local_class_member(class_owner,n,0); }
    V bound(const V& f) {
        if (f.t != V::FUNC) return f;
        for (const auto& p : f.box->fattrs)
            if ((p.first == Sym("__native_class_value__") || p.first == Sym("__native_builtin_callable__")) && p.second.truthy()) return f;
        return native_method_type().call(Args{f,self()});
    }
    V method(Sym n) override {
        if(n==Sym("__native_type__")) { V type=class_owner; V metadata=V::func([type](const Args&){return type;}); metadata.box->fattrs.emplace_back(Sym("__native_type_metadata__"),V(true)); return metadata; }
        if(n==Sym("__native_slot_names__")) return V::func([](const Args&){return V::tuple({});});
        V f=member(n); return f.has()?bound(f):V();
    }
    bool call_method(Sym n, const Args& a, V& out) override {
        V f=member(n); if(!f.has() || f.t!=V::FUNC)return false;
        out=bound(f).call(a);return true;
    }
    V dunder(const char* n, std::initializer_list<V> args) {
        V f=member(Sym(n));
        if(!f.has())throw PyError("TypeError","'"+cls->name+"' object does not support "+n);
        Args b;for(const V& v:args)b.pos.push_back(v);return bound(f).call(b);
    }
    V getitem(const V& k) override { return dunder("__getitem__", {k}); }
    void setitem(const V& k, const V& v) override { dunder("__setitem__", {k,v}); }
    void delitem(const V& k) override { dunder("__delitem__", {k}); }
    bool contains(const V& k) override { return dunder("__contains__", {k}).truthy(); }
    size_t length() override { return size_t(dunder("__len__", {}).num()); }
    V iterate() override { return iter_list(dunder("__iter__", {})); }
    V call_self(const Args& a) override { V f=member(Sym("__call__"));return f.has()?bound(f).call(a):PyObj::call_self(a); }
};
V local_class(const V& name, std::vector<std::pair<V, V>> members) {
    auto info=std::make_shared<LocalClassInfo>();info->name=name.str();
    V bases;
    for(const auto& item:members)if(item.first==V("__bases__"))bases=item.second;
    if(!bases.is_none() && (!bases.is_list() || bases.len()>1))throw PyError("NotImplementedError","local classes support one native base");
    V cls=class_value(name,[info,bases](const Args& a){
        V type;type.t=V::FUNC;type.box=BoxP(info->factory);
        V self;
        if(bases.is_list() && bases.len()) {
            V allocate=pvz::getattr(bases.idx(0),Sym("__new__"),V());
            if(allocate.t!=V::FUNC)throw PyError("NotImplementedError","native base has no allocation descriptor");
            self=allocate.call(Args{type});if(self.t!=V::INST)throw PyError("TypeError","native base allocator must return an instance");
            self.box->inst->setattr(Sym("__native_local_class__"),type);
        }else{auto object=std::make_shared<LocalObj>();object->cls=info;object->class_owner=type;self=V::inst(object);}
        V init=pvz::local_class_member(type,Sym("__init__"),0);
        if(init.has()){Args bound=a;bound.pos.insert(bound.pos.begin(),self);V result=init.call(bound);if(!result.is_none())throw PyError("TypeError","__init__() should return None");}
        else if(!a.pos.empty() || !a.kw.empty())throw PyError("TypeError",info->name+"() takes no arguments");
        return self;
    });
    for(const auto& p:members)pvz::setattr(cls,p.first.sym(),p.second);
    info->factory=cls.box.get();return cls;
}
}  // namespace pvz::py
namespace pvz {
// str.format: {} / {0} / {name} fields, !r / !s conversions, :spec through format_spec, {{ }} escapes
V str_format(const V& self, const Args& a) {
    const std::string& f = self.str();
    std::string out;
    size_t auto_idx = 0;
    for (size_t i = 0; i < f.size(); ++i) {
        char c = f[i];
        if (c == '{' && i + 1 < f.size() && f[i + 1] == '{') { out += '{'; ++i; continue; }
        if (c == '}' && i + 1 < f.size() && f[i + 1] == '}') { out += '}'; ++i; continue; }
        if (c != '{') { out += c; continue; }
        size_t j = f.find('}', i);
        if (j == std::string::npos) throw PyError("ValueError", "Single '{' encountered in format string");
        std::string field = f.substr(i + 1, j - i - 1), spec, conv;
        size_t colon = field.find(':');
        if (colon != std::string::npos) { spec = field.substr(colon + 1); field = field.substr(0, colon); }
        size_t bang = field.find('!');
        if (bang != std::string::npos) { conv = field.substr(bang + 1); field = field.substr(0, bang); }
        std::string base = field, rest;
        size_t sep = base.find_first_of(".[");
        if (sep != std::string::npos) { rest = base.substr(sep); base = base.substr(0, sep); }
        V v;
        if (base.empty()) v = a.pos.at(auto_idx++);
        else if (std::isdigit(static_cast<unsigned char>(base[0]))) v = a.pos.at(size_t(std::stoi(base)));
        else {
            bool found = false;
            for (auto& kv : a.kw) if (kv.first.str() == base) { v = kv.second; found = true; }
            if (!found) throw PyError("KeyError", base);
        }
        while (!rest.empty()) {   // .attr / [key] accessors
            if (rest[0] == '.') { size_t e = rest.find_first_of(".[", 1); v = pvz::getattr(v, Sym(rest.substr(1, e == std::string::npos ? std::string::npos : e - 1))); rest = e == std::string::npos ? "" : rest.substr(e); }
            else { size_t e = rest.find(']'); std::string k = rest.substr(1, e - 1); v = !k.empty() && std::isdigit(static_cast<unsigned char>(k[0])) ? rd(v, V(double(std::stoi(k)))) : rd(v, V(k)); rest = rest.substr(e + 1); }
        }
        if (conv == "r") v = py::repr(v);
        else if (conv == "s") v = V(py_str(v));
        out += spec.empty() ? py_str(v) : py::format_spec(v, V(spec)).str();
        i = j;
    }
    return V(out);
}
}  // namespace pvz
namespace pvz::py {
std::string cat_chunks(std::initializer_list<const char*> parts) { std::string s; for (auto* c : parts) s += c; return s; }

struct GenObj;
V next(const V& it) {
    V r = next(it, V());
    if (!r.has()) throw PyError("StopIteration", "");
    return r;
}

V divmod(const V& a, const V& b) { return V::tuple({floordiv(a, b), a % b}); }
V callable(const V& v) { return V(v.t == V::FUNC || v.t == V::INST); }
V id(const V& v) {
    if (v.box) return V(double(reinterpret_cast<uintptr_t>(v.t == V::INST ? (void*)v.box->inst.get() : (void*)v.box.get()) & ((1ull << 52) - 1)));
    return V(double(py_hash(v) & ((1ull << 52) - 1)));
}
V type(const V& v) {
    switch (v.t) {   // builtin values -> the canonical builtin type objects (see builtin())
        case V::BOOL: return builtin(V("bool"));
        case V::NUM: return builtin(V(v.n == std::floor(v.n) && std::fabs(v.n) < 9007199254740992.0 ? "int" : "float"));
        case V::STR: return builtin(V("str"));
        case V::LIST: return builtin(V("list"));
        case V::TUPLE: return builtin(V("tuple"));
        case V::DICT: for(const auto& attr:v.box->fattrs)if(attr.first==Sym("__native_template_class__"))return attr.second;return is_ordered_dict(v)?native_ordered_dict_type():builtin(V("dict"));
        case V::OBJ: return builtin(V("dict"));
        case V::SET: return builtin(V("set"));
        case V::NONE: case V::ABSENT: return builtin(V("NoneType"));
        default: break;
    }
    if (v.t == V::INST) {
        if(const V* local=v.box->inst->find_dyn(Sym("__native_local_class__")))return *local;
        V metadata=v.box->inst->method(Sym("__native_type__"));
        if(metadata.t==V::FUNC)for(const auto& attr:metadata.box->fattrs)
            if(attr.first==Sym("__native_type_metadata__") && attr.second.truthy())return metadata.call(Args{});
        return builtin(V(v.box->inst->type_name()));
    }
    return V(v.type_name());
}
V repr(const V& v) { return V(pvz::python_repr_text(v)); }
V invert(const V& v) { return V(double(~int64_t(v.num()))); }
V bitop(const char* op, const V& a, const V& b) {
    std::string o(op);
    if ((a.is_set() || b.is_set()) && o == "BitOr") { V r = V::set(a.items()); for (auto& x : b.items()) set_add(r, x); return r; }
    if ((a.is_set() || b.is_set()) && o == "BitAnd") { std::vector<V> r; for (auto& x : a.items()) if (b.contains(x)) r.push_back(x); return V::set(r); }
    if (a.is_dict() && b.is_dict() && o == "BitOr") { V r = copy(a); for (auto& p : b.kv()) r.at(p.first) = p.second; return r; }
    int64_t x = int64_t(a.num()), y = int64_t(b.num());
    if (o == "BitAnd") return V(double(x & y));
    if (o == "BitOr") return V(double(x | y));
    if (o == "BitXor") return V(double(x ^ y));
    if (o == "LShift") return V(double(x << y));
    if (o == "RShift") return V(double(x >> y));
    throw PyError("TypeError", "bad bit op");
}
V iadd(const V& a, const V& b) {
    if (a.t == V::LIST && b.is_list()) {
        auto copy_ = b.items();
        const_cast<V&>(a).items().insert(const_cast<V&>(a).items().end(), copy_.begin(), copy_.end());
        return a;
    }
    if (a.t == V::NUM && b.t == V::NUM) return V(a.n + b.n);
    return a + b;
}
V dict_of(const V& src) {
    V d = V::dict();
    if (src.is_dict()) { for (auto& p : src.kv()) d.at(p.first) = p.second; return d; }
    if (src.is_obj()) { src.o()->each([&](const V& k, const V& v) { d.at(k) = v; }); return d; }
    if (src.t == V::INST) {
        V keys = src.box->inst->iterate();
        for (auto& k : keys.items()) d.at(k) = src.box->inst->getitem(k);
        return d;
    }
    for (V held_ = iter_list(src); auto& kv : held_.items()) d.at(kv.idx(0)) = kv.idx(1);
    return d;
}
V dict_of(const V& src, std::initializer_list<std::pair<V, V>> extra) {
    V d = dict_of(src);
    for (auto& p : extra) d.at(p.first) = p.second;
    return d;
}
const V& dict_spread_marker() { static V m(Sym("__**spread**__")); return m; }
V dict_with_spread(std::initializer_list<std::pair<V, V>> kv) {
    V d = V::dict();
    for (auto& p : kv) {
        if (p.first.t == V::STR && str_eq(p.first, dict_spread_marker())) {
            V src = dict_of(p.second);
            for (auto& q : src.kv()) d.at(q.first) = q.second;
        } else d.at(p.first) = p.second;
    }
    return d;
}
V filter(const V& f, const V& seq) {
    std::vector<V> out;
    for (V held_ = iter_list(seq); auto& x : held_.items()) if ((f.is_none() ? x : f.call(Args{x})).truthy()) out.push_back(x);
    return V::list(std::move(out));
}
V map(const V& f, const V& seq) {
    std::vector<V> out;
    for (V held_ = iter_list(seq); auto& x : held_.items()) out.push_back(f.call(Args{x}));
    return V::list(std::move(out));
}
V hash(const V& v) { return V(double(py_hash(v) & ((1ull << 52) - 1))); }
V print(const Args& a) { for (auto& x : a.pos) printf("%s ", py_str(x).c_str()); printf("\n"); return V::none(); }
V chr(const V& v) {
    uint32_t c = uint32_t(v.num());
    std::string s;
    if (c < 0x80) s += char(c);
    else if (c < 0x800) { s += char(0xC0 | (c >> 6)); s += char(0x80 | (c & 0x3F)); }
    else if (c < 0x10000) { s += char(0xE0 | (c >> 12)); s += char(0x80 | ((c >> 6) & 0x3F)); s += char(0x80 | (c & 0x3F)); }
    else { s += char(0xF0 | (c >> 18)); s += char(0x80 | ((c >> 12) & 0x3F)); s += char(0x80 | ((c >> 6) & 0x3F)); s += char(0x80 | (c & 0x3F)); }
    return V(s);
}
V ord(const V& v) {
    const std::string& s = v.str();
    unsigned char c0 = s[0];
    if (c0 < 0x80) return V(double(c0));
    if ((c0 >> 5) == 6) return V(double(((c0 & 0x1F) << 6) | (s[1] & 0x3F)));
    if ((c0 >> 4) == 14) return V(double(((c0 & 0x0F) << 12) | ((s[1] & 0x3F) << 6) | (s[2] & 0x3F)));
    return V(double(((c0 & 0x07) << 18) | ((s[1] & 0x3F) << 12) | ((s[2] & 0x3F) << 6) | (s[3] & 0x3F)));
}
V bytes_v(const char* hex) {   // bytes literal: raw bytes in a string value
    std::string out;
    for (size_t i = 0; hex[i] && hex[i + 1]; i += 2) out += char(std::stoi(std::string(hex + i, 2), nullptr, 16));
    return V::bytes(std::move(out));
}
struct PlainObject : PyObj { const char* type_name() const override { return "object"; } };
V new_object() { return V::inst(std::make_shared<PlainObject>()); }
void delattr(const V& o, Sym name) {
    if (o.t == V::INST) {
        auto& d = o.box->inst->dyn;
        for (size_t i = 0; i < d.size(); ++i) if (d[i].first == name) { d.erase(d.begin() + i); return; }
        if (V* s = o.box->inst->slot(name)) { s->del(); return; }
    }
    throw PyError("AttributeError", name.str());
}
V slice_step(const V& seq, const V& start, const V& stop, const V& step) {
    int64_t st = step.is_none() ? 1 : int64_t(step.num());
    if (st == 1) return slice(seq, start, stop);
    V l = list_it(seq);
    int64_t n = int64_t(l.len());
    std::vector<V> out;
    if (st > 0) {
        int64_t a = start.is_none() ? 0 : int64_t(start.num()), b = stop.is_none() ? n : int64_t(stop.num());
        if (a < 0) a += n; if (b < 0) b += n;
        a = std::clamp<int64_t>(a, 0, n); b = std::clamp<int64_t>(b, 0, n);
        for (int64_t i = a; i < b; i += st) out.push_back(l.idx(i));
    } else {
        int64_t a = start.is_none() ? n - 1 : int64_t(start.num()), b = stop.is_none() ? -1 : int64_t(stop.num());
        if (!start.is_none() && a < 0) a += n;
        if (!stop.is_none() && b < 0) b += n;
        a = std::min(a, n - 1);
        for (int64_t i = a; i > b && i >= 0; i += st) out.push_back(l.idx(i));
    }
    return seq.t == V::TUPLE ? V::tuple(out) : V::list(out);
}

V concat_star(std::initializer_list<Piece> parts) {
    std::vector<V> out;
    for (auto& p : parts) {
        if (p.star) for (V held_ = iter_list(p.v); auto& x : held_.items()) out.push_back(x);
        else out.push_back(p.v);
    }
    return V::list(std::move(out));
}
Args star_args(std::initializer_list<V> pos, const V& star, std::initializer_list<std::pair<Sym, V>> kw, const V& kwstar) {
    Args a;
    a.pos.assign(pos.begin(), pos.end());
    if (star.has() && !star.is_none()) for (V held_ = iter_list(star); auto& x : held_.items()) a.pos.push_back(x);
    a.kw.assign(kw.begin(), kw.end());
    if (kwstar.has() && !kwstar.is_none()) {
        V d = dict_of(kwstar);
        for (auto& p : d.kv()) a.kw.emplace_back(p.first.sym(), p.second);
    }
    return a;
}

V max_it(const V& seq, const Key& key, const V& dflt) {
    V it = iter_list(seq);
    if (it.len() == 0) {
        if (dflt.has()) return dflt;
        throw PyError("ValueError", "max() arg is an empty sequence");
    }
    V best = it.idx(0), bk = key(best);
    for (size_t i = 1; i < it.len(); ++i) {
        V k = key(it.idx(int64_t(i)));
        if (py_lt(bk, k)) { best = it.idx(int64_t(i)); bk = k; }
    }
    return best;
}
V min_it(const V& seq, const Key& key, const V& dflt) {
    V it = iter_list(seq);
    if (it.len() == 0) {
        if (dflt.has()) return dflt;
        throw PyError("ValueError", "min() arg is an empty sequence");
    }
    V best = it.idx(0), bk = key(best);
    for (size_t i = 1; i < it.len(); ++i) {
        V k = key(it.idx(int64_t(i)));
        if (py_lt(k, bk)) { best = it.idx(int64_t(i)); bk = k; }
    }
    return best;
}
V sorted_it(const V& seq, const Key& key, bool reverse) {
    V l = list_it(seq);
    std::vector<std::pair<V, V>> kv;
    for (auto& x : l.items()) kv.emplace_back(key(x), x);
    if (reverse)
        std::stable_sort(kv.begin(), kv.end(), [](auto& a, auto& b) { return py_lt(b.first, a.first); });
    else
        std::stable_sort(kv.begin(), kv.end(), [](auto& a, auto& b) { return py_lt(a.first, b.first); });
    std::vector<V> out;
    for (auto& p : kv) out.push_back(p.second);
    return V::list(std::move(out));
}
V sort_inplace(const V& seq, const Args& a) {
    Key key;
    bool rev = false;
    for (auto& p : a.kw) {
        if (p.first == Sym("key")) key = Key(p.second);
        if (p.first == Sym("reverse")) rev = p.second.truthy();
    }
    V s = sorted_it(seq, key, rev);
    const_cast<V&>(seq).items() = s.items();
    return V::none();
}

// ---------------------------------------------------------------- strings
static std::string fmt_one(const std::string& spec, const V& v) {
    // spec like "%.2f", "%d", "%s", "%r", "%5.1f", "%x"
    char conv = spec.back();
    char buf[128];
    std::string f = spec;
    if (conv == 's') return py_str(v);
    if (conv == 'r') return repr(v).str();
    if (conv == 'd' || conv == 'i') {
        f.back() = 'l'; f += "ld";
        snprintf(buf, sizeof buf, f.c_str(), (long long)std::trunc(v.num()));
        return buf;
    }
    if (conv == 'x' || conv == 'X') {
        f.pop_back(); f += "ll"; f += conv;
        snprintf(buf, sizeof buf, f.c_str(), (long long)v.num());
        return buf;
    }
    snprintf(buf, sizeof buf, f.c_str(), v.num());
    return buf;
}
V percent(const V& fmt, const V& args) {
    const std::string& s = fmt.str();
    std::vector<V> av = args.t == V::TUPLE ? args.items() : std::vector<V>{args};
    std::string out;
    size_t ai = 0;
    for (size_t i = 0; i < s.size(); ++i) {
        if (s[i] != '%') { out += s[i]; continue; }
        if (i + 1 < s.size() && s[i + 1] == '%') { out += '%'; ++i; continue; }
        size_t j = i + 1;
        while (j < s.size() && std::string("0123456789.-+ #").find(s[j]) != std::string::npos) ++j;
        std::string spec = s.substr(i, j - i + 1);
        out += fmt_one(spec, ai < av.size() ? av[ai] : V::none());
        ++ai;
        i = j;
    }
    return V(out);
}
V format_spec(const V& v, const V& spec) {
    const std::string& sp = spec.is_str() ? spec.str() : std::string();
    if (sp.empty()) return V(py_str(v));
    std::string s = sp;
    std::string printf_spec = "%";
    if (s.back() == 'f' || s.back() == 'd' || s.back() == 'x' || s.back() == 'g' || s.back() == 'e' || s.back() == 's')
        printf_spec += s;
    else printf_spec += s + "s";
    if (printf_spec.find(',') != std::string::npos) printf_spec.erase(printf_spec.find(','), 1);
    return V(fmt_one(printf_spec, v));
}
V concat_str(std::initializer_list<V> parts) {
    std::string out;
    for (auto& p : parts) out += p.is_str() ? p.str() : py_str(p);
    return V(out);
}

// ---------------------------------------------------------------- exceptions
struct ExcObj : PyObj {
    std::string kind, msg;
    std::vector<std::string> bases;
    V args;
    const char* type_name() const override { return kind.c_str(); }
    bool isa(const char* c) const override {
        return std::string(c)=="object" || pvz::exception_matches(kind,bases,c);
    }
    V* slot(Sym n) override { if (n == Sym("args")) return &args; return nullptr; }
    bool call_method(Sym n, const Args&, V& out) override {
        if (n.str() != "__str__") return false;
        const auto& it = args.items();
        if (it.size() == 2 && it[0].is_num()) out = V("[Errno " + std::to_string(int64_t(it[0].num())) + "] " + py_str(it[1]));
        else if (it.size() == 1) out = V(py_str(it[0]));
        else if (it.empty()) out = V(msg);
        else out = V(dump(args));
        return true;
    }
};
V make_exc(const V& type, const Args& a, const char* bases) {
    auto e = std::make_shared<ExcObj>();
    e->kind = type.str();
    e->args = V::tuple(a.pos);
    e->msg = a.pos.empty() ? std::string() : py_str(a.pos[0]);
    std::string b(bases);
    size_t p = 0;
    while (!b.empty() && p <= b.size()) {
        size_t q = b.find(',', p);
        e->bases.push_back(b.substr(p, q == std::string::npos ? std::string::npos : q - p));
        if (q == std::string::npos) break;
        p = q + 1;
    }
    return V::inst(e);
}
void raise(const V& exc) {
    if (exc.t == V::INST) {
        if (auto* e = dynamic_cast<ExcObj*>(exc.box->inst.get())) throw PyError(e->kind, e->msg, e->bases);
    }
    if (exc.t == V::STR) throw PyError(exc.str(), "");
    throw PyError("Exception", py_str(exc));
}
V exc_value(const PyError& e) {
    auto x = std::make_shared<ExcObj>();
    x->kind = e.kind;
    std::string w = e.what();
    x->msg = w.size() > e.kind.size() + 2 ? w.substr(e.kind.size() + 2) : std::string();
    x->bases = e.bases;
    x->args = V::tuple({V(x->msg)});
    return V::inst(x);
}
V exc_type(const V& name) { return name; }

// ---------------------------------------------------------------- generators
struct GenObj : PyObj {
    PyGen g;
    GenKind kind;
    std::shared_ptr<PyObj> owner;   // keeps `this` of member coroutines alive
    bool started = false, finished = false;
    const char* type_name() const override { return kind == GenKind::CONTEXT ? "_GeneratorContextManager" : "generator"; }
    V iterate() override {
        std::vector<V> out;
        while (!finished && g.step()) out.push_back(g.h.promise().current);
        finished = true;
        return V::list(std::move(out));
    }
    V next_or(const V& dflt) {
        if (!finished && g.step()) return g.h.promise().current;
        finished = true;
        return dflt;
    }
};
V make_gen(GenKind kind, PyGen g, std::shared_ptr<PyObj> owner) {
    auto p = std::make_shared<GenObj>();
    p->g = std::move(g);
    p->kind = kind;
    p->owner = std::move(owner);
    return V::inst(p);
}
V next(const V& it, const V& dflt) {
    if (it.t == V::INST) {
        if (auto* g = dynamic_cast<GenObj*>(it.box->inst.get())) return g->next_or(dflt);
        if (auto* i = dynamic_cast<IterObj*>(it.box->inst.get())) {
            if (i->pos < i->items.len()) return i->items.idx(int64_t(i->pos++));
            return dflt;
        }
    }
    V l = iter_list(it);
    if (l.len()) return l.idx(0);
    return dflt;
}

WithGuard::WithGuard(const V& m) : mgr(m) {
    if (m.t == V::INST) {
        if (auto* g = dynamic_cast<GenObj*>(m.box->inst.get())) {
            if (!g->g.step()) throw PyError("RuntimeError", "generator didn't yield");
            value = g->g.h.promise().current;
            return;
        }
        if (m.box->inst->hasattr(Sym("__enter__"))) { value = callm(m, Sym("__enter__"), Args{}); return; }
    }
    if (m.is_none()) { value = V::none(); return; }   // nullcontext()
    throw PyError("TypeError", "object does not support the context manager protocol");
}
WithGuard::~WithGuard() noexcept(false) {
    bool unwinding = std::uncaught_exceptions() > 0;
    if (mgr.t == V::INST) {
        if (auto* g = dynamic_cast<GenObj*>(mgr.box->inst.get())) {
            if (unwinding) {
                // throw into the generator so its finally/except blocks run; swallow
                // whatever it raises (the original exception keeps propagating)
                g->g.h.promise().inject = std::make_exception_ptr(PyError("GeneratorExit", "with-body raised"));
                try { g->g.step(); } catch (...) {}
                return;
            }
            if (g->g.step()) throw PyError("RuntimeError", "generator didn't stop");
            return;
        }
        if (mgr.box->inst->hasattr(Sym("__exit__"))) {
            if (unwinding) { try { callm(mgr, Sym("__exit__"), Args{V::none(), V::none(), V::none()}); } catch (...) {} }
            else callm(mgr, Sym("__exit__"), Args{V::none(), V::none(), V::none()});
        }
    }
}

// ---------------------------------------------------------------- classes, modules, stdlib
V class_value(const V& name, Fn ctor) {
    V f = V::func(std::move(ctor));
    f.box->fattrs.emplace_back(Sym("__name__"), name);
    f.box->fattrs.emplace_back(Sym("__native_class_value__"),V(true));
    return f;
}
V class_method_override(const V& type, Sym name, const V& self) {
    if (type.t != V::FUNC) return V();
    // PvP73: interned once (each Sym("...") construction is a locked intern-table lookup; this runs
    // on every method dispatch of a class with native dispatch, e.g. the whole world renderer).
    static const Sym kDispatch("__native_class_dispatch__"), kStatics("__native_static_methods__"), kDeclared("__native_declared_method__");
    bool enabled = false; V statics;
    for (auto& [key, value] : type.box->fattrs) {
        if (key == kDispatch) enabled = value.truthy();
        else if (key == kStatics) statics = value;
    }
    if (!enabled) return V();
    for (auto& [key, value] : type.box->fattrs) if (key == name) {
        if (value.t == V::FUNC) {
            for (auto& [marker, ignored] : value.box->fattrs)
                if (marker == kDeclared) return V();
            if (statics.has() && statics.contains(V(name))) return value;
            return V::func([implementation = value, self](const Args& a) { Args bound = a; bound.pos.insert(bound.pos.begin(), self); return implementation.call(bound); });
        }
        // Mock instances are callable objects, not function descriptors: no implicit self.
        return value;
    }
    return V();
}
static std::map<std::string, V (*)(Sym)>& module_attr_tables() { static std::map<std::string, V (*)(Sym)> t; return t; }
void register_module_attrs(const char* name, V (*attrs)(Sym)) { module_attr_tables()[name] = attrs; }
V& loaded_modules() { static V d = V::dict(); return d; }
void note_module_loaded(const char* qualname) {
    V& d = loaded_modules();
    std::string q = qualname;
    std::string bare = q.rfind("pvp.", 0) == 0 ? q.substr(4) : q;
    d.at(V(q)) = module_ns(V(bare));
}
struct ModuleNS : PyObj {
    std::string name;
    const char* type_name() const override { return "module"; }
    V lookup(Sym n) {
        auto& t = module_attr_tables();
        auto it = t.find(name);
        return it == t.end() ? V() : it->second(n);
    }
    V property(Sym n, bool& found) override {
        V v = lookup(n);
        found = v.has();
        if (!found && n.str() == "__name__") { found = true; return V(name.rfind("test_pvp_",0)==0 ? name : "pvp." + name); }
        return v;
    }
    V method(Sym n) override { return lookup(n); }
    bool set_property(Sym n, const V& value) override {
        std::string hook = "module.write." + name;
        if (!has_native_hook(hook)) return false;
        return native_hook(V(hook), Args{V(n), value}).truthy();
    }
    bool call_method(Sym n, const Args& a, V& out) override {
        V f = lookup(n);
        if (!f.has()) return false;
        out = f.call(a);
        return true;
    }
};
const V& dict_missing(const V& d, const V& k) {
    if (d.t == V::DICT && d.box->missing == 1) { static const V zero(0.0); return zero; }
    if (d.t == V::DICT && d.box->missing == 2) {
        V v = d.box->fattrs.at(0).second.call(Args{});
        V& slot = const_cast<V&>(d).at(k);
        slot = v;
        return slot;
    }
    if(d.t==V::DICT && d.box->missing==3) {
        for(const auto& attr:d.box->fattrs)if(attr.first==Sym("__native_template_alias__")) {
            V key=attr.second.call(Args{d,k});if(const V* value=d.find(key))return *value;break;
        }
    }
    throw PyError("KeyError", py_str(k));
}
V native_template_missing(const V& dictionary,const V& key) {return dict_missing(dictionary,key);}
V module_ns(const V& name) {
    static std::map<std::string, V> mods;
    auto it = mods.find(name.str());
    if (it != mods.end()) return it->second;
    auto p = std::make_shared<ModuleNS>();
    p->name = name.str();
    V v = V::inst(p);
    mods[name.str()] = v;
    return v;
}

struct RandomObj : PyObj {
    PyRandom rng; double gauss_next = 0; bool has_gauss_next = false;
    const char* type_name() const override { return "Random"; }
    bool isa(const char* c) const override { return std::string(c) == "Random" || std::string(c) == "object"; }
    V method(Sym name) override;
};
V make_random(int64_t seed) { auto p = std::make_shared<RandomObj>(); p->rng.seed(seed); return V::inst(p); }
PyRandom* random_of(const V& v) {
    if (auto* r = as<RandomObj>(v)) return &r->rng;
    return nullptr;
}
V RandomObj::method(Sym name) {
    auto sp = std::static_pointer_cast<RandomObj>(shared_from_this());
    const std::string& n = name.str();
    if (n == "randint") return V::func([sp](const Args& a) { return V(double(sp->rng.randint(int64_t(a.pos.at(0).num()), int64_t(a.pos.at(1).num())))); });
    if (n == "random") return V::func([sp](const Args&) { return V(sp->rng.random()); });
    if (n == "uniform") return V::func([sp](const Args& a) { return V(sp->rng.uniform(a.pos.at(0).num(), a.pos.at(1).num())); });
    // CPython's normalvariate (Kinderman-Monahan) / gauss (Box-Muller with cached second value)
    if (n == "normalvariate" || n == "lognormvariate") {
        bool lg = n == "lognormvariate";
        return V::func([sp, lg](const Args& a) {
            double mu = a.pos.size() > 0 ? a.pos[0].num() : 0.0, sigma = a.pos.size() > 1 ? a.pos[1].num() : 1.0;
            const double NV_MAGICCONST = 4 * std::exp(-0.5) / std::sqrt(2.0);
            double z;
            for (;;) {
                double u1 = sp->rng.random(), u2 = 1.0 - sp->rng.random();
                z = NV_MAGICCONST * (u1 - 0.5) / u2;
                if (z * z / 4.0 <= -std::log(u2)) break;
            }
            double r = mu + z * sigma;
            return V(lg ? std::exp(r) : r);
        });
    }
    if (n == "getrandbits") return V::func([sp](const Args& a) {   // CPython word order (k <= 53 here)
        int k = int(a.pos.at(0).num());
        if (k <= 32) return V(double(sp->rng.genrand() >> (32 - k)));
        uint64_t lo = sp->rng.genrand();
        uint64_t hi = sp->rng.genrand() >> (64 - k);
        return V(double((hi << 32) | lo));
    });
    if (n == "gauss") return V::func([sp](const Args& a) {
        double mu = a.pos.size() > 0 ? a.pos[0].num() : 0.0, sigma = a.pos.size() > 1 ? a.pos[1].num() : 1.0;
        double z;
        if (sp->has_gauss_next) { z = sp->gauss_next; sp->has_gauss_next = false; }
        else {
            double x2pi = sp->rng.random() * 2 * 3.14159265358979323846, g2rad = std::sqrt(-2.0 * std::log(1.0 - sp->rng.random()));
            z = std::cos(x2pi) * g2rad; sp->gauss_next = std::sin(x2pi) * g2rad; sp->has_gauss_next = true;
        }
        return V(mu + z * sigma);
    });
    if (n == "choice") return V::func([sp](const Args& a) { V s = iter_list(a.pos.at(0)); return s.idx(int64_t(sp->rng.choice_index(s.len()))); });
    if (n == "randrange") return V::func([sp](const Args& a) {
        if (a.pos.size() == 1) return V(double(sp->rng.randrange(int64_t(a.pos[0].num()))));
        return V(double(sp->rng.randrange(int64_t(a.pos[0].num()), int64_t(a.pos[1].num()))));
    });
    if (n == "shuffle") return V::func([sp](const Args& a) {
        auto& it = const_cast<V&>(a.pos.at(0)).items();
        sp->rng.shuffle(it.size(), [&](size_t i, size_t j) { std::swap(it[i], it[j]); });
        return V::none();
    });
    if (n == "getstate") return V::func([sp](const Args&) {
        auto st = sp->rng.state();
        std::vector<V> words;
        for (int i = 0; i < 624; ++i) words.emplace_back(double(st.mt[i]));
        words.emplace_back(double(st.mti));
        return V::tuple({V(3.0), V::tuple(words), V::none()});
    });
    if (n == "setstate") return V::func([sp](const Args& a) {
        const V& w = a.pos.at(0).idx(1);
        PyRandom::State st;
        for (int i = 0; i < 624; ++i) st.mt[i] = uint32_t(w.idx(i).num());
        st.mti = int(w.idx(624).num());
        sp->rng.set_state(st);
        return V::none();
    });
    if (n == "seed") return V::func([sp](const Args& a) { sp->rng.seed(int64_t(a.pos.at(0).num())); return V::none(); });
    if (n == "sample") return V::func([sp](const Args& a) {
        // CPython 3.8 Random.sample (pool for small populations, rejection set otherwise)
        V popv = a.get(0, Sym("population"), nullptr, "sample");
        if (popv.t == V::DICT || popv.is_obj()) throw PyError("TypeError", "Population must be a sequence or set.  For dicts, use list(d).");
        std::vector<V> pop = iter_list(popv).items();
        int64_t k = int64_t(a.get(1, Sym("k"), nullptr, "sample").num());
        int64_t nn = int64_t(pop.size());
        if (k < 0 || k > nn) throw PyError("ValueError", "Sample larger than population or is negative");
        std::vector<V> result(static_cast<size_t>(k));
        int64_t setsize = 21;
        if (k > 5) setsize += int64_t(std::pow(4.0, std::ceil(std::log(double(k * 3)) / std::log(4.0))));
        if (nn <= setsize) {
            std::vector<V> pool = pop;
            for (int64_t i = 0; i < k; ++i) {
                int64_t j = int64_t(sp->rng.randbelow(uint64_t(nn - i)));
                result[size_t(i)] = pool[size_t(j)];
                pool[size_t(j)] = pool[size_t(nn - i - 1)];
            }
        } else {
            std::vector<int64_t> selected;
            for (int64_t i = 0; i < k; ++i) {
                int64_t j = int64_t(sp->rng.randbelow(uint64_t(nn)));
                while (std::find(selected.begin(), selected.end(), j) != selected.end()) j = int64_t(sp->rng.randbelow(uint64_t(nn)));
                selected.push_back(j);
                result[size_t(i)] = pop[size_t(j)];
            }
        }
        return V::list(std::move(result));
    });
    if (n == "choices") return V::func([sp](const Args& a) {
        // CPython 3.8 Random.choices
        std::vector<V> pop = iter_list(a.get(0, Sym("population"), nullptr, "choices")).items();
        static const V none_v = V::none(), one_v(1.0);
        V weights = a.get(1, Sym("weights"), &none_v), cum = a.get(2, Sym("cum_weights"), &none_v);
        int64_t k = int64_t(a.get(3, Sym("k"), &one_v).num());
        double nn = double(pop.size());
        std::vector<V> out;
        if (cum.is_none()) {
            if (weights.is_none()) {
                for (int64_t i = 0; i < k; ++i) out.push_back(pop[size_t(int64_t(sp->rng.random() * nn))]);
                return V::list(std::move(out));
            }
            std::vector<V> c; V acc;
            bool first = true;
            for (V held_ = iter_list(weights); auto& w : held_.items()) { acc = first ? w : acc + w; first = false; c.push_back(acc); }
            cum = V::list(c);
        } else if (!weights.is_none()) {
            throw PyError("TypeError", "Cannot specify both weights and cumulative weights");
        }
        auto& cw = cum.items();
        if (cw.size() != pop.size()) throw PyError("ValueError", "The number of weights does not match the population");
        double total = cw.back().num() + 0.0;
        size_t hi = pop.size() - 1;
        for (int64_t i = 0; i < k; ++i) {
            double x = sp->rng.random() * total;
            size_t lo = 0, h = hi;   // bisect_right(cum, x, 0, hi)
            while (lo < h) { size_t mid = (lo + h) / 2; if (x < cw[mid].num()) h = mid; else lo = mid + 1; }
            out.push_back(pop[lo]);
        }
        return V::list(std::move(out));
    });
    return V();
}

// ---- hashlib.sha256 (coop run seeds)
static std::string sha256_hex(const std::string& msg) {
    static const uint32_t K[64] = {
        0x428a2f98,0x71374491,0xb5c0fbcf,0xe9b5dba5,0x3956c25b,0x59f111f1,0x923f82a4,0xab1c5ed5,0xd807aa98,0x12835b01,
        0x243185be,0x550c7dc3,0x72be5d74,0x80deb1fe,0x9bdc06a7,0xc19bf174,0xe49b69c1,0xefbe4786,0x0fc19dc6,0x240ca1cc,
        0x2de92c6f,0x4a7484aa,0x5cb0a9dc,0x76f988da,0x983e5152,0xa831c66d,0xb00327c8,0xbf597fc7,0xc6e00bf3,0xd5a79147,
        0x06ca6351,0x14292967,0x27b70a85,0x2e1b2138,0x4d2c6dfc,0x53380d13,0x650a7354,0x766a0abb,0x81c2c92e,0x92722c85,
        0xa2bfe8a1,0xa81a664b,0xc24b8b70,0xc76c51a3,0xd192e819,0xd6990624,0xf40e3585,0x106aa070,0x19a4c116,0x1e376c08,
        0x2748774c,0x34b0bcb5,0x391c0cb3,0x4ed8aa4a,0x5b9cca4f,0x682e6ff3,0x748f82ee,0x78a5636f,0x84c87814,0x8cc70208,
        0x90befffa,0xa4506ceb,0xbef9a3f7,0xc67178f2};
    uint32_t h[8] = {0x6a09e667,0xbb67ae85,0x3c6ef372,0xa54ff53a,0x510e527f,0x9b05688c,0x1f83d9ab,0x5be0cd19};
    std::string m = msg;
    uint64_t bits = uint64_t(msg.size()) * 8;
    m += char(0x80);
    while (m.size() % 64 != 56) m += char(0);
    for (int i = 7; i >= 0; --i) m += char((bits >> (i * 8)) & 0xff);
    auto rotr = [](uint32_t x, int n) { return (x >> n) | (x << (32 - n)); };
    for (size_t off = 0; off < m.size(); off += 64) {
        uint32_t w[64];
        for (int i = 0; i < 16; ++i)
            w[i] = (uint32_t(uint8_t(m[off + i * 4])) << 24) | (uint32_t(uint8_t(m[off + i * 4 + 1])) << 16) |
                   (uint32_t(uint8_t(m[off + i * 4 + 2])) << 8) | uint32_t(uint8_t(m[off + i * 4 + 3]));
        for (int i = 16; i < 64; ++i) {
            uint32_t s0 = rotr(w[i - 15], 7) ^ rotr(w[i - 15], 18) ^ (w[i - 15] >> 3);
            uint32_t s1 = rotr(w[i - 2], 17) ^ rotr(w[i - 2], 19) ^ (w[i - 2] >> 10);
            w[i] = w[i - 16] + s0 + w[i - 7] + s1;
        }
        uint32_t a = h[0], b = h[1], c = h[2], d = h[3], e = h[4], f = h[5], g = h[6], hh = h[7];
        for (int i = 0; i < 64; ++i) {
            uint32_t S1 = rotr(e, 6) ^ rotr(e, 11) ^ rotr(e, 25);
            uint32_t ch = (e & f) ^ (~e & g);
            uint32_t t1 = hh + S1 + ch + K[i] + w[i];
            uint32_t S0 = rotr(a, 2) ^ rotr(a, 13) ^ rotr(a, 22);
            uint32_t mj = (a & b) ^ (a & c) ^ (b & c);
            uint32_t t2 = S0 + mj;
            hh = g; g = f; f = e; e = d + t1; d = c; c = b; b = a; a = t1 + t2;
        }
        h[0] += a; h[1] += b; h[2] += c; h[3] += d; h[4] += e; h[5] += f; h[6] += g; h[7] += hh;
    }
    char buf[65];
    for (int i = 0; i < 8; ++i) snprintf(buf + i * 8, 9, "%08x", h[i]);
    return std::string(buf, 64);
}
struct Sha256Obj : PyObj {
    std::string data;
    const char* type_name() const override { return "sha256"; }
    V method(Sym name) override {
        auto sp = std::static_pointer_cast<Sha256Obj>(shared_from_this());
        if (name.str() == "hexdigest") return V::func([sp](const Args&) { return V(sha256_hex(sp->data)); });
        if (name.str() == "update") return V::func([sp](const Args& a) { sp->data += a.pos.at(0).str(); return V::none(); });
        return V();
    }
};
V sha256_obj(const V& data) {
    auto p = std::make_shared<Sha256Obj>();
    p->data = data.is_str() ? data.str() : std::string();
    if (p->data.rfind("bytes:", 0) == 0) p->data = p->data.substr(6);
    return V::inst(p);
}

V path_new(const Args& a);
static V jv_(const nlohmann::json& j) {
    if (j.is_null()) return V::none();
    if (j.is_boolean()) return V(j.get<bool>());
    if (j.is_number()) return V(j.get<double>());
    if (j.is_string()) return V(j.get<std::string>());
    if (j.is_array()) { std::vector<V> it; for (auto& x : j) it.push_back(jv_(x)); return V::list(it); }
    V d = V::dict();
    for (auto it = j.begin(); it != j.end(); ++it) d.at(V(it.key())) = jv_(it.value());
    return d;
}
V json_loads(const V& text) { return jv_(nlohmann::json::parse(text.str())); }

bool g_real_clock = false;
static V registered_path(const std::string& dotted);
static V stdlib_override_path(const std::string& dotted);
static std::map<std::string, V>& stdlib_module_cache() { static std::map<std::string, V> modules; return modules; }
static thread_local std::map<std::string, size_t> stdlib_override_skip;
V stdlib(const V& name) {
    { V r = registered_path(name.str()); if (r.has()) return r; }   // `from pkg import submodule`
    if(name.str()=="types.MethodType")return native_method_type();
    if(name.str()=="collections.OrderedDict")return native_ordered_dict_type();
    // a bare name is an `import <module>` binding used as a value (ns.update(copy=copy)): the module object
    if (name.str().find('.') == std::string::npos) return stdlib_module(name);
    return V::func([name](const Args& a) { return stdlib_call(name, a); });
}
// modules provided by native code outside the simulation (the UI's pygame facade ...)
static std::map<std::string, V>& registered_modules() { static std::map<std::string, V> m; return m; }
void register_module(const std::string& name, const V& module) { registered_modules()[name] = module; }
// "pygame.display.set_mode" -> the registered module's attribute chain (ABSENT when not registered)
static V registered_path(const std::string& dotted) {
    auto& reg = registered_modules();
    size_t prefix = dotted.size();
    auto it = reg.find(dotted);
    while (it == reg.end()) {
        if (!prefix) break;
        size_t previous = dotted.rfind('.', prefix - 1);
        if (previous == std::string::npos) break;
        prefix = previous;
        it = reg.find(dotted.substr(0, prefix));
    }
    if (it == reg.end()) {
        std::string native=dotted.rfind("pvp.",0)==0?dotted.substr(4):dotted;
        size_t dot=native.find('.');std::string root=native.substr(0,dot);
        if(module_attr_tables().count(root)) {
            V current=module_ns(V(root));
            auto captured=stdlib_override_skip.find(dotted);
            if(dot!=std::string::npos && captured!=stdlib_override_skip.end() && captured->second) {
                size_t next=native.find('.',dot+1);
                current=module_attr_tables().at(root)(Sym(native.substr(dot+1,next==std::string::npos?next:next-dot-1)));
                if(!current.has())return V();dot=next;
            }
            while(dot!=std::string::npos) {
                size_t next=native.find('.',dot+1);
                current=pvz::getattr(current,Sym(native.substr(dot+1,next==std::string::npos?next:next-dot-1)));
                dot=next;
            }
            return current;
        }
        return stdlib_override_path(dotted);
    }
    size_t dot = prefix == dotted.size() ? std::string::npos : prefix;
    V cur = it->second;
    while (dot != std::string::npos) {
        size_t next = dotted.find('.', dot + 1);
        cur = pvz::getattr(cur, Sym(dotted.substr(dot + 1, next == std::string::npos ? std::string::npos : next - dot - 1)));
        dot = next;
    }
    return cur;
}
V stdlib_attr(const V& mod, const V& attr) {
    std::string m = mod.str(), at = attr.str();
    // `import importlib.util` then `importlib.util.f`: the translator emits (module "importlib.util", attr "util")
    // meaning the submodule itself, i.e. the dotted path m, not m.util
    if (m.size() > at.size() + 1 && m.compare(m.size() - at.size() - 1, std::string::npos, "." + at) == 0) {
        V r = registered_path(m); if (r.has()) return r;
    }
    { V r = registered_path(m + "." + at); if (r.has()) return r; }
    if (m == "math" && at == "pi") return V(3.141592653589793);
    if (m == "math" && at == "inf") return V(INFINITY);
    if (m == "math" && at == "tau") return V(6.283185307179586);
    if ((m == "os" && at == "path") || (m == "importlib" && at == "util")) return stdlib_module(V(m + "." + at));
    return pvz::getattr(stdlib_module(mod), Sym(at));
}
static double D(const Args& a, size_t i) { return a.pos.at(i).num(); }
V stdlib_call(const V& name, const Args& a) {
    const std::string& n = name.str();
    { V r = registered_path(n); if (r.has()) return r.call(a); }
    if(n=="marshal.dumps")return native_marshal_dumps(a);
    if(n=="marshal.loads")return native_marshal_loads(a);
    if(n.rfind("tracemalloc.",0)==0) {
        if(n=="tracemalloc.start") {
            if(a.pos.size()>1 || !a.kw.empty())throw PyError("TypeError","start accepts at most one frame limit");
            if(!a.pos.empty() && (a.pos[0].num()<1 || a.pos[0].num()>65535))throw PyError("ValueError","invalid frame limit");
            native_alloc_trace_start();return V::none();
        }
        if(!a.pos.empty() || !a.kw.empty())throw PyError("TypeError","native allocation trace operation takes no arguments");
        if(n=="tracemalloc.stop"){native_alloc_trace_stop();return V::none();}
        if(n=="tracemalloc.is_tracing")return V(native_alloc_trace_active());
        if(n=="tracemalloc.reset_peak"){native_alloc_trace_reset_peak();return V::none();}
        if(n=="tracemalloc.get_traced_memory") {uint64_t current=0,peak=0;native_alloc_trace_read(current,peak);return V::tuple({V(double(current)),V(double(peak))});}
        throw PyError("NotImplementedError","native allocation tracing provides byte counters, not CPython frame snapshots");
    }
    if(n=="contextlib.ExitStack")return native_exit_stack(a);
    if(n.rfind("gc.",0)==0)return callm(native_gc_module(),Sym(n.substr(3)),a);
    if (n == "math.hypot") return V(std::hypot(D(a, 0), D(a, 1)));
    if (n == "math.prod") {
        static const V one(1);
        V product = a.get(999999, Sym("start"), &one);
        V values = iter_list(a.get(0, Sym("iterable"), nullptr, "prod"));
        for (const V& value : values.items()) product = product * value;
        return product;
    }
    if (n == "math.floor") return V(std::floor(D(a, 0)));
    if (n == "math.ceil") return V(std::ceil(D(a, 0)));
    if (n == "math.sin") return V(std::sin(D(a, 0)));
    if (n == "math.cos") return V(std::cos(D(a, 0)));
    if (n == "math.tan") return V(std::tan(D(a, 0)));
    if (n == "math.atan2") return V(std::atan2(D(a, 0), D(a, 1)));
    if (n == "math.atan") return V(std::atan(D(a, 0)));
    if (n == "math.asin") return V(std::asin(D(a, 0)));
    if (n == "math.acos") return V(std::acos(D(a, 0)));
    if (n == "math.sqrt") return V(std::sqrt(D(a, 0)));
    if (n == "math.exp") return V(std::exp(D(a, 0)));
    if (n == "math.log") return a.pos.size() > 1 ? V(std::log(D(a, 0)) / std::log(D(a, 1))) : V(std::log(D(a, 0)));
    if (n == "math.degrees") return V(D(a, 0) * (180.0 / 3.141592653589793));
    if (n == "math.radians") return V(D(a, 0) * (3.141592653589793 / 180.0));
    if (n == "math.isfinite") return V(std::isfinite(D(a, 0)));
    if (n == "math.isnan") return V(std::isnan(D(a, 0)));
    if (n == "math.copysign") return V(std::copysign(D(a, 0), D(a, 1)));
    if (n == "math.fabs") return V(std::fabs(D(a, 0)));
    if (n == "copy.deepcopy") return pvz::deepcopy(a.pos.at(0));
    if (n == "copy.copy") return copy(a.pos.at(0));
    if (n == "random.SystemRandom") return make_random(int64_t(std::chrono::steady_clock::now().time_since_epoch().count() & 0x7fffffffffffll));
    if (n == "random.Random") return make_random(a.pos.empty() ? 0 : int64_t(D(a, 0)));
    if (n.rfind("random.", 0) == 0 && n != "random.SystemRandom") {
        // module-level random.*: python's global generator, seeded from the OS (not deterministic
        // there either - only used for fresh campaign seeds and similar)
        static V global_rng = make_random(int64_t(std::chrono::steady_clock::now().time_since_epoch().count() & 0x7fffffff));
        V f = global_rng.box->inst->method(Sym(n.substr(7)));
        if (f.has()) return f.call(a);
    }
    if (n == "contextlib.nullcontext") return V::none();
    if(n=="types.MethodType")return native_method_type().call(a);
    if (n == "types.SimpleNamespace") { V d = V::dict(); d.box->fattrs.emplace_back(Sym("__native_namespace__"),V(true)); for (auto& p : a.kw) d.at(V(p.first)) = p.second; return d; }
    // functions over CPython code objects: only the old-suite harness registers this (reference replay)
    if(n=="types.CellType")return native_cell(a);
    if (n == "types.FunctionType") { V cloned=clone_native_closure(a);return cloned.has()?cloned:native_hook(V(n), a); }
    if(n=="collections.OrderedDict")return native_ordered_dict_type().call(a);
    if (n == "time.perf_counter" || n == "time.time" || n == "time.process_time" || n == "time.monotonic" || n == "time.time_ns") {
        // the oracle runner keeps a frozen clock (deterministic); the game turns on the wall clock
        if (!g_real_clock) return V(0.0);
        using namespace std::chrono;
        if (n == "time.time") return V(duration<double>(system_clock::now().time_since_epoch()).count());
        if (n == "time.time_ns") return V(double(duration_cast<nanoseconds>(system_clock::now().time_since_epoch()).count()));
        return V(duration<double>(steady_clock::now().time_since_epoch()).count());
    }
    if (n == "pathlib.Path") return path_new(a);
    if (n == "pathlib.Path.cwd") return path_new(Args{V([] { auto u = std::filesystem::current_path().u8string(); return std::string(u.begin(), u.end()); }())});
    if (n == "pathlib.Path.home") { std::string h; if (!pvz::env_u8("USERPROFILE", h)) h = "."; return path_new(Args{V(h)}); }
    if (n == "sys._getframe") return getframe();
    if (n == "json.loads") return json_loads(a.pos.at(0));
    if (n == "weakref.WeakKeyDictionary" || n == "weakref.WeakValueDictionary") return V::dict();
    if (n == "weakref.ref") {
        if(a.pos.empty() || a.pos.size()>2 || !a.kw.empty())throw PyError("TypeError","weakref.ref expects a target and an optional callback");
        if(a.pos.size()==2 && !a.pos[1].is_none())throw PyError("NotImplementedError","native weak references with callbacks are not implemented");
        const V& target=a.pos[0];
        if(target.t!=V::INST) {
            if(target.t==V::FUNC)throw PyError("NotImplementedError","native function weak references are not implemented");
            throw PyError("TypeError","cannot create a weak reference to this native value");
        }
        std::weak_ptr<PyObj> weak=target.box->inst;
        return V::func([weak](const Args& args) {
            if(!args.pos.empty() || !args.kw.empty())throw PyError("TypeError","weak reference expects no arguments");
            auto target=weak.lock();return target?V::inst(std::move(target)):V::none();
        });
    }
    if (n == "collections.deque") return make_native_deque(a);
    if (n == "collections.defaultdict") {
        V d = V::dict();
        if (!a.pos.empty() && !a.pos[0].is_none()) { d.box->missing = 2; d.box->fattrs.emplace_back(Sym("__factory__"), a.pos[0]); }
        if (a.pos.size() > 1) for (auto& kv : a.pos[1].kv()) d.at(kv.first) = kv.second;
        return d;
    }
    if (n == "collections.Counter") {
        V d = V::dict();
        d.box->missing = 1;
        if (!a.pos.empty() && !a.pos[0].is_none()) {
            const V& src = a.pos[0];
            if (src.is_dict()) { for (auto& kv : src.kv()) d.at(kv.first) = kv.second; }
            else for (V held_ = iter_list(src); auto& x : held_.items()) { V* p = const_cast<V*>(d.find(x)); if (p && p->has()) *p = V(p->num() + 1); else d.at(x) = V(1.0); }
        }
        for (auto& [k, v] : a.kw) d.at(V(k.str())) = v;
        return d;
    }
    if (n == "functools.partial") {
        V f = a.pos.at(0);
        std::vector<V> bound(a.pos.begin() + 1, a.pos.end());
        auto kw = a.kw;
        return V::func([f, bound, kw](const Args& b) {
            Args c(bound, kw);
            c.pos.insert(c.pos.end(), b.pos.begin(), b.pos.end());
            c.kw.insert(c.kw.end(), b.kw.begin(), b.kw.end());
            return f.call(c);
        });
    }
    if (n == "functools.wraps") {
        V wrapped=a.pos.at(0),assigned=a.size()>1?a.pos[1]:V::tuple({V("__module__"),V("__name__"),V("__qualname__"),V("__doc__"),V("__annotations__")}),updated=a.size()>2?a.pos[2]:V::tuple({V("__dict__")});
        return V::func([wrapped,assigned,updated](const Args& input){
            V wrapper=input.pos.at(0);
            for(V held_assigned=py::iter_list(assigned);const V& name:held_assigned.items()){V value=pvz::getattr(wrapped,name.sym(),V());if(value.has())pvz::setattr(wrapper,name.sym(),value);}
            for(V held_updated=py::iter_list(updated);const V& name:held_updated.items()){V source;try{source=pvz::getattr(wrapped,name.sym());}catch(const PyError& e){if(!e.matches("AttributeError"))throw;source=V::dict();}V target=pvz::getattr(wrapper,name.sym());for(const auto& field:py::items_vec(source))pvz::setitem(target,field.first,field.second);}
            pvz::setattr(wrapper,Sym("__wrapped__"),wrapped);return wrapper;
        });
    }
    if (n == "os.environ.get" || n == "os.getenv") return a.pos.size() > 1 ? a.pos[1] : V::none();
    if (n == "json.dumps") return V(dump(a.pos.at(0)));
    if (n == "hashlib.sha256") return sha256_obj(a.pos.empty() ? V("") : a.pos[0]);
    if (n == "itertools.zip_longest") {
        V x = iter_list(a.pos.at(0)), y = iter_list(a.pos.at(1));
        std::vector<V> out;
        size_t m = std::max(x.len(), y.len());
        for (size_t i = 0; i < m; ++i) out.push_back(V::tuple({i < x.len() ? x.idx(int64_t(i)) : V::none(), i < y.len() ? y.idx(int64_t(i)) : V::none()}));
        return V::list(out);
    }
    throw PyError("NotImplementedError", "stdlib call " + n);
}
// one canonical object per builtin name, so `type(x) is bool` and `x is list` compare by identity

// bytearray: mutable raw bytes (network FrameDecoder buffer)
struct ByteArrayObj : PyObj {
    std::string data;
    const char* type_name() const override { return "bytearray"; }
    size_t length() override { return data.size(); }
    bool truth() override { return !data.empty(); }
    V iterate() override { std::vector<V> o; for (unsigned char c : data) o.emplace_back(double(c)); return V::list(o); }
    bool contains(const V& k) override { return k.t == V::STR ? data.find(k.str()) != std::string::npos : data.find(char(int(k.num()))) != std::string::npos; }
    static void norm(int64_t n, const V& start, const V& stop, int64_t& a, int64_t& b) {
        a = start.is_none() || !start.has() ? 0 : int64_t(start.num());
        b = stop.is_none() || !stop.has() ? n : int64_t(stop.num());
        if (a < 0) a = std::max<int64_t>(0, a + n);
        if (b < 0) b = std::max<int64_t>(0, b + n);
        a = std::min(a, n); b = std::min(b, n); if (b < a) b = a;
    }
    bool call_method(Sym name, const Args& a, V& out) override {
        const std::string& n = name.str();
        if (n == "extend" || n == "__iadd__") { data += bytes_data(a.pos.at(0)); out = n == "extend" ? V::none() : self(); return true; }
        if (n == "append") { data.push_back(char(int(a.pos.at(0).num()))); out = V::none(); return true; }
        if (n == "clear") { data.clear(); out = V::none(); return true; }
        if (n == "decode") { out = V(data); return true; }
        if (n == "copy") { auto o = std::make_shared<ByteArrayObj>(); o->data = data; out = V::inst(o); return true; }
        if (n == "hex") { static const char* h = "0123456789abcdef"; std::string s; for (unsigned char c : data) { s += h[c >> 4]; s += h[c & 15]; } out = V(s); return true; }
        if (n == "__eq__" || n == "__ne__") {
            const V& other = a.pos.at(0);
            const auto* array = as<ByteArrayObj>(other);
            bool equal = array ? data == array->data : (other.t == V::STR && other.byt && data == other.str());
            out = V(n == "__eq__" ? equal : !equal); return true;
        }
        if (n == "__str__" || n == "__repr__") {
            char quote = data.find('\'') != std::string::npos && data.find('"') == std::string::npos ? '"' : '\'';
            std::string text = "bytearray(b"; text += quote;
            static const char* hex = "0123456789abcdef";
            for (unsigned char c : data) {
                if (c == quote || c == '\\') { text += '\\'; text += char(c); }
                else if (c == '\n') text += "\\n";
                else if (c == '\r') text += "\\r";
                else if (c == '\t') text += "\\t";
                else if (c < 32 || c >= 127) { text += "\\x"; text += hex[c >> 4]; text += hex[c & 15]; }
                else text += char(c);
            }
            text += quote; text += ')'; out = V(text); return true;
        }
        if (n == "__getitem__") { int64_t i = int64_t(a.pos.at(0).num()); if (i < 0) i += int64_t(data.size()); if (i < 0 || i >= int64_t(data.size())) throw PyError("IndexError", "bytearray index out of range"); out = V(double((unsigned char)data[size_t(i)])); return true; }
        if (n == "__getslice__") { int64_t x, y; norm(int64_t(data.size()), a.pos.at(0), a.pos.at(1), x, y); out = V::bytes(data.substr(size_t(x), size_t(y - x))); return true; }
        if (n == "__setslice__") { int64_t x, y; norm(int64_t(data.size()), a.pos.at(0), a.pos.at(1), x, y); data.replace(size_t(x), size_t(y - x), bytes_data(a.pos.at(2))); out = V::none(); return true; }
        return false;
    }
    V method(Sym name) override {
        static const SymIndex methods({Sym("extend"),Sym("__iadd__"),Sym("append"),Sym("clear"),Sym("decode"),Sym("copy"),Sym("hex"),Sym("__getitem__"),Sym("__getslice__"),Sym("__setslice__"),Sym("__eq__"),Sym("__ne__"),Sym("__str__"),Sym("__repr__")});
        if (methods.find(name) < 0) return V();
        auto sp = std::static_pointer_cast<ByteArrayObj>(shared_from_this());
        return V::func([sp, name](const Args& a) { V out; if (!sp->call_method(name, a, out)) throw PyError("AttributeError", "bytearray." + name.str()); return out; });
    }
};
std::string bytes_data(const V& v) {
    if (v.t == V::STR) return v.str();
    if (auto* b = as<ByteArrayObj>(v)) return b->data;
    if (v.t == V::LIST || v.t == V::TUPLE) { std::string s; for (auto& x : v.items()) s.push_back(char(int(x.num()))); return s; }
    if (v.is_num()) return std::string(size_t(v.num()), '\0');
    if (v.is_none() || !v.has()) return std::string();
    throw PyError("TypeError", "a bytes-like object is required");
}
V make_bytearray(const V& src) { auto o = std::make_shared<ByteArrayObj>(); if (src.has() && !src.is_none()) o->data = bytes_data(src); return V::inst(o); }
V builtin(const V& name) {
    static std::map<std::string, V> cache;
    const std::string n = name.str();
    auto it = cache.find(n);
    if (it != cache.end()) return it->second;
    V f = V::func([n](const Args& a) { return builtin_call(V(n), a); });
    f.box->fattrs.emplace_back(Sym("__name__"), V(n));
    f.box->fattrs.emplace_back(Sym("__native_builtin_callable__"),V(true));
    cache[n] = f;
    return f;
}
V builtin_call(const V& name, const Args& a) {
    const std::string& n = name.str();
    if (n == "dir") {
        if(a.pos.size()!=1 || !a.kw.empty())throw PyError("TypeError","native dir expects one object");
        std::vector<std::string> names;
        auto add=[&](const std::string& s){if(std::find(names.begin(),names.end(),s)==names.end())names.push_back(s);};
        std::function<void(const V&,int)> collect=[&](const V& object,int depth){
            if(depth>64)throw PyError("RuntimeError","cyclic native class metadata");
            if(object.box)for(const auto& item:object.box->fattrs) {
                add(item.first.str());
                if(item.first==Sym("__bases__")) { V bases=py::iter_list(item.second);for(const V& base:bases.items())collect(base,depth+1); }
            }
            if(object.t==V::INST) {
                for(const auto& item:object.box->inst->dyn)add(item.first.str());
                V slots=object.box->inst->method(Sym("__native_slot_names__"));
                if(slots.has()) { V declared=py::iter_list(slots.call(Args{}));for(const V& key:declared.items())add(key.str()); }
                V cls=py::type(object);if(cls.t==V::FUNC)collect(cls,depth+1);
            }
        };
        collect(a.pos[0],0);std::sort(names.begin(),names.end());
        V result=V::list();for(const std::string& s:names)result.append(V(s));return result;
    }
    if (n == "vars") {
        if (a.pos.size()!=1 || !a.kw.empty()) throw PyError("TypeError","native vars expects one object");
        const V& object=a.pos[0];
        if(object.t==V::DICT)for(const auto& attr:object.box->fattrs)
            if(attr.first==Sym("__native_namespace__") && attr.second.truthy())return object;
        if(object.t!=V::INST)throw PyError("TypeError","vars() argument must have __dict__ attribute");
        if(!object.box->inst->method(Sym("__native_slot_names__")).has())throw PyError("NotImplementedError","declared attribute enumeration is unavailable for "+object.type_name());
        return pvz::getattr(object,Sym("__dict__"));
    }
    if (n == "setattr") {
        if (a.pos.size() != 3 || !a.kw.empty()) throw PyError("TypeError", "setattr expected 3 positional arguments");
        if (!a.pos[1].is_str()) throw PyError("TypeError", "attribute name must be string");
        pvz::setattr(a.pos[0], a.pos[1].sym(), a.pos[2]);
        return V::none();
    }
    if (n == "dict") {
        V d = a.pos.empty() ? V::dict() : dict_of(a.pos[0]);
        for (auto& p : a.kw) d.at(V(p.first)) = p.second;
        return d;
    }
    if (n == "list") return a.pos.empty() ? V::list() : list_it(a.pos[0]);
    if (n == "tuple") return a.pos.empty() ? V::tuple({}) : tuple_it(a.pos[0]);
    if (n == "set" || n == "frozenset") return a.pos.empty() ? V::set() : set_it(a.pos[0]);
    if (n == "str") return a.pos.empty() ? V("") : str(a.pos[0]);
    if (n == "int") return a.pos.empty() ? V(0.0) : int_(a.pos[0]);
    if (n == "float") return a.pos.empty() ? V(0.0) : float_(a.pos[0]);
    if (n == "bool") return a.pos.empty() ? V(false) : V(a.pos[0].truthy());
    if (n == "len") return len(a.pos.at(0));
    if (n == "abs") return abs(a.pos.at(0));
    if (n == "max") return max_it(a.pos.size() == 1 ? a.pos[0] : V::list(a.pos), Key(), V());
    if (n == "min") return min_it(a.pos.size() == 1 ? a.pos[0] : V::list(a.pos), Key(), V());
    if (n == "sorted") return sorted_it(a.pos.at(0), Key(), false);
    if (n == "round") return round(a.pos.at(0));
    if (n == "object") return new_object();
    if (n == "range") {
        if (a.pos.size() == 1) return range(int64_t(a.pos[0].num()));
        return range(int64_t(a.pos.at(0).num()), int64_t(a.pos.at(1).num()), a.pos.size() > 2 ? int64_t(a.pos[2].num()) : 1);
    }
    if (n == "repr") return repr(a.pos.at(0));
    if (n == "id") return id(a.pos.at(0));
    if (n == "hash") return V(double(py_hash(a.pos.at(0)) & ((1ull << 52) - 1)));
    if (n == "bytearray") return make_bytearray(a.pos.empty() ? V() : a.pos[0]);
    if (n == "bytes" && !a.pos.empty()) return V::bytes(bytes_data(a.pos[0]));
    if (n == "bytes") return V::bytes("");
    throw PyError("NotImplementedError", "builtin " + n);
}
V type_method(const V& type, const V& method, const Args& a) {
    // dict.__setitem__(self, k, v) / dict.get(self, ...) / list.append(self, x) ...
    std::string m = method.str();
    if (m == "__init__") return V::none();
    if (m == "fromkeys") {   // dict.fromkeys(iterable[, value]) (insertion order, duplicates collapse)
        V d = V::dict();
        V val = a.pos.size() > 1 ? a.pos[1] : V::none();
        for (V held_ = iter_list(a.pos.at(0)); auto& k : held_.items()) if (!d.contains(k)) d.at(k) = val;
        return d;
    }
    if (m == "maketrans" || m == "fromhex") throw PyError("NotImplementedError", std::string("type method ") + m);
    if (m == "__setitem__") { setitem(a.pos.at(0), a.pos.at(1), a.pos.at(2)); return V::none(); }
    if (m == "__getitem__") return rd(a.pos.at(0), a.pos.at(1));
    if (m == "__delitem__") { py_del(a.pos.at(0), a.pos.at(1)); return V::none(); }
    if (m == "__contains__") return V(a.pos.at(0).contains(a.pos.at(1)));
    Args rest(std::vector<V>(a.pos.begin() + 1, a.pos.end()), a.kw);
    return callm(a.pos.at(0), method.sym(), rest);
}
V isinstance_v(const V& o, const V& type) {
    if (type.t == V::FUNC) {
        if(o.t==V::INST)if(const V* local=o.box->inst->find_dyn(Sym("__native_local_class__"))) {
            std::vector<V> pending{*local};for(size_t i=0;i<pending.size() && i<64;++i){if(py_is(pending[i],type))return V(true);V bases=pvz::getattr(pending[i],Sym("__bases__"),V());if(bases.is_list())for(const V& base:bases.items())pending.push_back(base);}
        }
        for (const auto& attr : type.box->fattrs)
            if (attr.first == Sym("__name__") && attr.second.is_str())
                return V(pvz::isinstance(o, attr.second.str().c_str()));
        throw PyError("TypeError", "isinstance() arg 2 is not a recognized type");
    }
    if (type.is_str()) return V(pvz::isinstance(o, type.str().c_str()));
    if (type.is_list()) { for (auto& t : type.items()) if (isinstance_v(o, t).truthy()) return V(true); return V(false); }
    return V(false);
}

}  // namespace pvz::py

namespace pvz {
static bool match_internal_key(const V& key) {
    return key == V("__self_ns") || key == V("__region_zombies") || key == V("__region_plants");
}
V MatchNS::getitem(const V& key) {
    if (match_internal_key(key)) throw PyError("KeyError", py_str(key));
    const V* p = G->find_global(key);
    if (!p || !p->has()) throw PyError("KeyError", py_str(key));
    return *p;
}
void MatchNS::mirror_key(const V& key) {
    if (mirror.t != V::DICT || key.t != V::STR || key.str() == "__builtins__") return;
    if (mirror_hidden.has() && mirror_hidden.contains(key)) return;
    const V* cur = G->find_global(key);
    if (cur && cur->has()) mirror.at(key) = *cur;
    else if (mirror.find(key)) py_del(mirror, key);
}
void MatchNS::setitem(const V& key, const V& value) { G->global(key) = value; mirror_key(key); }
void MatchNS::delitem(const V& key) {
    V& v = G->global(key);
    if (!v.has()) throw PyError("KeyError", py_str(key));
    v.del();
    mirror_key(key);
}
bool MatchNS::contains(const V& key) { return !match_internal_key(key) && G->has_global(key); }
size_t MatchNS::length() { size_t n = 0; G->each_present([&](const V& key) { if (!match_internal_key(key)) ++n; }); return n; }
V MatchNS::iterate() {
    std::vector<V> keys;
    G->each_present([&](const V& k) { if (!match_internal_key(k)) keys.push_back(k); });
    return V::list(keys);
}
bool MatchNS::call_method(Sym name, const Args& a, V& out) {
    static const Sym S_get("get"), S_setdefault("setdefault"), S_pop("pop"), S_update("update");
    if (name == S_get) {
        const V* p = G->find_global(a.pos.at(0));
        out = (p && p->has()) ? *p : (a.pos.size() > 1 ? a.pos[1] : V::none());
        return true;
    }
    if (name == S_setdefault) {
        V& v = G->global(a.pos.at(0));
        if (!v.has()) v = a.pos.size() > 1 ? a.pos[1] : V::none();
        out = v;
        mirror_key(a.pos[0]);
        return true;
    }
    if (name == S_pop) {
        V& v = G->global(a.pos.at(0));
        if (!v.has()) {
            if (a.pos.size() > 1) { out = a.pos[1]; return true; }
            throw PyError("KeyError", py_str(a.pos[0]));
        }
        out = v;
        v.del();
        mirror_key(a.pos[0]);
        return true;
    }
    if (name == S_update) {
        if (!a.pos.empty()) {
            const V& src = a.pos[0];
            if (src.t == V::DICT) { for (auto& p : src.box->kv) { G->global(p.first) = p.second; mirror_key(p.first); } }
            else { V d = py::dict_of(src); for (auto& p : d.kv()) { G->global(p.first) = p.second; mirror_key(p.first); } }
        }
        for (auto& p : a.kw) { G->global(V(p.first)) = p.second; mirror_key(V(p.first)); }
        out = V::none();
        return true;
    }
    return false;
}
V MatchNS::method(Sym name) {
    const std::string& n = name.str();
    if (n != "get" && n != "setdefault" && n != "pop" && n != "update") return V();
    auto sp = std::static_pointer_cast<MatchNS>(shared_from_this());
    return V::func([sp, name](const Args& a) { V out; sp->call_method(name, a, out); return out; });
}
V match_ns(Match& G) {
    auto p = std::make_shared<MatchNS>();
    p->G = &G;
    return V::inst(p);
}
Match& match_of(const V& g) {
    auto* p = as<MatchNS>(g);
    if (!p) throw PyError("TypeError", "not a match namespace");
    return *p->G;
}
}  // namespace pvz

namespace pvz {
const V& DynNS::get_(Sym name) {
    auto it = map.find(name.id);
    if (it == map.end() || !it->second.has()) throw PyError("NameError", "name '" + name.str() + "' is not defined");
    return it->second;
}
void DynNS::set_(Sym name, const V& v) {
    auto it = map.find(name.id);
    if (it == map.end()) { order.push_back(name); map.emplace(name.id, v); }
    else it->second = v;
}
V DynNS::getitem(const V& key) {
    auto it = map.find(key.sym().id);
    if (it == map.end() || !it->second.has()) throw PyError("KeyError", py_str(key));
    return it->second;
}
void DynNS::setitem(const V& key, const V& value) { set_(key.sym(), value); }
void DynNS::delitem(const V& key) { map.erase(key.sym().id); gcache.clear(); }
bool DynNS::contains(const V& key) { if (!key.is_str()) return false; auto it = map.find(key.sym().id); return it != map.end() && it->second.has(); }
V DynNS::iterate() { std::vector<V> k; for (auto s : order) if (map.count(s.id)) k.emplace_back(s); return V::list(k); }
bool DynNS::call_method(Sym name, const Args& a, V& out) {
    static const Sym S_get("get"), S_items("items"), S_keys("keys"), S_setdefault("setdefault"), S_pop("pop"), S_update("update");
    if (name == S_get) {
        if (!a.pos.at(0).is_str()) { out = a.pos.size() > 1 ? a.pos[1] : V::none(); return true; }
        auto it = map.find(a.pos[0].sym().id);
        out = (it != map.end() && it->second.has()) ? it->second : (a.pos.size() > 1 ? a.pos[1] : V::none());
        return true;
    }
    if (name == S_items) {
        std::vector<V> o;
        for (auto s : order) { auto it = map.find(s.id); if (it != map.end()) o.push_back(V::tuple({V(s), it->second})); }
        out = V::list(o);
        return true;
    }
    if (name == S_keys) { out = iterate(); return true; }
    if (name == S_setdefault) {
        auto it = map.find(a.pos.at(0).sym().id);
        if (it != map.end() && it->second.has()) { out = it->second; return true; }
        set_(a.pos[0].sym(), a.pos.size() > 1 ? a.pos[1] : V::none());
        out = map[a.pos[0].sym().id];
        return true;
    }
    if (name == S_pop) {
        auto it = map.find(a.pos.at(0).sym().id);
        if (it == map.end()) { if (a.pos.size() > 1) { out = a.pos[1]; return true; } throw PyError("KeyError", py_str(a.pos[0])); }
        out = it->second; map.erase(it); gcache.clear(); return true;
    }
    if (name == S_update) {
        if (!a.pos.empty()) { V d = py::dict_of(a.pos[0]); for (auto& p : d.kv()) set_(p.first.sym(), p.second); }
        for (auto& p : a.kw) set_(p.first, p.second);
        out = V::none();
        return true;
    }
    return false;
}
V DynNS::method(Sym name) {
    const std::string& n = name.str();
    if (n != "get" && n != "items" && n != "keys" && n != "setdefault" && n != "pop" && n != "update") return V();
    auto sp = std::static_pointer_cast<DynNS>(shared_from_this());
    return V::func([sp, name](const Args& a) { V out; sp->call_method(name, a, out); return out; });
}
}  // namespace pvz

#include "data/datastore.h"
namespace pvz::py {
struct NoopModule : PyObj {
    std::string name;
    const char* type_name() const override { return name.c_str(); }
    V method(Sym n) override { auto p = std::make_shared<NoopModule>(); p->name = name + "." + n.str(); return V::inst(p); }
    void require_implemented() const {
        if (std::getenv("PVZ_TEST_STRICT")) throw PyError("NotImplementedError", "no-op compatibility object used: " + name);
    }
    V call_self(const Args&) override { require_implemented(); return V::none(); }
    bool contains(const V&) override { require_implemented(); return false; }
    V iterate() override { require_implemented(); return V::list(); }
    size_t length() override { require_implemented(); return 0; }
};
V noop_module(const V& name) { auto p = std::make_shared<NoopModule>(); p->name = name.str(); return V::inst(p); }
struct StdModule : PyObj {
    std::string name;
    const char* type_name() const override { return "module"; }
    V property(Sym attr, bool& found) override {
        found = true;
        if (attr == Sym("__name__")) return V(name);
        if (name == "sys" && attr == Sym("modules")) return loaded_modules();
        if (name == "collections" && attr == Sym("deque")) return native_deque_type();
        if(name=="collections" && attr==Sym("OrderedDict"))return native_ordered_dict_type();
        if (name == "types" && attr == Sym("MethodType")) return native_method_type();
        found = false; return V();
    }
    V method(Sym attr) override {
        std::string full = name + "." + attr.str();
        if(V actual=registered_path(full);actual.has())return actual;
        if (name == "math" && attr.str() == "pi") return V(3.141592653589793);
        return V::func([full](const Args& a) {
            // A bound original must remain original when wraps/side_effect calls it after replacement.
            ++stdlib_override_skip[full];
            struct Restore { std::string name; ~Restore() { if (!--stdlib_override_skip[name]) stdlib_override_skip.erase(name); } } restore{full};
            return stdlib_call(V(full), a);
        });
    }
};
static V stdlib_override_path(const std::string& dotted) {
    auto skip = stdlib_override_skip.find(dotted);
    if (skip != stdlib_override_skip.end() && skip->second) return V();
    auto& cache = stdlib_module_cache();
    size_t split = dotted.size();
    for (;;) {
        auto found = cache.find(dotted.substr(0, split));
        if (found != cache.end()) {
            if (split == dotted.size()) return found->second;
            std::string tail = dotted.substr(split + 1); size_t next = tail.find('.');
            Sym attr(tail.substr(0, next));
            PyObj* module = found->second.box->inst.get(); V value;
            if (V* replacement = module->find_dyn(attr)) value = *replacement;
            else { bool present = false; value = module->property(attr, present); if (!present) return V(); }
            while (next != std::string::npos) {
                size_t end = tail.find('.', next + 1);
                value = pvz::getattr(value, Sym(tail.substr(next + 1, end == std::string::npos ? end : end - next - 1)));
                next = end;
            }
            return value;
        }
        if (!split) break;
        split = dotted.rfind('.', split - 1); if (split == std::string::npos) break;
    }
    return V();
}
V stdlib_module(const V& name) {
    if(name.str()=="gc")return native_gc_module();
    { V r = registered_path(name.str()); if (r.has()) return r; }
    if(name.str()=="marshal")return native_marshal_module();
#ifdef _WIN32
    if (name.str() == "resource") throw PyError("ImportError", "resource is unavailable on Windows");
#endif
    auto p = std::make_shared<StdModule>(); p->name = name.str();
    V result = V::inst(p); stdlib_module_cache()[name.str()] = result; return result;
}
static V from_json(const nlohmann::json& j) {
    if (j.is_null()) return V::none();
    if (j.is_boolean()) return V(j.get<bool>());
    if (j.is_number()) return V(j.get<double>());
    if (j.is_string()) return V(j.get<std::string>());
    if (j.is_array()) { std::vector<V> it; for (auto& x : j) it.push_back(from_json(x)); return V::list(it); }
    if (j.is_object()) {
        if (j.contains("__set__")) { std::vector<V> it; for (auto& x : j["__set__"]) it.push_back(from_json(x)); return V::set(it); }
        if (j.contains("__float__")) { std::string f = j["__float__"]; return V(f == "inf" ? INFINITY : f == "-inf" ? -INFINITY : NAN); }
        V d = V::dict();
        for (auto& [k, v] : j.items()) d.at(V(k)) = from_json(v);
        return d;
    }
    return V::none();
}
V int_keyed(const V& d) {
    if (!d.is_dict()) return d;
    V out = V::dict();
    for (auto& kv : d.kv()) {
        const V& k = kv.first;
        bool digits = k.t == V::STR && !k.str().empty() && k.str().find_first_not_of("-0123456789") == std::string::npos;
        out.at(digits ? V(double(std::stoll(k.str()))) : k) = kv.second;
    }
    return out;
}
V data_value(const char* module, const char* key) { return from_json(data::get(module, key)); }
V atlas_image(const V& key) { return py_dict({{V("image"), key}}); }
V atlas_ground_gap(const V& name) { (void)name; return V(0.0); }   // TODO(render): compute from baked PNG
}  // namespace pvz::py

namespace pvz {
namespace {
// A live attribute mapping. Class dictionaries are read-only mapping proxies;
// function dictionaries retain normal attribute mutation semantics.
struct FunctionAttrs final : PyObj {
    V owner;
    bool readonly=false;
    const char* type_name() const override { return readonly?"mappingproxy":"dict"; }
    V* find(const V& key) {
        if(key.t!=V::STR)return nullptr;
        for(auto& item:owner.box->fattrs)if(item.first==key.sym())return &item.second;
        return nullptr;
    }
    V getitem(const V& key) override { V* value=find(key);if(!value)throw PyError("KeyError",py_str(key));return *value; }
    bool contains(const V& key) override { return find(key)!=nullptr; }
    size_t length() override { return owner.box->fattrs.size(); }
    V iterate() override { V out=V::list();for(const auto& item:owner.box->fattrs)out.append(V(item.first));return out; }
    void setitem(const V& key,const V& value) override {
        if(readonly)throw PyError("TypeError","class dictionary is read-only");
        if(key.t!=V::STR)throw PyError("TypeError","function attribute keys must be strings");
        pvz::setattr(owner,key.sym(),value);
    }
    void delitem(const V& key) override {
        if(readonly)throw PyError("TypeError","class dictionary is read-only");
        auto& items=owner.box->fattrs;for(size_t i=0;i<items.size();++i)if(items[i].first==key.sym()){items.erase(items.begin()+i);return;}
        throw PyError("KeyError",py_str(key));
    }
    bool call_method(Sym name,const Args& a,V& out) override {
        const std::string& n=name.str();
        if(n=="get"){V* value=find(a.pos.at(0));out=value?*value:a.pos.size()>1?a.pos[1]:V::none();return true;}
        if(n=="keys" || n=="items" || n=="values" || n=="copy") {
            out=n=="copy"?V::dict():V::list();
            for(const auto& item:owner.box->fattrs) {
                if(n=="copy")out.at(V(item.first))=item.second;
                else out.append(n=="keys"?V(item.first):n=="values"?item.second:V::tuple({V(item.first),item.second}));
            }
            return true;
        }
        return false;
    }
    V method(Sym name) override {
        static const SymIndex methods({Sym("get"),Sym("keys"),Sym("items"),Sym("values"),Sym("copy")});
        if(methods.find(name)<0)return V();auto self=std::static_pointer_cast<FunctionAttrs>(shared_from_this());
        return V::func([self,name](const Args& a){V result;self->call_method(name,a,result);return result;});
    }
};
}
V dunder_stub(const V& o, Sym name) {
    if(name==Sym("__dict__")) {
        auto view=std::make_shared<FunctionAttrs>();view->owner=o;
        for(const auto& attr:o.box->fattrs)if(attr.first==Sym("__native_class_value__") && attr.second.truthy())view->readonly=true;
        return V::inst(view);
    }
    if(name==Sym("__get__")) {
        for(const auto& attr:o.box->fattrs)
            if((attr.first==Sym("__native_class_value__") || attr.first==Sym("__native_builtin_callable__")) && attr.second.truthy())
                throw PyError("AttributeError","callable has no function descriptor");
        return V::func([o](const Args& args) {
            if(args.pos.empty() || args.pos.size()>2 || !args.kw.empty())throw PyError("TypeError","function __get__ requires one or two positional arguments");
            if(args.pos[0].is_none()) {
                if(args.pos.size()<2 || args.pos[1].is_none())throw PyError("TypeError","__get__(None, None) is invalid");
                return o;
            }
            return py::native_method_type().call(Args{o,args.pos[0]});
        });
    }
    if (name.str() == "__name__" || name.str() == "__qualname__") return V("<function>");
    if (name.str() == "__call__" || name.str() == "__func__") return o;
    for (const auto& attr : o.box->fattrs) if (attr.first == Sym("__name__") && attr.second.is_str()) {
        const auto& type = attr.second.str();
        if (type == "dict" || type == "list" || type == "tuple" || type == "set" || type == "str" || type == "object") {
            V type_name = attr.second;
            return V::func([type_name, name](const Args& a) { return py::type_method(type_name, V(name), a); });
        }
    }
    if (std::getenv("PVZ_TEST_STRICT")) throw PyError("AttributeError", "unsupported function attribute: " + name.str());
    return py::noop_module(V(name.str()));
}
}  // namespace pvz

#include "core/fsutil.h"
#include <filesystem>
#include <fstream>
#include <sstream>
namespace pvz::py {
struct PathObj : PyObj {
    std::filesystem::path p;
    const char* type_name() const override { return "Path"; }
    bool isa(const char* c) const override { return std::string(c) == "Path" || std::string(c) == "PurePath" || std::string(c) == "object"; }
    V property(Sym name, bool& found) override;
    V method(Sym name) override;
    bool call_method(Sym name, const Args& a, V& out) override {
        const auto& op=name.str();
        if (op!="__eq__" && op!="__ne__" && op!="__lt__" && op!="__le__" && op!="__gt__" && op!="__ge__") return false;
        auto* other=a.pos.empty()?nullptr:as<PathObj>(a.pos[0]);
        if (!other) return false;
        auto parts=[](std::filesystem::path path) {
            path.make_preferred();
            std::vector<std::filesystem::path::string_type> result;
            for (const auto& item:path) {
                auto text=item.native();
                if (text.empty() || item==std::filesystem::path(".")) continue;
#ifdef _WIN32
                std::transform(text.begin(),text.end(),text.begin(),[](wchar_t c){return std::towlower(c);});
#endif
                result.push_back(std::move(text));
            }
            return result;
        };
        auto first=parts(p),second=parts(other->p);
        out=V(op=="__eq__"?first==second:op=="__ne__"?first!=second:op=="__lt__"?first<second:op=="__le__"?first<=second:op=="__gt__"?first>second:first>=second);
        return true;
    }
};
V open_path(const std::filesystem::path& p, const std::string& mode);
static V make_path(const std::filesystem::path& p) { auto o = std::make_shared<PathObj>(); o->p = p; return V::inst(o); }
static std::filesystem::path path_of(const V& v) {
    if (auto* p = as<PathObj>(v)) return p->p;
    return u8p(py_str(v));
}
V PathObj::property(Sym name, bool& found) {
    found = true;
    const std::string& n = name.str();
    if (n == "parent") return make_path(p.parent_path());
    if (n == "name") return V(p8(p.filename()));
    if (n == "stem") return V(p8(p.stem()));
    if (n == "suffix") return V(p8(p.extension()));
    if (n == "parents") {
        std::vector<V> out;
        for (auto q = p.parent_path(); ; q = q.parent_path()) {
            out.push_back(make_path(q));
            if (q == q.parent_path() || q.empty()) break;
        }
        return V::tuple(out);
    }
    if (n == "parts") { std::vector<V> out; for (auto& part : p) out.emplace_back(p8(part)); return V::tuple(out); }
    if (n == "drive") return V(p8(p.root_name()));
    if (n == "anchor") return V(p8(p.root_name()) + p8(p.root_directory()));
    found = false;
    return V();
}
V PathObj::method(Sym name) {
    auto sp = std::static_pointer_cast<PathObj>(shared_from_this());
    const std::string& n = name.str();
    if (n == "resolve" || n == "absolute") return V::func([sp](const Args&) { return make_path(std::filesystem::absolute(sp->p)); });
    if (n == "__truediv__" || n == "joinpath") return V::func([sp](const Args& a) { return make_path(sp->p / path_of(a.pos.at(0))); });
    if (n == "exists") return V::func([sp](const Args&) { return V(std::filesystem::exists(sp->p)); });
    if (n == "is_file") return V::func([sp](const Args&) { return V(std::filesystem::is_regular_file(sp->p)); });
    if (n == "is_dir") return V::func([sp](const Args&) { return V(std::filesystem::is_directory(sp->p)); });
    if (n == "read_text") return V::func([sp](const Args&) {
        std::ifstream f(sp->p, std::ios::binary);
        if (!f) throw PyError("FileNotFoundError", p8(sp->p));
        std::stringstream ss; ss << f.rdbuf();
        std::string t = ss.str();
        if (t.size() >= 3 && (unsigned char)t[0] == 0xEF && (unsigned char)t[1] == 0xBB && (unsigned char)t[2] == 0xBF) t = t.substr(3);
        return V(t);
    });
    if (n == "write_text") return V::func([sp](const Args& a) {
        std::ofstream f(sp->p, std::ios::binary); f << py_str(a.pos.at(0)); return V::none();
    });
    if (n == "open") return V::func([sp](const Args& a) {
        V mode = (a.size() > 0 || a.has_kw(Sym("mode"))) ? a.get(0, Sym("mode"), nullptr) : V("r");
        return open_path(sp->p, mode.str());
    });
    if (n == "mkdir") return V::func([sp](const Args&) { std::filesystem::create_directories(sp->p); return V::none(); });
    if (n == "rglob") return V::func([sp](const Args& a) {
        const std::string pattern=py_str(a.pos.at(0));
        if (pattern!="*") throw PyError("NotImplementedError","Path.rglob currently supports the recursive all-entry pattern only");
        std::vector<V> out;
        if (std::filesystem::is_directory(sp->p))
            for (const auto& entry:std::filesystem::recursive_directory_iterator(sp->p)) out.push_back(make_path(entry.path()));
        return V::list(out);
    });
    if (n == "glob") return V::func([sp](const Args& a) {
        std::string pattern=py_str(a.pos.at(0));if(pattern.empty())throw PyError("ValueError","empty glob pattern");
        auto pattern_path=u8p(pattern);if(pattern_path.is_absolute())throw PyError("NotImplementedError","absolute glob patterns are not supported");
        if(pattern_path.has_parent_path())throw PyError("NotImplementedError","nested Path.glob patterns are not implemented");
        auto codepoints=[](const std::string& text){
            std::vector<uint32_t> out;
#ifdef _WIN32
            std::wstring wide=u8p(text).wstring();for(size_t i=0;i<wide.size();++i){uint32_t point=uint32_t(std::towlower(wide[i]));if(point>=0xd800 && point<=0xdbff && i+1<wide.size() && uint32_t(wide[i+1])>=0xdc00 && uint32_t(wide[i+1])<=0xdfff)point=0x10000+((point-0xd800)<<10)+(uint32_t(wide[++i])-0xdc00);out.push_back(point);}
#else
            for(size_t i=0;i<text.size();){unsigned char first=text[i++];uint32_t point=first;int extra=0;if(first>=0xf0){point=first&7;extra=3;}else if(first>=0xe0){point=first&15;extra=2;}else if(first>=0xc0){point=first&31;extra=1;}while(extra-- && i<text.size())point=(point<<6)|(uint8_t(text[i++])&63);out.push_back(point);}
#endif
            return out;
        };
        auto pat=codepoints(pattern);
        auto matches=[&](const std::string& filename){
            auto text=codepoints(filename);std::vector<int8_t> memo((pat.size()+1)*(text.size()+1),-1);
            std::function<bool(size_t,size_t)> match=[&](size_t i,size_t j)->bool {
                int8_t& result=memo[i*(text.size()+1)+j];if(result>=0)return result!=0;bool found=false;
                if(i==pat.size())found=j==text.size();
                else if(pat[i]=='*')found=match(i+1,j) || (j<text.size() && match(i,j+1));
                else if(j<text.size()) {
                    if(pat[i]=='?')found=match(i+1,j+1);
                    else if(pat[i]=='['){
                        size_t begin=i+1;if(begin<pat.size() && pat[begin]=='!')++begin;size_t end=begin;if(end<pat.size() && pat[end]==']')++end;while(end<pat.size() && pat[end]!=']')++end;
                        if(end==pat.size())found=text[j]=='[' && match(i+1,j+1);
                        else {bool hit=false;for(size_t k=begin;k<end;++k){if(k+2<end && pat[k+1]=='-'){hit=hit || (pat[k]<=text[j] && text[j]<=pat[k+2]);k+=2;}else hit=hit || pat[k]==text[j];}if(i+1<pat.size() && pat[i+1]=='!')hit=!hit;found=hit && match(end+1,j+1);}
                    }else found=pat[i]==text[j] && match(i+1,j+1);
                }
                result=found?1:0;return found;
            };return match(0,0);
        };
        std::vector<V> out;if(std::filesystem::is_directory(sp->p))for(const auto& entry:std::filesystem::directory_iterator(sp->p))if(matches(p8(entry.path().filename())))out.push_back(make_path(entry.path()));return V::list(out);
    });
    if (n == "__str__" || n == "__fspath__" || n == "as_posix") return V::func([sp, n](const Args&) {
        std::string s = p8(sp->p);
        if (n == "as_posix") for (auto& c : s) if (c == '\\') c = '/';
        return V(s);
    });
    if (n == "read_bytes") return V::func([sp](const Args&) {
        std::ifstream f(sp->p, std::ios::binary);
        if (!f) throw PyError("FileNotFoundError", p8(sp->p));
        std::stringstream ss; ss << f.rdbuf();
        return V::bytes(ss.str());
    });
    if (n == "write_bytes") return V::func([sp](const Args& a) {
        std::ofstream f(sp->p, std::ios::binary);
        if (!f) throw PyError("OSError", "cannot write " + p8(sp->p));
        const std::string& d = a.pos.at(0).str();
        f.write(d.data(), std::streamsize(d.size()));
        return V(double(d.size()));
    });
    if (n == "unlink") return V::func([sp](const Args& a) {
        std::error_code ec;
        bool missing_ok = false;
        for (auto& kv : a.kw) if (kv.first == Sym("missing_ok")) missing_ok = kv.second.truthy();
        if (!a.pos.empty()) missing_ok = a.pos[0].truthy();
        if (!std::filesystem::remove(sp->p, ec) && !missing_ok) throw PyError("FileNotFoundError", p8(sp->p));
        return V::none();
    });
    if (n == "rmdir") return V::func([sp](const Args&) { std::filesystem::remove(sp->p); return V::none(); });
    if (n == "iterdir") return V::func([sp](const Args&) {
        std::vector<V> out;
        std::error_code ec;
        for (auto& e : std::filesystem::directory_iterator(sp->p, ec)) out.push_back(make_path(e.path()));
        if (ec) throw PyError("FileNotFoundError", p8(sp->p));
        return V::list(out);
    });
    if (n == "with_name") return V::func([sp](const Args& a) { auto q = sp->p; q.replace_filename(path_of(a.pos.at(0))); return make_path(q); });
    if (n == "with_suffix") return V::func([sp](const Args& a) { auto q = sp->p; q.replace_extension(u8p(a.pos.at(0).str())); return make_path(q); });
    if (n == "rename" || n == "replace") return V::func([sp](const Args& a) {
        auto dst = path_of(a.pos.at(0));
        std::error_code ec;
        std::filesystem::rename(sp->p, dst, ec);
        if (ec) throw PyError("OSError", "rename " + p8(sp->p) + ": " + ec.message());
        return make_path(dst);
    });
    if (n == "touch") return V::func([sp](const Args&) { if (!std::filesystem::exists(sp->p)) std::ofstream(sp->p, std::ios::binary); return V::none(); });
    if (n == "is_absolute") return V::func([sp](const Args&) { return V(sp->p.is_absolute()); });
    if (n == "expanduser") return V::func([sp](const Args&) { return make_path(sp->p); });
    if (n == "relative_to") return V::func([sp](const Args& a) { return make_path(std::filesystem::relative(sp->p, path_of(a.pos.at(0)))); });
    if (n == "stat") return V::func([sp](const Args&) {
        std::error_code ec;
        auto size = std::filesystem::file_size(sp->p, ec);
        if (ec && !std::filesystem::exists(sp->p)) throw PyError("FileNotFoundError", p8(sp->p));
        auto t = std::filesystem::last_write_time(sp->p, ec);
        double mtime = double(std::chrono::duration_cast<std::chrono::seconds>(t.time_since_epoch()).count()) - 11644473600.0;
        V st = noop_module(V("stat_result"));
        pvz::setattr(st, Sym("st_size"), V(double(ec ? 0 : size)));
        pvz::setattr(st, Sym("st_mtime"), V(mtime));
        return st;
    });
    if (n == "samefile") return V::func([sp](const Args& a) { std::error_code ec; return V(std::filesystem::equivalent(sp->p, path_of(a.pos.at(0)), ec)); });
    if (n == "__eq__") return V::func([sp](const Args& a) { return V(as<PathObj>(a.pos.at(0)) && sp->p == path_of(a.pos[0])); });
    return V();
}
// __file__ of a translated module: extract/data/pvp/<module>.py (assets and AI knowledge sit there), except
// relay: relay.configured_endpoint() walks up from __file__ for relay.json, which must be the one beside the
// executable, not extract/data/relay.json (that module's data file)
V module_file(const V& module) {
    // translated test modules: tools/run_cpp_suite.py builds a read-only fixture root that mirrors the original
    // workspace layout (reference data + the native build's shipped assets) and exports PVZ_TEST_ROOT; the test's
    // ROOT = parents[1] then resolves inside that fixture instead of extract/data (production lookups unchanged)
    if (module.str().rfind("test_", 0) == 0 || module.str() == "multiworker_fixtures" || module.str() == "probe_pvp_net_guest_cost") {
        const char* root = std::getenv("PVZ_TEST_ROOT");
        if (root && *root) return V(std::string(root) + "/tests/" + module.str() + ".py");
    }
    if (module.str() == "relay") try {
        V exe = stdlib_attr(V("sys"), V("executable"));
        if (exe.t == V::STR && !exe.str().empty()) {
            const std::string& e = exe.str();
            size_t slash = e.find_last_of("/\\");
            if (slash != std::string::npos) return V(e.substr(0, slash) + "/pvp/" + module.str() + ".py");
        }
    } catch (const PyError&) {}
    return V(data::data_dir() + "/pvp/" + module.str() + ".py");
}
V path_new(const Args& a) {
    std::filesystem::path p;
    for (auto& x : a.pos) p /= path_of(x);
    return make_path(p);
}
}  // namespace pvz::py

#include <map>
namespace pvz::py {
struct FrameRec { V code; double lasti; V locals; V globals; int depth; bool region; };
static thread_local std::vector<FrameRec> g_frames;
V call_site(const V& code, double lasti, const V& locals, const V& f, const Args& a) {
    V globals = locals;
    if (!locals.is_inst() && !g_frames.empty()) globals = g_frames.back().globals;
    g_frames.push_back({code, lasti, locals, globals, g_call_depth + 1, false});
    struct Pop { ~Pop() { g_frames.pop_back(); } } pop_;
    return f.call(a);
}
void push_region_frame(const V& code, const V& ns) { g_frames.push_back({code, -1, ns, ns, g_call_depth + 1, true}); }
void pop_region_frame() { g_frames.pop_back(); }
V getframe() {
    // called from inside a function that was entered through V::call (depth g_call_depth)
    for (size_t i = g_frames.size(); i-- > 0;) {
        auto& fr = g_frames[i];
        if (!fr.region && fr.depth == g_call_depth)
            return py_dict({{V("f_code"), fr.code}, {V("f_lasti"), V(fr.lasti)}, {V("f_locals"), fr.locals}, {V("f_globals"), fr.globals}});
        if (fr.region && fr.depth == g_call_depth)   // direct callee of module-level region code
            return py_dict({{V("f_code"), fr.code}, {V("f_lasti"), V(-1.0)}, {V("f_locals"), fr.locals}, {V("f_globals"), fr.globals}});
        if (fr.depth < g_call_depth) break;
    }
    return py_dict({{V("f_code"), V::none()}, {V("f_lasti"), V(-1.0)}, {V("f_locals"), V::dict()}, {V("f_globals"), V::dict()}});
}
static std::map<std::string, Fn>& hooks() { static std::map<std::string, Fn> h; return h; }
void register_native_hook(const std::string& name, Fn fn) { hooks()[name] = std::move(fn); }
// A real dict-backed TemplateAtlas preserves its input entries. The native
// missing operation aliases an existing template entry without inserting a key.
// This is the original template algorithm, not a generic __missing__ emulator.
static const bool template_atlas_factory=[] {
    register_native_hook("runtime.current_function",[](const Args&){return pvz::native_current_function();});
    register_native_hook("core.template_atlas",[](const Args& a){
        V output=V::dict();for(const auto& item:items_vec(a.pos.at(0)))output.at(item.first)=item.second;
        V type=a.pos.at(1),getter=a.pos.at(2);output.box->missing=3;
        output.box->fattrs.emplace_back(Sym("__native_template_class__"),type);
        output.box->fattrs.emplace_back(Sym("__native_template_alias__"),V::func([getter](const Args& args){
            V dictionary=args.pos.at(0),key=args.pos.at(1);
            if(key.is_str())for(const auto& item:items_vec(getter.call(Args{}))) {
                std::string prefix=item.first.str()+"-";
                if(key.str().compare(0,prefix.size(),prefix)==0){V mapped=V(item.second.str()+key.str().substr(item.first.str().size()));if(dictionary.contains(mapped))return mapped;}
            }
            throw PyError("KeyError",py_str(key));return V();
        }));return output;
    });return true;
}();
bool has_native_hook(const std::string& name) { return hooks().count(name) != 0; }
V native_hook(const V& name, const Args& a) {
    auto it = hooks().find(name.str());
    if (it == hooks().end()) throw PyError("NotImplementedError", "native hook " + name.str());
    return it->second(a);
}
}  // namespace pvz::py

// ------------------------------------------------------------------ builtin open() / Path.open
namespace pvz::py {
namespace {
struct FileObj : PyObj {
    std::string path, mode; native_file::File f; bool binary = false;
    const char* type_name() const override { return binary ? "BufferedIOBase" : "TextIOWrapper"; }
    V property(Sym n, bool& found) override {
        found = true;
        if (n.str() == "name") return V(path);
        if (n.str() == "mode") return V(mode);
        if (n.str() == "closed") return V(!f.is_open());
        found = false; return V();
    }
    std::string read_all() { return f.read(); }
    std::vector<V> lines() {
        std::vector<V> out; std::string line;
        while (!(line = f.readline()).empty()) {
            if (!binary) {
                if (line.size() >= 2 && line.back() == '\n' && line[line.size()-2] == '\r') line.erase(line.size()-2, 1);
                else if (line.back() == '\r') line.pop_back();
            }
            out.emplace_back(binary ? V::bytes(line) : V(line));
        }
        return out;
    }
    V iterate() override { return V::list(lines()); }
    bool call_method(Sym name, const Args& a, V& out) override {
        const std::string& n = name.str();
        if (n == "write") {
            const V& x = a.pos.at(0);
            std::string s = binary ? bytes_data(x) : x.t == V::STR ? x.str() : py_str(x);
            out = V(double(f.write(s))); return true;
        }
        if (n == "read") {
            if (!a.pos.empty() && a.pos[0].num() >= 0) {
                std::string s = f.read(int64_t(a.pos[0].num()));
                out = binary ? V::bytes(s) : V(s); return true;
            }
            out = binary ? V::bytes(read_all()) : V(read_all()); return true;
        }
        if (n == "readline") {
            std::string line = f.readline(a.pos.empty() ? -1 : int64_t(a.pos[0].num()));
            out = binary ? V::bytes(line) : V(line); return true;
        }
        if (n == "readlines") { out = V::list(lines()); return true; }
        if (n == "flush") { f.flush(); out = V::none(); return true; }
        if (n == "fileno") { out = V(f.descriptor()); return true; }
        if (n == "tell") { out = V(double(f.tell())); return true; }
        if (n == "seek") {
            int dir = a.pos.size() > 1 ? int(a.pos[1].num()) : SEEK_SET;
            out = V(double(f.seek(int64_t(a.pos.at(0).num()), dir))); return true;
        }
        if (n == "close") { f.close(); out = V::none(); return true; }
        if (n == "__enter__") { (void)f.descriptor(); out = self(); return true; }
        if (n == "__exit__") { f.close(); out = V(false); return true; }
        return false;
    }
    V method(Sym name) override {
        auto sp = std::static_pointer_cast<FileObj>(shared_from_this());
        return V::func([sp, name](const Args& a) { V out; if (!sp->call_method(name, a, out)) throw PyError("AttributeError", name.str()); return out; });
    }
};
}  // namespace

V open_path(const std::filesystem::path& p, const std::string& mode) {
    auto fo = std::make_shared<FileObj>();
    fo->path = p8(p); fo->mode = mode;
    fo->binary = mode.find('b') != std::string::npos;
    fo->f.open(p, mode);
    // utf-8-sig style BOM skip for text reads
    if (!fo->binary && mode.find('r') != std::string::npos) {
        std::string b = fo->f.read(3);
        if (b != std::string("\xEF\xBB\xBF", 3)) fo->f.seek(0);
    }
    return V::inst(fo);
}
V open_file(const Args& a) {
    V file = a.get(0, Sym("file"), nullptr, "open");
    V mode = (a.size() > 1 || a.has_kw(Sym("mode"))) ? a.get(1, Sym("mode"), nullptr) : V("r");
    return open_path(path_of(file), mode.str());
}
}  // namespace pvz::py
