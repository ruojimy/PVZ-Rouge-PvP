// Real OS descriptor and replay persistence contract. Never opens user saves.
// fsync_replay_audit <new-output-directory>, with isolated PVP_USERDATA.
#include "pg/pg.h"
#include "core/fsutil.h"
#include "core/gil.h"
#include "data/datastore.h"
#include "sim/pvp/battle_api.h"
#include "sim/pvp/gen/pm_audit_log.h"
#include "sim/pvp/gen/pm_maps.h"
#include "ui/gen/pm_replay.h"
#include <SDL.h>
#include <nlohmann/json.hpp>
#include <cerrno>
#include <climits>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <functional>
#include <string>
#ifdef _WIN32
#include <windows.h>
#include <io.h>
#include <sys/stat.h>
#else
#include <unistd.h>
#include <fcntl.h>
#include <sys/stat.h>
#endif

using namespace pvz;
namespace {
using J=nlohmann::json;
void require(bool ok,const char* why){if(!ok)throw std::runtime_error(why);}
void expects(const char* kind,const std::function<void()>& action){
    bool caught=false;try{action();}catch(const PyError& e){caught=e.matches(kind);}
    require(caught,"Expected native Python-style I/O exception was not raised");
}
#ifdef _WIN32
struct InvalidParameterGuard {
    _invalid_parameter_handler old;
    static void ignore(const wchar_t*,const wchar_t*,const wchar_t*,unsigned int,uintptr_t){}
    InvalidParameterGuard():old(_set_thread_local_invalid_parameter_handler(ignore)){}
    ~InvalidParameterGuard(){_set_thread_local_invalid_parameter_handler(old);}
};
int parameter_calls=0;
void parameter_canary(const wchar_t*,const wchar_t*,const wchar_t*,unsigned int,uintptr_t){++parameter_calls;}
long long file_size(int fd){struct _stat64 st{};InvalidParameterGuard guard;return _fstat64(fd,&st)==0?st.st_size:-1;}
long long position(int fd){InvalidParameterGuard guard;return _lseeki64(fd,0,SEEK_CUR);}
int os_write(int fd,const char* p,int n){InvalidParameterGuard guard;return _write(fd,p,n);}
int os_read(int fd,char* p,int n){InvalidParameterGuard guard;return _read(fd,p,n);}
bool not_inherited(int fd){DWORD flags=0;return GetHandleInformation(reinterpret_cast<HANDLE>(_get_osfhandle(fd)),&flags)!=0&&!(flags&HANDLE_FLAG_INHERIT);}
size_t handle_count(){DWORD count=0;require(GetProcessHandleCount(GetCurrentProcess(),&count)!=0,"GetProcessHandleCount failed");return count;}
#else
long long file_size(int fd){struct stat st{};return ::fstat(fd,&st)==0?st.st_size:-1;}
long long position(int fd){return ::lseek(fd,0,SEEK_CUR);}
int os_write(int fd,const char* p,int n){return int(::write(fd,p,size_t(n)));}
int os_read(int fd,char* p,int n){return int(::read(fd,p,size_t(n)));}
bool not_inherited(int fd){int flags=::fcntl(fd,F_GETFD);return flags>=0&&(flags&FD_CLOEXEC);}
size_t handle_count(){size_t n=0;for(const auto& p:std::filesystem::directory_iterator("/proc/self/fd")){(void)p;++n;}return n;}
#endif
struct Held {
    V file;
    explicit Held(V value):file(std::move(value)){}
    ~Held(){try{callm(file,SY("close"),Args{});}catch(...) {}}
    int fd(){return int(callm(file,SY("fileno"),Args{}).num());}
    void write(const std::string& bytes){callm(file,SY("write"),Args{V(bytes)});}
    void flush(){callm(file,SY("flush"),Args{});}
    void seek(int n){callm(file,SY("seek"),Args{V(n)});}
    void close(){callm(file,SY("close"),Args{});}
};
V temporary(const std::filesystem::path& folder,bool del=false){
    return py::stdlib_call(SV("tempfile.NamedTemporaryFile"),Args({},{{SY("mode"),SV("w+b")},{SY("dir"),V(p8(folder))},
        {SY("prefix"),SV("同步-中文-")},{SY("suffix"),SV(".bin")},{SY("delete"),V(del)}}));
}
void sync(int fd){py::stdlib_call(SV("os.fsync"),Args{V(fd)});}
std::string read_bytes(const V& value){return value.t==V::STR?value.str():py::bytes_data(value);}
}

int main(int argc,char**argv){
    if(argc!=2)return 2;
    auto out=std::filesystem::absolute(u8p(argv[1]));
    if(std::filesystem::exists(out))return 2;
    std::filesystem::create_directories(out);
    J report={{"scope","Real OS descriptors and complete native replay; desktop process is not a power-loss test"},
        {"checks",J::array()},{"passed",false}};
    int failures=0;
    auto test=[&](const char* name,const std::function<void()>& action){
        std::string error;try{action();}catch(const std::exception& e){error=e.what();}
        report["checks"].push_back({{"name",name},{"passed",error.empty()},{"error",error}});
        failures+=!error.empty();fprintf(stderr,"%s %s %s\n",error.empty()?"PASS":"FAIL",name,error.c_str());fflush(stderr);
    };
    try{
        require(std::getenv("PVP_USERDATA")!=nullptr,"Isolated PVP_USERDATA required");
        SDL_SetMainReady();gil::init();data::set_data_dir("extract/data");pg::install_pygame();init_pvp_modules();
        test("temporary_real_fd_unicode_binary_shared_position",[&](){
            Held file(temporary(out));int fd=file.fd();std::string bytes=std::string("A\0B",3)+"中文";
            auto path=u8p(getattr(file.file,SY("name")).str());
            require(p8(path.filename()).rfind("同步-中文-",0)==0&&std::filesystem::exists(path),"Temporary Unicode prefix was not preserved");
            require(not_inherited(fd),"Temporary descriptor is inheritable");
            file.write(bytes);file.flush();sync(fd);
            require(file_size(fd)==static_cast<long long>(bytes.size()),"OS descriptor does not identify written temporary file");
            require(position(fd)==static_cast<long long>(bytes.size()),"fileno position is not shared with stdio");
            require(os_write(fd,"OS",2)==2,"OS write via temporary descriptor failed");
            file.seek(0);char buffer[64]{};int n=os_read(fd,buffer,64);
            require(n==int(bytes.size()+2)&&std::string(buffer,size_t(n))==bytes+"OS","OS read/seek does not share underlying file");
            file.seek(0);require(read_bytes(callm(file.file,SY("read"),Args{}))==bytes+"OS","stdio read differs from OS bytes");
        });
        test("two_live_files_have_distinct_real_descriptors",[&](){
            Held one(temporary(out)),two(temporary(out));require(one.fd()!=two.fd(),"Live files alias one descriptor");
            one.write("one");two.write("second");one.flush();two.flush();sync(one.fd());sync(two.fd());
            require(file_size(one.fd())==3&&file_size(two.fd())==6,"OS descriptors refer to wrong files");
        });
        test("negative_and_huge_descriptors_raise_oserror",[&](){
            expects("OSError",[&](){sync(-1);});expects("OSError",[&](){sync(INT_MAX);});
        });
        test("closed_descriptor_invalid_and_closed_methods_reject",[&](){
            Held file(temporary(out));int fd=file.fd();file.close();
            require(file_size(fd)==-1&&errno==EBADF,"Closed temporary descriptor remains open");
            expects("OSError",[&](){sync(fd);});expects("ValueError",[&](){file.fd();});
            expects("ValueError",[&](){file.write("after close");});file.close();
        });
        test("thread_local_invalid_parameter_policy_restored",[&](){
#ifdef _WIN32
            auto old=_set_thread_local_invalid_parameter_handler(parameter_canary);
            try{
                expects("OSError",[&](){sync(INT_MAX);});
                auto restored=_set_thread_local_invalid_parameter_handler(old);
                require(restored==parameter_canary&&parameter_calls==0,"fsync altered caller CRT handler or invoked it");
            }catch(...){_set_thread_local_invalid_parameter_handler(old);throw;}
#else
            expects("OSError",[&](){sync(INT_MAX);});
#endif
        });
        test("destructor_closes_descriptor",[&](){
            int fd;{V file=temporary(out);fd=int(callm(file,SY("fileno"),Args{}).num());}
            require(file_size(fd)==-1&&errno==EBADF,"Temporary destructor leaked descriptor");
        });
        test("repeated_create_close_has_no_os_handle_leak",[&](){
            {Held warm(temporary(out,true));warm.fd();}
            size_t before=handle_count();
            for(int i=0;i<128;++i){Held file(temporary(out,true));file.write("cycle");file.flush();sync(file.fd());file.close();}
            size_t after=handle_count();report["handle_count_before"]=before;report["handle_count_after"]=after;
            require(before==after,"Repeated temporary files leaked OS handles");
        });
        test("ordinary_open_file_real_fd_and_shared_position",[&](){
            Held file(py::open_file(Args{V(p8(out/u8p("普通文件.bin"))),SV("w+b")}));int fd=file.fd();
            require(not_inherited(fd),"Ordinary descriptor is inheritable");
            file.write("plain");file.flush();sync(fd);
            require(file_size(fd)==5&&position(fd)==5,"Ordinary FileObj descriptor is not its stream");
            require(os_write(fd,"OS",2)==2,"OS write on ordinary descriptor failed");file.seek(0);
            require(read_bytes(callm(file.file,SY("read"),Args{}))=="plainOS","Ordinary OS/stdio position differs");
            file.close();require(file_size(fd)==-1&&errno==EBADF,"Ordinary close leaked descriptor");
        });
        test("ordinary_modes_update_append_exclusive_and_closed",[&](){
            auto path=out/u8p("模式-中文.bin");
            {Held file(py::open_file(Args{V(p8(path)),SV("wb")}));file.write("alpha");file.flush();sync(file.fd());}
            {Held file(py::open_file(Args{V(p8(path)),SV("r+b")}));
                require(read_bytes(callm(file.file,SY("read"),Args{V(2)}))=="al","r+ read differs");
                file.write("X");file.flush();sync(file.fd());
                require(callm(file.file,SY("tell"),Args{})==V(3),"r+ read-to-write position differs");
                callm(file.file,SY("seek"),Args{V(-2),V(SEEK_END)});
                require(read_bytes(callm(file.file,SY("read"),Args{}))=="ha","SEEK_END differs");
            }
            {Held file(py::open_file(Args{V(p8(path)),SV("a+b")}));
                report["append_initial_position"]=callm(file.file,SY("tell"),Args{}).num();
                require(callm(file.file,SY("tell"),Args{})==V(5),"a+ initial position must be at EOF");
                file.seek(0);file.write("!");file.flush();sync(file.fd());file.seek(0);
                require(read_bytes(callm(file.file,SY("read"),Args{}))=="alXha!","Append overwrote instead of appending");
            }
            expects("FileExistsError",[&](){py::open_file(Args{V(p8(path)),SV("xb")});});
            {Held file(py::open_file(Args{V(p8(out/"exclusive-new.bin")),SV("x+b")}));
                file.write("created");file.flush();sync(file.fd());file.close();
                expects("ValueError",[&](){file.fd();});expects("ValueError",[&](){file.flush();});
            }
            {Held file(py::open_file(Args{V(p8(path)),SV("wb")}));file.write("truncated");}
            {Held file(py::open_file(Args{V(p8(path)),SV("rb")}));
                require(read_bytes(callm(file.file,SY("read"),Args{}))=="truncated","w did not truncate file");
                expects("OSError",[&](){file.write("readonly");});
            }
            expects("FileNotFoundError",[&](){py::open_file(Args{V(p8(out/"missing.bin")),SV("rb")});});
        });
        test("ordinary_utf8_bom_text_and_binary_line_contract",[&](){
            auto path=out/u8p("BOM-文本.txt");std::string bom("\xEF\xBB\xBF",3);
            {Held file(py::open_file(Args{V(p8(path)),SV("wb")}));file.write(bom+"alpha\r\nbeta\r\nlast");}
            {Held file(py::open_file(Args{V(p8(path)),SV("r")}));
                require(callm(file.file,SY("tell"),Args{})==V(3),"Text open did not skip UTF8 BOM");
                V first=callm(file.file,SY("readline"),Args{});
                require(first.t==V::STR&&!first.byt&&first.str()=="alpha\r\n","Text readline changed existing CRLF semantics");
                V rest=callm(file.file,SY("readlines"),Args{});
                require(rest.len()==2&&rest.idx(0)==SV("beta\n")&&rest.idx(1)==SV("last"),"Text readlines changed normalization");
                file.seek(0);require(read_bytes(callm(file.file,SY("read"),Args{V(3)}))==bom,"seek(0) unexpectedly reskipped BOM");
            }
            {Held file(py::open_file(Args{V(p8(path)),SV("rb")}));
                V first=callm(file.file,SY("readline"),Args{});
                require(first.t==V::STR&&first.byt&&read_bytes(first)==bom+"alpha\r\n","Binary readline type/bytes differ");
                V rest=callm(file.file,SY("readlines"),Args{});
                require(rest.len()==2&&rest.idx(0).byt&&read_bytes(rest.idx(0))=="beta\r\n","Binary readlines type/CRLF differ");
            }
        });
        test("ordinary_destructor_and_repeated_files_do_not_leak",[&](){
            int fd;{V file=py::open_file(Args{V(p8(out/"destructor.bin")),SV("w+b")});fd=int(callm(file,SY("fileno"),Args{}).num());}
            require(file_size(fd)==-1&&errno==EBADF,"Ordinary destructor leaked descriptor");
            size_t before=handle_count();
            for(int i=0;i<128;++i){Held file(py::open_file(Args{V(p8(out/"ordinary-cycle.bin")),SV("w+b")}));file.write("cycle");file.flush();sync(file.fd());}
            size_t after=handle_count();report["ordinary_handles_before"]=before;report["ordinary_handles_after"]=after;
            require(before==after,"Repeated ordinary files leaked OS handles");
        });
        test("actual_audit_log_spools_through_ordinary_fsync",[&](){
            V log=pm_audit_log::new_AuditLog(Args{V(2),V(4096),V(4096),V(p8(out))});
            for(int i=0;i<5;++i)callm(log,SY("append"),Args{py_dict({{SV("event"),SV("fd-audit")},{SV("index"),V(i)}})});
            V rows=py::list_it(log);require(rows.len()==5,"Spool readback lost audit entries");
            for(int i=0;i<5;++i)require(rd(rows.idx(i),SV("index"))==V(i),"Spool entry changed");
            callm(log,SY("close"),Args{});
        });
        test("actual_native_replay_export_read_and_state_verification",[&](){
            J decks={{"plant",{"plant:向日葵","plant:豌豆射手"}},{"zombie",{"zombie:脑光墓碑","zombie:普通僵尸"}}};
            BattleHandle h=battle_from_scenario({{"seed",301},{"decks",decks}});
            V deck=py::stdlib_call(SV("json.loads"),Args{V(decks.dump())});
            // Room passes its immutable MapSnapshot. NativeBattle's live map
            // contains engine annotations and is not a map-export fixture.
            V initial_map=callm(pm_maps::f_build_snapshot(Args{h.bridge,SV("家院"),V(301)}),SY("to_dict"),Args{});
            V recording=pm_replay::new_Recording(Args{h.battle,V(301),deck,V::list(),initial_map});
            try{
                for(int i=0;i<24;++i)callm(h.battle,SY("step"),Args{});
                auto replay_path=out/u8p("原生录制.pvp-replay.json");
                callm(recording,SY("export"),Args{V(p8(replay_path))});
                V data=pm_replay::f_read_recording(Args{V(p8(replay_path))});
                require(rd(data,SV("ticks"))==getattr(h.battle,SY("tick")),"Replay tick count differs");
                V playback=pm_replay::new_Playback(Args{data,h.bridge});
                try{
                    callm(playback,SY("seek"),Args{rd(data,SV("ticks"))});
                    for(int i=0;i<10&&!getattr(playback,SY("verified")).truthy();++i)
                        callm(playback,SY("update"),Args({V(0)},{{SY("max_steps"),V(1000)},{SY("budget"),V(1)}}));
                    require(!getattr(playback,SY("error")).truthy()&&getattr(playback,SY("verified")).truthy(),"Native replay final-state verification failed");
                    report["replay_bytes"]=std::filesystem::file_size(replay_path);report["replay_ticks"]=rd(data,SV("ticks")).num();
                    callm(playback,SY("close"),Args{});
                }catch(...){callm(playback,SY("close"),Args{});throw;}
                callm(h.battle,SY("close"),Args{});
            }catch(...){callm(h.battle,SY("close"),Args{});throw;}
        });
    }catch(const std::exception& e){report["fatal"]=e.what();++failures;}
    report["passed"]=failures==0;report["failures"]=failures;
    std::ofstream stream(out/"report.json",std::ios::binary);stream<<report.dump(2,' ',false,J::error_handler_t::replace)<<'\n';stream.close();
    return failures||stream.fail()?1:0;
}
