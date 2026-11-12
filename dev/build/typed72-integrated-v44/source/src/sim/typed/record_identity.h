#pragma once
#include <cstdint>
#include <limits>
#include <stdexcept>
namespace pvz::typed72 {
// Logical object identity survives roster/handle replacement. It never uses
// an address and can be remapped at save/replay boundaries independently of
// the lazily allocated, player-visible native source IDs.
struct RecordId {uint64_t value=0;friend bool operator==(RecordId,RecordId)=default;};
class RecordIdentities {
public:
    RecordId assign() {
        if(next_==std::numeric_limits<uint64_t>::max())throw std::overflow_error("record identity exhausted");
        return {++next_};
    }
    uint64_t last()const{return next_;}
private:
    uint64_t next_=0;
};
} // namespace pvz::typed72
