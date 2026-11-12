// Typed, serial C++ box gathering for native_candidates. Outputs remain in
// original target order and the exact periodic box predicate.
#include "sim/pvp/shim/pm_native_multiworker.h"
#include "core/pymath.h"
#include <chrono>
#include <cmath>
#include <cstdlib>
#include <limits>

namespace pvz::pm_native_multiworker {
namespace {
struct CandidateIndex : PyObj {
    V telemetry=py_dict({{V("gathers"),V(0)}, {V("queries"),V(0)},
        {V("targets"),V(0)}, {V("candidates"),V(0)},
        {V("brute_pairs"),V(0)}, {V("gather_ms"),V(0)}});
    V jobs, chunk=V(128), cell=V(96), parallel_min_pairs=V(100000);
    const char* type_name() const override { return "CandidateIndex"; }
    V* slot(Sym name) override {
        if(name==Sym("telemetry"))return &telemetry;
        if(name==Sym("jobs"))return &jobs;
        if(name==Sym("chunk"))return &chunk;
        if(name==Sym("cell"))return &cell;
        if(name==Sym("parallel_min_pairs"))return &parallel_min_pairs;
        return nullptr;
    }
    static int64_t bucket(double x,double size) {
        double result=std::floor(x/size);
        if(!std::isfinite(result)||result<=double(INT64_MIN)||result>=double(INT64_MAX))
            throw PyError("ValueError","candidate coordinate is not finite or is out of range");
        return int64_t(result);
    }
    V gather(const Args& a) {
        auto started=std::chrono::steady_clock::now();
        V targets=py::iter_list(a.get(0,Sym("targets"),nullptr,"gather"));
        V boxes=py::iter_list(a.get(1,Sym("boxes"),nullptr,"gather"));
        double width=a.get(2,Sym("width"),nullptr,"gather").num();
        bool wrap=a.get(3,Sym("wrap"),nullptr,"gather").truthy();
        double size=std::max(cell.num(),1.0);
        if(wrap && width==0)throw PyError("ZeroDivisionError","float modulo");
        struct Point { double x,y; int64_t bin; };
        std::vector<Point> points;points.reserve(targets.len());
        for(auto& row:targets.items()) {
            double x=rd(row,V(0)).num(),y=rd(row,V(1)).num();
            points.push_back({x,y,bucket(wrap?py::mod(x,width):x,size)});
        }
        V output=V::list();size_t candidate_count=0;
        for(auto& box:boxes.items()) {
            double qx=rd(box,V(0)).num(),qy=rd(box,V(1)).num();
            double left=rd(box,V(2)).num(),right=rd(box,V(3)).num();
            double up=rd(box,V(4)).num(),down=rd(box,V(5)).num();
            int64_t lo=bucket(qx-left,size),hi=bucket(qx+right,size);
            bool full_wrap=wrap && left+right>=width, crosses_seam=false;
            if(wrap && !full_wrap) {
                // The last bucket can be shorter than cell. Normalize the
                // physical interval by the real width before choosing bins;
                // modulo ceil(width/cell) misses the short seam interval.
                double lower=py::mod(qx-left,width),upper=py::mod(qx+right,width);
                lo=bucket(lower,size);hi=bucket(upper,size);
                crosses_seam=lower>upper;
            }
            V found=V::list();
            for(size_t index=0;index<points.size();++index) {
                auto& p=points[index];
                bool admitted=p.bin>=lo && p.bin<=hi;
                if(wrap) {
                    admitted=full_wrap || (crosses_seam
                        ? p.bin>=lo || p.bin<=hi : p.bin>=lo && p.bin<=hi);
                }
                if(!admitted)continue;
                double dx=p.x-qx;
                if(wrap)dx=py::mod(dx+width/2.0,width)-width/2.0;
                double dy=p.y-qy;
                if(-left<=dx && dx<=right && -up<=dy && dy<=down)found.append(V(index));
            }
            candidate_count+=found.len();output.append(found);
        }
        auto add=[&](const char* key,double value){telemetry.at(V(key))=V(telemetry.get(V(key)).num()+value);};
        add("gathers",1);add("queries",double(boxes.len()));add("targets",double(points.size()));
        add("candidates",double(candidate_count));add("brute_pairs",double(boxes.len())*double(points.size()));
        add("gather_ms",std::chrono::duration<double,std::milli>(std::chrono::steady_clock::now()-started).count());
        return output;
    }
    V method(Sym name) override {
        if(name!=Sym("gather"))return V();
        auto self=std::static_pointer_cast<CandidateIndex>(shared_from_this());
        return V::func([self](const Args& a){return self->gather(a);});
    }
};
}
V new_CandidateIndex(const Args& a) {
    auto p=std::make_shared<CandidateIndex>();
    V none=V::none(),default_chunk(128),default_cell(96),default_pairs(100000);
    p->jobs=a.get(0,Sym("jobs"),&none);
    p->chunk=a.get(1,Sym("chunk"),&default_chunk);
    if(const char* value=std::getenv("PVP_CANDIDATE_CHUNK"))p->chunk=py::int_(V(value));
    p->cell=a.get(2,Sym("cell"),&default_cell);
    p->parallel_min_pairs=a.get(3,Sym("parallel_min_pairs"),&none);
    if(p->parallel_min_pairs.is_none()) {
        const char* value=std::getenv("PVP_CANDIDATE_PARALLEL_MIN_PAIRS");
        p->parallel_min_pairs=value?py::int_(V(value)):default_pairs;
    }
    return V::inst(p);
}
V cls_CandidateIndex() {
    static V cls=py::class_value(V("CandidateIndex"),new_CandidateIndex);
    return cls;
}
}
