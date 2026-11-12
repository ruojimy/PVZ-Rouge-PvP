// Minimal PNG decoder (8-bit gray / gray+alpha / RGB / RGBA / palette, non-interlaced).
// The simulation samples real atlas pixels (原版 增粒子 picks random opaque pixels with the
// game RNG), so pixel data must be available without the renderer.
#pragma once
#include <cstdint>
#include <string>
#include <vector>

namespace pvz::png {

struct Image {
    int w = 0, h = 0;
    std::vector<uint8_t> rgba;   // w*h*4
    bool ok() const { return w > 0 && h > 0; }
    const uint8_t* at(int x, int y) const { return &rgba[(size_t(y) * w + x) * 4]; }
};

// Decode a PNG file; returns an empty image on failure (err describes why).
Image load(const std::string& path, std::string* err = nullptr);
Image decode(const std::vector<uint8_t>& data, std::string* err = nullptr);

// zlib stream inflate (exposed for tests)
bool inflate_zlib(const uint8_t* src, size_t n, std::vector<uint8_t>& out);
// zlib stream deflate: LZ77 (hash chains) + fixed Huffman codes; level 0 = stored blocks
void deflate_zlib(const uint8_t* src, size_t n, std::vector<uint8_t>& out, int level = 6);
uint32_t adler32(const uint8_t* p, size_t n);

}  // namespace pvz::png
