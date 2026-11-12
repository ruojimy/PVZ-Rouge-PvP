#include "sim/typed/attack_source.h"
#include <iostream>
#include <memory>
#include <stdexcept>
#include <string>
#include <utility>
using pvz::typed72::AttackSource;
namespace {
void require(bool condition,const char* message){if(!condition)throw std::runtime_error(message);}
}
int main(int argc,char** argv) {
    try {
        if(argc==2&&std::string(argv[1])=="--lifetime-only") {
            AttackSource retained;
            {auto name=std::make_unique<std::string>("普通僵尸");AttackSource live;live.bind_zombie_kind(*name);retained=live;}
            require(retained.zombie_name()=="普通僵尸","retained snapshot after native owner destruction");
            std::cout<<"retained source lifetime passed\n";return 0;
        }
        AttackSource copy,assigned,moved,move_assigned;
        {
            auto name=std::make_unique<std::string>("普通僵尸");
            AttackSource source;source.bind_zombie_kind(*name);
            require(source.has_zombie_name()&&source.zombie_name()=="普通僵尸","live initial kind");
            copy=source;
            *name="旗帜僵尸";
            require(source.zombie_name()=="旗帜僵尸","live transformed kind");
            require(copy.zombie_name()=="普通僵尸","copy must retain original value");
            assigned=source;
            moved=std::move(source);
            require(moved.zombie_name()=="旗帜僵尸","move must capture current value");
            *name="魅惑后变形";
            require(assigned.zombie_name()=="旗帜僵尸","assignment must not follow old unit");
            move_assigned=std::move(moved);
            source=source;
            require(source.zombie_name()=="魅惑后变形","self assignment keeps live binding");
        }
        require(copy.zombie_name()=="普通僵尸","copy survives owner destruction");
        require(assigned.zombie_name()=="旗帜僵尸","assigned survives owner destruction");
        require(moved.zombie_name()=="旗帜僵尸","moved-from metadata remains valid");
        require(move_assigned.zombie_name()=="旗帜僵尸","move-assigned survives owner destruction");
        AttackSource missing;AttackSource missing_copy(missing);
        require(!missing_copy.has_zombie_name(),"missing presence preserved");
        missing.zombie.set_null();AttackSource null_copy(missing);
        require(null_copy.has_zombie_name()&&null_copy.zombie_name().empty(),"null presence preserved");
        AttackSource string_source;string_source.zombie.set("元数据僵尸");
        AttackSource string_copy(string_source);string_source.zombie.set("变更");
        require(string_copy.zombie_name()=="元数据僵尸","owned metadata string copy");
        std::cout<<"source binding lifetime and value semantics passed\n";
        return 0;
    }catch(const std::exception& error){std::cerr<<error.what()<<'\n';return 1;}
}
