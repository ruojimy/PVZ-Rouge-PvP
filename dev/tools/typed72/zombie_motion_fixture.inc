    // Cold admission and observation of the mobile source slice.
    ZombieNavigation navigation;
    ZombieMotion mobile{battle,navigation,indexes,*this,*this};
    ZombieActionState action_state;
    ZombieActions zombies{battle,mobile,navigation,action_state,*this,*this,*this,static_cast<EntityRegionBindings&>(*this)};
    bool observe_actions=false;
    uint64_t next_flat=10000;
    bool observe_motion=false;
    std::optional<Point> rally;
    void add_entity(std::string name,double facing,Motion pos)override{ShootingProbe::add_entity(std::move(name),facing,pos);}
    void ordinary(size_t index,double direction,double amount)override{ordinary_damage(index,direction,amount);}
    void surface(size_t index,double direction,double amount)override{surface_damage(index,direction,amount);}
    void request_ladder(const ZombieRef& u)override{render_log.push_back(J::array({"ladder",index(u)}));}
    std::optional<Point> rally_destination(const ZombieRef&)override{return rally;}
    // This base fixture compares the raw native layer. The scripted
    // admission fixture overrides all four installed guard bindings.
    bool hold_dance()override{return false;}
    bool defer_dancer(Point,double,int64_t)override{return false;}
    bool hold_sled()override{return false;}
    bool hold_giant()override{return false;}
    void zombie_gate(size_t i)override{render_log.push_back(J::array({"zombie",i}));}
    void line(Point start,Point end)override{render_log.push_back(J::array({"line",{start.x,start.y},{end.x,end.y}}));}
    void crop(std::string name,Point p,bool mirror,Point size)override{render_log.push_back(J::array({"crop",name,{p.x,p.y},mirror,{size.x,size.y}}));}
    uint64_t flat_sprite(std::string name,Point size,bool mirror)override{
        render_log.push_back(J::array({"flat",name,{size.x,size.y},mirror}));return ++next_flat;
    }
    void ash_zombie(size_t i)override{ShootingProbe::ash_zombie(i);}
    void summon_zombie(std::string name,Motion p,double facing)override{
        auto& w=battle.runtime;const auto hero=world.globals.position.get();
        ZombieSpawnInput in;in.map_cols=battle.terrain.cols();in.map_rows=battle.terrain.rows();
        in.player={hero->x,hero->y};in.screen_height=navigation.screen_height;in.bosses=navigation.bosses;
        const auto& mode=world.globals.mode.get();
        if(mode=="抽奖模式")in.mode=NativeSpawnMode::lottery;
        else if(mode=="测试模式")in.mode=NativeSpawnMode::test;
        else if(mode=="末日模式")in.mode=NativeSpawnMode::doomsday;
        else if(mode=="无尽模式")in.mode=NativeSpawnMode::endless;
        else if(mode=="极难模式")in.mode=NativeSpawnMode::extreme;
        auto u=std::make_shared<CombatZombie>();ids.push_back(battle.add_zombie(u));units.push_back(u);
        populate_original_zombie(w,*u,std::move(name),p,facing,in);
    }
    void motion_setup(const J& op) {
        observe_motion=true;
        for(size_t i=0;i<navigation.flood.size();++i) {
            auto& field=*navigation.flood[i].field;field.clear();
            for(const auto& row:op.at("flood").at(i))for(const auto& value:row)field.push_back(value.get<int>());
            if(field.size()!=size_t(battle.terrain.rows()*battle.terrain.cols()))throw std::invalid_argument("fixture flood grid size");
            navigation.chase_fields[i]=navigation.flood[i].field;
        }
        navigation.scripted=op.value("scripted",false);navigation.director_available=op.value("director",true);
        navigation.target_plant=op.value("target",-1);navigation.hold_plant=op.value("hold",0.);
        navigation.wave=op.value("wave",0.);navigation.running=op.value("running",1.);
        navigation.screen_height=op.value("height",576.);navigation.water_sprite="水";
        navigation.ladder_count=op.value("ladders",0);navigation.ladder_cooldown=op.value("ladder_cd",0);
        navigation.cactus_secret=op.value("cactus",false);navigation.charm_secret=op.value("charm_secret",false);
        navigation.bosses=op.value("bosses",std::vector<std::string>{});
        indexes.ladders=op.value("ladder_cols",std::vector<int64_t>{});
        rally.reset();if(op.contains("rally"))rally=Point{op.at("rally").at(0),op.at("rally").at(1)};
    }
    void motion_unit(CombatZombie& u,const J& fields) {
        auto& n=u.native;auto& b=u.body;
        #define READ(nm,k) read(fields,k,n.nm);
        PVZ72_ZOMBIE_NATIVE_NUMBERS(READ)
        #undef READ
        read(fields,"分兵",n.split);read(fields,"大蒜",n.garlic);
        read(fields,"入水",b.in_water);read(fields,"跳舞",b.dancing);read(fields,"狂暴",b.berserk);
        read(fields,"黄油",b.butter);read(fields,"冰冻",b.ice);read(fields,"眩晕",b.stun);read(fields,"大小",b.size);
        read(fields,"_pvp_variant",u.source.variant);read(fields,"_pvp_content",u.source.content);
        read(fields,"_pvp_card",u.protection.card);read(fields,"_pvp_no_attack",u.patch.no_attack);
        read(fields,"_pvp_bite_plant",u.patch.bite_plant);read(fields,"_pvp_no_hero_attack",u.source.no_hero_attack);
        read(fields,"_pvp_max_hp",u.max_hp);
        read(fields,"__pvz_sb_zombie_observed_max_hp",u.patch.observed_max_hp);
        read(fields,"魅惑",u.source.charmed);
        read(fields,"灰烬",b.ash);read(fields,"气球",b.balloon);read(fields,"撑杆",b.pole_vault);
        read(fields,"出土",n.emerged);read(fields,"别消失",n.linger);read(fields,"旋转",n.rotation);read(fields,"离开",n.leaving);
        read(fields,"手持动画",n.hand_animation);read(fields,"篮球",u.protection.basketball);
        read_point(fields,"出场初位置",n.entry_start);read_point(fields,"出场末位置",n.entry_end);read_point(fields,"绳初位置",n.rope_start);
        if(fields.contains("防具"))b.armor=fields.at("防具");
        if(fields.contains("受伤"))b.hurt=fields.at("受伤");
        if(fields.contains("方向"))b.facing=fields.at("方向");
        if(fields.contains("手持受伤"))b.hand_hurt=fields.at("手持受伤");
        if(fields.contains("僵尸"))b.kind=fields.at("僵尸");
        if(fields.contains("手持"))b.hand=fields.at("手持");
        if(fields.contains("手持血量"))b.hand_hp=fields.at("手持血量");
        if(fields.contains("血量"))b.hp=fields.at("血量");
        if(fields.contains("位置"))b.motion.replace(motion(fields.at("位置")));
    }
    void snapshot_motion(J& row) const {
        if(!observe_motion)return;
        auto& records=row["motion_units"]=J::array();
        for(const auto& u:units) {
            J j=J::object();const auto& n=u->native;
            write(j,"坚持分兵",n.divide);write(j,"分兵",n.split);write(j,"再出场",n.respawn);
            write(j,"出场",n.entry);write(j,"炸音",n.explosion_sound);write(j,"中场",n.midfield);
            write(j,"苏醒",n.wake);write(j,"憋气",n.breath);write(j,"跳跃cd",n.jump_cd);
            write(j,"啃咬",n.biting);write(j,"移速",n.move_speed);write(j,"大蒜",n.garlic);
            write(j,"入水",u->body.in_water);write(j,"跳舞",u->body.dancing);
            write(j,"_pvp_bite_plant",u->patch.bite_plant);write(j,"_pvp_no_attack",u->patch.no_attack);
            for(const auto& [key,field]:{std::pair{"出场初位置",&n.entry_start},std::pair{"出场末位置",&n.entry_end}})
                if(field->present())j[key]={field->get().x,field->get().y};
            records.push_back(std::move(j));
        }
        if(!observe_actions)return;
        auto& actions=row["action_units"]=J::array();
        for(const auto& u:units){
            J j=J::object();const auto& n=u->native;
            #define WRITE(nm,k) write(j,k,n.nm);
            PVZ72_ZOMBIE_NATIVE_NUMBERS(WRITE)
            #undef WRITE
            write(j,"出土",n.emerged);write(j,"离开",n.leaving);write(j,"旋转",n.rotation);write(j,"别消失",n.linger);
            write(j,"手持动画",n.hand_animation);write(j,"篮球",u->protection.basketball);
            if(u->patch.miner_rally.present()){const auto p=u->patch.miner_rally.get();j["_pvp_miner_rally"]={p.x,p.y};}
            actions.push_back(std::move(j));
        }
        row["coin_count"]=action_state.coin_count;auto& coins=row["coins"]=J::array();
        for(const auto& coin:action_state.coins)coins.push_back({coin.age,as_json(coin.motion),coin.cooldown,coin.kind});
    }
