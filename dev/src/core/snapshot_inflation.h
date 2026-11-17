#pragma once
#include <memory>
#include <string>

namespace pvz {
struct SnapshotInflateState {
    bool eof = false;
    std::string unused_data, unconsumed_tail;
};
// Independent of V: a decoder may run with the adapter GIL released.
class SnapshotInflater {
public:
    SnapshotInflater();
    ~SnapshotInflater();
    SnapshotInflater(const SnapshotInflater&) = delete;
    SnapshotInflater& operator=(const SnapshotInflater&) = delete;
    std::string decompress(const std::string& input, size_t max_length = 0);
    std::string flush();
    SnapshotInflateState state() const;
private:
    struct Impl;
    std::unique_ptr<Impl> impl;
};
}
