#pragma once
#include "sim/typed/replay_codec.h"
#include <filesystem>
#include <functional>
namespace pvz::typed72 {
class ReplayJournalError:public std::runtime_error {public:using std::runtime_error::runtime_error;};
struct ReplayLogLimits {size_t entries=4096,buffer_bytes=2*1024*1024,record_bytes=1024*1024;};
// Native bounded tail and immutable disk segments. No per-event index grows
// with match length; exports scan one line at a time.
class ReplayJournal {
public:
    explicit ReplayJournal(ReplayLogLimits={},std::filesystem::path directory={});
    ~ReplayJournal();
    ReplayJournal(const ReplayJournal&)=delete;ReplayJournal& operator=(const ReplayJournal&)=delete;
    void append(const WireObject&);
    void visit(const std::function<void(const std::string&)>&);
    void close();
    size_t size()const{return count_;}
    size_t buffered_count()const{return tail_.size();}
    size_t buffered_bytes()const{return bytes_;}
    size_t spooled_count()const{return spooled_;}
    const std::filesystem::path& storage_path()const{return storage_;}
    const std::string& error()const{return error_;}
    bool closed()const{return closed_;}
private:
    ReplayLogLimits limits_;std::filesystem::path directory_,storage_;
    std::vector<std::string> tail_;size_t bytes_=0,count_=0,spooled_=0,segments_=0;
    bool closed_=false;std::string error_;
    std::filesystem::path segment(size_t)const;
    void flush();void check_open()const;
    [[noreturn]]void fail(const char* action,const std::exception&);
};
class ReplayPublication {
public:
    virtual ~ReplayPublication()=default;
    // Full current public snapshot, generated only on explicit checkpoint or
    // export. It must serialize the same typed world, never a shadow battle.
    virtual WireObject replay_snapshot()=0;
    virtual WireObject replay_result()const=0;
};
struct ReplayRecordingMetadata {ReplayIdentity identity;WireObject initial;std::string id,created;std::string format="pvz-pvp-replay-2";};
class ReplayRecording {
public:
    ReplayRecording(RoomState&,const RoomRules&,RoomScheduler&,RoomCommands&,RoomServices&,ReplayPublication&,ReplayRecordingMetadata,ReplayLogLimits={},std::filesystem::path directory={});
    std::string input(Seat,const WireObject& raw);
    std::string input(Seat,const WireObject& raw,const CommandAttempt& decoded);
    void clear(Seat);
    void step(int64_t steps=1);
    std::filesystem::path export_to(const std::filesystem::path&,std::optional<WireObject> result={});
    void close(){log_.close();}
    const std::string& error()const{return error_;}
    ReplayJournal& log(){return log_;}
    const ReplayRecordingMetadata& metadata()const{return metadata_;}
private:
    RoomState& room_;const RoomRules& rules_;RoomScheduler& scheduler_;RoomCommands& commands_;RoomServices& services_;ReplayPublication& publication_;
    ReplayRecordingMetadata metadata_;ReplayJournal log_;std::string error_;bool stepping_=false;
    void append(WireObject);
};
// Same bounded durable writer used by recording exports, exposed for a room
// journal's independent validation without requiring a mock battle clock.
void export_replay_journal(const std::filesystem::path&,const WireObject& metadata,ReplayJournal&);
} // namespace pvz::typed72
