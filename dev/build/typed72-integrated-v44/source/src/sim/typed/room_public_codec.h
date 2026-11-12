#pragma once
#include "sim/typed/room_public.h"
#include "sim/typed/room_wire.h"
#include "sim/typed/room_native_pose_codec.h"
namespace pvz::typed72 {
WireObject encode_public_unit(const RoomPublishedUnit&,const WireObject& complete_resolved_card);
WireObject encode_public_terrain_cell(const RoomPublicCell&);
// This is the AI input projection of an already published row, retaining the
// immutable typed card fields. It does not resample advanced native bodies.
AiUnitView ai_public_unit(const RoomPublishedUnit&);
}
