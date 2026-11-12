#include "cold_placement_rules.h"
#include <algorithm>
namespace pvz::typed72 {
namespace {
bool one(std::string_view value,std::initializer_list<std::string_view> choices){return std::find(choices.begin(),choices.end(),value)!=choices.end();}
std::optional<size_t> lookup(std::span<const ColdPlacementPlant> plants,Cell cell,bool no_shell=false){
    std::optional<size_t> found;
    for(size_t i=0;i<plants.size();++i)if(plants[i].cell==cell){
        if(plants[i].name=="南瓜头"){if(no_shell)continue;return i;}found=i;
    }return found;
}
}
ColdPlacementRules::ColdPlacementRules(const WorldTerrain& map,std::span<const ColdPlacementPlant> plants,
    std::span<const std::string> secrets,std::string_view source,double cost):spike_cost(cost),map_(map),plants_(plants),secrets_(secrets){
    if(source=="custom:ea660000000000000000000000000009")for(int y=0;y<map.rows();++y)
        for(int x=0;x<map.cols();++x){const auto& b=map.native_at(y,x).block;if(b.present()&&!b.is_null()&&b.get()=="铁路")bottom_rail_=y;}
}
bool ColdPlacementRules::secret(std::string_view name)const{return std::find(secrets_.begin(),secrets_.end(),name)!=secrets_.end();}
bool ColdPlacementRules::dense()const{return secret("密植");}
std::string ColdPlacementRules::block(int y,int64_t x)const{
    const auto& b=map_.native_at(y,map_.wrap(x)).block;
    std::string name=b.present()?(b.is_null()?"None":b.get()):"空";
    if(bottom_rail_&&((y<0?y+map_.rows():y)==*bottom_rail_)&&name=="铁路")name="土";return name;
}
bool ColdPlacementRules::water(int y,int64_t x)const{return map_.valid_row(y)&&block(y,x)=="水";}
bool ColdPlacementRules::marker(int y,int64_t x)const{return map_.native_at(y,map_.wrap(x)).plant.present();}
bool ColdPlacementRules::solid(int y,int64_t x)const {
    if(!map_.valid_row(y))return false;const auto name=block(y,x);
    return !map_.is_empty(name)&&!name.ends_with("水")&&!one(name,{"梯子块","梯子","扶梯","","空"});
}
std::vector<const ColdPlacementPlant*> ColdPlacementRules::plants_at(int y,int64_t x)const{
    std::vector<const ColdPlacementPlant*> result;
    for(const auto& plant:plants_)if(plant.cell==Cell{y,x})result.push_back(&plant);return result;
}
std::string ColdPlacementRules::dense_error(std::string_view name,int y,int64_t x)const{
    if(!dense()||one(name,{"咖啡豆","花盆","睡莲","石块"}))return {};
    auto here=plants_at(y,map_.wrap(x));
    if(name=="南瓜头")return std::any_of(here.begin(),here.end(),[](auto* p){return p->name=="南瓜头";})?"每格最多额外种一个南瓜头或藤蔓":"";
    return std::count_if(here.begin(),here.end(),[](auto* p){return !one(p->name,{"南瓜头","咖啡豆","花盆","睡莲","水盆"});})>=3?"密植每格最多种三个主体植物":"";
}
bool ColdPlacementRules::stone_cell(int y,int64_t x)const{
    if(!map_.valid_row(y))return false;const auto& tile=map_.native_at(y,map_.wrap(x));
    if(tile.block.present()&&!tile.block.is_null()&&block(y,x)!="空")return false;
    if(tile.plant.present()&&!tile.plant.is_null()&&tile.plant.get())return false;
    for(int dy=-1;dy<=1;++dy)for(int dx=-1;dx<=1;++dx)if((dy||dx)&&map_.valid_row(y+dy)){
        const auto& b=map_.native_at(y+dy,map_.wrap(x+dx)).block;
        if(b.present()&&!b.is_null()&&!map_.is_empty(block(y+dy,x+dx)))return true;
    }return false;
}
bool ColdPlacementRules::accepts(std::string_view name,int y,int64_t x)const{
    if(!map_.valid_row(y))return false;x=map_.wrap(x);
    if(!dense_error(name,y,x).empty())return false;
    if(name=="石块")return stone_cell(y,x);
    const auto here=plants_at(y,x);
    if(name=="咖啡豆"&&((dense()&&std::any_of(here.begin(),here.end(),[](auto* p){return p->sleeping;}))||
        std::any_of(here.begin(),here.end(),[](auto* p){return p->vine&&p->sleeping;})))return true;
    // Dense coffee takes its dedicated any-sleeper result even when false.
    if(dense()&&name=="咖啡豆")return false;
    const bool only_basin=!here.empty()&&std::all_of(here.begin(),here.end(),[](auto* p){return p->basin;});
    std::vector<ColdPlacementPlant> visible;visible.reserve(plants_.size()*2);
    for(const auto& p:plants_)if(!p.basin&&(!dense()||p.cell!=Cell{y,x}))visible.push_back(p);
    for(const auto& p:plants_)if(p.vine&&water(p.cell.y+1,p.cell.x))visible.push_back({"睡莲",{p.cell.y+1,p.cell.x}});
    return original_accepts(name,y,x,visible,marker(y,x)&&!dense()&&!only_basin);
}
bool ColdPlacementRules::original_accepts(std::string_view name,int y,int64_t x,std::span<const ColdPlacementPlant> visible,bool marked)const{
    const auto cell=Cell{y,x};const auto current=block(y,x);
    if(name.empty()||name=="铲子")return false;
    if(name=="咖啡豆"){const auto i=lookup(visible,cell,true);return marked&&i&&visible[*i].sleep_present;}
    if(name=="墓碑吞噬者")return current=="坟墓"&&!marked;
    if(one(name,{"睡莲","海蘑菇","缠绕海草","香蒲"}))return current=="水"&&block(y-1,x)!="水"&&map_.is_empty(block(y-1,x))&&!marked;
    bool supported=false;
    if(map_.valid_row(y+1)){
        const auto below=block(y+1,x);
        if(name=="花盆")supported=!map_.is_empty(below);
        else{
            if(name=="南瓜头"&&below=="水"&&marker(y+1,x)){
                const auto i=lookup(visible,{y+1,x});
                if(visible.empty())throw std::out_of_range("plant marker without native record");
                if(visible[i?*i:visible.size()-1].name=="香蒲")supported=true;
            }
            if(one(below,{"草","土"}))supported=true;
            else if(!one(name,{"地刺","地刺王"})&&below=="花盆块")supported=true;
            else if((secret("无土栽培")||(name=="高坚果"&&secret("石果")))&&!map_.is_empty(below))supported=true;
            else if(!one(name,{"地刺","地刺王","土豆地雷"})&&below=="水"){
                const auto i=lookup(visible,{y+1,x});if(i&&visible[*i].name=="睡莲")supported=true;
            }
            if(below=="铁路")supported=false;
        }
    }
    bool vacant=true;
    if(marked){
        const auto found=lookup(visible,cell);if(visible.empty())throw std::out_of_range("plant marker without native record");
        const auto index=found?*found:visible.size()-1;
        if(visible[index].name=="南瓜头"&&name!="南瓜头"){
            for(size_t i=0;i<visible.size();++i)if(i!=index&&visible[i].cell==cell){vacant=false;break;}
        }else if((name=="南瓜头"&&visible[index].name=="南瓜头")||name!="南瓜头")vacant=false;
    }
    return supported&&vacant&&current=="空";
}
bool ColdPlacementRules::shell_cell(int y,int64_t x,bool vine)const{
    if(!map_.valid_row(y))return false;x=map_.wrap(x);const auto here=plants_at(y,x);
    if(std::any_of(here.begin(),here.end(),[](auto* p){return p->name=="南瓜头";}))return false;
    if(std::any_of(here.begin(),here.end(),[](auto* p){return p->air;}))return true;
    if(vine&&here.empty()&&!solid(y,x)&&!block(y,x).ends_with("水")&&water(y+1,x))return true;
    return accepts("南瓜头",y,x);
}
bool ColdPlacementRules::idle_cell(int y,int64_t x)const{
    if(!map_.valid_row(y))return false;x=map_.wrap(x);
    if(dense())return !solid(y,x)&&dense_error("飞行植物",y,x).empty();
    return !solid(y,x)&&!marker(y,x)&&plants_at(y,x).empty();
}
bool ColdPlacementRules::grass_cell(int y,int64_t x)const{
    if(!idle_cell(y,x))return false;x=map_.wrap(x);
    for(int row=std::max(0,y-1);row<std::min(map_.rows(),y+2);++row)for(int dx=-1;dx<=1;++dx)
        if((row!=y||dx)&&solid(row,x+dx))return true;
    return false;
}
} // namespace pvz::typed72
