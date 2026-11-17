#include "ui/hand/texture74_internal.h"
#include "core/gil.h"
#include "data/datastore.h"
#include "sim/pvp/battle_api.h"
#include <fstream>
#include <iostream>
using namespace pvz;namespace tx=pvz::texture74;using J=nlohmann::json;
int main(int argc,char**argv){
 if(argc!=2)return 2;SDL_SetMainReady();gil::init();data::set_data_dir("extract/data");pg::install_pygame();init_pvp_modules();callm(pg::display_module(),Sym("set_mode"),Args{V::tuple({V(16),V(16)})});tx::load_inventory();
 std::map<std::string,std::vector<const tx::Resource*>> groups;
 for(const auto& r:tx::state().resources){const auto i=r.key.find(':');if(i==std::string::npos)continue;const auto prefix=r.key.substr(0,i);if(prefix=="world"||prefix=="ui"||prefix=="bg"||prefix=="near"||prefix=="global")groups[r.key.substr(i+1)].push_back(&r);}
 J tests=J::array();int errors=0;
 for(const auto& [name,resources]:groups)if(resources.size()>1)for(const auto* from:resources){
  try{auto image=tx::surface(from->w,from->h,std::vector<uint32_t>(size_t(from->w)*from->h,0x17cd83ff));const auto png=tx::png_encode(image);
   tx::activate({{"format","pvz-texture-pack-v1"},{"name","scope-isolation-test"},{"entries",{{from->key,{{"width",from->w},{"height",from->h},{"png",tx::b64(png)}}}}}});
   const V a=tx::artwork(from->key);if(a.is_none())throw std::runtime_error("exact override missing");for(const auto* other:resources)if(other!=from){const V b=tx::artwork(other->key);if(!b.is_none())++errors;tests.push_back({{"from",from->key},{"other",other->key},{"from_file",from->file},{"other_file",other->file},{"from_size",{from->w,from->h}},{"other_size",{other->w,other->h}},{"same_original_file_and_size",from->file==other->file&&from->w==other->w&&from->h==other->h},{"lookup_returns_source_override",!b.is_none()&&b.box==a.box}});}
  }catch(const std::exception& e){tests.push_back({{"from",from->key},{"error",e.what()}});++errors;}
 }
 tx::activate({{"format","pvz-texture-pack-v1"},{"name","original"},{"entries",J::object()}});std::ofstream(argv[1],std::ios::binary)<<J{{"errors",errors},{"tests",tests}}.dump(2);std::cout<<"scope_pairs="<<tests.size()<<" errors="<<errors<<'\n';return errors?1:0;
}
