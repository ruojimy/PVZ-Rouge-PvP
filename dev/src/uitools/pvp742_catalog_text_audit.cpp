// Compare packaged catalog text with the live compiled catalog and real almanac.
#include "pg/pg.h"
#include "core/gil.h"
#include "data/datastore.h"
#include "sim/pvp/battle_api.h"
#include "sim/pvp/gen/pm_catalog.h"
#include "sim/pvp/gen/pm_almanac_text.h"
#include "ui/gen/pm_reference.h"
#include "ui/gen/pm_rendering.h"
#include <nlohmann/json.hpp>
#include <fstream>
#include <iostream>
using namespace pvz;using J=nlohmann::json;
struct HelpRenderer : pm_rendering::C_Renderer {
 std::string bodies;
 V m_wrapped(const Args& a)override{bodies+=py_str(a.get(0,SY("text"),nullptr));return C_Renderer::m_wrapped(a);}
};
int main(int argc,char** argv){
 if(argc!=2)return 2;SDL_SetMainReady();gil::init();data::set_data_dir("extract/data");pg::install_pygame();init_pvp_modules();
 auto battle=battle_from_scenario({{"seed",742}});const auto& packaged=data::module("catalog").at("CARDS");J mismatches=J::array(),checks=J::array(),notes_mismatches=J::array();bool text_contracts=true,mark_range_correct=true;
 for(const auto& [id,c]:packaged.items()){
  const V live=py::m_get(pm_catalog::CARDS,V(id));if(live.is_none()){mismatches.push_back({{"id",id},{"error","compiled card missing"}});continue;}
  for(const char* field:{"name","description","native_description"}){
   const J expected=c.value(field,J(nullptr)),actual=J::parse(dump(py::m_get(live,V(field))));
   if(expected!=actual)mismatches.push_back({{"id",id},{"field",field},{"packaged",expected},{"compiled",actual}});
  }
 }
 for(const char* id:{"zsecret:补贴","plant:抓人草","secret:三向蓝火","zombie:墓碑吞噬者僵尸","plant:香蒲","secret:猫尾","plant:路灯花","secret:魅惑","zombie:传送带僵尸","zombie:海盗鹦鹉","zombie:乌鸦","zsecret:斩首行动"}){
  J row={{"id",id}};try{
   const V card=py::m_get(pm_catalog::CARDS,V(id));row["card"]=J::parse(dump(card));
   row["detailed"]=py_str(pm_catalog::f_describe(Args{V(id)}));
   row["brief"]=py_str(pm_catalog::f_describe(Args({V(id)},{{SY("detailed"),V(false)}})));
   row["reference"]=py_str(pm_reference::f_describe_reference(Args{battle.bridge,V(id)}));
   const auto expected=packaged.at(id).value("description",std::string{}),actual=py_str(py::m_get(card,SV("description"),SV("")));
   bool correct=expected==actual;
   for(const char* field:{"brief","detailed","reference"}){
    const auto text=row[field].get<std::string>();
    if(std::string(id)=="zsecret:补贴")correct=correct&&text.find("初始脑光")==std::string::npos&&text.find("间隔减半")!=std::string::npos;
    if(std::string(id)=="plant:抓人草")correct=correct&&text.find(field==std::string("brief")?"僵尸戴夫4":"僵尸戴夫受4伤害")!=std::string::npos&&text.find("僵尸戴夫8")==std::string::npos&&text.find("僵尸戴夫受8")==std::string::npos;
    if(std::string(id)=="zombie:墓碑吞噬者僵尸"&&std::string(field)!="brief")correct=correct&&text.find("高于半血每口3伤害，半血及以下每口6伤害")!=std::string::npos&&text.find("刚释放后的12秒")==std::string::npos;
    if((std::string(id)=="zombie:海盗鹦鹉"||std::string(id)=="zombie:乌鸦")&&std::string(field)!="brief")correct=correct&&text.find("跟随或集结途中")!=std::string::npos&&text.find("合法植物、魅惑僵尸或植物戴夫")!=std::string::npos&&text.find("受甜薯吸引时优先直奔甜薯")!=std::string::npos;
    if(std::string(id)=="plant:香蒲"||std::string(id)=="secret:猫尾"||std::string(id)=="plant:路灯花"){
     const bool mark=text.find("4.6格")!=std::string::npos&&text.find("标准地图")!=std::string::npos&&text.find("2.75格")==std::string::npos;
     correct=correct&&mark;mark_range_correct=mark_range_correct&&mark;
    }
   }
   row["passed"]=correct;
  }catch(const std::exception& e){row["passed"]=false;row["error"]=e.what();}
  if(!row["passed"].get<bool>())text_contracts=false;checks.push_back(row);std::cout<<row.dump()<<'\n';
 }
 const auto& notes=data::module("almanac_text").at("NOTES");pm_almanac_text::init();
 for(const auto& [id,text]:notes.items())if(text!=J::parse(dump(py::m_get(pm_almanac_text::NOTES,V(id)))))notes_mismatches.push_back(id);
 V pg=pg::pygame_module(),screen=callm(pg::display_module(),SY("set_mode"),Args{V::tuple({V(1280),V(720)})});auto help=std::make_shared<HelpRenderer>();V renderer=V::inst(help);pm_rendering::initcv_Renderer(help.get());help->m___init__(Args{pg,screen,battle.bridge});
 callm(renderer,SY("help"),Args{py_dict({{SV("help_page"),V(1)}})});
 const bool help_correct=help->bodies.find("猫尾秘籍开局前120秒不生效")!=std::string::npos&&help->bodies.find("猫尾秘籍开局前80秒")==std::string::npos;
 const bool passed=mismatches.empty()&&notes_mismatches.empty()&&text_contracts&&help_correct&&mark_range_correct;
 std::ofstream(argv[1],std::ios::binary)<<J{{"passed",passed},{"all_cards",packaged.size()},{"text_fields_checked",packaged.size()*3},{"text_mismatches",mismatches},{"brief_notes_checked",notes.size()},{"brief_note_mismatches",notes_mismatches},{"focused_checks",checks},{"mark_range_standard_map_4_6",mark_range_correct},{"help_page_tail_120",help_correct},{"help_bodies",help->bodies}}.dump(2);
 callm(battle.battle,SY("close"),Args{});return passed?0:1;
}
