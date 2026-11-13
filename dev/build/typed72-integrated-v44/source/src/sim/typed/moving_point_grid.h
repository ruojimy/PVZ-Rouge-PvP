#pragma once
#include "sim/typed/coverage_grid.h"
#include <unordered_map>
namespace pvz::typed72 {
// Incremental point index for the original point-distance/route selectors.
// It deliberately does not replace collision volumes or navigation cells.
class MovingPointGrid {
public:
    void reset(double tile,double width,size_t count);
    void move(size_t id,Point);
    std::span<const size_t> rectangle(CoverageBox);
    double covering_radius(Point)const;
    size_t size()const{return entries_.size();}
    uint64_t rebuilds=0,moves=0,cell_changes=0,queries=0;
private:
    struct Entry {int64_t key=0;size_t slot=0;bool inserted=false;};
    double cell_=1.,width_=1.,min_y_=0.,max_y_=0.;int64_t cols_=1;
    std::vector<Entry> entries_;
    std::unordered_map<int64_t,std::vector<size_t>> buckets_;
    std::vector<size_t> result_;
    std::vector<uint64_t> seen_;uint64_t stamp_=0;
    int64_t column(int64_t)const;
    void append(const std::vector<size_t>&);
};
}
