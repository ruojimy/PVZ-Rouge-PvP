#pragma once
#include "sim/typed/room_native_pose.h"
#include "sim/typed/room_wire.h"
namespace pvz::typed72 {
WireObject encode_attack_identity(const AttackIdentity&);
WireObject encode_native_pose(const RoomNativePose&);
}
