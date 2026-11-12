// PvP73 render performance: a native LRU for pvp.bounded_cache.BudgetCache.
//
// The translated BudgetCache kept an OrderedDict and called move_to_end on every hit. In the V
// runtime that is a linear key scan plus a vector erase/insert, and it invalidates the dict's hash
// index, so the next lookup rebuilt the index from scratch. Text/scaled-image caches hold thousands
// of entries keyed by (font, text, colour) - an instance key the V index cannot hash - so every
// lookup degraded to a linear scan of tuple comparisons. Render time grew as the caches filled
// (online play went from 14 ms to 22 ms per frame in an empty battle).
//
// Same contract as the Python class: entry and pixel-byte limits, exact values, oversized values
// not retained, least-recently-used eviction, hits/misses/evictions/clears/oversized statistics.
// Keys hash like Python: str/number/bool/None/tuple by value, pygame objects by identity.
#include "sim/pvp/pvprt.h"
#include <algorithm>
#include <cstring>
#include <list>
#include <unordered_map>
namespace pvz {
namespace {
bool key_hash(const V& k, uint64_t& h) {
    switch (k.t) {
        case V::STR: { const std::string_view s = k.str(); h = std::hash<std::string_view>()(s) ^ 0x51ull; return true; }
        case V::NUM: case V::BOOL: { double d = k.t == V::NUM ? k.n : (k.b ? 1. : 0.); if (d == 0.) d = 0.; std::memcpy(&h, &d, 8); h ^= 0x2ull; return true; }
        case V::NONE: h = 0x9e37ull; return true;
        case V::TUPLE: {
            uint64_t acc = 0x84222325cbf29ce4ull ^ k.box->items.size();
            for (const auto& x : k.box->items) { uint64_t c; if (!key_hash(x, c)) return false; acc = (acc ^ (c * 0x9E3779B97F4A7C15ull)) * 0x100000001b3ull; acc ^= acc >> 31; }
            h = acc; return true;
        }
        case V::INST: h = uint64_t(reinterpret_cast<uintptr_t>(k.box.get())) * 0x9E3779B97F4A7C15ull; return true;   // identity
        default: return false;
    }
}
bool key_eq(const V& a, const V& b) {
    if (a.t != b.t) return (a.t == V::NUM || a.t == V::BOOL) && (b.t == V::NUM || b.t == V::BOOL) && py_eq(a, b);
    switch (a.t) {
        case V::STR: return a.str() == b.str();
        case V::NUM: return a.n == b.n;
        case V::BOOL: return a.b == b.b;
        case V::NONE: return true;
        case V::INST: return a.box.get() == b.box.get();
        case V::TUPLE: {
            const auto& x = a.box->items; const auto& y = b.box->items;
            if (x.size() != y.size()) return false;
            for (size_t i = 0; i < x.size(); ++i) if (!key_eq(x[i], y[i])) return false;
            return true;
        }
        default: return py_eq(a, b);
    }
}
struct Key { V v; uint64_t h; };
struct KeyHash { size_t operator()(const Key& k) const { return size_t(k.h); } };
struct KeyEq { bool operator()(const Key& a, const Key& b) const { return a.h == b.h && key_eq(a.v, b.v); } };

struct NativeBudgetCache final : PyObj {
    struct Entry { V key, value; int64_t bytes; };
    std::list<Entry> order;   // front = least recently used
    std::unordered_map<Key, std::list<Entry>::iterator, KeyHash, KeyEq> index;
    int64_t entries, byte_limit, bytes = 0, peak_bytes = 0;
    int64_t hits = 0, misses = 0, evictions = 0, clears = 0, oversized = 0;
    V size_fn;
    NativeBudgetCache(int64_t e, int64_t limit, V size) : entries(e), byte_limit(limit), size_fn(std::move(size)) {}
    const char* type_name() const override { return "BudgetCache"; }
    bool isa(const char* c) const override { return std::string(c) == "BudgetCache" || std::string(c) == "object"; }
    static Key make_key(const V& key) {
        uint64_t h; if (!key_hash(key, h)) throw PyError("TypeError", "unhashable cache key");
        return {key, h};
    }
    int64_t measure(const V& value) {
        if (!size_fn.is_none()) return std::max<int64_t>(0, int64_t(size_fn.call(Args{value}).num()));
        return std::max<int64_t>(0, int64_t(callm(value, Sym("get_pitch"), Args{}).num() * callm(value, Sym("get_height"), Args{}).num()));
    }
    V get(const V& key, const V& dflt) {
        uint64_t h; if (!key_hash(key, h)) { ++misses; return dflt; }
        const auto it = index.find(Key{key, h});
        if (it == index.end()) { ++misses; return dflt; }
        ++hits; order.splice(order.end(), order, it->second);   // move_to_end, O(1)
        return it->second->value;
    }
    void erase_key(const Key& k) {
        const auto it = index.find(k); if (it == index.end()) return;
        bytes -= it->second->bytes; order.erase(it->second); index.erase(it);
    }
    void set(const V& key, const V& value) {
        const Key k = make_key(key);
        const int64_t amount = measure(value);
        erase_key(k);
        if (amount > byte_limit) { ++oversized; return; }   // the caller still draws its local value
        while (!order.empty() && (int64_t(order.size()) >= entries || bytes + amount > byte_limit)) {
            const auto& old = order.front(); uint64_t h; key_hash(old.key, h);
            bytes -= old.bytes; index.erase(Key{old.key, h}); order.pop_front(); ++evictions;
        }
        order.push_back({key, value, amount});
        index.emplace(k, std::prev(order.end()));
        bytes += amount; peak_bytes = std::max(peak_bytes, bytes);
    }
    void clear_all() { order.clear(); index.clear(); bytes = 0; ++clears; }
    V getitem(const V& key) override {
        uint64_t h; if (!key_hash(key, h) || !index.count(Key{key, h})) throw PyError("KeyError", py_str(key));
        return get(key, V::none());
    }
    void setitem(const V& key, const V& value) override { set(key, value); }
    void delitem(const V& key) override { uint64_t h; if (!key_hash(key, h) || !index.count(Key{key, h})) throw PyError("KeyError", py_str(key)); erase_key(Key{key, h}); }
    bool contains(const V& key) override { uint64_t h; return key_hash(key, h) && index.count(Key{key, h}); }
    size_t length() override { return order.size(); }
    bool truth() override { return !order.empty(); }
    V iterate() override { V out = V::list(); for (const auto& e : order) out.append(e.key); return out; }
    V stats() const {
        V d = V::dict();
        d.at(V("items")) = V(double(order.size())); d.at(V("bytes")) = V(double(bytes)); d.at(V("peak_bytes")) = V(double(peak_bytes));
        d.at(V("byte_limit")) = V(double(byte_limit)); d.at(V("entry_limit")) = V(double(entries));
        d.at(V("hits")) = V(double(hits)); d.at(V("misses")) = V(double(misses)); d.at(V("evictions")) = V(double(evictions));
        d.at(V("clears")) = V(double(clears)); d.at(V("oversized")) = V(double(oversized));
        return d;
    }
    V property(Sym name, bool& found) override {
        found = true;
        if (name == Sym("hits")) return V(double(hits));
        if (name == Sym("misses")) return V(double(misses));
        if (name == Sym("evictions")) return V(double(evictions));
        if (name == Sym("bytes")) return V(double(bytes));
        if (name == Sym("peak_bytes")) return V(double(peak_bytes));
        if (name == Sym("entries")) return V(double(entries));
        if (name == Sym("byte_limit")) return V(double(byte_limit));
        if (name == Sym("data")) {   // read-only view {key: (value, bytes)} like the Python OrderedDict
            V d = V::dict(); for (const auto& e : order) d.at(e.key) = V::tuple({e.value, V(double(e.bytes))}); return d;
        }
        found = false; return V();
    }
    V method(Sym name) override {
        auto self = std::static_pointer_cast<NativeBudgetCache>(shared_from_this());
        if (name == Sym("get")) return V::func([self](const Args& a) { static const V none = V::none(); return self->get(a.get(0, Sym("key"), nullptr), a.get(1, Sym("default"), &none)); });
        if (name == Sym("clear")) return V::func([self](const Args&) { self->clear_all(); return V::none(); });
        if (name == Sym("stats")) return V::func([self](const Args&) { return self->stats(); });
        if (name == Sym("keys")) return V::func([self](const Args&) { return self->iterate(); });
        if (name == Sym("values")) return V::func([self](const Args&) { V out = V::list(); for (const auto& e : self->order) out.append(e.value); return out; });
        if (name == Sym("items")) return V::func([self](const Args&) { V out = V::list(); for (const auto& e : self->order) out.append(V::tuple({e.key, e.value})); return out; });
        if (name == Sym("pop")) return V::func([self](const Args& a) {
            const V key = a.get(0, Sym("key"), nullptr); uint64_t h;
            if (key_hash(key, h)) { const auto it = self->index.find(Key{key, h}); if (it != self->index.end()) { V v = it->second->value; self->erase_key(Key{key, h}); return v; } }
            if (a.size() > 1) return a.pos[1];
            throw PyError("KeyError", py_str(key));
        });
        return V();
    }
};
}
V native_budget_cache(const V& entries, const V& byte_limit, const V& size) {
    return V::inst(std::make_shared<NativeBudgetCache>(int64_t(entries.num()), int64_t(byte_limit.num()), size));
}
}  // namespace pvz
