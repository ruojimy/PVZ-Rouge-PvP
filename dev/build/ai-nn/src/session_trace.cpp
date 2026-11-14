// Acceptance tool for step 1b: runs an exported opening through cold_file + Session::create
// with no inputs and writes, per room tick, what typed72_match_gate exposes for the same run:
// the match RNG digest, the public snapshot (MATCH_SNAPSHOTS) and the battle log entries.
//   session_trace cold.json[.gz] atlas.bin[.gz] atlas.bin.draw.json[.gz] ticks out.jsonl [map]
#include "common.h"
#include "sim/typed72_app/cold_file.h"
#include "sim/typed72_app/session.h"
#include <fstream>
#include <iostream>
int main(int argc,char** argv){
    try{
        if(argc!=6&&argc!=7)throw std::invalid_argument("usage: session_trace cold.json atlas.bin atlas.bin.draw.json ticks out.jsonl [map]");
        using namespace pvz::typed72app;using ainn::J;
        auto session=Session::create(load_cold_files(argv[1],argv[2],argv[3]),argc>6?argv[6]:"家院");
        const int ticks=std::stoi(argv[4]);std::ofstream out(argv[5],std::ios::binary);
        size_t log_read=0;
        const auto row=[&](int rt){
            J logs=J::array();for(;log_read<session->log_size();++log_read)logs.push_back(session->log_entry(log_read));
            out<<J{{"rt",rt},{"rng",ainn::rng_digest(session->rng_state())},{"snapshot",session->snapshot()},{"log",logs}}.dump(-1,' ',false,J::error_handler_t::replace)<<'\n';
        };
        row(-1);
        for(int rt=0;rt<ticks&&!session->finished();++rt){session->step();row(rt);}
        std::cout<<J{{"room_ticks",session->tick()},{"log_entries",session->log_size()},{"result",session->result_json()}}.dump()<<'\n';
        return out?0:3;
    }catch(const std::exception& error){std::cerr<<error.what()<<'\n';return 2;}
}
