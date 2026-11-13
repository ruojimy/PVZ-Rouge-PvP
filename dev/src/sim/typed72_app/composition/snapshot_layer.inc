    // ---- typed NativeBattle.snapshot() (room view; native_frame comes from the canvas) ----
    // MATCH_SNAPSHOTS=<path> writes {"rt":n,"snapshot":{...}} after construction (-1) and each room step.
    std::unique_ptr<std::ofstream> snapshot_out=[]{const char* s=std::getenv("MATCH_SNAPSHOTS");return s?std::make_unique<std::ofstream>(s,std::ios::binary):std::unique_ptr<std::ofstream>{};}();
    template<class T> static J opt_json(const Field<T>& f){return f.is_null()?J(nullptr):J(f.get());}
    // ColdCard mirrors the V card dict field for field (cold_card_fields.h is generated from it).
    static J card_json(const ColdCard& c){
        J j=J::object();
#define S(n) j[#n]=c.n;
        PVZ72_COLD_REQUIRED_STRINGS(S) PVZ72_COLD_REQUIRED_NUMBERS(S) PVZ72_COLD_REQUIRED_FLAGS(S)
#undef S
#define O(n) if(c.n.present())j[#n]=opt_json(c.n);
        PVZ72_COLD_OPTIONAL_STRINGS(O) PVZ72_COLD_OPTIONAL_NUMBERS(O) PVZ72_COLD_OPTIONAL_FLAGS(O)
#undef O
        if(c.slow.present())j["slow"]=c.slow.is_null()?J(nullptr):std::visit([](auto v){return J(v);},c.slow.get());
        if(c.targets.present())j["targets"]=opt_json(c.targets);
        if(c.native_secret_names.present())j["native_secret_names"]=opt_json(c.native_secret_names);
        return j;
    }
    J placement_state_json()const{
        J plants=J::array();
        for(const auto& p:*battle.plant_roster){
            const std::string content=p->source.content.present()&&!p->source.content.is_null()?p->source.content.get():std::string{};
            if(content=="抓人草触手")continue;
            const std::string copy=p->copy_card.present()&&!p->copy_card.is_null()?p->copy_card.get():std::string{};
            const bool shell=p->kind=="南瓜头"||content=="阳光藤蔓"||content=="忧郁藤蔓"||content=="抓人草"||(p->kind=="模仿者"&&copy=="plant:抓人草");
            J item={{"植物",shell?std::string("南瓜头"):p->kind},{"坐标",{p->cell.y,p->cell.x}}};
            if(content=="水盆")item["basin"]=true;
            if(p->sleep.present())item["睡觉"]=true;
            if(content=="阳光藤蔓"||content=="忧郁藤蔓"||content=="抓人草")item["vine"]=true;
            const bool flying=content=="旋转芜菁"||content=="芦笋战机"||(p->kind=="模仿者"&&(copy=="plant:旋转芜菁"||copy=="plant:芦笋战机"));
            if(flying)item["air"]=true;
            plants.push_back(std::move(item));
        }
        return {{"version",1},{"plants",plants},{"secrets",*tick_state.native_secrets},{"empty_blocks",battle.terrain.empty_blocks},{"spike_cost",deployment.spike_cost.or_missing(100.)}};
    }
    J battle_seats=J::array();  // NativeBattle.seats (cold)
    bool team_mode=false;
    // pvp native_audio.NativeAudio: bounded presentation sound events (never touches RNG).
    std::deque<J> audio_events;int64_t audio_sequence=0;std::map<std::pair<std::string,std::optional<int64_t>>,int64_t> audio_last;
    void audio_emit(const std::string& name,std::optional<Point> position,std::optional<int64_t> at_tick={}){
        if(name.empty()||name.size()>64*4||name.find_first_of("/\\.:")!=std::string::npos)return;
        J point=nullptr;std::optional<int64_t> column;
        if(position&&std::isfinite(position->x)&&std::isfinite(position->y)){
            point=J::array({pvz::py::roundn(position->x,1),pvz::py::roundn(position->y,1)});
            column=int64_t(point[0].get<double>()/(battle.runtime.tile*4.));
        }
        const int64_t tick=at_tick.value_or(battle.heroes.tick);const auto bucket=std::pair{name,column};
        const auto found=audio_last.find(bucket);if(tick-(found==audio_last.end()?-1000:found->second)<20)return;
        audio_last[bucket]=tick;
        if(audio_last.size()>512)std::erase_if(audio_last,[&](const auto& item){return !(tick-item.second<500);});
        ++audio_sequence;
        audio_events.push_back({{"id",audio_sequence},{"tick",tick},{"name",name},{"position",point}});
        if(audio_events.size()>128)audio_events.pop_front();
    }
    // Native sounds played before journal row `mark` (Sound::journal_mark <= mark); all by default.
    void drain_sounds(size_t mark=size_t(-1)){
        auto& sounds=battle.runtime.sounds;size_t n=0;
        for(;n<sounds.size()&&sounds[n].journal_mark<=mark;++n)audio_emit(sounds[n].name,sounds[n].spatial?std::optional<Point>(sounds[n].position):std::nullopt,sounds[n].tick>=0?std::optional<int64_t>(sounds[n].tick):std::nullopt);
        sounds.erase(sounds.begin(),sounds.begin()+std::ptrdiff_t(n));
    }
    void audio_event(const J& row,size_t mark=size_t(-1),std::optional<Point> source_at={}){
        static const std::map<std::string,std::string> sounds{{"shovel","铲子"},{"teleport","取走"},{"ghost_activated","三叶草"},{"ghost_exploded","辣椒"},
            {"cannon_fire","加农炮"},{"dance_started","跳舞"},{"deathmatch","来袭1"},{"hook_fired","投掷"},{"hook_hit","取走"},{"bone_thrown","投掷"},
            {"bone_grave","出坟墓"},{"bone_gravebuster","吃坟墓"},{"tentacle_hit","吃1"},{"lettuce_freeze","冰冻"}};
        const auto kind=row.value("event",std::string{});std::string sound;
        if(const auto i=sounds.find(kind);i!=sounds.end())sound=i->second;
        if(kind=="deploy")sound=row.value("side",std::string{})=="plant"?"种植1":"出坟墓";
        if(kind=="income")sound="捡阳光";
        if(sound.empty())return;
        drain_sounds(mark);
        std::optional<Point> at;if(row.contains("x")&&row.contains("y")&&row["x"].is_number()&&row["y"].is_number())at=Point{row["x"].get<double>(),row["y"].get<double>()};
        // NativeAudio.emit(sound, None) places an unpositioned sound at the current source's 位置;
        // only an event delivered as it happens has that source (journal rows flush later).
        if(!at)at=source_at;
        if(!at&&mark==size_t(-1)&&battle.runtime.sound_source)at=battle.runtime.sound_source();
        audio_emit(sound,at);
    }
    J audio_snapshot(){
        drain_sounds();const int64_t tick=battle.heroes.tick;
        while(!audio_events.empty()&&tick-audio_events.front()["tick"].get<int64_t>()>500)audio_events.pop_front();
        J events=J::array();for(const auto& e:audio_events)events.push_back(e);
        return {{"sequence",audio_sequence},{"events",events}};
    }
    // NativeBattle.snapshot: pvp70 = dict(projectiles=deepcopy(content.pvp70.shots)): the hook and
    // bone shot dicts (pvp70_content.py:449,506) with the keys each shot actually carries.
    J pvp70_projectiles()const{
        J out=J::array();
        const auto seat_text=[](const Field<Seat>& f)->J{if(!f.present())return J();if(f.is_null())return nullptr;return std::string(seat_name(f.get()));};
        for(const auto& s:battle.content_projectiles.shots){
            J row={{"x",s->motion.x},{"y",s->motion.y},{"vx",s->motion.vx},{"vy",s->motion.vy},{"age",s->age},{"direction",s->direction}};
            const auto put=[&](const char* k,J v){if(!v.is_discarded())row[k]=std::move(v);};
            const auto text_field=[](const Field<std::string>& f)->J{if(!f.present())return J(J::value_t::discarded);if(f.is_null())return nullptr;return f.get();};
            const auto bool_field=[](const Field<bool>& f)->J{if(!f.present())return J(J::value_t::discarded);if(f.is_null())return nullptr;return f.get();};
            put("kind",text_field(s->kind));put("source",text_field(s->source));put("target",text_field(s->target));
            if(s->owner.present())row["owner"]=seat_text(s->owner);if(s->seat.present())row["seat"]=seat_text(s->seat);
            if(s->cell.present())row["cell"]=s->cell.is_null()?J(nullptr):J::array({s->cell.get().y,s->cell.get().x});
            put("anchor",bool_field(s->anchor));put("defused",bool_field(s->defused));put("instant",bool_field(s->instant));
            out.push_back(std::move(row));
        }
        return out;
    }    // NativeBattle.snapshot, when zsecrets.enabled: public pickups (black armour keeps its art),
    // live effects and the remaining last-stand seconds per seat (zombie_secrets.py:652).
    J zsecrets_json(double now)const{
        static const std::map<std::string,std::string> art{{"黑路障僵尸","黑路障"},{"黑铁桶僵尸","黑铁桶"}};
        J pickups=J::array();
        for(const auto& i:zruntime.pickups){
            const std::string name=i.kind.empty()?i.name:i.kind;
            std::string asset=name;if(i.black)if(const auto a=art.find(*i.black);a!=art.end())asset=a->second;
            pickups.push_back({{"id",i.id},{"name",name},{"asset",asset},{"x",i.position.x},{"y",i.position.y}});
        }
        J effects=J::array();
        for(const auto& e:zruntime.effects)if(e.until>now)
            effects.push_back({{"kind",e.kind},{"seat",std::string(seat_name(e.seat))},{"target",e.target},{"x",e.x},{"y",e.y},{"tx",e.tx},{"ty",e.ty},{"born",e.born},{"until",e.until}});
        J stands=J::object();
        for(const auto seat:battle.heroes.last_stand_order)if(const auto& until=battle.heroes.last_stand[seat_index(seat)])stands[std::string(seat_name(seat))]=std::max(0.,*until-now);
        return {{"pickups",pickups},{"effects",effects},{"last_stand",stands}};
    }    J snapshot_players()const{
        J out=players_json();const double tile=battle.runtime.tile;
        for(const auto seat:seated_seats){
            const auto i=seat_index(seat);const std::string s(seat_name(seat));auto& row=out[s];
            const auto& p=*world.players[i];
            for(const char* k:{"id","side","owner","current_owner","original_owner","native_side","source_entity","root_source","root_original_owner"})row[k]=s;
            row["side"]=std::string(seat_name(team_of(seat)));row["native_side"]=std::string(seat_name(team_of(seat)));
            row["parent_entity"]=nullptr;row["parent_attack"]=nullptr;
            row["w"]=tile*.8;row["h"]=tile*1.9;
            row["deck"]=deployment.players[i].deck;row["secrets"]=p.secrets;
            row["input"]={{"move",p.move}};
            row["native_pose"]=published_pose[i].is_null()?frame_json(battle.heroes.hero(seat)):published_pose[i];
            // NativeBattle.select_grave sets players[seat]["selected_grave"] once (解除封印).
            if(const auto& g=battle.protection.selected_grave[i])row["selected_grave"]=*g;
            for(const char* k:{"control_until","tail_cd","knock_until","knock_vx"})if(!row.contains(k))row[k]=0;
            // Team seats carry their team as owner/side identity; the seat stays the id.
            const std::string team(seat_name(team_of(seat)));
            for(const char* k:{"owner","current_owner","original_owner","source_entity","root_source","root_original_owner"})row[k]=team;
            if(deployment.players[i].last_copy_card)row["last_copy_card"]=*deployment.players[i].last_copy_card;
            if(seat!=team_of(seat))row["seat"]=s;
            if(room.players[i].gift_ready_at>0.)row["gift_ready_at"]=room.players[i].gift_ready_at;
            // teleport_hero writes player["teleport_ready_at"] on a successful teleport (time+cooldown>0).
            if(room.players[i].teleport_ready_at>0.)row["teleport_ready_at"]=room.players[i].teleport_ready_at;
            // NativeBattle._deploy (ranked 黄金蓓蕾) writes player["collect_locked_until"]=max(old, time+lock);
            // the key then stays in the V player dict for the rest of the match.
            if(room.players[i].collect_locked_until>0.)row["collect_locked_until"]=room.players[i].collect_locked_until;
            if(cannon_aim_written[i]){const auto& aim=room.players[i].cannon_aim;row["cannon_aim"]=aim?J::array({aim->y,aim->x}):J(nullptr);}
            if(std::find(tick_state.present.begin(),tick_state.present.end(),seat)==tick_state.present.end())row["absent"]=true;
        }
        return out;
    }
    // Simulation.events (the last <=128 emitted events, inputs are log-only); newest last.
    J recent_events(size_t n)const{
        std::vector<const J*> rows;
        for(auto i=log.rbegin();i!=log.rend()&&rows.size()<n;++i)if(i->value("event",std::string{})!="input")rows.push_back(&*i);
        J out=J::array();for(auto i=rows.rbegin();i!=rows.rend();++i)out.push_back(**i);return out;
    }
    J snapshot_json(bool include_frame=true){
        J units=J::array();
        for(const auto& u:published.units){
            J card=nullptr;
            try{card=card_json(placement_view.unit_card(u.original_owner,u.card->id));}catch(const std::exception&){card=J(u.card->id);}
            units.push_back(encode_public_unit(u,card));
        }
        // Battle.events: emitted events only (inputs are log-only), the last 30.
        J events=recent_events(30);
        J resources=J::array();
        for(const auto& r:this->resources.records()){
            J row={{"id",r.id},{"side",std::string(seat_name(r.side))},{"amount",r.amount},{"x",r.position.x},{"y",r.position.y},{"born",r.born},{"source",r.source}};
            if(r.shared.present())row["shared"]=opt_json(r.shared);
            if(r.coin.present())row["coin"]=opt_json(r.coin);
            resources.push_back(std::move(row));
        }
        J tentacles=J::array();
        for(const auto& p:*battle.plant_roster){
            if(!p->source.content.present()||p->source.content.is_null()||p->source.content.get()!="抓人草触手")continue;
            if(!(p->hp.present()&&!p->hp.is_null()&&p->hp.get()>0.)||p->dead.present())continue;
            const auto& c=p->content70;
            tentacles.push_back({{"id",opt_json(p->source.id)},{"parent",c.parent.present()?opt_json(c.parent):J(nullptr)},{"phase",c.head_phase.present()?opt_json(c.head_phase):J(nullptr)},
                {"clock",c.head_clock.present()?opt_json(c.head_clock):J(nullptr)},{"target",c.head_target.present()?opt_json(c.head_target):J(nullptr)}});
        }
        J result=nullptr;
        if(room.result){result={{"winner",room.result->winner==RoomWinner::plant?"plant":room.result->winner==RoomWinner::zombie?"zombie":"draw"},{"reason",room.result->reason==RoomResultReason::hero_death?"hero_death":room.result->reason==RoomResultReason::waves_cleared?"waves_cleared":"surrender"},{"tick",room.result->tick}};
            scripted_result_fields(result,*room.result);}
        const double now=world.time;
        J out={{"tick",room.tick},{"time",now},{"deathmatch",room.deathmatch},{"result",result},{"audit_error",""},
                {"players",snapshot_players()},{"units",units},{"projectiles",J::array()},{"resources",resources},
                {"command",commands.shared==PathMode::follow_hero?"follow":"attack"},{"events",events},{"terrain_revision",published.terrain.revision},
                {"engine","original-native-250hz"},{"native_tick",battle.heroes.tick},
                {"native_placement_state",placement_state_json()},
                {"audio",audio_snapshot()},{"pvp70",{{"projectiles",pvp70_projectiles()},{"tentacles",tentacles}}}};
        if(include_frame)out["native_frame"]=canvas.frame_json(canvas.frames.frame());
        if(hero_flags.shared)out["rally_point"]={{"x",hero_flags.shared->x},{"y",hero_flags.shared->y}};
        if(zsecrets.enabled())out["zsecrets"]=zsecrets_json(now);
        if(battle.mode!=MatchMode::duel){
            const char* mode=battle.mode==MatchMode::duo?"duo":battle.mode==MatchMode::coop?"coop":"pve";
            out["mode"]=mode;out["seats"]=battle_seats;
            J requests=J::object();
            for(const auto& r:room.surrender_requests)if(r&&r->expires>now)requests[std::string(seat_name(team_of(r->seat)))]={{"id",r->id},{"seat",std::string(seat_name(r->seat))},{"expires",r->expires}};
            if(team_mode)out["surrender_requests"]=requests;
            J revive=J::object(),fallen=J::array();
            for(const auto s:seated_seats){const auto i=seat_index(s);
                if(room.revive[i]>0.)revive[std::string(seat_name(s))]=pvz::py::roundn(room.revive[i]/4.,3);
                if(room.down_since[i])fallen.push_back(std::string(seat_name(s)));}
            std::sort(fallen.begin(),fallen.end());
            J team={{"revive",revive},{"fallen",fallen},{"coins",this->resources.coins}};
            if(director.bound()){
                team["waves"]=director.waves_snapshot(now);
                if(director.coop_cycle())team["daylight"]=director.daylight_snapshot(now,battle.placement.day=="黑天");
            }
            out["team"]=team;
        }
        if(battle.mode==MatchMode::duo){out["commands"]=seat_commands();out["rally_points"]=seat_rallies();}
        return out;
    }
    void write_snapshot(int rt){if(snapshot_out)(*snapshot_out)<<J{{"rt",rt},{"snapshot",snapshot_json()}}.dump(-1,' ',false,J::error_handler_t::replace)<<'\n';}
    // ---- end snapshot layer ----
