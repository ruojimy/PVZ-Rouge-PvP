#pragma once
#include "sim/typed/geometry.h"
#include <optional>
#include <vector>
#include <cstdint>
namespace pvz::typed72 {
// Voronoi projection to a legal rally cell, using the EXISTING wrapped
// Manhattan distance and (row,column) tie order. This does not select a combat
// target or replace movement-specific native flow fields.
class LegalDestinationField {
public:
    std::optional<Cell> query(const std::vector<std::vector<uint8_t>>& solid,Cell requested);
    uint64_t queries=0,rebuilds=0,reused=0,visited=0;
private:
    std::vector<std::vector<uint8_t>> geometry_;
    std::vector<int> owner_,distance_,queue_;
    int rows_=0,cols_=0;
    void rebuild(const std::vector<std::vector<uint8_t>>&);
};
}
