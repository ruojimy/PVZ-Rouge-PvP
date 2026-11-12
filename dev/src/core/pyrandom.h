// Bit-exact reimplementation of CPython 3.8 `random.Random` (MT19937) for the
// operations the game uses: seed(int), random(), getrandbits(), randint(),
// randrange(), choice-index, uniform(), shuffle-index.
#pragma once
#include <cstdint>
#include <vector>
#include <stdexcept>

namespace pvz {

class PyRandom {
public:
    PyRandom() { seed(0); }
    explicit PyRandom(int64_t s) { seed(s); }

    // random.seed(n) for an int n (version 2): key = abs(n) as 32-bit words.
    void seed(int64_t n) {
        uint64_t a = n < 0 ? uint64_t(-(n + 1)) + 1 : uint64_t(n);
        std::vector<uint32_t> key;
        if (a == 0) key.push_back(0);
        while (a) { key.push_back(uint32_t(a & 0xffffffffu)); a >>= 32; }
        init_by_array(key.data(), key.size());
        gauss_next_valid = false;
    }

    // random.random(): 53-bit float in [0,1)
    double random() {
        uint32_t a = genrand() >> 5, b = genrand() >> 6;
        return (a * 67108864.0 + b) * (1.0 / 9007199254740992.0);
    }

    // random.getrandbits(k), k <= 64
    uint64_t getrandbits(int k) {
        if (k <= 0) return 0;
        if (k <= 32) return genrand() >> (32 - k);
        uint64_t result = 0;
        int shift = 0;
        while (k > 0) {
            uint32_t r = genrand();
            if (k < 32) r >>= (32 - k);
            result |= uint64_t(r) << shift;
            shift += 32;
            k -= 32;
        }
        return result;
    }

    // Random._randbelow_with_getrandbits(n)
    uint64_t randbelow(uint64_t n) {
        if (n == 0) return 0;
        int k = bit_length(n);
        uint64_t r = getrandbits(k);
        while (r >= n) r = getrandbits(k);
        return r;
    }

    // random.randrange(start, stop) with step 1
    int64_t randrange(int64_t start, int64_t stop) {
        int64_t width = stop - start;
        if (width <= 0) throw std::runtime_error("empty range for randrange()");
        return start + int64_t(randbelow(uint64_t(width)));
    }
    int64_t randrange(int64_t stop) { return randrange(0, stop); }

    // random.randint(a, b) inclusive
    int64_t randint(int64_t a, int64_t b) { return randrange(a, b + 1); }

    // random.choice(seq) -> index
    size_t choice_index(size_t len) {
        if (len == 0) throw std::runtime_error("Cannot choose from an empty sequence");
        return size_t(randbelow(len));
    }

    // random.uniform(a, b)
    double uniform(double a, double b) { return a + (b - a) * random(); }

    // random.shuffle(x): call swap(i, j) for each step, i descending
    template <class Swap>
    void shuffle(size_t n, Swap swap) {
        for (size_t i = n; i-- > 1;) {
            size_t j = size_t(randbelow(i + 1));
            swap(i, j);
        }
    }

    // State capture (for replays/snapshots).
    struct State { uint32_t mt[624]; int mti; };
    State state() const { State s; for (int i = 0; i < 624; ++i) s.mt[i] = mt[i]; s.mti = mti; return s; }
    void set_state(const State& s) { for (int i = 0; i < 624; ++i) mt[i] = s.mt[i]; mti = s.mti; }

    static int bit_length(uint64_t n) { int k = 0; while (n) { ++k; n >>= 1; } return k; }

private:
    uint32_t mt[624];
    int mti = 625;
    bool gauss_next_valid = false;

    void init_genrand(uint32_t s) {
        mt[0] = s;
        for (mti = 1; mti < 624; mti++)
            mt[mti] = (1812433253u * (mt[mti - 1] ^ (mt[mti - 1] >> 30)) + uint32_t(mti));
    }
    void init_by_array(const uint32_t* key, size_t key_length) {
        init_genrand(19650218u);
        size_t i = 1, j = 0;
        size_t k = 624 > key_length ? 624 : key_length;
        for (; k; k--) {
            mt[i] = (mt[i] ^ ((mt[i - 1] ^ (mt[i - 1] >> 30)) * 1664525u)) + key[j] + uint32_t(j);
            i++; j++;
            if (i >= 624) { mt[0] = mt[623]; i = 1; }
            if (j >= key_length) j = 0;
        }
        for (k = 623; k; k--) {
            mt[i] = (mt[i] ^ ((mt[i - 1] ^ (mt[i - 1] >> 30)) * 1566083941u)) - uint32_t(i);
            i++;
            if (i >= 624) { mt[0] = mt[623]; i = 1; }
        }
        mt[0] = 0x80000000u;
        mti = 624;
    }
public:
    uint32_t genrand() {
        static const uint32_t mag01[2] = {0x0u, 0x9908b0dfu};
        uint32_t y;
        if (mti >= 624) {
            int kk;
            for (kk = 0; kk < 624 - 397; kk++) {
                y = (mt[kk] & 0x80000000u) | (mt[kk + 1] & 0x7fffffffu);
                mt[kk] = mt[kk + 397] ^ (y >> 1) ^ mag01[y & 0x1u];
            }
            for (; kk < 623; kk++) {
                y = (mt[kk] & 0x80000000u) | (mt[kk + 1] & 0x7fffffffu);
                mt[kk] = mt[kk + (397 - 624)] ^ (y >> 1) ^ mag01[y & 0x1u];
            }
            y = (mt[623] & 0x80000000u) | (mt[0] & 0x7fffffffu);
            mt[623] = mt[396] ^ (y >> 1) ^ mag01[y & 0x1u];
            mti = 0;
        }
        y = mt[mti++];
        y ^= (y >> 11);
        y ^= (y << 7) & 0x9d2c5680u;
        y ^= (y << 15) & 0xefc60000u;
        y ^= (y >> 18);
        return y;
    }
};

}  // namespace pvz
