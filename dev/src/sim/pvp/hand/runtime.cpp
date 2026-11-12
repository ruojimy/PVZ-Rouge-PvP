#include "sim/pvp/hand/original_namespace.h"
#include <exception>
#include <algorithm>
// Hand-written replacements for the parts of pvp/native_runtime.py, native_physics.py and
// native_animation.py that build or execute original bytecode (exec / code slicing).
#include "sim/pvp/gen/pm_native_runtime.h"
#include "sim/pvp/gen/pm_native_physics.h"
#include "sim/pvp/gen/pm_native_animation.h"
#include "sim/pvp/gen/pm_native_flood.h"
#include "sim/pvp/gen/pm_native_status.h"
#include "sim/pvp/gen/pm_patch1501.h"
#include "sim/pvp/gen/pm_original_patch1501.h"
#include "sim/pvp/hand/original_patch_fingerprint.h"
#include "sim/pvp/hand/graphics.h"
#include "sim/pvp/hand/runtime_probe.h"
#include "data/datastore.h"
#include <unordered_set>
#include <set>
#include <cstring>
#include <cstdio>
#include <cstdlib>

namespace pvz {
#include "sim/pvp/hand/menu_callback.inc"
static NativePhysicsResultProbe physics_result_probe = nullptr;
void set_native_physics_result_probe(NativePhysicsResultProbe probe) { physics_result_probe = probe; }
// generated (src/sim/gen)
void register_original_funcs(Match& G);
// Original C++ functions bound to a caller-owned dictionary. This adapts the
// namespace representation; every call executes a real registered C++ body.
namespace {
struct OriginalDictEnvironment final : PyObj {
    V globals,originals=V::dict();
    Match state;
    int depth=0;
    const char* type_name()const override{return "CompiledOriginalNamespace";}
    void import_values(){
        std::vector<V> gone;state.each_present([&](const V& name){if(!globals.find(name))gone.push_back(name);});
        for(const V& name:gone)state.global(name).del();
        for(const auto& entry:globals.kv())if(entry.first.t==V::STR && entry.first!=V("__builtins__"))state.global(entry.first)=entry.second;
        state.rng_p=py::random_of(state.random);if(!state.rng_p)state.rng_p=&state.own_rng;
    }
    void export_values(){
        std::vector<V> gone;
        for(const auto& entry:globals.kv())if(entry.first.t==V::STR && entry.first!=V("__builtins__") && !state.has_global(entry.first))gone.push_back(entry.first);
        for(const V& name:gone)py_del(globals,name);
        state.each_present([&](const V& name){if(name!=V("__self_ns"))globals.at(name)=*state.find_global(name);});
    }
    V invoke(const std::function<V(Match&)>& body){
        bool outer=depth==0;if(outer)import_values();++depth;
        V result;std::exception_ptr failure;
        try{result=body(state);}catch(...){failure=std::current_exception();}
        --depth;if(outer)export_values();
        if(failure)std::rethrow_exception(failure);return result;
    }
};
std::shared_ptr<OriginalDictEnvironment> original_dict_environment(const V& mapping,bool create){
    if(mapping.t!=V::DICT){if(create)throw PyError("TypeError","Compiled original namespace requires a dictionary");return {};}
    for(auto& field:mapping.box->fattrs)if(field.first==Sym("__compiled_original_namespace__")){
        auto owner=field.second.t==V::INST?std::dynamic_pointer_cast<OriginalDictEnvironment>(field.second.box->inst):nullptr;
        if(owner && owner->globals.box.get()==mapping.box.get())return owner;
    }
    if(!create)return {};
    auto owner=std::make_shared<OriginalDictEnvironment>();owner->globals=mapping;register_original_funcs(owner->state);
    owner->state.each_present([&](const V& name){const V* fn=owner->state.find_global(name);if(fn && fn->t==V::FUNC)owner->originals.at(name)=*fn;});
    auto& fields=mapping.box->fattrs;
    fields.erase(std::remove_if(fields.begin(),fields.end(),[](const auto& field){return field.first==Sym("__compiled_original_namespace__");}),fields.end());
    fields.emplace_back(Sym("__compiled_original_namespace__"),V::inst(owner));return owner;
}
}
void mark_compiled_original_namespace(const V& mapping){original_dict_environment(mapping,true);}
bool is_compiled_original_namespace(const V& mapping){return bool(original_dict_environment(mapping,false));}
V bind_compiled_original_function(const V& mapping,const V& name){
    auto owner=original_dict_environment(mapping,true);const V* found=owner->originals.find(name);
    if(!found)throw PyError("NotImplementedError","No compiled original function: "+py_str(name));
    V fn=*found;V bound=V::func([owner,fn](const Args& args){return owner->invoke([&](Match&){return fn.call(args);});});
    bound.box->fattrs.emplace_back(Sym("__name__"),name);bound.box->fattrs.emplace_back(Sym("__native_original_binding__"),V(true));return bound;
}
V invoke_compiled_original_namespace(const V& mapping,const std::function<V(Match&)>& body){return original_dict_environment(mapping,true)->invoke(body);}
void flush_compiled_original_namespace(const V& mapping){original_dict_environment(mapping,true)->export_values();}
void flush_active_compiled_original_namespace(const V& mapping){auto owner=original_dict_environment(mapping,false);if(owner && owner->depth)owner->export_values();}

#define REGION(n) void region_##n(Match& G);
REGION(zombies) REGION(plants) REGION(entities) REGION(plant_maintenance) REGION(particles) REGION(placement)
REGION(coffee) REGION(shovel) REGION(sun_motion) REGION(water_animation) REGION(important_blocks)
REGION(water_ice_clock) REGION(umbrella_player_trigger) REGION(umbrella_player_bounce) REGION(cannon_select)
REGION(cannon_fire) REGION(plant_draw) REGION(unit_target_index) REGION(zombie_coordinates) REGION(zombie_body_index)
REGION(physics_chili_launch) REGION(physics_displacement) REGION(physics_double_jump_clock)
REGION(physics_effect_initialize) REGION(physics_environment_input) REGION(physics_hero_effects)
REGION(physics_hurt_recovery) REGION(physics_hurt_recovery_balloon12) REGION(physics_initialize)
REGION(physics_jump_keydown) REGION(physics_jump_keydown_max1) REGION(physics_jump_keydown_max2)
REGION(physics_jump_keydown_max3) REGION(physics_movement_lean) REGION(physics_pose_reset)
REGION(physics_tracking_bind) REGION(physics_tracking_coordinates) REGION(physics_tracking_initialize)
REGION(physics_tracking_plants) REGION(physics_tracking_player) REGION(physics_tracking_targets)
REGION(dave_draw) REGION(dave_state) REGION(zombies_scripted)
REGION(original_zombies) REGION(original_plants) REGION(original_entities) REGION(original_plant_maintenance)
#undef REGION

// a match namespace that owns its Match
struct OwnedMatchNS : MatchNS {
    std::unique_ptr<Match> own;
};
static V new_match_ns() {
    auto p = std::make_shared<OwnedMatchNS>();
    p->own = std::make_unique<Match>();
    p->G = p->own.get();
    V v = V::inst(p);
    p->G->__self_ns = v;   // (cycle by design: lives as long as the match)
    return v;
}

static V region_fn(Match* G, void (*fn)(Match&)) {
    auto self = std::make_shared<V>();
    V f = V::func([G, fn, self](const Args&) {
        py::push_region_frame(*self, G->__self_ns);
        struct Pop { ~Pop() { py::pop_region_frame(); } } pop_;
        fn(*G);
        return V::none();
    });
    f.box->fattrs.emplace_back(Sym("co_name"), V("<module>"));
    *self = f;   // f_code identity of the region
    return f;
}

// NativeRuntime starts with the original combat loops. NativeBattle explicitly
// requests its compiled PvP gates at the same boundary as Python _gated_regions.
V gated_combat_regions(const V& engine) {
    V source=pvz::getattr(engine,Sym("regions"));
    if(source.t!=V::DICT)throw PyError("TypeError","native region table must be a dictionary");
    for(const auto& attr:source.box->fattrs)if(attr.first==Sym("__native_pvp_gated_regions__") && attr.second.truthy())return source;
    Match& G=match_of(pvz::getattr(engine,Sym("g")));
    V regions=py::copy(source);
#define GATED(n) regions.at(V(#n))=region_fn(&G,&region_##n);
    GATED(zombies) GATED(plants) GATED(entities) GATED(plant_maintenance)
#undef GATED
    G.__region_zombies=rd(regions,V("zombies"));
    G.__region_plants=rd(regions,V("plants"));
    regions.box->fattrs.emplace_back(Sym("__native_pvp_gated_regions__"),V(true));
    return regions;
}

// The zombies region with ScriptedSpawnBudget's four iteration gates (pve / co-op), bound to g.
V scripted_zombies_region(const V& g) {
    Match& G = match_of(g);
    V f = region_fn(&G, &region_zombies_scripted);
    G.__region_zombies = f;   // the replaced code object is what frame inspection sees from now on
    return f;
}

static V json_to_v(const nlohmann::json& j) {
    // same decoding as py::data_value
    if (j.is_null()) return V::none();
    if (j.is_boolean()) return V(j.get<bool>());
    if (j.is_number()) return V(j.get<double>());
    if (j.is_string()) return V(j.get<std::string>());
    if (j.is_array()) { std::vector<V> it; for (auto& x : j) it.push_back(json_to_v(x)); return V::list(it); }
    V d = V::dict();
    for (auto& [k, v] : j.items()) d.at(V(k)) = json_to_v(v);
    return d;
}

V runtime_table_value(const nlohmann::json& value) {
    if (value.is_object()) {
        if (value.contains("@dict")) {
            V result = V::dict();
            for (auto& pair : value.at("@dict")) result.at(runtime_table_value(pair[0])) = runtime_table_value(pair[1]);
            return result;
        }
        const char* tag = value.contains("@tuple") ? "@tuple" : "@set";
        std::vector<V> items; for (auto& item : value.at(tag)) items.push_back(runtime_table_value(item));
        return value.contains("@tuple") ? V::tuple(items) : V::set(items);
    }
    if (value.is_array()) { std::vector<V> items; for (auto& item : value) items.push_back(runtime_table_value(item)); return V::list(items); }
    return json_to_v(value);
}

// periodic-row copy of a list (python PeriodicRow(row))
static V periodic(const V& row) { V l = V::list(py::iter_list(row).items()); l.box->periodic = true; return l; }

static const nlohmann::json& facts() { return data::module("runtime_facts"); }
static bool native_program_tag(const V& value, const char* tag) {
    if (value.t != V::FUNC) return false;
    for (auto& [name, flag] : value.box->fattrs) if (name == Sym(tag) && flag.t == V::BOOL) return flag.truthy();
    return false;
}

}  // namespace pvz

// ======================================================================= native_runtime
namespace pvz::pm_native_runtime {

// regions are bound per match in NativeRuntime.__init__; only the placement query reads this table
// (its exec is replaced by the run_placement_region hook, so the value is a marker)
V f_original_regions(const Args& A) { V d = V::dict(); d.at(V("placement")) = V("<placement region>"); return d; }

V f_load_patch(const Args& A) {
    static const V no_source = V::none();
    V source = A.get(0, Sym("source"), &no_source);
    V ns;
    if(native_program_tag(source,"__native_patch_program__"))ns=source.call(Args{});
    else if(source.t==V::STR){
        V digest=callm(py::stdlib_call(V("hashlib.sha256"),Args{V::bytes(source.str())}),Sym("hexdigest"),Args{});
        if(digest.str()!=original_patch_source_sha256)throw PyError("NotImplementedError","no native translation for supplied original patch source fingerprint");
        ns=pm_original_patch1501::load();
    }else if(source.is_none())ns=pm_patch1501::load();
    else throw PyError("TypeError","expected an original patch source or native program handle");
    setitem(ns, V("__pvz_sb_plant_zombie_test_enabled"), V(false));
    setitem(ns, V("__pvz_sb_log"), V::func([](const Args&) { return V::none(); }));
    return ns;
}

V new_PeriodicRow(const Args& A) { return periodic(A.pos.at(0)); }
V cls_PeriodicRow() { static V c = V::func([](const Args& A) { return new_PeriodicRow(A); }); return c; }
V new_MatchCopy(const Args& A) {
    struct MatchCopyObj : PyObj {
        V module;
        const char* type_name() const override { return "MatchCopy"; }
        V method(Sym name) override { return pvz::getattr(module, name); }
    };
    auto copy = std::make_shared<MatchCopyObj>();
    V module = py::stdlib_module(V("copy"));
    copy->module = A.get(0, Sym("module"), &module);
    return V::inst(copy);
}
V cls_MatchCopy() { static V c = V::func([](const Args& A) { return new_MatchCopy(A); }); return c; }

V C_NativeRuntime::m___init__(const Args& A) {
    V root = A.get(0, Sym("root"), nullptr);
    V terrain = A.get(1, Sym("terrain"), nullptr);
    static const V one(1.0), empty_tuple = V::tuple({});
    V seed = A.get(2, Sym("seed"), &one);
    V secrets = A.get(3, Sym("secrets"), &empty_tuple);
    V pygame = A.get(4, Sym("pygame"), &py_none_v);
    a_root = root;
    a_native_tick = V(0.0);
    a_rng = py::make_random(int64_t(seed.num()));
    a_tile = terrain.get(V("tile_size"), V(48.0));
    a_g = new_match_ns();
    Match& G = match_of(a_g);
    G.rng_p = py::random_of(a_rng);
    // regions bound to this match (python: original_regions(root) + exec(code, g))
    Match* Gp = &G;
    V regions = V::dict();
#define R(n) regions.at(V(#n)) = region_fn(Gp, &region_##n);
#define RAW(n) regions.at(V(#n)) = region_fn(Gp, &region_original_##n);
    RAW(zombies) RAW(plants) RAW(entities) RAW(plant_maintenance) R(particles) R(placement) R(coffee) R(shovel)
    R(sun_motion) R(water_animation) R(important_blocks) R(water_ice_clock) R(umbrella_player_trigger)
    R(umbrella_player_bounce) R(cannon_select) R(cannon_fire) R(plant_draw) R(unit_target_index)
    R(zombie_coordinates) R(zombie_body_index)
#undef R
#undef RAW
    a_regions = regions;
    G.__region_zombies = rd(regions, V("zombies"));     // f_code identity for sys._getframe emulation
    G.__region_plants = rd(regions, V("plants"));
    // ditu rows: PeriodicRow(dict(deepcopy(cell["native"]), 方块=cell["kind"]))
    std::vector<V> rows;
    for (V tmp1_ = py::iter_list(rd(terrain, V("tiles"))); auto& trow : tmp1_.items()) {
        std::vector<V> cells;
        for (auto& cell : trow.items()) {
            V d = py::dict_of(pvz::deepcopy(cell.get(V("native"), V::dict())));
            d.at(V("方块")) = rd(cell, V("kind"));
            cells.push_back(d);
        }
        rows.push_back(periodic(V::list(cells)));
    }
    V ditu = V::list(rows);
    // Original definitions/unit_tables, before NativeBattle applies its own patches.
    for (auto& [k, v] : data::module("_runtime_static").items()) G.global(V(k)) = runtime_table_value(v);
    G.__name__ = V("pvp_original_match");
    G.copy = new_MatchCopy(Args{});
    G.math = py::stdlib_module(V("math"));
    G.global(V("json")) = py::stdlib_module(V("json"));
    G.global(V("os")) = py::stdlib_module(V("os"));
    G.random = a_rng;
    G.pygame = pygame;
    if (native_program_tag(a_root, "__native_original_program__")) a_root.call(Args{a_g});
    else register_original_funcs(G);
    double tile = a_tile.num();
    double width = rd(terrain, V("width")).num();
    size_t nrows = rows.size(), ncols = rows.empty() ? 0 : rows[0].len();
    auto ones = [&]() { std::vector<V> r; for (size_t y = 0; y < nrows; ++y) { std::vector<V> c(ncols, V(1.0)); r.push_back(V::list(c)); } return V::list(r); };
    V noop = V::func([](const Args&) { return V::none(); });
    V env = terrain.get(V("environment"), V::dict());
    V wl = env.get(V("waterline_row"), V::none());
    G.比 = V(tile); G.bi = V(tile / 810.); G.plk = V(tile / 10000.); G.ditu = ditu;
    G.秘籍 = py::list_it(secrets); G.模式 = V("正常模式"); G.天 = V("白天"); G.tian = V("白天"); G.水 = V("水");
    G.作战 = terrain.get(V("map_id"), V("家院")); G.作战数 = V(1.0); G.boss战 = V(false); G.gaoyu = V(false);
    G.玩家位置 = V::nums({width / 2., 0., 0., 0.}); G.玩家方向 = V(1.0); G.玩家血量 = V(20.0);
    G.玩家受伤 = V(0.0); G.玩家倒地 = V(0.0); G.玩家跳跃 = V(0.0); G.二段跳 = V(0.0); G.玩家恢复 = V(0.0);
    G.玩家皮肤 = V("疯狂戴夫"); G.xx = V(0.0); G.yy = V(0.0); G.dushu = V(0.0); G.sbx = V(-1.0); G.sby = V(-1.0);
    G.选择植物 = V::list(); G.选择僵尸 = V::list(); G.植物 = V::list(); G.僵尸 = V::list(); G.实体 = V::list();
    G.粒子 = V::list(); G.阳光球 = V::list(); G.收集阳光 = V::list(); G.钱币 = V::list(); G.收集钱币 = V::list();
    G.阳光 = V(0.0); G.重要方块 = V::list(); G.人洪水 = ones(); G.植洪水 = ones(); G.人洪水圈 = V::list();
    G.植洪水圈 = V::list(); G.人洪水cd = V(0.0); G.植洪水cd = V(0.0); G.人洪水覆盖 = V(-1.0); G.植洪水覆盖 = V(-1.0);
    { std::vector<V> h(ncols, V(1.0)); G.洪水h = V::list(h); }
    G.摄像机 = V::nums({0, 0}); G.抖屏 = V::nums({0, 0, 0}); G.总宽 = V(1024.0); G.总高 = V(768.0);
    G.同横尸 = V::dict(); G.同竖尸 = V::dict(); G.种植cd = V::dict(); G.cd卡亮 = V::dict(); G.补帧 = V(1.0);
    G.种植 = V(""); G.拿中 = V(""); G.上次种植 = V(""); G.目标植物 = V(-1.0); G.nangua = V::list();
    G.zbspeedmax = V(tile / 10000. * 40); G.speedmax = V(tile / 10000. * 200); G.测试秘籍 = V(""); G.测试僵尸 = V("");
    G.版本 = V("v1.4.8"); G.关 = V(0.0); G.大波 = V(0.0); G.中波 = V(0.0); G.冲锋 = V(0.0); G.最后一波 = V(false);
    G.一大波僵尸 = V(0.0); G.梯子尸数 = V(0.0); G.梯子cd = V(0.0); G.冻水 = V(0.0); G.气球 = V(0.0); G.开车 = V(0.0);
    G.水平面 = wl.is_none() ? V(double(nrows)) : wl;
    G.shui = V(0.0); G.水波 = V(0.0); G.先别追植 = V(false); G.花盆顶 = V::dict();
    G.黑色 = V::tuple({V(50.0), V(50.0), V(50.0)}); G.左上 = V::nums({0, 0});
    G.右下 = V::nums({double(nrows), double(ncols)}); G.雨 = V::list(); G.拿中玉米炮 = V::list(); G.爆币 = V(0.0);
    G.播音 = noop; G.停音 = noop; G.沉浸播音 = noop; G.增加需要梯子 = noop;
    a_physics = pm_native_physics::new_NativePhysics(Args({root, a_g}, {{Sym("periodic"), V(true)}}));
    if (env.get(V("night"), V(false)).truthy()) { G.天 = V("黑天"); G.tian = V("黑天"); }
    bool rain = env.get(V("weather"), V::none()) == V("rain");
    G.雨天 = V(rain); G.yu = V(rain);
    callm(a_physics, Sym("initialize_tracking"), Args{});
    for (V* key : {&G.人洪水, &G.植洪水}) {
        if (key->is_list()) {
            std::vector<V> r;
            for (auto& row : key->items()) r.push_back(row.box && row.box->periodic ? row : periodic(row));
            *key = V::list(r);
        }
    }
    G.洪水 = V::list({G.人洪水, G.植洪水});
    // 出界 / 不封顶出界 / 实体出界: original(y, 0)
    for (V* fn : {&G.出界, &G.不封顶出界, &G.实体出界}) {
        V original = *fn;
        *fn = V::func([original](const Args& a) { return original.call(Args{a.pos.at(0), V(0.0)}); });
    }
    return V::none();
}

V C_NativeRuntime::m_execute(const Args& A) {
    V name = A.get(0, Sym("name"), nullptr);
    return rd(a_regions, name).call(Args{});
}

V C_NativeRuntime::m__install_periodic_bounds(const Args& A) { return V::none(); }

}  // namespace pvz::pm_native_runtime

// ======================================================================= native_physics
namespace pvz::pm_native_physics {

// ---- CPython 3.8 bytecode tooling (python: native_physics._instruction / slice_original), ported line by line.
// Only meaningful for a CPython code object (dis / code.replace come from the runtime that provides one: the
// old-suite harness); the game never calls these.
static PyError physics_error(const std::string& msg) { return PyError("NativePhysicsError", msg, {"RuntimeError"}); }
static int opcode_of(const char* name) { return int(rd(py::stdlib_attr(V("dis"), V("opmap")), V(name)).num()); }
static std::string encode_instruction(const std::string& opname, int64_t argument) {
    std::vector<int> parts{int(argument & 255)};
    while (argument > 255) { argument >>= 8; parts.insert(parts.begin(), int(argument & 255)); }
    std::string out;
    for (size_t i = 0; i + 1 < parts.size(); ++i) { out += char(opcode_of("EXTENDED_ARG")); out += char(parts[i]); }
    out += char(opcode_of(opname.c_str())); out += char(parts.back());
    return out;
}
V f__instruction(const Args& A) {
    static const V zero(0.0);
    return V::bytes(encode_instruction(A.get(0, Sym("opname"), nullptr).str(), int64_t(A.get(1, Sym("argument"), &zero).num())));
}
V f_slice_original(const Args& A) {
    V code = A.get(0, Sym("code"), nullptr);
    int64_t start = int64_t(A.get(1, Sym("start"), nullptr).num()), end = int64_t(A.get(2, Sym("end"), nullptr).num());
    static const V none = V::none();
    V replacements = A.get(3, Sym("replacements"), &none), given = A.get(4, Sym("_instructions"), &none);
    if (!isinstance(code, "CodeType") || int64_t(py::bytes_data(pvz::getattr(code, Sym("co_code"))).size()) < end + 6)
        throw physics_error("Original code region is unavailable");
    V instructions = given.is_none() ? py::iter_list(py::stdlib_call(V("dis.get_instructions"), Args{code})) : py::iter_list(given);
    auto& ins = instructions.items();
    std::set<int64_t> offsets;
    for (auto& i : ins) offsets.insert(int64_t(pvz::getattr(i, Sym("offset")).num()));
    if (!offsets.count(start) || !offsets.count(end) || start >= end) throw physics_error("Region is not aligned to original instructions");
    for (size_t j = 1; j < ins.size(); ++j) {
        int64_t off = int64_t(pvz::getattr(ins[j], Sym("offset")).num());
        if ((off == start || off == end) && pvz::getattr(ins[j - 1], Sym("opname")).str() == "EXTENDED_ARG")
            throw physics_error("Region cuts an original EXTENDED_ARG operand");
    }
    V jumps = V::list({});
    V absolute_jumps = py::iter_list(py::stdlib_attr(V("dis"), V("hasjabs")));
    V relative_jumps = py::iter_list(py::stdlib_attr(V("dis"), V("hasjrel")));
    for (auto& x : absolute_jumps.items()) jumps.append(x);
    for (auto& x : relative_jumps.items()) jumps.append(x);
    for (auto& i : ins) {
        int64_t off = int64_t(pvz::getattr(i, Sym("offset")).num());
        if (start <= off && off < end && jumps.contains(pvz::getattr(i, Sym("opcode")))) {
            int64_t target = int64_t(pvz::getattr(i, Sym("argval")).num());
            if (!(start <= target && target <= end))
                throw physics_error("Original branch escapes region: " + std::to_string(off) + " -> " + std::to_string(target));
        }
    }
    std::string result = py::bytes_data(pvz::getattr(code, Sym("co_code")));
    if (start) {
        std::string entry = encode_instruction("JUMP_ABSOLUTE", start);
        if (int64_t(entry.size()) > start) throw physics_error("No space for entry trampoline");
        result.replace(0, entry.size(), entry);
    }
    V replacement_dict = replacements.is_none() ? V::dict() : py::dict_of(replacements);
    for (auto& [k, v] : replacement_dict.kv()) {
        int64_t offset = int64_t(k.num()); std::string value = py::bytes_data(v);
        if (offset < start || offset + int64_t(value.size()) > end) throw physics_error("Replacement is outside the approved region");
        result.replace(size_t(offset), value.size(), value);
    }
    std::vector<V> constants = py::iter_list(pvz::getattr(code, Sym("co_consts"))).items();
    size_t none_index = constants.size();
    for (size_t i = 0; i < constants.size(); ++i) if (constants[i].is_none()) { none_index = i; break; }
    if (none_index == constants.size()) constants.push_back(V::none());
    std::string exit_code = encode_instruction("LOAD_CONST", int64_t(none_index)) + encode_instruction("RETURN_VALUE", 0);
    result.replace(size_t(end), exit_code.size(), exit_code);
    return callm(code, Sym("replace"), Args({}, {{Sym("co_code"), V::bytes(result)}, {Sym("co_consts"), V::tuple(constants)}}));
}
V f__int_const_index(const Args& A) { return PVZ_TODO("_int_const_index"); }
V f_flood_step(const Args& A) { return V::func([](const Args& a) { return pm_native_flood::f_advance(a); }); }
V f__capture_displacement(const Args& A) { return PVZ_TODO("_capture_displacement"); }
V f__periodic_out(const Args& A) { return PVZ_TODO("_periodic_out"); }
V f__periodic_open_top(const Args& A) { return PVZ_TODO("_periodic_open_top"); }

// Caller-owned plain dict (python: NativePhysics(root, isolated_world_namespace) where the dict IS the world's
// globals and the caller keeps reading / writing it). The native world state lives in a Match, so in this mode
// the dict is imported before every region run / avatar selection and the Match exported back afterwards.
// Containers are the same objects on both sides (aliases survive); only the names python's NativePhysics would
// put into the dict are exported (not the extra original functions the native registry installs).
static const char* const kPhysicsFunctions[] = {"位移处理", "无墙位移处理", "出界", "不封顶出界", "c", "jdz", "随", "抖"};
static void caller_import(PyObj* self, const V& g) {
    V* u = self->find_dyn(Sym("__native_caller_ns"));
    if (!u) return;
    Match& G = match_of(g);
    for (auto& [k, v] : u->kv()) if (v.has() && k.t == V::STR && k.str() != "__builtins__") G.global(k) = v;
}
static void caller_export(PyObj* self, const V& g) {
    V* u = self->find_dyn(Sym("__native_caller_ns"));
    if (!u) return;
    V* hidden = self->find_dyn(Sym("__native_hidden_names"));
    Match& G = match_of(g);
    G.each_present([&](const V& k) {
        if (hidden && hidden->contains(k)) return;
        const V* v = G.find_global(k);
        if (v && v->has()) u->at(k) = *v;
    });
    std::vector<V> gone;   // names a region / _restore deleted (every caller name was imported into the Match)
    for (auto& [k, v] : u->kv()) {
        if (k.t != V::STR || k.str() == "__builtins__") continue;
        const V* cur = G.find_global(k);
        if (!cur || !cur->has()) gone.push_back(k);
    }
    for (auto& k : gone) py_del(*u, k);
}
// The original I-Zombie operand restores the jump count to one. The default product uses the
// patched count of two; explicitly requesting the original behavior must run the original branch.
static V original_jump_region(Match* G, double limit) {
    return V::func([G, limit](const Args&) {
        if (attr(G->event, V("type")) == G->pygame_attr(V("KEYDOWN")) &&
            attr(G->event, V("key")) == G->跳跃 && G->玩家倒地 == V(0.0) &&
            G->玩家跳跃 < V(limit) && G->二段跳 == V(0.0)) {
            G->玩家跳跃 += V(1.0);
            if (G->玩家跳跃 == V(2.0)) {
                G->二段跳 = V(1.0);
                wr(G->玩家位置, V(2.0)) += G->玩家方向 * G->plk * V(200.0);
                if (G->模式 == V("我是僵尸")) G->玩家跳跃 = V(1.0);
            }
            wr(G->玩家位置, V(3.0)) = -G->plk * V(380.0);
        }
        return V::none();
    });
}
// worlds whose region is running right now: foreign code called from inside the region (a CPython reference
// function the caller put into its dict) must see the dict as python would - hooks native_world_flush/_reload
static std::vector<std::pair<PyObj*, V>>& active_worlds() { static std::vector<std::pair<PyObj*, V>> a; return a; }
struct CallerSync {
    PyObj* self; V g; bool out, pushed = false;
    CallerSync(PyObj* s, const V& gv, bool in, bool o) : self(s), g(gv), out(o) {
        if (in) caller_import(self, g);
        if (o && self->find_dyn(Sym("__native_caller_ns"))) { active_worlds().emplace_back(self, g); pushed = true; }
    }
    ~CallerSync() {
        if (pushed) active_worlds().pop_back();
        if (out) try { caller_export(self, g); } catch (...) {}
    }
};
static const bool world_hooks_ = [] {
    py::register_native_hook("native_world_flush", [](const Args&) { for (auto& [s, g] : active_worlds()) caller_export(s, g); return V::none(); });
    py::register_native_hook("native_world_reload", [](const Args&) { for (auto& [s, g] : active_worlds()) caller_import(s, g); return V::none(); });
    return true;
}();

V C_NativePhysics::m___init__(const Args& A) {
    a_root = A.get(0, Sym("root_code"), nullptr);
    a_g = A.get(1, Sym("isolated_world_namespace"), nullptr);
    if (a_g.t == V::DICT) {
        V caller = a_g;
        V ns = new_match_ns();
        Match& M = match_of(ns);
        // python installs exactly FUNCTIONS into the caller's dict; the native registry binds all originals to this
        // Match, so drop the others (a present 播音 / 增粒子 would also suppress _select's no-op hooks)
        register_original_funcs(M);
        std::vector<V> extra, hidden;
        M.each_present([&](const V& k) {
            if (k.str().rfind("__", 0) == 0) { hidden.push_back(k); return; }   // native bookkeeping (__self_ns ...)
            for (const char* f : kPhysicsFunctions) if (k.str() == f) return;
            extra.push_back(k);
        });
        for (auto& k : extra) M.global(k).del();
        dyn.emplace_back(Sym("__native_caller_ns"), caller);
        dyn.emplace_back(Sym("__native_hidden_names"), V::set(hidden));   // never exported to the caller's dict
        if (auto* ns_obj = as<MatchNS>(ns)) { ns_obj->mirror = caller; ns_obj->mirror_hidden = V::set(hidden); }
        // python: g.setdefault("copy", copy); g.setdefault("random", random.Random(0)) (kong / 同横尸 / 同竖尸 below)
        if (!caller.find(V("copy"))) caller.at(V("copy")) = py::stdlib_module(V("copy"));
        if (!caller.find(V("random"))) caller.at(V("random")) = py::make_random(0);
        V native_functions=V::dict();for(const char* name:kPhysicsFunctions)native_functions.at(V(name))=M.global(V(name));
        caller_import(this, ns);
        // Original NativePhysics replaces these eight functions even when a
        // caller supplies old bindings. Keep the actual new match-bound bodies.
        for(const auto& entry:native_functions.kv()){M.global(entry.first)=entry.second;caller.at(entry.first)=entry.second;}
        if (PyRandom* r = py::random_of(M.global(V("random")))) M.rng_p = r;
        a_g = ns;
    }
    CallerSync sync_(this, a_g, false, true);
    static const V t(true);
    a_periodic = V(A.get(2, Sym("periodic"), &t).truthy());
    a_geometry_cache = V(true);
    a_flood_geometry_shared = V(true);
    Match& G = match_of(a_g);
    Match* Gp = &G;
    if (!G.kong.has()) G.kong = V::list({V("空"), V("水"), V("花盆块"), V("坟墓"), V("梯子块")});
    if (!G.同横尸.has()) G.同横尸 = V::dict();
    if (!G.同竖尸.has()) G.同竖尸 = V::dict();
    // capture wrapper: 位移处理 records the collision result in __native_landing
    G.__native_displacement = G.位移处理;
    G.位移处理 = V::func([Gp](const Args& a) {
        V r = Gp->__native_displacement.call(a.pos.size() >= 2 ? a : Args{a.pos.at(0), V(1.0)});
        Gp->__native_landing = r;
        return r;
    });
    G.__native_original_out = G.出界;
    G.__native_original_open_top = G.不封顶出界;
    V regions = V::dict();
#define R(n) regions.at(V(#n)) = region_fn(Gp, &region_physics_##n);
    R(initialize) R(effect_initialize) R(displacement) R(environment_input) R(pose_reset) R(chili_launch)
    R(hurt_recovery) R(hurt_recovery_balloon12) R(movement_lean) R(double_jump_clock) R(hero_effects)
    R(jump_keydown) R(jump_keydown_max3) R(jump_keydown_max2) R(jump_keydown_max1) R(tracking_initialize)
    R(tracking_bind) R(tracking_coordinates) R(tracking_player) R(tracking_targets) R(tracking_plants)
#undef R
    static const V no_original(false);
    bool original_infinite = A.get(3, Sym("allow_original_zombie_infinite_jump"), &no_original).truthy();
    if (original_infinite) {
        regions.at(V("jump_keydown")) = original_jump_region(Gp, 2);
        for (int limit : {1, 2, 3})
            regions.at(V("jump_keydown_max" + std::to_string(limit))) = original_jump_region(Gp, limit);
    }
    a_regions = regions;
    a_jump_limit_regions = py_dict({{V(3.0), V("jump_keydown_max3")}, {V(2.0), V("jump_keydown_max2")}, {V(1.0), V("jump_keydown_max1")}});
    a_balloon_regions = py_dict({{V(12.0), V("hurt_recovery_balloon12")}});
    std::vector<V> changed, scratch;
    for (auto& s : facts()["physics_changed_names"]) changed.emplace_back(s.get<std::string>());
    for (auto& s : facts()["physics_tracking_scratch"]) scratch.emplace_back(s.get<std::string>());
    a_changed_names = V::set(changed);
    a_tracking_scratch = V::set(scratch);
    a_patch_offsets = original_infinite ? V::list() : V::list({V(161010.0)});
    a_recovery_patch_offsets = V::list({V(65430.0)});
    a_source_hash = V("6f10bada57913dd51bc4c87900d38ba875841d04febe3daafaeaa2d2f4cdf914");
    return V::none();
}

V C_NativePhysics::m__execute(const Args& A) {
    V region = A.get(0, Sym("region"), nullptr);
    CallerSync sync_(this, a_g, false, true);   // the Match is authoritative inside a call; imported at _select (every public entry)
    if (a_periodic.truthy() && (region == V("tracking_player") || region == V("tracking_plants"))) {
        pm_native_flood::f_advance(Args{a_g, V(region == V("tracking_plants"))});
        return V::none();
    }
    V result = rd(a_regions, region).call(Args{});
    if (physics_result_probe) physics_result_probe(a_g, region);
    return result;
}

V C_NativePhysics::m__select(const Args& A) {
    V state = A.get(0, Sym("state"), nullptr);
    caller_import(this, a_g);
    static const V zero(0.0), f(false);
    V move = A.get(1, Sym("move"), &zero);
    V jump_held = A.get(2, Sym("jump_held"), &f);
    V jump_down = A.get(3, Sym("jump_down"), &f);
    Match& G = match_of(a_g);
    double ratio = G.比.has() ? G.比.num() : 0;
    if (ratio <= 0) throw PyError("NativePhysicsError", "Native tile size 比 must be positive");
    V values = V::dict();
    // state items except 同横尸/同竖尸
    if (state.is_obj()) state.o()->each([&](const V& k, const V& v) { if (k != V("同横尸") && k != V("同竖尸")) values.at(k) = v; });
    else for (auto& p : state.kv()) if (p.first != V("同横尸") && p.first != V("同竖尸")) values.at(p.first) = p.second;
    double mv = move.num();
    V held = py_dict({{V(1.0), V(mv < 0)}, {V(2.0), V(mv > 0)}, {V(3.0), V(jump_held.truthy())}});
    values.at(V("plk")) = V(ratio / 10000.);
    values.at(V("bi")) = V(ratio / 810.);
    values.at(V("左走")) = V(1.0);
    values.at(V("右走")) = V(2.0);
    values.at(V("跳跃")) = V(3.0);
    V key = V::dict();
    key.at(V("get_pressed")) = V::func([held](const Args&) { return held; });
    values.at(V("pygame")) = py_dict({{V("KEYDOWN"), V(1.0)}, {V("key"), key}});
    values.at(V("event")) = py_dict({{V("type"), V(jump_down.truthy() ? 1.0 : 0.0)}, {V("key"), V(3.0)}});
    values.at(V("水")) = V("水");
    values.at(V("__native_landing")) = V(0.0);
    if (!G.播音.has()) values.at(V("播音")) = V::func([](const Args&) { return V::none(); });
    if (!G.增粒子.has()) values.at(V("增粒子")) = V::func([](const Args&) { return V::none(); });
    if (a_periodic.truthy()) {
        values.at(V("ditu")) = new__PeriodicGrid(Args{G.ditu, a_geometry_cache});
        V out = G.__native_original_out, top = G.__native_original_open_top;
        values.at(V("出界")) = V::func([out](const Args& a) { return out.call(Args{a.pos.at(0), V(0.0)}); });
        values.at(V("不封顶出界")) = V::func([top](const Args& a) { return top.call(Args{a.pos.at(0), V(0.0)}); });
    }
    V before = V::dict();
    std::vector<V> names = a_changed_names.items();
    for (auto& p : values.kv()) names.push_back(p.first);
    for (auto& n : names) {
        if (before.find(n)) continue;
        const V* cur = G.find_global(n);
        before.at(n) = (cur && cur->has()) ? *cur : V();   // ABSENT marks "missing"
    }
    for (auto& p : values.kv()) G.global(p.first) = p.second;
    caller_export(this, a_g);   // python's _select writes the selection into the caller's dict itself
    return before;
}

V C_NativePhysics::m__restore(const Args& A) {
    V before = A.get(0, Sym("before"), nullptr);
    Match& G = match_of(a_g);
    for (auto& p : before.kv()) {
        if (!p.second.has() || py_is(p.second, pm_native_physics::_MISSING)) G.global(p.first).del();
        else G.global(p.first) = p.second;
    }
    caller_export(this, a_g);
    return V::none();
}

}  // namespace pvz::pm_native_physics

// ======================================================================= native_animation
namespace pvz::pm_native_animation {

// Real baked source pixels are resolved only when requested. Recording a battle
// does not decode every atlas, and this object never retains a Match pointer.
struct RecordedSources : PyObj {
    V cache=V::dict(),loaded=V::dict();
    const char* type_name() const override { return "dict"; }
    bool isa(const char* c) const override { return !strcmp(c,"dict") || !strcmp(c,"object"); }
    V getitem(const V& key) override {
        if (const V* v=loaded.find(key))return *v;
        if (const V* v=cache.find(key)) return *v;
        V value=callm(py::native_hook("graphics.asset",Args{key}),Sym("copy"),Args{});
        cache.at(key)=value; return value;
    }
    void setitem(const V& key,const V& value) override { cache.at(key)=value; }
    bool contains(const V& key)override {
        if(cache.find(key) || loaded.find(key))return true;if(!key.is_str())return false;
        for(auto entry:{std::pair<const char*,const char*>{"world:","图集"},{"ui:","ui图集"},{"bg:","背景图集"},{"near:","近景图集"}}) {
            const std::string& text=key.str();size_t length=std::strlen(entry.first);
            if(text.compare(0,length,entry.first)==0)return !gfx::atlas_file(entry.second,text.substr(length)).empty();
        }
        return false;
    }
    V iterate() override {
        V keys=V::list();
        for (auto item : {std::pair<const char*,const char*>{"world:","图集"},{"ui:","ui图集"},{"bg:","背景图集"},{"near:","近景图集"}})
            for (const auto& key:gfx::atlas_keys(item.second)) keys.append(V(std::string(item.first)+key));
        for (const auto& item:cache.kv()) if (!py::in(item.first,keys)) keys.append(item.first);
        for (const auto& item:loaded.kv())if(!py::in(item.first,keys))keys.append(item.first);
        return keys;
    }
    size_t length() override { return iterate().len(); }
    V method(Sym name) override {
        auto sp=std::static_pointer_cast<RecordedSources>(shared_from_this());
        if (name==Sym("keys")) return V::func([sp](const Args&){return sp->iterate();});
        if (name==Sym("items") || name==Sym("values")) return V::func([sp,name](const Args&){
            V output=V::list(),keys=sp->iterate();
            for(const V& key:keys.items()){V value=sp->getitem(key);output.append(name==Sym("items")?V::tuple({key,value}):value);}
            return output;
        });
        if (name==Sym("get")) return V::func([sp](const Args& a){
            V key=a.pos.at(0);if(!sp->contains(key))return a.pos.size()>1?a.pos[1]:V::none();
            return sp->getitem(key);
        });
        return V();
    }
};

V new_NamespaceGraphics(const Args& A) {
    struct GraphicsObj : PyObj {
        V pg, pixel, recorder, sources, recorded_pg, metrics, defer_capture=V(false), skip_dave_pixels=V(true), tile, size;
        bool recording=false;
        const char* type_name() const override { return "NamespaceGraphics"; }
        bool isa(const char* c) const override { return !strcmp(c,"NamespaceGraphics") || !strcmp(c,"object"); }
        V pixels() {
            if (!pixel.has()) {
                pixel=py::native_hook("graphics.namespace",Args{pg,tile,size});
                pvz::setattr(pixel,Sym("defer_capture"),defer_capture);
                pvz::setattr(pixel,Sym("skip_dave_pixels"),skip_dave_pixels);
            }
            return pixel;
        }
        V* slot(Sym n) override {
            if (n==Sym("tile")) return pixel.has()?pixel.box->inst->slot(n):&tile;
            if(n==Sym("defer_capture"))return recording?&metrics.at(V("defer_capture")):(pixel.has()?pixel.box->inst->slot(n):&defer_capture);
            if (n==Sym("skip_dave_pixels")) return pixel.has()?pixel.box->inst->slot(n):&skip_dave_pixels;
            if(recording) {
                if(n==Sym("recorder"))return &recorder;if(n==Sym("sources"))return &sources;
                if(n==Sym("pygame"))return &recorded_pg;if(n==Sym("pg"))return &pg;
                if(metrics.is_dict() && metrics.find(V(n)))return &metrics.at(V(n));
                return nullptr;
            }
            if (n==Sym("recorder") || n==Sym("sources") || n==Sym("pygame") || n==Sym("pg") ||
                n==Sym("share_recipe") || n==Sym("local_pixels") || n==Sym("copy_on_write") ||
                n==Sym("lazy_pixels") || n==Sym("profile_detail") || n==Sym("copies") ||
                n==Sym("copy_bytes") || n==Sym("shared_copies") || n==Sym("identities"))
                return pixels().box->inst->slot(n);
            return nullptr;
        }
        V method(Sym n) override {
            auto sp=std::static_pointer_cast<GraphicsObj>(shared_from_this());
            if (n==Sym("install")) return V::func([sp](const Args& a) {
                if (as<MatchNS>(a.pos.at(0))) {
                    if (sp->pixel.has()) throw PyError("NativeGraphicsError","Cannot mix a pixel namespace with a recorded match namespace");
                    sp->recording=true;
                    sp->sources=V::inst(std::make_shared<RecordedSources>());
                    Match& world=match_of(a.pos.at(0));sp->recorder=gfx::install_graphics(world,int(sp->tile.num()));
                    sp->recorded_pg=world.pygame;sp->metrics=pvz::getattr(sp->recorded_pg,Sym("__graphics_metrics__"));
                    sp->metrics.at(V("defer_capture"))=sp->defer_capture;
                    as<RecordedSources>(sp->sources)->loaded=sp->metrics.get(V("loaded_sources"));
                    return sp->recorder;
                }
                return callm(sp->pixels(),Sym("install"),a);
            });
            if (recording) {
                if (n==Sym("export_assets")) return V::func([sp](const Args& a) {
                    Args input{sp->sources};
                    if (!a.pos.empty()) input.pos.push_back(a.pos[0]);
                    else if(a.has_kw(Sym("keys"))) input.pos.push_back(a.get(0,Sym("keys"),nullptr));
                    return py::native_hook("graphics.export_sources",input);
                });
                return V();
            }
            return pixels().box->inst->method(n);
        }
    };
    auto p=std::make_shared<GraphicsObj>();
    static const V t48(48.0);
    p->pg=A.get(0,Sym("pygame"),nullptr);
    p->tile=A.get(1,Sym("tile"),&t48);
    static const V size=V::tuple({V(1024),V(768)});
    p->size=A.get(2,Sym("size"),&size);
    return V::inst(p);
}
V cls_NamespaceGraphics() { static V c=py::class_value(V("NamespaceGraphics"),new_NamespaceGraphics);return c; }
#define PIXEL_CLASS(N) \
V new_##N(const Args& A) { return py::native_hook("graphics.new." #N,A); } \
V cls_##N() { return py::native_hook("graphics.class." #N,Args{}); }
PIXEL_CLASS(NativeImage) PIXEL_CLASS(DeferredImage) PIXEL_CLASS(_DeferredTransform)
PIXEL_CLASS(_Transforms) PIXEL_CLASS(_Draw) PIXEL_CLASS(_Pygame) PIXEL_CLASS(DrawRecorder)
#undef PIXEL_CLASS


static const char* DAVE_INPUTS[] = {"玩家皮肤", "玩家位置", "玩家方向", "玩家血量", "玩家倒地"};

// draw_dave(namespace, root_code, state, materialize=True): run the original body/hurt-flash
// region with the avatar's fields, keep only the 玩家受伤 counter, restore everything else.
V f_draw_dave(const Args& A) {
    V ns = A.get(0, Sym("namespace"), nullptr);
    if(ns.t==V::DICT)return invoke_compiled_original_namespace(ns,[&](Match& world){auto view=std::make_shared<MatchNS>();view->G=&world;Args actual=A;actual.pos.at(0)=V::inst(view);return f_draw_dave(actual);});
    V state = A.get(2, Sym("state"), nullptr);
    static const V t(true);
    bool materialize = A.get(3, Sym("materialize"), &t).truthy();
    Match& G = match_of(ns);
    for (const char* k : DAVE_INPUTS)
        if (!state.contains(V(k)) && !G.has_global(V(k))) throw PyError("NativeGraphicsError", std::string("Original Dave pose fields missing: ") + k);
    // touched = assigned-by-region | state keys
    static const char* ASSIGNED[] = {"玩家受伤", "lzx", "llzx", "lllzx"};
    V previous = V::dict();
    auto remember = [&](const V& k) {
        if (previous.find(k)) return;
        const V* cur = G.find_global(k);
        previous.at(k) = (cur && cur->has()) ? *cur : V();
    };
    for (const char* k : ASSIGNED) remember(V(k));
    V items = py::items(state);   // avatar state is a plain dict (or obj)
    for (auto& kv : items.items()) remember(kv.idx(0));
    for (auto& kv : items.items()) G.global(kv.idx(0)) = kv.idx(1);
    double maximum = state.get(V("_pvp_max_hp"), V(20.0)).num();
    if (maximum != 20.) G.玩家血量 = V(rd(state, V("玩家血量")).num() * 20. / maximum);
    V atlas=G.图集,skin=state.get(V("玩家皮肤")),original_skin=atlas.get(skin);
    auto restore=[&]{
        if(!original_skin.is_none())atlas.at(skin)=original_skin;
        for(const auto& item:previous.kv()){if(!item.second.has())G.global(item.first).del();else G.global(item.first)=item.second;}
    };
    try {
        if(materialize && state.get(V("_pvp_ice"),V(0))>V(0) && atlas.contains(skin+V("-冰冻"))) {
            V overlay=callm(rd(atlas,skin+V("-冰冻")),Sym("copy"),Args{});callm(overlay,Sym("set_alpha"),Args{V(100)});
            atlas.at(skin)=callm(original_skin,Sym("copy"),Args{});callm(rd(atlas,skin),Sym("blit"),Args{overlay,V::tuple({V(0),V(0)})});
        }
        if(materialize && state.get(V("_pvp_poison")).truthy()) {
            pm_native_status::init();atlas.at(skin)=pm_native_status::f_tint_poison(Args{rd(atlas,skin),state.get(V("_pvp_poison")).get(V("level")),G.pygame});
        }
        V before_hurt=G.玩家受伤;
        if(materialize)region_dave_draw(G);else region_dave_state(G);
        V position=state.get(V("玩家位置"));double tile=G.比.num();
        if(materialize && state.get(V("_pvp_pea_head")).truthy() && state.get(V("玩家血量"),V(0))>V(0)) {
            V head=atlas.get(V("豌豆射手"));if(!head.is_none()) {
                head=callm(pvz::getattr(G.pygame,Sym("transform")),Sym("scale"),Args{head,V::tuple({py::round(V(tile*.82)),py::round(V(tile*.82))})});
                if(state.get(V("玩家方向"),V(1))<V(0))head=callm(pvz::getattr(G.pygame,Sym("transform")),Sym("flip"),Args{head,V(true),V(false)});
                G.摄像显示.call(Args{head,V::tuple({position.idx(0)-V(tile*.41),position.idx(1)-V(tile*2.01)})});
            }
        }
        if(materialize && state.get(V("_pvp_butter"),V(0))>V(0))G.摄像显示.call(Args{rd(atlas,V("黄油")),V::tuple({position.idx(0)-V(tile*.5),position.idx(1)-V(tile*2.1)})});
        if(materialize && state.get(V("_pvp_stun"),V(0))>V(0)) {
            V spark=callm(pvz::getattr(G.pygame,Sym("transform")),Sym("scale"),Args{rd(atlas,V("星星")),V::tuple({V(std::max(1,int(tile*.2))),V(std::max(1,int(tile*.2)))})});
            for(int n=0;n<3;++n){double angle=py::m_get(ns,V("_pvp_native_tick"),V(0)).num()/50.+n*3.141592653589793*2/3;G.摄像显示.call(Args{spark,V::tuple({position.idx(0)+V(std::cos(angle)*tile*.4-tile*.1),position.idx(1)+V(-tile*2.25+std::sin(angle)*tile*.08)})});}
        }
        if(std::getenv("PVZ_DEBUG_DAVE") && (before_hurt.truthy() || G.玩家受伤.truthy()))fprintf(stderr,"draw_dave mat=%d hp=%g hurt %s -> %s maximum=%g\n",int(materialize),G.玩家血量.num(),py_str(before_hurt).c_str(),py_str(G.玩家受伤).c_str(),maximum);
        setitem(state,V("玩家受伤"),G.玩家受伤);
    }catch(...){restore();throw;}
    restore();
    return V::none();
}

}  // namespace pvz::pm_native_animation

namespace pvz {
// native_placement: a private namespace with only ditu/植物/秘籍/kong and the original
// 哪个植物 / 哪个无南瓜植物 / 出界(row, 0) bound to it.
void register_runtime_hooks() {
    py::register_native_hook("run_placement_region", [](const Args& a) {
        region_placement(match_of(a.pos.at(0)));
        return V::none();
    });
    py::register_native_hook("copy_deepcopy", [](const Args&) {
        return V::func([](const Args& b) { return pvz::deepcopy(b.pos.at(0)); });
    });
    py::register_native_hook("placement_namespace", [](const Args& a) {
        V ns = new_match_ns();
        Match& G = match_of(ns);
        register_original_funcs(G);
        G.ditu = a.pos.at(0);
        G.植物 = a.pos.at(1);
        G.秘籍 = a.pos.at(2);
        G.kong = a.pos.at(3);
        G.模式 = V("正常模式");
        V original = G.出界;
        G.出界 = V::func([original](const Args& b) { return original.call(Args{b.pos.at(0), V(0.0)}); });
        return ns;
    });
}
}  // namespace pvz
