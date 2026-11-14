#include "sim/typed72_app/cold_file.h"
#ifndef PVZ_AI_NN_PLAIN_FILES
#include <zlib.h>
#else
#include <fstream>
#include <filesystem>
#endif
#include <cstring>
#include <stdexcept>
namespace pvz::typed72app {
namespace {
using J=nlohmann::json;
uint32_t u32(const std::string& bytes,size_t& at){
    if(at+4>bytes.size())throw std::runtime_error("truncated cold atlas");
    const auto* p=reinterpret_cast<const unsigned char*>(bytes.data()+at);at+=4;
    return uint32_t(p[0])|uint32_t(p[1])<<8|uint32_t(p[2])<<16|uint32_t(p[3])<<24;   // little-endian file
}
}
std::string read_file_maybe_gz(const std::string& path){
#ifdef PVZ_AI_NN_PLAIN_FILES
    std::ifstream file(std::filesystem::u8path(path),std::ios::binary);
    if(!file)throw std::runtime_error("cannot open "+path);
    std::string out((std::istreambuf_iterator<char>(file)),{});
    if(file.bad())throw std::runtime_error("cannot read "+path);
    if(out.size()>=2&&uint8_t(out[0])==0x1f&&uint8_t(out[1])==0x8b)
        throw std::runtime_error("gzip disabled: run materialize_corpus.py first: "+path);
    return out;
#else
    gzFile in=gzopen(path.c_str(),"rb");
    if(!in)throw std::runtime_error("cannot open "+path);
    std::string out;char buffer[1<<16];
    for(;;){
        const int n=gzread(in,buffer,sizeof buffer);
        if(n<0){gzclose(in);throw std::runtime_error("cannot read "+path);}
        if(n==0)break;
        out.append(buffer,size_t(n));
    }
    gzclose(in);
    return out;
#endif
}
ColdExport load_cold_files(const std::string& cold_json,const std::string& atlas_bin,const std::string& draw_json){
    ColdExport out;
    out.cold=J::parse(read_file_maybe_gz(cold_json));
    out.draw_atlas=J::parse(read_file_maybe_gz(draw_json));
    // atlas.bin: u32 count, then per sprite u32 name bytes, name, u32 width, u32 height, RGBA rows.
    const std::string bytes=read_file_maybe_gz(atlas_bin);size_t at=0;
    const uint32_t count=u32(bytes,at);out.atlas.reserve(count);
    for(uint32_t i=0;i<count;++i){
        const uint32_t n=u32(bytes,at);
        if(at+n>bytes.size())throw std::runtime_error("truncated cold atlas");
        std::string name(bytes.data()+at,n);at+=n;
        const uint32_t w=u32(bytes,at),h=u32(bytes,at);
        if(w>INT32_MAX||h>INT32_MAX||uint64_t(w)*h>(bytes.size()-at)/4)
            throw std::runtime_error("invalid or truncated cold atlas dimensions");
        const size_t pixels=size_t(w)*h;
        ColdPixels p;p.width=int(w);p.height=int(h);p.rgba.resize(pixels);
        if(pixels)std::memcpy(p.rgba.data(),bytes.data()+at,pixels*4);
        at+=pixels*4;
        out.atlas.emplace_back(std::move(name),std::move(p));
    }
    if(at!=bytes.size())throw std::runtime_error("trailing bytes in cold atlas");
    return out;
}
std::vector<CorpusEntry> read_corpus_index(const std::string& corpus_dir){
    const J index=J::parse(read_file_maybe_gz(corpus_dir+"/index.json"));
    const std::string atlas=corpus_dir+"/"+index.at("atlas").get<std::string>();
    std::vector<CorpusEntry> out;
    for(const auto& e:index.at("entries")){
        CorpusEntry c;c.id=e.at("id");c.map=e.at("map");c.night=e.at("night");c.seed=e.at("seed");
        c.bans=e.at("bans").get<std::vector<std::string>>();
        c.plant_deck=e.at("decks").at("plant").get<std::vector<std::string>>();
        c.zombie_deck=e.at("decks").at("zombie").get<std::vector<std::string>>();
        c.cold_path=corpus_dir+"/"+e.at("cold").get<std::string>();
        c.draw_path=corpus_dir+"/"+e.at("draw").get<std::string>();
        c.atlas_path=atlas;
        out.push_back(std::move(c));
    }
    return out;
}
CorpusEntry corpus_entry(const std::string& corpus_dir,const std::string& id){
    for(auto& e:read_corpus_index(corpus_dir))if(e.id==id)return e;
    throw std::runtime_error("no corpus entry "+id);
}
ColdExport load_corpus_entry(const CorpusEntry& e){return load_cold_files(e.cold_path,e.atlas_path,e.draw_path);}
} // namespace pvz::typed72app
