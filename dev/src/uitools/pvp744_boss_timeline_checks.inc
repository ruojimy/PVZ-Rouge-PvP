 check("classic_eye_half_hp_and_exact_transform_clock",[]()->J{
  auto s=match(true,true,"duel",true);auto eye=spawn(*s,"克苏鲁之眼",2200.,200.);s->native_set(false,eye,{{"血量",1400.}});steps(*s,10);need(unit(*s,eye)["terraria"]["ai"][0]==0.,"transformed at exactly half health");
  s->native_set(false,eye,{{"血量",1399.}});J changes=J::array();int previous=0,transition_tick=0,servants=-1;
  for(int i=0;i<110;++i){steps(*s,1);auto row=unit(*s,eye);const auto& n=row["terraria"];int phase=n["ai"][0].get<int>();int frame=n["frame_ticks"].get<int>();if(phase!=previous){changes.push_back({{"phase",phase},{"frame",frame},{"clock",n["ai"][1]}});if(phase==1){transition_tick=frame-int(n["ai"][1].get<double>());servants=count(*s,5);}if(phase==2)need(frame-transition_tick-int(n["ai"][1].get<double>())==100,"acceleration duration");if(phase==3)need(frame-transition_tick-int(n["ai"][2].get<double>())==200,"total transformation duration");previous=phase;}if(phase==1||phase==2)need(count(*s,5)==servants,"Classic transformation spawned expert servants");}
  need(changes.size()==3&&previous==3,"missing transformation phases");return changes;
 });
 check("classic_eye_three_charges_per_phase",[]()->J{
  J evidence=J::array();for(bool second:{false,true}){auto s=match(true,true,"duel",true);auto eye=spawn(*s,"克苏鲁之眼",2200.,200.);command(*s,"plant",{{"op","health"},{"value",1000000.}});if(second){s->native_set(false,eye,{{"血量",1399.}});steps(*s,102);}
   int charges=0,previous=-1,last_charge=-1,last_frame=0;bool cycle=false;J events=J::array();
   for(int i=0;i<620;++i){steps(*s,1);const auto n=unit(*s,eye)["terraria"];int state=int(n["ai"][1].get<double>()),frame=n["frame_ticks"].get<int>();
    if(state==2&&int(n["ai"][3].get<double>())!=last_charge){last_charge=int(n["ai"][3].get<double>());++charges;double speed=std::hypot(n["vx"].get<double>(),n["vy"].get<double>());need(std::abs(speed-(second?6.8:6.))<.001,"charge speed");if(last_frame)need(std::abs(frame-last_frame-(second?131:151))<=1,"charge interval");last_frame=frame;events.push_back({{"frame",frame},{"speed",speed}});}
    if(charges>0&&state==0){cycle=true;break;}previous=state;
   }need(cycle&&charges==3,"not exactly three charges per hover");evidence.push_back({{"second",second},{"charges",events}});
  }return evidence;
 });
 check("worm_split_resets_defaults_and_retains_integer_life_ratio",[]()->J{
  auto s=match(true,true,"duel",true);spawn(*s,"世界吞噬者",2200.,900.);steps(*s,20);auto before=zombies(*s);auto middle=before[33]["_pvp_id"].get<std::string>(),newhead=before[34]["_pvp_id"].get<std::string>(),newtail=before[32]["_pvp_id"].get<std::string>();s->native_set(false,newhead,{{"血量",137.9}});s->native_set(false,middle,{{"血量",0.}});steps(*s,1);auto head=unit(*s,newhead),tail=unit(*s,newtail);
  need(head["terraria"]["type"]==13&&tail["terraria"]["type"]==15,"split type conversion");need(head["血量"]==137.,"Transform integer life ratio");need(head["terraria"]["alpha"].get<double>()>=171.&&tail["terraria"]["alpha"].get<double>()>=171.,"transformed segments did not restart fade-in");need(head["terraria"]["target"]!="","split head did not reacquire target");return {{"head",head["terraria"]},{"tail",tail["terraria"]}};
 });
 check("worm_water_uses_burrowing_motion",[]()->J{
  J samples=J::array();double air=0.,water=0.;for(bool wet:{false,true}){auto s=match(true,true,"duel",true);if(wet)for(int y=7;y<=15;++y)for(int x=40;x<=51;++x)s->fixture_ditu(y,x,{{"方块","水"}});auto head=spawn(*s,"世界吞噬者",2200.,500.);steps(*s,1);const auto n=unit(*s,head)["terraria"];double vy=n["vy"];if(wet)water=vy;else air=vy;samples.push_back({{"water",wet},{"vx",n["vx"]},{"vy",vy}});}
  need(air>0.&&water>0.&&water<air,"water followed the air gravity branch");return samples;
 });
 check("worm_head_tail_adjacent_and_multiple_breaks",[]()->J{
  J cases=J::array();for(const auto& removed:std::vector<std::vector<int>>{{0},{66},{22,23},{20,40},{1,3}}){
   auto s=match(true,true,"duel",true);spawn(*s,"世界吞噬者",2200.,900.);steps(*s,20);const auto before=zombies(*s);
   for(int index:removed)s->native_set(false,before[index]["_pvp_id"].get<std::string>(),{{"血量",0.}});
   steps(*s,2);int expected_heads=removed==std::vector<int>{20,40}?3:removed.front()==0||removed.front()==66||removed==std::vector<int>{1,3}?1:2;
   int expected_size=67-int(removed.size())-(removed==std::vector<int>{1,3}?2:0);
   need(count(*s,13)==expected_heads&&count(*s,15)==expected_heads,"wrong independent chains after break");
   need(int(zombies(*s).size())==expected_size,"orphan segment cleanup");
   J positions=J::object();for(const auto& u:zombies(*s))if(u["terraria"]["type"]==13)positions[u["_pvp_id"].get<std::string>()]=u["位置"];
   steps(*s,15);for(const auto& [id,position]:positions.items())need(unit(*s,id)["位置"]!=position,"split chain head stopped moving");
   auto survivors=zombies(*s);for(const auto& u:survivors)s->native_set(false,u["_pvp_id"].get<std::string>(),{{"血量",0.}});steps(*s,2);need(zombies(*s).empty(),"complete chain kill left survivors");
   cases.push_back({{"removed",removed},{"heads",expected_heads},{"survivors",expected_size}});
  }return cases;
 });
 check("original_transform_and_death_gore_reaches_frame",[]()->J{
  auto count_gore=[](Session& s){J found=J::object();const auto frame=s.reference_native_frame();for(const auto& cmd:frame["commands"]){const auto serialized=cmd.dump();for(int id:{2,6,7,8,9,10,24,25,26,27,28,29,54,55,56,57})if(serialized.find("world:terraria/Gore_"+std::to_string(id)+"\"")!=std::string::npos)found[std::to_string(id)]=found.value(std::to_string(id),0)+1;}return found;};
  auto eye=match();auto id=spawn(*eye,"克苏鲁之眼");eye->native_set(false,id,{{"血量",1399.}});steps(*eye,52);auto transformation=count_gore(*eye);for(auto key:{"6","7","8"})need(transformation.value(key,0)==2,"missing transformation gore");
  J deaths=J::object();for(auto name:{"克苏鲁之眼","世界吞噬者","骷髅王"}){auto s=match();spawn(*s,name);auto units=zombies(*s);for(const auto& u:units)s->native_set(false,u["_pvp_id"].get<std::string>(),{{"血量",0.}});steps(*s,1);deaths[name]=count_gore(*s);}
  for(auto key:{"2","7","9","10"})need(deaths["克苏鲁之眼"].value(key,0)==2,"missing eye death gore");
  for(auto key:{"24","25","28","29"})need(deaths["世界吞噬者"].value(key,0)==1,"missing worm end gore");
  for(auto key:{"26","27"})need(deaths["世界吞噬者"].value(key,0)==65,"missing body death gore");
  need(deaths["骷髅王"].value("54",0)==1&&deaths["骷髅王"].value("55",0)==1&&deaths["骷髅王"].value("56",0)==2&&deaths["骷髅王"].value("57",0)==6,"missing skull/hand death gore");
  return {{"transform",transformation},{"deaths",deaths}};
 });
 check("skeletron_classic_800_hover_400_spin_and_idle_hand_retreat",[]()->J{
  auto s=match(true,true,"duel",true);auto skull=spawn(*s,"骷髅王",2200.,500.);command(*s,"plant",{{"op","health"},{"value",1000000.}});int previous=0;J events=J::array();
  for(int i=0;i<605;++i){steps(*s,1);auto n=unit(*s,skull)["terraria"];int phase=int(n["ai"][1].get<double>());if(phase!=previous){events.push_back({{"phase",phase},{"frame",n["frame_ticks"]},{"timer",n["ai"][2]}});previous=phase;}}
  need(events.size()==2,"skeletron phase count");need(events[0]["frame"].get<int>()-events[0]["timer"].get<int>()==800,"hover duration");need(events[1]["frame"].get<int>()-events[1]["timer"].get<int>()==1200,"spin duration");
  // A fresh head has both hands idle; retreat shortens each idle hand to ten AI frames.
  auto r=match(true,true,"duel",true);auto head=spawn(*r,"骷髅王",2200.,500.);r->fixture_set_avatar("plant",{{"玩家位置",{2200.,9500.,0.,0.}},{"_pvp_butter",1000000.}});steps(*r,1);need(count(*r,36)==2,"hands vanished immediately");steps(*r,5);need(count(*r,36)==0&&!unit(*r,head).is_null(),"idle hands did not retreat ahead of head");return events;
 });
