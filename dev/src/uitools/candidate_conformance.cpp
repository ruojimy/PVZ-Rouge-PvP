#include "sim/pvp/shim/pm_native_multiworker.h"
#include <cstdio>
#include <fstream>
#include <iterator>

using namespace pvz;
int main(int argc,char** argv) {
    if(argc!=2){fprintf(stderr,"usage: candidate_conformance reference.json\n");return 2;}
    try {
        std::ifstream input(argv[1],std::ios::binary);
        if(!input){fprintf(stderr,"reference file missing\n");return 2;}
        std::string text((std::istreambuf_iterator<char>(input)),std::istreambuf_iterator<char>());
        V cases=py::json_loads(V(text));size_t failed=0,index=0;
        for(auto& item:cases.items()) {
            V candidate=pm_native_multiworker::new_CandidateIndex(Args{V::none(),V(128),item.get(V("cell"))});
            V actual=callm(candidate,Sym("gather"),Args{item.get(V("targets")),item.get(V("boxes")),item.get(V("width")),item.get(V("wrap"))});
            if(actual!=item.get(V("expected"))) {++failed;fprintf(stderr,"MISMATCH case %zu\n",index);}
            ++index;
        }
        printf("CANDIDATE CONFORMANCE: %zu cases, %zu mismatches\n",index,failed);
        return !index?2:(failed?1:0);
    } catch(const std::exception& e){fprintf(stderr,"ERROR: %s\n",e.what());return 2;}
}
