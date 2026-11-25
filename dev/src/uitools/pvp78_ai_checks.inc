namespace {
J ai78_checks(){
    J rows=J::array();
    rows.push_back(scenario("ai78.native_drafts",[](){
        expect(ranked_fast_heads::configured().has_value(),"no packaged model");
        auto bridge=pm_native_bridge::C_NativeBridge::m_from_marshaled(Args{});
        J out;
        for(bool duo:{false,true}){
            auto rules=py::copy(pm_catalog::RULES);
            pm_pvp61_ranked::f_apply_options(Args{rules,V(true),V(false)});
            auto room=pm_room::new_Room(Args{bridge,rules});
            if(duo)callm(room,SY("set_mode"),Args{V("duo")});
            else{
                auto terrain=pm_maps::f_build_snapshot(Args({bridge,V("家院"),V(78830000)},{{SY("weather"),V("clear")}}));
                setattr(room,SY("map"),terrain);setattr(room,SY("map_id"),V("家院"));setattr(room,SY("seed"),V(78830000));
            }
            callm(room,SY("_start_bans"),Args{});
            J choices=J::array();std::set<std::string> seats;
            while(true){
                const auto action=callm(room,SY("_draft_action"),Args{});if(!action.truthy())break;
                const auto side=rd(action,V("side")),seat=py::m_get(action,V("seat"),side);
                const auto selected=ranked_fast_heads::choose(room,action);
                expect(selected.has_value(),"native head unavailable "+dump(action));seats.insert(py_str(seat));
                auto result=callm(room,rd(action,V("kind"))==V("ban")?SY("_ban"):SY("_pick"),Args{side,*selected,V(false),seat});
                expect(!result.truthy(),"illegal action "+dump(action)+": "+py_str(result));
                choices.push_back(J::parse(dump(*selected)));expect(choices.size()<100,"draft loop");
            }
            expect(seats.size()==(duo?4:2),"missing seats");
            out[duo?"duo":"ranked"]=choices;
        }
        return out;
    }));
    rows.push_back(scenario("ai78.advice",[](){
        auto h=battle_from_scenario({{"seed",784}});
        auto screen=callm(pg::display_module(),SY("set_mode"),Args{V::tuple({V(960),V(640)})});
        auto app=pm_app::new_Application(Args{pg::pygame_module(),screen,h.bridge});
        callm(app,SY("create_offline_host"),Args{});
        auto room=getattr(app,SY("room"));auto view=py::dict_of(getattr(app,SY("view")));
        setitem(view,V("mode"),V("duo"));auto cards=py_dict({
            {V("plant"),V::list({V("plant:激光豆")})},{V("plant2"),V::list({V("plant:巴豆")})},
            {V("zombie"),V::list({V("zombie:盾卫僵尸")})},{V("zombie2"),V::list({V("zombie:克苏鲁之仆")})}});
        setitem(view,V("decks"),cards);setitem(view,V("bans"),V::list({V("plant:双子向日葵")}));
        setattr(app,SY("view"),view);
        J out;
        for(const char* seat:{"plant","plant2","zombie","zombie2"}){
            const V k(seat);const auto side=std::string(seat).starts_with("plant")?V("plant"):V("zombie");
            const auto advice=callm(app,SY("draft_advice"),Args{side,k});
            expect(rd(advice,V("policy"))==V("FastDrafter"),"advice fallback");
            const auto d=rd(advice,V("deck"));expect(d.idx(0)==rd(cards,k).idx(0)&&!py::in(V("plant:双子向日葵"),d),"seat or bans ignored");
            out[seat]=J::parse(dump(d));
        }
        callm(room,SY("set_mode"),Args{V("coop")});callm(app,SY("bind_coop_progress"),Args{});
        auto progress=getattr(room,SY("coop_progress"));auto camps=getattr(progress,SY("campaigns"));
        setattr(room,SY("pve"),py_dict({{V("day"),V(1)},{V("decks"),V::dict()}}));
        for(const char* seat:{"plant","plant2"}){
            auto c=rd(camps,V(seat));auto allowed=callm(c,SY("available_unlocked"),Args{});
            auto d=pm_coop_ai::f_deck_for(Args{c,room,V(seat)});
            expect(d.len()>0&&d.len()<=callm(c,SY("slots"),Args{}).num(),"coop slots");
            for(const auto& key:d.items())expect(py::in(key,allowed),"unowned co-op pick");
            out[std::string("coop_")+seat]=J::parse(dump(d));
        }
        return out;
    }));
    rows.push_back(scenario("ai78.test_mode",[](){
        auto h=battle_from_scenario({{"seed",784}});
        auto surface=callm(pg::display_module(),SY("set_mode"),Args{V::tuple({V(960),V(540)})});
        auto a=pm_app::new_Application(Args{pg::pygame_module(),surface,h.bridge});
        callm(a,SY("create"),Args{V(true)});
        const auto op=[&](const char* name,const V& data=V::none()){test74::action(a,V::tuple({V("test74"),V(name),data}));};
        op("start");op("open",V("cards"));
        J decks;
        for(const char* seat:{"plant","zombie"}){
            op("side",V(seat));const V first(std::string(seat)=="plant"?"plant:巴豆":"zombie:普通僵尸");
            op("slot",V(3));op("card",first);callm(a,SY("refresh"),Args{});op("reference");callm(a,SY("refresh"),Args{});
            const auto d=rd(rd(rd(getattr(a,SY("view")),V("battle")),V("players")),V(seat));
            const auto cards=rd(d,V("deck"));expect(cards.len()==13&&cards.idx(3)==first,"test slot "+dump(cards));
            for(const auto& key:cards.items())expect(key.truthy(),"blank test slot");
            decks[seat]=J::parse(dump(cards));
        }
        return decks;
    }));
    rows.push_back(scenario("ai78.team_combat",[](){
        J out;
        for(const char* mode:{"coop","duo"}){
            const std::string name=mode;
            J d=decks({"plant:激光豆","plant:巴豆"},{"zombie:脑光墓碑","zombie:普通僵尸"});d["plant2"]=d["plant"];if(name=="duo")d["zombie2"]=d["zombie"];
            auto h=battle_from_scenario({{"seed",784},{"fixture_flat",true},{"mode",name},{"decks",d},{"clear_cooldowns",true}});
            auto session=typed72app::Session::create(typed72app::export_cold(h.battle,784),"性能固定场景");
            for(const char* seat:{"plant","plant2"})session->fixture_player(seat,{{"resource",2500.}});
            session->fixture_set_avatar("plant",{{"玩家位置",{1400.,960.,0.,0.}}});
            session->fixture_set_avatar("plant2",{{"玩家位置",{1536.,960.,0.,0.}}});
            session->sync_public();
            int seq=0;
            const auto plant_beam=[&](const char* seat,double x){
                auto error=session->command(seat,{{"type","deploy"},{"seq",++seq},{"card","plant:激光豆"},{"x",x},{"y",936.},{"facing",1}});
                expect(error.empty(),"deploy "+std::string(seat)+": "+error);
                session->sync_public();auto view=session->ai_control_view(Seat::plant);
                for(const auto& u:view.units)if(u.card_id=="plant:激光豆"&&u.seat.value_or("plant")==seat)return u.id;
                throw std::runtime_error("missing owner "+std::string(seat));
            };
            const auto first=plant_beam("plant",1368.);
            const auto second=plant_beam("plant2",1512.);
            auto enemy=session->spawn("zombie:普通僵尸","zombie",1740.,960.,-1,false);
            expect(enemy.has_value(),"spawn fixtures");session->sync_public();
            std::set<std::string> aimed;int crotons=0;
            J diagnostics=J::object();
            for(int tick=0;tick<600;++tick){
                if(tick%60==0){auto v=session->ai_control_view(Seat::plant2);auto me=v.player("plant");
                    session->spawn("zombie:铁桶僵尸","zombie",me->x+2.5*v.tile,me->y-0.5*v.tile,-1,false);session->sync_public();
                    if(tick==60){diagnostics["hero"]={me->x,me->y,me->resource,me->deck};for(auto& u:v.units)diagnostics["units"].push_back({u.card_id,u.behavior,u.x,u.y,u.facing});}
                }
                for(const auto owner:{Seat::plant,Seat::plant2}){
                    const auto seat=std::string(seat_name(owner));session->ai_observe(owner);
                    session->ai_plan(owner,false);
                    session->ai_control(owner,"r22",[&](const std::string& kind,const typed72app::ai::Args& args){
                        nlohmann::json cmd={{"type",kind},{"seq",++seq}};
                        for(const auto& [k,v]:args)std::visit([&](const auto& val){
                            using T=std::decay_t<decltype(val)>;
                            if constexpr(std::is_same_v<T,double>){
                                if(std::trunc(val)==val)cmd[k]=static_cast<int64_t>(val);else cmd[k]=val;
                            }else if constexpr(!std::is_same_v<T,std::monostate>)cmd[k]=val;
                        },v);
                        auto error=session->command(seat,cmd);if(kind=="deploy"||kind=="laser")diagnostics["inputs"][kind+":"+cmd.value("card",std::string{})+":"+error]=1;
                        if(error.empty()&&kind=="laser"&&cmd.contains("target")){
                            expect(cmd["target"]==(owner==Seat::plant?first:second),"bot retargeted teammate beam");aimed.insert(seat);
                        }
                        if(error.empty()&&kind=="deploy"&&cmd.value("card",std::string{})=="plant:巴豆")++crotons;
                        return error;
                    });
                }
                if(aimed.size()==2&&crotons>0)break;
                session->step();
            }
            out[name]={{"own_beam",aimed},{"crotons",crotons}};
            expect(aimed.size()==2&&crotons>0,"team AI commands "+out.dump()+" "+diagnostics.dump());
        }
        return out;
    }));
    return rows;
}
}
