// CPython 3.8 numeric semantics on doubles (exact for integral values < 2^53).
#pragma once
#include <cmath>
#include <cstdint>
#include <algorithm>
#include <limits>
#include <string>

namespace pvz::py {

// CPython 3.8 math.hypot uses scaled, compensated accumulation. Its last
// bit can decide which equal-radius target wins a distance/ID ordering.
// Reference algorithm: https://github.com/python/cpython/blob/v3.8.10/Modules/mathmodule.c#L2238-L2263
inline double hypot(double x, double y) {
    x = std::abs(x);
    y = std::abs(y);
    if (std::isinf(x) || std::isinf(y)) return std::numeric_limits<double>::infinity();
    if (std::isnan(x) || std::isnan(y)) return std::numeric_limits<double>::quiet_NaN();
    const double scale = std::max(x, y);
    if (scale == 0.) return 0.;
    double sum = 1.;
    double correction = 0.;
    for (const double coordinate : {x, y}) {
        const double ratio = coordinate / scale;
        const double square = ratio * ratio;
        const double previous = sum;
        sum += square;
        correction += (previous - sum) + square;
    }
    return scale * std::sqrt(sum - 1. + correction);
}

// float.__floordiv__ / int.__floordiv__ (CPython float_divmod algorithm)
inline double floordiv(double vx, double wx) {
    double mod = std::fmod(vx, wx);
    double div = (vx - mod) / wx;
    if (mod != 0.0) {
        if ((wx < 0) != (mod < 0)) { mod += wx; div -= 1.0; }
    }
    double floordiv;
    if (div != 0.0) {
        floordiv = std::floor(div);
        if (div - floordiv > 0.5) floordiv += 1.0;
    } else {
        floordiv = std::copysign(0.0, vx / wx);
    }
    return floordiv;
}

// float.__mod__
inline double mod(double vx, double wx) {
    double m = std::fmod(vx, wx);
    if (m != 0.0) {
        if ((wx < 0) != (m < 0)) m += wx;
    } else {
        m = std::copysign(0.0, wx);
    }
    return m;
}

// int(x) for a float: truncation toward zero
inline double trunc(double x) { return std::trunc(x); }
inline int64_t to_int(double x) { return int64_t(std::trunc(x)); }

// abs()
inline double jdz(double x) { return std::fabs(x); }

// round(x) with banker's rounding (Python 3 round to int)
inline double round0(double x) {
    double r = std::round(x);
    if (std::fabs(x - std::trunc(x)) == 0.5) r = 2.0 * std::round(x / 2.0);
    return r;
}

// round(x, n): CPython uses correctly rounded dtoa; approximate via string is
// slow. Used only for display; game logic avoids it.
inline double roundn(double x, int n) {
    double p = std::pow(10.0, n);
    return round0(x * p) / p;
}

// x ** y for doubles (float_pow semantics for finite non-negative bases)
inline double pow(double x, double y) { return std::pow(x, y); }

// str() of a value that Python holds as int
inline std::string str_int(double x) { return std::to_string(int64_t(x)); }

inline double max(double a, double b) { return b > a ? b : a; }   // Python max keeps first on ties
inline double min(double a, double b) { return b < a ? b : a; }

}  // namespace pvz::py
