from pathlib import Path
p=Path('cold72_export.cpp');t=p.read_text(encoding='utf8')
def sub(a,b):
    global t
    assert t.count(a)==1,a
    t=t.replace(a,b)
sub('#include "pg/pg.h"\n','#include "pg/pg.h"\n#include "sim/pvp/hand/graphics.h"\n')
sub('J parsed(const V& v)','''// Particle sampling reads sprite alpha, so these pixels feed the authoritative RNG.
void write_atlas(const V& atlas,const std::string& path){
    std::ofstream o(u8p(path),std::ios::binary);uint32_t count=0;o.write(reinterpret_cast<const char*>(&count),4);
    for(const auto& [key,image]:py::items_vec(atlas)){
        V surface;
        try{surface=pvz::getattr(image,Sym("pixels"));}catch(const PyError&){continue;}
        const auto* s=pg::surf(surface);const uint32_t w=uint32_t(s->w()),h=uint32_t(s->h());const auto name=key.str();const uint32_t n=uint32_t(name.size());
        o.write(reinterpret_cast<const char*>(&n),4);o.write(name.data(),n);o.write(reinterpret_cast<const char*>(&w),4);o.write(reinterpret_cast<const char*>(&h),4);
        std::vector<uint8_t> rgba;rgba.reserve(size_t(w)*h*4);
        for(uint32_t y=0;y<h;++y)for(uint32_t x=0;x<w;++x){
            const auto* pixel=reinterpret_cast<const uint32_t*>(static_cast<const uint8_t*>(s->s->pixels)+size_t(y)*s->s->pitch)+x;
            uint8_t r,g,b,a;SDL_GetRGBA(*pixel,s->s->format,&r,&g,&b,&a);rgba.insert(rgba.end(),{r,g,b,a});
        }
        o.write(reinterpret_cast<const char*>(rgba.data()),std::streamsize(rgba.size()));++count;
    }
    o.seekp(0);o.write(reinterpret_cast<const char*>(&count),4);std::printf("atlas images %u\\n",count);
}
J parsed(const V& v)''')
sub('if(argc!=3){std::fprintf(stderr,"usage: cold72_export scenario out\\n");return 1;}','if(argc!=3&&argc!=4){std::fprintf(stderr,"usage: cold72_export scenario out [atlas]\\n");return 1;}')
sub('out["rng_room"]=','if(argc==4)write_atlas(G.find_global(V("图集"))?*G.find_global(V("图集")):V::dict(),argv[3]);\n        out["rng_room"]=')
p.write_text(t,encoding='utf8')
p=Path('match_probe.cpp');t=p.read_text(encoding='utf8')
sub('''        tick_state.observer=this;\n''','''        tick_state.observer=this;
        runtime.presentation.enabled=g.at("设置").at("粒子效果");runtime.presentation.camera={g.at("摄像机").at(0),g.at("摄像机").at(1)};runtime.presentation.screen_width=g.at("总宽");
''')
sub('''void load_rng(pvz::PyRandom& rng,const J& j)''','''void load_atlas(const std::string& path,std::unordered_map<std::string,SpritePixels>& atlas){
    std::ifstream in(path,std::ios::binary);if(!in)throw std::runtime_error("missing cold atlas");uint32_t count=0;in.read(reinterpret_cast<char*>(&count),4);
    for(uint32_t i=0;i<count;++i){
        uint32_t n=0,w=0,h=0;in.read(reinterpret_cast<char*>(&n),4);std::string name(n,0);in.read(name.data(),n);in.read(reinterpret_cast<char*>(&w),4);in.read(reinterpret_cast<char*>(&h),4);
        SpritePixels s;s.width=int(w);s.height=int(h);s.pixels.resize(size_t(w)*h);in.read(reinterpret_cast<char*>(s.pixels.data()),std::streamsize(size_t(w)*h*4));atlas.emplace(std::move(name),std::move(s));
    }
    if(!in)throw std::runtime_error("truncated cold atlas");
}
void load_rng(pvz::PyRandom& rng,const J& j)''')
sub('''if(argc!=5)throw std::invalid_argument("usage: match72 cold.json scenario.json out.jsonl report.json");''','''if(argc!=6)throw std::invalid_argument("usage: match72 cold.json atlas.bin scenario.json out.jsonl report.json");''')
sub('''std::ifstream cold_stream(argv[1],std::ios::binary),scenario_stream(argv[2],std::ios::binary);''','''std::ifstream cold_stream(argv[1],std::ios::binary),scenario_stream(argv[3],std::ios::binary);''')
sub('''std::ofstream output(argv[3],std::ios::binary);''','''std::ofstream output(argv[4],std::ios::binary);''')
sub('''std::ofstream(argv[4],std::ios::binary)<<report''','''std::ofstream(argv[5],std::ios::binary)<<report''')
sub('''        match.setup(cold,scenario);\n''','''        load_atlas(argv[2],match.battle.runtime.presentation.atlas);\n        match.setup(cold,scenario);\n''')
p.write_text(t,encoding='utf8')
p=Path('compare_match.py');t=p.read_text(encoding='utf8')
sub("for cmd in ([EXPORT,source,cold],[RECORD,source,ref]):","atlas=out/'atlas.bin'\n    for cmd in ([EXPORT,source,cold,atlas],[RECORD,source,ref]):")
sub("run=subprocess.run([str(MATCH),str(cold),str(source),str(typed),str(report)]","run=subprocess.run([str(MATCH),str(cold),str(atlas),str(source),str(typed),str(report)]")
p.write_text(t,encoding='utf8')
