// Prints reference sequences for comparison with tools/test_core_ref.py
#include "core/pyrandom.h"
#include "core/pymath.h"
#include "core/number_text.h"
#include "core/value.h"
#include <cstdio>

int main() {
    using namespace pvz;
    struct NumberTextCase {double value;const char* expected;};
    for(const auto& test: {
            NumberTextCase{0.,"0"},NumberTextCase{-0.,"0"},NumberTextCase{-123.,"-123"},
            NumberTextCase{4.125,"4.125"},NumberTextCase{.1,"0.10000000000000001"},
            NumberTextCase{9007199254740991.,"9007199254740991"},NumberTextCase{9007199254740992.,"9007199254740992"},
            NumberTextCase{1e20,"1e+20"}}){
        if(native_number_text(test.value)!=test.expected || py_str(V(test.value))!=test.expected){
            std::fprintf(stderr,"native number text mismatch for %.17g\n",test.value);
            return 1;
        }
    }
    for (long long s : {0LL, 1LL, 7LL, 12345678901LL, -5LL}) {
        PyRandom r(s);
        printf("seed %lld:", s);
        for (int i = 0; i < 3; ++i) printf(" %.17g", r.random());
        for (int i = 0; i < 5; ++i) printf(" %lld", (long long)r.randint(1, 100));
        for (int i = 0; i < 3; ++i) printf(" %lld", (long long)r.randint(-50, 50));
        printf(" %llu", (unsigned long long)r.getrandbits(40));
        printf(" %.17g", r.uniform(-3.5, 9.25));
        printf(" %lld\n", (long long)r.randint(0, 1000000007));
    }
    double vals[][2] = {{7, 2}, {-7, 2}, {7, -2}, {7.5, 2}, {-7.5, 0.5}, {1e10, 3}, {-0.0, 5}, {5.3, 0.1}, {-100.25, 48}};
    for (auto& v : vals) printf("fd %.17g mod %.17g\n", py::floordiv(v[0], v[1]), py::mod(v[0], v[1]));
    printf("round %g %g %g %g\n", py::round0(2.5), py::round0(3.5), py::round0(-2.5), py::round0(2.4999));
    return 0;
}
