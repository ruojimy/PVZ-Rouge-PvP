#pragma once
#include "sim/typed/targets.h"
#include <algorithm>
namespace pvz::typed72 {
inline std::vector<Cell> solo_open_cells(const TypedBattleState& world){
    const auto& map=world.terrain;
    std::vector<Cell> cells;
    for(int row=1;row+1<map.rows();++row)for(int col=0;col<map.cols();++col){
        const auto& tile=map.native_at(row,col);
        if(tile.plant.or_missing(false)||tile.block.or_missing("")!="空"||map.native_at(row-1,col).block.or_missing("")!="空")continue;
        const auto& floor=map.native_at(row+1,col).block;
        if(!floor.present()||floor.is_null()||floor.get().find("铁轨")!=std::string::npos||floor.get().find("铁路")!=std::string::npos)continue;
        if(!map.empty(row,col)||map.water(row,col))continue;
        if(!map.empty(row+1,col)||map.water(row+1,col))cells.push_back({row,col});
    }
    return cells;
}
template<class Match> void advance_solo_board(Match& match){
    auto& world=match.battle;auto& solo=world.solo;auto& rng=world.runtime.rng;
    if(solo.board_ready&&!solo.refill)return;
    if(solo.refill_wait>0){--solo.refill_wait;return;}
    const bool opening=!solo.board_ready;
    if(opening||solo.refill_step==0){
        solo.refill_cells=solo_open_cells(world);
        solo.stars_left=3;solo.cattails_left=1;solo.magnets_left=2;solo.pumpkins=0;
        if(!opening)solo.refill=std::min(24,int(solo.refill_cells.size()));
    }
    auto& cells=solo.refill_cells;
    if(opening)solo.facing=rng.randrange(2)?1:-1;
    auto draw=[&](auto accepts)->std::optional<Cell>{
        std::vector<size_t> choices;
        for(size_t i=0;i<cells.size();++i)if(accepts(cells[i]))choices.push_back(i);
        if(choices.empty())return {};
        const size_t offset=choices[size_t(rng.randrange(choices.size()))];
        const Cell result=cells[offset];cells.erase(cells.begin()+offset);return result;
    };
    const auto own=[&](Cell c){return solo.facing==1?c.x<35:c.x>35;};
    if(opening){
        const bool buster=std::find(solo.defenders.begin(),solo.defenders.end(),"plant:墓碑吞噬者")!=solo.defenders.end();
        for(int i=0;i<(buster?2:3);++i){
            auto pos=draw([&](Cell c){return own(c)&&!world.terrain.water(c.y+1,c.x);});if(!pos)break;
            auto& t=world.terrain.native_at(pos->y,pos->x);t.block.set("坟墓");t.grave_art.set(rng.randint(1,5));solo.graves.push_back(*pos);
        }
        if(!solo.graves.empty()){
            const auto g=solo.graves.front();auto& p=*world.heroes.hero(Seat::zombie).frame.position.get();
            p.x=(g.x+.5)*world.runtime.tile;p.y=(g.y+1.)*world.runtime.tile;
        }
        match.sync_terrain();solo.board_ready=true;
    }
    const int count=opening?std::min(int(cells.size()),16+3*solo.stage):std::min(1,int(cells.size()));
    for(int i=0;i<count;++i){
        const int step=opening?i:solo.refill_step;
        const int targets=opening&&!solo.boss()?3:1;
        const bool objective=step<targets;
        auto pos=draw([&](Cell c){return !objective||step>=2||(solo.facing==1?c.x>35:c.x<35);});
        if(!pos&&objective)pos=draw([](Cell){return true;});
        if(!pos)break;
        auto c=*pos;const double tile=world.runtime.tile;
        int facing=-solo.facing;if((c.x+1)%4==0||(facing==1&&c.x>63)||(facing==-1&&c.x<8))facing=-facing;
        const auto call=[&](const std::string& key,Cell where){return match.cold_admission.spawn(key,Seat::plant,{(where.x+.5)*tile,(where.y+1.)*tile},facing);};
        const auto& floor=world.terrain.native_at(c.y+1,c.x).block.get();
        const bool water=world.terrain.water(c.y+1,c.x);
        std::string key;
        if(objective){
            if(water)++c.y;
            auto p=match.factory.plant(c,solo.boss()?"黄金脑子":"脑子",facing);
            if(p)solo.objectives.push_back(p);
        }else{
            if(step<targets+(opening?8:2))key="plant:向日葵";
            else if(opening&&step<targets+11)key="plant:金盏花";
            else{
                std::vector<std::string> choices;
                for(const auto& k:solo.defenders){
                    if(k=="plant:向日葵"||k=="plant:金盏花"||k=="plant:墓碑吞噬者")continue;
                    if((k=="plant:地刺"||k=="plant:地刺王")&&floor!="草"&&floor!="土")continue;
                    if(!water&&(k=="plant:海蘑菇"||k=="plant:香蒲"||k=="plant:缠绕海草"))continue;
                    if((k=="plant:杨桃"&&solo.stars_left==0)||(k=="plant:香蒲"&&solo.cattails_left==0))continue;
                    if(water&&(k=="plant:磁力菇"||k=="plant:吸金磁")&&!solo.magnets_left)continue;
                    if(k=="plant:南瓜头"&&2*solo.pumpkins>=int(world.plant_roster->size()))continue;
                    choices.push_back(k);
                }
                if(choices.empty())continue;
                key=choices[size_t(rng.randrange(choices.size()))];
            }
            if(key=="plant:杨桃")--solo.stars_left;
            if(key=="plant:香蒲")--solo.cattails_left;
            if(water&&(key=="plant:磁力菇"||key=="plant:吸金磁"))--solo.magnets_left;
            if(key=="plant:南瓜头"){
                std::vector<Cell> overlays;
                for(const auto& p:*world.plant_roster){
                    const auto it=find_plant(*world.plant_roster,p->cell);
                    if(it&&world.plant_roster->at(*it)->kind!="南瓜头")overlays.push_back(p->cell);
                }
                if(!overlays.empty()){
                    cells.push_back(c);c=overlays[size_t(rng.randrange(overlays.size()))];call(key,c);++solo.pumpkins;
                }
            }else{
                if(water){
                    if(key=="plant:海蘑菇"||key=="plant:缠绕海草"||key=="plant:香蒲"||key=="plant:冰冻生菜")++c.y;
                    else call("plant:睡莲",{c.y+1,c.x});
                }else if(floor!="草"&&floor!="土"){
                    call("plant:花盆",c);--c.y;
                }
                call(key,c);
            }
        }
        if(!opening){++solo.refill_step;--solo.refill;solo.refill_wait=99;}
    }
    if(!opening&&!count)solo.refill=0;
}
template<class Match> void settle_solo_board(Match& match){
    auto& world=match.battle;auto& solo=world.solo;const auto tile=world.runtime.tile;
    const auto center=[&](const PlantRef& p){return Point{(p->cell.x+.5)*tile,(p->cell.y+.5)*tile};};
    auto& account=match.resources.accounts[seat_index(Seat::zombie)];
    if(solo.bite_brains){match.resources.create(Seat::zombie,std::exchange(solo.bite_brains,0),world.heroes.players.at(seat_index(Seat::zombie))->position,"plant_bite");}
    for(const auto& p:solo.marigold_hits)if(p->hp.or_missing(0.)>0.&&!p->dead.present()){
        match.resources.drop_coin(p->marigold_paid?10.:50.,center(p),p->marigold_paid?"silver":"gold");p->marigold_paid=true;
    }
    solo.marigold_hits.clear();
    std::erase_if(solo.objectives,[&](const auto& p){
        if(p->hp.or_missing(0.)>0.&&!p->dead.present()&&std::find(world.plant_roster->begin(),world.plant_roster->end(),p)!=world.plant_roster->end())return false;
        match.resources.drop_coin(solo.boss()?50.:10.,center(p),solo.boss()?"gold":"silver");
        if(++solo.brains<3&&solo.boss()){solo.refill=24;solo.refill_step=0;solo.refill_wait=0;}
        return true;
    });
    if(solo.brains>=3){
        std::vector<std::string> coins;for(const auto& r:match.resources.records())if(r.coin.present())coins.push_back(r.id);
        for(const auto& id:coins)match.resources.collect(id,Seat::zombie);
        return;
    }
    const auto& deck=match.deployment.players[seat_index(Seat::zombie)].deck;
    const bool has_army=std::any_of(world.targets->begin(),world.targets->end(),[](const auto& t){return t.unit&&t.unit->body.hp>0.&&!t.unit->protection.grave&&!t.unit->source.plant.present();});
    solo.bankrupt=!has_army&&std::none_of(deck.begin(),deck.end(),[&](const auto& key){
        const auto* entry=match.catalog.find(key);return entry&&entry->side=="zombie"&&entry->category!="secret"&&match.placement_view.player_card(Seat::zombie,key).cost<=account.balance;
    });
}
}
