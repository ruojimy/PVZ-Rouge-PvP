    // ---- native frame layer (snapshot["native_frame"], protocol native-draw-v1) ----
    // The typed NativeCanvas records every draw; MATCH_FRAMES=<path> writes each published
    // frame as {"tick":T,"frame":{...}}. MATCH_FRAME_DEBUG=a:b traces art events for ticks a..b.
    NativeCanvas canvas;
    PlantDrawRules plant_draw_rules;
    NativePlantDraw plant_draw{battle,canvas,plant_draw_rules,tick_state.native_secrets,world_region.water_offset,[this]{return int64_t(navigation.target_plant);}};
    J unsupported_draws=J::object();
    std::unordered_map<uint64_t,NativeArt> flat_images;
    std::pair<int64_t,int64_t> frame_debug=[]{const char* s=std::getenv("MATCH_FRAME_DEBUG");long long a=-1,b=-2;if(!s||std::sscanf(s,"%lld:%lld",&a,&b)!=2){a=-1;b=-2;}return std::pair<int64_t,int64_t>{a,b};}();
    void fdbg(const std::string& text)const{if(canvas.frames.frame().tick>=frame_debug.first&&canvas.frames.frame().tick<=frame_debug.second)std::fprintf(stderr,"[frame %lld] %s\n",(long long)canvas.frames.frame().tick,text.c_str());}
    std::unique_ptr<std::ofstream> frame_out=[]{const char* s=std::getenv("MATCH_FRAMES");return s?std::make_unique<std::ofstream>(s,std::ios::binary):std::unique_ptr<std::ofstream>{};}();
    void unsupported_draw(const std::string& what){auto& n=unsupported_draws[what];n=n.is_number()?n.get<int64_t>()+1:1;}
    std::optional<NativeFrameSource> frame_source(const std::shared_ptr<AttackSource>& s)const{
        if(!s||!s->id.present()||s->id.is_null()||s->id.get().empty())return std::nullopt;
        if(const auto u=s->unit.lock()){const auto& m=u->body.motion.get();return NativeFrameSource{s->id.get(),{m.x,m.y}};}
        if(const auto e=s->entity.lock()){const auto& m=e->motion.get();return NativeFrameSource{s->id.get(),{m.x,m.y}};}
        // DrawRecorder: a hero source is placed by its 玩家位置.
        if(s->id.get().starts_with("hero:"))if(const auto seat=known_seat(s->id.get().substr(5));seat&&battle.heroes.contains(*seat)){
            const auto& m=*battle.heroes.hero(*seat).frame.position.get();return NativeFrameSource{s->id.get(),{m.x,m.y}};
        }
        return std::nullopt;
    }
    void install_frames(const std::string& draw_atlas_path,const J& cold){
        std::ifstream in(draw_atlas_path,std::ios::binary);if(!in)throw std::runtime_error("missing draw atlas "+draw_atlas_path);
        install_frames_json(J::parse(in),cold);
    }
    void install_frames_json(const J& draw_atlas,const J& cold){
        const auto& constants=cold.at("constants");const auto& g=cold.at("globals");
        canvas.install(draw_atlas,battle.runtime.presentation.atlas,constants.at("scale_factor"),constants.at("rider_lift"));
        canvas.frames.tile=battle.runtime.tile;
        if(g.contains("xianbi"))canvas.line_width=g.at("xianbi").get<double>();
        canvas.frames.sources=[this]{return frame_source(battle.heroes.source());};
        battle.runtime.sound_source=[this]()->std::optional<Point>{
            const auto s=battle.heroes.source();if(!s)return std::nullopt;
            if(const auto u=s->unit.lock()){const auto& m=u->body.motion.get();return Point{m.x,m.y};}
            if(const auto e=s->entity.lock()){const auto& m=e->motion.get();return Point{m.x,m.y};}
            return std::nullopt;
        };
        plant_draw_rules.root_plants=g.at("根茎叶植物").get<std::vector<std::string>>();
        plant_draw_rules.big_heads=g.at("大头").get<std::vector<std::string>>();
        plant_draw_rules.lobbers=g.at("投手植物").get<std::vector<std::string>>();
        for(const auto& [k,v]:g.at("花盆顶").items())plant_draw_rules.pot_tops[k]=v;
        plant_draw_rules.mode=g.at("模式").get<std::string>();
        plant_draw_rules.content_plants=constants.at("content_plants").get<std::vector<std::string>>();
        plant_draw.hooks=&plant_hooks;
        content_draw.content_zombies=constants.at("content_zombies").get<std::vector<std::string>>();
        if(constants.contains("pvp64_sinks"))for(const auto& [k,v]:constants.at("pvp64_sinks").items())content_draw.pvp64_sinks[k]=v;
        content_draw.unsupported=[this](const std::string& what){unsupported_draw(what);};
        content_draw.carried_barrel=[this](const ZombieRef& unit){barrels.draw(unit,canvas.drawing());};
    }
    // pvp wrapper chain over 显示植物 (native_content.draw_plant and later wrappers).
    struct PlantHooks final:PlantDrawHooks {
        MatchProbe& p;explicit PlantHooks(MatchProbe& probe):p(probe){}
        bool draw_plant(size_t index)override{return p.content_plant_draw(index);}
        bool draw_lily(size_t index)override{p.plant_draw.lily(index);return true;}
        // pvp58_vines.is_shell: the pumpkin, the vines (and grabber) on its layer, or an imitator copying the grabber.
        bool is_shell(const CombatPlant& plant)const override{
            const std::string content=plant.source.content.present()&&!plant.source.content.is_null()?plant.source.content.get():std::string{};
            const std::string copy=plant.copy_card.present()&&!plant.copy_card.is_null()?plant.copy_card.get():std::string{};
            return plant.kind=="南瓜头"||content=="阳光藤蔓"||content=="忧郁藤蔓"||content=="抓人草"||(plant.kind=="模仿者"&&copy=="plant:抓人草");
        }
    };
    PlantHooks plant_hooks{*this};
    bool content_plant_draw(size_t index){
        content_draw.native_tick=battle.heroes.tick;
        return content_draw.draw_plant(*battle.plant_roster->at(index));
    }
    // Atlas membership (V: `name in 图集`), e.g. the crush art swap of content plants.
    bool has_sprite(const std::string& name)const override{return canvas.has(name);}
    NativePatchDraw patch_draw{battle,canvas};
    void draw_patch(double now)override{
        ContentPhaseProbe::draw_patch(now);
        if(!patch_draw.unsupported)patch_draw.unsupported=[this](const std::string& what){unsupported_draw(what);};
        if(!patch_draw.thunder)patch_draw.thunder=[this](const ZombieRef& u){return ShootingProbe::fume.thunder(u);};
        if(!patch_draw.update_bubbles)patch_draw.update_bubbles=[this](double when){ShootingProbe::fume.update_bubbles(when);};
        patch_draw.now=now;
        patch_draw.draw_overlays();
    }
    NativeContentDraw content_draw{battle,canvas};
    void draw_content_zombie(const ZombieRef& unit)override{
        ContentPhaseProbe::draw_content_zombie(unit);
        content_draw.native_tick=battle.heroes.tick;
        if(!content_draw.draw_cart)content_draw.draw_cart=[this](const ZombieRef& u,CartDrawing& d){carts.draw(u,d);};
        content_draw.draw_zombie(unit);
    }
    void draw_zombie(const ZombieRef& unit)override{
        ContentPhaseProbe::draw_zombie(unit);
        content_draw.native_tick=battle.heroes.tick;content_draw.draw_zombie64(unit);
    }
    void draw_barrel_sprite(Point feet,double angle)override{ContentPhaseProbe::draw_barrel_sprite(feet,angle);content_draw.draw_barrel(feet,angle);}
    // NativeBattle._step post draw: self.content.barrels.draw(obj) for every orphan barrel (suspended from
    // the zombie region, so this is its only draw). PvP73: the production layer only recorded the call,
    // so a barrel left by a dead 滚桶僵尸 was never drawn.
    void draw_barrel(const ZombieRef& unit)override{NativeTickProbe::draw_barrel(unit);barrels.draw(unit,canvas.drawing());}
    // native_content draw_dart / mortar shots: asset art turned about its centre.
    void draw_dart(const EntityRef& entity,Point point,double angle)override{
        if(!canvas.drawing())return;
        const auto key=entity->art_name.present()&&!entity->art_name.is_null()?entity->art_name.get():std::string{};
        content_draw.draw_center(canvas.has(key)?canvas.image(key):canvas.image("豌豆"),point.x,point.y,angle);
    }
    void draw_mortar_projectile(const EntityRef& entity,double angle,const std::optional<Point>& trail,std::string_view tail)override{
        if(!canvas.drawing())return;
        if(trail)content_draw.draw_center(canvas.image(std::string(tail)),trail->x,trail->y,angle);
        const auto& p=entity->motion.get();
        content_draw.draw_center(canvas.has(entity->kind)?canvas.image(entity->kind):canvas.image("豌豆"),p.x,p.y,angle);
    }
    NativeContentDraw& effects(){content_draw.native_tick=battle.heroes.tick;return content_draw;}
    void draw_ghost_effect(const GhostBlast& v)override{ContentPhaseProbe::draw_ghost_effect(v);effects().ghost_effect(v);}
    void draw_reed_effect(const ReedBolt& v)override{ContentPhaseProbe::draw_reed_effect(v);effects().reed_effect(v);}
    void draw_spring_effect(const SpringSwipe& v)override{ContentPhaseProbe::draw_spring_effect(v);effects().spring_effect(v);}
    void draw_grenade_effect(const GrenadeBlast& v)override{ContentPhaseProbe::draw_grenade_effect(v);effects().grenade_effect(v);}
    void draw_grenade_projectile(const GrenadeRef& s,double a,double al)override{ContentPhaseProbe::draw_grenade_projectile(s,a,al);effects().grenade_projectile(s,a,al);}
    void draw_hook_rope(Point p)override{ContentPhaseProbe::draw_hook_rope(p);effects().hook_rope(p);}
    void draw_zombie_projectile(const ContentProjectileRef& s,std::string_view n,double a,double al)override{ContentPhaseProbe::draw_zombie_projectile(s,n,a,al);effects().zombie_projectile(s,n,a,al);}
    void draw_lettuce_flash(const LettuceFlash& v)override{ContentPhaseProbe::draw_lettuce_flash(v);effects().lettuce_flash(v);}
    void draw_zombie70_effects()override{ContentPhaseProbe::draw_zombie70_effects();}
    void draw_hero(Seat seat,bool materialize)override{
        ContentPhaseProbe::draw_hero(seat,materialize);
        draw_dave(canvas,{battle.heroes.hero(seat),battle.heroes.globals,battle.runtime.tile,battle.heroes.tick,tick_state.dave_hurt_alpha.at(seat_index(seat)),materialize},
                  [this](const std::string& what){unsupported_draw(what);});
    }
    void stun_star(Point point,Point size)override{
        ContentPhaseProbe::stun_star(point,size);
        if(canvas.drawing())canvas.display(NativeArtStore::scale(canvas.image("星星"),int(size.x),int(size.y)),point);
    }
    void tint_poison(const ZombieRef& u)override{
        ContentPhaseProbe::tint_poison(u);
        if(!u->poison.poison.present()||u->poison.poison.is_null()||!u->poison.poison.get())return;
        const auto& level=u->poison.poison.get()->level;if(!level.present()||level.is_null())return;
        std::vector<std::string> roots{u->body.kind+"-身",u->body.kind+"-首"};
        const auto plant=u->patch.plant_name.present()&&!u->patch.plant_name.is_null()?u->patch.plant_name.get():u->body.kind;
        if(canvas.has(plant+"-植头"))roots.push_back(plant+"-植头");
        canvas.tint_roots(roots,level.get());
    }
    // __pvz_sb_spawn_zombie_pea runs the lazy plant-zombie art patch (sim time, drawn or not).
    void ensure_plant_zombie_assets()override{ContentPhaseProbe::ensure_plant_zombie_assets();canvas.patch_plant_zombie_assets();}
    // 飞贼僵尸 rope: 画线((50,50,50), start, end).
    void line(Point start,Point end)override{ContentPhaseProbe::line(start,end);canvas.line(NativeCanvas::Json::array({50,50,50}),start,end);}
    void draw_particles(const std::vector<ParticleRect>& rects)override{
        for(const auto& r:rects)canvas.frames.primitive({"rect",r.color,r.x,r.y,r.width,r.height,0});
    }
    void draw_plants()override{ContentPhaseProbe::draw_plants();plant_draw.draw_all();}
    // native_expansion armor gate and art aliases.
    void expansion_armor_gate(const ZombieRef& unit)override{fdbg("armor_gate "+(unit?unit->body.kind:std::string("-")));canvas.expansion.gate(unit);}
    void expansion_armor_clear()override{canvas.expansion.clear();}
    bool expansion_has_art(const std::string& key)const override{return canvas.has(key);}
    void expansion_alias_one(const std::string& old,const std::string& next)override{fdbg("alias "+old+" -> "+next);canvas.alias_one(old,next);}
    void expansion_restore_art()override{canvas.restore();}
    void alias_art(const std::string& old,const std::string& next)override{
        fdbg("alias_art "+old+" , "+next);
        ContentPhaseProbe::alias_art(old,next);canvas.alias(old,next);
    }
    // 扁死: 变图(图集[name], 比*1.4, 比*.3), 反 when facing -1; one image per squashed entity.
    uint64_t flat_sprite(std::string name,Point size,bool mirror)override{
        const auto id=ContentPhaseProbe::flat_sprite(name,size,mirror);
        auto image=canvas.resize(canvas.image(name),size.x,size.y);
        if(mirror)image=NativeCanvas::flip(image);
        flat_images[id]=image;return id;
    }
    NativeArt frame_image(const EntitySprite& sprite){
        if(const auto* name=std::get_if<std::string>(&sprite))return canvas.image(*name);
        const auto found=flat_images.find(std::get<uint64_t>(sprite));
        if(found==flat_images.end())throw std::runtime_error("native frame: unknown flat sprite");
        return found->second;
    }
    void draw(EntityDraw d)override{
        ContentPhaseProbe::draw(d);
        if(!canvas.drawing())return;
        auto image=frame_image(d.sprite);
        if(const auto* n=std::get_if<std::string>(&d.sprite))fdbg("draw "+*n);
        if(const auto* n=std::get_if<std::string>(&d.sprite);n&&skip_plant_zombie_armor(*n))return;
        if(d.dimensions)image=canvas.resize(image,d.dimensions->x,d.dimensions->y);
        if(d.mirrored)image=NativeCanvas::flip(image);
        if(d.rotation)canvas.rotated(image,d.position,*d.rotation);else canvas.display(image,d.position);
    }
    // patch1501 should_skip_native_plant_zombie_armor_draw (screen.blit wrapper): the native
    // armor layer (防具/冰冻防具, with its hurt flash) of a plant zombie wearing 路障/铁桶, or of
    // a 南瓜头防具 wearer, is not blitted; the patch overlay draws that armor instead.
    bool skip_plant_zombie_armor(const std::string& sprite)const{
        const auto s=battle.heroes.source();if(!s)return false;const auto u=s->unit.lock();if(!u)return false;
        const auto& armor=u->body.armor;if(armor.empty()||u->body.armor_hp<=0.)return false;
        const bool plant=u->patch.plant_zombie.present()&&!u->patch.plant_zombie.is_null()&&u->patch.plant_zombie.get();
        if(!(armor=="南瓜头防具"||(plant&&(armor=="路障"||armor=="铁桶"))))return false;
        return sprite==armor||sprite==armor+"-受伤"||sprite==armor+"-冰冻"||sprite==armor+"-冰冻-受伤";
    }
    void alpha(const EntitySprite& s,double a)override{ContentPhaseProbe::alpha(s,a);NativeCanvas::set_alpha(frame_image(s),a);}
    void begin_frame(int64_t tick)override{ContentPhaseProbe::begin_frame(tick);canvas.frames.begin_frame(tick);}
    void set_drawing(bool draw)override{ContentPhaseProbe::set_drawing(draw);canvas.frames.enabled=draw;}
    void entity_override(FrameEntity source)override{
        ContentPhaseProbe::entity_override(source);
        if(const auto* seat=std::get_if<Seat>(&source)){
            const auto& m=*battle.heroes.hero(*seat).frame.position.get();
            canvas.frames.entity_override=NativeFrameSource{"hero:"+std::string(seat_name(*seat)),{m.x,m.y}};
        }else if(const auto* unit=std::get_if<ZombieRef>(&source)){
            canvas.frames.entity_override=frame_source(source_ref(*unit));
        }else canvas.frames.entity_override.reset();
    }
    void snapshot()override{
        ContentPhaseProbe::snapshot();
        if(frame_out)(*frame_out)<<J{{"tick",canvas.frames.frame().tick},{"frame",canvas.frame_json(canvas.frames.frame())}}.dump(-1,' ',false,J::error_handler_t::replace)<<'\n';
    }
    // ---- end native frame layer ----
