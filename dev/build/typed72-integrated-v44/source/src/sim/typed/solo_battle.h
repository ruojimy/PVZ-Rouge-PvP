#pragma once
#include "sim/typed/plant.h"
#include "sim/typed/terrain.h"
#include <algorithm>
#include <set>
#include <string>
#include <vector>
namespace pvz::typed72 {
enum class SoloMode { none, lottery, izombie };
struct SoloBattle {
    SoloMode mode=SoloMode::none;
    int stage=1,brains=0,refill=0,refill_step=0,refill_wait=0,wave_remainder=2;
    bool board_ready=false,first_soldier=true,bankrupt=false;
    int facing=1;
    std::vector<Cell> graves,refill_cells;
    int stars_left=3,cattails_left=1,magnets_left=2,pumpkins=0;
    std::vector<PlantRef> objectives,marigold_hits;
    std::vector<std::string> defenders{"plant:豌豆射手","plant:向日葵","plant:金盏花","plant:土豆地雷"};
    std::vector<std::string> lottery_zombies,lottery_plants;
    std::set<std::string> spent;
    int bite_brains=0;
    bool lottery()const{return mode==SoloMode::lottery;}
    bool izombie()const{return mode==SoloMode::izombie;}
    bool active()const{return mode!=SoloMode::none;}
    bool boss()const{return lottery()?stage%8==0:izombie()&&stage==19;}
    int available_graves(const WorldTerrain& terrain)const{
        return static_cast<int>(std::count_if(graves.begin(),graves.end(),[&](Cell c){return terrain.native_at(c.y,c.x).block.or_missing("")=="坟墓";}));
    }
    void prepare_plant(const PlantRef& p)const{
        const auto& k=p->kind;
        if(k=="冰冻生菜")return;
        if(k=="黄金蓓蕾"||k=="寒冰辣椒"||k=="石果子"||k=="窝瓜"||k=="樱桃炸弹"||k=="毁灭菇"||k=="寒冰菇"||k=="火爆辣椒"||k=="三叶草"){
            p->sleep.set(0.);p->biteable_blover=k=="三叶草";
        }else p->sleep.erase();
    }
    void plant_bitten(const PlantRef& plant,double previous){
        if(!izombie()||previous<=0.||plant->hp.get()>=previous)return;
        const auto& name=plant->kind;
        const bool lethal=plant->hp.get()<=0.;
        if(name!="黄金蓓蕾")plant->sleep.erase();
        if(name=="向日葵")bite_brains+=15;
        else if(name=="双子向日葵")bite_brains+=25;
        else if(name=="黄金蓓蕾"&&lethal)bite_brains+=200;
        else if(name=="阳光菇"&&lethal)bite_brains+=plant->grown.or_missing(0.)>0.?75:50;
        else if(name=="金盏花"&&!lethal&&std::find(marigold_hits.begin(),marigold_hits.end(),plant)==marigold_hits.end())marigold_hits.push_back(plant);
    }
};
}
