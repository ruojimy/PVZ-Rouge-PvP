#pragma once
// Small helpers shared by the headless AI tools (build/ai-nn/src). No V, no kernel types.
#include <nlohmann/json.hpp>
#include <array>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <string>
namespace ainn {
using J=nlohmann::json;
// SHA-256 (FIPS 180-4), streaming.
class Sha256 {
public:
    Sha256(){reset();}
    void reset(){h_={0x6a09e667u,0xbb67ae85u,0x3c6ef372u,0xa54ff53au,0x510e527fu,0x9b05688cu,0x1f83d9abu,0x5be0cd19u};len_=0;fill_=0;}
    void update(const void* data,size_t n){
        const auto* p=static_cast<const uint8_t*>(data);len_+=n;
        while(n){const size_t take=std::min(n,size_t(64)-fill_);std::memcpy(buf_+fill_,p,take);fill_+=take;p+=take;n-=take;if(fill_==64){block(buf_);fill_=0;}}
    }
    void update(const std::string& s){update(s.data(),s.size());}
    std::string hex(){
        Sha256 c=*this;const uint64_t bits=c.len_*8;const uint8_t one=0x80,zero=0;
        c.update(&one,1);while(c.fill_!=56)c.update(&zero,1);
        uint8_t be[8];for(int i=0;i<8;++i)be[i]=uint8_t(bits>>(56-8*i));c.update(be,8);
        char out[65];for(int i=0;i<8;++i)std::snprintf(out+8*i,9,"%08x",c.h_[i]);return std::string(out,64);
    }
private:
    static uint32_t rotr(uint32_t x,int n){return x>>n|x<<(32-n);}
    void block(const uint8_t* p){
        static constexpr uint32_t k[64]={
            0x428a2f98,0x71374491,0xb5c0fbcf,0xe9b5dba5,0x3956c25b,0x59f111f1,0x923f82a4,0xab1c5ed5,0xd807aa98,0x12835b01,0x243185be,0x550c7dc3,0x72be5d74,0x80deb1fe,0x9bdc06a7,0xc19bf174,
            0xe49b69c1,0xefbe4786,0x0fc19dc6,0x240ca1cc,0x2de92c6f,0x4a7484aa,0x5cb0a9dc,0x76f988da,0x983e5152,0xa831c66d,0xb00327c8,0xbf597fc7,0xc6e00bf3,0xd5a79147,0x06ca6351,0x14292967,
            0x27b70a85,0x2e1b2138,0x4d2c6dfc,0x53380d13,0x650a7354,0x766a0abb,0x81c2c92e,0x92722c85,0xa2bfe8a1,0xa81a664b,0xc24b8b70,0xc76c51a3,0xd192e819,0xd6990624,0xf40e3585,0x106aa070,
            0x19a4c116,0x1e376c08,0x2748774c,0x34b0bcb5,0x391c0cb3,0x4ed8aa4a,0x5b9cca4f,0x682e6ff3,0x748f82ee,0x78a5636f,0x84c87814,0x8cc70208,0x90befffa,0xa4506ceb,0xbef9a3f7,0xc67178f2};
        uint32_t w[64];
        for(int i=0;i<16;++i)w[i]=uint32_t(p[4*i])<<24|uint32_t(p[4*i+1])<<16|uint32_t(p[4*i+2])<<8|p[4*i+3];
        for(int i=16;i<64;++i){const uint32_t s0=rotr(w[i-15],7)^rotr(w[i-15],18)^w[i-15]>>3,s1=rotr(w[i-2],17)^rotr(w[i-2],19)^w[i-2]>>10;w[i]=w[i-16]+s0+w[i-7]+s1;}
        uint32_t a=h_[0],b=h_[1],c=h_[2],d=h_[3],e=h_[4],f=h_[5],g=h_[6],h=h_[7];
        for(int i=0;i<64;++i){
            const uint32_t t1=h+(rotr(e,6)^rotr(e,11)^rotr(e,25))+((e&f)^(~e&g))+k[i]+w[i];
            const uint32_t t2=(rotr(a,2)^rotr(a,13)^rotr(a,22))+((a&b)^(a&c)^(b&c));
            h=g;g=f;f=e;e=d+t1;d=c;c=b;b=a;a=t1+t2;
        }
        h_[0]+=a;h_[1]+=b;h_[2]+=c;h_[3]+=d;h_[4]+=e;h_[5]+=f;h_[6]+=g;h_[7]+=h;
    }
    std::array<uint32_t,8> h_;uint64_t len_;uint8_t buf_[64];size_t fill_;
};
// The match RNG digest typed72_match_gate prints (match_probe.cpp digest/hex_digest):
// FNV-1a style mix over the 624 MT words and the index, from Session::rng_state().
inline std::string rng_digest(const J& state){
    uint64_t h=1469598103934665603ull;
    const auto mix=[&](uint32_t v){h=(h^v)*1099511628211ull;};
    for(const auto& w:state.at("mt"))mix(w.get<uint32_t>());
    mix(uint32_t(state.at("mti").get<int64_t>()));
    char text[32];std::snprintf(text,sizeof text,"%016llx",(unsigned long long)h);return text;
}
// A number as it reaches Session::command in the game: the V runtime dumps every number with
// "%.17g" (core/value.cpp dump_to) and typed_battle.cpp parses that text back (vj), so
// integral values arrive as JSON integers and the rest as doubles.
inline J game_number(double v){
    if(std::isnan(v))return "nan";
    if(std::isinf(v))return v>0?"inf":"-inf";
    char buf[64];std::snprintf(buf,sizeof buf,"%.17g",v);return J::parse(buf);
}
} // namespace ainn
