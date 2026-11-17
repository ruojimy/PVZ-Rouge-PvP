// Material isolation regression driver; links the current production libraries.
#include "pg/pg.h"
#include "core/gil.h"
#include "data/datastore.h"
#include "sim/pvp/battle_api.h"
#include "sim/typed72_app/cold_export.h"
#include "sim/typed72_app/session.h"
#include "sim/typed/native_canvas.h"
#include "sim/typed/cold_catalog.h"
#include "sim/typed/targets.h"
#include "sim/typed/native_patch_draw.h"
#include "sim/typed/plant_zombie_target.h"
#include <nlohmann/json.hpp>
#include <fstream>
#include <iostream>
#include <map>
#include <set>
using namespace pvz;using J=nlohmann::json;
static void palette(const J& j,std::map<std::string,int>& out){
 if(j.is_object()){
  const auto op=j.value("op",std::string{});
  if(op=="asset"&&j.contains("key"))++out[j["key"].get<std::string>()];
  if(op=="fill")++out["fill:"+j.value("color",J()).dump()+":"+J(j.value("flags",0)).dump()];
  if(j.contains("alpha")&&!j["alpha"].is_null()&&j["alpha"]!=255)++out["alpha:"+j["alpha"].dump()];
  for(const auto& [k,v]:j.items())palette(v,out);
 }else if(j.is_array())for(const auto& v:j)palette(v,out);
}
static std::string field(const J& e,const char* name){return e.contains(name)&&e[name].is_string()?e[name].get<std::string>():std::string{};}
int main(int argc,char**argv){
 if(argc!=3)return 2;SDL_SetMainReady();gil::init();data::set_data_dir("extract/data");pg::install_pygame();init_pvp_modules();
 std::ifstream input(argv[1]);J config=J::parse(input),rows=J::array(),atlas_info;int errors=0;
 for(const auto& spec:config["scenarios"]){
  J row={{"name",spec.at("name")},{"units",J::object()},{"timeline",J::array()}};
  try{
   const J pd=spec.value("plant_deck",J::array({"plant:向日葵"})),zd=spec.value("zombie_deck",J::array({"zombie:脑光墓碑","zombie:普通僵尸"}));
   auto handle=battle_from_scenario({{"seed",743},{"durable_heroes",true},{"decks",{{"plant",pd},{"zombie",zd}}}});
   auto cold=typed72app::export_cold(handle.battle,743);
   if(atlas_info.is_null()){
    J identities=J::object();for(const auto& [key,entry]:cold.draw_atlas["world"].items())identities[entry.at("id").dump()].push_back(key);
    J shared=J::array();for(const auto& [id,keys]:identities.items())if(keys.size()>1)shared.push_back(keys);
    atlas_info={{"world_keys",cold.draw_atlas["world"].size()},{"shared_image_identity_groups",shared},{"constants",cold.cold["constants"]},{"cards",J::array()}};
    for(const auto& c:typed72::compiled_cold_catalog().cards)atlas_info["cards"].push_back({{"id",c.id},{"name",c.name},{"asset",c.asset},{"native_name",c.native_name.present()&&!c.native_name.is_null()?J(c.native_name.get()):J()}});
    // Check every requested alias with real production artwork, including state variants.
    J checks=J::array();for(const auto& edge:config.value("alias_pairs",J::array()))for(const char* suffix:{"","-受伤","-冰冻","-灰烬","-魅惑"}){
     const auto old=edge[0].get<std::string>()+suffix,next=edge[1].get<std::string>()+suffix;
     if(!cold.draw_atlas["world"].contains(old)||!cold.draw_atlas["world"].contains(next))continue;
     typed72::NativeCanvas canvas;canvas.install(cold.draw_atlas,{},cold.cold["constants"]["scale_factor"],cold.cold["constants"]["rider_lift"]);
     auto original=canvas.image(old);canvas.alias_one(old,next);canvas.restore();const bool once=canvas.image(old)==original;
     canvas.alias_one(old,next);canvas.alias_one(old,next);canvas.restore();const bool repeated=canvas.image(old)==original;
     canvas.atlas.atlas[old]=original;canvas.tint_roots({old},1);canvas.alias_one(old,next);canvas.restore();const bool tint=canvas.image(old)==original;
     checks.push_back({{"old",old},{"replacement",next},{"single_alias_restored",once},{"repeated_alias_restored",repeated},{"tint_then_alias_restored",tint}});
    }atlas_info["alias_restore_checks"]=checks;
    // A recorded image must keep its original alpha/recipe after the shared source changes.
    auto image=std::make_shared<typed72::NativeArtImage>();image->alpha=123;const auto frozen=typed72::NativeArtStore::freeze(image);image->alpha=27;
    atlas_info["freeze_alpha_isolated"]=(frozen->alpha==123);
    std::unordered_map<std::string,typed72::SpritePixels> pixels;
    for(const auto& [name,p]:cold.atlas){typed72::SpritePixels px;px.width=p.width;px.height=p.height;px.pixels=p.rgba;pixels.emplace(name,std::move(px));}
    const auto carrier=[&](typed72::NativeCanvas& c){auto z=std::make_shared<typed72::CombatZombie>();z->body.kind="巨人僵尸";z->body.armor="铁桶";z->body.armor_hp=100.;z->body.hp=1000.;c.expansion.gate(z);c.frames.begin_frame(0);c.display(c.image("巨人僵尸-首"),{100.,100.});return c.frame_json(c.frames.frame());};
    typed72::NativeCanvas cached,clean;cached.install(cold.draw_atlas,pixels,cold.cold["constants"]["scale_factor"],cold.cold["constants"]["rider_lift"]);clean.install(cold.draw_atlas,pixels,cold.cold["constants"]["scale_factor"],cold.cold["constants"]["rider_lift"]);
    cached.tint_roots({"巨人僵尸-身","巨人僵尸-首"},1);const auto poisoned=carrier(cached);cached.expansion.clear();cached.restore();const auto after=carrier(cached),control=carrier(clean);
    std::map<std::string,int> ap,cp;palette(after,ap);palette(control,cp);atlas_info["carrier_cache"]={{"healthy_after_poison_palette",ap},{"healthy_fresh_palette",cp},{"isolated",ap==cp},{"after_frame",after},{"control_frame",control},{"poison_frame",poisoned}};
    J head_checks=J::array();for(const char* name:{"豌豆僵尸","机枪僵尸","大喷菇僵尸","坚果僵尸","高坚果僵尸","毁灭菇僵尸","辣椒僵尸","倭瓜僵尸","墓碑吞噬者僵尸","三叶草僵尸","路灯花僵尸","萝卜伞僵尸","吸金磁僵尸"}){
     if(!typed72::native_plant_zombie_config(name))continue;
     typed72::NativeCanvas c;c.install(cold.draw_atlas,pixels,cold.cold["constants"]["scale_factor"],cold.cold["constants"]["rider_lift"]);c.patch_plant_zombie_assets();
     typed72::TypedBattleState world;auto u=std::make_shared<typed72::CombatZombie>();u->body.kind="普通僵尸";u->body.hp=100.;u->body.facing=-1.;u->body.motion.replace({300.,300.,0.,0.});u->patch.plant_zombie.set(true);u->patch.plant_name.set(name);world.targets->push_back(typed72::CombatTarget::zombie(u));typed72::NativePatchDraw draw(world,c);
     const auto sample=[&]{c.frames.begin_frame(0);draw.plant_zombie_heads();std::map<std::string,int> p;palette(c.frame_json(c.frames.frame()),p);return p;};
     const auto plain=sample();c.tint_roots({std::string(name)+"-植头"},1);const auto left=sample();u->body.facing=1.;const auto right=sample();
     J check={{"name",name},{"plain_left_palette",plain},{"poisoned_left_palette",left},{"poisoned_right_palette",right},{"left_changes_under_poison",plain!=left},{"right_has_poison",right.contains("fill:[255,115,190]:3")}};
     // Rebuild only the generated flip, then poison it first and clear status.
     const auto key=std::string(name)+"-植头左";c.atlas.atlas.erase(key);u->body.facing=-1.;const auto first_poison=sample();c.restore();const auto after_clear=sample();check["poison_first_left_palette"]=first_poison;check["healthy_left_after_clear"]=after_clear;check["healthy_left_restored"]=after_clear==plain;
     // Exercise the real per-unit poison field too, including both levels and
     // clearing it on the same cached draw object, with and without armor.
     J transitions=J::array();
     for(const char* armor:{"","路障","铁桶"})for(int level:{1,2}){
      u->body.armor=armor;u->body.armor_hp=100.;
      u->poison.poison.erase();const auto healthy=sample();
      auto state=std::make_shared<typed72::PoisonState>();state->level.set(level);u->poison.poison.set(state);
      const auto poisoned=sample();u->poison.poison.erase();const auto cleared=sample();
      transitions.push_back({{"level",level},{"armor",armor},{"changed",poisoned!=healthy},{"cleared",cleared==healthy}});
     }
     check["unit_poison_transitions"]=transitions;head_checks.push_back(check);
    }atlas_info["plant_zombie_head_cache"]=head_checks;
   }
   auto b=typed72app::Session::create(std::move(cold),"家院");std::map<std::string,std::string> ids,tags;
   for(const auto side:{"plant","zombie"})b->fixture_set_avatar(side,{{"玩家位置",{3500,864,0,0}},{"玩家血量",1000000000.}});
   const auto spawn=[&](const J& u){const std::string card=u.at("card"),side=u.value("side",card.starts_with("plant:")?std::string("plant"):std::string("zombie")),tag=u.at("tag");
    auto id=b->spawn(card,side,u.value("x",2136.),u.value("y",864.),u.value("facing",side=="plant"?1.:-1.),false);if(!id)throw std::runtime_error("spawn failed: "+card);
    ids[tag]=*id;tags[*id]=tag;row["units"][tag]={{"card",card},{"id",*id}};
    if(side=="zombie")b->fixture_place_zombie(*id,u.value("x",2136.),u.value("y",864.),u.value("facing",-1.));
    if(u.contains("fields"))b->native_set(false,*id,u["fields"]);
   };
   for(const auto& u:spec["units"])spawn(u);
   for(const auto side:{"plant","zombie"})if(spec.contains("heroes")&&spec["heroes"].contains(side))b->fixture_set_avatar(side,spec["heroes"][side]);
   {const auto view=b->native_view();for(const auto key:{"植物","僵尸"})for(const auto& u:view["g"][key]){const auto id=field(u,"_pvp_id");if(tags.contains(id))row["units"][tags[id]]["native_record"]=u;}}
   for(int step=0;step<spec.value("steps",6);++step){
    for(const auto& a:spec.value("actions",J::array()))if(a.at("step")==step){if(a.contains("spawn"))spawn(a["spawn"]);else b->native_set(false,ids.at(a.at("tag").get<std::string>()),a.at("fields"));}
    b->step();J view;try{view=b->native_view();}catch(const std::exception& e){if(!spec.value("native_view_optional",false))throw;row["native_view_errors"].push_back({{"step",step},{"error",e.what()}});view={{"g",{{"实体",J::array()}}}};}const auto frame=b->reference_native_frame();auto owners=tags;J shots=J::array();
    for(const auto& e:view["g"]["实体"]){const auto id=field(e,"_pvp_id");std::string tag;
     for(const char* key:{"_pvp_root_source","_pvp_source_entity"}){const auto source=field(e,key);if(tags.contains(source)){tag=tags.at(source);break;}}
     if(!tag.empty())owners[id]=tag;
     if(spec.value("record_shots",false)){J shot=J::object();for(const char* k:{"_pvp_id","_pvp_root_source","_pvp_source_entity","_pvp_plant_kind","_pvp_content","_pvp_fire_color","__pvz_sb_zombie_pea_fire","_pvp_multi_red","名","位置","消亡"})if(e.contains(k))shot[k]=e[k];shot["tag"]=tag;shots.push_back(shot);}
    }
    std::map<std::string,int> all;J bytag=J::object();for(const auto& command:frame["commands"]){std::map<std::string,int> found;palette(command,found);for(const auto& [key,n]:found)all[key]+=n;
     const auto id=field(command,"entity"),tag=owners.contains(id)?owners.at(id):id.empty()?std::string("unattributed"):id;
     if(!bytag.contains(tag))bytag[tag]=J::object();for(const auto& [key,n]:found)bytag[tag][key]=bytag[tag].value(key,0)+n;
    }
    J statuses=J::object();if(view["g"].contains("僵尸"))for(const auto& u:view["g"]["僵尸"]){const auto id=field(u,"_pvp_id");if(!tags.contains(id))continue;J status=J::object();for(const char* k:{"_pvp_poison","_pvp_poison_killed","冰冻","魅惑","血量","防具","防具血量"})if(u.contains(k))status[k]=u[k];statuses[tags.at(id)]=status;}
    J sample={{"step",step},{"all",all},{"tags",bytag},{"statuses",statuses}};if(spec.value("record_shots",false))sample["shots"]=shots;row["timeline"].push_back(sample);
   }
   row["completed"]=true;callm(handle.battle,SY("close"),Args{});
  }catch(const std::exception& e){row["completed"]=false;row["error"]=e.what();++errors;}
  std::cout<<row["name"]<<" completed="<<row["completed"]<<'\n';rows.push_back(row);
 }
 J failures=J::array();const auto require=[&](bool ok,const std::string& name){if(!ok)failures.push_back(name);};
 for(const auto& c:atlas_info["alias_restore_checks"])for(const char* key:{"single_alias_restored","repeated_alias_restored","tint_then_alias_restored"})require(c.at(key).get<bool>(),c.at("old").get<std::string>()+":"+key);
 require(atlas_info.at("freeze_alpha_isolated"),"freeze alpha");require(atlas_info["carrier_cache"].at("isolated"),"carrier poison cache");
 for(const auto& c:atlas_info["plant_zombie_head_cache"]){
  for(const char* key:{"left_changes_under_poison","right_has_poison","healthy_left_restored"})require(c.at(key).get<bool>(),c.at("name").get<std::string>()+":"+key);
  for(const auto& t:c["unit_poison_transitions"])require(t.at("changed")&&t.at("cleared"),c.at("name").get<std::string>()+":unit poison:"+t.dump());
 }
 std::ofstream(argv[2],std::ios::binary)<<J{{"errors",errors},{"assertion_failures",failures},{"scenarios",rows},{"atlas",atlas_info}}.dump(2);return errors||!failures.empty()?1:0;
}
