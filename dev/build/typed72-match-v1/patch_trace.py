from pathlib import Path
p=Path('match_probe.cpp');t=p.read_text(encoding='utf8')
def sub(a,b):
    global t
    assert t.count(a)==1,a
    t=t.replace(a,b)
sub('#include <cstdio>\n','''#include <cstdio>
#include <windows.h>
#include <dbghelp.h>
#pragma comment(lib,"dbghelp.lib")
namespace {
// Debug aid only (MATCH_TRACE=1): prints the throw site of the first C++ exceptions.
int trace_budget=6;
LONG WINAPI trace_throw(EXCEPTION_POINTERS* info){
    if(info->ExceptionRecord->ExceptionCode!=0xE06D7363||trace_budget<=0)return EXCEPTION_CONTINUE_SEARCH;
    --trace_budget;void* frames[32];const auto n=RtlCaptureStackBackTrace(1,32,frames,nullptr);const auto process=GetCurrentProcess();
    char buffer[sizeof(SYMBOL_INFO)+256];auto* symbol=reinterpret_cast<SYMBOL_INFO*>(buffer);symbol->SizeOfStruct=sizeof(SYMBOL_INFO);symbol->MaxNameLen=255;
    std::fprintf(stderr,"--- throw\\n");
    for(USHORT i=0;i<n;++i){DWORD64 d=0;DWORD dl=0;IMAGEHLP_LINE64 line{};line.SizeOfStruct=sizeof(line);
        if(SymFromAddr(process,DWORD64(frames[i]),&d,symbol)){const bool has=SymGetLineFromAddr64(process,DWORD64(frames[i]),&dl,&line);
            std::fprintf(stderr,"%s %s:%lu\\n",symbol->Name,has?line.FileName:"?",has?line.LineNumber:0ul);}}
    return EXCEPTION_CONTINUE_SEARCH;
}
void install_trace(){if(!std::getenv("MATCH_TRACE"))return;SymSetOptions(SYMOPT_LOAD_LINES);SymInitialize(GetCurrentProcess(),nullptr,TRUE);AddVectoredExceptionHandler(1,trace_throw);}
}
''')
sub('        if(argc!=6)throw','        install_trace();\n        if(argc!=6)throw')
# Same placeholder rule as battle_record_jsonl.
sub('''payload["seq"]=++seqs[seat_index(seat)];\n''','''payload["seq"]=++seqs[seat_index(seat)];
                for(auto item=payload.begin();item!=payload.end();++item){
                    if(*item=="$grave"){J found=nullptr;for(const auto& u:match.published.units)if(u.card&&u.card->behavior=="grave"&&u.hp>0.&&u.side==Seat::zombie)found=u.id;*item=found;}
                    else if(*item=="$sun"){J found=nullptr;for(const auto& r:match.resources.records())if(r.side==seat){found=r.id;break;}*item=found;}
                }
''')
p.write_text(t,encoding='utf8')
p=Path('CMakeLists.txt');t=p.read_text(encoding='utf8')
sub('typed72-integrated-v5/build/Release/pvztyped72.lib','typed72-integrated-v5/build-zi/Release/pvztyped72.lib')
sub('target_compile_options(match72 PRIVATE /utf-8 /fp:precise /W1 /MP1 /FS /bigobj)','target_compile_options(match72 PRIVATE /utf-8 /fp:precise /W1 /MP1 /FS /bigobj /Zi)\ntarget_link_options(match72 PRIVATE /DEBUG)')
p.write_text(t,encoding='utf8')
p=Path('../typed72-integrated-v5/CMakeLists.txt');t=p.read_text(encoding='utf8')
sub('target_compile_options(pvztyped72 PUBLIC /utf-8 /fp:precise /W3 /MP1 /FS /bigobj)','target_compile_options(pvztyped72 PUBLIC /utf-8 /fp:precise /W3 /MP1 /FS /bigobj)\nif(PVZ_ZI)\n  target_compile_options(pvztyped72 PUBLIC /Zi)\nendif()')
p.write_text(t,encoding='utf8')
