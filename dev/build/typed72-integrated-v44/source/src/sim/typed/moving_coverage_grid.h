#pragma once
// Shared, exact broad phase. Membership changes invalidate candidate lists;
// motion inside the same covered cells never skips the caller's precise test.
#include "sim/typed/coverage_grid.h"
#include "core/pymath.h"
#include <unordered_map>
#include <map>
#include <tuple>
#include <algorithm>
#include <cmath>
#include <stdexcept>
namespace pvz::typed72 {
class MovingCoverageGrid {
    struct CellSlot {int64_t key;size_t slot;};
    struct Entry {std::vector<CellSlot> cells;bool wide=false;};
    using Region=std::tuple<int64_t,int64_t,int64_t,int64_t>;
    struct Cached {uint64_t epoch=0;std::vector<size_t> ids;};
    std::vector<Entry> entries_;
    std::unordered_map<int64_t,std::vector<size_t>> buckets_;
    std::map<Region,Cached> cache_;
    std::vector<size_t> wide_,scratch_ids_;
    std::vector<int64_t> scratch_keys_;
    std::vector<uint64_t> seen_;uint64_t stamp_=0,epoch_=1;
    size_t cache_bytes_=0;
    double cell_=1.,width_=1.;int64_t cols_=1;
    int64_t column(int64_t x)const {const auto r=x%cols_;return r<0?r+cols_:r;}
    Region region(CoverageBox b)const {
        const auto left=int64_t(std::floor(b.left/cell_)),right=int64_t(std::floor(b.right/cell_));
        return {int64_t(std::floor(b.top/cell_)),int64_t(std::floor(b.bottom/cell_)),column(left),std::min(cols_,right-left+1)};
    }
    static bool finite(CoverageBox b){return std::isfinite(b.left)&&std::isfinite(b.top)&&std::isfinite(b.right)&&std::isfinite(b.bottom)&&b.left<=b.right&&b.top<=b.bottom&&std::max({std::abs(b.left),std::abs(b.top),std::abs(b.right),std::abs(b.bottom)})<1.e12;}
    void erase(size_t id){
        auto& e=entries_.at(id);
        for(const auto old:e.cells){
            auto found=buckets_.find(old.key);auto& bucket=found->second;const auto other=bucket.back();
            bucket[old.slot]=other;bucket.pop_back();
            if(other!=id)for(auto& c:entries_[other].cells)if(c.key==old.key){c.slot=old.slot;break;}
            if(bucket.empty())buckets_.erase(found);
        }
        e.cells.clear();
        if(e.wide){std::erase(wide_,id);e.wide=false;}
    }
public:
    uint64_t resets=0,updates=0,cell_changes=0,queries=0,cache_hits=0,raw_candidates=0;
    void reset(double cell,double width,size_t count){
        if(!std::isfinite(cell)||!std::isfinite(width)||cell<=0.||width<=0.)throw std::invalid_argument("invalid spatial grid dimensions");
        cell_=cell;width_=width;cols_=std::max<int64_t>(1,int64_t(std::llround(width/cell)));
        entries_.clear();entries_.resize(count);buckets_.clear();wide_.clear();seen_.assign(count,0);stamp_=0;
        cache_.clear();cache_bytes_=0;++epoch_;++resets;
    }
    void cover(size_t id,CoverageBox b){
        ++updates;scratch_keys_.clear();bool wide=!finite(b);
        if(!wide){
            const auto [y0,y1,x0,n]=region(b);wide=n<=0||y1-y0+1>4096/std::max<int64_t>(1,n);
            if(!wide)for(auto y=y0;y<=y1;++y)for(int64_t i=0;i<n;++i)scratch_keys_.push_back(y*cols_+column(x0+i));
        }
        auto& e=entries_.at(id);
        bool equal=e.wide==wide&&e.cells.size()==scratch_keys_.size();
        if(equal)for(size_t i=0;i<e.cells.size();++i)if(e.cells[i].key!=scratch_keys_[i]){equal=false;break;}
        if(equal)return;
        erase(id);e.wide=wide;
        if(wide)wide_.push_back(id);
        else for(const auto key:scratch_keys_){auto& bucket=buckets_[key];e.cells.push_back({key,bucket.size()});bucket.push_back(id);}
        ++epoch_;++cell_changes;
    }
    std::span<const size_t> rectangle(CoverageBox b){
        ++queries;
        if(!finite(b)){scratch_ids_.clear();for(size_t i=0;i<entries_.size();++i)if(entries_[i].wide||!entries_[i].cells.empty())scratch_ids_.push_back(i);return scratch_ids_;}
        const auto key=region(b);auto found=cache_.find(key);
        if(found!=cache_.end()&&found->second.epoch==epoch_){++cache_hits;return found->second.ids;}
        scratch_ids_.clear();if(++stamp_==0){std::fill(seen_.begin(),seen_.end(),0);++stamp_;}
        const auto add=[&](size_t id){++raw_candidates;if(seen_[id]!=stamp_){seen_[id]=stamp_;scratch_ids_.push_back(id);}};
        const auto [y0,y1,x0,n]=key;
        if(y1-y0+1>4096/std::max<int64_t>(1,n)){
            for(const auto& [cell,ids]:buckets_){const auto row=int64_t(py::floordiv(double(cell),double(cols_)));const auto x=column(cell);if(row<y0||row>y1||column(x-x0)>=n)continue;for(const auto id:ids)add(id);}
        }else for(auto y=y0;y<=y1;++y)for(int64_t i=0;i<n;++i){const auto bucket=buckets_.find(y*cols_+column(x0+i));if(bucket!=buckets_.end())for(const auto id:bucket->second)add(id);}
        for(const auto id:wide_)add(id);std::sort(scratch_ids_.begin(),scratch_ids_.end());
        if(cache_.size()>=256||cache_bytes_+scratch_ids_.size()*sizeof(size_t)>4*1024*1024){cache_.clear();cache_bytes_=0;}
        auto& row=cache_[key];cache_bytes_-=row.ids.capacity()*sizeof(size_t);row.ids=scratch_ids_;row.epoch=epoch_;cache_bytes_+=row.ids.capacity()*sizeof(size_t);
        return row.ids;
    }
    size_t storage_bytes()const {size_t n=cache_bytes_+entries_.capacity()*sizeof(Entry)+seen_.capacity()*sizeof(uint64_t);for(const auto& e:entries_)n+=e.cells.capacity()*sizeof(CellSlot);for(const auto& [k,b]:buckets_)n+=sizeof(k)+b.capacity()*sizeof(size_t);return n;}
};
}
