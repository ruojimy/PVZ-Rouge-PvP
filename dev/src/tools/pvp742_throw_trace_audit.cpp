#include "core/trace.h"
#include "core/alloc.h"
#include <map>
#include <new>
#include <limits>
#include <cstdio>
#include <cstring>
#include <stdexcept>
int main(int argc,char** argv){
 if(argc!=2)return 2;pvz::install_crash_handler();FILE* file=std::fopen(argv[1],"w+b");if(!file)return 2;
 bool missing=false,allocation=false;const auto before=pvz::native_small_allocator_stats();
 try{std::map<int,int> values;values.at(42);}catch(const std::out_of_range& e){missing=true;std::fprintf(file,"expected map fingerprint: %s\n",e.what());pvz::print_last_cpp_throw(file);}
 volatile size_t requested=std::numeric_limits<size_t>::max();
 try{void* p=::operator new(requested);::operator delete(p);}catch(const std::bad_alloc& e){allocation=true;std::fprintf(file,"expected oversized allocation: %s\n",e.what());pvz::print_last_cpp_throw(file);}
 const auto after=pvz::native_small_allocator_stats();
 std::fprintf(file,"allocator failure count=%llu size=%llu\n",static_cast<unsigned long long>(after.allocation_failures),static_cast<unsigned long long>(after.last_failure_bytes));
 std::fflush(file);std::rewind(file);char output[16384]{};std::fread(output,1,sizeof(output)-1,file);std::fclose(file);pvz::release_crash_reserve();
 bool stack=true;
#ifdef _WIN32
 stack=std::strstr(output,"C++ original throw stack (before unwinding)")!=nullptr;
#endif
 const bool passed=missing&&allocation&&stack&&after.allocation_failures>before.allocation_failures&&after.last_failure_bytes==requested;
 std::printf("throw_trace_and_allocation_request=%s\n",passed?"PASS":"FAIL");return passed?0:1;
}
