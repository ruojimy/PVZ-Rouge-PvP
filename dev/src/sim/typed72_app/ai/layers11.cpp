#include "sim/typed72_app/ai/layers11.h"
#include "core/pymath.h"
#include <algorithm>
#include <cmath>

namespace pvz::typed72app::ai {
namespace {
double pmod(double a,double b){return py::mod(a,b);}
bool one_of(const std::string& s,std::initializer_list<const char*> set){for(const char* v:set)if(s==v)return true;return false;}
std::vector<std::string> role_get(const std::map<std::string,std::vector<std::string>>& m,const std::string& k){auto f=m.find(k);return f==m.end()?std::vector<std::string>{}:f->second;}
bool flag(const typed72::Field<bool>& f){return f.present()&&!f.is_null()&&f.get();}
std::optional<double> num(const typed72::Field<double>& f,std::optional<double> d){if(!f.present())return d;if(f.is_null())return std::nullopt;return f.get();}
const std::string SCARECROW="zombie:稻草人";
const std::string STURDY="zombie:坚固脑光墓碑";
// ground(c, x, y).get('kind'): None outside the rows.
std::optional<std::string> kind_at(Ctx& c,double x,double y){
    const auto row=int64_t(std::floor((y+2)/c.tile));const auto col=int64_t(std::floor(pmod(x,c.width)/c.tile));
    if(row>=0&&row<int64_t(c.b.tiles.size()))return c.b.tiles[size_t(row)].at(size_t(col)).kind;
    return std::nullopt;
}
std::pair<int64_t,int64_t> half_cell(Ctx& c,double x,double y){return {int64_t(std::floor(pmod(x,c.width)/(c.tile*.5))),int64_t(std::floor(y/(c.tile*.5)))};}
}

double balloon_hp(Seat side,const Player& me){return side==Seat::zombie&&me.in_deck(STURDY)?12.:10.;}

// ------------------------------------------------------------ ForwardPlant
void ForwardPlant::observe_health(Ctx& c){
    Recovery<PlantV7>::observe_health(c);
    const auto old=salvo_positions;salvo_velocity.clear();
    for(const auto* u:c.enemy){
        const auto f=old.find(u->id);
        if(f!=old.end()&&c.t>f->second[2]){
            const double vx=wrap_delta(f->second[0],u->x,c.width)/(c.t-f->second[2]);
            salvo_velocity[u->id]=std::max(-250.,std::min(250.,vx));
        }
    }
    salvo_positions.clear();for(const auto* u:c.enemy)salvo_positions[u->id]={u->x,u->y,c.t};
}
double ForwardPlant::half(Ctx& c){return mode=="siege"?2.5:PlantV7::half(c);}
std::pair<double,double> ForwardPlant::next_siege_anchor(Ctx&,const PlanDict&){throw std::logic_error("front7.ForwardPlant.next_siege_anchor is replaced by tactics65 in r22");}
bool ForwardPlant::siege_established(Ctx& c,const PlanDict& plan){
    const auto sb_1=*siege_anchor;const auto ax=std::get<0>(sb_1);const auto ay=std::get<1>(sb_1);
    if(std::abs(wrap_delta(c.me.x,ax,c.width))>95)return false;
    const double age=c.t-checkpoint_started.value_or(c.t);
    bool fire=false;
    for(const auto* u:c.own){const auto r=role(c,u->card_id);if((r=="shoot"||r=="lob")&&std::abs(wrap_delta(ax,u->x,c.width))<2.2*c.tile&&std::abs(u->y-ay)<2*c.tile){fire=true;break;}}
    bool wall=false;
    for(const auto* u:c.own)if(u->behavior=="wall"){const double v=double(*siege_dir)*wrap_delta(ax,u->x,c.width);if(0<v&&v<4*c.tile){wall=true;break;}}
    return age>=plan.num("siege_dwell",8)&&fire&&(wall||risk(c,ax,ay+2)<35);
}
void ForwardPlant::step(const View& v,const typed72::AiObservation& o,const PlanDict& plan,const Field& f,Services& s){
    PlanDict p=plan;
    const auto* me=v.player(v.team==Seat::plant?"plant":"zombie");
    if(recovering||me->hp<=10)p.set("mode",std::string("defend"));
    PlantV7::step(v,o,p,f,s);
}
bool ForwardPlant::salvo(Ctx& c,const std::map<std::string,std::vector<std::string>>& by_role,const PlanDict& plan){
    if(salvo_checked&&*salvo_checked==c.t)return false;
    salvo_checked=c.t;
    std::vector<std::string> keys;for(const auto& k:role_get(by_role,"instant"))if(one_of(c.card(k).behavior,{"ash","doom","chili","ghost"})&&c.ready(k,0.))keys.push_back(k);
    if(keys.empty())return false;
    std::vector<const Unit*> enemies;for(const auto* u:c.enemy)if(u->mobile&&in_view(c.me.x,c.me.y,u->x,u->y,c.width))enemies.push_back(u);
    bool urgent=false;
    if(c.me.hp<=14)for(const auto* u:enemies)if(std::abs(c.dx(u->x))<80&&std::abs(u->y-c.me.y)<110){urgent=true;break;}
    stable_sort_by(keys,[&](const std::string& k){return c.card(k).cost;});
    for(const auto& key:keys){
        const auto& card=c.card(key);const auto beh=card.behavior;const double cost=card.cost;
        double rx,ry;
        if(beh=="ash"){rx=1.5;ry=1.5;}else if(beh=="doom"){rx=3.3;ry=3.3;}else if(beh=="chili"){rx=5.;ry=1.1;}else{rx=5.;ry=.85;}
        struct Best{double score,x,y,value;size_t hits;};std::optional<Best> best;
        for(const auto& s:c.spots(true)){
            if(s.water&&!flag(card.aquatic))continue;
            std::vector<const Unit*> hits;
            for(const auto* u:enemies){
                if(beh=="chili"&&u->flying)continue;
                const auto vf=salvo_velocity.find(u->id);const double vx=vf==salvo_velocity.end()?0.:vf->second;
                const double ux=pmod(u->x+vx*.6,c.width);
                if(std::abs(wrap_delta(s.x,ux,c.width))<rx*c.tile&&std::abs(u->y-s.y)<ry*c.tile)hits.push_back(u);
            }
            double value=0;for(const auto* u:hits)value+=card_cost(*u,25.)*std::max(.25,std::min(1.,u->hp/std::max(1.,u->max_hp)));
            const bool hero_hit=in_view(c.me.x,c.me.y,c.foe.x,c.foe.y,c.width)&&std::abs(wrap_delta(s.x,c.foe.x,c.width))<rx*c.tile&&std::abs(c.foe.y-s.y)<ry*c.tile;
            const bool lethal=hero_hit&&c.foe.hp<=(beh=="chili"?10:16)&&beh!="ghost";
            const bool acceptable=lethal||(urgent&&!hits.empty())||(value>=std::max(plan.num("salvo_value",200),cost*1.5)&&(hits.size()>=2||value>=cost*2.5));
            if(!acceptable)continue;
            if(beh=="ghost"){
                bool near_ghost=false;for(const auto* u:c.own)if(u->behavior=="ghost"&&std::abs(wrap_delta(s.x,u->x,c.width))<3*c.tile&&std::abs(s.y-u->y)<c.tile)near_ghost=true;
                if(near_ghost)continue;
            }
            const double score=value+(lethal?200.:0.)-(std::abs(c.dx(s.x))*.02);
            if(!best||score>best->score)best=Best{score,s.x,s.y,value,hits.size()};
        }
        if(best&&place_at(c,key,best->x,best->y,front).empty()){
            log["salvo:"+beh]+=1;log["salvo_value"]+=double(int64_t(best->value));log["salvo_targets"]+=double(best->hits);
            return true;
        }
    }
    log["_salvo_wait"]+=1;
    return false;
}
bool ForwardPlant::emergency(Ctx& c,const std::map<std::string,std::vector<std::string>>& by_role,const PlanDict& plan){
    if(salvo(c,by_role,plan))return true;
    auto roles=by_role;std::vector<std::string> inst;for(const auto& k:role_get(by_role,"instant"))if(one_of(c.card(k).behavior,{"squash","chomp"}))inst.push_back(k);
    roles["instant"]=inst;
    return PlantV7::emergency(c,roles,plan);
}
bool ForwardPlant::strike(Ctx& c,const std::map<std::string,std::vector<std::string>>& by_role){
    auto roles=by_role;std::vector<std::string> inst;for(const auto& k:role_get(by_role,"instant"))if(one_of(c.card(k).behavior,{"squash","chomp"}))inst.push_back(k);
    roles["instant"]=inst;
    return PlantV7::strike(c,roles);
}
void ForwardPlant::deploy_logic(Ctx& c,const PlanDict& plan){
    std::vector<std::pair<std::string,std::string>> roles;for(const auto& k:deck(c))roles.emplace_back(k,role(c,k));
    std::map<std::string,std::vector<std::string>> by_role;for(const auto& [k,r]:roles)by_role[r].push_back(k);
    const auto role_of=[&](const std::string& id){for(const auto& [k,r]:roles)if(k==id)return r;throw std::out_of_range("roles["+id+"]");};
    if(emergency(c,by_role,plan))return;
    bool fire_all=false;for(const auto* u:c.own){const auto r=role(c,u->card_id);if(r=="shoot"||r=="lob"){fire_all=true;break;}}
    bool producers=false;for(const auto* u:c.own)if(card_producer(*u))producers=true;
    if(producers&&!fire_all){
        std::vector<std::string> guns;for(const auto& k:deck(c)){const auto r=role(c,k);if(r=="shoot"||r=="lob")guns.push_back(k);}
        stable_sort_by(guns,[&](const std::string& k){return c.card(k).cost;});
        for(const auto& k:guns)if(c.ready(k,0.)&&place(c,k,role(c,k),plan)){log["opening_fire"]+=1;return;}
    }
    if(mode=="siege"&&!recovering){
        bool fire=false;
        for(const auto* u:c.own){const auto r=role(c,u->card_id);if((r=="shoot"||r=="lob")&&std::abs(wrap_delta(anchor->first,u->x,c.width))<2.2*c.tile&&std::abs(u->y-anchor->second)<2*c.tile){fire=true;break;}}
        if(!fire){
            auto guns=role_get(by_role,"lob");for(const auto& k:role_get(by_role,"shoot"))guns.push_back(k);
            stable_sort_by(guns,[&](const std::string& k){return c.card(k).cost;});
            for(const auto& k:guns)if(c.ready(k,25.)&&place(c,k,role_of(k),plan)){log["front_fire"]+=1;return;}
        }
    }
    PlantV7::deploy_logic(c,plan);
}
bool ForwardPlant::bloom_and_vines(Ctx& c,std::map<std::string,std::vector<std::string>> by_role,const PlanDict& plan){
    double producers=0;for(const auto* u:c.own)if(card_producer(*u))++producers;
    if(producers>=plan.num("econ_goal",4)||c.deathmatch){
        std::vector<std::string> v;for(const auto& k:role_get(by_role,"vine"))if(k!="plant:阳光藤蔓")v.push_back(k);
        by_role["vine"]=v;
    }
    return PlantV7::bloom_and_vines(c,by_role,plan);
}

// ---------------------------------------------------------------- Plant64
std::string Plant64::role(Ctx& c,const std::string& key){
    const auto& b=c.card(key).behavior;
    if(b=="mortar")return "lob";if(b=="spring")return "shoot";if(b=="taunt")return "wall";
    return ForwardPlant::role(c,key);
}
bool Plant64::place(Ctx& c,const std::string& key,const std::string& r,const PlanDict& plan){
    if(c.card(key).behavior=="spring"){
        const auto enemies=nearby(c,6*c.tile);
        const Unit* target=nullptr;
        for(const auto* u:enemies)if(!target||std::abs(c.dx(u->x))<std::abs(c.dx(target->x)))target=u;
        auto cand=c.spots(true);
        if(target){
            std::vector<Spot> kept;for(const auto& p:cand)if(std::abs(wrap_delta(p.x,target->x,c.width))<2.2*c.tile&&std::abs(p.y-target->y)<1.5*c.tile)kept.push_back(p);
            cand=kept;stable_sort_by(cand,[&](const Spot& p){return std::abs(c.dx(p.x));});
        }else{
            std::vector<Spot> kept;for(const auto& p:cand){const double a=along(c,p.x);if(half(c)-1.5<=a&&a<=half(c)+1&&std::abs(p.y-anchor->second)<c.tile)kept.push_back(p);}
            cand=kept;stable_sort_by(cand,[&](const Spot& p){return std::abs(along(c,p.x)-half(c));});
        }
        for(size_t i=0;i<cand.size()&&i<8;++i){
            const int facing=target?sgn(wrap_delta(cand[i].x,target->x,c.width)):front;
            if(place_at(c,key,cand[i].x,cand[i].y,facing).empty()){log["spring_front"]+=1;return true;}
        }
        return false;
    }
    return ForwardPlant::place(c,key,r,plan);
}
std::vector<std::string> Plant64::rank_cards(Ctx& c,const std::vector<std::string>& keys,const std::string& r){
    auto out=ForwardPlant::rank_cards(c,keys,r);
    stable_sort_by(out,[&](const std::string& k){return c.card(k).behavior=="mortar"?-1:0;});
    return out;
}

// ---------------------------------------------------------------- Plant65
std::pair<double,double> Plant65::next_siege_anchor(Ctx& c,const PlanDict& plan){
    static const std::array<std::pair<double,double>,3> tiers{{{3,2.2},{5,3.5},{7,5.5}}};
    const auto cur=siege_anchor?std::pair<double,double>{c.me.x,c.me.y}:*home_anchor;
    const auto sb_2=enemy_base(c);const auto bx=std::get<0>(sb_2);const auto by=std::get<1>(sb_2);(void)by;
    const int d=siege_dir&&*siege_dir?*siege_dir:route_dir(c,cur.first,bx);
    siege_dir=d;
    const double dist=pmod((bx-cur.first)*d,c.width);
    const double gap=plan.num("siege_gap",240);
    if(dist-gap<c.tile)return cur;
    for(size_t tier=0;tier<tiers.size();++tier){
        const auto sb_3=tiers[tier];const auto tiles=std::get<0>(sb_3);const auto rise=std::get<1>(sb_3);
        const double step=std::min(plan.num("siege_step",3)*tiles/3.*c.tile,dist-gap);
        const double target=pmod(cur.first+d*step,c.width);
        std::vector<std::pair<double,std::pair<double,double>>> cands;
        for(const auto& bucket:c.field.spots)for(const auto& s:bucket){
            const double progress=d*wrap_delta(cur.first,s.x,c.width);
            if(s.water||!(c.tile*.5<=progress&&progress<=step+c.tile)||std::abs(s.y-cur.second)>rise*c.tile)continue;
            if(!landing(c,s.x,s.y+2,false))continue;
            if(c.deathmatch&&wet(c,s.x,s.y+2))continue;
            const double score=std::abs(wrap_delta(target,s.x,c.width))+std::abs(s.y-cur.second)*.9+risk(c,s.x,s.y+2)*2;
            cands.push_back({score,{s.x,s.y}});
        }
        if(!cands.empty()){
            log["siege_step"]+=1;if(tier)log["siege_step_wide"]+=1;
            checkpoint_started=c.t;platform.reset();siege_blocks=0;
            const auto* best=&cands[0];for(const auto& x:cands)if(x.first<best->first)best=&x;
            return best->second;
        }
    }
    log["front_blocked"]+=1;
    ++siege_blocks;
    if(siege_blocks>=plan.num("siege_flip_after",40)){siege_dir=-d;siege_blocks=0;log["siege_route_flip"]+=1;}
    return cur;
}
bool Plant65::siege_established(Ctx& c,const PlanDict& plan){
    if(Balloon65<Plant64>::siege_established(c,plan))return true;
    const auto sb_4=*siege_anchor;const auto ax=std::get<0>(sb_4);const auto ay=std::get<1>(sb_4);
    const bool reached=std::abs(c.dx(ax))<95&&std::abs(c.me.y-ay)<1.5*c.tile;
    if(!checkpoint_started)checkpoint_started=c.t;
    const double started=*checkpoint_started;
    if(!reached&&c.t-started>plan.num("siege_stuck",12)){log["siege_unreachable"]+=1;checkpoint_started=c.t;return true;}
    const double held=c.t-started;
    const bool crowded=c.spots(true).size()<5;
    if(reached&&((held>plan.num("siege_hold",25)&&(nearby(c,4*c.tile).empty()||c.me.resource>400))||(held>12&&crowded))){
        log["siege_hold_release"]+=1;checkpoint_started=c.t;return true;
    }
    return false;
}
std::string Plant65::place_at(Ctx& c,const std::string& key,double x,double y,int facing){
    const auto err=Balloon65<Plant64>::place_at(c,key,x,y,facing);
    if(err=="need pot"||err=="need lily"||err=="spike needs soil"){log["skip:"+err]+=1;return "memo";}
    return err;
}

// ---------------------------------------------------------------- Plant10
void Plant10::deploy_logic(Ctx& c,const PlanDict& plan){
    if(rebuild_economy(c,plan))return;
    if(mode=="siege"&&anchor&&c.me.resource>=plan.num("walk_spend",300)&&std::abs(wrap_delta(anchor->first,c.me.x,c.width))>150){
        const auto saved=anchor;anchor=std::pair<double,double>{c.me.x,c.me.y};mode="defend";
        struct Restore{Plant10& s;std::optional<std::pair<double,double>> a;~Restore(){s.anchor=a;s.mode="siege";}} restore{*this,saved};
        log["walk_spend"]+=1;
        PlanDict p=plan;p.set("mode",std::string("defend"));
        Plant65::deploy_logic(c,p);
        return;
    }
    Plant65::deploy_logic(c,plan);
}
bool Plant10::rebuild_economy(Ctx& c,const PlanDict& in){
    if(c.deathmatch||in.num("econ_goal",0)<=0)return false;
    if(recovering)return false;
    double prods=0,fire=0;
    for(const auto* u:c.own){if(card_producer(*u))++prods;const auto r=role(c,u->card_id);if(r=="shoot"||r=="lob")++fire;}
    if(prods>=in.num("econ_goal",0)||(fire<1&&prods>=2))return false;
    if(pressure(c)>in.num("econ_pressure",120))return false;
    std::vector<std::string> econ;for(const auto& k:deck(c))if(c.card(k).producer&&role(c,k)=="econ")econ.push_back(k);
    if(!c.night){
        const auto d=deck(c);const bool awake=std::find(d.begin(),d.end(),"plant:咖啡豆")!=d.end();
        std::vector<std::string> kept;for(const auto& k:econ)if(!flag(c.card(k).mushroom)||awake)kept.push_back(k);econ=kept;
    }
    const double reserve=in.num("econ_reserve",0);
    stable_sort_by(econ,[&](const std::string& k){const auto& cd=c.card(k);return -num(cd.yield_amount,25.).value()/std::max(25.,cd.cost!=0.?cd.cost:25.);});
    PlanDict plan=in;
    for(const auto& k:econ){
        if(!c.ready(k,reserve))continue;
        if(mode=="siege"){const double saved=plan.num("econ_back",4);plan.set("econ_back",std::max(saved,6.));}
        if(place(c,k,"econ",plan)){log["econ_rebuild"]+=1;return true;}
    }
    return false;
}
std::vector<std::string> Plant10::rank_cards(Ctx& c,const std::vector<std::string>& keys,const std::string& r){
    auto out=Plant65::rank_cards(c,keys,r);
    if(r=="lob"&&!out.empty()&&lobs_blocked(c)){log["lob_skip_umbrella"]+=1;return {};}
    return out;
}
bool Plant10::lobs_blocked(Ctx& c){
    size_t umbrellas=0;for(const auto* u:c.enemy)if(u->card_id=="zombie:萝卜伞僵尸")++umbrellas;
    if(!umbrellas)return false;
    bool straight=false;for(const auto& k:deck(c))if(role(c,k)=="shoot"&&!flag(c.card(k).lob))straight=true;
    size_t lobs=0;for(const auto* u:c.own)if(role(c,u->card_id)=="lob")++lobs;
    return straight&&lobs>=2;
}
bool Plant10::place_(Ctx& c,const std::string& key,const std::string& r,const PlanDict& plan,double ax,double ay,double h){
    if(Plant65::place_(c,key,r,plan,ax,ay,h))return true;
    double want;
    if(r=="shoot")want=0.;else if(r=="wall")want=h-.3;else if(r=="spike")want=1.;else if(r=="torch")want=-1.;else if(r=="mine")want=2.;else return false;
    const bool aquatic=flag(c.card(key).aquatic);
    std::vector<Spot> cand;for(const auto& p:c.spots(true)){const double a=along(c,p.x);if(-8<=a&&a<=h+1.5&&(aquatic||!p.water)&&std::abs(p.y-ay)>=12)cand.push_back(p);}
    stable_sort_by(cand,[&](const Spot& p){return std::abs(p.y-ay)/c.tile*.6+std::abs(along(c,p.x)-want);});
    int tries=0;
    for(const auto& p:cand){
        const auto err=place_at(c,key,p.x,p.y,r=="wall"?front:facing_for(c,p.x));
        if(err.empty()){log["place_fallback:"+r]+=1;return true;}
        if(err!="memo")++tries;
        if(tries>=4)break;
    }
    return false;
}

// ---------------------------------------------------------------- Plant11
void Plant11::deploy_logic(Ctx& c,const PlanDict& plan){
    const double floor=income_floor(c,plan);
    if(floor==0.){Plant10::deploy_logic(c,plan);return;}
    auto ready=c.ready;
    c.ready=[&c,ready,floor](const std::string& key,double reserve){
        if(c.card(key).producer)return ready(key,reserve);
        return ready(key,std::max(reserve,floor));
    };
    log["income_floor"]+=1;
    struct Restore{Ctx& c;std::function<bool(const std::string&,double)> r;~Restore(){c.ready=r;}} restore{c,ready};
    Plant10::deploy_logic(c,plan);
}
double Plant11::income_floor(Ctx& c,const PlanDict& plan){
    if(c.deathmatch||recovering)return 0;
    for(const auto* u:c.own)if(card_producer(*u))return 0;
    if(c.me.hp<.5*c.me.max_hp||pressure(c)>plan.num("floor_pressure",250))return 0;
    const auto d=deck(c);const bool awake=c.night||std::find(d.begin(),d.end(),"plant:咖啡豆")!=d.end();
    std::optional<double> best;
    for(const auto& k:d){const auto& cd=c.card(k);if(cd.behavior=="produce"&&(awake||!flag(cd.mushroom))){if(!best||cd.cost<*best)best=cd.cost;}}
    return best.value_or(0.);
}
std::string Plant11::place_at(Ctx& c,const std::string& key,double x,double y,int facing){
    if(!dead_spots)dead_spots.emplace();
    auto& dead=*dead_spots;
    const auto cell=half_cell(c,x,y);
    {auto f=dead.find(cell);if((f==dead.end()?-1.:f->second)>c.t){log["dead_spot_skip"]+=1;return "memo";}}
    if(!bad_pot_ground)bad_pot_ground.emplace();
    auto& bad=*bad_pot_ground;
    const auto beh=c.card(key).behavior;
    if(!bad.empty()&&!one_of(beh,{"pot","lily","spike"})){
        const auto here=kind_at(c,x,y);
        for(const auto& [pair,lift]:bad){
            if(here==std::optional<std::string>(pair.first)&&kind_at(c,x,y-lift)==std::optional<std::string>(pair.second)){
                bool support=false;
                for(const auto& s:c.obs.empty_supports)if(std::abs(wrap_delta(s.position.x,x,c.width))<c.tile*.6&&std::abs(s.position.y-y)<c.tile)support=true;
                if(!support){log["bad_pot_ground_skip"]+=1;return "memo";}
            }
        }
    }
    const auto err=Plant10::place_at(c,key,x,y,facing);
    if(err.find("原版种植条件")!=std::string::npos){
        for(const auto& s:c.obs.empty_supports){
            if(std::abs(wrap_delta(s.position.x,x,c.width))<c.tile*.6&&std::abs(s.position.y-y)<c.tile){
                dead[cell]=c.t+120.;
                const double lift=s.position.y-s.plant_y;
                const auto a=kind_at(c,s.position.x,s.position.y),b=kind_at(c,s.position.x,s.plant_y);
                if(a!=b){
                    if(!a||!b)throw std::logic_error("bad_pot_ground pair with a missing kind");
                    bool known=false;for(const auto& e:bad)if(e.first==std::make_pair(*a,*b))known=true;
                    if(!known)bad.push_back({{*a,*b},lift});
                }
                log["dead_spot"]+=1;
                break;
            }
        }
    }
    return err;
}

// ---------------------------------------------------------- CoverageZombie
std::vector<std::string> CoverageZombie::deck(Ctx& c){
    std::vector<std::string> out;for(const auto& k:Recovery<ZombieT7>::deck(c))if(k!=SCARECROW)out.push_back(k);return out;
}
bool CoverageZombie::coverage_deploy(Ctx& c,const PlanDict& plan,const std::vector<const Unit*>& graves){
    if(c.deathmatch||!c.me.in_deck(SCARECROW)||!c.ready(SCARECROW,25.))return false;
    std::vector<const Unit*> producers;for(const auto* g:graves)if(card_producer(*g))producers.push_back(g);
    std::vector<const Unit*> crows;for(const auto* u:c.own)if(u->card_id==SCARECROW)crows.push_back(u);
    if(double(crows.size())>=plan.num("scarecrow_max",3))return false;
    const double radius=6*c.tile;
    std::vector<const Unit*> uncovered;
    for(const auto* g:producers){bool cov=false;for(const auto* s:crows)if(std::hypot(wrap_delta(s->x,g->x,c.width),s->y-g->y)<=radius)cov=true;if(!cov)uncovered.push_back(g);}
    struct Cand{double benefit;size_t n;double neg;const Unit* ex;};std::optional<Cand> best;
    for(const auto* ex:graves){
        if(!in_view(c.me.x,c.me.y,ex->x,ex->y,c.width))continue;
        std::vector<const Unit*> covered;for(const auto* g:uncovered)if(std::hypot(wrap_delta(ex->x,g->x,c.width),ex->y-g->y)<=radius)covered.push_back(g);
        double benefit=0;for(const auto* g:covered)benefit+=income(c,{g});
        bool drowsy=false;for(const auto* g:covered)if(g->drowsy)drowsy=true;
        if(covered.empty()||(covered.size()<2&&!drowsy))continue;
        if(risk(c,ex->x,ex->y)>90)continue;
        const Cand cand{benefit,covered.size(),-std::abs(c.dx(ex->x)),ex};
        if(!best||std::tie(cand.benefit,cand.n,cand.neg)>std::tie(best->benefit,best->n,best->neg))best=cand;
    }
    if(best&&deploy_(c,SCARECROW,best->ex->x,best->ex->y-24,best->ex->id,1).empty()){
        log["scarecrow"]+=1;log["scarecrow_new_coverage"]+=double(best->n);return true;
    }
    return false;
}
void CoverageZombie::deploy_logic(Ctx& c,const PlanDict& plan,const std::vector<const Unit*>& graves,double foe_home_d){
    if(coverage_deploy(c,plan,graves))return;
    Recovery<ZombieT7>::deploy_logic(c,plan,graves,foe_home_d);
}
void CoverageZombie::step_ctx(Ctx& c,const PlanDict& plan){
    observe_health(c);
    if(!home)home=std::pair<double,double>{c.me.x,c.me.y};
    std::vector<const Unit*> graves;for(const auto* u:c.own)if(u->behavior=="grave")graves.push_back(u);
    const double d=std::abs(wrap_delta(home->first,c.foe.x,c.width));
    const int direction=sgn(wrap_delta(home->first,c.foe.x,c.width));
    const bool escaped=escape(c,plan);
    const Unit* stale=tend(c,graves,plan);
    if(!escaped){
        double post=pmod(home->first-direction*(d<650?6:2)*c.tile,c.width);
        if(std::abs(c.dx(c.foe.x))<400)post=pmod(c.me.x-sgn(c.dx(c.foe.x))*250,c.width);
        std::vector<const Unit*> close;for(const auto* u:c.enemy)if(u->mobile&&std::abs(c.dx(u->x))<130&&std::abs(u->y-c.me.y)<130)close.push_back(u);
        if(!close.empty())post=pmod(c.me.x-sgn(c.dx(close[0]->x))*200,c.width);
        if(stale&&close.empty()&&risk(c,c.me.x,c.me.y)<30)post=stale->x;
        if(c.deathmatch){
            std::vector<const Unit*> dry;for(const auto* g:graves)if(!wet(c,g->x,g->y))dry.push_back(g);
            if(!dry.empty()){
                const auto key=[&](const Unit* g){return risk(c,g->x,g->y)+std::abs(c.dx(g->x))*.02;};
                const Unit* best=dry[0];double bk=key(best);for(const auto* g:dry){const double k=key(g);if(k<bk){bk=k;best=g;}}
                post=best->x;
            }
        }
        bool jump=false;for(const auto& x:c.obs.threats)if(x.projectile&&x.eta_ms<450)jump=true;
        drive(c,post,jump,25);
    }
    detonate(c,plan);
    command_logic(c,plan,d,direction);
    if(c.t>=next_deploy){next_deploy=c.t+.3;deploy_logic(c,plan,graves,d);}
}

// --------------------------------------------------------------- Zombie65
void Zombie65::deploy_logic(Ctx& c,const PlanDict& plan,const std::vector<const Unit*>& graves,double foe_home_d){
    if(c.deathmatch&&c.me.in_deck(STURDY)){
        const auto& card=c.card(STURDY);
        double sturdy=0;for(const auto* g:graves)if(g->card_id==STURDY)++sturdy;
        if(sturdy<plan.num("sturdy_deathmatch_max",3)&&c.me.resource>=card.cost&&c.me.cooldown(STURDY,0.)<=c.t&&place_grave(c,STURDY,graves)){
            log["deathmatch_sturdy"]+=1;return;
        }
    }
    Balloon65<CoverageZombie>::deploy_logic(c,plan,graves,foe_home_d);
}

// --------------------------------------------------------------- Zombie11
// Shipped behaviour (generated pm_rv_tactics11.cpp): `self.try_deploy = tracked` writes a
// declared slot that ztactics61.place_grave's find_dyn("try_deploy") never sees, so the
// real try_deploy runs, no spot is ever marked dead, and live_spots filters nothing.
// The Python source intended tracking; the game as shipped does not track. We match the
// shipped game (shadow audit: V logs no dead_grave_spot). Flip only as a deliberate AI change.
// PvP73 (待办 A1): the Python design is restored - a spot that refused a grave is skipped for a while
// instead of being retried 180+ times. Deliberate AI change; the V shadow audit now differs here.
static constexpr bool kShippedTracksDeadGraveSpots=true;
bool Zombie11::place_grave(Ctx& c,const std::string& key,const std::vector<const Unit*>& graves){
    if(!kShippedTracksDeadGraveSpots){if(!dead_grave_spots)dead_grave_spots.emplace();return Zombie65::place_grave(c,key,graves);}
    if(!dead_grave_spots)dead_grave_spots.emplace();
    auto* dead=&*dead_grave_spots;
    auto spots=c.spots;auto previous=try_deploy_hook;
    const double now=c.t;
    c.spots=[&c,spots,dead,now](bool free){
        std::vector<Spot> out;for(const auto& p:spots(free)){const auto f=dead->find(half_cell(c,p.x,p.y));if((f==dead->end()?-1.:f->second)<=now)out.push_back(p);}return out;
    };
    try_deploy_hook=[this,previous,dead,now](Ctx& c_,const std::string& k,double x,double y,const std::optional<std::string>& grave,int facing){
        const auto err=previous?previous(c_,k,x,y,grave,facing):try_deploy(c_,k,x,y,grave,facing);
        if(!err.empty()&&err!="memo"&&!grave&&(err.find("水面")!=std::string::npos||err.find("原版")!=std::string::npos)){
            (*dead)[half_cell(c_,x,y+24)]=now+300.;log["dead_grave_spot"]+=1;
        }
        return err;
    };
    struct Restore{Ctx& c;Zombie11& z;decltype(spots) s;decltype(previous) p;~Restore(){c.spots=s;z.try_deploy_hook=p;}} restore{c,*this,spots,previous};
    return Zombie65::place_grave(c,key,graves);
}
} // namespace pvz::typed72app::ai
