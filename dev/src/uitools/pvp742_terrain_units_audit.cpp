#include "pg/pg.h"
#include "core/gil.h"
#include "data/datastore.h"
#include "sim/pvp/battle_api.h"
#include "sim/typed72_app/cold_export.h"
#include "sim/typed72_app/session.h"
#include "sim/typed/flood.h"
#include <nlohmann/json.hpp>
#include <algorithm>
#include <fstream>
#include <iostream>
#include <set>
using namespace pvz;
using J=nlohmann::json;
namespace {
void require(bool ok,const std::string& message){if(!ok)throw std::runtime_error(message);}
J unit(typed72app::Session& battle,const std::string& id){
    const auto view=battle.native_view();for(const auto& z:view.at("g").at("僵尸"))if(z.value("_pvp_id",std::string{})==id)return z;
    throw std::runtime_error("missing native zombie "+id);
}
std::string spawn(typed72app::Session& battle,const char* kind,double x,double y,double facing){
    const auto id=battle.spawn(std::string("zombie:")+kind,"zombie",x,y,facing,false);
    require(id.has_value(),std::string("spawn rejected: ")+kind);
    require(battle.fixture_place_zombie(*id,x,y,facing),"fixture placement rejected");
    battle.native_set(false,*id,{{"血量",1.e8},{"_pvp_max_hp",1.e8},{"出场",500}});
    return *id;
}
void attack(typed72app::Session& battle){
    if(battle.snapshot(false).at("command")!="attack")require(battle.command("zombie",{{"type","command"},{"seq",1}}).empty(),"attack command failed");
}
J trace(typed72app::Session& battle,const std::set<std::string>& ids){
    const auto view=battle.native_view();J out=J::array();for(const auto& z:view.at("g").at("僵尸"))if(ids.contains(z.value("_pvp_id",std::string{}))){
        J p;for(const char* key:{"_pvp_id","位置","跳跃cd","出场","分兵","分裂","手持","血量","大蒜"})if(z.contains(key))p[key]=z.at(key);out.push_back(std::move(p));
    }return out;
}
}
int main(int argc,char** argv){
    if(argc<2)return 2;
    SDL_SetMainReady();gil::init();data::set_data_dir("extract/data");pg::install_pygame();init_pvp_modules();
    J rows=J::array();int failures=0;
    auto test=[&](const std::string& name,auto run){J row={{"name",name}};try{row["evidence"]=run();row["passed"]=true;}catch(const std::exception& e){row["passed"]=false;row["error"]=e.what();++failures;}std::cerr<<J{{"name",name},{"passed",row["passed"]},{"error",row.value("error",std::string{})}}.dump()<<std::endl;rows.push_back(std::move(row));};
    test("production_flood_narrow_passage_24_32_64_rows",[]()->J{
        J cases=J::array();for(int height:{24,32,64})for(int row:std::set<int>{0,1,22,23,24,height-2,height-1}){
            if(row>=height)continue;std::vector<uint8_t> empty(size_t(height)*8,1),valid(height,1);
            if(row>0)empty[size_t(row-1)*8+2]=0;if(row+1<height)empty[size_t(row+1)*8+2]=0;
            typed72::FloodTerrain terrain(height,8,std::move(empty),std::move(valid));typed72::FloodState state;state.field->assign(size_t(height)*8,0);
            typed72::advance_flood(terrain,state,{false,false,{row,1},double(height-1)});
            const bool interior=row>0&&row+1<height;const int value=state.field->at(size_t(row)*8+2);
            require(interior?value==0:value==-4,"flood narrow gap/edge mismatch at height="+std::to_string(height)+" row="+std::to_string(row)+" value="+std::to_string(value));
            cases.push_back({{"height",height},{"row",row},{"narrow_gap_rejected",interior},{"field_value",value}});
        }return cases;
    });
    auto h=battle_from_scenario({{"seed",742},{"fixture_flat",true},{"durable_heroes",true}});
    const auto cold=typed72app::export_cold(h.battle,742);
    for(const char* kind:{"梯子僵尸","传送带僵尸"})test(std::string("natural_wall_build_")+kind,[&]()->J{
        auto b=typed72app::Session::create(cold,"性能固定场景");
        b->fixture_set_avatar("plant",{{"玩家位置",{2184,768,0,0}},{"玩家血量",1.e8}});
        b->fixture_set_avatar("zombie",{{"玩家位置",{2880,960,0,0}},{"玩家血量",1.e8}});
        for(int y=16;y<20;++y)for(int x=42;x<48;++x)b->fixture_ditu(y,x,{{"方块","土"},{"里方块","空"}});
        const auto builder=spawn(*b,kind,1992,960,1);attack(*b);
        J placed=J::array(),trail=J::array();int first=-1;
        for(int tick=0;tick<1000;++tick){b->step();if(tick%40==0)trail.push_back({{"room_tick",tick},{"builders",trace(*b,{builder})}});
            const auto terrain=b->map_tiles();
            for(size_t y=0;y<terrain.size();++y)for(size_t x=0;x<terrain[y].size();++x)if(terrain[y][x].value("kind",std::string{})=="梯子块"){
                if(first<0)first=tick;placed.push_back({{"row",y},{"col",x},{"belt",terrain[y][x].at("native").value("_pvp_belt",false)}});
            }
            if(!placed.empty())break;
        }
        require(!placed.empty(),"builder did not place a ladder/conveyor at a reachable vertical wall: "+trail.dump());
        const bool conveyor=std::string(kind)=="传送带僵尸";
        for(const auto& cell:placed)require(cell.at("belt").get<bool>()==conveyor,"conveyor terrain tag mismatch: "+cell.dump());
        const auto row=placed[0].at("row").get<int>(),col=placed[0].at("col").get<int>();
        const auto rider=spawn(*b,"普通僵尸",(col+.5)*48.,(row+1.)*48.,1);
        b->native_set(false,rider,{{"冰冻",2000},{"黄油",2000}});b->step();const auto ridden=unit(*b,rider);
        if(conveyor)for(const char* field:{"冰冻","黄油"})require(ridden.value(field,0.)==0.,std::string("belt did not clear ")+field);
        if(conveyor)require(ridden.at("位置").at(3).get<double>()<0.,"belt supplied no upward acceleration");
        else require(ridden.value("冰冻",0.)>1000.&&ridden.value("黄油",0.)>0.,"ordinary ladder incorrectly gained conveyor immunity");
        const auto terrain=b->map_tiles();require(terrain[row][col].at("native").value("_pvp_belt",false)==conveyor,"belt flag lost during terrain republish");
        J regression=J::array();for(int tick=0;tick<240;++tick){b->step();if(tick%8==0)regression.push_back({{"room_tick",tick},{"actors",trace(*b,{builder,rider})}});}
        return {{"first_placement_room_tick",first},{"placed",placed},{"rider",ridden},{"builder",unit(*b,builder)},{"trail",trail},{"regression24",regression},{"regression24_rng",b->rng_state()}};
    });
    auto oasis_handle=battle_from_scenario({{"seed",742},{"team_map","ea66000000000000000000000000000a"},{"mode","coop"},{"durable_heroes",true}});
    const auto oasis=typed72app::export_cold(oasis_handle.battle,742);
    for(int count:{4,40})test("oasis_left_high_platform_"+std::to_string(count),[&]()->J{
        auto b=typed72app::Session::create(oasis,"绿洲·扩展");
        for(const char* side:{"plant","plant2"})b->fixture_set_avatar(side,{{"玩家位置",{888,576,0,0}},{"玩家血量",1.e8}});
        b->fixture_set_avatar("zombie",{{"玩家位置",{3888,1248,0,0}},{"玩家血量",1.e8}});
        std::set<std::string> ids;for(int i=0;i<count;++i)ids.insert(spawn(*b,"普通僵尸",552.+(i%4)*.1,1248,1));attack(*b);
        J trail=J::array();double highest=1248.;int above_ground=0;
        for(int tick=0;tick<1400;++tick){b->step();if(tick%20==0){const auto actors=trace(*b,ids);for(const auto& z:actors){const double y=z.at("位置").at(1);highest=std::min(highest,y);if(y<1200)++above_ground;}trail.push_back({{"room_tick",tick},{"actors",actors}});}}
        require(highest<(count>=40?600.:1100.),"crowd stalled below the Oasis left platform: highest feet y="+std::to_string(highest));
        return {{"units",count},{"highest_feet_y",highest},{"above_ground_samples",above_ground},{"terrain_map","ea66000000000000000000000000000a"},{"trail",trail},{"final_rng",b->rng_state()}};
    });
    callm(h.battle,SY("close"),Args{});callm(oasis_handle.battle,SY("close"),Args{});
    std::ofstream(argv[1],std::ios::binary)<<J{{"passed",failures==0},{"failures",failures},{"cases",rows}}.dump();return failures?1:0;
}
