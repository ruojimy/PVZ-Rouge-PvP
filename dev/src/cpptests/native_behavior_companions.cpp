#include "cpptests/registry.h"
#include "sim/pvp/gen/pm_native_physics.h"
#include "sim/pvp/hand/hero_monitor.h"
#include <cstdio>
#include <functional>
#include "cpptests/gen/pm_test_pvp_native_physics.h"
#include "cpptests/gen/pm_test_pvp_native_targets.h"
#include "cpptests/gen/pm_test_pvp_triple_jump.h"
namespace pvz::pm_test_pvp_native_physics {
struct NativeBehavior0 : C_NativePhysicsTests { V m_native_behavior_companion(const Args& A); };
V NativeBehavior0::m_native_behavior_companion(const Args& A) {
    V L_engine;
    V L_ns;
    V L_params;
    V L_reference;
    V L_state;
    V L_tick;
    V L_tiles;
    V L_y;
    L_tiles = callm(pm_test_pvp_native_physics::module_ns(), SY("terrain"), Args{});
    { const int64_t b1_ = (int64_t)(V(7.0)).num(), e1_ = (int64_t)(V(10.0)).num(), s1_ = 1;
    for (int64_t i1_ = b1_; s1_ > 0 ? i1_ < e1_ : i1_ > e1_; i1_ += s1_) {
        L_y = V(double(i1_)); 
        pvz::setitem(rd(rd(L_tiles, L_y), V(19.0)), SV("方块"), SV("石"));
    }}
    { V ut2_ = py::as_seq(callm(self(), SY("physics"), Args{L_tiles})); L_engine = ut2_.idx(0); L_ns = ut2_.idx(1); } 
    L_state = callm(L_engine, SY("make_state"), Args{V(400.0), V(480.0)});
    L_reference = callm(self(), SY("reference"), Args{L_state, L_tiles});
    { const int64_t b3_ = 0, e3_ = (int64_t)(V(900.0)).num(), s3_ = 1;
    for (int64_t i3_ = b3_; s3_ > 0 ? i3_ < e3_ : i3_ > e3_; i3_ += s3_) {
        L_tick = V(double(i3_)); 
        L_params = py_dict({{SV("move"), ((L_tick < V(450.0)) ? V(V(1.0)) : V(V(-1.0)))}, {SV("jump_down"), V(py::in(L_tick, V::tuple({V(25.0), V(55.0), V(500.0), V(560.0)})))}, {SV("jump_held"), V(((L_tick % V(100.0)) < V(30.0)))}});
        (void)(callm(L_engine, SY("step"), [&]() -> Args { Args expanded_; expanded_.pos.push_back(L_state); auto keyword_=[&](Sym key_,const V& value_){ for(const auto& present_:expanded_.kw)if(present_.first==key_)throw PyError("TypeError","multiple values for keyword argument "+key_.str());expanded_.kw.emplace_back(key_,value_); }; { V mapping_=L_params; V keys_; if(mapping_.t==V::DICT || mapping_.t==V::OBJ) keys_=py::keys(mapping_); else if(mapping_.t==V::INST && pvz::hasattr(mapping_,SY("keys")))keys_=callm(mapping_,SY("keys"),Args{});else throw PyError("TypeError","argument after ** must be a mapping");V held_=py::iter_list(keys_);for(const V& key_:held_.items()){if(!key_.is_str() || key_.byt)throw PyError("TypeError","keywords must be strings");keyword_(key_.sym(),rd(mapping_,key_));} } return expanded_; }()));
        (void)(callm(self(), SY("ref_step"), [&]() -> Args { Args expanded_; expanded_.pos.push_back(L_reference); auto keyword_=[&](Sym key_,const V& value_){ for(const auto& present_:expanded_.kw)if(present_.first==key_)throw PyError("TypeError","multiple values for keyword argument "+key_.str());expanded_.kw.emplace_back(key_,value_); }; { V mapping_=L_params; V keys_; if(mapping_.t==V::DICT || mapping_.t==V::OBJ) keys_=py::keys(mapping_); else if(mapping_.t==V::INST && pvz::hasattr(mapping_,SY("keys")))keys_=callm(mapping_,SY("keys"),Args{});else throw PyError("TypeError","argument after ** must be a mapping");V held_=py::iter_list(keys_);for(const V& key_:held_.items()){if(!key_.is_str() || key_.byt)throw PyError("TypeError","keywords must be strings");keyword_(key_.sym(),rd(mapping_,key_));} } return expanded_; }()));
        (void)(callm(self(), SY("assert_native_state"), Args{L_state, L_reference, L_tick}));
    }}
    (void)(callm(self(), SY("assertEqual"), Args{V(900.0), rdm(L_state, &Obj::native_ticks, SV("native_ticks"))}));
    (void)(callm(self(), SY("assertEqual"), Args{V(3.6), (V(900.0) * pm_native_physics::NATIVE_DT)}));
    return V::none();
}

V make_companion_0() { init();auto p=std::make_shared<NativeBehavior0>();V v=V::inst(p);initcv_NativePhysicsTests(p.get());p->m___init__(Args{V("test_original_normal_full_block_matches_every_tick_on_ground_air_wall_and_landing")});return v; }
}
namespace pvz::pm_test_pvp_native_physics {
struct NativeBehavior1 : C_NativePhysicsTests { V m_native_behavior_companion(const Args& A); };
V NativeBehavior1::m_native_behavior_companion(const Args& A) {
    V L__;
    V L_a;
    V L_b;
    V L_original;
    V L_patched;
    { V ut1_ = py::as_seq(callm(self(), SY("physics"), Args{})); L_patched = ut1_.idx(0); L__ = ut1_.idx(1); } 
    { V ut2_ = py::as_seq(callm(self(), SY("physics"), Args({}, {{SY("original_infinite"), V(true)}}))); L_original = ut2_.idx(0); L__ = ut2_.idx(1); } 
    L_a = callm(L_patched, SY("make_state"), Args({V(400.0), V(350.0)}, {{SY("mode"), SV("我是僵尸")}}));
    L_b = callm(L_original, SY("make_state"), Args({V(400.0), V(350.0)}, {{SY("mode"), SV("我是僵尸")}}));
    { const int64_t b3_ = 0, e3_ = (int64_t)(V(2.0)).num(), s3_ = 1;
    for (int64_t i3_ = b3_; s3_ > 0 ? i3_ < e3_ : i3_ > e3_; i3_ += s3_) {
        L__ = V(double(i3_)); 
        (void)(callm(L_patched, SY("step"), Args({L_a}, {{SY("jump_down"), V(true)}})));
        (void)(callm(L_original, SY("step"), Args({L_b}, {{SY("jump_down"), V(true)}})));
    }}
    (void)(callm(self(), SY("assertEqual"), Args{rdm(L_a, &Obj::玩家位置, SV("玩家位置")), rdm(L_b, &Obj::玩家位置, SV("玩家位置"))}));
    (void)(callm(self(), SY("assertEqual"), Args{V(2.0), rdm(L_a, &Obj::玩家跳跃, SV("玩家跳跃"))}));
    (void)(callm(self(), SY("assertEqual"), Args{V(1.0), rdm(L_b, &Obj::玩家跳跃, SV("玩家跳跃"))}));
    (void)(callm(self(), SY("assertAlmostEqual"), Args{(V(250.0) * V(0.0048)), rdm(L_a, &Obj::speedmax, SV("speedmax"))}));
    return V::none();
}

V make_companion_1() { init();auto p=std::make_shared<NativeBehavior1>();V v=V::inst(p);initcv_NativePhysicsTests(p.get());p->m___init__(Args{V("test_zombie_infinite_jump_is_one_documented_operand_change")});return v; }
}
namespace pvz::pm_test_pvp_native_targets {
struct NativeBehavior2 : C_NativeTargetTests { V m_native_behavior_companion(const Args& A); };
V NativeBehavior2::m_native_behavior_companion(const Args& A) {
    V L_entity;
    V L_raw_hurt;
    L_entity = callm(self(), SY("source"), Args{});
    (void)(callm(a_g, SY("update"), Args({}, {{SY("僵尸"), V::list({a_proxy})}, {SY("实体"), V::list({L_entity})}, {SY("l"), V(0.0)}, {SY("name"), SV("豌豆")}, {SY("shanchu"), V(false)}})));
    L_raw_hurt = rd(pvz::getattr(a_targets, SY("originals")), SV("掉血"));
    {
      py::WithGuard wg1_(callm(a_targets, SY("context"), Args{SV("zombie"), SV("plant"), SV("entities"), L_entity}));
        (void)(py::native_hook(V("exec"), Args{a_pea_collision, a_g}));
    }
    (void)(callm(self(), SY("assertTrue"), Args{rd(a_g, SV("shanchu"))}));
    (void)(callm(self(), SY("assertEqual"), Args{V(16.0), rdm(rd(a_heroes, SV("zombie")), &Obj::玩家血量, SV("玩家血量"))}));
    (void)(callm(self(), SY("assertEqual"), Args{V(16.0), rdm(a_proxy, &Obj::血量, SV("血量"))}));
    (void)(callm(self(), SY("assertEqual"), Args{V(1.0), rdm(rd(a_heroes, SV("zombie")), &Obj::玩家倒地, SV("玩家倒地"))}));
    (void)(callm(self(), SY("assertEqual"), Args{V(1.0), rdm(rd(a_heroes, SV("zombie")), &Obj::玩家受伤, SV("玩家受伤"))}));
    (void)(callm(self(), SY("assertEqual"), Args{V(20.0), rdm(rd(a_heroes, SV("plant")), &Obj::玩家血量, SV("玩家血量"))}));
    (void)(callm(self(), SY("assertEqual"), Args{V(2.0), rdm(a_proxy, &Obj::大小, SV("大小"))}));
    return V::none();
}

V make_companion_2() { init();auto p=std::make_shared<NativeBehavior2>();V v=V::inst(p);initcv_NativeTargetTests(p.get());p->m___init__(Args{V("test_real_native_pea_collision_routes_original_damage_body_to_zombie_dave")});return v; }
}
namespace pvz::pm_test_pvp_triple_jump {
struct NativeBehavior3 : C_TripleJumpTests { V m_native_behavior_companion(const Args& A); };
V NativeBehavior3::m_native_behavior_companion(const Args& A) {
    V L_b;
    V L_physics;
    L_b = callm(self(), SY("battle"), Args({}, {{SY("plants"), V::list({pm_test_pvp_triple_jump::SECRET, SV("plant:向日葵")})}, {SY("zombies"), V::list({SV("zombie:脑光墓碑")})}}));
    L_physics = pvz::getattr(pvz::getattr(L_b, SY("engine")), SY("physics"));
    (void)(callm(self(), SY("assertIn"), Args{V(3.0), pvz::getattr(L_physics, SY("jump_limit_regions"))}));
    (void)(callm(self(), SY("assertEqual"), Args{callm(L_physics, SY("region_for_jump_limit"), Args{V::none()}), SV("jump_keydown")}));
    {
      V raises_mgr1_ = callm(self(), SY("assertRaises"), Args{py::exc_type(SV("Exception"))});
      V raises_value1_ = callm(raises_mgr1_, SY("__enter__"), Args{});
      bool raises_caught1_ = false;
      try {
        (void)(callm(L_physics, SY("region_for_jump_limit"), Args{V(9.0)}));
      } catch (const PyError& e) {
        raises_caught1_ = true;
        std::string message = e.what(); size_t colon = message.find(": "); if (colon != std::string::npos) message = message.substr(colon + 2);
        if (!callm(raises_mgr1_, SY("__exit__"), Args{py::exc_type(V(e.kind)), py::exc_value(e), V::none()}).truthy()) throw;
      }
      if (!raises_caught1_) callm(raises_mgr1_, SY("__exit__"), Args{V::none(), V::none(), V::none()});
    }
    return V::none();
}

V make_companion_3() { init();auto p=std::make_shared<NativeBehavior3>();V v=V::inst(p);initcv_TripleJumpTests(p.get());p->m___init__(Args{V("test_the_raised_cap_is_one_operand_byte")});return v; }
}
namespace pvz {size_t test_unsupported_count();std::string test_last_unsupported();}
namespace pvz::cpptests {
static bool run_companion(const std::string& id,V(*class_value)(),V(*make)(),const std::function<void(V&)>& body) {
    const auto unsupported=test_unsupported_count();const auto hero=pm_hero_guard::reported_violation_count();V cls,inst;std::string error;
    try {set_current_test("");cls=class_value();callm(cls,Sym("setUpClass"),Args{});set_current_test(id);inst=make();callm(inst,Sym("setUp"),Args{});body(inst);}catch(const std::exception& e){error=e.what();}
    if(inst.has()){try{callm(inst,Sym("tearDown"),Args{});callm(inst,Sym("doCleanups"),Args{});}catch(const std::exception& e){error+=std::string(" cleanup: ")+e.what();}}
    if(cls.has()){try{callm(cls,Sym("tearDownClass"),Args{});}catch(const std::exception& e){error+=std::string(" class cleanup: ")+e.what();}}
    if(error.empty())error=reference_consumption_error(id);
    if(test_unsupported_count()!=unsupported)error+=" unsupported: "+test_last_unsupported();
    if(pm_hero_guard::reported_violation_count()!=hero)error+=" hero guard violation";
    printf("NATIVE_BEHAVIOR_%s %s %s\n",error.empty()?"PASS":"FAIL",id.c_str(),error.c_str());return error.empty();
}
bool native_behavior_companion(const std::string& id) {

    if(id=="test_pvp_native_physics.NativePhysicsTests.test_original_normal_full_block_matches_every_tick_on_ground_air_wall_and_landing")return run_companion(id,[]()->V{pm_test_pvp_native_physics::init();return pm_test_pvp_native_physics::cls_NativePhysicsTests();},pm_test_pvp_native_physics::make_companion_0,[](V& v){as<pm_test_pvp_native_physics::NativeBehavior0>(v)->m_native_behavior_companion(Args{});});
    if(id=="test_pvp_native_physics.NativePhysicsTests.test_zombie_infinite_jump_is_one_documented_operand_change")return run_companion(id,[]()->V{pm_test_pvp_native_physics::init();return pm_test_pvp_native_physics::cls_NativePhysicsTests();},pm_test_pvp_native_physics::make_companion_1,[](V& v){as<pm_test_pvp_native_physics::NativeBehavior1>(v)->m_native_behavior_companion(Args{});});
    if(id=="test_pvp_native_targets.NativeTargetTests.test_real_native_pea_collision_routes_original_damage_body_to_zombie_dave")return run_companion(id,[]()->V{pm_test_pvp_native_targets::init();return pm_test_pvp_native_targets::cls_NativeTargetTests();},pm_test_pvp_native_targets::make_companion_2,[](V& v){as<pm_test_pvp_native_targets::NativeBehavior2>(v)->m_native_behavior_companion(Args{});});
    if(id=="test_pvp_triple_jump.TripleJumpTests.test_the_raised_cap_is_one_operand_byte")return run_companion(id,[]()->V{pm_test_pvp_triple_jump::init();return pm_test_pvp_triple_jump::cls_TripleJumpTests();},pm_test_pvp_triple_jump::make_companion_3,[](V& v){as<pm_test_pvp_triple_jump::NativeBehavior3>(v)->m_native_behavior_companion(Args{});});
    throw PyError("ValueError","Unknown native behavior companion");
}
}
