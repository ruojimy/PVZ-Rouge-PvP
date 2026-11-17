#pragma once
#include <string>
namespace pvz {
// Data-only fast path for immutable native marshal snapshots. False requests
// the existing V codec for uncommon mapping keys / unsupported representations.
// Never touches V, symbols, Python exceptions, or the global interpreter lock.
bool snapshot_json_from_marshal(const std::string& frozen, std::string& json);
}
