#include "sim/typed/replay_recording.h"
#include "sim/typed/replay_digest.h"
#include "sim/typed/command_codec.h"
#include <array>
#include <charconv>
#include <cstdio>
#include <ctime>
#include <fstream>
#include <random>
#include <system_error>
#ifdef _WIN32
#define NOMINMAX
#include <Windows.h>
#include <io.h>
#else
#include <unistd.h>
#include <fcntl.h>
#endif
namespace pvz::typed72 {
namespace {
bool truth(const WireObject& v){if(v.is_null())return false;if(v.is_boolean())return v.get<bool>();if(v.is_number())return v.get<double>()!=0.;if(v.is_string())return !v.get_ref<const std::string&>().empty();return !v.empty();}
std::string unique_id(){std::random_device source;std::string out;out.reserve(32);static constexpr char hex[]="0123456789abcdef";for(int i=0;i<16;++i){const auto value=source()&255;out.push_back(hex[value>>4]);out.push_back(hex[value&15]);}return out;}
std::string created(){const auto now=std::time(nullptr);std::tm value{};
#ifdef _WIN32
    localtime_s(&value,&now);
#else
    localtime_r(&now,&value);
#endif
    std::array<char,32> result{};if(!std::strftime(result.data(),result.size(),"%Y-%m-%d %H:%M:%S",&value))throw std::runtime_error("recording timestamp failed");return result.data();}
struct DurableFile {
    FILE* file=nullptr;
    explicit DurableFile(const std::filesystem::path& path){
#ifdef _WIN32
        _wfopen_s(&file,path.c_str(),L"wbx");
#else
        file=std::fopen(path.c_str(),"wbx");
#endif
        if(!file)throw std::system_error(errno,std::generic_category(),"create recording file");}
    ~DurableFile(){if(file)std::fclose(file);}
    void write(std::string_view text){if(!text.empty()&&std::fwrite(text.data(),1,text.size(),file)!=text.size())throw std::system_error(errno,std::generic_category(),"write recording file");}
    void finish(){if(std::fflush(file))throw std::system_error(errno,std::generic_category(),"flush recording file");
#ifdef _WIN32
        if(_commit(_fileno(file)))throw std::system_error(errno,std::generic_category(),"sync recording file");
#else
        if(::fsync(::fileno(file)))throw std::system_error(errno,std::generic_category(),"sync recording file");
#endif
        auto* done=file;file=nullptr;if(std::fclose(done))throw std::system_error(errno,std::generic_category(),"close recording file");}
};
void replace(const std::filesystem::path& from,const std::filesystem::path& to){
#ifdef _WIN32
    if(!MoveFileExW(from.c_str(),to.c_str(),MOVEFILE_REPLACE_EXISTING|MOVEFILE_WRITE_THROUGH))throw std::system_error(int(GetLastError()),std::system_category(),"replace recording file");
#else
    std::filesystem::rename(from,to);const int parent=::open(to.parent_path().c_str(),O_RDONLY|O_DIRECTORY);if(parent<0)throw std::system_error(errno,std::generic_category(),"open recording directory");const int result=::fsync(parent),code=errno;::close(parent);if(result)throw std::system_error(code,std::generic_category(),"sync recording directory");
#endif
}
void remove_pending(const std::filesystem::path& path){std::error_code error;std::filesystem::remove(path,error);}
}
ReplayJournal::ReplayJournal(ReplayLogLimits limits,std::filesystem::path directory):limits_(limits),directory_(std::move(directory)){if(!limits.entries||!limits.buffer_bytes||!limits.record_bytes)throw std::invalid_argument("audit limits must be positive");tail_.reserve(limits.entries);}
ReplayJournal::~ReplayJournal(){try{close();}catch(...){}}
void ReplayJournal::check_open()const{if(closed_)throw ReplayJournalError("审计日志已关闭");}
[[noreturn]]void ReplayJournal::fail(const char* action,const std::exception& error){const auto* system=dynamic_cast<const std::system_error*>(&error);error_=std::string("审计日志")+action+"失败（"+(system?"OSError":"ValueError");if(system)error_+=" / errno "+std::to_string(system->code().value());error_+="）；已保留记录，对局必须暂停";throw ReplayJournalError(error_);}
std::filesystem::path ReplayJournal::segment(size_t index)const{std::array<char,40> text{};std::snprintf(text.data(),text.size(),"part-%08llu.jsonl",static_cast<unsigned long long>(index));return storage_/text.data();}
void ReplayJournal::append(const WireObject& event){check_open();if(!error_.empty())throw ReplayJournalError(error_);std::string line;try{line=native_replay_canonical(event,false);line+='\n';}catch(const std::exception& e){fail("编码",e);}if(line.size()>limits_.record_bytes)fail("记录过大",std::invalid_argument("record exceeds limit"));bytes_+=line.size();tail_.push_back(std::move(line));++count_;if(tail_.size()>=limits_.entries||bytes_>=limits_.buffer_bytes)flush();}
void ReplayJournal::flush(){if(tail_.empty())return;std::filesystem::path pending;try{if(storage_.empty()){const auto parent=directory_.empty()?std::filesystem::temp_directory_path():std::filesystem::absolute(directory_);for(int retry=0;retry<16;++retry){auto candidate=parent/("pvz-pvp-audit-"+unique_id());if(std::filesystem::create_directory(candidate)){storage_=std::move(candidate);break;}}if(storage_.empty())throw std::runtime_error("cannot allocate audit directory");}const auto destination=segment(segments_);pending=destination;pending+=".pending";{DurableFile file(pending);file.write(std::to_string(tail_.size())+"\n");for(const auto& line:tail_)file.write(line);file.finish();}replace(pending,destination);}catch(const std::exception& e){if(!pending.empty())remove_pending(pending);fail("写盘",e);}++segments_;spooled_+=tail_.size();tail_.clear();bytes_=0;}
void ReplayJournal::visit(const std::function<void(const std::string&)>& visitor){
    check_open();const size_t segments=segments_;const auto tail=tail_;
    for(size_t i=0;i<segments;++i){std::ifstream file;size_t count=0;
        try{file.open(segment(i),std::ios::binary);if(!file)throw std::system_error(errno,std::generic_category(),"read audit segment");std::string header;if(!std::getline(file,header))throw std::invalid_argument("missing segment header");const auto parsed=std::from_chars(header.data(),header.data()+header.size(),count);if(parsed.ec!=std::errc{}||parsed.ptr!=header.data()+header.size()||!count||count>limits_.entries)throw std::invalid_argument("invalid segment count");}catch(const std::exception& e){fail("读取",e);}
        for(size_t n=0;n<count;++n){std::string line;try{if(!std::getline(file,line)||line.size()+1>limits_.record_bytes)throw std::invalid_argument("incomplete or oversized segment");const auto checked=WireObject::parse(line);}catch(const std::exception& e){fail("读取",e);}visitor(line);}
        try{if(file.peek()!=std::char_traits<char>::eof())throw std::invalid_argument("unexpected segment contents");if(file.bad())throw std::runtime_error("audit segment read failed");}catch(const std::exception& e){fail("读取",e);}
    }
    for(const auto& line:tail)visitor(line);
}
void ReplayJournal::close(){if(closed_)return;if(!storage_.empty()){for(size_t i=0;i<segments_;++i)std::filesystem::remove(segment(i));std::filesystem::remove(storage_);}tail_.clear();bytes_=0;closed_=true;}
void export_replay_journal(const std::filesystem::path& destination,const WireObject& metadata,ReplayJournal& log){if(!metadata.is_object())throw std::invalid_argument("recording metadata must be an object");const auto path=std::filesystem::absolute(destination);std::filesystem::create_directories(path.parent_path());auto pending=path;pending+="."+unique_id()+".pending";try{DurableFile stream(pending);std::string initial=native_replay_canonical(metadata,false);initial.pop_back();stream.write(initial);stream.write(metadata.empty()?"\"operations\":[":",\"operations\":[");bool first=true;log.visit([&](const std::string& line){if(!first)stream.write(",");stream.write(line);first=false;});stream.write("]}");stream.finish();replace(pending,path);}catch(...){remove_pending(pending);throw;}}
ReplayRecording::ReplayRecording(RoomState& room,const RoomRules& rules,RoomScheduler& scheduler,RoomCommands& commands,RoomServices& services,ReplayPublication& publication,ReplayRecordingMetadata metadata,ReplayLogLimits limits,std::filesystem::path directory):room_(room),rules_(rules),scheduler_(scheduler),commands_(commands),services_(services),publication_(publication),metadata_(std::move(metadata)),log_(limits,std::move(directory)){if(metadata_.id.empty())metadata_.id=unique_id();if(metadata_.created.empty())metadata_.created=created();}
void ReplayRecording::append(WireObject event){if(!error_.empty())return;try{WireObject full={{"tick",room_.tick}};for(const auto& [key,value]:event.items())full[key]=value;log_.append(full);}catch(const std::exception& e){error_="回放记录失败："+std::string(e.what());}}
std::string ReplayRecording::input(Seat seat,const WireObject& raw){return input(seat,raw,decode_command(raw));}
std::string ReplayRecording::input(Seat seat,const WireObject& raw,const CommandAttempt& decoded){auto clean=recorded_replay_input(raw,metadata_.format);const auto result=commands_.apply(seat,decoded);append({{"kind","input"},{"side",seat_name(seat)},{"payload",std::move(clean)},{"error",result}});return result;}
void ReplayRecording::clear(Seat seat){commands_.clear(seat);if(!stepping_)append({{"kind","clear"},{"side",seat_name(seat)}});}
void ReplayRecording::step(int64_t count){stepping_=true;try{for(int64_t i=0;i<count;++i){room_.capture_intermediate=i<count-1;const auto before=room_.tick;scheduler_.step(1);if(before==room_.tick)break;if(room_.tick%(rules_.tick_rate*5)==0)append({{"kind","check"},{"sha256",native_replay_digest(publication_.replay_snapshot())}});}}catch(...){stepping_=false;room_.capture_intermediate=room_.defer_capture=false;services_.capture_deferred(false);throw;}stepping_=false;room_.capture_intermediate=room_.defer_capture=false;services_.capture_deferred(false);}
std::filesystem::path ReplayRecording::export_to(const std::filesystem::path& path,std::optional<WireObject> result){if(!error_.empty())throw std::invalid_argument(error_);WireObject metadata={{"format",metadata_.format},{"build",metadata_.identity.build},{"catalog_hash",metadata_.identity.catalog_hash},{"rules_hash",metadata_.identity.rules_hash},{"id",metadata_.id},{"created",metadata_.created},{"initial",metadata_.initial},{"ticks",room_.tick},{"result",result&&truth(*result)?*result:publication_.replay_result()},{"final_hash",native_replay_digest(publication_.replay_snapshot())}};export_replay_journal(path,metadata,log_);return path;}
} // namespace pvz::typed72
