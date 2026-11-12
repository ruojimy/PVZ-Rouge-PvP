#include "sim/pvp/hand/graphics.h"
#include <map>
// Hand-written replacements: bytecode gates (already present in the translated live regions),
// NativeTargets.install (needs the guard-less original 掉血), and NativeBridge (C++ map generator).
#include "sim/pvp/gen/pm_native_gate.h"
#include "sim/pvp/gen/pm_native_battle.h"
#include "sim/pvp/gen/pm_native_targets.h"
#include "sim/pvp/gen/pm_native_bridge.h"
#include "sim/mapgen.h"
#include "data/datastore.h"
#include "core/resource_paths.h"
#include "core/fsutil.h"
#include "sim/pvp/gen/pm_native_runtime.h"
#include "sim/pvp/gen/pm_patch1501.h"
namespace pvz { void register_original_funcs(Match&); V gated_combat_regions(const V&); }

namespace pvz::pm_native_gate {
// The translated regions (src/sim/gen/regions.cpp) were decompiled from the live, already-gated
// PvP71 code objects, so every gate/predicate replacement is already in place.
V f_replace_predicate(const Args& A) { return A.pos.at(0); }
V f__replace_predicate(const Args& A) { return A.pos.at(0); }
V f_inject_iteration_gate(const Args& A) { return A.pos.at(0); }
}  // namespace pvz::pm_native_gate

namespace pvz::pm_native_battle {
V f__gated_regions(const Args& A) { return pvz::gated_combat_regions(A.pos.at(0)); }
}  // namespace pvz::pm_native_battle

namespace pvz::pm_native_targets {
static const bool target_index_hook = [] {
    py::register_native_hook("run_target_index", [](const Args& a) {
        const V& code = a.pos.at(0);
        if (code.t == V::FUNC) return code.call(Args{});
        // The product always receives a compiled region. The old-suite adapter may bind a
        // verified bytecode fixture to that same real native region; it never replays an oracle.
        V region = py::native_hook(V("test.resolve_unit_target_index"), a);
        return region.call(Args{});
    });
    return true;
}();
V C_NativeTargets::m_install(const Args& A) {
    Match& G = match_of(a_g);
    static const char* names[] = {"掉血", "伤害僵尸", "表面伤害僵尸", "灰烬僵尸", "新增实体"};
    for (auto* n : names)
        if (!G.has_global(V(n))) throw PyError("NativeTargetError", std::string("Missing native target callbacks: ") + n);
    const V* cur = G.find_global(V("_pvp_native_targets"));
    if (cur && cur->has() && !cur->is_none() && !py_is(*cur, self()))
        throw PyError("NativeTargetError", "Native target overlay is already installed");
    if (a_originals.truthy()) return V::none();
    V originals = V::dict();
    for (auto* n : names) originals.at(V(n)) = G.global(V(n));
    a_originals = originals;
    // native_hurt: original 掉血 body without its I-Zombie immunity guard (bytecode 8:92)
    V hurt = rd(originals, V("掉血"));
    Match* Gp = &G;
    a_native_hurt = V::func([Gp, hurt](const Args& a) {
        V saved = Gp->模式;
        Gp->模式 = V("正常模式");
        try { hurt.call(a); } catch (...) { Gp->模式 = saved; throw; }
        Gp->模式 = saved;
        return V::none();
    });
    G.掉血 = method(Sym("_player_damage"));
    G.伤害僵尸 = method(Sym("_zombie_damage"));
    G.表面伤害僵尸 = method(Sym("_surface_damage"));
    G.灰烬僵尸 = method(Sym("_ash_damage"));
    G.新增实体 = method(Sym("_new_entity"));
    // _tag_bypassed_add_entity: projectiles from the stored pre-patch 新增实体 still get allegiance
    const V* stored = G.find_global(V("__pvz_sb_add_entity_original"));
    if (stored && stored->t == V::FUNC && !G.has_global(V("__pvp_tagged_add_installed"))) {
        V original = *stored;
        auto sp = std::static_pointer_cast<C_NativeTargets>(shared_from_this());
        G.global(V("__pvz_sb_add_entity_original")) = V::func([sp, original](const Args& a) {
            return sp->m__tag_added(Args{original, V::tuple(a.pos)});
        });
        G.global(V("__pvp_tagged_add_installed")) = V(true);
    }
    G._pvp_native_targets = self();
    return V::none();
}
}  // namespace pvz::pm_native_targets

namespace pvz::pm_native_bridge {
static V grid_to_v(const GenGrid& g) {
    std::vector<V> rows;
    for (auto& row : g) {
        std::vector<V> cells;
        for (auto& c : row) {
            V d = V::dict();
            d.at(V("方块")) = V(c.方块);
            if (c.has里) d.at(V("里方块")) = V(c.里方块);
            cells.push_back(d);
        }
        rows.push_back(V::list(cells));
    }
    return V::list(rows);
}
static V literals() { return py::data_value("_original_literals", "地图数据").is_dict() ? V() : V(); }

V C_NativeBridge::m___init__(const Args& A) {
    V globals = A.get(0, Sym("game_globals"), nullptr);
    static const V dflt("live-original-runtime");
    a_source = py::str(A.get(1, Sym("source"), &dflt));
    a__globals = globals;
    a__combat_root = V::none();
    a__payload = V::none();
    a__map_function = V::none();
    a__map_data = globals.get(V("地图数据"), V::dict());
    a_generator_revision = V("native-cpp-mapgen-1");
    return V::none();
}

V C_NativeBridge::m_from_marshaled(const Args& A) {
    V globals = V::dict();
    for (const char* k : {"地图数据", "所有秘籍", "介绍秘籍", "所有作战", "所有植物", "参战僵尸图", "花费阳光", "kong", "boss", "介绍植物"}) {
        try { globals.at(V(k)) = py::data_value("_original_literals", k); } catch (...) {}
        if (std::string(k) == "花费阳光") globals.at(V(k)) = py::int_keyed(globals.at(V(k)));
    }
    return new_NativeBridge(Args({globals, V("original-marshal:pvzrouge.pyc")}));
}

// Native equivalents of (code, source, assets): executable C++ binding/factory handles and the
// actual shipped image directory. There is no Python executable or Python-source payload to find.
V C_NativeBridge::m_combat_payload(const Args& A) {
    if (a__payload.has() && !a__payload.is_none()) return a__payload;
    a__payload=pvz::getattr(self(),Sym("_resolve_payload")).call(Args{});
    return a__payload;
}
V C_NativeBridge::m__resolve_payload(const Args& A) {
    V original = V::func([](const Args& a) { register_original_funcs(match_of(a.pos.at(0))); return a.pos[0]; });
    original.box->fattrs.emplace_back(Sym("__name__"), V("register_original_funcs"));
    original.box->fattrs.emplace_back(Sym("__native_original_program__"), V(true));
    V patch = V::func([](const Args&) { return pm_patch1501::load(); });
    patch.box->fattrs.emplace_back(Sym("__name__"), V("compiled_patch1501_factory"));
    patch.box->fattrs.emplace_back(Sym("__native_patch_program__"), V(true));
    a__payload = V::tuple({original, patch, py::path_new(Args{V(p8(native_image_directory()))})});
    return a__payload;
}

// surface(name, ui): a shared Surface of the original atlas. The C++ build serves the baked PNG
// (tools/bake_atlas.py) through the UI's real pygame; without a display module there is none.
V C_NativeBridge::m_surface(const Args& A) {
    V name = A.get(0, Sym("name"), nullptr);
    static const V f(false);
    bool ui = A.get(1, Sym("ui"), &f).truthy();
    if (name.t != V::STR) return V::none();
    std::string file = gfx::atlas_file(ui ? "ui图集" : "图集", name.str());
    if (file.empty()) return V::none();
    static std::map<std::string, V> cache;
    auto it = cache.find(file);
    if (it != cache.end()) return it->second;
    V pygame = py::stdlib_module(V("pygame"));
    V image = pvz::getattr(pygame, Sym("image"), V::none());
    if (image.is_none() || image.t != V::INST) return V::none();
    V surf = callm(callm(image, Sym("load"), Args{V(file)}), Sym("convert_alpha"), Args{});
    cache[file] = surf;
    return surf;
}
V C_NativeBridge::m_atlas_keys(const Args& A) {
    static const V f(false);
    bool ui = A.get(0, Sym("ui"), &f).truthy();
    std::vector<V> out;
    for (auto& k : gfx::atlas_keys(ui ? "ui图集" : "图集")) out.emplace_back(k);
    return V::tuple(out);
}
V C_NativeBridge::m_generate_map(const Args& A) {
    V name = A.get(0, Sym("name"), nullptr);
    V seed = A.get(1, Sym("seed"), nullptr);
    if (!py::in(name, pvz::getattr(self(), Sym("map_names"))))
        throw PyError("NativeBridgeError", "Map is not in the verified original catalogue: " + py_str(name));
    return grid_to_v(generate_original_map(name.str(), int64_t(seed.num())));
}

static PyError literal_error(const std::string& message) { return PyError("NativeBridgeError", message, {"RuntimeError"}); }
static bool literal_declined(const PyError& error) {
    for (const char* type : {"NativeBridgeError", "KeyError", "IndexError", "TypeError", "ValueError"})
        if (error.matches(type)) return true;
    return false;
}
V f__literal_step(const Args& A) {
    V instruction = A.get(0, Sym("instruction"), nullptr), stack = A.get(1, Sym("stack"), nullptr);
    V values = A.get(2, Sym("values"), nullptr), arg = pvz::getattr(instruction, Sym("argval"));
    std::string op = pvz::getattr(instruction, Sym("opname")).str();
    auto pop = [&]() { if (stack.items().empty()) throw PyError("IndexError", "pop from empty list"); V v = stack.items().back(); stack.items().pop_back(); return v; };
    auto take = [&](size_t size) {
        // Python slices clamp at the beginning of the stack.
        size = std::min(size, stack.items().size());
        std::vector<V> result(stack.items().end() - size, stack.items().end());
        stack.items().resize(stack.items().size() - size); return result;
    };
    if (op == "EXTENDED_ARG" || op == "NOP") return V::none();
    if (op == "LOAD_CONST") {
        if (isinstance(arg, "CodeType")) throw literal_error("Code objects are not literal data");
        stack.append(pvz::deepcopy(arg));
    } else if (op == "LOAD_NAME") stack.append(rd(values, arg));
    else if (op == "BUILD_LIST" || op == "BUILD_TUPLE" || op == "BUILD_SET") {
        auto items = take(size_t(arg.num()));
        stack.append(op == "BUILD_TUPLE" ? V::tuple(items) : op == "BUILD_SET" ? V::set(items) : V::list(items));
    } else if (op == "BUILD_MAP") {
        auto items = take(size_t(arg.num()) * 2); V dict = V::dict();
        for (size_t i = 0; i + 1 < items.size(); i += 2) dict.at(items[i]) = items[i + 1];
        stack.append(dict);
    } else if (op == "BUILD_CONST_KEY_MAP") {
        V keys = pop(); auto items = take(size_t(arg.num())); V dict = V::dict();
        for (size_t i = 0; i < std::min(keys.len(), items.size()); ++i) dict.at(keys.idx(int64_t(i))) = items[i];
        stack.append(dict);
    } else if (op == "STORE_NAME" || op == "STORE_GLOBAL") pvz::setitem(values, arg, pop());
    else if (op == "STORE_SUBSCR") { V key = pop(), target = pop(), item = pop(); pvz::setitem(target, key, item); }
    else if (op == "BINARY_ADD") { V right = pop(), left = pop(); stack.append(left + right); }
    else if (op == "UNARY_NEGATIVE") stack.append(-pop());
    else throw literal_error("Nonliteral instruction: " + op);
    return V::none();
}
V f__extract_literal_assignment(const Args& A) {
    V instructions = py::iter_list(A.get(0, Sym("instructions"), nullptr)), target = A.get(1, Sym("target"), nullptr);
    V known = A.get(2, Sym("known"), nullptr);
    for (size_t end = 0; end < instructions.len(); ++end) {
        V ins = instructions.idx(int64_t(end)); std::string op = pvz::getattr(ins, Sym("opname")).str();
        if ((op != "STORE_NAME" && op != "STORE_GLOBAL") || pvz::getattr(ins, Sym("argval")) != target) continue;
        int64_t start = int64_t(end) - 1;
        while (start >= 0) {
            std::string previous = pvz::getattr(instructions.idx(start), Sym("opname")).str();
            if (previous == "STORE_NAME" || previous == "STORE_GLOBAL" || previous == "STORE_SUBSCR" ||
                previous == "POP_TOP" || previous == "RETURN_VALUE" || previous == "GET_ITER" ||
                previous == "FOR_ITER" || previous.find("JUMP") != std::string::npos) break;
            --start;
        }
        V stack = V::list(), values = py::dict_of(known);
        try {
            for (size_t part = size_t(start + 1); part <= end; ++part)
                f__literal_step(Args{instructions.idx(int64_t(part)), stack, values});
            if (values.contains(target) && !stack.len()) return rd(values, target);
        } catch (const PyError& e) { if (!literal_declined(e)) throw; }
    }
    return V::none();
}
V f__extract_literal_dictionary(const Args& A) {
    V instructions = py::iter_list(A.get(0, Sym("instructions"), nullptr)), target = A.get(1, Sym("target"), nullptr);
    V known = A.get(2, Sym("known"), nullptr);
    for (size_t end = 1; end < instructions.len(); ++end) {
        V ins = instructions.idx(int64_t(end)), previous = instructions.idx(int64_t(end - 1));
        std::string op = pvz::getattr(ins, Sym("opname")).str();
        if ((op != "STORE_NAME" && op != "STORE_GLOBAL") || pvz::getattr(ins, Sym("argval")) != target ||
            pvz::getattr(previous, Sym("opname")) != V("BUILD_MAP") || pvz::getattr(previous, Sym("argval")) != V(0.0)) continue;
        V stack = V::list(), values = pvz::deepcopy(known);
        for (size_t part = end - 1; part < instructions.len(); ++part) {
            try { f__literal_step(Args{instructions.idx(int64_t(part)), stack, values}); }
            catch (const PyError& e) { if (!literal_declined(e)) throw; break; }
        }
        V found = values.get(target, V::none()); if (found.t == V::DICT) return found;
    }
    return V::none();
}
V f__extract_secret_text(const Args& A) {
    V instructions = py::iter_list(A.get(0, Sym("instructions"), nullptr)), names = A.get(1, Sym("names"), nullptr);
    std::vector<V> plain;
    for (auto& ins : instructions.items()) if (pvz::getattr(ins, Sym("opname")) != V("EXTENDED_ARG")) plain.push_back(ins);
    V result = V::dict();
    for (size_t i = 0; i + 6 < plain.size(); ++i) {
        auto op = [&](size_t n) { return pvz::getattr(plain[i + n], Sym("opname")); };
        auto arg = [&](size_t n) { return pvz::getattr(plain[i + n], Sym("argval")); };
        if (op(0) == V("LOAD_NAME") && arg(0) == V("mj") && op(1) == V("LOAD_CONST") && names.contains(arg(1)) &&
            op(2) == V("COMPARE_OP") && arg(2) == V("==") && op(3) == V("POP_JUMP_IF_FALSE") &&
            op(4) == V("LOAD_CONST") && arg(4).t == V::STR && op(5) == V("STORE_NAME") && arg(5) == V("zi")) result.at(arg(1)) = arg(4);
    }
    return result;
}
}  // namespace pvz::pm_native_bridge

#include "sim/pvp/gen/pm_native_scale.h"
namespace pvz::pm_native_scale {
// Baked atlas inputs retain their original pre-scale pixels under private asset
// keys. Recompute factors and the measured painted-row drop for each match.
// Default assets stay byte-identical; non-default scales use the original
// native_scale.shrink body and real linked SDL pixels, never an upscaled bake.
V f_install(const Args& A) {
    V g=A.pos.at(0),pg=A.pos.at(1),atlas=rd(g,V("图集")),tile=rd(g,V("比"));
    FACTOR.kv().clear();LIFT.kv().clear();
    const auto& baked=data::module("runtime_facts").at("native_scale_FACTOR");
    bool pixels=py::has_native_hook("graphics.materialize_image");
    auto input=[&](const V& key){std::string source="@native-scale-source/"+key.str(),file=gfx::atlas_file("图集",source);if(file.empty())throw PyError("NativeGraphicsError","Missing original pre-scale atlas input: "+key.str());V dims=callm(rd(atlas,key),Sym("get_size"),Args{});return gfx::make_image("world:"+source,int(dims.idx(0).num()),int(dims.idx(1).num()));};
    auto named_pixels=[&](const V& key,const V& surface){int w=int(callm(surface,Sym("get_width"),Args{}).num()),h=int(callm(surface,Sym("get_height"),Args{}).num());V image=gfx::make_image("world:"+key.str(),w,h);image.box->inst->setattr(Sym("__materialized_pixels__"),surface);return image;};
    bool changed=false;
    for(const auto& item:py::items_vec(SCALE_TILES)) {
        V unit=item.first,tiles=item.second;FACTOR.at(unit)=tiles/ZOMBIE_CELL_TILES;
        V current=py::m_get(atlas,unit);if(current.is_none())continue;
        V original=input(unit),top_before=f_painted_top(Args{original});
        double wanted=(tiles*tile/callm(original,Sym("get_height"),Args{})).num();
        bool use_baked=baked.contains(unit.str()) && FACTOR.at(unit)==V(baked.at(unit.str()).get<double>());
        if(!use_baked) {
            if(!pixels)throw PyError("NotImplementedError","Non-default native art scaling requires the linked pixel backend");
            V keys=f_family(Args{atlas,unit});
            for(const V& key:keys.items()) {
                V raw=py::native_hook("graphics.materialize_image",Args{callm(input(key),Sym("describe"),Args{})});
                V scaled=wanted<1.?f_shrink(Args{pg,raw,V(wanted)}):callm(raw,Sym("copy"),Args{});
                pvz::setitem(atlas,key,named_pixels(key,scaled));
            }
            changed=true;
        }
        V top_after=f_painted_top(Args{rd(atlas,unit)});
        if(wanted<1. && !top_before.is_none() && !top_after.is_none())LIFT.at(unit)=top_after-top_before;
    }
    if(changed)for(const char* armour:{"路障","铁桶","橄榄球头盔","黑路障","黑铁桶","黑橄榄球头盔"})for(const V& state:STATES.items()) {
        V key=V(armour)+state;if(!atlas.contains(key))continue;
        V raw=rd(atlas,key);if(gfx::image_of(raw))raw=py::native_hook("graphics.materialize_image",Args{callm(raw,Sym("describe"),Args{})});
        V worn=f_shrink(Args{pg,raw,f_factor(Args{V("小鬼僵尸")})}),name=V("小鬼僵尸-")+key;
        pvz::setitem(atlas,name,named_pixels(name,worn));
    }
    return V::none();
}
}  // namespace pvz::pm_native_scale

#include "sim/pvp/gen/pm_native_protection.h"
namespace pvz::pm_native_protection {
// The damage-expression rewrite of the four patch functions is applied to the patch source before
// translation (tools/pvp2cpp.py protect_patch_damage); region edits are already in the live regions.
V f_replace_damage_write(const Args& A) { return A.pos.at(0); }
V f__patch_damage_code(const Args& A) { return V::none(); }
V C_NativeProtection::m___init__(const Args& A) {
    V battle = A.get(0, Sym("battle"), nullptr);
    a_b = battle;
    V rules = pvz::getattr(battle, Sym("rules"));
    a_until = py::round(V(rd(rules, V("producer_protection_seconds")).num() * 250.0));
    a_factor = py::float_(rd(rules, V("producer_protection_multiplier")));
    V amount = method(Sym("amount"));
    pvz::setitem(pvz::getattr(battle, Sym("g")), V("_pvp_damage_amount"), amount);
    pvz::setitem(pvz::getattr(pvz::getattr(battle, Sym("patch")), Sym("ns")), V("_pvp_damage_amount"), amount);
    return V::none();
}
}  // namespace pvz::pm_native_protection

namespace pvz::pm_native_targets {
// HeroProxy (a dict subclass in python): a native zombie record for a Dave, intercepting the
// original code's direct writes to 血量 / 灰烬 / 冰冻 / 黄油 / 眩晕 and conversion keys.
struct HeroProxyHook : Obj::Hook {
    V controller, side;
    const char* type_name() const override { return "HeroProxy"; }
    static const char* state_key(const V& key) {
        if (key.t != V::STR) return nullptr;
        if (key == SV("冰冻")) return "_pvp_ice";
        if (key == SV("黄油")) return "_pvp_butter";
        if (key == SV("眩晕")) return "_pvp_stun";
        return nullptr;
    }
    void sync(Obj& o) {
        V avatar = rd(pvz::getattr(controller, SY("heroes")), side);
        o.slot(SV("冰冻")) = avatar.get(SV("_pvp_ice"), V(0.0));
        o.slot(SV("黄油")) = avatar.get(SV("_pvp_butter"), V(0.0));
        o.slot(SV("眩晕")) = avatar.get(SV("_pvp_stun"), V(0.0));
        o.slot(SV("血量")) = V(std::max(0., rd(avatar, SV("玩家血量")).num()) * 1.0);
        o.slot(SV("位置")) = rd(avatar, SV("玩家位置"));
        o.slot(SV("方向")) = avatar.get(SV("玩家方向"), V(1.0));
    }
    bool set(Obj& o, const V& key, const V& value) override {
        if (const char* sk = state_key(key)) {
            if (callm(controller, SY("owner"), Args{}) != side) {
                V v = py::max(V(0.0), value);
                setitem(rd(pvz::getattr(controller, SY("heroes")), side), V(sk), v);
                o.slot(key) = v;
            }
            return true;
        }
        if (key == SV("血量")) {
            V old = o.slot(key);
            if (value < old) {
                V kind = value <= V(-1024.0) ? SV("swallow") : pvz::getattr(controller, SY("damage_kind"));
                callm(controller, SY("damage_hero"), Args{side, V((old.num() - value.num()) / 1.0), kind});
                sync(o);
            }
            return true;
        }
        if (key == SV("灰烬")) {
            callm(controller, SY("damage_hero"), Args{side, V(40.0), SV("ash")});
            sync(o);
            return true;
        }
        static const V conversions[] = {V("魅惑"), V("灰烬"), V("死亡"), V("消亡"), V("出土"), V("僵尸"), V("大小"), V("防具"), V("防具血量"), V("手持"), V("手持血量")};
        for (auto& c : conversions) if (key == c) return true;
        return false;   // ordinary dict write
    }
    bool getattr(Obj&, Sym name, V& out) override {
        if (name == SY("controller")) { out = controller; return true; }
        if (name == SY("side")) { out = side; return true; }
        return false;
    }
    bool call(Obj& o, const V& self_v, Sym name, const Args& a, V& out) override {
        if (name == SY("sync")) { sync(o); out = V::none(); return true; }
        if (name == SY("update")) {
            V d = a.pos.empty() ? V::dict() : py::dict_of(a.pos[0]);
            for (auto& p : a.kw) d.at(V(p.first)) = p.second;
            for (auto& p : d.kv()) setitem(self_v, p.first, p.second);
            out = V::none();
            return true;
        }
        return false;
    }
};
V new_HeroProxy(const Args& A) {
    V tmpl = A.get(0, Sym("template"), nullptr);
    V v = V::obj();
    Obj* o = v.o();
    if (tmpl.is_obj()) tmpl.o()->each([&](const V& k, const V& x) { o->slot(k) = x; });
    else for (auto& p : tmpl.kv()) o->slot(p.first) = p.second;
    auto hook = std::make_shared<HeroProxyHook>();
    hook->controller = A.get(1, Sym("controller"), nullptr);
    hook->side = A.get(2, Sym("side"), nullptr);
    V team = py::startswith(hook->side, V("plant")) ? V("plant") : V("zombie");
    o->slot(V("_pvp_hero")) = hook->side;
    o->slot(V("_pvp_owner")) = team;
    o->slot(V("_pvp_id")) = V("hero:") + hook->side;
    o->slot(V("出场")) = V(500.0);
    o->slot(V("防具")) = V("");
    o->slot(V("防具血量")) = V(0.0);
    o->slot(V("手持")) = V("");
    o->slot(V("手持血量")) = V(0.0);
    hook->sync(*o);
    o->hook = hook;
    return v;
}
V cls_HeroProxy() { static V c = V::func([](const Args& A) { return new_HeroProxy(A); }); return c; }
}  // namespace pvz::pm_native_targets
