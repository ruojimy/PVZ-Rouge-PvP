from pathlib import Path
p=Path('match_probe.cpp');t=p.read_text(encoding='utf8')
def sub(a,b):
    global t
    assert t.count(a)==1,a
    t=t.replace(a,b)
sub('        garden.configure_locked_secrets();expansion.configure_locked_secrets();zsecrets.configure_locked();\n','''        garden.configure_locked_secrets();expansion.configure_locked_secrets();zsecrets.configure_locked();
        // Lock-time secret switches, each from the same team set the source reads.
        const auto plant_team=b.at("team_secrets").at("plant").get<std::vector<std::string>>();
        const auto plant_has=[&](const char* key){return std::find(plant_team.begin(),plant_team.end(),std::string(key))!=plant_team.end();};
        gas_secret=plant_has("secret:毒气");hardening=plant_has("secret:硬化");phototherapy=plant_has("secret:光疗");
        plant_rules.lantern_secret=phototherapy;navigation.cactus_secret=plant_has("secret:尖刺");navigation.charm_secret=plant_has("secret:魅惑");
        death_rules.nuclear_secret=plant_has("secret:核平");death_rules.zombie_secrets_enabled=zsecrets.enabled();
        death_rules.brain_holders.clear();death_rules.conversion_holders.clear();death_rules.conversion_forms.clear();
        for(const auto seat:tick_state.present)if(team_of(seat)==Seat::zombie){
            if(zsecrets.seat_has(seat,"脑光"))death_rules.brain_holders.push_back(seat);
            if(zsecrets.seat_has(seat,"植物僵尸"))death_rules.conversion_holders.push_back(seat);
        }
        // zombie_secrets.PLANT_ZOMBIES, limited to forms present in the card pool.
        for(const auto& [plant,form]:std::initializer_list<std::pair<const char*,const char*>>{{"豌豆射手","豌豆僵尸"},{"机枪射手","机枪僵尸"},{"坚果","坚果僵尸"},{"高坚果","高坚果僵尸"},
                {"火爆辣椒","辣椒僵尸"},{"毁灭菇","毁灭菇僵尸"},{"三叶草","三叶草僵尸"},{"路灯花","路灯花僵尸"},{"倭瓜","倭瓜僵尸"},{"窝瓜","倭瓜僵尸"},{"墓碑吞噬者","墓碑吞噬者僵尸"},
                {"萝卜伞","萝卜伞僵尸"},{"吸金磁","吸金磁僵尸"},{"大喷菇","大喷菇僵尸"}})
            if(catalog.find(std::string("zombie:")+form))death_rules.conversion_forms[plant]=form;
        battle.zombie_peas.secret_system_enabled=zsecrets.enabled();battle.zombie_peas.shotgun=zsecrets.has("散弹攻击");
        economy_state.subsidy=zsecrets.has("补贴");room.zombie_secrets=zsecrets.enabled();
''')
p.write_text(t,encoding='utf8')
print('ok')
