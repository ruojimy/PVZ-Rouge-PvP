#define PVZ72_ROOM_PROBE_EMBEDDED
#include "room_probe.cpp"
#include "sim/typed/replay_recording.h"
#include "sim/typed/replay_digest.h"
#include "sim/typed/command_gateway.h"
namespace {
struct ReplayFixture;
struct TypedReplayBattle:ReplayBattle {
    std::unique_ptr<ReplayFixture> fixture;
    explicit TypedReplayBattle(const J&);
    ~TypedReplayBattle();
    RoomState& room()override;RoomScheduler& scheduler()override;RoomCommands& commands()override;
    bool matches_snapshot(const std::string&,const std::string&,const std::string&)override;
};
struct TypedReplayFactory:ReplayFactory {J initial;double clock=0.;explicit TypedReplayFactory(J init):initial(std::move(init)){}std::unique_ptr<ReplayBattle> create()override{return std::make_unique<TypedReplayBattle>(initial);}double monotonic_seconds()override{const auto result=clock;clock+=.001;return result;}};
struct ReplayFixture:RoomProbe,ReplayPublication {
    J initial;RoomInputGateway gateway{inputs};std::unique_ptr<ReplayRecording> recording;bool snapshot_resources=false;J exported=nullptr;ReplayData replay_data;std::unique_ptr<TypedReplayFactory> replay_factory;std::unique_ptr<ReplayPlayer> playback;
    explicit ReplayFixture(const J& input):RoomProbe(input.value("seed",int64_t(1)),input.at("world_rules").at("width"),input.at("world_rules").value("splash",20./3.)),initial(input){
        snapshot_resources=input.value("snapshot_resources",false);J base=input;const auto cfg=base.at("world_rules");base.erase("world_rules");base.erase("snapshot_resources");configure_shooting(*this,base);battle.world_width.set(cfg.at("width"));battle.dense_planting=cfg.at("dense");battle.protection.deathmatch=cfg.at("deathmatch");rules.damaging=cfg.at("damaging").get<std::vector<std::string>>();rules.thrown=cfg.at("thrown").get<std::vector<std::string>>();rules.homing_height=cfg.at("heights").get<decltype(rules.homing_height)>();collision.unit_scale=cfg.at("scale").get<decltype(collision.unit_scale)>();initial["operations"]=J::array();for(const auto& op:input.at("operations")){if(op.at("op")=="record_setup")break;initial["operations"].push_back(op);}
    }
    WireObject replay_snapshot()override{J heroes=J::object();for(size_t i=0;i<world.heroes.size();++i)if(world.heroes[i]){const auto& h=*world.heroes[i];const auto& m=*h.frame.position.get();auto& row=heroes[std::string(seat_name(Seat(i)))];row={{"hp",pvz::py::roundn(h.frame.hp.get(),6)},{"motion",J::array({pvz::py::roundn(m.x,6),pvz::py::roundn(m.y,6),pvz::py::roundn(m.vx,6),pvz::py::roundn(m.vy,6)})},{"seq",room.players[i].sequence},{"move",world.players[i]->move}};if(snapshot_resources){row["resource"]=pvz::py::roundn(resources.accounts[i].balance,6);row["gift_ready"]=pvz::py::roundn(room.players[i].gift_ready_at,6);}}return { {"tick",room.tick},{"native_tick",world.tick},{"time",pvz::py::roundn(world.time,6)},{"heroes",heroes},{"result",replay_result()} };}
    WireObject replay_result()const override{return room.result?room_result(*room.result):J(nullptr);}
    bool extra_operation(const J& op,J& result)override{const auto name=op.at("op").get<std::string>();if(name=="record_setup"){recording=std::make_unique<ReplayRecording>(room,room_rules,scheduler,inputs,*this,*this,ReplayRecordingMetadata{{"fixture","catalog","rules"},J{{"map",J::object()},{"rules",{{"tick_rate",room_rules.tick_rate}}},{"seed",1},{"decks",J::object()},{"bans",J::array()}},"fixture-id","fixture-time",op.value("format",std::string("pvz-pvp-replay-1"))},ReplayLogLimits{3,1024,1024*1024});gateway.recording(recording.get());}
        else if(name=="record_input")result=gateway.raw(parse_seat(op.at("side")),op.at("payload"));
        else if(name=="record_generated"){const auto decoded=decode_command(op.at("payload"));result=gateway.generated(parse_seat(op.at("side")),decoded.sequence.value,decoded.payload);}
        else if(name=="record_clear")gateway.clear(parse_seat(op.at("side")));
        else if(name=="record_step")recording->step(op.value("count",int64_t(1)));
        else if(name=="record_play"){
            replay_data={};replay_data.ticks=room.tick;replay_data.tick_rate=room_rules.tick_rate;replay_data.format=recording->metadata().format;replay_data.build="fixture";replay_data.final_hash=native_replay_digest(replay_snapshot());recording->log().visit([&](const std::string& line){const J event=J::parse(line);ReplayOperation operation;operation.tick=event.at("tick");const auto kind=event.at("kind");if(kind=="input")operation.value=ReplayInput{parse_seat(event.at("side")),decode_command(event.at("payload")),event.at("error")};else if(kind=="clear")operation.value=ReplayClear{parse_seat(event.at("side"))};else operation.value=ReplayCheck{event.at("sha256")};replay_data.operations.push_back(std::move(operation));});
            if(op.value("bad_hash",false))replay_data.final_hash="incorrect";playback.reset();replay_factory=std::make_unique<TypedReplayFactory>(initial);playback=std::make_unique<ReplayPlayer>(replay_data,*replay_factory);
        }else if(name=="play_update"){if(op.contains("playing"))playback->playing=op.at("playing");if(op.contains("speed"))playback->speed=op.at("speed");playback->update(op.value("dt",0.),op.contains("max_steps")?std::optional<int64_t>(op.at("max_steps")):std::nullopt,op.contains("budget")?std::optional<double>(op.at("budget")):std::nullopt);}
        else if(name=="play_seek")playback->seek(op.at("tick"));
        else if(name=="record_close")recording->close();
        else return RoomProbe::extra_operation(op,result);return true;
    }
    void extra_snapshot(J& row)override{RoomProbe::extra_snapshot(row);if(recording){J events=J::array();if(!recording->log().closed())recording->log().visit([&](const std::string& line){events.push_back(J::parse(line));});row["recording"]={{"events",events},{"error",recording->error()},{"closed",recording->log().closed()},{"snapshot",replay_snapshot()}};}if(playback){auto& fixture=*static_cast<TypedReplayBattle*>(playback->battle())->fixture;row["playback"]={{"tick",fixture.room.tick},{"cursor",playback->cursor()},{"error",playback->error},{"verified",playback->verified},{"playing",playback->playing},{"credit",playback->credit},{"target",playback->target?J(*playback->target):J(nullptr)},{"snapshot",fixture.replay_snapshot()}};}}
};
TypedReplayBattle::TypedReplayBattle(const J& input):fixture(std::make_unique<ReplayFixture>(input)){fixture->operations(input.at("operations"));fixture->states.clear();}
TypedReplayBattle::~TypedReplayBattle()=default;
RoomState& TypedReplayBattle::room(){return fixture->room;}RoomScheduler& TypedReplayBattle::scheduler(){return fixture->scheduler;}RoomCommands& TypedReplayBattle::commands(){return fixture->inputs;}
bool TypedReplayBattle::matches_snapshot(const std::string& expected,const std::string& format,const std::string& build){return replay_snapshot_matches(fixture->replay_snapshot(),expected,format,build);}
J lifecycle(const J& input){ReplayFixture probe(input);probe.operations(input.at("operations"));return probe.states;}
}
int main(int argc,char** argv){try{if(argc!=3)throw std::invalid_argument("expected input output");std::ifstream in(argv[1],std::ios::binary);std::ofstream out(argv[2],std::ios::binary);std::string line;while(std::getline(in,line))if(!line.empty())out<<lifecycle(J::parse(line)).dump()<<'\n';return in.bad()||!out?2:0;}catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 2;}}
