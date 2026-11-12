// Python 3.8 operator semantics on V (used by translated code and the port).
#pragma once
#include "core/value.h"
#include "core/pymath.h"
#include "core/obj.h"
#include <algorithm>
#include <string>

namespace pvz {

// ---------------------------------------------------------------- arithmetic
// general implementations (pyops.cpp) behind inline NUM x NUM fast paths
V add_slow(const V& a, const V& b);
V sub_slow(const V& a, const V& b);
V mul_slow(const V& a, const V& b);
V div_slow(const V& a, const V& b);
V mod_slow(const V& a, const V& b);
V neg_slow(const V& a);
V floordiv_slow(const V& a, const V& b);
V& iadd_slow(V& a, const V& b);
bool py_lt_slow(const V& a, const V& b);
bool set_subset(const V& a, const V& b);
inline V operator+(const V& a, const V& b) { if (a.t == V::NUM && b.t == V::NUM) return V(a.n + b.n); return add_slow(a, b); }
inline V operator-(const V& a, const V& b) { if (a.t == V::NUM && b.t == V::NUM) return V(a.n - b.n); return sub_slow(a, b); }
inline V operator*(const V& a, const V& b) { if (a.t == V::NUM && b.t == V::NUM) return V(a.n * b.n); return mul_slow(a, b); }
inline V operator/(const V& a, const V& b) { if (a.t == V::NUM && b.t == V::NUM && b.n != 0.0) return V(a.n / b.n); return div_slow(a, b); }
inline V operator%(const V& a, const V& b) { if (a.t == V::NUM && b.t == V::NUM && b.n != 0.0) return V(py::mod(a.n, b.n)); return mod_slow(a, b); }
inline V operator-(const V& a) { if (a.t == V::NUM) return V(-a.n); return neg_slow(a); }
inline V floordiv(const V& a, const V& b) { if (a.t == V::NUM && b.t == V::NUM && b.n != 0.0) return V(py::floordiv(a.n, b.n)); return floordiv_slow(a, b); }
V pow(const V& a, const V& b);

inline V operator+(const V& a, double b) { if (a.t == V::NUM) return V(a.n + b); return a + V(b); }
inline V operator-(const V& a, double b) { if (a.t == V::NUM) return V(a.n - b); return a - V(b); }
inline V operator*(const V& a, double b) { if (a.t == V::NUM) return V(a.n * b); return a * V(b); }
inline V operator/(const V& a, double b) { return a / V(b); }
inline V operator+(double a, const V& b) { if (b.t == V::NUM) return V(a + b.n); return V(a) + b; }
inline V operator-(double a, const V& b) { if (b.t == V::NUM) return V(a - b.n); return V(a) - b; }
inline V operator*(double a, const V& b) { if (b.t == V::NUM) return V(a * b.n); return V(a) * b; }
inline V operator/(double a, const V& b) { return V(a) / b; }
inline V operator+(const V& a, int b) { return a + double(b); }
inline V operator-(const V& a, int b) { return a - double(b); }
inline V operator*(const V& a, int b) { return a * double(b); }
inline V operator/(const V& a, int b) { return a / double(b); }
inline V operator+(int a, const V& b) { return double(a) + b; }
inline V operator-(int a, const V& b) { return double(a) - b; }
inline V operator*(int a, const V& b) { return double(a) * b; }
inline V operator/(int a, const V& b) { return double(a) / b; }

inline V& operator+=(V& a, const V& b) { if (a.t == V::NUM && b.t == V::NUM) { a.n += b.n; return a; } return iadd_slow(a, b); }
inline V& operator-=(V& a, const V& b) { if (a.t == V::NUM && b.t == V::NUM) { a.n -= b.n; return a; } a = a - b; return a; }
inline V& operator*=(V& a, const V& b) { if (a.t == V::NUM && b.t == V::NUM) { a.n *= b.n; return a; } a = a * b; return a; }
inline V& operator/=(V& a, const V& b) { a = a / b; return a; }
inline V& operator%=(V& a, const V& b) { a = a % b; return a; }
inline V& operator+=(V& a, double b) { if (a.t == V::NUM) { a.n += b; return a; } return a += V(b); }
inline V& operator-=(V& a, double b) { if (a.t == V::NUM) { a.n -= b; return a; } return a -= V(b); }
inline V& operator*=(V& a, double b) { if (a.t == V::NUM) { a.n *= b; return a; } return a *= V(b); }
inline V& operator+=(V& a, int b) { return a += double(b); }
inline V& operator-=(V& a, int b) { return a -= double(b); }
inline V& operator*=(V& a, int b) { return a *= double(b); }
V ifloordiv(V& a, const V& b);

// ---------------------------------------------------------------- comparison
inline bool py_lt(const V& a, const V& b) { if (a.t == V::NUM && b.t == V::NUM) return a.n < b.n; return py_lt_slow(a, b); }
inline bool operator<(const V& a, const V& b) { return py_lt(a, b); }
inline bool operator>(const V& a, const V& b) { return py_lt(b, a); }
inline bool operator<=(const V& a, const V& b) { return a.t == V::SET && b.t == V::SET ? set_subset(a, b) : !py_lt(b, a); }
inline bool operator>=(const V& a, const V& b) { return a.t == V::SET && b.t == V::SET ? set_subset(b, a) : !py_lt(a, b); }
#define PVZ_CMP_NUM(T)                                                                            \
    inline bool operator<(const V& a, T b) { return a.t == V::NUM ? a.n < double(b) : py_lt(a, V(b)); }  \
    inline bool operator>(const V& a, T b) { return a.t == V::NUM ? a.n > double(b) : py_lt(V(b), a); }  \
    inline bool operator<=(const V& a, T b) { return a.t == V::NUM ? a.n <= double(b) : !py_lt(V(b), a); } \
    inline bool operator>=(const V& a, T b) { return a.t == V::NUM ? a.n >= double(b) : !py_lt(a, V(b)); } \
    inline bool operator==(const V& a, T b) { return a.is_num() && a.num() == double(b); }          \
    inline bool operator!=(const V& a, T b) { return !(a == b); }                                    \
    inline bool operator<(T a, const V& b) { return b > a; }                                         \
    inline bool operator>(T a, const V& b) { return b < a; }                                         \
    inline bool operator<=(T a, const V& b) { return b >= a; }                                       \
    inline bool operator>=(T a, const V& b) { return b <= a; }                                       \
    inline bool operator==(T a, const V& b) { return b == a; }                                       \
    inline bool operator!=(T a, const V& b) { return !(b == a); }
PVZ_CMP_NUM(double)
PVZ_CMP_NUM(int)
#undef PVZ_CMP_NUM
inline bool operator==(const V& a, const char* b) { return a.t == V::STR && (a.s == V::kLong ? a.box->text == b : a.s == Sym(b).id); }
inline bool operator!=(const V& a, const char* b) { return !(a == b); }
inline bool operator==(const V& a, Sym b) { return a.t == V::STR && (a.s == V::kLong ? a.str() == b.str() : a.s == b.id); }
inline bool operator!=(const V& a, Sym b) { return !(a == b); }

// ---------------------------------------------------------------- builtins
namespace py {
inline bool in(const V& x, const V& c) { return c.contains(x); }
inline V len(const V& x) { return V(double(x.len())); }
V int_(const V& x);
V float_(const V& x);
V str(const V& x);
V abs(const V& x);
V bool_(const V& x);
V round(const V& x);
V round(const V& x, const V& nd);
V max(const V& a, const V& b);
V min(const V& a, const V& b);
V max(const V& seq);
V min(const V& seq);
V sum(const V& seq);
V list(const V& iterable);
V tuple(const V& iterable);
V sorted(const V& iterable);
V reversed(const V& seq);
V slice(const V& seq, const V& start, const V& stop);   // seq[start:stop] (None = open)
void set_slice(const V& seq_, const V& start, const V& stop, const V& value);
V pop(const V& seq_);                         // list.pop()
V pop(const V& seq_, const V& i);             // list.pop(i) / dict.pop(k)
V pop(const V& d_, const V& k, const V& dflt);
void insert(const V& seq_, const V& i, const V& x);
void remove(const V& seq_, const V& x);
V index(const V& seq, const V& x);
V count(const V& seq, const V& x);
void extend(const V& seq_, const V& other);
V setdefault(const V& d_, const V& k, const V& dflt);
V keys(const V& d);
V values(const V& d);
V items(const V& d);
std::vector<std::pair<V, V>> items_vec(const V& d);   // `for k, v in d.items()` snapshot
V split(const V& s, const V& sep);
bool startswith(const V& s, const V& prefix);
bool endswith(const V& s, const V& suffix);
V join(const V& sep, const V& seq);
V replace(const V& s, const V& a, const V& b);
V copy(const V& x);                    // list.copy()/dict.copy()/ list(x)[:] shallow
inline V deepcopy(const V& x) { return pvz::deepcopy(x); }
// iteration: returns a snapshot list to iterate (python iterates live lists;
// the translator emits index loops for lists that may mutate)
V iter_list(const V& x);
V range(int64_t stop);
V range(int64_t start, int64_t stop, int64_t step = 1);
}  // namespace py

// unit-dict member access helper used by translated code: obj(v)->血量
inline Obj* obj(const V& v) { return v.o(); }

}  // namespace pvz
