#include "core/fsutil.h"
#include "sim/pvp/gen/pm_native_animation.h"
#include <fstream>
#include "core/native_closure.h"
#include "sim/pvp/shim/pm_native_assets.h"
#include "sim/pvp/gen/pm_native_runtime.h"
#include "sim/pvp/gen/pm_pvp70_catalog.h"
#include "cpptests/gen/pm_test_pvp_70_features.h"
#include "cpptests/gen/pm_test_pvp_70_animation.h"
// Negative controls exercise the actual translated assertion adapter, not a Python copy.
#include "cpptests/gen/pm_pvzunit.h"
#include "cpptests/gen/pm_test_pvp_hero_isolation.h"
#include "cpptests/gen/pm_test_pvp_content_acceptance.h"
#include "ui/gen/pm_app.h"
#include "ui/gen/pm_ui_expansion_assets.h"
#include "ui/gen/pm_map_editor_actions.h"
#include "ui/gen/pm_scaled_display.h"
#include "pg/pg.h"
#include "ui/gen/pm_performance_window.h"
#include "sim/pvp/gen/pm_native_battle.h"
#include "sim/pvp/gen/pm_native_bridge.h"
#include <cstdio>
#include "core/alloc.h"
#include "sim/pvp/shim/pm_cppcore.h"
#include "sim/pvp/shim/pm_native_multiworker.h"
#include "sim/pvp/shim/pm_gc_policy.h"
#include "sim/pvp/hand/graphics.h"
namespace pvz { bool native_box_is_live(const Box*); }
namespace pvz::cpptests {
// Diagnostic only: execute the existing compiled original atlas loader over
// real isolated SDL IO. No Python command/result is used as the product.
bool native_atlas_probe() {
    int errors=0;
    try {
        V pg=py::stdlib_module(V("pygame"));callm(pg,Sym("init"),Args{});
        callm(pvz::getattr(pg,Sym("display")),Sym("set_mode"),Args{V::tuple({V(960),V(640)})});
        V bridge=pm_native_bridge::C_NativeBridge::m_from_marshaled(Args{});
        V payload=callm(bridge,Sym("combat_payload"),Args{});
        std::vector<V> rows;
        for(int y=0;y<12;++y){std::vector<V> row;for(int x=0;x<16;++x)row.push_back(py_dict({{V("kind"),V("空")}}));rows.push_back(V::list(row));}
        V terrain=py_dict({{V("tile_size"),V(48)},{V("width"),V(768)},{V("rows"),V(12)},{V("tiles"),V::list(rows)}});
        V runtime=pm_native_runtime::new_NativeRuntime(Args({payload.idx(0),terrain},{{Sym("pygame"),pg}}));
        V ns=pvz::getattr(runtime,Sym("g"));Match& world=match_of(ns);
        pm_native_assets::f_load_original_assets(Args{ns,payload.idx(0),payload.idx(2),V(48)});
        world.总宽=V(960);world.总高=V(640);
        world.生成近景=V::func([](const Args&){return V::none();});
        world.加载游戏.call(Args{});
        if(const char* path=std::getenv("PVZ_NATIVE_ATLAS_REPORT")) {
            V report=V::dict();
            for(const auto& pair:std::vector<std::pair<const char*,V>>{{"world",world.图集},{"ui",world.ui图集}}) {
                V atlas=V::dict();
                for(const auto& entry:pair.second.kv()) {
                    V pixels=callm(pvz::getattr(pg,Sym("image")),Sym("tobytes"),Args{entry.second,V("RGBA")});
                    V digest=callm(py::stdlib_call(V("hashlib.sha256"),Args{pixels}),Sym("hexdigest"),Args{});
                    atlas.at(entry.first)=py_dict({{V("size"),py::list_it(callm(entry.second,Sym("get_size"),Args{}))},{V("rgba_sha256"),digest},{V("alpha"),callm(entry.second,Sym("get_alpha"),Args{})},{V("colorkey"),pm_native_animation::f__plain(Args{callm(entry.second,Sym("get_colorkey"),Args{})})}});
                }
                report.at(V(pair.first))=atlas;
            }
            std::ofstream output(u8p(path),std::ios::binary);output<<dump(report);if(!output)throw PyError("OSError","Cannot write actual atlas pixel report");
        }

        printf("NATIVE_ATLAS_PROBE %s\n",dump(py_dict({{V("world_assets"),V(double(world.图集.len()))},{V("ui_assets"),V(double(world.ui图集.len()))},{V("tile"),world.比},{V("plk"),world.plk}})).c_str());
    }catch(const PyError& e){++errors;fprintf(stderr,"NATIVE_ATLAS_PROBE_ERROR %s\n",e.what());}
    printf("NATIVE_ATLAS_PROBE_ERRORS %d\n",errors);return errors==0;
}

bool joystick_contract();
namespace {
struct MappingContract : PyObj {
    V data=V::dict();
    V getitem(const V& key) override { const V* value=data.find(key);if(!value)throw PyError("KeyError",py_str(key));return *value; }
    void setitem(const V& key,const V& value) override {data.at(key)=value;}
    void delitem(const V& key) override {py_del(data,key);}
    V iterate() override {std::vector<V> keys;for(const auto& item:data.kv())keys.push_back(item.first);return V::list(keys);}
};
}

bool framework_contract() {
    pm_pvzunit::init();
    V tc = pm_pvzunit::new_TestCase(Args{});
    int failed=0, checked=0;
    auto check = [&](const char* method, const Args& a, bool should_fail) {
        ++checked;
        try {
            callm(tc, Sym(method), a);
            if (should_fail) { ++failed; fprintf(stderr,"CONTRACT FAILED: %s accepted bad input\n",method); }
        } catch (PyError& e) {
            if (!should_fail || !e.matches("AssertionError")) { ++failed; fprintf(stderr,"CONTRACT FAILED: %s: %s\n",method,e.what()); }
        }
    };
    check("assertEqual", Args{V(1),V(2)},true);
    check("assertEqual", Args{V(1),V(1)},false);
    check("assertTrue", Args{V(false)},true);
    check("assertFalse", Args{V(true)},true);
    check("assertListEqual",Args{V::list({V(1)}),V::tuple({V(1)})},true);
    check("assertListEqual",Args{V::list({V(1)}),V::list({V(1)})},false);
    check("assertTupleEqual",Args{V::tuple({V(1)}),V::list({V(1)})},true);
    check("assertDictEqual",Args{V(1),V(1)},true);
    check("assertSequenceEqual",Args({V::tuple({V(1)}),V::tuple({V(1)})},{{Sym("seq_type"),py::builtin(V("list"))}}),true);
    check("assertSequenceEqual",Args{V::list({V(1)}),V::tuple({V(1)})},false);
    check("assertIsInstance",Args{tc,pm_pvzunit::cls_TestCase()},false);
    check("assertNotIsInstance",Args{tc,pm_pvzunit::cls_TestCase()},true);
    check("assertAlmostEqual",Args({V(1),V(1.1)},{{Sym("delta"),V(.01)}}),true);
    check("assertRegex",Args{V("boom12"),V("^boom[0-9]+$")},false);
    check("assertRegex",Args{V("boom"),V("^different$")},true);
    try {
        V manager=callm(tc,Sym("assertRaisesRegex"),Args{py::exc_type(V("ValueError")),V("^boom[0-9]+$")});
        callm(manager,Sym("__enter__"),Args{});
        V accepted=callm(manager,Sym("__exit__"),Args{py::exc_type(V("ValueError")),py::make_exc(V("ValueError"),Args{V("boom12")},""),V::none()});
        ++checked;if(!accepted.truthy())++failed;
        manager=callm(tc,Sym("assertRaises"),Args{py::exc_type(V("ValueError"))});
        callm(manager,Sym("__enter__"),Args{});
        V wrong=callm(manager,Sym("__exit__"),Args{py::exc_type(V("TypeError")),py::make_exc(V("TypeError"),Args{V("bad")},""),V::none()});
        ++checked;if(wrong.truthy())++failed;
        manager=callm(tc,Sym("assertRaises"),Args{py::exc_type(V("ValueError"))});
        callm(manager,Sym("__enter__"),Args{});
        ++checked;bool rejected=false;
        try {callm(manager,Sym("__exit__"),Args{V::none(),V::none(),V::none()});}
        catch(PyError& e){rejected=e.matches("AssertionError");}
        if(!rejected)++failed;
        V mapping=V::dict();mapping.at(V("a"))=V(1);
        V values=V::dict();values.at(V("a"))=V(2);
        V patch=py::stdlib_call(V("unittest.mock.patch.dict"),Args{mapping,values});
        callm(patch,Sym("start"),Args{});++checked;if(mapping.get(V("a"))!=V(2))++failed;
        mapping.at(V("extra"))=V(3);callm(patch,Sym("stop"),Args{});
        ++checked;if(mapping.get(V("a"))!=V(1)||mapping.contains(V("extra")))++failed;
        V env=py::stdlib_attr(V("os"),V("environ"));
        V key("PVZ_CPPTEST_ENV_CONTRACT"),extra("PVZ_CPPTEST_ENV_EXTRA");
        V original=callm(env,Sym("get"),Args{key,V()});
        V original_extra=callm(env,Sym("get"),Args{extra,V()});
        V replacement=V::dict();replacement.at(key)=V("during");
        patch=py::stdlib_call(V("unittest.mock.patch.dict"),Args{env,replacement});
        callm(patch,Sym("start"),Args{});
        ++checked;if(callm(env,Sym("get"),Args{key})!=V("during"))++failed;
        pvz::setitem(env,extra,V("added inside"));callm(patch,Sym("stop"),Args{});
        ++checked;if(callm(env,Sym("get"),Args{key,V()})!=original || callm(env,Sym("get"),Args{extra,V()})!=original_extra)++failed;
    } catch(PyError& e){++failed;fprintf(stderr,"CONTRACT FAILED: context/patch: %s\n",e.what());}
    try {
        auto expect=[&](bool ok,const char* name){++checked;if(!ok){++failed;fprintf(stderr,"CONTRACT FAILED: iterable lifetime %s\n",name);}};
        V keys=py_dict({{V("one"),V(1)},{V("two"),V(2)}});
        expect(py::concat_star({py::star(keys),py::one(V("tail"))})==V::list({V("one"),V("two"),V("tail")}),"dictionary star");
        Args args=py::star_args({},keys,{},V::none());
        expect(args.pos.size()==2 && args.pos[0]==V("one") && args.pos[1]==V("two"),"star arguments");
        expect(py::any(keys).truthy(),"any dictionary");
        expect(!py::all(py_dict({{V(""),V(1)}})).truthy(),"all dictionary");
        expect(py::sum_it(V::set({V(1),V(2),V(3)}),V(0))==V(6),"sum set");
        expect(py::map(py::builtin(V("str")),V("ab"))==V::list({V("a"),V("b")}),"map string");
        expect(py::filter(V::none(),V("ab"))==V::list({V("a"),V("b")}),"filter string");
        V joined=callm(V::set({V("one")}),Sym("union"),Args{keys});
        expect(joined.len()==2 && joined.contains(V("two")),"set union dictionary");
        expect(pvz::getattr(keys,Sym("missing"),V(42))==V(42),"missing dictionary attribute default");
        bool rejected=false;
        try{(void)pvz::getattr(keys,Sym("missing"));}catch(PyError& e){rejected=e.matches("AttributeError");}
        expect(rejected,"missing dictionary attribute raises");
        expect(pvz::getattr(keys,Sym("get")).call(Args{V("one")})==V(1),"bound dictionary method");
        V namespace_=py_dict({{V("spots"),V::func([](const Args&){return V(1);})}});
        V saved=pvz::getattr(namespace_,Sym("spots"));
        pvz::setattr(namespace_,Sym("spots"),V::func([saved](const Args& a){return saved.call(a)+V(1);}));
        expect(callm(namespace_,Sym("spots"),Args{})==V(2) && saved.call(Args{})==V(1),"captured callable stays bound");
    }catch(PyError& e){++failed;fprintf(stderr,"CONTRACT FAILED: iterable lifetime: %s\n",e.what());}
    try {
        auto expect = [&](bool okay, const char* name) { ++checked; if (!okay) { ++failed; fprintf(stderr, "CONTRACT FAILED: mock %s\n", name); } };
        auto rejects = [&](const V& mock, const char* method, const Args& a) {
            bool caught = false;
            try { callm(mock, Sym(method), a); } catch (const PyError& e) { caught = e.matches("AssertionError"); }
            expect(caught, method);
        };
        V mock = py::stdlib_call(V("unittest.mock.Mock"), Args({}, {{Sym("return_value"), V(7)}}));
        rejects(mock, "assert_called_once", Args{});
        expect(mock.call(Args({V(1)}, {{Sym("x"), V(2)}})) == V(7), "configured result");
        callm(mock, Sym("assert_called_once_with"), Args({V(1)}, {{Sym("x"), V(2)}})); ++checked;
        rejects(mock, "assert_called_once_with", Args({V(1)}, {{Sym("x"), V(3)}}));
        rejects(mock, "assert_not_called", Args{});
        V record = pvz::getattr(mock, Sym("call_args"));
        expect(pvz::getattr(record, Sym("args")) == V::tuple({V(1)}) && rd(pvz::getattr(record, Sym("kwargs")), V("x")) == V(2), "recorded args and kwargs");
        callm(mock, Sym("reset_mock"), Args{});
        callm(mock, Sym("assert_not_called"), Args{}); ++checked;
        int actual_calls = 0;
        V original = V::func([&](const Args& a) { ++actual_calls; return a.pos.at(0) * V(2); });
        V target = py_dict({{V("f"), original}});
        V patch = py::stdlib_call(V("unittest.mock.patch.object"), Args({target, V("f")}, {{Sym("wraps"), original}}));
        V wrapped = callm(patch, Sym("start"), Args{});
        expect(callm(target, Sym("f"), Args{V(3)}) == V(6) && actual_calls == 1, "wraps executes original");
        callm(wrapped, Sym("assert_called_once_with"), Args{V(3)}); ++checked;
        callm(patch, Sym("stop"), Args{});
        expect(py_is(rd(target, V("f")), original) && callm(target, Sym("f"), Args{V(4)}) == V(8), "binding restored");
        V math = py::stdlib_module(V("math"));
        V sqrt = pvz::getattr(math, Sym("sqrt"));
        patch = py::stdlib_call(V("unittest.mock.patch.object"), Args({math, V("sqrt")}, {{Sym("wraps"), sqrt}}));
        wrapped = callm(patch, Sym("start"), Args{});
        expect(py::stdlib_call(V("math.sqrt"), Args{V(9)}) == V(3), "stdlib replacement reaches original once");
        callm(wrapped, Sym("assert_called_once_with"), Args{V(9)}); ++checked;
        callm(patch, Sym("stop"), Args{});
        expect(py::stdlib_call(V("math.sqrt"), Args{V(16)}) == V(4), "stdlib restored");
        mock = py::stdlib_call(V("unittest.mock.Mock"), Args({}, {{Sym("side_effect"), py::make_exc(V("OSError"), Args{V("expected")}, "")}}));
        bool raised = false; try { mock.call(Args{}); } catch (const PyError& e) { raised = e.matches("OSError"); }
        expect(raised && pvz::getattr(mock, Sym("call_count")) == V(1), "raising side effect records call");
        V app_type = pm_app::cls_Application();
        V app = callm(app_type, Sym("__new__"), Args{app_type});
        pvz::setattr(app, Sym("mode"), V("local"));
        expect(callm(app, Sym("local_sides"), Args{}) == V::list({V("plant"), V("zombie")}), "real application unpatched sides");
        bool bound_self = false;
        V replacement = V::func([&](const Args& a) { bound_self = !a.pos.empty() && py_is(a.pos[0], app); return V::list({V("zombie")}); });
        patch = py::stdlib_call(V("unittest.mock.patch.object"), Args{app_type, V("local_seats"), replacement});
        callm(patch, Sym("start"), Args{});
        expect(callm(app, Sym("local_sides"), Args{}) == V::list({V("zombie")}) && bound_self, "real application class patch reaches internal call and binds self");
        callm(patch, Sym("stop"), Args{});
        expect(callm(app, Sym("local_sides"), Args{}) == V::list({V("plant"), V("zombie")}), "real application class patch restored");
        V path = py::stdlib_call(V("pathlib.Path"), Args{V("native-path-contract")});
        expect(py_eq(path, py::stdlib_call(V("pathlib.Path"), Args{V("native-path-contract")})), "independent equal paths");
        expect(!py_eq(path, py::stdlib_call(V("pathlib.Path"), Args{V("different-path-contract")})), "different paths remain unequal");
        expect(!isinstance(V(1.5), "int") && isinstance(V(2), "int"), "fractional values fail integer validation");
        V raw=V::bytes(std::string("\0\xff\xc3\xa9",4));
        V repeated=raw*V(3);
        expect(repeated.byt && repeated.len()==12,"byte repetition preserves byte length");
        V array=py::builtin_call(V("bytearray"),Args{repeated});
        expect(py_eq(repeated,array) && py_eq(array,repeated),"bytes and bytearray compare actual contents");
        callm(array,Sym("append"),Args{V(1)});
        expect(!py_eq(repeated,array),"bytearray content mismatch stays unequal");
        expect(!pvz::hasattr(array,Sym("getvalue")),"bytearray does not advertise absent methods");
        auto mapping=std::make_shared<MappingContract>();
        mapping->data=py_dict({{V("old"),V(1)},{V("keep"),V(2)}});
        V mapped=V::inst(mapping),initial_mapping=py::copy(mapping->data);
        V mapping_patch=py::stdlib_call(V("unittest.mock.patch.dict"),Args{mapped,py_dict({{V("old"),V(9)},{V("temporary"),V(3)}})});
        callm(mapping_patch,Sym("start"),Args{});
        expect(mapping->data.get(V("old"),V())==V(9) && mapping->data.get(V("temporary"),V())==V(3),"patch.dict mutates actual custom mapping storage");
        pvz::setitem(mapped,V("inside"),V(4));mapped.box->inst->delitem(V("keep"));
        callm(mapping_patch,Sym("stop"),Args{});
        expect(py_eq(mapping->data,initial_mapping),"patch.dict restores removed values and removes keys added inside the context");
        mapping_patch=py::stdlib_call(V("unittest.mock.patch.dict"),Args({mapped,py_dict({{V("only"),V(7)}})},{{Sym("clear"),V(true)}}));
        callm(mapping_patch,Sym("__enter__"),Args{});
        expect(mapping->data.len()==1 && mapping->data.get(V("only"),V())==V(7),"clear patch removes original mapping keys");
        callm(mapping_patch,Sym("__exit__"),Args{py::exc_type(V("ValueError")),py::make_exc(V("ValueError"),Args{V("boom")},""),V::none()});
        expect(py_eq(mapping->data,initial_mapping),"mapping restores original storage on exceptional context exit");
        bool invalid_mapping_rejected=false;
        try {V bad=py::stdlib_call(V("unittest.mock.patch.dict"),Args{py::new_object(),V::dict()});callm(bad,Sym("start"),Args{});}
        catch(const PyError& e){invalid_mapping_rejected=e.matches("TypeError");}
        expect(invalid_mapping_rejected,"objects without the mapping protocol are rejected");
        Match key_match; V key_ns=match_ns(key_match);
        expect(callm(key_ns,Sym("get"),Args{V::none(),V(73)})==V(73),"namespace None lookup keeps the real default");
        pvz::setitem(key_ns,V::none(),V(19));pvz::setitem(key_ns,V(4),V(23));pvz::setitem(key_ns,V("4"),V(29));
        expect(rd(key_ns,V::none())==V(19) && rd(key_ns,V(4))==V(23) && rd(key_ns,V("4"))==V(29),"namespace retains distinct non-string and string keys");
        key_ns.box->inst->delitem(V::none());
        expect(!key_ns.box->inst->contains(V::none()) && callm(key_ns,Sym("get"),Args{V::none(),V(73)})==V(73),"namespace deletion and missing non-string lookup");
        V attribute_battle=V::inst(std::make_shared<pm_native_battle::C_NativeBattle>());
        pvz::setattr(attribute_battle,Sym("tick"),V(17));pvz::setattr(attribute_battle,Sym("fixture_dynamic"),V(21));
        V actual_attributes=py::builtin_call(V("vars"),Args{attribute_battle});
        expect(actual_attributes.box->inst->contains(V("tick")) && actual_attributes.box->inst->contains(V("fixture_dynamic")) && !actual_attributes.box->inst->contains(V("spawn")),"NativeBattle vars enumerates live declared and dynamic instance attributes");
        pm_test_pvp_hero_isolation::init();
        V hero_module=pm_test_pvp_hero_isolation::module_ns();
        expect(py_is(py::stdlib_module(V("test_pvp_hero_isolation")),hero_module) && pvz::getattr(hero_module,Sym("__name__"))==V("test_pvp_hero_isolation"),"original test module import retains actual identity and name");
        V original_spawnable=pvz::getattr(hero_module,Sym("spawnable"));int filtered_calls=0;
        V filtered=V::func([&](const Args& a){++filtered_calls;return V::list({a.pos.at(0)});});
        V hero_patch=py::stdlib_call(V("unittest.mock.patch"),Args{V("test_pvp_hero_isolation.spawnable"),filtered});
        callm(hero_patch,Sym("start"),Args{});
        expect(callm(hero_module,Sym("spawnable"),Args{V("plant")})==V::list({V("plant")}) && filtered_calls==1,"dotted patch replaces the actual hero helper binding");
        callm(hero_patch,Sym("stop"),Args{});
        expect(!py_is(pvz::getattr(hero_module,Sym("spawnable")),filtered) && callm(hero_module,Sym("spawnable"),Args{V("plant")}).len()>10,"dotted patch restores the actual hero helper implementation");
        V garbage_module=py::stdlib_module(V("gc"));
        V actual_callbacks=pvz::getattr(garbage_module,Sym("callbacks"));
        std::vector<std::string> collector_phases;double reported_reclaimed=-1;
        V observer=V::func([&](const Args& args){collector_phases.push_back(args.pos.at(0).str());if(args.pos[0]==V("stop"))reported_reclaimed=args.pos[1].get(V("collected")).num();return V::none();});
        actual_callbacks.append(observer);
        struct RemoveCollectorObserver { V callbacks,observer;~RemoveCollectorObserver(){try{callm(callbacks,Sym("remove"),Args{observer});}catch(const PyError&){}} } remove_observer{actual_callbacks,observer};
        V live_cycle=V::list();live_cycle.append(live_cycle);Box* live_cycle_box=live_cycle.box.get();
        V dead_cycle=V::list();dead_cycle.append(dead_cycle);Box* dead_cycle_box=dead_cycle.box.get();dead_cycle=V::none();
        V peer_a=V::dict(),peer_b=V::list();peer_a.at(V("peer"))=peer_b;peer_b.append(peer_a);
        Box* peer_a_box=peer_a.box.get();Box* peer_b_box=peer_b.box.get();peer_a=V::none();peer_b=V::none();
        V unit_cycle=V::obj();unit_cycle.at(V("self"))=unit_cycle;Box* unit_cycle_box=unit_cycle.box.get();unit_cycle=V::none();
        V collected=py::stdlib_call(V("gc.collect"),Args{});
        expect(collected.num()>=4 && !native_box_is_live(dead_cycle_box) && !native_box_is_live(peer_a_box) && !native_box_is_live(peer_b_box) && !native_box_is_live(unit_cycle_box),"manual collector actually reclaims isolated list/dict/unit cycles");
        expect(native_box_is_live(live_cycle_box) && py_is(live_cycle.idx(0),live_cycle),"manual collector preserves a live self-referential container");
        expect(collector_phases==std::vector<std::string>({"start","stop"}) && reported_reclaimed==collected.num(),"collector callbacks report the actual collection and count");
        live_cycle=V::none();py::stdlib_call(V("gc.collect"),Args{});
        expect(!native_box_is_live(live_cycle_box),"released live root permits actual later collection");
        V opaque_child=V::list();opaque_child.append(opaque_child);Box* opaque_child_box=opaque_child.box.get();
        V opaque_owner=V::func([held=opaque_child](const Args&){return held;});opaque_child=V::none();
        py::stdlib_call(V("gc.collect"),Args{});
        expect(native_box_is_live(opaque_child_box) && py_is(opaque_owner.call(Args{}).idx(0),opaque_owner.call(Args{})),"opaque function references remain conservative roots");
        opaque_owner=V::none();py::stdlib_call(V("gc.collect"),Args{});
        expect(!native_box_is_live(opaque_child_box),"dropping an opaque owner allows the remaining container cycle to be collected");
        bool invalid_generation=false;try{py::stdlib_call(V("gc.collect"),Args{V(-1)});}catch(const PyError& error){invalid_generation=error.matches("ValueError");}
        expect(invalid_generation,"collector rejects an invalid generation");
        V gc_capabilities=pvz::getattr(garbage_module,Sym("native_capabilities"));
        expect(gc_capabilities.get(V("manual_collection")).truthy() && !gc_capabilities.get(V("automatic_generations")).truthy() && !gc_capabilities.get(V("native_instance_cycles")).truthy(),"collector scope explicitly excludes unsupported native-instance and automatic generation collection");
        V ordered_type=py::stdlib(V("collections.OrderedDict"));
        V ordered=ordered_type.call(Args{V::list({V::tuple({V("a"),V(1)}),V::tuple({V("b"),V(2)})})});
        expect(py_is(py::type(ordered),ordered_type) && isinstance(ordered,"OrderedDict") && isinstance(ordered,"dict") && !isinstance(V::dict(),"OrderedDict"),"ordered mapping has its own real type while remaining a dict");
        expect(pvz::hasattr(ordered,Sym("move_to_end")) && !pvz::hasattr(V::dict(),Sym("move_to_end")),"only ordered mappings expose move_to_end");
        pvz::getattr(ordered,Sym("move_to_end")).call(Args{V("a")});
        expect(py::keys(ordered)==V::list({V("b"),V("a")}),"ordered mapping moves the actual key to the end");
        callm(ordered,Sym("move_to_end"),Args({V("a")},{{Sym("last"),V(false)}}));
        expect(py::keys(ordered)==V::list({V("a"),V("b")}),"ordered mapping moves the actual key to the front");
        V reverse_order=ordered_type.call(Args{V::list({V::tuple({V("b"),V(2)}),V::tuple({V("a"),V(1)})})});
        expect(!py_eq(ordered,reverse_order) && py_eq(ordered,py::dict_of(reverse_order)),"OrderedDict equality uses order only when both operands are ordered mappings");
        V ordered_copy=py::copy(ordered),ordered_deep=py::deepcopy(ordered);
        expect(py_is(py::type(ordered_copy),ordered_type) && py_is(py::type(ordered_deep),ordered_type) && py_eq(ordered,ordered_copy),"shallow and deep copies retain ordered mapping type and contents");
        callm(ordered,Sym("clear"),Args{});
        expect(ordered.len()==0 && py_is(py::type(ordered),ordered_type) && pvz::hasattr(ordered,Sym("move_to_end")),"clearing a room cache retains the ordered mapping interface");
        bool plain_move_rejected=false;try{callm(V::dict(),Sym("move_to_end"),Args{V("a")});}catch(const PyError& error){plain_move_rejected=error.matches("AttributeError");}
        expect(plain_move_rejected,"ordinary dicts reject the ordered-only operation");
        expect(callm(ordered_copy,Sym("popitem"),Args({},{{Sym("last"),V(false)}}))==V::tuple({V("a"),V(1)}) && py::keys(ordered_copy)==V::list({V("b")}),"oldest-item eviction changes actual ordered storage");
        int bound_calls=0;
        V receiver=py_dict({{V("value"),V(9)}});
        V bound_function=V::func([&](const Args& a){++bound_calls;return V::tuple({rd(a.pos.at(0),V("value")),V::tuple(std::vector<V>(a.pos.begin()+1,a.pos.end())),a.kwrest({})});});
        bound_function.box->fattrs.emplace_back(Sym("__name__"),V("fixture_function"));
        V method_type=py::stdlib(V("types.MethodType"));
        V bound=method_type.call(Args{bound_function,receiver});
        V bound_result=bound.call(Args({V(3),V(4)},{{Sym("flag"),V(5)}}));
        expect(bound_calls==1 && py_eq(bound_result,V::tuple({V(9),V::tuple({V(3),V(4)}),py_dict({{V("flag"),V(5)}})})),"MethodType invokes actual callable with receiver, positions and keywords");
        expect(py_is(pvz::getattr(bound,Sym("__self__")),receiver) && py_is(pvz::getattr(bound,Sym("__func__")),bound_function),"bound method exposes actual receiver and function");
        expect(py_is(py::type(bound),method_type) && py::isinstance_v(bound,method_type).truthy(),"bound method has its actual native method type");
        expect(py_eq(bound,method_type.call(Args{bound_function,receiver})) && !py_eq(bound,method_type.call(Args{bound_function,py::copy(receiver)})),"method equality uses actual receiver identity as CPython does");
        bool read_only=false;try{pvz::setattr(bound,Sym("__self__"),V::none());}catch(const PyError& e){read_only=e.matches("AttributeError");}
        expect(read_only,"method receiver metadata is read-only");
        bool bad_callable=false;try{method_type.call(Args{V(3),receiver});}catch(const PyError& e){bad_callable=e.matches("TypeError");}
        expect(bad_callable,"MethodType rejects a non-callable");
        bool bad_module=false;try{method_type.call(Args{py::stdlib_module(V("math")),receiver});}catch(const PyError& e){bad_module=e.matches("TypeError");}
        expect(bad_module,"MethodType rejects a module that has no call protocol");
        bool bad_receiver=false;try{method_type.call(Args{bound_function,V::none()});}catch(const PyError& e){bad_receiver=e.matches("TypeError");}
        expect(bad_receiver,"MethodType rejects a None receiver");
        V descriptor=pvz::getattr(bound_function,Sym("__get__"));
        V descriptor_bound=descriptor.call(Args{receiver,py::builtin(V("dict"))});
        expect(descriptor_bound.call(Args{V(6)})==V::tuple({V(9),V::tuple({V(6)}),V::dict()}),"function descriptor forwards to the actual bound function");
        expect(py_is(descriptor.call(Args{V::none(),py::builtin(V("dict"))}),bound_function),"unbound function descriptor preserves actual function identity");
        expect(py_is(pvz::getattr(callm(bound_function,Sym("__get__"),Args{receiver}),Sym("__self__")),receiver),"direct __get__ calls bind the original receiver");
        bool bad_descriptor_none=false;try{descriptor.call(Args{V::none()});}catch(const PyError& error){bad_descriptor_none=error.matches("TypeError");}
        expect(bad_descriptor_none,"function __get__(None) rejects an absent owner as CPython does");
        bool bad_descriptor_args=false;try{descriptor.call(Args{receiver,V::none(),V(1)});}catch(const PyError& error){bad_descriptor_args=error.matches("TypeError");}
        expect(bad_descriptor_args,"function descriptor rejects extra arguments");
        expect(pvz::hasattr(bound_function,Sym("__get__")) && !pvz::getattr(bound_function,Sym("__get__"),V::none()).is_none(),"function descriptor is visible to actual attribute lookup");
        expect(!pvz::hasattr(method_type,Sym("__get__")) && !pvz::hasattr(py::builtin(V("len")),Sym("__get__")) && pvz::getattr(method_type,Sym("__get__"),V::none()).is_none(),"native class and builtin callable are not misidentified as Python function descriptors");
        V directory_error=py::make_exc(V("IsADirectoryError"),Args{V("test directory")},"");
        expect(isinstance(directory_error,"OSError") && !isinstance(directory_error,"TypeError"),"directory exception retains its real OSError ancestry");
        V weak_target=V::inst(std::make_shared<PyObj>());
        V weak=py::stdlib_call(V("weakref.ref"),Args{weak_target});
        expect(py_is(weak.call(Args{}),weak_target),"native weak reference returns its live target");
        weak_target=V::none();
        expect(weak.call(Args{}).is_none(),"native weak reference does not keep its target alive");
        auto receiver_only_battle=std::make_shared<pm_native_battle::C_NativeBattle>();
        V bound_close=receiver_only_battle->method(Sym("close"));
        expect(py_is(pvz::getattr(bound_close,Sym("__self__")),V::inst(receiver_only_battle)),"real NativeBattle close exposes its actual receiver for cleanup");
        V valid_weak_callback_target=V::inst(std::make_shared<PyObj>());
        bool weak_callback_rejected=false;try{py::stdlib_call(V("weakref.ref"),Args{valid_weak_callback_target,bound_function});}catch(const PyError& e){weak_callback_rejected=e.matches("NotImplementedError");}
        expect(weak_callback_rejected,"unsupported weak callbacks are rejected explicitly");
        V environment=py::stdlib_attr(V("os"),V("environ")),environment_key=V("PVZ_NATIVE_ENV_CONTRACT_41");
        struct RestoreEnvironment {
            V env,key,prior;bool existed;
            ~RestoreEnvironment(){try{if(existed)pvz::setitem(env,key,prior);else if(env.box->inst->contains(key))env.box->inst->delitem(key);}catch(const PyError&){}}
        } environment_restore{environment,environment_key,callm(environment,Sym("get"),Args{environment_key,V::none()}),environment.box->inst->contains(environment_key)};
        pvz::setitem(environment,environment_key,V("原生环境值"));
        expect(pvz::getattr(py::stdlib_module(V("os")),Sym("environ")).box->inst->getitem(environment_key)==V("原生环境值"),"environment preserves actual Unicode values");
        V environment_copy=py::dict_of(environment);
        expect(environment_copy.get(environment_key,V())==V("原生环境值"),"dict(environment) uses actual iteration and item lookup");
        pvz::setitem(environment,environment_key,V(""));
        expect(environment.box->inst->contains(environment_key) && environment.box->inst->getitem(environment_key)==V(""),"empty environment values remain present");
        expect(callm(environment,Sym("pop"),Args{environment_key})==V("") && !environment.box->inst->contains(environment_key),"environment pop removes the entry");
        bool missing_environment=false;try{callm(environment,Sym("pop"),Args{environment_key});}catch(const PyError& e){missing_environment=e.matches("KeyError");}
        expect(missing_environment,"environment pop without a default rejects missing entries");
        V imported_patch=py::stdlib(V("unittest.mock.patch"));
        V actual_patch=py::stdlib_attr(V("unittest.mock"),V("patch"));
        expect(py_is(imported_patch,actual_patch) && pvz::hasattr(imported_patch,Sym("object")) && pvz::hasattr(imported_patch,Sym("dict")),"registered callable imports retain actual identity and attributes");
        V callback_object=py::stdlib_call(V("types.SimpleNamespace"),Args{});
        py::builtin(V("setattr")).call(Args{callback_object,V("state"),V(9)});
        expect(pvz::getattr(callback_object,Sym("state"))==V(9),"first-class setattr updates the real object");
        V small=V::set({V("z"),V("b")}), large=V::set({V("a"),V("b"),V("z")});
        V disjoint=V::set({V("q")});
        expect(small<=large && small<large && large>=small && large>small,"set comparisons use membership rather than insertion order");
        expect(small<=small && small>=small && !(small<small) && !(small>small),"equal sets are non-strict subsets");
        expect(!(small<=disjoint) && !(small>=disjoint) && !(small<disjoint) && !(small>disjoint),"disjoint sets stay incomparable");
        expect(V::set()<=small && V::set()<small,"empty set is a subset");
        V temporary=py::stdlib_call(V("tempfile.TemporaryDirectory"),Args{});
        V binary_path=py::stdlib_call(V("pathlib.Path"),Args{pvz::getattr(temporary,Sym("name"))})/V("binary-chunk-contract.dat");
        callm(binary_path,Sym("write_bytes"),Args{repeated});
        V binary_file=py::open_file(Args{py::str(binary_path),V("rb")});
        V chunk=callm(binary_file,Sym("read"),Args{V(6)});
        expect(chunk.byt && chunk.len()==6 && py_eq(chunk,V::bytes(repeated.str().substr(0,6))),"sized binary file reads preserve byte length and content");
        callm(binary_file,Sym("seek"),Args{V(0)});
        chunk=callm(binary_file,Sym("read"),Args{});
        expect(chunk.byt && py_eq(chunk,repeated),"whole binary reads remain unchanged");
        callm(binary_file,Sym("close"),Args{});
        V glob_root=py::stdlib_call(V("pathlib.Path"),Args{pvz::getattr(temporary,Sym("name"))});
        for(const char* filename:{"audit-42.json","audit-old.txt","audit-.json","rv_r22.py","rv_old.py","中文🙂.json"})callm(glob_root/V(filename),Sym("write_text"),Args{V("glob canary")});
        V glob_results=callm(glob_root,Sym("glob"),Args{V("audit-*.json")}),glob_names=V::set();
        for(const V& path:glob_results.items())glob_names.set_insert_new(pvz::getattr(path,Sym("name")));
        expect(glob_results.len()==2 && glob_names.contains(V("audit-42.json")) && glob_names.contains(V("audit-.json")),"Path.glob honours literal prefixes and suffixes around stars");
        expect(callm(glob_root,Sym("glob"),Args{V("rv_[!o]*.py")}).len()==1 && callm(glob_root,Sym("glob"),Args{V("中文?.json")}).len()==1,"Path.glob matches character classes and Unicode scalar question marks");
        callm(temporary,Sym("cleanup"),Args{});

        auto path_value=[](const char* text){return py::stdlib_call(V("pathlib.Path"),Args{V(text)});};
        expect(path_value("a/b")<path_value("a-b"),"path ordering compares components");
        expect(py_eq(path_value("a/./b"),path_value("a/b")),"path removes dot components for comparison");
        expect(!py_eq(path_value("a/../b"),path_value("b")),"path comparison preserves parent components");
#ifdef _WIN32
        expect(py_eq(path_value("A/B"),path_value("a/b")),"Windows path comparison folds case");
#endif
        V local_type=py::local_class(V("MutableLocal"),{{V("state"),V(1)},{V("read"),V::func([](const Args& a){return pvz::getattr(a.pos.at(0),Sym("state"));})}});
        V local_instance=local_type.call(Args{});
        expect(callm(local_instance,Sym("read"),Args{})==V(1),"local instance resolves class attributes");
        pvz::setattr(local_type,Sym("state"),V(2));
        expect(callm(local_instance,Sym("read"),Args{})==V(2) && callm(local_type.call(Args{}),Sym("read"),Args{})==V(2),"class mutation reaches existing and new local instances");
        V local_bound=pvz::getattr(local_instance,Sym("read"));
        expect(py_is(pvz::getattr(local_bound,Sym("__self__")),local_instance) && py_is(py::type(local_instance),local_type),"local methods retain receiver and class identity");
        local_type=V();
        expect(local_bound.call(Args{})==V(2),"bound local method retains live class after caller releases type");
        void* before_trace=::operator new(4000);
        native_alloc_trace_start();
        void* traced_buffer=::operator new(1000003);
        uint64_t live_alloc=0,peak_alloc=0;native_alloc_trace_read(live_alloc,peak_alloc);
        ::operator delete(before_trace);
        uint64_t after_old_free=0,unused_peak=0;native_alloc_trace_read(after_old_free,unused_peak);
        ::operator delete(traced_buffer);
        uint64_t after_traced_free=0,retained_peak=0;native_alloc_trace_read(after_traced_free,retained_peak);
        native_alloc_trace_reset_peak();uint64_t reset_current=0,reset_peak=0;native_alloc_trace_read(reset_current,reset_peak);
        native_alloc_trace_stop();
        expect(live_alloc==1000003 && peak_alloc==1000003,"allocation trace measures real requested bytes");
        expect(after_old_free==live_alloc && after_traced_free==0 && retained_peak==1000003,"trace ignores older frees and retains actual peak after release");
        expect(reset_current==0 && reset_peak==0 && !native_alloc_trace_active(),"trace reset and stop operate on actual counters");
        native_alloc_trace_start();void* prior_epoch=::operator new(1001);native_alloc_trace_stop();
        native_alloc_trace_start();::operator delete(prior_epoch);native_alloc_trace_read(live_alloc,peak_alloc);native_alloc_trace_stop();
        expect(live_alloc==0 && peak_alloc==0,"restarting trace never charges frees from a previous generation");
        V callback_namespace=py::stdlib_call(V("types.SimpleNamespace"),Args({},{{Sym("update"),V::func([](const Args& a){return a.pos.at(0);})}}));
        expect(callm(callback_namespace,Sym("update"),Args{V(42)})==V(42),"namespace callbacks override dictionary method spellings");
        V owned_word(std::string("same-word")),symbol_word(Sym("same-word"));
        expect(py_eq(owned_word,symbol_word) && py_hash(owned_word)==py_hash(symbol_word),"owned and interned strings compare and hash by text");
        V mixed_keys=V::dict();for(int i=0;i<40;++i)mixed_keys.at(V(std::string("dynamic-key-")+std::to_string(i)))=V(i);
        expect(mixed_keys.get(V(Sym("dynamic-key-31")))==V(31),"indexed dictionaries find owned keys through symbols");
        mixed_keys.at(V(Sym("dynamic-key-31")))=V(99);
        expect(mixed_keys.len()==40 && mixed_keys.get(V(std::string("dynamic-key-31")))==V(99),"mixed key updates keep one equal string key");
        V mixed_set=V::set({owned_word});
        expect(mixed_set.contains(symbol_word),"sets preserve owned and symbol text equality");
        V tuple_keys=V::dict();tuple_keys.at(V::tuple({owned_word,V(1)}))=V(7);
        expect(tuple_keys.get(V::tuple({symbol_word,V(1)}))==V(7),"tuple key hashing agrees for both string representations");
        size_t before_dynamic_strings=sym_count();
        for(int i=0;i<1000;++i){V transient(std::string("transient-json-record-")+std::to_string(i));if(transient.str().empty())throw PyError("AssertionError","lost owned text");}
        expect(sym_count()==before_dynamic_strings,"transient runtime text is released instead of permanently interned");
        expect(owned_word==Sym("same-word"),"owned text compares to the native symbol overload");
        V object_key=V::obj();pvz::setitem(object_key,V(std::string("x")),V(13));
        expect(py::m_get(object_key,V(Sym("x")))==V(13),"owned names reach typed object slots");
        auto dynamic_namespace=std::make_shared<DynNS>();dynamic_namespace->setitem(V(std::string("entry")),V(14));
        expect(dynamic_namespace->contains(V(std::string("entry"))) && callm(V::inst(dynamic_namespace),Sym("get"),Args{V(std::string("entry"))})==V(14),"dynamic namespace lookup resolves owned names correctly");
        V live_vars=callm(py::builtin(V("vars")),Sym("__call__"),Args{callback_namespace});
        expect(live_vars.get(V(std::string("update"))).t==V::FUNC,"namespace vars retain actual owned key lookup");
        V native_subclass=py::local_class(V("LocalMapSubclass"),{{V("__bases__"),V::tuple({pm_map_editor_actions::cls_MapEditing()})},{V("value"),V(23)},{V("probe"),V::func([](const Args& a){return pvz::getattr(a.pos.at(0),Sym("value"));})}});
        V native_subclass_instance=native_subclass.call(Args{});
        std::weak_ptr<PyObj> native_subclass_weak=native_subclass_instance.box->inst;
        expect(as<pm_map_editor_actions::C_MapEditing>(native_subclass_instance)!=nullptr,"local subclass allocates a real native base instance");
        expect(py_is(py::type(native_subclass_instance),native_subclass) && py::isinstance_v(native_subclass_instance,native_subclass).truthy() && py::isinstance_v(native_subclass_instance,pm_map_editor_actions::cls_MapEditing()).truthy(),"local native subclass preserves derived and base identities");
        expect(callm(native_subclass_instance,Sym("probe"),Args{})==V(23),"native subclass dispatch binds its actual receiver");
        pvz::setattr(native_subclass,Sym("value"),V(24));
        expect(callm(native_subclass_instance,Sym("probe"),Args{})==V(24),"native subclass uses the live class descriptor table");
        V native_subclass_method=pvz::getattr(native_subclass_instance,Sym("probe"));
        native_subclass_instance=V();native_subclass=V();
        expect(native_subclass_method.call(Args{})==V(24),"bound native subclass method retains its receiver and class");
        native_subclass_method=V();expect(native_subclass_weak.expired(),"local subclass descriptors do not create a receiver ownership cycle");
        expect(py_str(V::list({V(170),V(70),V(230)}))=="[170, 70, 230]","container text uses Python element separators");
        expect(py_str(V::tuple({V(1)}))=="(1,)" && py_str(V::set())=="set()","tuple and empty-set text retain their real types");
        V pygame=py::stdlib_module(V("pygame"));
        expect(joystick_contract(),"real SDL virtual joystick and raw event integration");
        V pygame_error=pvz::getattr(pygame,Sym("error")).call(Args{V("SDL failure canary")});
        expect(isinstance(pygame_error,"RuntimeError") && py_str(pygame_error)=="SDL failure canary","pygame error is a callable exception class with real message and ancestry");
        V rect=callm(pygame,Sym("Rect"),Args{V(-1),V(2),V(3),V(4)});
        expect(py_eq(rect,callm(pygame,Sym("Rect"),Args{V(-1),V(2),V(3),V(4)})),"rectangles compare coordinate values");
        expect(!py_eq(rect,callm(pygame,Sym("Rect"),Args{V(0),V(2),V(3),V(4)})),"rectangle mismatch remains unequal");

        V display_module=pvz::getattr(pygame,Sym("display"));
        callm(display_module,Sym("set_mode"),Args{V::tuple({V(96),V(64)})});
        V sdl_owner=py::stdlib_call(V("types.SimpleNamespace"),Args({},{{Sym("pg"),pygame}}));
        V display_backend=pm_scaled_display::new_ScaledDisplay(Args{sdl_owner});
        V actual_lib=callm(display_backend,Sym("_sdl"),Args{}),actual_window=callm(display_backend,Sym("_window"),Args{});
        V actual_renderer=callm(actual_lib,Sym("SDL_GetRenderer"),Args{actual_window});
        expect(actual_renderer.t==V::INST && callm(display_backend,Sym("_probe"),Args{actual_renderer}).truthy(),"linked SDL backend reads the actual rendered canary pixel");
        bool invalid_handle=false;try{callm(display_backend,Sym("_probe"),Args{V(1)});}catch(const PyError& e){invalid_handle=e.matches("RuntimeError");}
        expect(invalid_handle,"SDL backend rejects untyped raw pointer values");
        callm(display_backend,Sym("_release_window_surface"),Args{});
        expect(callm(actual_lib,Sym("SDL_GetRenderer"),Args{actual_window}).is_none(),"native display release actually destroys its SDL renderer");
        callm(display_module,Sym("set_mode"),Args{V::tuple({V(96),V(64)})});
        actual_renderer=callm(actual_lib,Sym("SDL_GetRenderer"),Args{callm(display_backend,Sym("_window"),Args{})});
        expect(actual_renderer.t==V::INST && callm(display_backend,Sym("_probe"),Args{actual_renderer}).truthy(),"set_mode recreates a working SDL renderer after release");
        {
        for(const V& raw:{V("0"),V("off"),V("FALSE"),V(" No \t"),V(0),V(false)})
            expect(!pm_native_multiworker::f_fastpath_enabled(Args{raw}).truthy(),"actual fastpath parser rejects each documented false spelling");
        for(const V& raw:{V(""),V("yes"),V(1),V(true),V("truth")})
            expect(pm_native_multiworker::f_fastpath_enabled(Args({},{{Sym("value"),raw}})).truthy(),"actual fastpath parser accepts the original other values and keyword binding");
        V environment=py::stdlib_attr(V("os"),V("environ"));
        V old_fastpath=callm(environment,Sym("get"),Args{V("PVP_SIM_FASTPATH")});
        struct RestoreFastpath {V environment,previous;~RestoreFastpath(){if(previous.is_none()){try{py_del(environment,V("PVP_SIM_FASTPATH"));}catch(const PyError&){}}else pvz::setitem(environment,V("PVP_SIM_FASTPATH"),previous);}} restore_fastpath{environment,old_fastpath};
        pvz::setitem(environment,V("PVP_SIM_FASTPATH"),V(" off "));
        expect(!pm_native_multiworker::f_fastpath_enabled(Args{}).truthy(),"fastpath reads live OS environment changes");
        pvz::setitem(environment,V("PVP_SIM_FASTPATH"),V("1"));
        V recipe_pg=gfx::make_pygame(),recipe_metrics=pvz::getattr(recipe_pg,Sym("__graphics_metrics__"));
        V recipe_transform=pvz::getattr(recipe_pg,Sym("transform"));
        recipe_metrics.at(V("lazy_pixels"))=V(true);recipe_metrics.at(V("cache_enabled"))=V(true);
        V recipe_source=callm(recipe_pg,Sym("Surface"),Args{V::tuple({V(9),V(7)}),V(65536)});
        callm(recipe_source,Sym("fill"),Args{V::tuple({V(33),V(77),V(121),V(255)})});
        V deferred_image=callm(recipe_transform,Sym("rotate"),Args{recipe_source,V(90)});
        expect(recipe_metrics.get(V("executions"))==V(0) && recipe_metrics.get(V("deferred"))==V(1),"pure deferred recipes do not claim an SDL transform execution");
        recipe_metrics.at(V("lazy_pixels"))=V(false);
        V eager_image=callm(recipe_transform,Sym("rotate"),Args{recipe_source,V(90)});
        expect(recipe_metrics.get(V("executions"))==V(1) && recipe_metrics.get(V("output_pixels"))==V(63),"eager frontend counts its actual successful SDL transform and output area");
        V real_source=callm(pygame,Sym("Surface"),Args{V::tuple({V(9),V(7)}),V(65536)});
        callm(real_source,Sym("fill"),Args{V::tuple({V(33),V(77),V(121),V(255)})});
        V real_rotated=callm(pvz::getattr(pygame,Sym("transform")),Sym("rotate"),Args{real_source,V(90)});
        V retained=*eager_image.box->inst->find_dyn(Sym("__materialized_pixels__"));
        expect(callm(pvz::getattr(pygame,Sym("image")),Sym("tobytes"),Args{retained,V("RGBA")})==callm(pvz::getattr(pygame,Sym("image")),Sym("tobytes"),Args{real_rotated,V("RGBA")}),"retained eager recipe pixels equal direct linked SDL pixels");
        expect(recipe_metrics.get(V("executions"))==V(1),"client or direct SDL transforms outside the frontend scope are excluded");
        recipe_metrics.at(V("defer_capture"))=V(true);
        callm(recipe_transform,Sym("rotate"),Args{recipe_source,V(180)});
        expect(recipe_metrics.get(V("executions"))==V(1) && recipe_metrics.get(V("deferred"))==V(2),"capture demand actually avoids eager materialization");
        recipe_metrics.at(V("copy_on_write"))=V(false);
        V physical_copy=callm(eager_image,Sym("copy"),Args{});
        expect(recipe_metrics.get(V("copies"))==V(1) && recipe_metrics.get(V("copy_bytes"))==V(252),"physical copy counters use the real copied SDL surface pitch and height");
        callm(eager_image,Sym("fill"),Args{V::tuple({V(1),V(2),V(3),V(255)})});
        expect(!eager_image.box->inst->find_dyn(Sym("__materialized_pixels__")),"mutation invalidates only its private eager pixel snapshot");
        expect(callm(physical_copy,Sym("get_at"),Args{V::tuple({V(0),V(0)})})==V::tuple({V(33),V(77),V(121),V(255)}),"physical copy pixels survive mutation of their source");
        bool transform_rejected=false;V old_count=recipe_metrics.get(V("executions"));
        try{callm(recipe_transform,Sym("rotate"),Args{V("bad source"),V(90)});}catch(const PyError& e){transform_rejected=e.matches("TypeError");}
        expect(transform_rejected && recipe_metrics.get(V("executions"))==old_count,"failed transform requests do not create successful execution counts");
        recipe_metrics.at(V("defer_capture"))=V(false);
        V actual_rotozoom=callm(recipe_transform,Sym("rotozoom"),Args{recipe_source,V(90),V(1.5)});
        V direct_rotozoom=callm(pvz::getattr(pygame,Sym("transform")),Sym("rotozoom"),Args{real_source,V(90),V(1.5)});
        V cached_rotozoom=*actual_rotozoom.box->inst->find_dyn(Sym("__materialized_pixels__"));
        expect(callm(actual_rotozoom,Sym("get_size"),Args{})==callm(direct_rotozoom,Sym("get_size"),Args{}) && callm(pvz::getattr(pygame,Sym("image")),Sym("tobytes"),Args{cached_rotozoom,V("RGBA")})==callm(pvz::getattr(pygame,Sym("image")),Sym("tobytes"),Args{direct_rotozoom,V("RGBA")}),"rotozoom records and executes its actual zoom and rotation with matching geometry and pixels");
        V actual_mixer=pvz::getattr(pygame,Sym("mixer"));callm(actual_mixer,Sym("init"),Args{});
        callm(actual_mixer,Sym("set_num_channels"),Args{V(24)});callm(actual_mixer,Sym("set_reserved"),Args{V(16)});
        callm(actual_mixer,Sym("quit"),Args{});callm(actual_mixer,Sym("init"),Args{});
        expect(callm(actual_mixer,Sym("get_num_channels"),Args{})==V(8),"actual SDL mixer reinitializes eight channels after a reserved 24-channel session");
        V free_channel=callm(actual_mixer,Sym("find_channel"),Args{});
        expect(free_channel.t==V::INST && callm(free_channel,Sym("get_sound"),Args{}).is_none(),"mixer restart releases reservations and stale channel sound ownership");
        }
        {
            V pending_module=py::stdlib_module(V("_native_contract_late"));
            V captured_original=pvz::getattr(pending_module,Sym("probe"));
            py::register_module_attrs("_native_contract_late",+[](Sym name)->V{if(name==Sym("probe"))return V::func([](const Args&){return V(17);});return V();});
            V actual_module=py::module_ns(V("_native_contract_late"));
            pvz::setattr(actual_module,Sym("probe"),V::func([](const Args&){return V(29);}));
            expect(captured_original.call(Args{})==V(17),"captured original module function stays original after late registration and replacement");
            expect(py::stdlib_call(V("_native_contract_late.probe"),Args{})==V(29),"fresh module lookup invokes the actual replacement");
            V captured_replacement=pvz::getattr(pending_module,Sym("probe"));
            pvz::setattr(actual_module,Sym("probe"),V::func([](const Args&){return V(31);}));
            expect(captured_replacement.call(Args{})==V(29),"captured module function values do not rebind on a later patch");
            V native_function=py::with_globals(V::func([](const Args&){return py::getframe();}),V::dict(),V(std::string("_native_contract_identity")));
            V native_identity=pvz::getattr(native_function,Sym("__code__"));
            V locals=py_dict({{V("source"),V(41)}});
            V actual_frame=py::call_site(V(Sym("patch:_native_contract_identity")),0,locals,native_function,Args{});
            expect(py_is(actual_frame.get(V("f_code")),native_identity) && py_is(actual_frame.get(V("f_locals")),locals),"fixed native patch identifiers preserve actual caller identity and locals after text ownership changes");
            V wrong_frame=py::call_site(V(Sym("patch:_different_native_contract_identity")),0,locals,native_function,Args{});
            expect(!py_is(wrong_frame.get(V("f_code")),native_identity),"different native patch identifiers remain distinct");
        }
        {
            V front=gfx::make_pygame(),settings=pvz::getattr(front,Sym("__graphics_metrics__"));settings.at(V("local_pixels"))=V(true);
            V recorder=pvz::getattr(front,Sym("__recorder__"));
            V image=callm(front,Sym("Surface"),Args{V::tuple({V(12),V(10)}),V(65536)});
            callm(image,Sym("fill"),Args{V::tuple({V(11),V(22),V(33),V(255)})});
            callm(recorder,Sym("begin_frame"),Args{V(1)});callm(recorder,Sym("blit"),Args{image,V::tuple({V(0),V(0)})});
            V frame=callm(recorder,Sym("snapshot"),Args{}),packet=pvz::getattr(recorder,Sym("latest_pixels"));
            V description=frame.get(V("commands")).idx(0).get(V("surface"));
            expect(!packet.is_none() && py_is(pvz::getattr(packet,Sym("frame")),frame),"recorded native frame owns an actual local FramePixels packet");
            V pixels=callm(packet,Sym("get"),Args{frame,description});
            expect(pixels.t==V::INST && py_is(pixels,callm(packet,Sym("get"),Args{frame,description})),"frame-local pixels execute once and retain a stable actual SDL Surface");
            callm(image,Sym("fill"),Args{V::tuple({V(90),V(80),V(70),V(255)})});
            expect(callm(pixels,Sym("get_at"),Args{V::tuple({V(0),V(0)})})==V::tuple({V(11),V(22),V(33),V(255)}),"later source mutations preserve the completed packet pixels");
            expect(callm(packet,Sym("get"),Args{pvz::deepcopy(frame),description}).is_none() && callm(packet,Sym("get"),Args{frame,pvz::deepcopy(description)}).is_none(),"foreign or copied wire frames and descriptions do not gain local pixel access");
            expect(pvz::getattr(packet,Sym("bytes"))>V(0) && pvz::getattr(packet,Sym("bytes"))<=V(24*1024*1024),"actual retained recipe pixel budget is positive and bounded");
            settings.at(V("local_pixels"))=V(false);callm(recorder,Sym("begin_frame"),Args{V(2)});callm(recorder,Sym("snapshot"),Args{});
            expect(pvz::getattr(recorder,Sym("latest_pixels")).is_none(),"disabling local pixels actually omits the next frame packet");
        }
        {
            pm_ui_expansion_assets::init();V saved=pm_ui_expansion_assets::TEMPLATE_ART;
            pm_ui_expansion_assets::TEMPLATE_ART=py_dict({{V("template-canary"),V("actual-body")}});
            V dictionary=pm_ui_expansion_assets::new_TemplateAtlas(Args{py_dict({{V("actual-body-layer"),V(42)},{V("changed-body-layer"),V(43)}})});
            expect(rd(dictionary,V("template-canary-layer"))==V(42) && dictionary.len()==2 && !dictionary.contains(V("template-canary-layer")),"TemplateAtlas resolves an actual stored template without adding an alias entry");
            expect(callm(dictionary,Sym("get"),Args{V("template-canary-layer")}).is_none(),"TemplateAtlas.get and membership preserve original dict semantics");
            pm_ui_expansion_assets::TEMPLATE_ART.at(V("template-canary"))=V("changed-body");
            expect(rd(dictionary,V("template-canary-layer"))==V(43) && callm(dictionary,Sym("__missing__"),Args{V("template-canary-layer")})==V(43),"TemplateAtlas reads its live template map and explicit missing method");
            expect(py_is(py::type(dictionary),pm_ui_expansion_assets::cls_TemplateAtlas()) && py::isinstance_v(dictionary,pm_ui_expansion_assets::cls_TemplateAtlas()).truthy() && isinstance(dictionary,"dict"),"TemplateAtlas retains its real derived and dictionary type identities");
            bool absent=false;try{(void)rd(dictionary,V("unknown-layer"));}catch(const PyError& e){absent=e.matches("KeyError");}expect(absent,"unknown TemplateAtlas assets still fail with KeyError");
            pm_ui_expansion_assets::TEMPLATE_ART=saved;
        }
        {
            V alpha_image=callm(pygame,Sym("Surface"),Args{V::tuple({V(10),V(10)}),V(65536)});
            callm(alpha_image,Sym("fill"),Args{V::tuple({V(0),V(0),V(0),V(0)})});
            callm(alpha_image,Sym("set_at"),Args{V::tuple({V(1),V(1)}),V::tuple({V(1),V(2),V(3),V(1)})});
            callm(alpha_image,Sym("set_at"),Args{V::tuple({V(4),V(4)}),V::tuple({V(1),V(2),V(3),V(8)})});
            V strict=callm(alpha_image,Sym("get_bounding_rect"),Args({},{{Sym("min_alpha"),V(8)}}));
            V default_bounds=callm(alpha_image,Sym("get_bounding_rect"),Args{});
            expect(py_eq(strict,callm(pygame,Sym("Rect"),Args{V(4),V(4),V(1),V(1)})) && py_eq(default_bounds,callm(pygame,Sym("Rect"),Args{V(1),V(1),V(4),V(4)})),"SDL alpha bounds apply the actual keyword threshold rather than silently using one");
            expect(py_eq(strict,callm(alpha_image,Sym("get_bounding_rect"),Args{V(8)})),"positional and keyword alpha thresholds select identical pixels");
        }
        {
            V nested=V::list({py_dict({{V("values"),V::list({V(1)})}})}),cloned=pm_cppcore::f_fast_deepcopy(Args{nested});
            rd(cloned.idx(0),V("values")).append(V(2));
            expect(rd(nested.idx(0),V("values")).len()==1 && rd(cloned.idx(0),V("values")).len()==2,"standalone copy helper makes an actual independent nested data copy");
            V module=pm_cppcore::module_ns(),prior=pvz::getattr(module,Sym("status"));
            pvz::setattr(module,Sym("status"),V::func([](const Args&){return py_dict({{V("active"),V(true)}});}));
            expect(callm(module,Sym("status"),Args{}).get(V("active")).truthy(),"cppcore module lookup invokes an actual replaced status function");
            pvz::setattr(module,Sym("status"),prior);
        }
        {
            bool outside=false;try{py::native_hook(V("runtime.current_function"),Args{});}catch(const PyError& e){outside=e.matches("RuntimeError");}expect(outside,"current native function rejects use outside an executing function");
            V recursive=V::func([](const Args& args)->V{int n=int(args.pos.at(0).num());if(!n)return V(0);return py::native_hook(V("runtime.current_function"),Args{}).call(Args{V(n-1)})+V(n);});
            expect(recursive.call(Args{V(6)})==V(21),"immutable native local self-reference executes real recursion without an uninitialized capture");
            auto token=std::make_shared<int>(7);std::weak_ptr<int> weak=token;V callback;
            callback=V::func([&callback,weak,token](const Args&){callback=V();return V(!weak.expired());});token.reset();
            V alive_during_call=callback.call(Args{});
            expect(alive_during_call.truthy() && weak.expired(),"executing native callback survives owner replacement and releases its capture after returning");
        }

        expect(callm(V("海盗船长-身0"),Sym("rstrip"),Args{V("0")})==V("海盗船长-身") && callm(V("0frame0"),Sym("rstrip"),Args{V("0")})==V("0frame"),"animation frame suffix stripping preserves the leading characters");
        expect(callm(V("xy层xy"),Sym("lstrip"),Args{V("yx")})==V("层xy") && callm(V("层边层"),Sym("strip"),Args{V("层")})==V("边"),"strip honors character sets and Unicode codepoint boundaries");
        expect(callm(V("\xE3\x80\x80 x \xC2\xA0"),Sym("strip"),Args{})==V("x") && callm(V("  x  "),Sym("lstrip"),Args{})==V("x  "),"default whitespace stripping and one-sided stripping retain Python semantics");

        {
            V original=V::func([](const Args&){return V(99);}),wrapper=V::func([](const Args&){return V(42);});
            pvz::setattr(original,Sym("__name__"),V("original_damage"));pvz::setattr(original,Sym("sentinel"),V(17));
            V decorated=py::stdlib_call(V("functools.wraps"),Args{original}).call(Args{wrapper});
            expect(py_is(decorated,wrapper) && decorated.call(Args{})==V(42) && py_is(pvz::getattr(decorated,Sym("__wrapped__")),original),"wraps preserves the executing wrapper body and actual original function link");
            expect(pvz::getattr(decorated,Sym("__name__"))==V("original_damage") && pvz::getattr(decorated,Sym("sentinel"))==V(17),"wraps copies real function metadata and attribute mapping");
            V clock=V::list({V(0)});V callback=V::func([clock](const Args& args){return callm(clock,Sym("__setitem__"),Args{V(0),clock.idx(0)+args.pos.at(0)});});callback.call(Args{V(.004)});
            expect(clock.idx(0)==V(.004),"native clock callbacks mutate their real shared list through __setitem__");
        }

        {
            struct RealDelegate final:PyObj {V target;bool call_method(Sym name,const Args& args,V& result)override{if(name!=Sym("__getattr__"))return false;result=pvz::getattr(target,args.pos.at(0).sym());return true;}};
            auto proxy=std::make_shared<RealDelegate>();proxy->target=py::new_object();pvz::setattr(proxy->target,Sym("capacity"),V(4));V object=V::inst(proxy);
            expect(pvz::getattr(object,Sym("capacity"),V(0))==V(4) && pvz::hasattr(object,Sym("capacity")),"default attribute lookup and hasattr invoke an actual native __getattr__ delegate");
            expect(pvz::getattr(object,Sym("missing"),V(7))==V(7) && !pvz::hasattr(object,Sym("missing")),"delegated missing attributes retain default and hasattr behavior");
        }
        V json_error=py::make_exc(V("JSONDecodeError"),Args{V("invalid JSON")},"");
        expect(isinstance(json_error,"ValueError"),"JSONDecodeError retains ValueError ancestry");
        expect(!isinstance(json_error,"TypeError"),"JSONDecodeError does not match unrelated TypeError");
        expect(isinstance(py::make_exc(V("FileNotFoundError"),Args{},""),"OSError"),"file errors retain OSError ancestry");
        expect(isinstance(py::make_exc(V("KeyError"),Args{},""),"LookupError"),"key errors retain LookupError ancestry");
        expect(isinstance(py::make_exc(V("TabError"),Args{},""),"IndentationError"),"TabError retains its actual direct parent");
        V raises=callm(tc,Sym("assertRaises"),Args{py::exc_type(V("ValueError"))});
        callm(raises,Sym("__enter__"),Args{});
        expect(callm(raises,Sym("__exit__"),Args{py::exc_type(V("JSONDecodeError")),json_error,V::none()}).truthy(),"original assertion adapter accepts subclass exceptions");
        V window=pm_performance_window::new_BattleWindow(Args{});
        V window_type=py::type(window);
        V another_window=window_type.call(Args{});
        expect(py_is(window_type,pm_performance_window::cls_BattleWindow()) && another_window.t==V::INST && !py_is(window,another_window),"type(window) returns its real constructor and creates a fresh instance");

    } catch (const PyError& e) { ++failed; fprintf(stderr, "CONTRACT FAILED: mock adapter: %s\n", e.what()); }
    {
        V environment=V::dict(),shared=V::list({V(5)});
        V closure=make_native_closure(V("capture_contract"),V::tuple({V("amount"),V("shared")}),V::tuple({V(2),shared}),environment,[](const V& cells,const Args&){return native_cell_value(cells.idx(0))+native_cell_value(cells.idx(1)).idx(0);});
        V code=pvz::getattr(closure,Sym("__code__")),cells=pvz::getattr(closure,Sym("__closure__"));
        V clone=clone_native_closure(Args({code,environment},{{Sym("closure"),V::tuple({native_cell(Args{V(7)}),cells.idx(1)})}}));
        check("assertEqual",Args{closure.call(Args{}),V(7)},false);
        check("assertEqual",Args{clone.call(Args{}),V(12)},false);
        shared.idx(0)=V(9);pvz::setattr(cells.idx(0),Sym("cell_contents"),V(3));
        check("assertEqual",Args{closure.call(Args{}),V(12)},false);
        check("assertEqual",Args{clone.call(Args{}),V(16)},false);
        check("assertFalse",Args{V(isinstance(code,"CodeType"))},false);
        bool bad_count=false,bad_cell=false,bad_globals=false;
        try{clone_native_closure(Args({code,environment},{{Sym("closure"),V::tuple({})}}));}catch(const PyError& e){bad_count=e.matches("ValueError");}
        try{clone_native_closure(Args({code,environment},{{Sym("closure"),V::tuple({V(1),cells.idx(1)})}}));}catch(const PyError& e){bad_cell=e.matches("TypeError");}
        try{clone_native_closure(Args({code,V::dict()},{{Sym("closure"),cells}}));}catch(const PyError& e){bad_globals=e.matches("ValueError");}
        check("assertTrue",Args{V(bad_count&&bad_cell&&bad_globals)},false);
    }
    printf("FRAMEWORK CONTRACT: %d checks, %d failures\n",checked,failed);
    return failed==0;
}
// Optional, because creating real applications is deliberately outside the cheap
// framework checks that run before every old-suite module.
bool application_lifecycle_contract() {
    int checks=0,failures=0;
    auto check=[&](bool value){++checks;if(!value)++failures;};
    try {
        V pg=py::stdlib_module(V("pygame"));callm(pg,Sym("init"),Args{});
        V screen=callm(pvz::getattr(pg,Sym("display")),Sym("set_mode"),Args{V::tuple({V(960),V(640)})});
        V bridge=pm_native_bridge::C_NativeBridge::m_from_marshaled(Args{});
        for(int round=0;round<4;++round) {
            V api=py_dict({{V("event_get"),V::func([](const Args&){return V::list();})},{V("display_flip"),V::func([](const Args&){return V::none();})}});
            V app=pm_app::new_Application(Args({pg,screen,bridge},{{Sym("raw_api"),api},{Sym("asset_dir"),V("build/Release/图片")}}));
            std::weak_ptr<PyObj> weak=app.box->inst;
            V touch=pvz::getattr(app,Sym("touch")),backend=pvz::getattr(app,Sym("display_backend"));
            V original_close_room=pvz::getattr(app,Sym("close_room"));
            // Exercise the actual self-bound method restoration path.
            pvz::setattr(app,Sym("refresh"),pvz::getattr(app,Sym("refresh")));
            if(round==3) {
                pvz::setattr(app,Sym("close_room"),V::func([](const Args&)->V{throw PyError("OSError","lifecycle close canary");}));
                bool threw=false;try{callm(app,Sym("close"),Args{});}catch(const PyError& e){threw=e.matches("OSError");}
                check(threw && py_is(pvz::getattr(touch,Sym("app")),app) && !app.box->inst->find_dyn(Sym("__native_closed__")));
                pvz::setattr(app,Sym("close_room"),original_close_room);
            }
            original_close_room=V();
            callm(app,Sym("close"),Args{});callm(app,Sym("close"),Args{});
            check(pvz::getattr(touch,Sym("app")).is_none() && pvz::getattr(backend,Sym("app")).is_none());
            app=V();check(weak.expired());
        }
    }catch(const PyError& e){++failures;fprintf(stderr,"APP LIFECYCLE FAILED: %s\n",e.what());}
    printf("APP_LIFECYCLE {\"checks\":%d,\"failures\":%d,\"scope\":\"actual application close, receiver restoration, failed close retry and C++ weak ownership\"}\n",checks,failures);
    return failures==0;
}

// Runs in a fresh process before the general framework contract. CPython's
// idna import race has no native codec loader; exercise real application host
// creation and transport shutdown here instead of pretending to run Python -c.
bool native_platform_contract() {
    int checks=0,failures=0;auto check=[&](bool value){++checks;if(!value)++failures;};
    try {
        V policy=pm_gc_policy::module_ns();
        check(!pvz::getattr(policy,Sym("supported")).truthy());
        check(pvz::getattr(policy,Sym("backend"))==V("c++-raii"));
        check(!callm(policy,Sym("apply"),Args{V("old")}).truthy());
        check(!callm(policy,Sym("apply"),Args{V("new")}).truthy());
        callm(policy,Sym("release"),Args{V("old")});callm(policy,Sym("release"),Args{V("old")});
        check(!callm(policy,Sym("active"),Args{}).truthy());callm(policy,Sym("release"),Args{V("new")});
        bool created=false;
        V driver=V::func([&](const Args& args){V app=args.pos.at(0);if(args.pos.at(1)==V(2)){
            callm(app,Sym("action"),Args{V::tuple({V("menu"),V("host")})});
            V probe=py::stdlib_call(V("socket.socket"),Args{});
            callm(probe,Sym("bind"),Args{V::tuple({V("127.0.0.1"),V(0)})});
            V port=callm(probe,Sym("getsockname"),Args{}).idx(1);callm(probe,Sym("close"),Args{});
            V state=pvz::getattr(app,Sym("state"));state.at(V("network_mode"))=V("direct");state.at(V("port"))=py::str(port);
            callm(app,Sym("action"),Args{V::tuple({V("menu"),V("create_host")})});
            V transport=pvz::getattr(app,Sym("transport"),V::none());created=transport.has()&&!transport.is_none();
            printf("NATIVE_HOST_CREATION created=%d port=%s message=%s\n",int(created),py_str(port).c_str(),py_str(py::m_get(state,V("message"),V(""))).c_str());
            pvz::setattr(app,Sym("running"),V(false));
        }return V::none();});
        pm_app::f_run(Args({},{{Sym("auto_test"),driver}}));check(created);
    }catch(const std::exception& error){++failures;fprintf(stderr,"NATIVE_PLATFORM_ERROR %s\n",error.what());}
    printf("NATIVE_PLATFORM {\"checks\":%d,\"failures\":%d}\n",checks,failures);return failures==0;
}

// Optional diagnostic: actual production callbacks and intermediates from the
// original cross-system projectile fixture. It does not replay a Python result.
bool projectile_diagnostic() {
    int differences=0;V type=pm_test_pvp_content_acceptance::cls_ContentAcceptance(),test;
    try {
        callm(type,Sym("setUpClass"),Args{});test=type.call(Args{V("native_projectile_diagnostic")});
        V battle=callm(test,Sym("make"),Args{V::list({V("plant:原始豌豆射手")}),V::list({V("secret:毒气")})});
        V game=pvz::getattr(battle,Sym("g")),ns=pvz::getattr(pvz::getattr(battle,Sym("patch")),Sym("ns"));
        V target=callm(test,Sym("obj"),Args{battle,V("zombie:豌豆僵尸"),V(700)}),other=callm(test,Sym("obj"),Args{battle,V("zombie:普通僵尸"),V(730)});
        V center=rd(ns,V("__pvz_sb_plant_zombie_head_center")).call(Args{game,target});
        for(V probe_rows=V::list({V::tuple({V("原始豌豆射手"),V("豌豆"),V(30)}),V::tuple({V("原始豌豆射手"),V("火豆"),V(60)}),V::tuple({V("原始豌豆射手"),V("蓝火豆"),V(90)}),V::tuple({V("甜椒投手"),V("西瓜"),V(60)}),V::tuple({V("小喷菇"),V("泡泡"),V(5)})});const V& row:probe_rows.items()) {
            callm(target,Sym("update"),Args{py_dict({{V("血量"),V(1000)},{V("防具"),V("")},{V("防具血量"),V(0)},{V("手持"),V("")},{V("手持血量"),V(0)}})});
            pvz::setitem(rd(target,V("位置")),V(2),V(0));pvz::setitem(other,V("血量"),V(1000));pvz::setitem(game,V("实体"),V::list());
            V source=py_dict({{V("植物"),row.idx(0)},{V("_pvp_owner"),V("plant")}});if(row.idx(0)!=V("小喷菇"))source.at(V("_pvp_content"))=row.idx(0);
            {py::WithGuard context(callm(pvz::getattr(battle,Sym("targets")),Sym("context"),Args{V("zombie"),V("plant"),V("plants"),source}));rd(game,V("新增实体")).call(Args{row.idx(1),V(1),V::list({center.idx(0),center.idx(1),V(2),V(0)})});}
            V entity=rd(game,V("实体")).idx(-1);V report=py_dict({{V("content"),row.idx(0)},{V("shot"),row.idx(1)},{V("before_entity"),pvz::deepcopy(entity)},{V("center"),center},{V("expected_damage"),row.idx(2)}});
            rd(ns,V("__pvz_sb_plant_zombie_head_hit_scan")).call(Args{game});
            V damage=V(1000)-rd(target,V("血量"));report.at(V("actual_damage"))=damage;report.at(V("after_entity"))=entity;report.at(V("velocity"))=rd(target,V("位置")).idx(2);report.at(V("other_damage"))=V(1000)-rd(other,V("血量"));
            if(damage!=row.idx(2))++differences;printf("PROJECTILE_DIAGNOSTIC %s\n",dump(report).c_str());
        }
    }catch(const PyError& error){++differences;fprintf(stderr,"PROJECTILE_DIAGNOSTIC_ERROR %s\n",error.what());}
    if(test.has())try{callm(test,Sym("doCleanups"),Args{});}catch(const PyError&){++differences;}
    try{callm(type,Sym("tearDownClass"),Args{});}catch(const PyError&){++differences;}
    printf("PROJECTILE_DIAGNOSTIC_DIFFERENCES %d\n",differences);return differences==0;
}

// Optional diagnostics execute the actual original fixture helpers and product.
bool contact_animation_diagnostic(){
 int errors=0;V type=pm_test_pvp_70_features::cls_PvP70Tests(),test;
 try{
  callm(type,Sym("setUpClass"),Args{});test=type.call(Args{V("native_contact_diagnostic")});
  V battle;
  // Use the catalog constant actually consumed by the original fixture.
  V grabber=pm_pvp70_catalog::GRABBER;
  battle=callm(test,Sym("new"),Args({},{{Sym("plants"),V::list({V("plant:")+grabber})}}));
  V root=callm(test,Sym("deploy"),Args{battle,V("plant"),V("plant:")+grabber,V(6)});
  V head=callm(test,Sym("pinned_head"),Args{battle,root,V(11.5)});
  V zombie=callm(test,Sym("zombie"),Args({battle,V("zombie:普通僵尸"),V(14)},{{Sym("hold"),V(false)}}));
  for(int tick=0;tick<2500;++tick){
   callm(battle,Sym("_step_original"),Args{});
   if(tick%120==0)printf("CONTACT_DIAGNOSTIC %s\n",dump(py_dict({{V("tick"),V(tick+1)},{V("zpos"),rd(zombie,V("位置"))},{V("bite"),rd(zombie,V("啃咬"))},{V("head_hp"),rd(head,V("植物血"))},{V("head_cell"),rd(head,V("坐标"))},{V("head_point"),py::m_get(head,V("_pvp_head_point"))}})).c_str());
  }
 }catch(const PyError& e){++errors;fprintf(stderr,"CONTACT_DIAGNOSTIC_ERROR %s\n",e.what());}
 if(test.has())try{callm(test,Sym("doCleanups"),Args{});}catch(const PyError&){++errors;}
 try{callm(type,Sym("tearDownClass"),Args{});}catch(const PyError&){++errors;}
 type=pm_test_pvp_70_animation::cls_AnimationTests();test=V();
 try{
  callm(type,Sym("setUpClass"),Args{});test=type.call(Args{V("native_animation_diagnostic")});
  V battle=callm(test,Sym("new"),Args({},{{Sym("plants"),V::list({V("plant:坚果")})}}));
  callm(test,Sym("deploy"),Args{battle,V("plant"),V("plant:坚果"),V(10)});
  V zombie=callm(test,Sym("zombie"),Args({battle,V("zombie:海盗船长"),V(12.5)},{{Sym("hold"),V(false)}}));
  for(int tick=0;tick<420;++tick){
   callm(battle,Sym("step"),Args{V(1)});
   if(tick==14 || py::m_get(zombie,V("啃咬"),V(0)).truthy()){
    V report=py_dict({{V("tick"),V(tick+1)},{V("zombie"),pvz::deepcopy(zombie)},{V("layers"),pm_test_pvp_70_animation::f_layers(Args{battle,zombie})}});
    printf("CAPTAIN_DIAGNOSTIC %s\n",dump(report).c_str());
    if(py::m_get(zombie,V("啃咬"),V(0)).truthy()){
     for(int k=0;k<8;++k)callm(battle,Sym("step"),Args{V(1)});
     printf("CAPTAIN_BITE_LAYERS %s\n",dump(pm_test_pvp_70_animation::f_layers(Args{battle,zombie})).c_str());break;
    }
   }
  }
 }catch(const PyError& e){++errors;fprintf(stderr,"CAPTAIN_DIAGNOSTIC_ERROR %s\n",e.what());}
 if(test.has())try{callm(test,Sym("doCleanups"),Args{});}catch(const PyError&){++errors;}
 try{callm(type,Sym("tearDownClass"),Args{});}catch(const PyError&){++errors;}
 return errors==0;
}

}
