#include "core/pyops.h"
#include "core/pyobj.h"
#include <cstdlib>
#include <cerrno>
namespace pvz::py { V percent(const V& fmt, const V& args); V native_slice(const V&,const V&,const V&); }

namespace pvz {
bool is_ordered_dict(const V&);

static PyError type_err(const char* op, const V& a, const V& b) {
    return PyError("TypeError", std::string("unsupported operand type(s) for ") + op + ": '" + a.type_name() +
                                    "' and '" + b.type_name() + "'");
}

V add_slow(const V& a, const V& b) {
    if (a.is_num() && b.is_num()) return V(a.num() + b.num());
    if (a.t == V::STR && b.t == V::STR) { V r(a.str() + b.str()); r.byt = a.byt | b.byt; return r; }
    if (a.is_list() && b.t == a.t) {
        std::vector<V> it = a.items();
        it.insert(it.end(), b.items().begin(), b.items().end());
        return a.t == V::TUPLE ? V::tuple(std::move(it)) : V::list(std::move(it));
    }
    throw type_err("+", a, b);
}
V sub_slow(const V& a, const V& b) {
    if (a.is_num() && b.is_num()) return V(a.num() - b.num());
    if (a.t == V::SET && b.is_list()) {   // set difference (order of the left operand)
        std::vector<V> r;
        for (auto& x : a.items()) if (!b.contains(x)) r.push_back(x);
        return V::set(r);
    }
    if (a.t == V::INST) return callm(a, Sym("__sub__"), Args{b});
    throw type_err("-", a, b);
}
V mul_slow(const V& a, const V& b) {
    if (a.is_num() && b.is_num()) return V(a.num() * b.num());
    auto rep = [](const V& seq, double times) {
        std::vector<V> out;
        for (int64_t k = 0; k < int64_t(times); ++k) out.insert(out.end(), seq.items().begin(), seq.items().end());
        return seq.t == V::TUPLE ? V::tuple(std::move(out)) : V::list(std::move(out));
    };
    if (a.is_list() && b.is_num()) return rep(a, b.num());
    if (b.is_list() && a.is_num()) return rep(b, a.num());
    if (a.t == V::STR && b.is_num()) { std::string s; for (int64_t k = 0; k < int64_t(b.num()); ++k) s += a.str(); V result(s); result.byt = a.byt; return result; }
    if (b.t == V::STR && a.is_num()) return mul_slow(b, a);
    throw type_err("*", a, b);
}
V callm(const V& o, Sym name, const Args& a);
V div_slow(const V& a, const V& b) {
    if (a.t == V::INST) return callm(a, Sym("__truediv__"), Args{b});
    if (a.is_num() && b.is_num()) {
        if (b.num() == 0.0) throw PyError("ZeroDivisionError", "division by zero");
        return V(a.num() / b.num());
    }
    throw type_err("/", a, b);
}
V mod_slow(const V& a, const V& b) {
    if (a.t == V::STR) return py::percent(a, b);
    if (a.is_num() && b.is_num()) {
        if (b.num() == 0.0) throw PyError("ZeroDivisionError", "modulo by zero");
        return V(py::mod(a.num(), b.num()));
    }
    throw type_err("%", a, b);
}
V neg_slow(const V& a) {
    if (a.is_num()) return V(-a.num());
    throw PyError("TypeError", "bad operand type for unary -: '" + a.type_name() + "'");
}
V floordiv_slow(const V& a, const V& b) {
    if (a.is_num() && b.is_num()) {
        if (b.num() == 0.0) throw PyError("ZeroDivisionError", "integer division or modulo by zero");
        return V(py::floordiv(a.num(), b.num()));
    }
    throw type_err("//", a, b);
}
V pow(const V& a, const V& b) {
    if (a.is_num() && b.is_num()) return V(std::pow(a.num(), b.num()));
    throw type_err("**", a, b);
}

V& iadd_slow(V& a, const V& b) {
    if (a.t == V::LIST && b.is_list()) {   // list += iterable extends in place (aliases see it)
        auto copy = b.items();
        a.items().insert(a.items().end(), copy.begin(), copy.end());
        return a;
    }
    a = a + b;
    return a;
}
V ifloordiv(V& a, const V& b) { a = floordiv(a, b); return a; }

bool set_subset(const V& a, const V& b) {
    if (a.len() > b.len()) return false;
    for (const auto& item : a.items()) if (!b.contains(item)) return false;
    return true;
}
bool py_lt_slow(const V& a, const V& b) {
    if (a.is_num() && b.is_num()) return a.num() < b.num();
    if (a.t == V::SET && b.t == V::SET) return a.len() < b.len() && set_subset(a, b);
    if (a.t == V::STR && b.t == V::STR) return a.str() < b.str();   // UTF-8 byte order == code point order
    V comparison;
    if (a.t == V::INST && a.box->inst->call_method(Sym("__lt__"), Args{b}, comparison)) return comparison.truthy();
    if (b.t == V::INST && b.box->inst->call_method(Sym("__gt__"), Args{a}, comparison)) return comparison.truthy();
    if (a.is_list() && b.is_list()) {
        auto& x = a.items(); auto& y = b.items();
        size_t n = std::min(x.size(), y.size());
        for (size_t i = 0; i < n; ++i)
            if (!py_eq(x[i], y[i])) return py_lt(x[i], y[i]);
        return x.size() < y.size();
    }
    throw PyError("TypeError", "'<' not supported between instances of '" + a.type_name() + "' and '" + b.type_name() + "'");
}

namespace py {

V int_(const V& x) {
    if (x.is_num()) {
        if(std::isnan(x.num()))throw PyError("ValueError","cannot convert NaN to integer");
        if(!std::isfinite(x.num()))throw PyError("OverflowError","cannot convert infinity to integer");
        return V(std::trunc(x.num()));
    }
    if (x.t == V::STR) {
        const std::string& source=x.str();
        size_t first=source.find_first_not_of(" \t\n\r\v\f"),last=source.find_last_not_of(" \t\n\r\v\f");
        auto invalid=[&]()->V {throw PyError("ValueError","invalid literal for int(): '"+source+"'");};
        if(first==std::string::npos)return invalid();
        std::string text=source.substr(first,last-first+1),digits;
        size_t start=(text[0]=='+' || text[0]=='-')?1:0;
        if(start==text.size())return invalid();
        for(size_t i=0;i<text.size();++i) {
            if(i<start){digits+=text[i];continue;}
            if(text[i]>='0' && text[i]<='9'){digits+=text[i];continue;}
            if(text[i]=='_' && i>start && i+1<text.size() && text[i-1]>='0' && text[i-1]<='9' && text[i+1]>='0' && text[i+1]<='9')continue;
            return invalid();
        }
        char* end = nullptr;
        errno=0;long long v = std::strtoll(digits.c_str(), &end, 10);
        if(errno==ERANGE)return V(std::strtod(digits.c_str(),nullptr)); // existing native numeric model
        if (!end || *end) return invalid();
        return V(double(v));
    }
    throw PyError("TypeError", "int() argument must be a string or a number, not '" + x.type_name() + "'");
}
V float_(const V& x) {
    if (x.is_num()) return V(x.num());
    if (x.t == V::STR) return V(std::strtod(x.str().c_str(), nullptr));
    throw PyError("TypeError", "float() argument must be a string or a number");
}
V str(const V& x) { return V(py_str(x)); }
V abs(const V& x) { return V(std::fabs(x.num())); }
V bool_(const V& x) { return V(x.truthy()); }
V round(const V& x) { return V(py::round0(x.num())); }
V round(const V& x, const V& nd) { return V(py::roundn(x.num(), int(nd.num()))); }
V max(const V& a, const V& b) { return py_lt(a, b) ? b : a; }
V min(const V& a, const V& b) { return py_lt(b, a) ? b : a; }
V max(const V& seq) {
    auto& it = seq.items();
    if (it.empty()) throw PyError("ValueError", "max() arg is an empty sequence");
    V best = it[0];
    for (size_t i = 1; i < it.size(); ++i) if (py_lt(best, it[i])) best = it[i];
    return best;
}
V min(const V& seq) {
    auto& it = seq.items();
    if (it.empty()) throw PyError("ValueError", "min() arg is an empty sequence");
    V best = it[0];
    for (size_t i = 1; i < it.size(); ++i) if (py_lt(it[i], best)) best = it[i];
    return best;
}
V sum(const V& seq) { V s(0.0); for (auto& x : seq.items()) s = s + x; return s; }
V list(const V& it) {
    if (it.is_list()) return V::list(it.items());
    if (it.is_dict()) { std::vector<V> k; for (auto& p : it.kv()) k.push_back(p.first); return V::list(std::move(k)); }
    if(it.t==V::INST || it.t==V::STR){V values=iter_list(it);return V::list(values.items());}
    throw PyError("TypeError", "list() of " + it.type_name());
}
V tuple(const V& it) { V l = list(it); l.t = V::TUPLE; return l; }
V sorted(const V& it) {
    V l = list(it);
    std::stable_sort(l.items().begin(), l.items().end(), [](const V& a, const V& b) { return py_lt(a, b); });
    return l;
}
V reversed(const V& seq) { if(seq.t==V::INST){V method=seq.box->inst->method(Sym("__reversed__"));if(method.has())return method.call(Args{});} V l = list(seq); std::reverse(l.items().begin(), l.items().end()); return l; }

static void norm(int64_t n, const V& start, const V& stop, int64_t& a, int64_t& b) {
    a = start.is_none() ? 0 : int64_t(start.num());
    b = stop.is_none() ? n : int64_t(stop.num());
    if (a < 0) a = std::max<int64_t>(0, a + n);
    if (b < 0) b = std::max<int64_t>(0, b + n);
    a = std::min(a, n);
    b = std::min(b, n);
    if (b < a) b = a;
}
V slice(const V& seq, const V& start, const V& stop) {
    if (seq.t == V::INST) { V out; if (seq.box->inst->call_method(Sym("__getslice__"), Args{start.has() ? start : V::none(), stop.has() ? stop : V::none()}, out)) return out; return seq.box->inst->getitem(native_slice(start,stop,V::none())); }
    if (seq.t == V::STR && seq.byt) {
        int64_t a, b;
        norm(int64_t(seq.str().size()), start, stop, a, b);
        return V::bytes(seq.str().substr(size_t(a), size_t(b - a)));
    }
    if (seq.t == V::STR) {
        // code-point slicing
        const std::string& s = seq.str();
        std::vector<size_t> cp;
        for (size_t i = 0; i < s.size(); ++i) if ((static_cast<unsigned char>(s[i]) & 0xC0) != 0x80) cp.push_back(i);
        int64_t a, b;
        norm(int64_t(cp.size()), start, stop, a, b);
        size_t bs = a < int64_t(cp.size()) ? cp[size_t(a)] : s.size();
        size_t be = b < int64_t(cp.size()) ? cp[size_t(b)] : s.size();
        return V(s.substr(bs, be - bs));
    }
    auto& it = seq.items();
    int64_t a, b;
    norm(int64_t(it.size()), start, stop, a, b);
    std::vector<V> out(it.begin() + a, it.begin() + b);
    return seq.t == V::TUPLE ? V::tuple(std::move(out)) : V::list(std::move(out));
}
void set_slice(const V& seq_, const V& start, const V& stop, const V& value) { V& seq = const_cast<V&>(seq_);
    if (seq.t == V::INST) { V out; if (seq.box->inst->call_method(Sym("__setslice__"), Args{start.has() ? start : V::none(), stop.has() ? stop : V::none(), value}, out)) return; }
    auto& it = seq.items();
    int64_t a, b;
    norm(int64_t(it.size()), start, stop, a, b);
    std::vector<V> repl = value.items();
    it.erase(it.begin() + a, it.begin() + b);
    it.insert(it.begin() + a, repl.begin(), repl.end());
}
V pop(const V& seq_) { V& seq = const_cast<V&>(seq_);
    if (seq.t == V::SET) {
        if (seq.box->items.empty()) throw PyError("KeyError", "pop from an empty set");
        V x = seq.box->items.back();
        seq.set_erase(x);
        return x;
    }
    auto& it = seq.items();
    if (it.empty()) throw PyError("IndexError", "pop from empty list");
    V x = it.back();
    it.pop_back();
    return x;
}
V pop(const V& seq_, const V& i) { V& seq = const_cast<V&>(seq_);
    if (seq.is_dict() || seq.is_obj()) {
        const V* p = seq.find(i);
        if (!p || !p->has()) throw PyError("KeyError", py_str(i));
        V x = *p;
        seq.erase(i);
        return x;
    }
    auto& it = seq.items();
    int64_t k = int64_t(i.num()), n = int64_t(it.size());
    if (k < 0) k += n;
    if (k < 0 || k >= n) throw PyError("IndexError", "pop index out of range");
    V x = it[size_t(k)];
    it.erase(it.begin() + k);
    return x;
}
V pop(const V& d_, const V& k, const V& dflt) { V& d = const_cast<V&>(d_);
    const V* p = d.find(k);
    if (!p || !p->has()) return dflt;
    V x = *p;
    d.erase(k);
    return x;
}
void insert(const V& seq_, const V& i, const V& x) { V& seq = const_cast<V&>(seq_);
    auto& it = seq.items();
    int64_t k = int64_t(i.num()), n = int64_t(it.size());
    if (k < 0) k = std::max<int64_t>(0, k + n);
    k = std::min(k, n);
    it.insert(it.begin() + k, x);
}
void remove(const V& seq_, const V& x) { V& seq = const_cast<V&>(seq_);
    if (seq.t == V::SET) { if (!seq.set_erase(x)) throw PyError("KeyError", py_str(x)); return; }
    auto& it = seq.items();
    for (size_t i = 0; i < it.size(); ++i) if (py_eq(it[i], x)) { it.erase(it.begin() + i); return; }
    throw PyError("ValueError", "list.remove(x): x not in list");
}
V index(const V& seq, const V& x) {
    auto& it = seq.items();
    for (size_t i = 0; i < it.size(); ++i) if (py_eq(it[i], x)) return V(double(i));
    throw PyError("ValueError", "x not in list");
}
V count(const V& seq, const V& x) { double n = 0; for (auto& e : seq.items()) if (py_eq(e, x)) ++n; return V(n); }
void extend(const V& seq_, const V& other) { V& seq = const_cast<V&>(seq_); auto copy = list(other); seq.items().insert(seq.items().end(), copy.items().begin(), copy.items().end()); }
V setdefault(const V& d_, const V& k, const V& dflt) { V& d = const_cast<V&>(d_);
    V& slot = d.at(k);
    if (!slot.has()) slot = dflt;
    return slot;
}
V keys(const V& d) {
    std::vector<V> out;
    if (d.is_obj()) d.o()->each([&](const V& k, const V&) { out.push_back(k); });
    else for (auto& p : d.kv()) out.push_back(p.first);
    return V::list(std::move(out));
}
V values(const V& d) {
    std::vector<V> out;
    if (d.is_obj()) d.o()->each([&](const V&, const V& v) { out.push_back(v); });
    else for (auto& p : d.kv()) out.push_back(p.second);
    return V::list(std::move(out));
}
std::vector<std::pair<V, V>> items_vec(const V& d) {
    std::vector<std::pair<V, V>> out;
    if (d.t == V::DICT) { out = d.box->kv; return out; }
    if (d.is_obj() && !d.o()->hook) { d.o()->each([&](const V& k, const V& v) { out.emplace_back(k, v); }); return out; }
    V it = d.t == V::INST || d.is_obj() ? py::iter_list(callm(d, Sym("items"), Args{})) : items(d);
    for (auto& p : it.items()) out.emplace_back(p.idx(0), p.idx(1));
    return out;
}
V items(const V& d) {
    std::vector<V> out;
    if (d.is_obj()) d.o()->each([&](const V& k, const V& v) { out.push_back(V::tuple({k, v})); });
    else for (auto& p : d.kv()) out.push_back(V::tuple({p.first, p.second}));
    return V::list(std::move(out));
}
V split(const V& s, const V& sep) {
    const std::string& str = s.str();
    const std::string& d = sep.str();
    std::vector<V> out;
    size_t a = 0;
    while (true) {
        size_t b = str.find(d, a);
        out.emplace_back(str.substr(a, b == std::string::npos ? std::string::npos : b - a));
        if (b == std::string::npos) break;
        a = b + d.size();
    }
    return V::list(std::move(out));
}
bool startswith(const V& s, const V& p) { return s.str().rfind(p.str(), 0) == 0; }
bool endswith(const V& s, const V& p) {
    const std::string& a = s.str(); const std::string& b = p.str();
    return a.size() >= b.size() && a.compare(a.size() - b.size(), b.size(), b) == 0;
}
V join(const V& sep, const V& seq) {
    std::string out;
    bool first = true;
    for (auto& x : seq.items()) { if (!first) out += sep.str(); first = false; out += x.str(); }
    return V(out);
}
V replace(const V& s, const V& a, const V& b) {
    std::string str = s.str();
    const std::string& f = a.str(); const std::string& t = b.str();
    if (f.empty()) return s;
    size_t pos = 0;
    while ((pos = str.find(f, pos)) != std::string::npos) { str.replace(pos, f.size(), t); pos += t.size(); }
    return V(str);
}
V copy(const V& x) {
    if (x.is_list()) { V l = V::list(x.items()); l.t = x.t; return l; }
    if (x.is_dict()) { V d = V::dict(); d.kv() = x.kv(); if(is_ordered_dict(x))d.box->fattrs.emplace_back(Sym("__native_ordered_dict__"),V(true)); return d; }
    if (x.is_obj()) { V d = V::obj(); *d.o() = *x.o(); return d; }
    return x;
}
V iter_list(const V& x) {
    if (x.is_list()) return x;
    if (x.t == V::INST) return x.box->inst->iterate();
    if (x.is_dict() || x.is_obj()) return keys(x);
    if (x.t == V::STR && x.byt) { std::vector<V> out; for (unsigned char c : x.str()) out.emplace_back(double(c)); return V::list(std::move(out)); }
    if (x.t == V::STR) {
        std::vector<V> out;
        const std::string& s = x.str();
        size_t i = 0;
        while (i < s.size()) {
            size_t j = i + 1;
            while (j < s.size() && (static_cast<unsigned char>(s[j]) & 0xC0) == 0x80) ++j;
            out.emplace_back(s.substr(i, j - i));
            i = j;
        }
        return V::list(std::move(out));
    }
    throw PyError("TypeError", "'" + x.type_name() + "' object is not iterable");
}
V range(int64_t stop) { return range(0, stop, 1); }
V range(int64_t start, int64_t stop, int64_t step) {
    std::vector<V> out;
    if (step > 0) for (int64_t i = start; i < stop; i += step) out.emplace_back(double(i));
    else for (int64_t i = start; i > stop; i += step) out.emplace_back(double(i));
    return V::list(std::move(out));
}

}  // namespace py
}  // namespace pvz
