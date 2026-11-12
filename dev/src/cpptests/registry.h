// Old-suite test cases translated to C++ (tools/gen_cpp_tests.py writes registry.cpp).
#pragma once
#include "sim/pvp/pvprt.h"
#include <vector>

namespace pvz::cpptests {
struct Case {
    const char* module;     // test module (test_pvp_*)
    const char* binding;    // class name as bound in that module
    const char* cls;        // defining class
    V (*cls_value)();       // initializes the defining module, returns the class object
    std::vector<const char*> tests;
};
const std::vector<Case>& registry();
bool framework_contract();
void install_test_adapters();
void set_current_test(const std::string& id);   // module.Binding.test, "" outside a test body (bytecode_ref.cpp)
std::string reference_consumption_error(const std::string& id);   // "" unless captured invocations were left unreplayed
}  // namespace pvz::cpptests
