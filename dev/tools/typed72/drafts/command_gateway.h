#pragma once
#include "sim/typed/replay_recording.h"
#include "sim/typed/command_codec.h"
namespace pvz::typed72 {
// The live composition routes human, network and AI input through this one
// concrete gateway. Playback deliberately applies already-recorded commands
// directly, so replaying cannot recursively record another replay.
class RoomInputGateway {
public:
    explicit RoomInputGateway(RoomCommands& commands):commands_(commands){}
    void recording(ReplayRecording* value){recording_=value;}
    std::string raw(Seat seat,const WireObject& input){return raw(seat,input,decode_command(input));}
    std::string raw(Seat seat,const WireObject& input,const CommandAttempt& decoded){return recording_?recording_->input(seat,input,decoded):commands_.apply(seat,decoded);}
    std::string generated(Seat seat,int64_t sequence,CommandPayload payload){
        CommandAttempt attempt{true,{InputFieldState::value,sequence},std::move(payload)};
        if(!recording_)return commands_.apply(seat,attempt);
        return recording_->input(seat,encode_generated_command(sequence,attempt.payload),attempt);
    }
    void clear(Seat seat){if(recording_)recording_->clear(seat);else commands_.clear(seat);}
private:RoomCommands& commands_;ReplayRecording* recording_=nullptr;
};
} // namespace pvz::typed72
