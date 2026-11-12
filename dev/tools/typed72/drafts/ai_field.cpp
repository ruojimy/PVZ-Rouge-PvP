#include "sim/typed/ai_field.h"
#include "core/pymath.h"
#include <tuple>

namespace pvz::typed72 {
AiField::AiField(const TargetSight& terrain,double w,double h,double t,std::optional<std::string> hash)
    :width(w),height(h),tile(t),terrain_hash(std::move(hash)){
    const auto rows=terrain.solid.size(),cols=rows?terrain.solid.front().size():0;
    for(size_t col=0;col<cols;++col)for(size_t row=1;row<rows;++row){
        const bool water=terrain.water.at(row).at(col)!=0;
        if((!terrain.solid.at(row).at(col)&&!water)||terrain.solid.at(row-1).at(col))continue;
        const double x=(col+.5)*tile,y=row*tile-2.;const int zone=int(py::mod(x,width)/width*6.)%6;
        spots.at(size_t(zone)).push_back({{x,y},water});
    }
    for(auto& bucket:spots)std::sort(bucket.begin(),bucket.end(),[](const auto& a,const auto& b){return std::tie(a.point.x,a.point.y,a.water)<std::tie(b.point.x,b.point.y,b.water);});
}
std::vector<AiFieldSpot> AiField::candidates(int zone,double hero_x,std::optional<double> hero_y,int64_t limit)const{
    if(zone<0||zone>=6)return {};
    std::vector<std::pair<double,AiFieldSpot>> selected;
    for(const auto& spot:spots[size_t(zone)]){
        const auto distance=std::abs(ai_wrap_delta(hero_x,spot.point.x,width));if(distance>480.)continue;
        if(hero_y&&(spot.point.y-*hero_y< -384.||spot.point.y-*hero_y>256.))continue;
        selected.emplace_back(distance,spot);
    }
    std::sort(selected.begin(),selected.end(),[](const auto& a,const auto& b){return std::tie(a.first,a.second.point.x,a.second.point.y,a.second.water)<std::tie(b.first,b.second.point.x,b.second.point.y,b.second.water);});
    const auto n=limit>=0?std::min<int64_t>(limit,selected.size()):std::max<int64_t>(0,int64_t(selected.size())+limit);
    std::vector<AiFieldSpot> result;result.reserve(size_t(n));for(int64_t i=0;i<n;++i)result.push_back(selected[size_t(i)].second);return result;
}
std::vector<int> AiField::zones_in_view(double hero_x)const{std::vector<int> result;for(int i=0;i<6;++i)if(!candidates(i,hero_x,{},1).empty())result.push_back(i);return result;}
const AiField* AiFieldCache::update(const TargetSight* terrain,double width,double height,double tile,int64_t revision,std::optional<std::string> hash){
    if(terrain&&(!field_||revision_!=revision||hash!=field_->terrain_hash)&&!terrain->solid.empty()){
        field_=std::make_unique<AiField>(*terrain,width,height,tile,std::move(hash));revision_=revision;
    }
    return field_.get();
}
} // namespace pvz::typed72
