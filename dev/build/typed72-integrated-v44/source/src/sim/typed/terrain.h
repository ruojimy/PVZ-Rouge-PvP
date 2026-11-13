#pragma once
#include "sim/typed/state.h"
namespace pvz::typed72 {
// A map record owns terrain/placement markers, not another plant's HP.
// Shared records preserve references held while callbacks replace a cell.
#define PVZ72_TILE_NUMBERS(X) \
 X(lily,"睡莲") X(root_animation,"根动画") X(destroyed,"摧") X(snow_gone,"雪消失") \
 X(growing,"长出") X(wave,"水纹") X(wave_cd,"水纹cd") X(grave_art,"坟墓")
#define PVZ72_TILE_FLAGS(X) \
 X(plant,"植物") X(empty_marker,"kong") X(pot,"花盆") X(stone_placeholder,"智能石块占位") X(belt,"_pvp_belt")
struct TerrainCell {
    Field<std::string> basin;
    // custom_maps.document_cell appearance metadata (_pvp_block_color / _pvp_wall_color, RGB ints):
    // kept with the native cell through the battle, publication and replay; never gameplay.
    Field<std::vector<int64_t>> block_color,wall_color;
    Field<std::string> block,inner_block;
#define NUM(n,k) Field<double> n;
    PVZ72_TILE_NUMBERS(NUM)
#undef NUM
#define FLAG(n,k) Field<bool> n;
    PVZ72_TILE_FLAGS(FLAG)
#undef FLAG
};
using TileRef=std::shared_ptr<TerrainCell>;
struct ImportantBlock {Cell cell;std::string block;};
class WorldTerrain {
public:
    std::vector<std::vector<TileRef>> grid;
    std::vector<std::string> empty_blocks;
    std::vector<ImportantBlock> important;
    double water_surface=0.;
    bool periodic_x=true;
    int rows()const{return static_cast<int>(grid.size());}
    int cols()const{return grid.empty()?0:static_cast<int>(grid.front().size());}
    int wrap(int64_t col)const {
        const auto width=cols();if(width<=0)throw std::domain_error("empty terrain width");const auto r=col%width;return int(r<0?r+width:r);
    }
    bool valid_row(int row)const{return row>=0&&row<rows();}
    bool outside(int64_t row,int64_t col)const{return row<0||row>=rows()||(!periodic_x&&(col<0||col>=cols()));}
    TileRef at(int64_t row,int64_t col)const {
        if(row<0||row>=rows())return {};
        const auto& cells=grid[size_t(row)];if(col<0||uint64_t(col)>=cells.size())return {};return cells[size_t(col)];
    }
    TerrainCell& native_at(int64_t row,int64_t col)const {
        const auto& cells=grid.at(native_index(row,grid.size()));
        if(periodic_x && !cells.empty())col%=int64_t(cells.size());
        const auto& cell=cells.at(native_index(col,cells.size()));
        if(!cell)throw std::logic_error("native terrain cell is not a record");return *cell;
    }
    bool is_empty(std::string_view block)const{return std::find(empty_blocks.begin(),empty_blocks.end(),block)!=empty_blocks.end();}
    bool empty(int64_t row,int64_t col)const {
        if(row<0||row>=rows())throw std::out_of_range("terrain query row");
        const auto& block=native_at(row,wrap(col)).block;if(!block.present())throw std::logic_error("missing terrain block");
        return !block.is_null()&&is_empty(block.get());
    }
    bool empty_canonical(int row,int col)const {
        const auto& cells=grid.at(size_t(row));
        if(cells.size()!=size_t(cols()))return empty(row,col);
        const auto& cell=cells.at(size_t(col));if(!cell)throw std::logic_error("native terrain cell is not a record");
        const auto& block=cell->block;if(!block.present())throw std::logic_error("missing terrain block");
        return !block.is_null()&&is_empty(block.get());
    }
    bool water(int64_t row,int64_t col)const {
        if(row<0||row>=rows())throw std::out_of_range("terrain query row");
        const auto& block=native_at(row,wrap(col)).block;if(!block.present())throw std::logic_error("missing terrain block");
        return !block.is_null()&&(block.get()=="水"||block.get()=="黑水");
    }
private:
    static size_t native_index(int64_t index,size_t size) {
        if(index<0)index+=static_cast<int64_t>(size);
        if(index<0||uint64_t(index)>=size)throw std::out_of_range("native terrain index");return size_t(index);
    }
};
} // namespace pvz::typed72
