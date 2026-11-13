#include "sim/typed/coverage_grid.h"
#include "core/pymath.h"
#include <algorithm>
#include <cmath>
#include <limits>
#include <stdexcept>
namespace pvz::typed72 { namespace {
bool bounded(CoverageBox b){return std::isfinite(b.left)&&std::isfinite(b.right)&&std::isfinite(b.top)&&std::isfinite(b.bottom)&&std::max({std::abs(b.left),std::abs(b.right),std::abs(b.top),std::abs(b.bottom)})<0x1p50;}
}
int64_t CoverageGrid::column(int64_t x)const{const auto r=x%cols_;return r<0?r+cols_:r;}
void CoverageGrid::reset(double cell,double width,int rows,size_t count){
    if(!std::isfinite(cell)||cell<=0.||!std::isfinite(width)||width<=0.||rows<0)throw std::invalid_argument("invalid spatial grid geometry");
    const int64_t cols=std::max<int64_t>(1,int64_t(std::ceil(width/cell)));
    if(cols!=cols_||rows!=rows_){dense_.assign(size_t(cols)*rows,{});touched_.clear();}
    else {for(const auto key:touched_)dense_[key]={};touched_.clear();}
    cell_=width/double(cols);width_=width;cols_=cols;rows_=rows;
    marks_.clear();ids_.clear();ranges_.clear();unbounded_.clear();candidates_.clear();
    if(seen_.size()<count)seen_.resize(count,0);
    ++builds;
}
void CoverageGrid::cover(size_t id,CoverageBox b){
    if(id>=seen_.size())seen_.resize(id+1,0);
    if(!bounded(b)){unbounded_.push_back(id);return;}
    if(b.left>b.right||b.top>b.bottom)return;
    const auto left=int64_t(std::floor(b.left/cell_)),right=int64_t(std::floor(b.right/cell_));
    const auto top=int64_t(std::floor(b.top/cell_)),bottom=int64_t(std::floor(b.bottom/cell_));
    const auto columns=std::min(cols_,right-left+1);
    if(double(bottom-top+1)*columns>double(std::max<size_t>(1,dense_.size()))*16.+64.){unbounded_.push_back(id);return;}
    for(auto row=top;row<=bottom;++row){
        if(right-left+1>=cols_){for(int64_t col=0;col<cols_;++col)marks_.emplace_back(row*cols_+col,id);}
        else for(auto col=left;col<=right;++col)marks_.emplace_back(row*cols_+column(col),id);
    }
}
void CoverageGrid::finish(){
    std::sort(marks_.begin(),marks_.end());marks_.erase(std::unique(marks_.begin(),marks_.end()),marks_.end());
    ids_.reserve(marks_.size());
    for(size_t at=0;at<marks_.size();){
        const auto key=marks_[at].first;const auto start=uint32_t(ids_.size());
        do {ids_.push_back(marks_[at++].second);}while(at<marks_.size()&&marks_[at].first==key);
        const auto count=uint32_t(ids_.size())-start;ranges_.push_back({key,start,count});
        if(key>=0&&uint64_t(key)<dense_.size()){dense_[size_t(key)]={start,count};touched_.push_back(size_t(key));}
    }
}
void CoverageGrid::append_id(size_t id){++raw_candidates;if(seen_[id]!=stamp_){seen_[id]=stamp_;candidates_.push_back(id);}}
void CoverageGrid::append(uint32_t first,uint32_t count){for(size_t i=first;i<size_t(first)+count;++i)append_id(ids_[i]);}
void CoverageGrid::begin_query(){
    ++queries;candidates_.clear();if(++stamp_==0){std::fill(seen_.begin(),seen_.end(),0);++stamp_;}
    for(const auto id:unbounded_)append_id(id);
}
void CoverageGrid::gather(int64_t row,int64_t col){
    ++visited_cells;const auto key=row*cols_+column(col);
    if(row>=0&&row<rows_){const auto r=dense_[size_t(key)];append(r.first,r.count);return;}
    const auto i=std::lower_bound(ranges_.begin(),ranges_.end(),key,[](const auto& r,int64_t k){return r.key<k;});
    if(i!=ranges_.end()&&i->key==key)append(i->first,i->count);
}
std::span<const size_t> CoverageGrid::end_query(){std::sort(candidates_.begin(),candidates_.end());unique_candidates+=candidates_.size();return candidates_;}
std::span<const size_t> CoverageGrid::point(Point p){
    begin_query();if(bounded({p.x,p.y,p.x,p.y}))gather(int64_t(std::floor(p.y/cell_)),int64_t(std::floor(p.x/cell_)));return end_query();
}
std::span<const size_t> CoverageGrid::rectangle(CoverageBox b){
    begin_query();if(!bounded(b)){for(const auto& r:ranges_)append(r.first,r.count);return end_query();}
    if(b.left>b.right||b.top>b.bottom)return end_query();
    const auto left=int64_t(std::floor(b.left/cell_)),right=int64_t(std::floor(b.right/cell_)),top=int64_t(std::floor(b.top/cell_)),bottom=int64_t(std::floor(b.bottom/cell_));
    const bool all=right-left+1>=cols_;const auto lo=column(left),hi=column(right);
    if(double(bottom-top+1)*std::min(cols_,right-left+1)>double(ranges_.size())){
        for(const auto& r:ranges_){const auto row=r.key>=0?r.key/cols_:(r.key-(cols_-1))/cols_;const auto col=column(r.key);if(row>=top&&row<=bottom&&(all||(lo<=hi?(col>=lo&&col<=hi):(col>=lo||col<=hi)))){++visited_cells;append(r.first,r.count);}}
    }else for(auto row=top;row<=bottom;++row){if(all){for(int64_t col=0;col<cols_;++col)gather(row,col);}else for(auto col=left;col<=right;++col)gather(row,col);}
    return end_query();
}
std::span<const size_t> CoverageGrid::segment(Point a,Point b){
    const CoverageBox box{std::min(a.x,b.x),std::min(a.y,b.y),std::max(a.x,b.x),std::max(a.y,b.y)};
    if(!bounded(box))return rectangle(box);
    auto x=int64_t(std::floor(a.x/cell_)),y=int64_t(std::floor(a.y/cell_));const auto ex=int64_t(std::floor(b.x/cell_)),ey=int64_t(std::floor(b.y/cell_));
    if(double(std::abs(ex-x))+std::abs(ey-y)>double(dense_.size()+ranges_.size()*4+64))return rectangle(box);
    begin_query();gather(y,x);const double dx=b.x-a.x,dy=b.y-a.y,inf=std::numeric_limits<double>::infinity();
    const int sx=(dx>0.)-(dx<0.),sy=(dy>0.)-(dy<0.);
    const double tx=sx?cell_/std::abs(dx):inf,ty=sy?cell_/std::abs(dy):inf;
    double mx=sx?((sx>0?(x+1)*cell_:x*cell_)-a.x)/dx:inf,my=sy?((sy>0?(y+1)*cell_:y*cell_)-a.y)/dy:inf;
    while(x!=ex||y!=ey){
        if(x==ex){y+=sy;my+=ty;gather(y,x);}
        else if(y==ey){x+=sx;mx+=tx;gather(y,x);}
        else if(mx<my){x+=sx;mx+=tx;gather(y,x);}
        else if(my<mx){y+=sy;my+=ty;gather(y,x);}
        else {gather(y,x+sx);gather(y+sy,x);x+=sx;y+=sy;mx+=tx;my+=ty;gather(y,x);}
    }
    return end_query();
}
}
