#pragma once
#include "sim/typed/ai_tactical_base.h"
#include "sim/typed/ai_firing.h"
#include "sim/typed/room_public_terrain.h"
namespace pvz::typed72 {
struct AiPlantPlacementFrame {
    std::span<const std::string> deck,secrets;
    std::span<const AiObservedTarget> empty_supports;
    const RoomPublicTerrain& terrain;
    AiFiring& firing;
};
struct AiPlantPlacementState {
    std::map<std::pair<int64_t,int64_t>,double> dead_spots;
    struct BadGround {std::optional<std::string> pot,top;double lift;};
    std::vector<BadGround> bad_pot_ground;
};
// Concrete shipped place_at MRO: r19 -> r18 -> r11 -> PvP65 -> v6.
// All deployments use the same validated tactical preview/input machinery;
// the public terrain and existing supports only guide that decision.
class AiPlantPlacement {
public:
    AiPlantPlacement(AiTacticalState& state,AiPlantPlacementState& places,AiFiringFailures& failures):state_(state),places_(places),failures_(failures),base_(state){}
    std::string place_at(AiTacticalContext&,const AiPlantPlacementFrame&,const std::string&,Point,int facing);
    std::string try_deploy(AiTacticalContext&,const AiPlantPlacementFrame&,const std::string&,Point,std::optional<std::string> grave={},int facing=1);
    static const RoomPublicCell* ground(const AiTacticalContext&,const AiPlantPlacementFrame&,Point);
private:
    AiTacticalState& state_;AiPlantPlacementState& places_;AiFiringFailures& failures_;AiTacticalBase base_;
    std::optional<int> direction(AiTacticalContext&,const AiPlantPlacementFrame&,const std::string&,Point,int);
    std::string place18(AiTacticalContext&,const AiPlantPlacementFrame&,const std::string&,Point,int);
    std::string place11(AiTacticalContext&,const AiPlantPlacementFrame&,const std::string&,Point,int);
    std::string place65(AiTacticalContext&,const AiPlantPlacementFrame&,const std::string&,Point,int);
    std::string place6(AiTacticalContext&,const AiPlantPlacementFrame&,const std::string&,Point,int);
};
}
