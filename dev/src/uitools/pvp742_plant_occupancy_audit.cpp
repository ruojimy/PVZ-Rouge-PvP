#include "sim/typed/content_plants70.h"
#include "sim/typed/projectile_rules.h"
#include "core/function_profile.h"
#include <nlohmann/json.hpp>
#include <chrono>
#include <fstream>
#include <iostream>
using J=nlohmann::json;namespace t=pvz::typed72;
namespace {
void require(bool ok,const char* what){if(!ok)throw std::runtime_error(what);}
struct Damage:t::ContentUnitDamage {void ordinary(size_t,double,double)override{throw std::logic_error("unexpected damage");}void surface(size_t,double,double)override{throw std::logic_error("unexpected surface damage");}};
struct Taunts:t::ContentTaunts {std::optional<t::ContentTarget> taunt_target(const t::ContentTarget&,std::optional<t::ContentTarget> next)override{return next;}};
struct Services:t::ContentPlant70Services {
 t::PlantRef spawn_tentacle_native(t::Cell,double)override{throw std::logic_error("unexpected spawn");}
 void register_tentacle(const t::PlantRef&,const t::Field<std::string>&)override{throw std::logic_error("unexpected registration");}
 void plant70_event(const t::Plant70Event&)override{throw std::logic_error("unexpected event");}
 void sync_terrain()override{throw std::logic_error("unexpected terrain publication");}
 void tentacle_knock(size_t,double)override{throw std::logic_error("unexpected knockback");}
};
struct Fixture {
 t::TypedBattleState world{742};t::CollisionCatalog catalog;Damage damage;Taunts taunts;Services services;std::vector<std::string> aquatic;
 t::ContentTargets targets{world,damage,catalog,4608.};t::ContentQueries queries{world,targets,taunts};t::ContentFrost frost{world};
 t::ContentPlants70 plants{world,queries,targets,frost,services,aquatic};
 Fixture(){world.runtime.tile=48.;world.world_width.set(4608.);world.world_height.set(1536.);world.heroes.tick=1;
  for(int y=0;y<32;++y){std::vector<t::TileRef> row;for(int x=0;x<96;++x){auto cell=std::make_shared<t::TerrainCell>();cell->block.set("空");cell->inner_block.set("空");row.push_back(cell);}world.terrain.grid.push_back(std::move(row));}}
 t::PlantRef add(t::Cell cell,bool head=false){auto p=std::make_shared<t::CombatPlant>(head?"抓人草触手":"坚果",cell,1.);p->hp.set(54.);p->max_hp.set(54.);p->source.owner.set("plant");p->source.id.set("p"+std::to_string(world.plant_roster_revision));if(head){p->source.content.set("抓人草触手");p->head_point.set({(cell.x+.25)*48.,(cell.y+.25)*48.});}world.add_plant(p);if(!world.terrain.outside(cell.y,cell.x))world.terrain.native_at(cell.y,cell.x).plant.set(true);return p;}
 bool alive(const t::PlantRef& p)const{return p->hp.or_missing(0.)>0.&&!p->dead.present()&&!p->ash.present();}
 bool slow_in(t::Cell cell,const t::PlantRef& exclude={})const{for(const auto& p:*world.plant_roster)if(p!=exclude&&alive(p)&&p->cell==cell)return true;return false;}
 t::WaterCells slow_only()const{t::WaterCells cells;for(const auto& h:*world.plant_roster)if(t::ContentPlants70::is_head(h)&&alive(h)){bool ordinary=false;for(const auto& p:*world.plant_roster)if(alive(p)&&!t::ContentPlants70::is_head(p)&&p->cell==h->cell){ordinary=true;break;}if(!ordinary)cells.emplace(h->cell.y,h->cell.x);}return cells;}
 void verify(){require(plants.head_only_cells()==slow_only(),"head-only projection diverged from original full scan");for(const auto& p:*world.plant_roster){require(plants.plant_in(p->cell)==slow_in(p->cell),"occupancy differs");require(plants.plant_in(p->cell,p)==slow_in(p->cell,p),"exclude/layer occupancy differs");}require(!plants.plant_in({-20,-20}),"empty outside cell was occupied");}
 J state(){J records=J::array(),marks=J::array(),heads=J::array();for(const auto& p:*world.plant_roster)records.push_back({{"id",p->source.id.get()},{"cell",{p->cell.y,p->cell.x}},{"hp",p->hp.get()},{"dead",p->dead.present()},{"head",t::ContentPlants70::is_head(p)}});for(int y=0;y<32;++y)for(int x=0;x<96;++x)if(world.terrain.native_at(y,x).plant.present())marks.push_back({y,x});for(auto [y,x]:plants.head_only_cells())heads.push_back({y,x});return {{"plants",records},{"marked_cells",marks},{"head_only",heads}};}
};
J work(const t::ContentPlants70::OccupancyWork& w){return {{"rebuilds",w.rebuilds},{"indexed_plants",w.indexed_plants},{"queries",w.queries},{"candidates",w.candidates},{"full_scan_candidate_upper_bound",w.full_scan_candidates}};}
}
int main(int argc,char** argv){
 if(argc<2)return 2;J checks=J::array();int failures=0;
 auto test=[&](const char* name,auto run){J c={{"name",name}};try{c["state"]=run();c["passed"]=true;}catch(const std::exception& e){c["error"]=e.what();c["passed"]=false;++failures;}std::cerr<<J{{"name",name},{"passed",c["passed"]},{"error",c.value("error",std::string{})}}.dump()<<std::endl;checks.push_back(std::move(c));};
 test("same_cell_layers_live_death_and_type_changes",[]{Fixture f;auto ordinary=f.add({10,4});auto a=f.add({10,4},true),b=f.add({10,4},true);f.verify();ordinary->hp.set(0.);f.verify();a->dead.set(t::DeathMarker(0.));f.verify();b->ash.set(0.);f.verify();ordinary->hp.set(54.);ordinary->source.content.set("抓人草触手");f.verify();ordinary->source.content.erase();f.verify();return f.state();});
 test("moving_heads_preserve_or_clear_old_cell_marks",[]{Fixture f;auto ordinary=f.add({10,4});auto a=f.add({10,4},true),b=f.add({10,4},true);f.verify();a->head_point.set({8.25*48.,12.25*48.});f.plants.anchor_head(a);require(f.world.terrain.native_at(10,4).plant.present(),"overlapping ordinary plant lost its marker");ordinary->hp.set(0.);b->head_point.set({9.25*48.,12.25*48.});f.plants.anchor_head(b);require(!f.world.terrain.native_at(10,4).plant.present(),"last live head left a stale plant marker");f.verify();return f.state();});
 test("same_tick_remove_birth_restores_size_and_data_pointer",[]{Fixture f;f.world.plant_roster->reserve(32);f.add({8,2});auto head=f.add({10,5},true);f.plants.head_only_cells();const auto* data=f.world.plant_roster->data();const auto count=f.world.plant_roster->size(),revision=f.world.plant_roster_revision;f.world.erase_plant_at(0);f.add({15,12});require(data==f.world.plant_roster->data()&&count==f.world.plant_roster->size(),"fixture failed to reproduce identical roster signature");require(f.world.plant_roster_revision>revision,"lifecycle revision did not change");f.world.terrain.native_at(15,12).plant.erase();f.plants.head_cells.emplace(15,12);f.plants.restore_marks();require(f.world.terrain.native_at(15,12).plant.present(),"same-sized replacement missed occupancy invalidation");f.verify();return f.state();});
 test("same_tick_direct_cell_edits_and_roster_replacement",[]{Fixture f;auto ordinary=f.add({10,4});auto h=f.add({10,5},true);f.verify();ordinary->cell={10,5};require(f.plants.plant_in({10,5},h),"manual ordinary cell write remained in cached old cell");ordinary->cell={10,6};f.world.terrain.native_at(10,6).plant.set(true);h->cell={10,6};h->head_point.set({8.25*48.,12.25*48.});f.plants.anchor_head(h);require(f.world.terrain.native_at(10,6).plant.present(),"manual layered cell write was not refreshed before head move");auto replacement=std::make_shared<t::PlantRoster>(*f.world.plant_roster);f.world.plant_roster=replacement;f.verify();return f.state();});
 test("ring_seam_clamped_vertical_edges_and_outside_records",[]{Fixture f;auto h=f.add({10,2},true);f.add({-1,-4});f.verify();h->head_point.set({-12.,10000.});f.plants.anchor_head(h);require(h->cell==t::Cell{30,95},"head seam/bottom clamp changed");h->head_point.set({24.,-200.});f.plants.anchor_head(h);require(h->cell==t::Cell{0,0},"head top clamp changed");f.verify();return f.state();});
 Fixture dense;for(int i=0;i<350;++i)dense.add({20+i/96,i%96});for(int i=0;i<350;++i)dense.add({4+i/96,i%96},true);
 const auto expected=dense.slow_only();const auto start=std::chrono::steady_clock::now();for(int i=0;i<128;++i)require(dense.plants.head_only_cells()==expected,"dense projection changed");const double elapsed=std::chrono::duration<double,std::milli>(std::chrono::steady_clock::now()-start).count();
 J functions=J::object();for(const auto& [name,p]:pvz::function_profile::snapshot())functions[name]={{"calls",p.calls},{"total_ms",p.total_ms},{"max_ms",p.max_ms}};
 J out={{"passed",failures==0},{"failures",failures},{"cases",checks},{"dense",{{"plants",700},{"heads",350},{"queries",128},{"elapsed_ms",elapsed},{"work",work(dense.plants.occupancy_work())},{"head_only_cells",expected.size()}}},{"function_profile",functions},{"scope","Production ContentPlants70 occupancy methods; original full-scan oracle. Services unrelated to these methods reject unexpected calls. End-to-end Session state/RNG/native-frame comparison is separate."}};
 std::ofstream(argv[1],std::ios::binary)<<out.dump(2);std::cout<<J{{"passed",out["passed"]},{"dense_ms",elapsed},{"work",out["dense"]["work"]}}.dump()<<std::endl;return failures?1:0;
}
