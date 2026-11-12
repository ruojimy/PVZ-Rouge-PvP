#include "core/png.h"
#include "core/fsutil.h"
#include <cstring>
#include <algorithm>
#include <fstream>

namespace pvz::png {
namespace {

// ---------------------------------------------------------------- inflate (RFC 1951)
struct BitReader {
    const uint8_t* p; size_t n, pos = 0; uint32_t bitbuf = 0; int bitcnt = 0;
    BitReader(const uint8_t* d, size_t len) : p(d), n(len) {}
    bool need(int k) {
        while (bitcnt < k) {
            if (pos >= n) return false;
            bitbuf |= uint32_t(p[pos++]) << bitcnt;
            bitcnt += 8;
        }
        return true;
    }
    bool bits(int k, uint32_t& v) {
        if (k == 0) { v = 0; return true; }
        if (!need(k)) return false;
        v = bitbuf & ((1u << k) - 1);
        bitbuf >>= k; bitcnt -= k;
        return true;
    }
    void align() { bitbuf = 0; bitcnt = 0; }
};

struct Huffman {
    uint16_t count[16] = {};
    uint16_t symbol[320] = {};
    bool build(const uint8_t* lengths, int n) {
        std::memset(count, 0, sizeof(count));
        for (int i = 0; i < n; ++i) count[lengths[i]]++;
        count[0] = 0;
        uint16_t offs[16] = {};
        for (int i = 1; i < 16; ++i) offs[i] = offs[i - 1] + count[i - 1];
        for (int i = 0; i < n; ++i) if (lengths[i]) symbol[offs[lengths[i]]++] = uint16_t(i);
        return true;
    }
    // canonical decode, one bit at a time (inputs are small atlas images)
    int decode(BitReader& br) const {
        int code = 0, first = 0, index = 0;
        for (int len = 1; len < 16; ++len) {
            uint32_t b;
            if (!br.bits(1, b)) return -1;
            code |= int(b);
            int c = count[len];
            if (code - c < first) return symbol[index + (code - first)];
            index += c; first += c; first <<= 1; code <<= 1;
        }
        return -1;
    }
};

const uint16_t kLenBase[29] = {3, 4, 5, 6, 7, 8, 9, 10, 11, 13, 15, 17, 19, 23, 27, 31, 35, 43, 51, 59, 67, 83, 99, 115, 131, 163, 195, 227, 258};
const uint8_t kLenExtra[29] = {0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 2, 2, 2, 2, 3, 3, 3, 3, 4, 4, 4, 4, 5, 5, 5, 5, 0};
const uint16_t kDistBase[30] = {1, 2, 3, 4, 5, 7, 9, 13, 17, 25, 33, 49, 65, 97, 129, 193, 257, 385, 513, 769, 1025, 1537, 2049, 3073, 4097, 6145, 8193, 12289, 16385, 24577};
const uint8_t kDistExtra[30] = {0, 0, 0, 0, 1, 1, 2, 2, 3, 3, 4, 4, 5, 5, 6, 6, 7, 7, 8, 8, 9, 9, 10, 10, 11, 11, 12, 12, 13, 13};

bool inflate_block(BitReader& br, std::vector<uint8_t>& out, const Huffman& lit, const Huffman& dist) {
    for (;;) {
        int sym = lit.decode(br);
        if (sym < 0) return false;
        if (sym < 256) { out.push_back(uint8_t(sym)); continue; }
        if (sym == 256) return true;
        sym -= 257;
        if (sym >= 29) return false;
        uint32_t e;
        if (!br.bits(kLenExtra[sym], e)) return false;
        size_t len = kLenBase[sym] + e;
        int ds = dist.decode(br);
        if (ds < 0 || ds >= 30) return false;
        if (!br.bits(kDistExtra[ds], e)) return false;
        size_t d = kDistBase[ds] + e;
        if (d > out.size()) return false;
        size_t from = out.size() - d;
        for (size_t i = 0; i < len; ++i) out.push_back(out[from + i]);
    }
}

bool inflate_raw(BitReader& br, std::vector<uint8_t>& out) {
    for (;;) {
        uint32_t final_, type;
        if (!br.bits(1, final_) || !br.bits(2, type)) return false;
        if (type == 0) {
            br.align();
            if (br.pos + 4 > br.n) return false;
            uint16_t len = uint16_t(br.p[br.pos] | (br.p[br.pos + 1] << 8));
            br.pos += 4;
            if (br.pos + len > br.n) return false;
            out.insert(out.end(), br.p + br.pos, br.p + br.pos + len);
            br.pos += len;
        } else if (type == 1) {
            static Huffman lit, dist;
            static bool init = false;
            if (!init) {
                uint8_t l[288];
                for (int i = 0; i < 144; ++i) l[i] = 8;
                for (int i = 144; i < 256; ++i) l[i] = 9;
                for (int i = 256; i < 280; ++i) l[i] = 7;
                for (int i = 280; i < 288; ++i) l[i] = 8;
                lit.build(l, 288);
                uint8_t d[30];
                for (int i = 0; i < 30; ++i) d[i] = 5;
                dist.build(d, 30);
                init = true;
            }
            if (!inflate_block(br, out, lit, dist)) return false;
        } else if (type == 2) {
            uint32_t hlit, hdist, hclen;
            if (!br.bits(5, hlit) || !br.bits(5, hdist) || !br.bits(4, hclen)) return false;
            hlit += 257; hdist += 1; hclen += 4;
            static const uint8_t order[19] = {16, 17, 18, 0, 8, 7, 9, 6, 10, 5, 11, 4, 12, 3, 13, 2, 14, 1, 15};
            uint8_t cl[19] = {};
            for (uint32_t i = 0; i < hclen; ++i) { uint32_t v; if (!br.bits(3, v)) return false; cl[order[i]] = uint8_t(v); }
            Huffman clh; clh.build(cl, 19);
            uint8_t lens[320] = {};
            uint32_t idx = 0;
            while (idx < hlit + hdist) {
                int sym = clh.decode(br);
                if (sym < 0) return false;
                if (sym < 16) { lens[idx++] = uint8_t(sym); continue; }
                uint32_t rep = 0; uint8_t val = 0;
                if (sym == 16) { if (idx == 0) return false; val = lens[idx - 1]; uint32_t v; if (!br.bits(2, v)) return false; rep = 3 + v; }
                else if (sym == 17) { uint32_t v; if (!br.bits(3, v)) return false; rep = 3 + v; }
                else { uint32_t v; if (!br.bits(7, v)) return false; rep = 11 + v; }
                if (idx + rep > hlit + hdist) return false;
                while (rep--) lens[idx++] = val;
            }
            Huffman lit, dist;
            lit.build(lens, int(hlit));
            dist.build(lens + hlit, int(hdist));
            if (!inflate_block(br, out, lit, dist)) return false;
        } else {
            return false;
        }
        if (final_) return true;
    }
}

uint32_t be32(const uint8_t* p) { return (uint32_t(p[0]) << 24) | (uint32_t(p[1]) << 16) | (uint32_t(p[2]) << 8) | p[3]; }

int paeth(int a, int b, int c) {
    int p = a + b - c, pa = p > a ? p - a : a - p, pb = p > b ? p - b : b - p, pc = p > c ? p - c : c - p;
    if (pa <= pb && pa <= pc) return a;
    return pb <= pc ? b : c;
}

}  // namespace

bool inflate_zlib(const uint8_t* src, size_t n, std::vector<uint8_t>& out) {
    if (n < 2 || (src[0] & 0x0F) != 8) return false;
    BitReader br(src + 2, n - 2);
    return inflate_raw(br, out);
}

uint32_t adler32(const uint8_t* p, size_t n) {
    uint32_t a = 1, b = 0;
    for (size_t i = 0; i < n; ++i) { a = (a + p[i]) % 65521; b = (b + a) % 65521; }
    return (b << 16) | a;
}

namespace {
struct BitWriter {
    std::vector<uint8_t>& out; uint32_t buf = 0; int cnt = 0;
    explicit BitWriter(std::vector<uint8_t>& o) : out(o) {}
    void bits(uint32_t v, int n) { buf |= v << cnt; cnt += n; while (cnt >= 8) { out.push_back(uint8_t(buf)); buf >>= 8; cnt -= 8; } }
    void huff(uint32_t code, int len) {   // Huffman codes are sent most-significant bit first
        uint32_t r = 0;
        for (int i = 0; i < len; ++i) r |= ((code >> i) & 1u) << (len - 1 - i);
        bits(r, len);
    }
    void flush() { if (cnt > 0) { out.push_back(uint8_t(buf)); buf = 0; cnt = 0; } }
};
void fixed_lit(BitWriter& w, int v) {
    if (v < 144) w.huff(0x30 + v, 8);
    else if (v < 256) w.huff(0x190 + (v - 144), 9);
    else if (v < 280) w.huff(v - 256, 7);
    else w.huff(0xC0 + (v - 280), 8);
}
}  // namespace

void deflate_zlib(const uint8_t* src, size_t n, std::vector<uint8_t>& out, int level) {
    out.push_back(0x78); out.push_back(level <= 0 ? 0x01 : 0x9C);
    if (level <= 0) {
        size_t pos = 0;
        do {
            size_t len = std::min<size_t>(65535, n - pos);
            out.push_back(pos + len >= n ? 1 : 0);
            out.push_back(uint8_t(len)); out.push_back(uint8_t(len >> 8));
            out.push_back(uint8_t(~len)); out.push_back(uint8_t(~len >> 8));
            out.insert(out.end(), src + pos, src + pos + len);
            pos += len;
        } while (pos < n);
    } else {
        BitWriter w(out);
        w.bits(1, 1); w.bits(1, 2);                 // final block, fixed Huffman
        constexpr int HB = 15, HS = 1 << HB, WIN = 32768;
        std::vector<int32_t> head(HS, -1), prev(n ? n : 1, -1);
        int chain = level >= 6 ? 64 : 16;
        auto hash3 = [&](size_t i) { return ((uint32_t(src[i]) << 10) ^ (uint32_t(src[i + 1]) << 5) ^ src[i + 2]) & (HS - 1); };
        size_t i = 0;
        while (i < n) {
            int best = 0, bdist = 0;
            if (i + 2 < n) {
                uint32_t h = hash3(i);
                int32_t c = head[h];
                for (int k = 0; c >= 0 && k < chain && int(i) - c <= WIN; ++k, c = prev[size_t(c)]) {
                    int len = 0, maxl = int(std::min<size_t>(258, n - i));
                    while (len < maxl && src[size_t(c) + size_t(len)] == src[i + size_t(len)]) ++len;
                    if (len > best) { best = len; bdist = int(i) - c; if (len == maxl) break; }
                }
            }
            if (best >= 3) {
                int li = 0; while (li < 28 && kLenBase[li + 1] <= best) ++li;
                fixed_lit(w, 257 + li);
                w.bits(uint32_t(best - kLenBase[li]), kLenExtra[li]);
                int di = 0; while (di < 29 && kDistBase[di + 1] <= bdist) ++di;
                w.huff(uint32_t(di), 5);
                w.bits(uint32_t(bdist - kDistBase[di]), kDistExtra[di]);
                for (int k = 0; k < best; ++k, ++i)
                    if (i + 2 < n) { uint32_t h = hash3(i); prev[i] = head[h]; head[h] = int32_t(i); }
            } else {
                fixed_lit(w, src[i]);
                if (i + 2 < n) { uint32_t h = hash3(i); prev[i] = head[h]; head[h] = int32_t(i); }
                ++i;
            }
        }
        fixed_lit(w, 256);
        w.flush();
    }
    uint32_t ad = adler32(src, n);
    out.push_back(uint8_t(ad >> 24)); out.push_back(uint8_t(ad >> 16)); out.push_back(uint8_t(ad >> 8)); out.push_back(uint8_t(ad));
}

Image decode(const std::vector<uint8_t>& d, std::string* err) {
    auto fail = [&](const char* m) { if (err) *err = m; return Image{}; };
    static const uint8_t sig[8] = {137, 80, 78, 71, 13, 10, 26, 10};
    if (d.size() < 8 || std::memcmp(d.data(), sig, 8) != 0) return fail("not a png");
    size_t pos = 8;
    int w = 0, h = 0, depth = 0, ctype = 0, interlace = 0;
    std::vector<uint8_t> idat, palette, trns;
    while (pos + 8 <= d.size()) {
        uint32_t len = be32(&d[pos]);
        std::string type(reinterpret_cast<const char*>(&d[pos + 4]), 4);
        const uint8_t* body = &d[pos + 8];
        if (pos + 12 + len > d.size()) return fail("truncated chunk");
        if (type == "IHDR") {
            w = int(be32(body)); h = int(be32(body + 4)); depth = body[8]; ctype = body[9]; interlace = body[12];
        } else if (type == "PLTE") {
            palette.assign(body, body + len);
        } else if (type == "tRNS") {
            trns.assign(body, body + len);
        } else if (type == "IDAT") {
            idat.insert(idat.end(), body, body + len);
        } else if (type == "IEND") {
            break;
        }
        pos += 12 + len;
    }
    if (w <= 0 || h <= 0) return fail("no IHDR");
    if (depth != 8 || interlace != 0) return fail("unsupported png format (needs 8-bit, non-interlaced)");
    int channels = ctype == 0 ? 1 : ctype == 2 ? 3 : ctype == 3 ? 1 : ctype == 4 ? 2 : ctype == 6 ? 4 : 0;
    if (!channels) return fail("bad color type");
    std::vector<uint8_t> raw;
    raw.reserve(size_t(w) * h * channels + h);
    if (!inflate_zlib(idat.data(), idat.size(), raw)) return fail("inflate failed");
    size_t stride = size_t(w) * channels;
    if (raw.size() < (stride + 1) * h) return fail("short image data");
    std::vector<uint8_t> px(stride * h);
    for (int y = 0; y < h; ++y) {
        uint8_t f = raw[y * (stride + 1)];
        const uint8_t* src = &raw[y * (stride + 1) + 1];
        uint8_t* dst = &px[y * stride];
        const uint8_t* prev = y ? &px[(y - 1) * stride] : nullptr;
        for (size_t i = 0; i < stride; ++i) {
            int a = i >= size_t(channels) ? dst[i - channels] : 0;
            int b = prev ? prev[i] : 0;
            int c = (prev && i >= size_t(channels)) ? prev[i - channels] : 0;
            int v = src[i];
            switch (f) {
                case 0: break;
                case 1: v += a; break;
                case 2: v += b; break;
                case 3: v += (a + b) / 2; break;
                case 4: v += paeth(a, b, c); break;
                default: return fail("bad filter");
            }
            dst[i] = uint8_t(v);
        }
    }
    Image img;
    img.w = w; img.h = h;
    img.rgba.resize(size_t(w) * h * 4);
    for (size_t i = 0, n = size_t(w) * h; i < n; ++i) {
        uint8_t* o = &img.rgba[i * 4];
        const uint8_t* s = &px[i * channels];
        switch (ctype) {
            case 0: o[0] = o[1] = o[2] = s[0]; o[3] = 255; break;
            case 4: o[0] = o[1] = o[2] = s[0]; o[3] = s[1]; break;
            case 2:
                o[0] = s[0]; o[1] = s[1]; o[2] = s[2]; o[3] = 255;
                if (trns.size() >= 6 && s[0] == trns[1] && s[1] == trns[3] && s[2] == trns[5]) o[3] = 0;
                break;
            case 6: o[0] = s[0]; o[1] = s[1]; o[2] = s[2]; o[3] = s[3]; break;
            case 3: {
                size_t k = s[0];
                if (k * 3 + 2 < palette.size()) { o[0] = palette[k * 3]; o[1] = palette[k * 3 + 1]; o[2] = palette[k * 3 + 2]; }
                else { o[0] = o[1] = o[2] = 0; }
                o[3] = k < trns.size() ? trns[k] : 255;
                break;
            }
        }
    }
    return img;
}

Image load(const std::string& path, std::string* err) {
    std::ifstream f(u8p(path), std::ios::binary);
    if (!f) { if (err) *err = "cannot open " + path; return Image{}; }
    std::vector<uint8_t> d((std::istreambuf_iterator<char>(f)), std::istreambuf_iterator<char>());
    return decode(d, err);
}

}  // namespace pvz::png
