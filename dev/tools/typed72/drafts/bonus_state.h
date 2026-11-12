#pragma once
#include "sim/typed/field.h"
#include "sim/typed/record_identity.h"
#include <array>
#include <vector>

namespace pvz::typed72 {
// Native head scans use `消亡 is True`. Numeric animation clocks, including
// numeric 1, must remain distinguishable from that terminal marker.
class EntityExpiry : public Field<double> {
public:
    void set(double value) { Field<double>::set(value); boolean_ = false; }
    void set(int value) { set(double(value)); }
    void set(bool value) { Field<double>::set(value ? 1. : 0.); boolean_ = true; }
    void set_null() { Field<double>::set_null(); boolean_ = false; }
    void erase() { Field<double>::erase(); boolean_ = false; }
    bool is_true() const { return present() && !is_null() && boolean_ && get() != 0.; }
    bool boolean_encoding() const { return boolean_; }
private:
    bool boolean_ = false;
};

struct BonusEntityState {
    Field<bool> damage_done, star_patched, head_hit;
    Field<std::vector<RecordId>> star_hits, head_hits;
    Field<double> last_guide, guide_count;
};

struct BonusPlantState {
    Field<bool> stone_placeholder, cannon_reloading;
    Field<std::vector<Field<double>>> tripea_angles;
    Field<std::vector<Field<RecordId>>> tripea_targets;
};
} // namespace pvz::typed72
