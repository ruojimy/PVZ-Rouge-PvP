#include "core/function_profile.h"
#include "core/native_closure.h"
#include "core/gil.h"
#include "core/pyobj.h"
#include "core/obj.h"
#include "core/pyops.h"
#include <cctype>
#include <cmath>
#ifdef __ANDROID__
#include <android/log.h>
#include <cstdlib>
#endif

namespace pvz {
#ifdef __ANDROID__
// Explicit diagnostic intent only; ordinary play does not emit call tracing.
struct UiCallTrace72 {
    const char* owner = nullptr;
    const char* method = nullptr;
    UiCallTrace72(const V& object, Sym name) {
        static const bool enabled = [] { auto value = std::getenv("PVZ72_TRACE_UI"); return value && *value == '1'; }();
        if (!enabled || object.t != V::INST) return;
        for (const char* candidate : {"handle_events", "finger", "_down", "_up", "pointer_down", "pointer_up",
             "action", "command", "refresh", "snapshot", "render", "bp", "card_grid", "native_frame",
             "seed_packet", "icon", "flip", "_set_draft_turn", "_finish_draft_action", "_ban"}) {
            if (name.str() != candidate) continue;
            owner = object.box->inst->type_name(); method = candidate;
            __android_log_print(ANDROID_LOG_INFO, "PVP72_UI", "BEGIN %s.%s", owner, method);
            break;
        }
    }
    ~UiCallTrace72() { if (method) __android_log_print(ANDROID_LOG_INFO, "PVP72_UI", "END %s.%s", owner, method); }
};
#endif
bool is_ordered_dict(const V&);

V str_format(const V& self, const Args& a);   // pvprt.cpp (uses format_spec)
V PyObj::call_self(const Args&) { throw PyError("TypeError", std::string("'") + type_name() + "' object is not callable"); }

// instance.__dict__: a live mapping onto the instance's attributes (declared slots + dynamic)
namespace {
struct InstDict : PyObj {
    std::shared_ptr<PyObj> owner;
    const char* type_name() const override { return "dict"; }
    bool isa(const char* c) const override { return std::string(c) == "dict" || std::string(c) == "object"; }
    V* find(const V& k) {
        if (k.t != V::STR) return nullptr;
        Sym n=k.sym();
        if (V* s = owner->slot(n)) return s->has() ? s : nullptr;
        return owner->find_dyn(n);
    }
    V getitem(const V& k) override { V* p = find(k); if (!p) throw PyError("KeyError", py_str(k)); return *p; }
    void setitem(const V& k, const V& v) override { owner->setattr(k.sym(), v); }
    void delitem(const V& k) override {
        Sym n = k.sym();
        if (V* s = owner->slot(n)) { s->del(); return; }
        for (size_t i = 0; i < owner->dyn.size(); ++i) if (owner->dyn[i].first == n) { owner->dyn.erase(owner->dyn.begin() + long(i)); return; }
        throw PyError("KeyError", py_str(k));
    }
    bool contains(const V& k) override { return find(k) != nullptr; }
    size_t length() override { return iterate().len(); }
    V iterate() override {
        V keys=V::list();
        V names=owner->method(Sym("__native_slot_names__"));
        if (names.has()) {
            V declared=names.call(Args{});
            if (declared.t!=V::TUPLE && declared.t!=V::LIST) throw PyError("TypeError","invalid native attribute metadata");
            for (const V& key:declared.items()) if (find(key) && !keys.contains(key)) keys.append(key);
        }
        for (auto& p:owner->dyn) { V key(p.first); if (p.first!=Sym("__native_local_class__") && p.second.has() && !keys.contains(key)) keys.append(key); }
        return keys;
    }
    V method(Sym name) override {
        static const SymIndex supported({Sym("get"),Sym("setdefault"),Sym("pop"),Sym("update"),Sym("keys"),Sym("items"),Sym("values"),Sym("copy")});
        if(supported.find(name)<0)return V();
        auto view=std::static_pointer_cast<InstDict>(shared_from_this());
        return V::func([view,name](const Args& a){V out;view->call_method(name,a,out);return out;});
    }
    bool call_method(Sym name, const Args& a, V& out) override {
        const std::string& n = name.str();
        if (n=="keys" || n=="items" || n=="values" || n=="copy") {
            V keys=iterate(), value=n=="copy"?V::dict():V::list();
            for(const V& key:keys.items()) {
                V item=getitem(key);
                if(n=="copy")value.at(key)=item;
                else value.append(n=="keys"?key:(n=="items"?V::tuple({key,item}):item));
            }
            out=value;return true;
        }
        if (n == "get") { V* p = find(a.pos.at(0)); out = p ? *p : (a.pos.size() > 1 ? a.pos[1] : V::none()); return true; }
        if (n == "setdefault") {
            V* p = find(a.pos.at(0));
            if (!p) { owner->setattr(a.pos[0].sym(), a.pos.size() > 1 ? a.pos[1] : V::none()); p = find(a.pos[0]); }
            out = *p; return true;
        }
        if (n == "pop") {
            V* p = find(a.pos.at(0));
            if (!p) { if (a.pos.size() > 1) { out = a.pos[1]; return true; } throw PyError("KeyError", py_str(a.pos[0])); }
            out = *p; delitem(a.pos[0]); return true;
        }
        if (n == "update") {
            if (!a.pos.empty()) for (auto& kv : a.pos[0].kv()) owner->setattr(kv.first.sym(), kv.second);
            for (auto& kv : a.kw) owner->setattr(kv.first, kv.second);
            out = V::none(); return true;
        }
        return false;
    }
};
}

namespace py { V native_method_type(); }
// Runtime subclass descriptors apply to a real allocated native base instance.
V local_class_member(const V& type,Sym name,int depth=0) {
    if(depth>64)throw PyError("RuntimeError","cyclic local class bases");
    if(type.t!=V::FUNC)return V();
    V bases;
    for(const auto& item:type.box->fattrs){if(item.first==name)return item.second;if(item.first==Sym("__bases__"))bases=item.second;}
    if(bases.is_list())for(const V& base:bases.items()){V value=local_class_member(base,name,depth+1);if(value.has())return value;}
    return V();
}
static V local_instance_attribute(PyObj* instance,Sym name) {
    const V* marker=instance->find_dyn(Sym("__native_local_class__"));if(!marker)return V();
    V type=*marker;if(name==Sym("__class__"))return type;
    V value=local_class_member(type,name);if(value.t!=V::FUNC)return value;
    for(const auto& item:value.box->fattrs)if((item.first==Sym("__native_class_value__") || item.first==Sym("__native_builtin_callable__")) && item.second.truthy())return value;
    return py::native_method_type().call(Args{value,instance->self()});
}
V PyObj::getattr(Sym name) {
    static const Sym S_dict("__dict__");
    if (name == S_dict) { auto d = std::make_shared<InstDict>(); d->owner = shared_from_this(); return V::inst(d); }
    if (V* s = slot(name)) {
        if (s->has()) return *s;
    }
    if (V* d = find_dyn(name)) return *d;
    if(V value=local_instance_attribute(this,name);value.has())return value;
    bool found = false;
    V p = property(name, found);
    if (found) return p;
    V m = method(name);
    if (m.has()) return m;
    static const Sym S_getattr("__getattr__");   // python: __getattr__ runs only after normal lookup fails
    if (!(name == S_getattr)) { V out; if (call_method(S_getattr, Args{V(name.str())}, out)) return out; }
    throw PyError("AttributeError", std::string("'") + type_name() + "' object has no attribute '" + name.str() + "'");
}

bool PyObj::hasattr(Sym name) {
    if(V value=local_instance_attribute(this,name);value.has())return true;
    if (V* s = slot(name)) if (s->has()) return true;
    if (find_dyn(name)) return true;
    bool found = false;
    property(name, found);
    if (found) return true;
    return method(name).has();
}

void PyObj::setattr(Sym name, V value) {
    if (set_property(name, value)) return;
    if (V* s = slot(name)) { *s = std::move(value); return; }
    if (V* d = find_dyn(name)) { *d = std::move(value); return; }
    dyn.emplace_back(name, std::move(value));
}

namespace py { V native_template_missing(const V&,const V&); }
V dunder_stub(const V& o, Sym name);   // pvprt.cpp: introspection on functions/classes
V getattr(const V& o, Sym name) {
    if (o.t == V::INST) return o.box->inst->getattr(name);
    if (o.t == V::TUPLE) for (auto& [key, value] : o.box->fattrs) if (key == name) return value;
    if (o.t == V::OBJ && o.box->obj->hook) { V out; if (o.box->obj->hook->getattr(*o.box->obj, name, out)) return out; }
    if (o.t == V::FUNC) {
        for (auto& p : o.box->fattrs) if (p.first == name) return p.second;
        return dunder_stub(o, name);   // introspection only (X.method.__code__ for the retired core)
    }
    if (o.t == V::DICT || o.t == V::OBJ) {   // namespace-like dicts (SimpleNamespace stand-ins)
        if(o.t==V::DICT && o.box->missing==3) {
            for(const auto& field:o.box->fattrs)if(field.first==Sym("__native_template_class__") && name==Sym("__class__"))return field.second;
            if(name==Sym("__missing__"))return V::func([o](const Args& args){return py::native_template_missing(o,args.pos.at(0));});
        }
        const V* p = o.find(V(name));
        if (p && p->has()) return *p;
        if(name==Sym("move_to_end") && is_ordered_dict(o)) return V::func([o,name](const Args& args){return callm(o,name,args);});
        static const SymIndex methods({SY("get"),SY("keys"),SY("values"),SY("items"),
            SY("copy"),SY("clear"),SY("update"),SY("setdefault"),SY("pop"),SY("popitem")});
        if(methods.find(name)<0)
            throw PyError("AttributeError","'"+o.type_name()+"' object has no attribute '"+name.str()+"'");
    }
    if (o.t == V::TUPLE && o.box->color) {   // pygame.Color channels (the value stays tuple-equal like pygame's)
        static const SymIndex ch({SY("r"), SY("g"), SY("b"), SY("a")});
        int k = ch.find(name);
        if (k >= 0) return size_t(k) < o.box->items.size() ? o.box->items[size_t(k)] : V(255.0);
    }
    if (o.t == V::DICT || o.t == V::OBJ || o.is_list() || o.t == V::STR) {
        // bound builtin method value (d.get, lst.append ...)
        V self = o;
        return V::func([self, name](const Args& a) { return callm(self, name, a); });
    }
    throw PyError("AttributeError", "'" + o.type_name() + "' object has no attribute '" + name.str() + "'");
}

V getattr(const V& o, Sym name, const V& dflt) {
    if (o.t == V::FUNC) {   // function attributes: no introspection stub when a default is given
        for (auto& p : o.box->fattrs) if (p.first == name) return p.second;
        if(name==Sym("__get__")){try{return dunder_stub(o,name);}catch(const PyError& error){if(!error.matches("AttributeError"))throw;}}
        return dflt;
    }
    if (o.t == V::NONE || o.t == V::ABSENT || o.t == V::NUM || o.t == V::BOOL) {
        static const Sym S_class("__class__");
        if (name != S_class) return dflt;   // no attributes; avoid raising (getattr with a default is common)
    }
    if (o.t == V::INST) {   // non-raising lookup in the instance (same order as PyObj::getattr)
        PyObj* p = o.box->inst.get();
        static const Sym S_dict("__dict__");
        if (name != S_dict) {
            if (V* sl = p->slot(name)) if (sl->has()) return *sl;
            if (V* d = p->find_dyn(name)) return *d;
            bool found = false;
            V pr = p->property(name, found);
            if (found) return pr;
            V m = p->method(name);
            if (m.has()) return m;
            // Missing native slots may still be supplied by the real __getattr__.
        }
    }
    try { return getattr(o, name); } catch (PyError& e) { if (e.kind == "AttributeError") return dflt; throw; }
}

void setattr(const V& o, Sym name, const V& value) {
    if (o.t == V::INST) { o.box->inst->setattr(name, value); return; }
    if (o.t == V::FUNC) {
        for (auto& p : o.box->fattrs) if (p.first == name) { p.second = value; return; }
        o.box->fattrs.emplace_back(name, value);
        return;
    }
    if (o.t == V::DICT || o.t == V::OBJ) { const_cast<V&>(o).at(V(name)) = value; return; }
    throw PyError("AttributeError", "cannot set attribute on '" + o.type_name() + "'");
}

bool hasattr(const V& o, Sym name) {
    if(o.t==V::INST){try{(void)getattr(o,name);return true;}catch(const PyError& error){if(error.matches("AttributeError"))return false;throw;}}
    if (o.t == V::TUPLE) for (auto& [key, value] : o.box->fattrs) if (key == name) return true;
    if (o.t == V::FUNC) { for (auto& p : o.box->fattrs) if (p.first == name) return true; if(name==Sym("__get__")){try{return dunder_stub(o,name).has();}catch(const PyError& error){if(!error.matches("AttributeError"))throw;}} return false; }
    if (o.t == V::DICT || o.t == V::OBJ) {
        if(o.t==V::DICT && o.box->missing==3 && (name==Sym("__missing__") || name==Sym("__class__")))return true;
        if (o.contains(V(name))) return true;
        // same bound dict methods getattr() hands out (hasattr(unit, "get") is True for a dict unit in Python)
        if(name==Sym("move_to_end") && is_ordered_dict(o))return true;
        static const SymIndex methods({SY("get"),SY("keys"),SY("values"),SY("items"),
            SY("copy"),SY("clear"),SY("update"),SY("setdefault"),SY("pop"),SY("popitem")});
        return methods.find(name) >= 0;
    }
    return false;
}

thread_local int g_call_depth = 0;
static thread_local const V* current_called_function=nullptr;
V native_current_function(){if(!current_called_function)throw PyError("RuntimeError","No active native function");return *current_called_function;}

V V::call(const Args& a) const {
    ++g_v_activity_calls;
    gil::poll();
    struct Depth { Depth() { ++g_call_depth; } ~Depth() { --g_call_depth; } } depth_;
    if (t == FUNC) {
        // The executing function owns itself until its body and callbacks return.
        // A direct, immutable local self-reference needs no captured self-cycle.
        V executing=*this;const V* previous=current_called_function;current_called_function=&executing;
        struct Restore {const V* previous;~Restore(){current_called_function=previous;}} restore{previous};
        return executing.box->fn(a);
    }
    if (t == INST) return box->inst->call_self(a);
    throw PyError("TypeError", "'" + type_name() + "' object is not callable");
}

static const V& arg(const Args& a, size_t i, const char* m) {
    if (i >= a.pos.size()) throw PyError("TypeError", std::string(m) + "() missing argument");
    return a.pos[i];
}

// Keep the common instance path out of the large builtin dispatcher stack
// frame. This preserves late-bound instance overrides while bounded graphics
// recursion no longer allocates every builtin branch's locals at each level.
static V callm_builtin(const V& o, Sym name, const Args& a);
static V callm_instance(const V& o, Sym name, const Args& a) {
        PyObj* p = o.box->inst.get();
        V* sl = p->slot(name);   // an instance attribute shadows the method
        if ((!sl || !sl->has()) && !p->find_dyn(name)) {
            if(V method=local_instance_attribute(p,name);method.has())return method.call(a);
            V out;
            struct Depth { Depth() { ++g_call_depth; } ~Depth() { --g_call_depth; } } depth_;
            if (p->call_method(name, a, out)) return out;
        }
        return p->getattr(name).call(a);
}
V callm(const V& o, Sym name, const Args& a) {
#ifdef __ANDROID__
    UiCallTrace72 trace(o, name);
#endif
    ++g_v_activity_calls;
    gil::poll();
    return o.t==V::INST?callm_instance(o,name,a):callm_builtin(o,name,a);
}
static V callm_builtin(const V& o, Sym name, const Args& a) {
    if(o.t==V::DICT)for(const auto& marker:o.box->fattrs)
        if(marker.first==Sym("__native_namespace__") && marker.second.truthy()) {
            if(const V* value=o.find(V(name))) {V held=*value;return held.call(a);}
            break;
        }
    if (o.t == V::OBJ && o.box->obj->hook) { V out; if (o.box->obj->hook->call(*o.box->obj, o, name, a, out)) return out; }
    const std::string& m = name.str();
    V& self = const_cast<V&>(o);
    auto nargs = a.pos.size();
    if(o.t==V::LIST && name==Sym("__setitem__")){if(a.pos.size()!=2 || !a.kw.empty())throw PyError("TypeError","list.__setitem__ requires index and value");if(!a.pos[0].is_num() || !std::isfinite(a.pos[0].num()) || std::trunc(a.pos[0].num())!=a.pos[0].num())throw PyError("TypeError","list index must be an integer");self.idx(int64_t(a.pos[0].num()))=a.pos[1];return V::none();}
    if (o.is_list() || o.t == V::SET) {
        if (name == SY("append")) { self.append(arg(a, 0, "append")); return V::none(); }
        if (name == SY("popleft")) { auto& it = self.items(); if (it.empty()) throw PyError("IndexError", "pop from an empty deque"); V x = it.front(); it.erase(it.begin()); return x; }
        if (name == SY("appendleft")) { self.items().insert(self.items().begin(), arg(a, 0, "appendleft")); return V::none(); }
        if (name == SY("add")) { if (!self.contains(arg(a, 0, "add"))) self.set_insert_new(a.pos[0]); return V::none(); }
        if (name == SY("pop")) return nargs ? py::pop(self, a.pos[0]) : py::pop(self);
        if (name == SY("insert")) { py::insert(self, arg(a, 0, m.c_str()), arg(a, 1, m.c_str())); return V::none(); }
        if (name == SY("remove")) { py::remove(self, arg(a, 0, "remove")); return V::none(); }
        if (name == SY("discard")) { if (self.contains(arg(a, 0, "discard"))) py::remove(self, a.pos[0]); return V::none(); }
        if (name == SY("index")) return py::index(self, arg(a, 0, "index"));
        if (name == SY("count")) return py::count(self, arg(a, 0, "count"));
        if (name == SY("extend")) { py::extend(self, arg(a, 0, "extend")); return V::none(); }
        if (name == SY("copy")) return py::copy(self);
        if (name == SY("clear")) { self.items().clear(); return V::none(); }
        if (name == SY("reverse")) { std::reverse(self.items().begin(), self.items().end()); return V::none(); }
        if (name == SY("update") && o.t == V::SET) { for (V held_ = py::iter_list(arg(a, 0, "update")); auto& x : held_.items()) if (!self.contains(x)) self.set_insert_new(x); return V::none(); }
        if (name == SY("union")) { V r = V::set(self.items()); for (V held_ = py::iter_list(arg(a, 0, "union")); auto& x : held_.items()) if (!r.contains(x)) r.set_insert_new(x); return r; }
        if (name == SY("issubset")) { for (auto& x : self.items()) if (!arg(a, 0, "issubset").contains(x)) return V(false); return V(true); }
        if (name == SY("intersection")) { std::vector<V> r; for (auto& x : self.items()) if (arg(a, 0, "intersection").contains(x)) r.push_back(x); return V::set(r); }
        if (o.t == V::SET && (name == SY("intersection_update") || name == SY("difference_update"))) {
            bool keep_in = name == SY("intersection_update");
            V other = arg(a, 0, "update");
            std::vector<V> r;
            for (auto& x : o.items()) if (other.contains(x) == keep_in) r.push_back(x);
            self.items() = std::move(r);
            return V::none();
        }
        if (name == SY("symmetric_difference") || name == SY("symmetric_difference_update")) {
            V other = py::iter_list(arg(a, 0, "symmetric_difference"));
            std::vector<V> r;
            for (auto& x : o.items()) if (!other.contains(x)) r.push_back(x);
            for (auto& x : other.items()) if (!o.contains(x)) r.push_back(x);
            if (name == SY("symmetric_difference")) return V::set(r);
            self.items() = V::set(r).items();
            return V::none();
        }
        if (name == SY("issuperset")) { for (V held_ = py::iter_list(arg(a, 0, "issuperset")); auto& x : held_.items()) if (!o.contains(x)) return V(false); return V(true); }
        if (name == SY("isdisjoint")) { for (V held_ = py::iter_list(arg(a, 0, "isdisjoint")); auto& x : held_.items()) if (o.contains(x)) return V(false); return V(true); }
        if (name == SY("difference")) { std::vector<V> r; for (auto& x : self.items()) if (!arg(a, 0, "difference").contains(x)) r.push_back(x); return V::set(r); }
        if (name == SY("sort")) {
            // key=/reverse= handled by py::sorted_by in translated code; plain sort here
            std::stable_sort(self.items().begin(), self.items().end(), [](const V& x, const V& y) { return py_lt(x, y); });
            return V::none();
        }
    }
    if (o.t == V::DICT || o.t == V::OBJ) {
        if (name == SY("get")) return self.get(arg(a, 0, "get"), nargs > 1 ? a.pos[1] : V::none());
        if (name == SY("pop")) return nargs > 1 ? py::pop(self, a.pos[0], a.pos[1]) : py::pop(self, arg(a, 0, "pop"));
        if (name == SY("setdefault")) return py::setdefault(self, arg(a, 0, "setdefault"), nargs > 1 ? a.pos[1] : V::none());
        if (o.t == V::DICT && name == SY("move_to_end")) {
            PVP_PROFILE_SCOPE("OrderedDict::move_to_end");
            if(!is_ordered_dict(o))throw PyError("AttributeError","dict has no attribute move_to_end");
            if(nargs<1 || nargs>2 || (nargs>1 && a.has_kw(SY("last"))))throw PyError("TypeError","move_to_end expects a key and optional last");
            for(const auto& kw:a.kw)if(kw.first!=SY("last"))throw PyError("TypeError","unexpected move_to_end keyword");
            auto& kv = self.kv();
            bool last = true;
            if (nargs > 1) last = a.pos[1].truthy();
            for (auto& p : a.kw) if (p.first == SY("last")) last = p.second.truthy();
            for (size_t i = 0; i < kv.size(); ++i)
                if (py_eq(kv[i].first, a.pos.at(0))) {
                    auto e = kv[i];
                    kv.erase(kv.begin() + long(i));
                    if (last) kv.push_back(e); else kv.insert(kv.begin(), e);
                    return V::none();
                }
            throw PyError("KeyError", py_str(a.pos[0]));
        }
        if (o.t == V::DICT && name == SY("popitem")) {
            if(!is_ordered_dict(o) && (nargs || !a.kw.empty()))throw PyError("TypeError","dict.popitem takes no arguments");
            if(nargs>1 || (nargs && a.has_kw(SY("last"))))throw PyError("TypeError","popitem expects optional last");
            for(const auto& kw:a.kw)if(kw.first!=SY("last"))throw PyError("TypeError","unexpected popitem keyword");
            auto& kv = self.kv();
            if (kv.empty()) throw PyError("KeyError", "popitem(): dictionary is empty");
            bool last = true;
            if (nargs > 0) last = a.pos[0].truthy();
            for (auto& p : a.kw) if (p.first == SY("last")) last = p.second.truthy();
            auto e = last ? kv.back() : kv.front();
            if (last) kv.pop_back(); else kv.erase(kv.begin());
            return V::tuple({e.first, e.second});
        }
        if (name == SY("keys")) return py::keys(self);
        if (name == SY("values")) return py::values(self);
        if (name == SY("items")) return py::items(self);
        if (name == SY("copy")) return py::copy(self);
        if (name == SY("update")) {
            if (nargs) {
                const V& other = a.pos[0];
                if (other.is_list()) for (auto& kv : other.items()) self.at(kv.idx(0)) = kv.idx(1);
                else if (other.is_obj()) other.o()->each([&](const V& k, const V& v) { self.at(k) = v; });
                else for (auto& p : other.kv()) self.at(p.first) = p.second;
            }
            for (auto& p : a.kw) self.at(V(p.first)) = p.second;
            return V::none();
        }
        if (name == SY("clear")) {
            if (o.t == V::DICT) self.kv().clear();
            else { V keys = py::keys(self); for (auto& k : keys.items()) self.erase(k); }
            return V::none();
        }
    }
    if (o.t == V::STR) {
        if (name == SY("split")) {
            if (nargs && !a.pos[0].is_none()) return py::split(self, a.pos[0]);
            std::vector<V> out; std::string cur; bool in = false;   // split(): runs of whitespace, no empties
            for (char c : self.str()) {
                if (std::isspace(static_cast<unsigned char>(c))) { if (in) { out.emplace_back(cur); cur.clear(); in = false; } }
                else { cur += c; in = true; }
            }
            if (in) out.emplace_back(cur);
            return V::list(out);
        }
        if (name == SY("startswith")) {
            const V& p = arg(a, 0, "startswith");
            if (p.is_list()) { for (auto& x : p.items()) if (py::startswith(self, x)) return V(true); return V(false); }
            return V(py::startswith(self, p));
        }
        if (name == SY("endswith")) {
            const V& p = arg(a, 0, "endswith");
            if (p.is_list()) { for (auto& x : p.items()) if (py::endswith(self, x)) return V(true); return V(false); }
            return V(py::endswith(self, p));
        }
        if (name == SY("join")) return py::join(self, py::iter_list(arg(a, 0, "join")));
        if (name == SY("replace")) return py::replace(self, arg(a, 0, "replace"), arg(a, 1, "replace"));
        if (name == SY("strip") || name == SY("rstrip") || name == SY("lstrip")) {
            if(a.pos.size()>1 || !a.kw.empty())throw PyError("TypeError","strip accepts at most one positional argument");
            const V chars=a.pos.empty()?V::none():a.pos[0];
            if(!chars.is_none() && (chars.t!=V::STR || chars.byt!=self.byt))throw PyError("TypeError","strip characters must have the same string type");
            const std::string text=self.str();
            auto spans=[&](const std::string& value){std::vector<std::pair<size_t,size_t>> out;for(size_t i=0;i<value.size();){unsigned char c=static_cast<unsigned char>(value[i]);size_t n=self.byt||c<128?1:c<224?2:c<240?3:4;n=std::min(n,value.size()-i);out.emplace_back(i,n);i+=n;}return out;};
            auto tokens=spans(text);std::vector<std::string> trim;
            if(!chars.is_none())for(auto span:spans(chars.str()))trim.push_back(chars.str().substr(span.first,span.second));
            auto removable=[&](const std::pair<size_t,size_t>& span){
                std::string item=text.substr(span.first,span.second);
                if(!chars.is_none())return std::find(trim.begin(),trim.end(),item)!=trim.end();
                uint32_t cp=static_cast<unsigned char>(item[0]);
                if(item.size()>1){cp&=(1u<<(7-item.size()))-1;for(size_t i=1;i<item.size();++i)cp=(cp<<6)|(static_cast<unsigned char>(item[i])&63);}
                return (cp>=9 && cp<=13)||cp==32||(!self.byt && ((cp>=28 && cp<=31)||cp==0x85||cp==0xa0||cp==0x1680||(cp>=0x2000 && cp<=0x200a)||cp==0x2028||cp==0x2029||cp==0x202f||cp==0x205f||cp==0x3000));
            };
            size_t begin=0,end=tokens.size();
            if(name!=SY("rstrip"))while(begin<end && removable(tokens[begin]))++begin;
            if(name!=SY("lstrip"))while(end>begin && removable(tokens[end-1]))--end;
            size_t first=begin<tokens.size()?tokens[begin].first:text.size(),last=end?tokens[end-1].first+tokens[end-1].second:0;
            V result(text.substr(first,last>first?last-first:0));result.byt=self.byt;return result;
        }
        if (name == SY("format")) return str_format(self, a);
        if (name == SY("isidentifier")) return V(!self.str().empty());
        if (name == SY("encode")) { V r = self; r.byt = 1; return r; }
        if (name == SY("decode")) { V r = self; r.byt = 0; return r; }
        if (name == SY("isdigit")) { const std::string& t = self.str(); return V(!t.empty() && t.find_first_not_of("0123456789") == std::string::npos); }

        if (name == SY("rsplit")) return nargs ? py::split(self, a.pos[0]) : py::split(self, V(" "));
        if (name == SY("count")) { const std::string& t = self.str(); const std::string& n = arg(a, 0, "count").str(); double c = 0; size_t p = 0; if (!n.empty()) while ((p = t.find(n, p)) != std::string::npos) { ++c; p += n.size(); } return V(c); }
        if (name == SY("zfill")) { std::string t = self.str(); size_t w = size_t(arg(a, 0, "zfill").num()); while (t.size() < w) t = "0" + t; return V(t); }
        if (name == SY("find")) { auto p = self.str().find(arg(a, 0, "find").str()); return V(p == std::string::npos ? -1.0 : double(p)); }
        if (name == SY("index") && self.t == V::STR) { auto p = self.str().find(arg(a, 0, "index").str()); if (p == std::string::npos) throw PyError("ValueError", "substring not found"); return V(double(p)); }
        if (name == SY("lower") || name == SY("upper") || name == SY("casefold") || name == SY("swapcase") ||
            name == SY("title") || name == SY("capitalize")) {
            std::string t = self.str();   // ASCII letters only (CJK text has no case)
            bool up = name == SY("upper"), sw = name == SY("swapcase"), ti = name == SY("title"), cap = name == SY("capitalize");
            bool start = true;
            for (auto& c : t) {
                unsigned char u = static_cast<unsigned char>(c);
                if (u >= 0x80) { start = false; continue; }
                bool alpha = std::isalpha(u) != 0;
                if (sw) c = char(std::isupper(u) ? std::tolower(u) : std::toupper(u));
                else if (ti) c = char(start ? std::toupper(u) : std::tolower(u));
                else if (cap) c = char(&c == &t[0] ? std::toupper(u) : std::tolower(u));
                else c = char(up ? std::toupper(u) : std::tolower(u));
                start = !alpha;
            }
            return V(t);
        }
        if (name == SY("partition") || name == SY("rpartition")) {
            const std::string& t = self.str();
            const std::string& sep = arg(a, 0, "partition").str();
            size_t p = name == SY("partition") ? t.find(sep) : t.rfind(sep);
            if (p == std::string::npos)
                return name == SY("partition") ? V::tuple({V(t), V(""), V("")}) : V::tuple({V(""), V(""), V(t)});
            return V::tuple({V(t.substr(0, p)), V(sep), V(t.substr(p + sep.size()))});
        }
        if (name == SY("ljust") || name == SY("rjust") || name == SY("center")) {
            std::string t = self.str();
            size_t width = size_t(arg(a, 0, "ljust").num());
            std::string fill = nargs > 1 ? a.pos[1].str() : std::string(" ");
            size_t cps = 0; for (unsigned char c : t) if ((c & 0xC0) != 0x80) ++cps;
            if (cps >= width) return self;
            size_t pad = width - cps;
            auto rep = [&](size_t n) { std::string r; for (size_t i = 0; i < n; ++i) r += fill; return r; };
            if (name == SY("ljust")) return V(t + rep(pad));
            if (name == SY("rjust")) return V(rep(pad) + t);
            size_t left = pad / 2 + (pad & width & 1);
            return V(rep(left) + t + rep(pad - left));
        }
        if (name == SY("isalpha") || name == SY("isalnum") || name == SY("isspace") || name == SY("isupper") || name == SY("islower") ||
            name == SY("isnumeric") || name == SY("isdecimal") || name == SY("isascii") || name == SY("isprintable")) {
            const std::string& t = self.str();
            if (t.empty()) return V(name == SY("isascii") || name == SY("isprintable"));
            bool any_cased = false;
            for (unsigned char c : t) {
                if (name == SY("isascii")) { if (c >= 0x80) return V(false); continue; }
                if (name == SY("isprintable")) { if (c < 0x20 || c == 0x7f) return V(false); continue; }
                if (c >= 0x80) { if (name == SY("isspace") || name == SY("isnumeric") || name == SY("isdecimal")) return V(false); continue; }
                if (name == SY("isalpha") && !std::isalpha(c)) return V(false);
                if (name == SY("isalnum") && !std::isalnum(c)) return V(false);
                if (name == SY("isspace") && !std::isspace(c)) return V(false);
                if ((name == SY("isnumeric") || name == SY("isdecimal")) && !std::isdigit(c)) return V(false);
                if (name == SY("isupper")) { if (std::islower(c)) return V(false); if (std::isupper(c)) any_cased = true; }
                if (name == SY("islower")) { if (std::isupper(c)) return V(false); if (std::islower(c)) any_cased = true; }
            }
            if (name == SY("isupper") || name == SY("islower")) return V(any_cased);
            return V(true);
        }
        if (name == SY("splitlines")) {
            const std::string& t = self.str();
            bool keep = nargs > 0 && a.pos[0].truthy();
            std::vector<V> out; size_t s0 = 0;
            for (size_t i = 0; i < t.size(); ++i) {
                if (t[i] == '\n' || t[i] == '\r') {
                    size_t e = i;
                    if (t[i] == '\r' && i + 1 < t.size() && t[i + 1] == '\n') ++i;
                    out.emplace_back(t.substr(s0, (keep ? i + 1 : e) - s0));
                    s0 = i + 1;
                }
            }
            if (s0 < t.size()) out.emplace_back(t.substr(s0));
            return V::list(out);
        }
        if (name == SY("rfind") || name == SY("rindex")) {
            auto p = self.str().rfind(arg(a, 0, "rfind").str());
            if (p == std::string::npos && name == SY("rindex")) throw PyError("ValueError", "substring not found");
            return V(p == std::string::npos ? -1.0 : double(p));
        }
        if (name == SY("expandtabs")) { std::string t = self.str(), o; for (char c : t) { if (c == '\t') o += "        "; else o += c; } return V(o); }
        if (name == SY("removeprefix")) { const std::string& t = self.str(); const std::string& p = arg(a, 0, "removeprefix").str(); return t.rfind(p, 0) == 0 ? V(t.substr(p.size())) : self; }
        if (name == SY("removesuffix")) { const std::string& t = self.str(); const std::string& p = arg(a, 0, "removesuffix").str(); return t.size() >= p.size() && t.compare(t.size() - p.size(), p.size(), p) == 0 ? V(t.substr(0, t.size() - p.size())) : self; }
    }
    if (o.t == V::FUNC && name == SY("__call__")) return o.call(a);
    if (o.t == V::FUNC)   // function attributes; class values carry their static / class methods here
        for (auto& p : o.box->fattrs) if (p.first == name) return p.second.call(a);
    if(o.t==V::FUNC && name==Sym("__get__"))return pvz::getattr(o,name).call(a);
    if(o.t==V::DICT && o.box->missing==3 && name==Sym("__missing__"))return py::native_template_missing(o,arg(a,0,"__missing__"));
    if (o.t == V::DICT) {   // namespace-like dict (SimpleNamespace stand-in): call the stored member
        const V* p = o.find(V(name));
        if (p && p->has()) return p->call(a);
    }
    throw PyError("AttributeError", "'" + o.type_name() + "' object has no attribute '" + m + "'");
}

bool isinstance(const V& o, const char* type) {
    std::string t(type);
    switch (o.t) {
        case V::NUM: return (t == "int" && std::isfinite(o.n) && std::trunc(o.n) == o.n) || t == "float" || t == "Number" || t == "Real";
        case V::BOOL: return t == "bool" || t == "int";
        case V::STR: return t == "str";
        case V::LIST: return t == "list" || t == "Sequence";
        case V::TUPLE: return t == "tuple" || t == "Sequence";
        case V::DICT: {
            if(t=="dict" || t=="Mapping" || (t=="OrderedDict" && is_ordered_dict(o)))return true;
            if(o.box->missing==3)for(const auto& field:o.box->fattrs)if(field.first==Sym("__native_template_class__"))for(const auto& attr:field.second.box->fattrs)if(attr.first==Sym("__name__") && attr.second.str()==t)return true;
            return false;
        }
        case V::OBJ: return t == "dict" || t == "Mapping" || (o.box->obj->hook && t == o.box->obj->hook->type_name());
        case V::SET: return t == "set" || t == "frozenset";
        case V::FUNC: return t == "function";
        case V::INST: return o.box->inst->isa(type);
        case V::NONE: case V::ABSENT: return t == "NoneType";
    }
    return false;
}

}  // namespace pvz

namespace pvz {
V PyObj::getitem(const V&) { throw PyError("TypeError", std::string("'") + type_name() + "' object is not subscriptable"); }
void PyObj::setitem(const V&, const V&) { throw PyError("TypeError", std::string("'") + type_name() + "' object does not support item assignment"); }
void PyObj::delitem(const V&) { throw PyError("TypeError", std::string("'") + type_name() + "' object does not support item deletion"); }
bool PyObj::contains(const V&) { throw PyError("TypeError", std::string("argument of type '") + type_name() + "' is not iterable"); }
size_t PyObj::length() { throw PyError("TypeError", std::string("object of type '") + type_name() + "' has no len()"); }
V PyObj::iterate() { throw PyError("TypeError", std::string("'") + type_name() + "' object is not iterable"); }
// Native closure blueprints describe actual C++ captures, never CPython wordcode.
// A clone runs the same compiled body with independently selected real cells.
namespace {
struct NativeCell final : PyObj {
    V value;
    const char* type_name()const override{return "cell";}
    V property(Sym name,bool& found)override{
        if(name!=Sym("cell_contents")){found=false;return V();}
        found=true;if(!value.has())throw PyError("ValueError","Cell is empty");return value;
    }
    bool set_property(Sym name,const V& v)override{if(name!=Sym("cell_contents"))return false;value=v;return true;}
};
struct NativeClosureBlueprint final : PyObj {
    V name,names,globals;
    NativeClosureBody body;
    const char* type_name()const override{return "NativeClosureBlueprint";}
    V property(Sym field,bool& found)override{
        found=true;
        if(field==Sym("co_freevars"))return names;
        if(field==Sym("co_name"))return name;
        found=false;return V();
    }
    bool set_property(Sym,const V&)override{throw PyError("AttributeError","Native closure blueprints are immutable");}
};
struct NativeClosureFunction final : PyObj {
    V blueprint,cells;
    const char* type_name()const override{return "function";}
    V property(Sym field,bool& found)override{
        auto* code=as<NativeClosureBlueprint>(blueprint);found=true;
        if(field==Sym("__code__"))return blueprint;
        if(field==Sym("__closure__"))return cells;
        if(field==Sym("__globals__"))return code->globals;
        if(field==Sym("__name__"))return code->name;
        found=false;return V();
    }
    V call_self(const Args& args)override{return as<NativeClosureBlueprint>(blueprint)->body(cells,args);}
};
}
V native_cell(const Args& args){
    if(args.pos.size()>1||!args.kw.empty())throw PyError("TypeError","CellType accepts at most one positional value");
    auto cell=std::make_shared<NativeCell>();if(!args.pos.empty())cell->value=args.pos[0];return V::inst(cell);
}
V native_cell_value(const V& value){auto* cell=as<NativeCell>(value);if(!cell)throw PyError("TypeError","Expected a native closure cell");if(!cell->value.has())throw PyError("ValueError","Cell is empty");return cell->value;}
V make_native_closure(const V& name,const V& names,const V& values,const V& globals,NativeClosureBody body){
    if(names.t!=V::TUPLE||values.t!=V::TUPLE||names.len()!=values.len())throw PyError("TypeError","Native closure capture names and values must match");
    auto code=std::make_shared<NativeClosureBlueprint>();code->name=name;code->names=names;code->globals=globals;code->body=std::move(body);
    auto fn=std::make_shared<NativeClosureFunction>();fn->blueprint=V::inst(code);
    std::vector<V> cells;for(const auto& value:values.items())cells.push_back(native_cell(Args{value}));fn->cells=V::tuple(cells);return V::inst(fn);
}
V clone_native_closure(const Args& args){
    if(args.pos.empty()||!as<NativeClosureBlueprint>(args.pos[0]))return V();
    if(args.pos.size()<2||args.pos.size()>5)throw PyError("TypeError","Native closure clone requires blueprint and compiled global environment");
    auto* code=as<NativeClosureBlueprint>(args.pos[0]);
    if(args.pos[1].t!=code->globals.t || !args.pos[1].box || args.pos[1].box.get()!=code->globals.box.get())throw PyError("ValueError","Cannot replace a compiled closure's global environment");
    if(args.pos.size()>2&&!args.pos[2].is_none()&&args.pos[2]!=code->name)throw PyError("ValueError","Cannot rename a compiled closure blueprint");
    if(args.pos.size()>3&&!args.pos[3].is_none())throw PyError("NotImplementedError","Compiled closure defaults cannot be replaced");
    V cells=args.pos.size()>4?args.pos[4]:args.get(99999,Sym("closure"),nullptr);
    if(cells.t!=V::TUPLE||cells.len()!=code->names.len())throw PyError("ValueError","Native closure cell count does not match blueprint");
    for(const auto& value:cells.items())if(!as<NativeCell>(value))throw PyError("TypeError","Native closure capture must be a cell");
    for(const auto& kw:args.kw)if(kw.first!=Sym("closure"))throw PyError("TypeError","Unsupported native closure clone argument");
    auto fn=std::make_shared<NativeClosureFunction>();fn->blueprint=args.pos[0];fn->cells=cells;return V::inst(fn);
}

}  // namespace pvz
