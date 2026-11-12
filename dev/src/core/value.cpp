#include "core/value.h"
#include "core/number_text.h"
#include "core/obj.h"
#include "core/pyobj.h"
#include <cstdio>
#include <cstring>
#include <unordered_map>
#include <algorithm>

namespace pvz {
size_t symbol_text_hash(uint32_t id);

bool is_ordered_dict(const V& value) {
    if(value.t!=V::DICT)return false;
    for(const auto& attr:value.box->fattrs)if(attr.first==Sym("__native_ordered_dict__"))return attr.second.truthy();
    return false;
}

namespace {
// All Box values already have intrusive reference counts. Keep an intrusive
// inventory too, without an allocating registry or changes to the V ABI.
// The GIL is required, just as it is for every existing Box reference count.
struct TrackedBox;
TrackedBox* live_boxes=nullptr;
struct TrackedBox final : Box {
    TrackedBox* previous=nullptr;
    TrackedBox* next=nullptr;
    TrackedBox() {
        next=live_boxes;if(next)next->previous=this;live_boxes=this;
    }
    ~TrackedBox() {
        if(previous)previous->next=next;else live_boxes=next;
        if(next)next->previous=previous;
    }
};
template<class F> void traced_box_edges(const Box& box,F&& visit) {
    auto value=[&](const V& item){if(item.box)visit(item.box.get());};
    for(const V& item:box.items)value(item);
    for(const auto& item:box.kv){value(item.first);value(item.second);}
    for(const auto& item:box.fattrs)value(item.second);
    if(box.obj) {
        for(const auto& key:obj_keys())value(box.obj.get()->*(key.member));
        for(const auto& item:box.obj->extras){value(item.first);value(item.second);}
    }
}
}
Box::~Box() = default;
// Conservative trial deletion for containers. Opaque C++ callables, native
// instances and hooked dictionaries remain roots. Untraced references also
// remain roots because their actual rc is not subtracted. This deliberately
// does NOT claim to collect native-instance or closure cycles.
size_t collect_container_cycles() {
    std::vector<TrackedBox*> boxes;
    for(auto* box=live_boxes;box;box=box->next)boxes.push_back(box);
    std::unordered_map<const Box*,size_t> index;index.reserve(boxes.size());
    for(size_t i=0;i<boxes.size();++i)index.emplace(boxes[i],i);
    std::vector<size_t> incoming(boxes.size(),0),pending;
    std::vector<unsigned char> reachable(boxes.size(),0);
    for(const auto* box:boxes)traced_box_edges(*box,[&](const Box* child){auto i=index.find(child);if(i!=index.end())++incoming[i->second];});
    for(size_t i=0;i<boxes.size();++i) {
        const auto* box=boxes[i];
        if(box->rc<0 || incoming[i]>size_t(box->rc))throw PyError("RuntimeError","invalid native container reference graph");
        if(size_t(box->rc)>incoming[i] || box->inst || box->fn || (box->obj && box->obj->hook)) {
            reachable[i]=1;pending.push_back(i);
        }
    }
    while(!pending.empty()) {
        size_t i=pending.back();pending.pop_back();
        traced_box_edges(*boxes[i],[&](const Box* child){auto found=index.find(child);if(found!=index.end() && !reachable[found->second]){reachable[found->second]=1;pending.push_back(found->second);}});
    }
    // Protect every unreachable node before severing any edge. Clearing one
    // cycle must not leave a dangling pointer later in the inventory snapshot.
    std::vector<BoxP> held;
    for(size_t i=0;i<boxes.size();++i)if(!reachable[i])held.emplace_back(boxes[i]);
    for(auto& hold:held) {
        Box& box=*hold;box.items.clear();box.kv.clear();box.fattrs.clear();
        box.obj.reset();box.kidx.clear();box.kidx_valid=false;box.text.clear();
    }
    return held.size();
}
bool native_box_is_live(const Box* wanted) {
    for(const auto* box=live_boxes;box;box=box->next)if(box==wanted)return true;
    return false;
}
size_t native_live_box_count() {
    size_t count=0;for(const auto* box=live_boxes;box;box=box->next)++count;return count;
}

int alloc_anchor();
static int g_alloc_anchor = alloc_anchor();   // links src/core/alloc.cpp (global operator new)
void box_release(BoxBase* b) { delete static_cast<TrackedBox*>(b); }
V::V(const char* x) : t(STR), n(0) {
    size_t len = std::strlen(x);
    if (len <= kShortStr) { s = Sym(std::string_view(x, len)).id; return; }
    s = kLong; box = make_box(); box->text.assign(x, len);
}
V::V(const std::string& x) : t(STR), n(0) {
    if (x.empty()) { s=0; return; }
    s = kLong; box = make_box(); box->text = x;
}
V::V(std::string&& x) : t(STR), n(0) {
    if (x.empty()) { s=0; return; }
    s = kLong; box = make_box(); box->text = std::move(x);
}
Sym V::sym() const {
    if (t != STR) throw PyError("TypeError", "not a string (" + type_name() + ")");
    return s == kLong ? Sym(box->text) : Sym(s);
}
// PvP73 pure-typed gate: per-thread V activity (box allocations + call dispatch). The typed battle
// adapter samples it around its dynamic entry points; any V work inside them is a gate failure.
thread_local uint64_t g_v_activity_boxes = 0;
thread_local uint64_t g_v_activity_calls = 0;
VActivity v_activity() { return {g_v_activity_boxes, g_v_activity_calls}; }
BoxP make_box() { ++g_v_activity_boxes; return BoxP(new TrackedBox()); }

V V::list(std::vector<V> items) { V v; v.t = LIST; v.box = make_box(); v.box->items = std::move(items); return v; }
V V::tuple(std::vector<V> items) { V v = list(std::move(items)); v.t = TUPLE; return v; }
V V::dict() { V v; v.t = DICT; v.box = make_box(); return v; }
V V::obj() { V v; v.t = OBJ; v.box = make_box(); v.box->obj = std::make_unique<Obj>(); return v; }
V V::func(Fn f) { V v; v.t = FUNC; v.box = make_box(); v.box->fn = std::move(f); return v; }
V V::inst(std::shared_ptr<PyObj> p) { V v; v.t = INST; v.box = make_box(); v.box->inst = std::move(p); return v; }
V V::set(std::vector<V> items) {
    V v; v.t = SET; v.box = make_box();
    for (auto& x : items) if (!v.contains(x)) v.set_insert_new(x);
    return v;
}
// ---- set membership: a hash index over box->items (reusing the dict index fields) once a set grows,
// so building a large set (pvp67 taco artwork: tens of thousands of pixel tuples) is not quadratic
static bool hashable_key(const V& k) {
    switch (k.t) {
        case V::NUM: case V::BOOL: case V::STR: return true;
        case V::TUPLE: for (auto& x : k.box->items) if (!hashable_key(x)) return false; return true;
        default: return false;
    }
}
static constexpr size_t kSetIndexMin = 24;
static size_t set_index_hash(const V& key) {
    // libc++'s 64-bit hash<double> is the binary64 representation. Pixel
    // coordinates therefore have zero low bits, and a tuple's public hash
    // retains those weak low bits. Mix only the private bucket hash before
    // masking a power-of-two table; leave py_hash and set iteration untouched.
    uint64_t h = static_cast<uint64_t>(py_hash(key));
    h ^= h >> 30;
    h *= 0xbf58476d1ce4e5b9ULL;
    h ^= h >> 27;
    h *= 0x94d049bb133111ebULL;
    h ^= h >> 31;
    return static_cast<size_t>(h);
}
static void set_index_put(Box* b, size_t i) {
    size_t mask = b->kidx.size() - 1, h = set_index_hash(b->items[i]) & mask;
    while (b->kidx[h]) h = (h + 1) & mask;
    b->kidx[h] = uint32_t(i + 1);
}
static bool set_index_build(Box* b) {
    for (auto& x : b->items) if (!hashable_key(x)) return false;
    size_t cap = 32;
    while (cap < b->items.size() * 2 + 2) cap <<= 1;
    b->kidx.assign(cap, 0u);
    for (size_t i = 0; i < b->items.size(); ++i) set_index_put(b, i);
    b->kidx_valid = true;
    return true;
}
static int set_index_find(Box* b, const V& key) {   // 1 found, 0 absent, -1 no index
    if (!b->kidx_valid && !set_index_build(b)) return -1;
    size_t mask = b->kidx.size() - 1, h = set_index_hash(key) & mask;
    while (uint32_t s = b->kidx[h]) {
        if (py_eq(b->items[s - 1], key)) return 1;
        h = (h + 1) & mask;
    }
    return 0;
}
// remove key from a SET; with an index: backward-shift deletion + swap-with-last (O(1)); else linear
bool V::set_erase(const V& key) const {
    Box* b = box.get();
    auto& it = b->items;
    if (it.size() >= kSetIndexMin && hashable_key(key) && (b->kidx_valid || set_index_build(b))) {
        size_t mask = b->kidx.size() - 1, h = set_index_hash(key) & mask;
        while (b->kidx[h] && !py_eq(it[b->kidx[h] - 1], key)) h = (h + 1) & mask;
        if (!b->kidx[h]) return false;
        size_t pos = b->kidx[h] - 1;
        // backward-shift delete slot h
        size_t hole = h, j = h;
        for (;;) {
            j = (j + 1) & mask;
            if (!b->kidx[j]) break;
            size_t home = set_index_hash(it[b->kidx[j] - 1]) & mask;
            bool between = hole <= j ? (hole < home && home <= j) : (hole < home || home <= j);
            if (!between) { b->kidx[hole] = b->kidx[j]; hole = j; }
        }
        b->kidx[hole] = 0;
        size_t last = it.size() - 1;
        if (pos != last) {   // move the last element into pos and repoint its slot
            size_t g = set_index_hash(it[last]) & mask;
            while (b->kidx[g] != last + 1) g = (g + 1) & mask;
            b->kidx[g] = uint32_t(pos + 1);
            it[pos] = std::move(it[last]);
        }
        it.pop_back();
        return true;
    }
    for (size_t i = 0; i < it.size(); ++i)
        if (py_eq(it[i], key)) { it.erase(it.begin() + i); b->kidx_valid = false; return true; }
    return false;
}
void V::set_insert_new(const V& x) const {
    Box* b = box.get();
    b->items.push_back(x);
    if (!b->kidx_valid) return;
    if (!hashable_key(x) || b->items.size() * 2 > b->kidx.size()) { b->kidx_valid = false; return; }
    set_index_put(b, b->items.size() - 1);
}
PyObj* V::inst_ptr() const {
    if (t != INST) throw PyError("TypeError", "not an instance (" + type_name() + ")");
    return box->inst.get();
}
bool exception_matches(const std::string& kind, const std::vector<std::string>& bases, const char* type) {
    std::string t(type);
    if (t == "Exception" || t == "BaseException" || t == kind) return true;
    for (auto& b : bases) if (b == t) return true;
    // python's built-in exception hierarchy (child -> parent)
    static const std::pair<const char*, const char*> parent[] = {
        {"KeyError", "LookupError"}, {"IndexError", "LookupError"}, {"ZeroDivisionError", "ArithmeticError"},
        {"OverflowError", "ArithmeticError"}, {"FloatingPointError", "ArithmeticError"},
        {"FileNotFoundError", "OSError"}, {"FileExistsError", "OSError"}, {"PermissionError", "OSError"},
        {"IsADirectoryError", "OSError"}, {"NotADirectoryError", "OSError"}, {"TimeoutError", "OSError"},
        {"BlockingIOError", "OSError"}, {"InterruptedError", "OSError"}, {"ConnectionError", "OSError"},
        {"ConnectionResetError", "ConnectionError"}, {"ConnectionRefusedError", "ConnectionError"},
        {"ConnectionAbortedError", "ConnectionError"}, {"BrokenPipeError", "ConnectionError"},
        {"gaierror", "OSError"}, {"timeout", "OSError"}, {"herror", "OSError"},
        {"IOError", "OSError"}, {"EnvironmentError", "OSError"},
        {"UnicodeDecodeError", "UnicodeError"}, {"UnicodeEncodeError", "UnicodeError"}, {"UnicodeError", "ValueError"},
        {"JSONDecodeError", "ValueError"}, {"ModuleNotFoundError", "ImportError"},
        {"RecursionError", "RuntimeError"}, {"NotImplementedError", "RuntimeError"},
        {"UnboundLocalError", "NameError"}, {"TabError", "IndentationError"}, {"IndentationError", "SyntaxError"}};
    std::string cur = kind;
    for (int guard = 0; guard < 8; ++guard) {
        const char* up = nullptr;
        for (auto& [c, p] : parent) if (cur == c) { up = p; break; }
        if (!up) break;
        if (t == up) return true;
        cur = up;
    }
    for (auto& b : bases) {
        std::string c2 = b;
        for (int guard = 0; guard < 8; ++guard) {
            const char* up = nullptr;
            for (auto& [c, p] : parent) if (c2 == c) { up = p; break; }
            if (!up) break;
            if (t == up) return true;
            c2 = up;
        }
    }
    return false;
}
bool PyError::matches(const char* type) const { return exception_matches(kind,bases,type); }
V Args::get(size_t i, Sym name, const V* dflt, const char* fn) const {
    if (i < pos.size()) return pos[i];
    for (auto& p : kw) if (p.first == name) return p.second;
    if (dflt) return *dflt;
    throw PyError("TypeError", std::string(fn) + "() missing required argument: '" + name.str() + "'");
}
V Args::rest(size_t from) const {
    std::vector<V> r;
    for (size_t i = from; i < pos.size(); ++i) r.push_back(pos[i]);
    return V::tuple(std::move(r));
}
V Args::kwrest(std::initializer_list<const char*> known) const {
    V d = V::dict();
    for (auto& p : kw) {
        bool k = false;
        for (auto* n : known) if (p.first == Sym(n)) { k = true; break; }
        if (!k) d.at(V(p.first)) = p.second;
    }
    return d;
}
V V::nums(std::initializer_list<double> xs) {
    std::vector<V> it; it.reserve(xs.size());
    for (double x : xs) it.emplace_back(x);
    return list(std::move(it));
}

bool V::truthy() const {
    switch (t) {
        case ABSENT: case NONE: return false;
        case BOOL: return b;
        case NUM: return n != 0.0;
        case STR: return s != 0;
        case LIST: case TUPLE: return !box->items.empty();
        case DICT: return !box->kv.empty();
        case OBJ: return box->obj->size() != 0;
        case FUNC: return true;
        case INST: return box->inst->truth();
        case SET: return !box->items.empty();
    }
    return false;
}

std::string V::type_name() const {
    if(is_ordered_dict(*this))return "OrderedDict";
    static const char* names[] = {"absent", "NoneType", "bool", "num", "str", "list", "tuple", "dict", "obj", "function", "instance", "set"};
    return names[t];
}

Obj* V::o() const {
    if (t != OBJ) throw PyError("TypeError", "not a unit dict (" + type_name() + ")");
    return box->obj.get();
}

std::vector<V>& V::items() {
    if (!is_list()) throw PyError("TypeError", "not a list (" + type_name() + ")");
    if (t == SET) box->kidx_valid = false;   // caller may mutate
    return box->items;
}
const std::vector<V>& V::items() const {
    if (!is_list()) throw PyError("TypeError", "not a list (" + type_name() + ")");
    return box->items;
}
size_t V::len() const {
    switch (t) {
        case LIST: case TUPLE: case SET: return box->items.size();
        case DICT: return box->kv.size();
        case OBJ: return box->obj->size();
        case INST: return box->inst->length();
        case STR: {
            if (byt) return str().size();
            // python len() counts code points
            const std::string& u = str();
            size_t n = 0;
            for (unsigned char c : u) if ((c & 0xC0) != 0x80) ++n;
            return n;
        }
        default: throw PyError("TypeError", "object of type '" + type_name() + "' has no len()");
    }
}
static inline int64_t norm_index(int64_t i, int64_t n, bool periodic) {
    if (i >= 0 && i < n) return i;
    if (i < 0 && i >= -n) return i + n;
    if (periodic && n) { int64_t m = i % n; return m < 0 ? m + n : m; }
    throw PyError("IndexError", "list index out of range");
}
V& V::idx_slow(int64_t i) {
    auto& it = items();
    return it[size_t(norm_index(i, int64_t(it.size()), box->periodic))];
}
const V& V::idx_slow(int64_t i) const {
    const auto& it = items();
    return it[size_t(norm_index(i, int64_t(it.size()), box->periodic))];
}
void V::append(V x) const { const_cast<V*>(this)->items().push_back(std::move(x)); }

std::vector<std::pair<V, V>>& V::kv() {
    if (!is_dict()) throw PyError("TypeError", "not a dict (" + type_name() + ")");
    box->kidx_valid = false;   // caller may mutate
    return box->kv;
}

// ---- dict key lookup: integer compares for str/num keys, hash index for large dicts
// 1 = string key (code = sym), 2 = numeric key (code = double bits), 0 = other
static int key_code(const V& k, uint64_t& code) {
    if (k.t == V::STR) { code = k.s == V::kLong ? std::hash<std::string_view>()(k.box->text) : symbol_text_hash(k.s); return 1; }
    if (k.t == V::NUM || k.t == V::BOOL) {
        double d = k.t == V::NUM ? k.n : (k.b ? 1.0 : 0.0);
        if (d == 0.0) d = 0.0;
        std::memcpy(&code, &d, 8);
        return 2;
    }
    if (k.t == V::NONE) { code = 0x9e37; return 4; }
    if (k.t == V::TUPLE) {   // tuple keys ((x, y), (card, side) ...): combined element codes
        uint64_t h = 0x84222325cbf29ce4ull ^ k.box->items.size();
        for (auto& x : k.box->items) {
            uint64_t c;
            int kt = key_code(x, c);
            if (!kt) return 0;
            h = (h ^ ((c + uint64_t(kt) * 0x632BE59BD9B4E019ull) * 0x9E3779B97F4A7C15ull)) * 0x100000001b3ull;
            h ^= h >> 31;
        }
        code = h;
        return 3;
    }
    // PvP73: pygame Font / Surface hash by identity (as in pygame); render caches key on them.
    if (k.t == V::INST) {
        const char* n = k.box->inst->type_name();
        if (std::strcmp(n, "Font") == 0 || std::strcmp(n, "Surface") == 0) { code = uint64_t(reinterpret_cast<uintptr_t>(k.box.get())); return 5; }
    }
    return 0;
}
static inline bool fast_key_eq(const V& a, const V& k) {
    if (k.t == V::STR) return a.t == V::STR && str_eq(a, k);
    if (k.t == V::NUM) return a.t == V::NUM ? a.n == k.n : (a.t == V::BOOL && (a.b ? 1.0 : 0.0) == k.n);
    return py_eq(a, k);
}
static inline size_t key_hash(int kt, uint64_t c) {
    uint64_t h = (c + uint64_t(kt) * 0x632BE59BD9B4E019ull) * 0x9E3779B97F4A7C15ull;
    return size_t(h ^ (h >> 29));
}
static void index_insert(Box* b, uint32_t i) {
    uint64_t c;
    int kt = key_code(b->kv[i].first, c);
    if (!kt) return;                                   // tuples etc. are found by the linear path
    size_t mask = b->kidx.size() - 1, h = key_hash(kt, c) & mask;
    while (b->kidx[h]) h = (h + 1) & mask;
    b->kidx[h] = i + 1;
}
static void build_index(Box* b) {
    size_t cap = 32;
    while (cap < b->kv.size() * 2) cap <<= 1;
    b->kidx.assign(cap, 0u);
    for (uint32_t i = 0; i < b->kv.size(); ++i) index_insert(b, i);
    b->kidx_valid = true;
}
static long dict_find(Box* b, const V& key) {
    auto& d = b->kv;
    uint64_t c;
    int kt;
    if (d.size() >= 12 && (kt = key_code(key, c)) != 0) {
        if (!b->kidx_valid) build_index(b);
        size_t mask = b->kidx.size() - 1, h = key_hash(kt, c) & mask;
        while (uint32_t s = b->kidx[h]) {
            if (fast_key_eq(d[s - 1].first, key)) return long(s - 1);
            h = (h + 1) & mask;
        }
        return -1;   // an indexed key (str / number / None / tuple of those) cannot equal a non-indexed one
    }
    for (size_t i = 0; i < d.size(); ++i) if (fast_key_eq(d[i].first, key)) return long(i);
    return -1;
}
const std::vector<std::pair<V, V>>& V::kv() const {
    if (!is_dict()) throw PyError("TypeError", "not a dict (" + type_name() + ")");
    return box->kv;
}
V& V::at(const V& key) {
    if (t == OBJ) return box->obj->slot(key);
    if (!is_dict()) throw PyError("TypeError", "not a dict (" + type_name() + ")");
    Box* b = box.get();
    long i = dict_find(b, key);
    if (i >= 0) return b->kv[size_t(i)].second;
    b->kv.emplace_back(key, V());
    if (b->kidx_valid) {
        if (b->kv.size() * 2 > b->kidx.size()) build_index(b);
        else index_insert(b, uint32_t(b->kv.size() - 1));
    }
    return b->kv.back().second;
}
const V* V::find_slow(const V& key) const {
    if (t == OBJ) return box->obj->find(key);
    if (t != DICT) return nullptr;
    long i = dict_find(box.get(), key);
    return i >= 0 ? &box->kv[size_t(i)].second : nullptr;
}
bool V::contains_slow(const V& key) const {
    switch (t) {
        case DICT: case OBJ: { const V* p = find(key); return p && p->has(); }
        case LIST: case TUPLE: case SET:
            if (t == SET && box->items.size() >= kSetIndexMin && hashable_key(key)) {
                int r = set_index_find(box.get(), key);
                if (r >= 0) return r == 1;
            }
            for (auto& it : box->items) if (py_eq(it, key)) return true;
            return false;
        case STR: return str().find(key.str()) != std::string::npos;
        case INST: return box->inst->contains(key);
        default: throw PyError("TypeError", "argument of type '" + type_name() + "' is not iterable");
    }
}
V V::get(const V& key, V dflt) const {
    const V* p = find(key);
    return (p && p->has()) ? *p : dflt;
}
void V::erase(const V& key) {
    if (t == OBJ) { box->obj->del(key); return; }
    auto& d = kv();
    for (size_t i = 0; i < d.size(); ++i)
        if (py_eq(d[i].first, key)) { d.erase(d.begin() + i); return; }
    throw PyError("KeyError", py_str(key));
}

// V::call is defined in pyobj.cpp (instances with __call__)

bool py_eq(const V& a, const V& b) {
    if (a.is_num() && b.is_num()) return a.num() == b.num();
    if (a.t != b.t) {
        V result;
        if (a.t == V::INST && a.box->inst->call_method(Sym("__eq__"), Args{b}, result)) return result.truthy();
        if (b.t == V::INST && b.box->inst->call_method(Sym("__eq__"), Args{a}, result)) return result.truthy();
        return a.is_none() && b.is_none();
    }
    switch (a.t) {
        case V::ABSENT: case V::NONE: return true;
        case V::STR: return str_eq(a, b);
        case V::LIST: case V::TUPLE: {
            if (a.box == b.box) return true;
            auto& x = a.box->items; auto& y = b.box->items;
            if (x.size() != y.size()) return false;
            for (size_t i = 0; i < x.size(); ++i) if (!py_eq(x[i], y[i])) return false;
            return true;
        }
        case V::DICT: {
            if (a.box == b.box) return true;
            auto& x = a.box->kv;
            if (x.size() != b.box->kv.size()) return false;
            if(is_ordered_dict(a) && is_ordered_dict(b)) {
                for(size_t i=0;i<x.size();++i)if(!py_eq(x[i].first,b.box->kv[i].first) || !py_eq(x[i].second,b.box->kv[i].second))return false;
                return true;
            }
            for (auto& p : x) { const V* q = b.find(p.first); if (!q || !py_eq(p.second, *q)) return false; }
            return true;
        }
        case V::OBJ: case V::FUNC: return a.box == b.box;
        case V::INST: {
            if (a.box == b.box || a.box->inst.get() == b.box->inst.get()) return true;
            V result;
            if (a.box->inst->call_method(Sym("__eq__"), Args{b}, result)) return result.truthy();
            if (b.box->inst->call_method(Sym("__eq__"), Args{a}, result)) return result.truthy();
            return false;
        }
        case V::SET: {
            if (a.box->items.size() != b.box->items.size()) return false;
            for (auto& x : a.box->items) if (!b.contains(x)) return false;
            return true;
        }
        default: return false;
    }
}

size_t py_hash(const V& v) {
    switch (v.t) {
        case V::NUM: case V::BOOL: return std::hash<double>()(v.num());
        case V::STR: return v.s == V::kLong ? std::hash<std::string_view>()(v.box->text) : symbol_text_hash(v.s);
        case V::TUPLE: { size_t h = 7; for (auto& x : v.box->items) h = h * 31 + py_hash(x); return h; }
        default: return 0;
    }
}

// copy.deepcopy with its memo: objects reached twice stay shared in the copy
// (the flood state keeps 洪水[0] is 人洪水; a copy must keep that alias).
static V deepcopy_m(const V& v, std::unordered_map<const Box*, V>& memo) {
    if (!v.box || v.t == V::FUNC || v.t == V::INST || v.t == V::STR) return v;
    auto hit = memo.find(v.box.get());
    if (hit != memo.end()) return hit->second;
    V out = v;
    out.box = make_box();
    memo.emplace(v.box.get(), out);
    out.box->periodic = v.box->periodic;
    out.box->color = v.box->color;   // copy.deepcopy(pygame.Color) is still a Color
    out.box->missing = v.box->missing; if (v.box->missing == 2) out.box->fattrs = v.box->fattrs;
    if(is_ordered_dict(v))out.box->fattrs.emplace_back(Sym("__native_ordered_dict__"),V(true));
    out.box->items.reserve(v.box->items.size());
    for (auto& it : v.box->items) out.box->items.push_back(deepcopy_m(it, memo));
    for (auto& p : v.box->kv) out.box->kv.emplace_back(deepcopy_m(p.first, memo), deepcopy_m(p.second, memo));
    if (v.box->obj) {
        out.box->obj = std::make_unique<Obj>();
        Obj* d = out.box->obj.get();
        const Obj* s = v.box->obj.get();
        for (auto& k : obj_keys()) d->*(k.member) = deepcopy_m(s->*(k.member), memo);
        for (auto& p : s->extras) d->extras.emplace_back(deepcopy_m(p.first, memo), deepcopy_m(p.second, memo));
    }
    return out;
}
V deepcopy(const V& v) {
    if (!v.box || v.t == V::FUNC || v.t == V::INST || v.t == V::STR) return v;
    std::unordered_map<const Box*, V> memo;
    return deepcopy_m(v, memo);
}

// Python container display is distinct from the compact JSON wire encoder below.
// A recursion guard renders existing cycles without recursing through the stack.
std::string python_repr_text(const V& v) {
    if(v.t==V::STR) {
        const std::string& text=v.str();char quote=text.find(char(39))!=std::string::npos && text.find(char(34))==std::string::npos?char(34):char(39);
        std::string out=v.byt?"b":"";out+=quote;
        for(unsigned char c:text){
            if(c==92 || c==unsigned(quote)){out+=char(92);out+=char(c);}
            else if(c==10 || c==13 || c==9){out+=char(92);out+=(c==10?'n':c==13?'r':'t');}
            else if(c<32 || c==127 || (v.byt && c>=128)){static const char hex[]="0123456789abcdef";out+=char(92);out+='x';out+=hex[c>>4];out+=hex[c&15];}
            else out+=char(c);
        }
        out+=quote;return out;
    }
    bool sequence=v.t==V::LIST || v.t==V::TUPLE || v.t==V::SET;
    bool mapping=v.t==V::DICT || v.t==V::OBJ;
    if(!sequence && !mapping)return v.t==V::FUNC?std::string("<function>"):py_str(v);
    static thread_local std::vector<const Box*> active;
    if(std::find(active.begin(),active.end(),v.box.get())!=active.end())return v.t==V::LIST?"[...]":v.t==V::TUPLE?"(...)":"{...}";
    active.push_back(v.box.get());struct Pop {std::vector<const Box*>& stack;~Pop(){stack.pop_back();}} pop{active};
    if(v.t==V::SET && v.items().empty())return "set()";
    std::string out=sequence?(v.t==V::TUPLE?"(":v.t==V::SET?"{":"["):"{";
    size_t count=0;
    if(sequence){for(const V& item:v.items()){if(count++)out+=", ";out+=python_repr_text(item);}if(v.t==V::TUPLE && count==1)out+=",";}
    else {
        auto entry=[&](const V& key,const V& item){if(!item.has())return;if(count++)out+=", ";out+=python_repr_text(key)+": "+python_repr_text(item);};
        if(v.t==V::DICT)for(const auto& pair:v.kv())entry(pair.first,pair.second);else v.o()->each(entry);
    }
    out+=sequence?(v.t==V::TUPLE?")":v.t==V::SET?"}":"]"):"}";return out;
}
std::string py_str(const V& v) {
    switch (v.t) {
        case V::ABSENT: case V::NONE: return "None";
        case V::BOOL: return v.b ? "True" : "False";
        case V::NUM: return native_number_text(v.n);
        case V::STR: return v.str();
        case V::INST: {
            { V out; if (v.box->inst->call_method(Sym("__str__"), Args{}, out)) return py_str(out); }
            V m = v.box->inst->method(Sym("__str__"));
            if (m.has()) return py_str(m.call(Args{}));
            return std::string("<") + v.box->inst->type_name() + " object>";
        }
        default: return python_repr_text(v);
    }
}

static void dump_to(const V& v, std::string& o) {
    char buf[64];
    switch (v.t) {
        case V::ABSENT: o += "<absent>"; break;
        case V::NONE: o += "null"; break;
        case V::BOOL: o += v.b ? "true" : "false"; break;
        case V::NUM:
            if (std::isnan(v.n)) { o += "\"nan\""; break; }
            if (std::isinf(v.n)) { o += v.n > 0 ? "\"inf\"" : "\"-inf\""; break; }
            snprintf(buf, sizeof buf, "%.17g", v.n);
            o += buf; break;
        case V::STR: {
            o += '"';
            for (char c : v.str()) { if (c == '"' || c == '\\') o += '\\'; o += c; }
            o += '"'; break;
        }
        case V::LIST: case V::TUPLE:
            o += '[';
            for (size_t i = 0; i < v.box->items.size(); ++i) { if (i) o += ','; dump_to(v.box->items[i], o); }
            o += ']'; break;
        case V::DICT:
            o += '{';
            for (size_t i = 0; i < v.box->kv.size(); ++i) {
                if (i) o += ',';
                o += '"'; o += py_str(v.box->kv[i].first); o += "\":";
                dump_to(v.box->kv[i].second, o);
            }
            o += '}'; break;
        case V::OBJ: o += v.box->obj->dump(); break;
        case V::FUNC: o += "\"<function>\""; break;
        case V::INST: o += "\"<instance>\""; break;
        case V::SET:
            o += '[';
            for (size_t i = 0; i < v.box->items.size(); ++i) { if (i) o += ','; dump_to(v.box->items[i], o); }
            o += ']'; break;
    }
}

std::string dump(const V& v) { std::string o; dump_to(v, o); return o; }

}  // namespace pvz
