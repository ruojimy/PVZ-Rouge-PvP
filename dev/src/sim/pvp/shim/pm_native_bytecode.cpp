#include "sim/pvp/shim/pm_native_bytecode.h"
#include "sim/pvp/hand/graphics.h"
#include <cmath>
#include <algorithm>
namespace pvz { namespace pm_native_bytecode {
V f_instruction_window(const Args& A) {
    V code = A.get(0, Sym("code"), nullptr), start = A.get(1, Sym("start"), nullptr), end = A.get(2, Sym("end"), nullptr);
    std::string bytes = py::bytes_data(pvz::getattr(code, Sym("co_code")));
    int64_t first = int64_t(start.num()), last = int64_t(end.num()), size = int64_t(bytes.size());
    if (first < 0) first = std::max(int64_t(0), first + size); else first = std::min(first, size);
    if (last < 0) last = std::max(int64_t(0), last + size); else last = std::min(last, size);
    V section = callm(code, Sym("replace"), Args({}, {{Sym("co_code"), V::bytes(bytes.substr(size_t(first), size_t(std::max(int64_t(0), last - first))))}, {Sym("co_lnotab"), V::bytes("")}}));
    V decoded = f_instructions(Args{section}), relative = py::stdlib_attr(V("dis"), V("hasjrel"));
    std::vector<V> result;
    for (auto& ins : decoded.items()) {
        V value = pvz::getattr(ins, Sym("argval"));
        if (relative.contains(pvz::getattr(ins, Sym("opcode")))) value += start;
        result.push_back(callm(ins, Sym("_replace"), Args({}, {{Sym("offset"), pvz::getattr(ins, Sym("offset")) + start}, {Sym("argval"), value}})));
    }
    return V::tuple(result);
}
V f_instructions(const Args& A) {
    V code = A.get(0, Sym("code"), nullptr);
    return py::tuple_it(py::stdlib_call(V("dis.get_instructions"), Args{code}));
}
V f_decode(const Args& A) { return py::stdlib_call(V("marshal.loads"), A); }
void init() { static bool done = false; if (done) return; done = true; }
}}  // namespace pvz::pm_native_bytecode
