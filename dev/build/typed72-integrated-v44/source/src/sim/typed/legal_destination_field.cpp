#include "sim/typed/legal_destination_field.h"
#include "core/function_profile.h"
#include <algorithm>
#include <stdexcept>
namespace pvz::typed72 {
void LegalDestinationField::rebuild(const std::vector<std::vector<uint8_t>>& solid){
    PVP_PROFILE_SCOPE("LegalDestinationField::rebuild");++rebuilds;geometry_=solid;
    rows_=int(solid.size());cols_=rows_?int(solid.front().size()):0;
    for(const auto& row:solid)if(int(row.size())!=cols_)throw std::invalid_argument("ragged published rally map");
    const auto count=size_t(rows_)*cols_;owner_.assign(count,-1);distance_.assign(count,-1);queue_.clear();queue_.reserve(count);
    // Row-major sources make equal-distance ownership deterministic.
    for(int i=0;i<int(count);++i)if(!solid[size_t(i/cols_)][size_t(i%cols_)]){owner_[i]=i;distance_[i]=0;queue_.push_back(i);}
    for(size_t head=0;head<queue_.size();++head){const int at=queue_[head],y=at/cols_,x=at%cols_;++visited;
        const int next[4]={y?at-cols_:-1,y+1<rows_?at+cols_:-1,y*cols_+(x?x-1:cols_-1),y*cols_+(x+1<cols_?x+1:0)};
        for(const int n:next)if(n>=0&&distance_[n]<0){distance_[n]=distance_[at]+1;owner_[n]=owner_[at];queue_.push_back(n);}
    }
}
std::optional<Cell> LegalDestinationField::query(const std::vector<std::vector<uint8_t>>& solid,Cell requested){
    PVP_PROFILE_SCOPE("LegalDestinationField::query");++queries;
    // Byte-wise geometry comparison also catches fixture edits without a
    // publication revision; visual-only revisions do not rebuild this field.
    if(geometry_!=solid||rows_!=int(solid.size())||(rows_&&cols_!=int(solid.front().size())))rebuild(solid);else ++reused;
    if(requested.y<0||requested.y>=rows_||requested.x<0||requested.x>=cols_)return {};
    const int owner=owner_[size_t(requested.y)*cols_+size_t(requested.x)];
    return owner<0?std::optional<Cell>{}:Cell{owner/cols_,owner%cols_};
}
}
