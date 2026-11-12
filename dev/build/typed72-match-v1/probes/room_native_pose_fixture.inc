// Test-only cold loader, deliberately separate from the publication codec.
AttackIdentity pose_attack(const J& raw){
    if(raw.is_null())return AttackIdentity::null();
    if(raw.is_string())return AttackIdentity::literal(raw.get<std::string>());
    if(raw.is_boolean())return AttackIdentity::boolean(raw.get<bool>());
    if(raw.is_number_integer())return AttackIdentity::integer(raw.get<int64_t>());
    if(!raw.is_array()&&!(raw.is_object()&&raw.size()==1&&raw.contains("tuple")))throw std::invalid_argument("invalid fixture attack identity");
    std::vector<AttackIdentity> values;for(const auto& child:raw.is_array()?raw:raw.at("tuple"))values.push_back(pose_attack(child));return AttackIdentity::sequence(values,raw.is_array());
}
void read_pose(HeroState& h,const J& raw){
    h=HeroState{};
#define READ(n,k) read_field(h.frame.n,raw,k);
    PVZ72_HERO_NUMBERS(READ) PVZ72_HERO_BOOLEANS(READ) PVZ72_HERO_STRINGS(READ)
#undef READ
    if(raw.contains("玩家位置")){const auto& m=raw.at("玩家位置");if(m.is_null())h.frame.position.set_null();else h.frame.position.set(std::make_shared<Motion>(Motion{m[0],m[1],m[2],m[3]}));}
    if(raw.contains("秘籍")){const auto& names=raw.at("秘籍");if(names.is_null())h.frame.secrets.set_null();else h.frame.secrets.set(std::make_shared<std::vector<std::string>>(names.get<std::vector<std::string>>()));}
    read_field(h.max_hp,raw,"_pvp_max_hp");read_field(h.ice,raw,"_pvp_ice");read_field(h.butter,raw,"_pvp_butter");read_field(h.stun,raw,"_pvp_stun");read_field(h.last_damage,raw,"_pvp_last_damage");read_field(h.regen_progress,raw,"_pvp_regen_progress");read_field(h.pea_angle,raw,"_pvp_pea_angle");
    read_field(h.native_ticks,raw,"native_ticks");read_field(h.landing_result,raw,"landing_result");read_field(h.balloon_hp,raw,"_pvp_balloon_hp");read_field(h.cold_until,raw,"_pvp_cold_until");read_field(h.previous_hp,raw,"_pvp_previous_hp");read_field(h.water_damage_clock,raw,"_pvp_water_damage_clock");read_field(h.masochist_ready,raw,"_pvp_masochist_ready");read_field(h.sturdy_down,raw,"_pvp_sturdy_down");
    read_field(h.floating_body,raw,"_pvp_floating_body");read_field(h.rally_before,raw,"_pvp_rally_before");read_field(h.rally_checked,raw,"_pvp_rally_checked");read_field(h.rally_eligible,raw,"_pvp_rally_eligible");
    if(raw.contains("_pvp_seat"))h.actual_seat=seat(raw.at("_pvp_seat"));
    if(raw.contains("_pvp_owner")||raw.contains("_pvp_id")){h.avatar_source=std::make_shared<AttackSource>();read_field(h.avatar_source->owner,raw,"_pvp_owner");read_field(h.avatar_source->id,raw,"_pvp_id");}
    if(raw.contains("_pvp_launch_attack"))h.launch_attack=pose_attack(raw.at("_pvp_launch_attack"));
    if(raw.contains("_pvp_poison")){
        const auto& raw_poison=raw.at("_pvp_poison");if(raw_poison.is_null())h.poison.set_null();else{
            auto p=std::make_shared<PoisonState>();read_field(p->level,raw_poison,"level");read_field(p->until,raw_poison,"until");read_field(p->next,raw_poison,"next");
            if(raw_poison.contains("owner")){if(raw_poison.at("owner").is_null())p->owner.set_null();else p->owner.set(seat(raw_poison.at("owner")));}
            if(raw_poison.contains("layers")){if(raw_poison.at("layers").is_null())p->layers.set_null();else{auto layers=std::make_shared<PoisonLayers>();for(const auto& [key,value]:raw_poison.at("layers").items())layers->emplace_back(std::stoi(key),value.is_null()?nullptr:std::make_shared<PoisonLayer>(PoisonLayer{value.at("until"),value.at("next"),seat(value.at("owner"))}));p->layers.set(std::move(layers));}}
            h.poison.set(std::move(p));
        }
    }
}
