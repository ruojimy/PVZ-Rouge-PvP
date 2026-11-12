// V: a Python-like dynamic value for the ported game state.
//   ABSENT (missing key) | NONE | BOOL | NUM (double; exact for ints < 2^53)
//   | STR (Sym) | LIST / TUPLE | DICT (ordered, any hashable V key) | OBJ (unit dict
//   with typed member slots, see sim/obj.h) | FUNC (callable).
// LIST/TUPLE/DICT/OBJ have reference semantics like Python; deepcopy() copies.
#pragma once
#include "core/sym.h"
#include <cmath>
#include <functional>
#include <memory>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>
#include <unordered_map>

namespace pvz {

struct V;
struct Box;
struct Obj;
struct PyObj;
struct Args;
// Non-atomic intrusive reference count (the simulation is single-threaded).
struct BoxBase { int rc = 0; };
// PvP73 pure-typed gate: V work done on the calling thread so far (see value.cpp).
struct VActivity { uint64_t boxes = 0, calls = 0; };
VActivity v_activity();
extern thread_local uint64_t g_v_activity_calls;
void box_release(BoxBase* b);   // deletes the Box (value.cpp)
class BoxP {
    BoxBase* p = nullptr;
public:
    BoxP() = default;
    explicit BoxP(BoxBase* b) : p(b) { if (p) ++p->rc; }
    BoxP(const BoxP& o) : p(o.p) { if (p) ++p->rc; }
    BoxP(BoxP&& o) noexcept : p(o.p) { o.p = nullptr; }
    ~BoxP() { if (p && --p->rc == 0) box_release(p); }
    BoxP& operator=(const BoxP& o) {
        if (o.p) ++o.p->rc;
        BoxBase* old = p; p = o.p;
        if (old && --old->rc == 0) box_release(old);
        return *this;
    }
    BoxP& operator=(BoxP&& o) noexcept {
        if (this != &o) { BoxBase* old = p; p = o.p; o.p = nullptr; if (old && --old->rc == 0) box_release(old); }
        return *this;
    }
    void reset() { if (p && --p->rc == 0) box_release(p); p = nullptr; }
    inline Box* get() const;
    inline Box* operator->() const;
    inline Box& operator*() const;
    explicit operator bool() const { return p != nullptr; }
    bool operator==(const BoxP& o) const { return p == o.p; }
    bool operator!=(const BoxP& o) const { return p != o.p; }
};
using Fn = std::function<V(const Args&)>;

void trace_pyerror(const std::string& what);
extern thread_local int g_call_depth;   // depth of V::call nesting (frame emulation)
struct PyError : std::runtime_error {
    std::string kind;                 // exception class name (python type)
    std::vector<std::string> bases;   // ancestor class names for `except Base`
    PyError(std::string k, const std::string& msg) : std::runtime_error(k + ": " + msg), kind(std::move(k)) { trace_pyerror(what()); }
    PyError(std::string k, const std::string& msg, std::vector<std::string> b)
        : std::runtime_error(k + ": " + msg), kind(std::move(k)), bases(std::move(b)) { trace_pyerror(what()); }
    bool matches(const char* type) const;   // except <type>
};

struct V {
    enum T : uint8_t { ABSENT = 0, NONE, BOOL, NUM, STR, LIST, TUPLE, DICT, OBJ, FUNC, INST, SET };
    T t = ABSENT;
    uint8_t byt = 0;   // STR holding python bytes: len / slicing / iteration count bytes, not code points
    union { double n; uint32_t s; bool b; };
    BoxP box;

    V() : n(0) {}
    V(double x) : t(NUM), n(x) {}
    V(int x) : t(NUM), n(double(x)) {}
    V(long x) : t(NUM), n(double(x)) {}
    V(long long x) : t(NUM), n(double(x)) {}
    V(unsigned x) : t(NUM), n(double(x)) {}
    V(unsigned long long x) : t(NUM), n(double(x)) {}
    V(unsigned long x) : t(NUM), n(double(x)) {}
    V(bool x) : t(BOOL), n(0) { b = x; }
    V(Sym x) : t(STR), n(0) { s = x.id; }
    // strings: up to kShortStr bytes are interned symbols (s = id); longer text (snapshots, file data,
    // bytes) lives uninterned in box->text with s = kLong, so it is freed with its last reference.
    static constexpr uint32_t kLong = 0xFFFFFFFFu;
    static constexpr size_t kShortStr = 256;
    V(const char* x);
    V(const std::string& x);
    V(std::string&& x);
    static V none() { V v; v.t = NONE; return v; }
    static V bytes(std::string raw) { V v(std::move(raw)); v.byt = 1; return v; }
    static V list(std::vector<V> items = {});
    static V tuple(std::vector<V> items);
    static V dict();
    static V obj();                         // new empty unit Obj
    static V func(Fn f);
    static V inst(std::shared_ptr<PyObj> p);
    static V set(std::vector<V> items = {});
    static V nums(std::initializer_list<double> xs);

    bool has() const { return t != ABSENT; }
    bool is_none() const { return t == NONE || t == ABSENT; }
    bool is_num() const { return t == NUM || t == BOOL; }
    bool is_str() const { return t == STR; }
    bool is_list() const { return t == LIST || t == TUPLE || t == SET; }
    bool is_dict() const { return t == DICT; }
    bool is_obj() const { return t == OBJ; }
    bool is_inst() const { return t == INST; }
    bool is_set() const { return t == SET; }
    PyObj* inst_ptr() const;
    void del() { t = ABSENT; box.reset(); n = 0; }

    double num() const {
        if (t == NUM) return n;
        if (t == BOOL) return b ? 1.0 : 0.0;
        throw PyError("TypeError", "not a number (" + type_name() + ")");
    }
    explicit operator double() const { return num(); }
    Sym sym() const;                                   // interns long text on demand
    inline const std::string& str() const;
    bool is_long_str() const { return t == STR && s == kLong; }
    bool truthy() const;
    explicit operator bool() const { return truthy(); }
    std::string type_name() const;
    Obj* o() const;                         // OBJ payload (throws otherwise)

    // sequences
    std::vector<V>& items();
    const std::vector<V>& items() const;
    size_t len() const;
    inline V& idx(int64_t i);
    V& idx_slow(int64_t i);
    inline const V& idx(int64_t i) const;
    const V& idx_slow(int64_t i) const;
    void append(V x) const;

    // dicts (DICT or OBJ): python d[k], k in d, d.get(k, x), del d[k]
    V& at(const V& key);
    inline const V* find(const V& key) const;
    const V* find_slow(const V& key) const;
    inline bool contains(const V& key) const;      // python `key in self` for dict/obj/list/str
    bool contains_slow(const V& key) const;
    void set_insert_new(const V& x) const;
    bool set_erase(const V& key) const;      // SET: remove (keeps the hash index); false if absent   // SET: append a value known to be absent (keeps the hash index)
    V get(const V& key, V dflt = V::none()) const;
    void erase(const V& key);
    std::vector<std::pair<V, V>>& kv();
    const std::vector<std::pair<V, V>>& kv() const;

    V call(const Args& a) const;

    V& operator=(double x) { t = NUM; n = x; box.reset(); return *this; }
    V& operator=(int x) { return *this = double(x); }
    V& operator=(long long x) { return *this = double(x); }
    V& operator=(bool x) { t = BOOL; b = x; box.reset(); return *this; }
    V& operator=(Sym x) { t = STR; s = x.id; box.reset(); return *this; }
    V& operator=(const char* x) { return *this = Sym(x); }
};

struct Box : BoxBase {
    std::vector<V> items;                         // LIST / TUPLE
    uint8_t missing = 0;                          // DICT: 1 = Counter (missing -> 0), 2 = defaultdict (fattrs[0] = factory)
    bool periodic = false;                        // PvP PeriodicRow: out-of-range index wraps (key % n)
    bool color = false;                           // TUPLE built by pygame.Color: also exposes .r .g .b .a
    std::vector<std::pair<V, V>> kv;              // DICT (insertion order)
    std::vector<uint32_t> kidx;                   // lazily built open-addressing index for large dicts (str / num keys), slot = i + 1
    bool kidx_valid = false;
    std::unique_ptr<Obj> obj;                     // OBJ
    Fn fn;                                        // FUNC
    std::shared_ptr<PyObj> inst;                  // INST
    std::vector<std::pair<Sym, V>> fattrs;        // FUNC attributes (__globals__, __name__, custom)
    std::string text;                             // STR with s == V::kLong: uninterned long text / bytes
    ~Box();
};
inline Box* BoxP::get() const { return static_cast<Box*>(p); }
inline Box* BoxP::operator->() const { return static_cast<Box*>(p); }
inline Box& BoxP::operator*() const { return *static_cast<Box*>(p); }
inline const std::string& V::str() const {
    if (t == STR && s == kLong) return box->text;
    return sym().str();
}
// string equality: short strings are canonical symbols; long ones compare their text
inline bool str_eq(const V& a, const V& b) { if(a.s!=V::kLong && b.s!=V::kLong)return a.s==b.s; return a.str()==b.str(); }
// ---- inline fast paths (common cases); everything else goes to the *_slow implementations in value.cpp
inline V& V::idx(int64_t i) {
    if ((t == LIST || t == TUPLE) && i >= 0 && size_t(i) < box->items.size()) return box->items[size_t(i)];
    return idx_slow(i);
}
inline const V& V::idx(int64_t i) const {
    if ((t == LIST || t == TUPLE) && i >= 0 && size_t(i) < box->items.size()) return box->items[size_t(i)];
    return idx_slow(i);
}
inline const V* V::find(const V& key) const {
    if (t == DICT && key.t == STR) {   // small dicts (map cells, records): symbol compare, no index
        const auto& kv = box->kv;
        if (kv.size() < 12) {
            for (const auto& p : kv) if (p.first.t == STR && str_eq(p.first, key)) return &p.second;
            return nullptr;   // a string key equals only string keys
        }
    }
    return find_slow(key);
}
inline bool V::contains(const V& key) const {
    if ((t == LIST || t == TUPLE || (t == SET && box->items.size() < 24)) && key.t == STR) {
        for (const auto& it : box->items) if (it.t == STR && str_eq(it, key)) return true;
        for (const auto& it : box->items) if (it.t == INST) return contains_slow(key);   // custom __eq__
        return false;
    }
    if (t == DICT && key.t == STR) { const V* p = find(key); return p && p->has(); }
    return contains_slow(key);
}
BoxP make_box();

bool py_eq(const V& a, const V& b);
size_t py_hash(const V& v);
inline bool operator==(const V& a, const V& b) {
    if (a.t == b.t) { if (a.t == V::NUM) return a.n == b.n; if (a.t == V::STR) return str_eq(a, b); }
    return py_eq(a, b);
}
inline bool operator!=(const V& a, const V& b) { return !py_eq(a, b); }

V deepcopy(const V& v);
std::string dump(const V& v);      // JSON-ish
std::string py_str(const V& v);    // python str()

}  // namespace pvz

namespace pvz {
// Call arguments: positional + keyword (python calling convention).
// Small-buffer vector of V for positional arguments (most calls pass <= 4).
class ArgVec {
    static constexpr size_t N = 4;
    size_t n_ = 0, cap_ = N;
    V* p_;
    alignas(V) unsigned char buf_[N * sizeof(V)];
    V* inl() { return reinterpret_cast<V*>(buf_); }
    void grow(size_t want) {
        size_t nc = cap_ * 2; if (nc < want) nc = want;
        V* np = static_cast<V*>(::operator new(nc * sizeof(V)));
        for (size_t i = 0; i < n_; ++i) { new (np + i) V(std::move(p_[i])); p_[i].~V(); }
        if (p_ != inl()) ::operator delete(p_);
        p_ = np; cap_ = nc;
    }
public:
    using value_type = V;
    using iterator = V*;
    using const_iterator = const V*;
    ArgVec() : p_(inl()) {}
    ArgVec(std::initializer_list<V> il) : p_(inl()) { reserve(il.size()); for (auto& v : il) new (p_ + n_++) V(v); }
    ArgVec(const std::vector<V>& v) : p_(inl()) { reserve(v.size()); for (auto& x : v) new (p_ + n_++) V(x); }
    ArgVec(std::vector<V>&& v) : p_(inl()) { reserve(v.size()); for (auto& x : v) new (p_ + n_++) V(std::move(x)); }
    template <class It> ArgVec(It a, It b) : p_(inl()) { for (; a != b; ++a) push_back(*a); }
    ArgVec(const ArgVec& o) : p_(inl()) { reserve(o.n_); for (size_t i = 0; i < o.n_; ++i) new (p_ + n_++) V(o.p_[i]); }
    ArgVec(ArgVec&& o) noexcept : p_(inl()) {
        if (o.p_ != o.inl()) { p_ = o.p_; n_ = o.n_; cap_ = o.cap_; o.p_ = o.inl(); o.n_ = 0; o.cap_ = N; }
        else { for (size_t i = 0; i < o.n_; ++i) { new (p_ + i) V(std::move(o.p_[i])); o.p_[i].~V(); } n_ = o.n_; o.n_ = 0; }
    }
    ArgVec& operator=(const ArgVec& o) { if (this != &o) { clear(); reserve(o.n_); for (size_t i = 0; i < o.n_; ++i) new (p_ + n_++) V(o.p_[i]); } return *this; }
    ArgVec& operator=(ArgVec&& o) noexcept { if (this != &o) { this->~ArgVec(); new (this) ArgVec(std::move(o)); } return *this; }
    ~ArgVec() { clear(); if (p_ != inl()) ::operator delete(p_); }
    void reserve(size_t c) { if (c > cap_) grow(c); }
    void clear() { for (size_t i = 0; i < n_; ++i) p_[i].~V(); n_ = 0; }
    size_t size() const { return n_; }
    bool empty() const { return n_ == 0; }
    V& operator[](size_t i) { return p_[i]; }
    const V& operator[](size_t i) const { return p_[i]; }
    V& at(size_t i) { if (i >= n_) throw std::out_of_range("ArgVec"); return p_[i]; }
    const V& at(size_t i) const { if (i >= n_) throw std::out_of_range("ArgVec"); return p_[i]; }
    V& back() { return p_[n_ - 1]; }
    V& front() { return p_[0]; }
    V* begin() { return p_; }
    V* end() { return p_ + n_; }
    const V* begin() const { return p_; }
    const V* end() const { return p_ + n_; }
    void push_back(const V& v) { if (n_ == cap_) { V t(v); grow(n_ + 1); new (p_ + n_++) V(std::move(t)); } else new (p_ + n_++) V(v); }
    void push_back(V&& v) { if (n_ == cap_) { V t(std::move(v)); grow(n_ + 1); new (p_ + n_++) V(std::move(t)); } else new (p_ + n_++) V(std::move(v)); }
    template <class... A> V& emplace_back(A&&... a) { push_back(V(std::forward<A>(a)...)); return back(); }
    void pop_back() { p_[--n_].~V(); }
    V* insert(V* at, const V& v) {
        size_t i = size_t(at - p_); push_back(v);
        for (size_t j = n_ - 1; j > i; --j) std::swap(p_[j], p_[j - 1]);
        return p_ + i;
    }
    template <class It> V* insert(V* at, It a, It b) {
        size_t i = size_t(at - p_), k = 0;
        std::vector<V> tmp(a, b);
        for (auto& x : tmp) { insert(p_ + i + k, x); ++k; }
        return p_ + i;
    }
    V* erase(V* at) { size_t i = size_t(at - p_); for (size_t j = i; j + 1 < n_; ++j) p_[j] = std::move(p_[j + 1]); pop_back(); return p_ + i; }
    template <class It> void assign(It a, It b) { std::vector<V> tmp(a, b); clear(); for (auto& x : tmp) push_back(std::move(x)); }
    operator std::vector<V>() const { return std::vector<V>(begin(), end()); }
};

struct Args {
    ArgVec pos;
    std::vector<std::pair<Sym, V>> kw;
    Args() = default;
    Args(std::initializer_list<V> p) : pos(p) {}
    Args(ArgVec p) : pos(std::move(p)) {}
    Args(ArgVec p, std::vector<std::pair<Sym, V>> k) : pos(std::move(p)), kw(std::move(k)) {}
    size_t size() const { return pos.size(); }
    // bind parameter i / name; dflt == nullptr means required
    V get(size_t i, Sym name, const V* dflt, const char* fn = "") const;
    bool has_kw(Sym name) const { for (auto& p : kw) if (p.first == name) return true; return false; }
    V rest(size_t from) const;                                    // *args tuple
    V kwrest(std::initializer_list<const char*> known) const;     // **kwargs dict
};
}  // namespace pvz
