#pragma once
#include "sim/typed/geometry.h"
#include <cstdint>
#include <cstddef>
#include <span>
#include <utility>
#include <vector>
namespace pvz::typed72 {
struct CoverageBox {double left,top,right,bottom;};
// Retain only candidates across synchronous death/replace callbacks. The legacy
// branch retains its original full shallow copy for differential verification.
template<class Ref> struct SpatialSelection {
    std::vector<Ref> values;std::vector<size_t> indices;
    size_t ordinal(size_t n)const{return indices.empty()?n:indices[n];}
    static SpatialSelection legacy(const std::vector<Ref>& all){return {all,{}};}
    static SpatialSelection local(const std::vector<Ref>& all,std::span<const size_t> ids){
        SpatialSelection result;result.values.reserve(ids.size());result.indices.assign(ids.begin(),ids.end());
        for(const auto id:ids)result.values.push_back(all.at(id));return result;
    }
};
// Conservative broad phase only. Clients keep their exact shape, faction,
// hit budget and traversal order. Cell size is supplied from native geometry.
class CoverageGrid {
public:
    void reset(double cell,double width,int rows,size_t ids);
    void cover(size_t id,CoverageBox);
    void finish();
    std::span<const size_t> point(Point);
    std::span<const size_t> rectangle(CoverageBox);
    std::span<const size_t> segment(Point from,Point to);
    size_t occupied_cells()const{return ranges_.size();}
    double cell_size()const{return cell_;}
    int64_t columns()const{return cols_;}
    size_t storage_bytes()const{return marks_.capacity()*sizeof(marks_[0])+ids_.capacity()*sizeof(size_t)+candidates_.capacity()*sizeof(size_t)+unbounded_.capacity()*sizeof(size_t)+touched_.capacity()*sizeof(size_t)+ranges_.capacity()*sizeof(Range)+dense_.capacity()*sizeof(DenseRange)+seen_.capacity()*sizeof(uint64_t);}
    uint64_t builds=0,queries=0,visited_cells=0,raw_candidates=0,unique_candidates=0;
private:
    struct Range {int64_t key;uint32_t first=0,count=0;};
    struct DenseRange {uint32_t first=0,count=0;};
    double cell_=1.,width_=1.;int64_t cols_=1;int rows_=0;
    std::vector<std::pair<int64_t,size_t>> marks_;
    std::vector<size_t> ids_,candidates_,unbounded_,touched_;
    std::vector<Range> ranges_;
    std::vector<DenseRange> dense_;
    std::vector<uint64_t> seen_;uint64_t stamp_=0;
    int64_t column(int64_t x)const;
    void begin_query();
    void gather(int64_t row,int64_t col);
    void append(uint32_t first,uint32_t count);
    void append_id(size_t id);
    std::span<const size_t> end_query();
};
}
