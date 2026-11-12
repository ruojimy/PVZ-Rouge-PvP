from pathlib import Path
p=Path('match_probe.cpp');t=p.read_text(encoding='utf8')
def sub(a,b):
    global t
    assert t.count(a)==1,a
    t=t.replace(a,b)
# NativeProtection: self.until = round(seconds * NATIVE_HZ).
sub('policy.until=rules_json.at("producer_protection_seconds");','policy.until=int64_t(pvz::py::round0(rules_json.at("producer_protection_seconds").get<double>()*250.));')
sub('''        return zsecrets.seat_has(seat,"豌豆")?1:0;\n''','''        // zombie_secrets.jump_cap: 豌豆 one jump (two with 威压), 威压 alone three.
        const bool pea=zsecrets.seat_has(seat,"豌豆"),pressure=zsecrets.seat_has(seat,"威压");
        return pea?(pressure?2:1):pressure?3:0;\n''')
sub('    // Same wrapper order as the verified expansion and garden stages.\n','''    // patch.draw -> draw_plant_zombie_heads: only runs on drawn native ticks, and its
    // head-angle sync writes the authoritative aim. Pixels stay in presentation.
    void draw_patch(double now)override{
        ContentPhaseProbe::draw_patch(now);
        for(const auto& target:*battle.targets){
            if(!target.unit)continue;auto& u=*target.unit;const auto& pa=u.patch;
            if(!(pa.plant_zombie.present()&&!pa.plant_zombie.is_null()&&pa.plant_zombie.get())||u.body.hp<=0.)continue;
            if(!pa.plant_name.present()||pa.plant_name.is_null()||!native_plant_zombie_config(pa.plant_name.get()))continue;
            sync_native_head_angle(u);
        }
    }
    // Same wrapper order as the verified expansion and garden stages.
''')
p.write_text(t,encoding='utf8')
