// Real production snapshot codec: bounded output, integrity, and stream boundaries.
#include "pg/pg.h"
#include "core/gil.h"
#include "core/alloc.h"
#include "core/snapshot_compression.h"
#include "data/datastore.h"
#include "ui/gen/pm_app.h"
#include <nlohmann/json.hpp>
#include <chrono>
#include <fstream>
#include <iostream>
using namespace pvz;
using J = nlohmann::json;
namespace {
V wire(const std::string& compressed) {
    V encoded = py::stdlib_call(V("base64.b64encode"), Args{V::bytes(compressed)});
    return py_dict({{V("encoding"),V("zlib-json")}, {V("data"),callm(encoded,SY("decode"),Args{V("ascii")})}});
}
bool rejects(const std::string& compressed) {
    try { pm_app::f_unpack_snapshot(Args{wire(compressed)}); return false; }
    catch (const PyError&) { return true; }
}
}
int main(int argc,char** argv) {
    if(argc!=2) return 2;
    SDL_SetMainReady(); gil::init(); data::set_data_dir("extract/data"); pg::install_pygame(); pm_app::init();
    J checks=J::array();
    auto check=[&](const char* name,bool ok,J evidence=J::object()) { checks.push_back({{"name",name},{"passed",ok},{"evidence",evidence}}); };
    const std::string raw="{\"phase\":\"battle\",\"seq\":123,\"name\":\"合作\"}";
    for(int level:{0,1,4,6,9}) {
        V out=pm_app::f_unpack_snapshot(Args{wire(snapshot_compress(raw,level))});
        check(("roundtrip_level_"+std::to_string(level)).c_str(),py::m_get(out,V("seq"))==V(123));
    }
    const std::string encoded=snapshot_compress(raw,4);
    std::string corrupt=encoded; corrupt.back()^=1;
    check("corrupt_checksum_rejected",rejects(corrupt));
    check("missing_checksum_rejected",rejects(encoded.substr(0,encoded.size()-4)));
    check("trailing_bytes_rejected",rejects(encoded+"junk"));
    check("concatenated_stream_rejected",rejects(encoded+encoded));
    {
        bool all_rejected=true;
        for(size_t end=0;end<encoded.size();++end)
            all_rejected=rejects(encoded.substr(0,end)) && all_rejected;
        check("all_truncated_prefixes_rejected",all_rejected,{{"prefixes",encoded.size()}});
        std::string invalid=encoded; invalid.front()^=1;
        check("invalid_header_rejected",rejects(invalid));
    }
    {
        V inflater=py::stdlib_call(V("zlib.decompressobj"),Args{});
        std::string decoded;
        for(char byte:encoded) decoded+=py::bytes_data(callm(inflater,SY("decompress"),Args{V::bytes(std::string(1,byte))}));
        check("incremental_stream_exact",decoded==raw && getattr(inflater,SY("eof")).truthy());
    }
    {
        bool equal=true;
        for(size_t cap:{size_t(1),raw.size(),raw.size()+1}) {
            V inflater=py::stdlib_call(V("zlib.decompressobj"),Args{});
            std::string result=py::bytes_data(callm(inflater,SY("decompress"),Args{V::bytes(encoded),V(double(cap))}));
            for(size_t i=0;i<=raw.size() && !getattr(inflater,SY("eof")).truthy();++i)
                result+=py::bytes_data(callm(inflater,SY("decompress"),Args{getattr(inflater,SY("unconsumed_tail")),V(double(cap))}));
            equal=equal && result==raw && getattr(inflater,SY("eof")).truthy();
        }
        check("small_and_exact_output_caps",equal);
    }
    {
        V inflater=py::stdlib_call(V("zlib.decompressobj"),Args{});
        V result=callm(inflater,SY("decompress"),Args{V::bytes(snapshot_compress("",4))});
        check("empty_stream_eof",py::len(result).num()==0 && getattr(inflater,SY("eof")).truthy());
        callm(inflater,SY("decompress"),Args{V::bytes("first")});
        callm(inflater,SY("decompress"),Args{V::bytes("second")});
        check("post_eof_unused_data_accumulates",py::bytes_data(getattr(inflater,SY("unused_data")))=="firstsecond");
    }
    {
        V inflater=py::stdlib_call(V("zlib.decompressobj"),Args{});
        std::string result=py::bytes_data(callm(inflater,SY("decompress"),Args{V::bytes(encoded),V(7)}));
        result+=py::bytes_data(callm(inflater,SY("flush"),Args{}));
        check("flush_consumes_bounded_tail",result==raw && getattr(inflater,SY("eof")).truthy() && !getattr(inflater,SY("unconsumed_tail")).truthy());
        bool closed=false;
        try { callm(inflater,SY("decompress"),Args{V::bytes("")}); } catch(const PyError&) { closed=true; }
        check("flush_finishes_stream_once",closed && py::len(callm(inflater,SY("flush"),Args{})).num()==0);
    }
    {
        V inflater=py::stdlib_call(V("zlib.decompressobj"),Args{});
        std::string result=py::bytes_data(callm(inflater,SY("decompress"),Args{V::bytes(encoded.substr(0,encoded.size()-3)),V(7)}));
        result+=py::bytes_data(callm(inflater,SY("flush"),Args{}));
        const bool incomplete=!getattr(inflater,SY("eof")).truthy();
        result+=py::bytes_data(callm(inflater,SY("decompress"),Args{V::bytes(encoded.substr(encoded.size()-3))}));
        check("truncated_flush_preserves_incomplete_state",incomplete && result==raw && getattr(inflater,SY("eof")).truthy());
    }
    {
        V inflater=py::stdlib_call(V("zlib.decompressobj"),Args{});
        std::string result=py::bytes_data(callm(inflater,SY("decompress"),Args{V::bytes(corrupt),V(7)}));
        result+=py::bytes_data(callm(inflater,SY("flush"),Args{}));
        check("bad_checksum_flush_never_claims_eof",result==raw && !getattr(inflater,SY("eof")).truthy());
    }
    {
        const size_t limit=size_t(pm_app::MAX_SNAPSHOT_BYTES.num());
        std::string exact="{\"padding\":\""+std::string(limit-14,'a')+"\"}";
        V result=pm_app::f_unpack_snapshot(Args{wire(snapshot_compress(exact,1))});
        check("snapshot_exact_limit_accepted",exact.size()==limit && py::len(py::m_get(result,V("padding"))).num()==limit-14);
        exact.insert(exact.size()-2,1,'a');
        check("snapshot_one_byte_over_limit_rejected",rejects(snapshot_compress(exact,1)));
    }
    {
        // The input is intentionally small after compression, but expands to 32 MiB.
        const std::string expanded(32*1024*1024,'a');
        const std::string compressed=snapshot_compress(expanded,1);
        V input=V::bytes(compressed),inflater=py::stdlib_call(V("zlib.decompressobj"),Args{});
        constexpr size_t cap=1024*1024;
        native_alloc_trace_start(); native_alloc_trace_reset_peak();
        V decoded=callm(inflater,SY("decompress"),Args{input,V(double(cap))});
        uint64_t live=0,peak=0; native_alloc_trace_read(live,peak); native_alloc_trace_stop();
        check("output_cap_during_inflate",py::len(decoded).num()==cap && peak<8*cap,
              {{"cap_bytes",cap},{"expanded_bytes",expanded.size()},{"compressed_bytes",compressed.size()},
               {"requested_allocation_peak",peak},{"returned_bytes",py::len(decoded).num()}});
        check("bounded_stream_not_eof",!getattr(inflater,SY("eof")).truthy() && getattr(inflater,SY("unconsumed_tail")).truthy());
        std::string result=py::bytes_data(decoded);
        while(!getattr(inflater,SY("eof")).truthy() && result.size()<=expanded.size()) {
            V tail=getattr(inflater,SY("unconsumed_tail"));
            V next=callm(inflater,SY("decompress"),Args{tail,V(double(cap))});
            if(!py::len(next).truthy()) break;
            result+=py::bytes_data(next);
        }
        check("bounded_stream_resume_exact",result==expanded);
    }
    {
        std::string raw_large="{\"units\":[";
        for(int i=0;i<4096;++i) { if(i)raw_large+=',';raw_large+="{\"id\":"+std::to_string(i)+",\"x\":1234.25,\"y\":789.5,\"hp\":100,\"card\":\"普通僵尸\"}"; }
        raw_large+="]}";
        const V payload=wire(snapshot_compress(raw_large,4));
        double ms=0; bool equal=true;
        for(int i=0;i<12;++i) {
            const auto start=std::chrono::steady_clock::now();
            const V result=pm_app::f_unpack_snapshot(Args{payload});
            ms+=std::chrono::duration<double,std::milli>(std::chrono::steady_clock::now()-start).count();
            equal=equal && py::len(py::m_get(result,V("units"))).num()==4096;
        }
        check("synthetic_snapshot_unpack",equal,{{"iterations",12},{"raw_bytes",raw_large.size()},{"mean_ms",ms/12}});
    }
    int failures=0;for(const auto& c:checks)if(!c.at("passed").get<bool>())++failures;
    J report={{"passed",failures==0},{"failures",failures},{"checks",checks},
              {"scope","Production zlib adapter and unpack_snapshot; synthetic payloads, no device or WAN acceptance"}};
    std::ofstream(argv[1],std::ios::binary)<<report.dump(2);
    std::cout<<report.dump()<<'\n';return failures?1:0;
}
