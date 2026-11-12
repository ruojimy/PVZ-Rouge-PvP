#include "sim/typed/replay_digest.h"
#include "sim/typed/replay_codec.h"
#include <algorithm>
#include <cmath>
#include <cstdio>
#include <cstdlib>

namespace pvz::typed72 {
namespace {
std::string number(double d){
    if(!std::isfinite(d))throw std::invalid_argument("Out of range float values are not JSON compliant");
    if(d==std::floor(d)&&std::fabs(d)<1e16){char b[32];std::snprintf(b,sizeof b,"%lld",static_cast<long long>(d));return b;}
    char b[32];for(int prec=1;prec<=17;++prec){std::snprintf(b,sizeof b,"%.*g",prec,d);if(std::strtod(b,nullptr)==d)break;}
    std::string s(b);if(s.find_first_of(".eEn")==std::string::npos)s+=".0";return s;
}
void string(std::string& out,const std::string& text){
    out+='"';for(const unsigned char c:text){
        switch(c){case '"':out+="\\\"";continue;case '\\':out+="\\\\";continue;
        case '\n':out+="\\n";continue;case '\r':out+="\\r";continue;case '\t':out+="\\t";continue;
        case '\b':out+="\\b";continue;case '\f':out+="\\f";continue;}
        if(c<0x20){char b[8];std::snprintf(b,sizeof b,"\\u%04x",c);out+=b;}else out+=char(c);
    }out+='"';
}
void encode(std::string& out,const WireObject& j,bool sorted,size_t depth){
    if(depth>1024)throw std::length_error("replay JSON recursion limit");
    if(j.is_null()){out+="null";return;}if(j.is_boolean()){out+=j.get<bool>()?"true":"false";return;}
    if(j.is_number()){out+=number(j.get<double>());return;}if(j.is_string()){string(out,j.get_ref<const std::string&>());return;}
    if(j.is_array()){out+='[';bool first=true;for(const auto& child:j){if(!first)out+=',';first=false;encode(out,child,sorted,depth+1);}out+=']';return;}
    if(j.is_object()){
        std::vector<std::string> keys;keys.reserve(j.size());for(const auto& item:j.items())keys.push_back(item.key());if(sorted)std::stable_sort(keys.begin(),keys.end());
        out+='{';bool first=true;for(const auto& key:keys){if(!first)out+=',';first=false;string(out,key);out+=':';encode(out,j.at(key),sorted,depth+1);}out+='}';return;
    }
    throw std::invalid_argument("unsupported replay JSON value");
}
}
std::string native_replay_canonical(const WireObject& value,bool sorted){std::string out;encode(out,value,sorted,0);return out;}
std::string native_replay_digest(const WireObject& value){return replay_sha256(native_replay_canonical(value));}
bool replay_snapshot_matches(const WireObject& value,std::string_view expected,std::string_view format,std::string_view build){
    if(native_replay_digest(value)==expected)return true;auto normalized=value;
    return normalize_r8_rope_width(normalized,format,build)&&native_replay_digest(normalized)==expected;
}
} // namespace pvz::typed72

namespace pvz::typed72 {
std::string replay_sha256(const std::string& msg) {
    static const uint32_t K[64] = {
        0x428a2f98,0x71374491,0xb5c0fbcf,0xe9b5dba5,0x3956c25b,0x59f111f1,0x923f82a4,0xab1c5ed5,0xd807aa98,0x12835b01,
        0x243185be,0x550c7dc3,0x72be5d74,0x80deb1fe,0x9bdc06a7,0xc19bf174,0xe49b69c1,0xefbe4786,0x0fc19dc6,0x240ca1cc,
        0x2de92c6f,0x4a7484aa,0x5cb0a9dc,0x76f988da,0x983e5152,0xa831c66d,0xb00327c8,0xbf597fc7,0xc6e00bf3,0xd5a79147,
        0x06ca6351,0x14292967,0x27b70a85,0x2e1b2138,0x4d2c6dfc,0x53380d13,0x650a7354,0x766a0abb,0x81c2c92e,0x92722c85,
        0xa2bfe8a1,0xa81a664b,0xc24b8b70,0xc76c51a3,0xd192e819,0xd6990624,0xf40e3585,0x106aa070,0x19a4c116,0x1e376c08,
        0x2748774c,0x34b0bcb5,0x391c0cb3,0x4ed8aa4a,0x5b9cca4f,0x682e6ff3,0x748f82ee,0x78a5636f,0x84c87814,0x8cc70208,
        0x90befffa,0xa4506ceb,0xbef9a3f7,0xc67178f2};
    uint32_t h[8] = {0x6a09e667,0xbb67ae85,0x3c6ef372,0xa54ff53a,0x510e527f,0x9b05688c,0x1f83d9ab,0x5be0cd19};
    std::string m = msg;
    uint64_t bits = uint64_t(msg.size()) * 8;
    m += char(0x80);
    while (m.size() % 64 != 56) m += char(0);
    for (int i = 7; i >= 0; --i) m += char((bits >> (i * 8)) & 0xff);
    auto rotr = [](uint32_t x, int n) { return (x >> n) | (x << (32 - n)); };
    for (size_t off = 0; off < m.size(); off += 64) {
        uint32_t w[64];
        for (int i = 0; i < 16; ++i)
            w[i] = (uint32_t(uint8_t(m[off + i * 4])) << 24) | (uint32_t(uint8_t(m[off + i * 4 + 1])) << 16) |
                   (uint32_t(uint8_t(m[off + i * 4 + 2])) << 8) | uint32_t(uint8_t(m[off + i * 4 + 3]));
        for (int i = 16; i < 64; ++i) {
            uint32_t s0 = rotr(w[i - 15], 7) ^ rotr(w[i - 15], 18) ^ (w[i - 15] >> 3);
            uint32_t s1 = rotr(w[i - 2], 17) ^ rotr(w[i - 2], 19) ^ (w[i - 2] >> 10);
            w[i] = w[i - 16] + s0 + w[i - 7] + s1;
        }
        uint32_t a = h[0], b = h[1], c = h[2], d = h[3], e = h[4], f = h[5], g = h[6], hh = h[7];
        for (int i = 0; i < 64; ++i) {
            uint32_t S1 = rotr(e, 6) ^ rotr(e, 11) ^ rotr(e, 25);
            uint32_t ch = (e & f) ^ (~e & g);
            uint32_t t1 = hh + S1 + ch + K[i] + w[i];
            uint32_t S0 = rotr(a, 2) ^ rotr(a, 13) ^ rotr(a, 22);
            uint32_t mj = (a & b) ^ (a & c) ^ (b & c);
            uint32_t t2 = S0 + mj;
            hh = g; g = f; f = e; e = d + t1; d = c; c = b; b = a; a = t1 + t2;
        }
        h[0] += a; h[1] += b; h[2] += c; h[3] += d; h[4] += e; h[5] += f; h[6] += g; h[7] += hh;
    }
    char buf[65];
    for (int i = 0; i < 8; ++i) snprintf(buf + i * 8, 9, "%08x", h[i]);
    return std::string(buf, 64);
}
} // namespace pvz::typed72
