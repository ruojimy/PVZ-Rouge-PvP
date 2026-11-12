#include "core/sym.h"
#include <deque>
#include <mutex>
#include <unordered_map>

namespace pvz {
namespace {
struct Table {
    std::deque<std::string> strings;
    std::deque<size_t> content_hashes;
    std::unordered_map<std::string_view, uint32_t> index;
    std::mutex mu;
    Table() { strings.emplace_back(); content_hashes.push_back(std::hash<std::string_view>()(strings.back())); index.emplace(strings.back(), 0); }
};
Table& table() { static Table t; return t; }
}  // namespace

Sym::Sym(std::string_view s) {
    Table& t = table();
    std::lock_guard<std::mutex> lock(t.mu);
    auto it = t.index.find(s);
    if (it != t.index.end()) { id = it->second; return; }
    t.strings.emplace_back(s);
    t.content_hashes.push_back(std::hash<std::string_view>()(s));
    id = uint32_t(t.strings.size() - 1);
    t.index.emplace(t.strings.back(), id);
}

const std::string& Sym::str() const { return table().strings[id]; }

size_t symbol_text_hash(uint32_t id) { return table().content_hashes[id]; }

size_t sym_count() { return table().strings.size(); }

}  // namespace pvz
