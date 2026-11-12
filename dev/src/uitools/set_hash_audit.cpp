// Runtime set-index correctness and actual occupied-bucket clustering.
// No SDL window, userdata, game world or renderer is initialized.
// set_hash_audit <report.json> [width=249] [height=195]
#include "sim/pvp/pvprt.h"
#include "core/gil.h"
#include "core/fsutil.h"
#include <nlohmann/json.hpp>
#include <algorithm>
#include <chrono>
#include <fstream>
#include <functional>
#include <set>
#include <string>
#include <vector>

using namespace pvz;
using json=nlohmann::json;
namespace {
void check(bool yes,const char* message){if(!yes)throw std::runtime_error(message);}
V point(int x,int y){return V::tuple({V(x),V(y)});}
double now(){return std::chrono::duration<double>(std::chrono::steady_clock::now().time_since_epoch()).count();}
void index_integrity(const V& set) {
    const Box* b=set.box.get();
    if(!b->kidx_valid)return;
    std::vector<unsigned char> occurrences(b->items.size());
    size_t empty=0;
    for(uint32_t slot:b->kidx) {
        if(!slot){++empty;continue;}
        check(slot<=b->items.size(),"Set index points outside item vector");
        check(!occurrences[slot-1],"Set item has duplicate index slots");
        occurrences[slot-1]=1;
    }
    check(empty>0,"Set index has no terminating empty bucket");
    for(unsigned char count:occurrences)check(count==1,"Set item missing from index");
}
size_t longest_cluster(const V& set) {
    const auto& table=set.box->kidx;
    auto empty=std::find(table.begin(),table.end(),0u);
    check(empty!=table.end(),"Cannot inspect a full hash table");
    size_t start=size_t(empty-table.begin()),run=0,longest=0;
    for(size_t offset=1;offset<=table.size();++offset) {
        if(table[(start+offset)%table.size()])longest=std::max(longest,++run);else run=0;
    }
    return longest;
}
}
int main(int argc,char**argv) {
    if(argc<2)return 2;
    int width=argc>2?std::stoi(argv[2]):249,height=argc>3?std::stoi(argv[3]):195;
    if(width<1 || height<1 || width*int64_t(height)>1000000)return 2;
    json report;bool passed=false;
    try {
        gil::init();
        double start=now();V pixels=V::set();
        for(int y=0;y<height;++y)for(int x=0;x<width;++x)py::set_add(pixels,point(x,y));
        double build=now()-start;
        check(pixels.len()==size_t(width*height),"Coordinate set lost or duplicated pixels");
        index_integrity(pixels);
        check(pixels.box->kidx_valid,"Large coordinate set did not build an index");
        size_t capacity=pixels.box->kidx.size(),cluster=longest_cluster(pixels);
        check(cluster<2000,"Large coordinate set has pathological actual bucket clustering");
        std::vector<size_t> old_home(capacity);
        for(int y=0;y<height;++y)for(int x=0;x<width;++x)++old_home[py_hash(point(x,y))&(capacity-1)];
        size_t old_unique=0,old_max=0;
        for(size_t count:old_home){old_unique+=count!=0;old_max=std::max(old_max,count);}

        start=now();
        for(int y=0;y<height;++y)for(int x=0;x<width;++x)check(pixels.contains(point(x,y)),"Inserted coordinate is not found");
        for(int y=0;y<height;++y)check(!pixels.contains(point(width+1,y)),"Absent coordinate reported present");
        double lookup=now()-start;
        start=now();size_t removed=0;
        for(int y=0;y<height;++y)for(int x=0;x<width;++x)if((x+y)%2==0) {
            check(pixels.set_erase(point(x,y)),"Indexed removal failed");++removed;
        }
        index_integrity(pixels);
        for(int y=0;y<height;++y)for(int x=0;x<width;++x)
            check(pixels.contains(point(x,y))==((x+y)%2!=0),"Removal corrupted another coordinate lookup");
        double erase=now()-start;
        check(pixels.len()+removed==size_t(width*height),"Removal count mismatch");
        start=now();std::set<int64_t> popped;size_t pop_count=pixels.len();
        while(pixels.truthy()) {
            V item=py::pop(pixels);int x=int(item.idx(0).num()),y=int(item.idx(1).num());
            check((x+y)%2!=0,"Pop returned a previously removed key");
            check(popped.insert(int64_t(y)*width+x).second,"Pop returned a duplicate key");
            check(!pixels.contains(item),"Popped key remains in set");
            if(popped.size()%4096==0)index_integrity(pixels);
        }
        check(popped.size()==pop_count,"Pop failed to exhaust all remaining keys");
        double pop=now()-start;

        // Test indexed numeric equality, not only the small-set linear fallback.
        V numbers=V::set();for(int i=0;i<80;++i)py::set_add(numbers,V(i));
        py::set_add(numbers,V(false));py::set_add(numbers,V(-0.0));py::set_add(numbers,V(true));
        check(numbers.len()==80,"BOOL/zero numeric duplicates changed set cardinality");
        check(numbers.contains(V(false)) && numbers.contains(V(-0.0)) && numbers.contains(V(true)),"Numeric-equal key lookup failed");
        check(py_hash(V(false))==py_hash(V(0.0)) && py_hash(V(-0.0))==py_hash(V(0.0)) && py_hash(V(true))==py_hash(V(1.0)),"Public equal-key hashes disagree");
        check(py_hash(V(17.0))==std::hash<double>()(17.0),"The public numeric hash was changed");
        check(numbers.set_erase(V(-0.0)) && !numbers.contains(V(false)),"-0 removal did not remove equal false/zero key");
        check(numbers.set_erase(V(true)) && !numbers.contains(V(1.0)),"True removal did not remove equal numeric one");
        index_integrity(numbers);

        // Lookup cannot reorder items; removal retains the previous swap-last rule.
        V ordered=V::set();for(int i=0;i<64;++i)py::set_add(ordered,point(i,7));
        std::vector<V> previous=ordered.box->items;
        for(const V& item:previous)check(ordered.contains(item),"Lookup failed in order fixture");
        for(size_t i=0;i<previous.size();++i)check(py_eq(previous[i],ordered.box->items[i]),"Lookup changed vector order");
        check(ordered.set_erase(point(17,7)),"Swap-last removal failed");
        previous[17]=previous.back();previous.pop_back();
        for(size_t i=0;i<previous.size();++i)check(py_eq(previous[i],ordered.box->items[i]),"Removal changed existing swap-last semantics");
        py::set_add(ordered,point(999,7));check(py_eq(ordered.box->items.back(),point(999,7)),"Insertion did not append to item vector");
        index_integrity(ordered);
        report={{"passed",true},{"keys",width*height},{"grid",{width,height}},
            {"actual_index_capacity",capacity},{"actual_longest_occupied_cluster",cluster},
            {"unmixed_start_buckets",old_unique},{"unmixed_max_start_bucket",old_max},
            {"seconds",{{"insert",build},{"lookup",lookup},{"erase_and_verify",erase},{"pop",pop}}},
            {"removed",removed},{"popped",pop_count},{"numeric_equal_keys",true},
            {"public_hash_unchanged",true},{"vector_order_semantics_unchanged",true}};
        passed=true;
    }catch(const std::exception& e){report={{"passed",false},{"error",e.what()}};}
    std::ofstream output(u8p(argv[1]),std::ios::binary);output<<report.dump(2);output.close();
    printf("%s\n",report.dump().c_str());return passed && !output.fail()?0:1;
}
