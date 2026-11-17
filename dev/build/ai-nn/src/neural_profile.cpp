// Research-only profiling wrapper. Same headless driver and kernel; timers stay out of state.
#include "core/function_profile.h"
#define main neural_unprofiled_main
#include "headless_match.cpp"
#undef main
int main(int argc,char** argv){
    const int result=neural_unprofiled_main(argc,argv);
    ainn::J profile=ainn::J::object();
    for(const auto& [name,row]:pvz::function_profile::snapshot())
        profile[name]={{"calls",row.calls},{"total_ms",row.total_ms},{"max_ms",row.max_ms}};
    std::cerr<<ainn::J{{"profile_enabled",pvz::function_profile::enabled()},
        {"functions",profile},{"returncode",result}}.dump()<<'\n';
    return result;
}
