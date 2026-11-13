#include "sim/typed/moving_point_grid.h"
#include "core/pymath.h"
#include <algorithm>
#include <cmath>
#include <stdexcept>
namespace pvz::typed72 {
int64_t MovingPointGrid::column(int64_t x)const{const auto n=x%cols_;return n<0?n+cols_:n;}
void MovingPointGrid::reset(double tile,double width,size_t count){
    if(!(tile>0.)||!(width>0.))throw std::invalid_argument("invalid moving grid");
    width_=width;cols_=std::max<int64_t>(1,int64_t(std::ceil(width/tile)));cell_=width/double(cols_);
    entries_.assign(count,{});buckets_.clear();result_.clear();seen_.assign(count,0);stamp_=0;min_y_=max_y_=0.;++rebuilds;
}
void MovingPointGrid::move(size_t id,Point p){
    if(!std::isfinite(p.x)||!std::isfinite(p.y)||std::abs(p.y)>0x1p45)throw std::invalid_argument("non-finite moving point");
    ++moves;min_y_=std::min(min_y_,p.y);max_y_=std::max(max_y_,p.y);
    const auto row=int64_t(std::floor(p.y/cell_));const auto col=int64_t(std::floor(py::mod(p.x,width_)/cell_));const auto key=row*cols_+column(col);
    auto& e=entries_.at(id);if(e.inserted&&e.key==key)return;
    if(e.inserted){auto old=buckets_.find(e.key);auto& ids=old->second;const auto last=ids.back();ids[e.slot]=last;entries_[last].slot=e.slot;ids.pop_back();if(ids.empty())buckets_.erase(old);}
    auto& ids=buckets_[key];e={key,ids.size(),true};ids.push_back(id);++cell_changes;
}
void MovingPointGrid::append(const std::vector<size_t>& ids){for(const auto id:ids)if(seen_[id]!=stamp_){seen_[id]=stamp_;result_.push_back(id);}}
std::span<const size_t> MovingPointGrid::rectangle(CoverageBox box){
    ++queries;result_.clear();if(++stamp_==0){std::fill(seen_.begin(),seen_.end(),0);++stamp_;}
    if(box.left>box.right||box.top>box.bottom)return result_;
    const auto left=int64_t(std::floor(box.left/cell_)),right=int64_t(std::floor(box.right/cell_)),top=int64_t(std::floor(box.top/cell_)),bottom=int64_t(std::floor(box.bottom/cell_));
    const bool all=right-left+1>=cols_;const auto lo=column(left),hi=column(right);
    if(double(bottom-top+1)*std::min(cols_,right-left+1)>double(buckets_.size())){
        for(const auto& [key,ids]:buckets_){const auto row=key>=0?key/cols_:(key-(cols_-1))/cols_,col=column(key);
            if(row>=top&&row<=bottom&&(all||(lo<=hi?(col>=lo&&col<=hi):(col>=lo||col<=hi))))append(ids);}
    }else for(auto row=top;row<=bottom;++row){const auto n=std::min(cols_,right-left+1);for(int64_t offset=0;offset<n;++offset){const auto found=buckets_.find(row*cols_+column(left+offset));if(found!=buckets_.end())append(found->second);}}
    std::sort(result_.begin(),result_.end());return result_;
}
double MovingPointGrid::covering_radius(Point p)const{return std::max({width_/2.,std::abs(p.y-min_y_),std::abs(p.y-max_y_)})+cell_;}
}
