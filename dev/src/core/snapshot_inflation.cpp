#include "core/snapshot_inflation.h"
#define Z_PREFIX
#include "zlib-1.3.2-compress/zlib.h"
#include <algorithm>
#include <array>
#include <limits>
#include <mutex>
#include <stdexcept>

namespace pvz {
struct SnapshotInflater::Impl {
    z_stream stream{};
    mutable std::mutex mutex;
    SnapshotInflateState status;
    bool initialized = false;
    Impl() {
        const int code=inflateInit(&stream);
        if(code==Z_MEM_ERROR) throw std::bad_alloc();
        if(code!=Z_OK) throw std::runtime_error("zlib inflate initialization failed");
        initialized=true;
    }
    ~Impl() { if(initialized) inflateEnd(&stream); }
    std::string decompress(const std::string& input, size_t max_length, bool finish=false);
};
SnapshotInflater::SnapshotInflater():impl(std::make_unique<Impl>()) {}
SnapshotInflater::~SnapshotInflater()=default;
SnapshotInflateState SnapshotInflater::state() const {
    std::lock_guard<std::mutex> lock(impl->mutex);
    return impl->status;
}
std::string SnapshotInflater::decompress(const std::string& input,size_t max_length) {
    std::lock_guard<std::mutex> lock(impl->mutex);
    return impl->decompress(input,max_length);
}
std::string SnapshotInflater::flush() {
    std::lock_guard<std::mutex> lock(impl->mutex);
    if(!impl->initialized) return {};
    // A bounded decompress leaves input for flush to consume. Copy before the
    // decoder clears its public tail, and keep the operation under one lock.
    const std::string pending=impl->status.unconsumed_tail;
    auto result=impl->decompress(pending,0,true);
    if(impl->status.eof) {
        inflateEnd(&impl->stream);
        impl->initialized=false;
    }
    return result;
}
std::string SnapshotInflater::Impl::decompress(const std::string& input,size_t max_length,bool finish) {
    if(!initialized) throw std::runtime_error("inconsistent zlib stream state");
    auto& s=stream;
    if(input.size()>std::numeric_limits<uInt>::max()) throw std::overflow_error("zlib input too large");
    status.unconsumed_tail.clear();
    if(status.eof) { status.unused_data+=input; return {}; }
    s.next_in=reinterpret_cast<Bytef*>(const_cast<char*>(input.data()));
    s.avail_in=static_cast<uInt>(input.size());
    struct ResetPointers {
        z_stream& s;
        ~ResetPointers() { s.next_in=nullptr; s.avail_in=0; s.next_out=nullptr; s.avail_out=0; }
    } reset{s};
    std::string output;
    std::array<char,64*1024> buffer{};
    for(;;) {
        const size_t available=max_length?std::min(buffer.size(),max_length-output.size()):buffer.size();
        if(!available) break;
        s.next_out=reinterpret_cast<Bytef*>(buffer.data());
        s.avail_out=static_cast<uInt>(available);
        const auto before=s.avail_in;
        const int code=inflate(&s,finish?Z_FINISH:Z_NO_FLUSH);
        const size_t produced=available-s.avail_out;
        output.append(buffer.data(),produced);
        if(code==Z_STREAM_END) { status.eof=true; break; }
        if(code==Z_MEM_ERROR) throw std::bad_alloc();
        if(code!=Z_OK && code!=Z_BUF_ERROR) {
            // CPython flush returns available output on incomplete/bad streams;
            // eof stays false. Network validation uses strict decompress + eof.
            if(finish) break;
            throw std::runtime_error(s.msg?s.msg:"invalid zlib stream");
        }
        if(!produced && before==s.avail_in) break;
    }
    const auto remaining=input.substr(input.size()-s.avail_in);
    if(status.eof) status.unused_data+=remaining;
    else status.unconsumed_tail=remaining;
    // zlib retains its dictionary and bit state, never pointers into caller storage.
    return output;
}
}
