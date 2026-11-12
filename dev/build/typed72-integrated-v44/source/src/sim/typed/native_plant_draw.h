#pragma once
// Original 显示植物 (definitions bytecode, src/sim/gen/original_funcs.cpp fn_显示植物) and
// pvp/native_runtime.py NativeRuntime.draw_plants. Pure presentation of plant state, except
// the tomb eater's grave dust (增粒子), which the original emits from this draw on every
// drawn tick and which therefore consumes the battle RNG exactly where the original does.
#include "sim/typed/native_canvas.h"
#include "sim/typed/state.h"
#include "sim/typed/plant.h"
#include "sim/typed/terrain.h"
#include <functional>
namespace pvz::typed72 {
struct PlantDrawRules {
    std::vector<std::string> root_plants;   // 根茎叶植物
    std::vector<std::string> big_heads;     // 大头
    std::vector<std::string> lobbers;       // 投手植物
    std::map<std::string,double> pot_tops;  // 花盆顶 ("row-col" -> lift)
    std::string mode;                       // 模式
    std::vector<std::string> content_plants; // pvp content_catalog.PLANTS (reskinned originals)
};
// Content plants with their own drawers (flying, pvp61, pvp64, september, vines, pvp70):
// draw_plant returns true when it drew the plant itself.
class PlantDrawHooks {
public:
    virtual ~PlantDrawHooks()=default;
    virtual bool draw_plant(size_t index)=0;
    // native_runtime.draw_plants: _pvp_draw_lily when installed.
    virtual bool draw_lily(size_t index)=0;
    virtual bool is_shell(const CombatPlant&)const=0;
};
class NativePlantDraw {
public:
    NativePlantDraw(TypedBattleState& world,NativeCanvas& canvas,const PlantDrawRules& rules,
                    const std::shared_ptr<std::vector<std::string>>& secrets,const double& water_offset,std::function<int64_t()> target_plant)
        :world_(world),canvas_(canvas),rules_(rules),secrets_(secrets),water_offset_(water_offset),target_plant_(std::move(target_plant)){}
    PlantDrawHooks* hooks=nullptr;
    void draw_all();
    // The original 显示植物(l), without the pvp wrapper chain.
    void original(size_t index);
    // 显示植物(l) through the installed wrapper chain: content drawers, native_content's
    // reskin of content plants, native_expansion's pea angle, patch1501's tripea/stone.
    void show(size_t index);
    void expansion_layer(size_t index);
    void patch_layer(size_t index);
    void tripea_heads(const CombatPlant&);
    // pvp64 draw_lily (_pvp_draw_lily): the terrain-loop 睡莲块 riding the water bob.
    void lily(size_t index);
private:
    TypedBattleState& world_;
    NativeCanvas& canvas_;
    const PlantDrawRules& rules_;
    const std::shared_ptr<std::vector<std::string>>& secrets_;
    const double& water_offset_;
    std::function<int64_t()> target_plant_;
};
} // namespace pvz::typed72
