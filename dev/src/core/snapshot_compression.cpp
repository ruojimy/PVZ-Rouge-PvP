#include "core/snapshot_compression.h"
#include "core/value.h"
#define Z_PREFIX
#include "zlib-1.3.2-compress/zlib.h"
#include <limits>
namespace pvz {
std::string snapshot_compress(const std::string& input, int level) {
    if(input.size()>std::numeric_limits<uLong>::max())throw PyError("OverflowError","zlib input too large");
    uLongf size=compressBound(uLong(input.size()));std::string output(size,'\0');
    int error=compress2(reinterpret_cast<Bytef*>(output.data()),&size,
        reinterpret_cast<const Bytef*>(input.data()),uLong(input.size()),level);
    if(error==Z_MEM_ERROR)throw PyError("MemoryError","zlib compression allocation failed");
    if(error!=Z_OK)throw PyError("ValueError","zlib compression failed: "+std::to_string(error));
    output.resize(size);return output;
}
}
