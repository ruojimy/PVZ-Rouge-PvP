#include "sim/typed/ai_observation_codec.h"
#include "sim/typed/ai_team_support.h"
#include <fstream>
#include <iostream>
using namespace pvz::typed72;
namespace {
#include "ai_probe_fixture.inc"
J run(const J& c){
    const Seat side=faction(c.value("side",J("plant")));const std::string name=fixture_seat_name(side),enemy_name=side==Seat::plant?"zombie":"plant";J out=J::array();
    if(c.at("kind")=="observation"){
        AiObservationBuilder builder(side,c.value("width",3456.),c.value("height",1152.),c.value("tile",48.),c.value("night",false));
        for(const auto& f:c.at("frames")){
            const auto b=f.value("battle",J::object()),players=b.value("players",J::object());
            AiPublicHero mine,enemy;AiObservationFrame frame;
            if(players.contains(name)){mine=public_hero(players[name]);frame.mine=&mine;}
            if(players.contains(enemy_name)){enemy=public_hero(players[enemy_name]);frame.enemy=&enemy;frame.enemy_input_present=players[enemy_name].contains("input")&&json_truth(players[enemy_name]["input"]);}
            auto units=public_units(b.value("units",J::array()));std::vector<AiVisibleShot> shots;std::vector<AiPublicResource> resources;std::vector<AiDeckCardView> cards;
            for(const auto& s:b.value("projectiles",J::array()))shots.push_back(public_shot(s));
            for(const auto& r:b.value("resources",J::array()))resources.push_back({r.value("id",std::string{}),faction(r.value("side",J{})),point(r),r.value("amount",0.),optional_value<std::string>(r,"source")});
            if(frame.mine){const auto p=players[name];const auto cds=p.value("cooldowns",J::object());for(const auto& key:p.value("deck",J::array())){
                const auto id=key.get<std::string>();if(!c.at("catalog").contains(id))continue;const auto d=c["catalog"][id];
                cards.push_back({id,d.at("name"),d.at("behavior"),d.at("cost"),cds.value(id,0.),optional_value<double>(d,"range"),d.value("producer",false),d.value("mushroom",false),d.value("category",std::string{})=="secret"});}}
            frame.units=units;frame.shots=shots;frame.resources=resources;frame.cards=cards;frame.time=b.value("time",0.);frame.tick=b.value("tick",int64_t(0));frame.deathmatch=b.value("deathmatch",false);
            const auto terrain=b.contains("map")&&json_truth(b["map"])?b["map"]:f.value("map",J::object());frame.night=terrain.value("environment",J::object()).value("night",false);
            try{out.push_back(encode_ai_observation(builder.build(frame,f.value("plan_id",int64_t(0)),f.value("match_id",int64_t(0)),f.value("observation_id",int64_t(0)))));}catch(const std::exception& e){out.push_back({{"error",e.what()}});}
        }
    }else if(c.at("kind")=="team_support"){
        AiTeamSupportState state;AiTeamSupport support(state);
        for(const auto& f:c.at("frames")){
            const auto b=f.at("battle"),players=b.at("players"),p=players.at(name);const auto mine=public_hero(p);
            AiPublicHero mate;AiSupportFrame frame{.me=mine};frame.side=side;frame.seat=b.contains("local_seat")?seat_value(b["local_seat"]):side;
            const auto mode=b.value("mode",std::string("duel"));frame.mode=mode=="duo"?AiTeamMode::duo:mode=="coop"?AiTeamMode::coop:mode=="pve"?AiTeamMode::pve:AiTeamMode::duel;
            if(players.contains(name+"2")){mate=public_hero(players[name+"2"]);frame.mate=&mate;}
            frame.time=b.value("time",0.);frame.width=c.value("width",3456.);frame.tile=c.value("tile",48.);frame.deathmatch=b.value("deathmatch",false);
            const std::string real=frame.seat==seat_value(name+"2")?name:name+"2";
            for(const auto& fallen:b.value("team",J::object()).value("fallen",J::array()))if(fallen==real)frame.mate_fallen=true;
            std::vector<AiPublicHero> heroes;for(const auto& k:{std::string(enemy_name),std::string(enemy_name)+"2"})if(players.contains(k))heroes.push_back(public_hero(players[k]));frame.enemy_heroes=heroes;
            std::vector<AiUnitView> own,enemy;for(const auto& raw:b.value("units",J::array())){auto u=public_unit(raw);if(!raw.contains("max_hp"))u.max_hp=raw.value("hp",1.);(u.side==side?own:enemy).push_back(std::move(u));}frame.own=own;frame.enemy=enemy;
            std::vector<AiObservedThreat> threats;for(const auto& t:f.value("threats",J::array())){AiObservedThreat v;v.projectile=t.value("source",std::string{})=="projectile";v.eta_ms=t.value("eta_ms",int64_t(9999));threats.push_back(v);}frame.threats=threats;
            std::vector<AiSupportCard> deck;for(const auto& key:p.value("deck",J::array())){const auto id=key.get<std::string>();const auto card=c.at("catalog").at(id);deck.push_back({id,card.value("behavior",std::string{}),card.value("cost",0.),card.value("producer",false),p.value("ready",J::object()).value(id,true)});}frame.deck=deck;
            const auto home=f.at("home");auto decision=support.decide(frame,{home[0],home[1]});
            out.push_back({{"decision",support_decision(decision)},{"active",state.active},{"until",state.until},{"cooldown_until",state.cooldown_until},{"quiet_since",state.quiet_since?J(*state.quiet_since):J(nullptr)},{"last",support_decision(state.last)}});
        }
    }else throw std::invalid_argument("unknown AI probe case");
    return out;
}
}
int main(int argc,char** argv){try{if(argc!=3)throw std::invalid_argument("usage: ai_observation72_probe input output");std::ifstream input(argv[1],std::ios::binary);std::ofstream output(argv[2],std::ios::binary);std::string line;while(std::getline(input,line))if(!line.empty())output<<run(J::parse(line)).dump()<<'\n';return input.bad()||!output?2:0;}catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 2;}}
