// Test-only adapters. Unsupported patch targets fail explicitly; no successful no-op mocks.
#include "cpptests/registry.h"
#include "pg/pg.h"
#include <algorithm>
#include <stdexcept>
namespace pvz::cpptests {
namespace {
struct DictPatch : PyObj {
    V target, values, saved;
    std::vector<std::pair<V,V>> old;
    bool env=false, clear=false, active=false;
    const char* type_name() const override { return "_patch_dict"; }
    V snapshot() {
        if(env)return callm(target,Sym("copy"),Args{});
        if(!target.is_inst())return py::copy(target);
        V out=V::dict();
        V keys=py::iter_list(target.box->inst->iterate());
        for(const auto& key:keys.items())out.at(key)=target.box->inst->getitem(key);
        return out;
    }
    void put(const V& key,const V& value) {
        if(target.is_inst())pvz::setitem(target,key,value);else target.at(key)=value;
    }
    void erase(const V& key) {
        if(target.is_inst())target.box->inst->delitem(key);else py_del(target,key);
    }
    V start() {
        if(active)throw PyError("RuntimeError","patch already active");
        saved=snapshot();
        try {
            if(clear)for(const auto& pair:saved.kv())erase(pair.first);
            for(const auto& pair:values.kv())put(pair.first,pair.second);
        }
        catch(...) {
            V current=snapshot();
            for(const auto& pair:current.kv())if(!saved.contains(pair.first))erase(pair.first);
            for(const auto& pair:saved.kv())put(pair.first,pair.second);
            throw;
        }
        active=true;return target;
    }
    V stop() {
        if(!active)return V::none();
        V current=snapshot();
        for(const auto& pair:current.kv())if(!saved.contains(pair.first))erase(pair.first);
        for(const auto& pair:saved.kv())put(pair.first,pair.second);
        active=false;return V(false);
    }
    V method(Sym n) override {
        auto self=std::static_pointer_cast<DictPatch>(shared_from_this());
        if(n==Sym("start")||n==Sym("__enter__")) return V::func([self](const Args&){return self->start();});
        if(n==Sym("stop")||n==Sym("__exit__")) return V::func([self](const Args&){return self->stop();});
        return V();
    }
};
V& mock_default() { static V value = py::new_object(); return value; }
V call_record(const Args& a) {
    V args = V::tuple(a.pos), kwargs = V::dict();
    for (auto& [name, value] : a.kw) kwargs.at(V(name)) = value;
    V record = V::tuple({args, kwargs});
    record.box->fattrs.emplace_back(Sym("args"), args);
    record.box->fattrs.emplace_back(Sym("kwargs"), kwargs);
    return record;
}
struct MockObject : PyObj {
    V result, effect = V::none(), wraps = V::none(), spec = V::none();
    V calls = V::list(), effect_items;
    size_t effect_index = 0;
    bool magic = false, spec_set = false;
    const char* type_name() const override { return magic ? "MagicMock" : "Mock"; }
    bool isa(const char* type) const override { return std::string(type) == "Mock" || std::string(type) == type_name() || std::string(type) == "object"; }
    size_t length() override { if (magic) return 0; throw PyError("TypeError", "Mock has no len()"); }
    V make_child() { auto child = std::make_shared<MockObject>(); child->magic = magic; return V::inst(child); }
    V default_result() { if (!result.has()) result = make_child(); return result; }
    V property(Sym name, bool& found) override {
        found = true;
        if (name == Sym("return_value")) return default_result();
        if (name == Sym("side_effect")) return effect;
        if (name == Sym("call_count")) return V(double(calls.len()));
        if (name == Sym("called")) return V(calls.len() != 0);
        if (name == Sym("call_args")) return calls.len() ? calls.items().back() : V::none();
        if (name == Sym("call_args_list")) return calls;
        found = false; return V();
    }
    bool set_property(Sym name, const V& value) override {
        if (name == Sym("return_value")) { result = value; return true; }
        if (name == Sym("side_effect")) { effect = value; effect_items = V(); effect_index = 0; return true; }
        if (spec_set && !spec.is_none() && !pvz::hasattr(spec, name))
            throw PyError("AttributeError", "Mock spec has no attribute " + name.str());
        return false;
    }
    V call_self(const Args& a) override {
        calls.append(call_record(a));   // calls that raise still count, just as in unittest.mock
        if (!effect.is_none()) {
            if (isinstance(effect, "BaseException")) py::raise(effect);
            if (effect.t == V::STR && (effect.str() == "OSError" || effect.str() == "ValueError" || effect.str() == "RuntimeError" || effect.str() == "TypeError")) py::raise(effect);
            V value;
            if (py::callable(effect).truthy()) value = effect.call(a);
            else {
                if (!effect_items.has()) effect_items = py::iter_list(effect);
                if (effect_index >= effect_items.len()) throw PyError("StopIteration", "");
                value = effect_items.idx(int64_t(effect_index++));
                if (isinstance(value, "BaseException")) py::raise(value);
            }
            if (!py_is(value, mock_default())) return value;
        }
        if (result.has()) return result;
        if (!wraps.is_none()) return wraps.call(a);
        return default_result();
    }
    V method(Sym name) override {
        auto self = std::static_pointer_cast<MockObject>(shared_from_this());
        std::string n = name.str();
        if (n == "__call__") return V::func([self](const Args& a) { return self->call_self(a); });
        if (n == "reset_mock") return V::func([self](const Args& a) {
            self->calls = V::list();
            for (auto& [key, value] : a.kw) if (value.truthy()) {
                if (key == Sym("return_value")) self->result = V();
                else if (key == Sym("side_effect")) { self->effect = V::none(); self->effect_items = V(); self->effect_index = 0; }
            }
            for (auto& [key, child] : self->dyn) if (as<MockObject>(child)) callm(child, Sym("reset_mock"), Args{});
            return V::none();
        });
        if (n == "assert_called" || n == "assert_called_once" || n == "assert_not_called" ||
            n == "assert_called_with" || n == "assert_called_once_with" || n == "assert_any_call")
            return V::func([self, n](const Args& a) {
                size_t count = self->calls.len(); bool okay = true;
                if (n == "assert_called") okay = count != 0;
                else if (n == "assert_called_once") okay = count == 1;
                else if (n == "assert_not_called") okay = count == 0;
                else if (n == "assert_any_call") {
                    V want = call_record(a); okay = false;
                    for (auto& call : self->calls.items()) if (py_eq(call, want)) { okay = true; break; }
                } else {
                    okay = count && py_eq(self->calls.items().back(), call_record(a));
                    if (n == "assert_called_once_with") okay = okay && count == 1;
                }
                if (!okay) throw PyError("AssertionError", n + " failed; observed " + std::to_string(count) + " calls");
                return V::none();
            });
        if (n.rfind("assert", 0) == 0) throw PyError("AttributeError", "Unsupported mock assertion: " + n);
        if (!spec.is_none() && !pvz::hasattr(spec, name)) throw PyError("AttributeError", "Mock spec has no attribute " + n);
        V child = make_child();
        if (magic && (n == "__exit__" || n == "__aexit__")) as<MockObject>(child)->result = V(false);
        dyn.emplace_back(name, child); return child;
    }
};
V make_mock(const Args& a, bool magic = false) {
    auto mock = std::make_shared<MockObject>(); mock->magic = magic;
    if (!a.pos.empty()) mock->spec = a.pos[0];
    for (auto& [key, value] : a.kw) {
        if (key == Sym("wraps")) mock->wraps = value;
        else if (key == Sym("spec")) mock->spec = value;
        else if (key == Sym("spec_set")) { mock->spec = value; mock->spec_set = !value.is_none() && value.truthy(); }
        else if (key == Sym("name") || key == Sym("unsafe")) continue;
        else mock->setattr(key, value);
    }
    return V::inst(mock);
}

struct AttributePatch : PyObj {
    V target, replacement, saved;
    Sym name;
    enum Kind { SLOT, DYNAMIC, PROPERTY, MAPPING, FUNCTION, MODULE } kind = DYNAMIC;
    bool existed = false, local = false, create = false, active = false, inject = false;
    const char* type_name() const override { return "_patch_object"; }
    V start() {
        if (active) throw PyError("RuntimeError", "patch already active");
        existed = pvz::hasattr(target, name);
        if (!existed && !create) throw PyError("AttributeError", "Patch target has no attribute " + name.str());
        if (existed) saved = pvz::getattr(target, name);
        if (target.t == V::INST) {
            PyObj* object = target.box->inst.get();
            if (as<pg::Module>(target)) { kind = MODULE; local = existed; }
            else if (V* slot = object->slot(name)) { kind = SLOT; local = slot->has(); if (local) saved = *slot; }
            else { kind = DYNAMIC; local = object->find_dyn(name) != nullptr; }
        } else if (target.t == V::DICT || target.t == V::OBJ) { kind = MAPPING; local = existed; }
        else if (target.t == V::FUNC) { kind = FUNCTION; local = existed; }
        else throw PyError("TypeError", "Patch requires an attribute-bearing target");
        pvz::setattr(target, name, replacement);
        if (target.t == V::INST && kind == DYNAMIC && !target.box->inst->find_dyn(name)) kind = PROPERTY;
        active = true; return replacement;
    }
    V stop() {
        if (!active) return V(false);
        if (kind == PROPERTY || local) pvz::setattr(target, name, saved);
        else if (kind == MODULE) {
            auto& attrs = as<pg::Module>(target)->attrs;
            attrs.erase(std::remove_if(attrs.begin(), attrs.end(), [&](auto& item) { return item.first == name; }), attrs.end());
        } else if (kind == SLOT) target.box->inst->slot(name)->del();
        else if (kind == DYNAMIC) py::delattr(target, name);
        else if (kind == MAPPING) py_del(target, V(name));
        else {
            auto& attrs = target.box->fattrs;
            attrs.erase(std::remove_if(attrs.begin(), attrs.end(), [&](auto& item) { return item.first == name; }), attrs.end());
        }
        active = false; return V(false);
    }
    V method(Sym n) override {
        auto self = std::static_pointer_cast<AttributePatch>(shared_from_this());
        if (n == Sym("start") || n == Sym("__enter__")) return V::func([self](const Args&) { return self->start(); });
        if (n == Sym("stop") || n == Sym("__exit__")) return V::func([self](const Args&) { return self->stop(); });
        return V();
    }
    V call_self(const Args& a) override {
        auto self = std::static_pointer_cast<AttributePatch>(shared_from_this()); V function = a.pos.at(0);
        return V::func([self, function](const Args& args) {
            V mock = self->start(); Args bound = args; if (self->inject) bound.pos.push_back(mock);
            try { V result = function.call(bound); self->stop(); return result; }
            catch (...) { self->stop(); throw; }
        });
    }
};
V object_patch(const Args& a) {
    auto patch = std::make_shared<AttributePatch>();
    patch->target = a.pos.at(0); patch->name = a.pos.at(1).sym();
    V explicit_new; bool has_new = a.pos.size() > 2;
    if (has_new) explicit_new = a.pos[2];
    Args mock_args;
    for (auto& [key, value] : a.kw) {
        if (key == Sym("new")) { explicit_new = value; has_new = true; }
        else if (key == Sym("create")) patch->create = value.truthy();
        else if (key == Sym("autospec") || key == Sym("new_callable"))
            throw PyError("NotImplementedError", "patch option requires an additional native adapter: " + key.str());
        else mock_args.kw.emplace_back(key, value);
    }
    patch->inject = !has_new || py_is(explicit_new, mock_default());
    patch->replacement = patch->inject ? make_mock(mock_args, true) : explicit_new;
    return V::inst(patch);
}
V dotted_patch(const Args& a) {
    if (a.pos.empty() || !a.pos[0].is_str()) throw PyError("TypeError", "patch requires a dotted target name");
    std::string name = a.pos[0].str(); size_t split = name.rfind('.');
    if (split == std::string::npos) throw PyError("TypeError", "patch target must name a module attribute");
    std::string module_name = name.substr(0, split);
    if (module_name.rfind("modkit.pvp.", 0) == 0) module_name = module_name.substr(7);
    V target;
    if (module_name.rfind("pvp.", 0) == 0) {
        size_t end = module_name.find('.', 4);
        target = py::import_pvp_module(module_name.substr(0, end));
        while (end != std::string::npos) {
            size_t next = module_name.find('.', end + 1);
            target = pvz::getattr(target, Sym(module_name.substr(end + 1, next == std::string::npos ? next : next - end - 1)));
            end = next;
        }
    } else target = py::stdlib_module(V(module_name));
    Args args; args.pos = {target, V(name.substr(split + 1))};
    if (a.pos.size() > 1) args.pos.push_back(a.pos[1]); args.kw = a.kw;
    return object_patch(args);
}
V dict_patch(const Args& a) {
    if(a.pos.empty()) throw PyError("TypeError","patch.dict requires a mapping");
    auto p=std::make_shared<DictPatch>();p->target=a.pos[0];
    if(p->target.is_inst() && std::string(p->target.box->inst->type_name())=="_Environ") p->env=true;
    if(p->target.is_str()) {
        if(p->target.str()=="os.environ") { p->env=true;p->target=py::stdlib_attr(V("os"),V("environ")); }
        else throw PyError("NotImplementedError","patch.dict target "+p->target.str());
    }
    if(!p->env&&!p->target.is_dict()&&!p->target.is_obj()&&!p->target.is_inst())throw PyError("TypeError","patch.dict requires a mapping");
    p->values=a.pos.size()>1?py::dict_of(a.pos[1]):V::dict();
    if(a.pos.size()>2)p->clear=a.pos[2].truthy();
    for(auto& kv:a.kw) {if(kv.first==Sym("clear"))p->clear=kv.second.truthy();else p->values.at(V(kv.first))=kv.second;}
    return V::inst(p);
}
}
void install_relay_fixture();   // relay_fixture.cpp
void install_bytecode_ref();    // bytecode_ref.cpp
void install_graphics_contract();
void install_legacy_fixture();
void install_runtime_contract();
void install_units_probe();
void install_multiworker_fixture();
void install_dart_reference_fixture();
void install_guest_cost_fixture();
void install_test_adapters() {
    install_relay_fixture();
    install_bytecode_ref();
    install_graphics_contract();
    install_legacy_fixture();
    install_runtime_contract();
    install_units_probe();
    install_multiworker_fixture();
    install_dart_reference_fixture();
    install_guest_cost_fixture();
    V mock=pg::new_module("unittest.mock");
    V patch=V::func(dotted_patch);
    patch.box->fattrs.emplace_back(Sym("dict"),V::func(dict_patch));
    patch.box->fattrs.emplace_back(Sym("object"),V::func(object_patch));
    pg::module_of(mock)->add("patch",patch);
    pg::module_of(mock)->fn("Mock",[](const Args& a){return make_mock(a);});
    pg::module_of(mock)->fn("MagicMock",[](const Args& a){return make_mock(a,true);});
    pg::module_of(mock)->fn("AsyncMock",[](const Args&)->V {throw PyError("NotImplementedError","AsyncMock is not implemented by the native adapter");});
    pg::module_of(mock)->fn("call",call_record);
    pg::module_of(mock)->add("DEFAULT",mock_default());
    py::register_module("unittest.mock",mock);
    // CPython's `from unittest import mock` returns the child module.
    V unittest_mod=pg::new_module("unittest");pg::module_of(unittest_mod)->add("mock",mock);py::register_module("unittest",unittest_mod);
}
}
