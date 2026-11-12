#pragma once
#include "sim/typed/terrain.h"
#include <optional>
#include <span>
namespace pvz::typed72 {
// An ephemeral, ordered projection of the native plant roster for a legality
// query. It contains no HP, identity, owner, or mutable unit authority.
struct ColdPlacementPlant {
    std::string name;
    Cell cell;
    bool sleeping=false,basin=false,vine=false,air=false,sleep_present=false;
};
class ColdPlacementRules {
public:
    ColdPlacementRules(const WorldTerrain&,std::span<const ColdPlacementPlant>,std::span<const std::string> native_secrets,
                       std::string_view map_source={},double spike_cost=100.);
    double spike_cost;
    bool dense()const;
    bool water(int row,int64_t col)const;
    bool marker(int row,int64_t col)const;
    std::vector<const ColdPlacementPlant*> plants_at(int row,int64_t col)const;
    std::string dense_error(std::string_view name,int row,int64_t col)const;
    bool accepts(std::string_view name,int row,int64_t col)const;
    bool shell_cell(int row,int64_t col,bool vine)const;
    bool idle_cell(int row,int64_t col)const;
    bool grass_cell(int row,int64_t col)const;
    bool stone_cell(int row,int64_t col)const;
    std::string block(int row,int64_t col)const;
    bool solid(int row,int64_t col)const;
private:
    const WorldTerrain& map_;
    std::span<const ColdPlacementPlant> plants_;
    std::span<const std::string> secrets_;
    std::optional<int> bottom_rail_;
    bool secret(std::string_view)const;
    bool original_accepts(std::string_view,int,int64_t,std::span<const ColdPlacementPlant>,bool marked)const;
};
} // namespace pvz::typed72
