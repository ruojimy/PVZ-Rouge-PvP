namespace {
const std::string laser_card="plant:激光豆", croton_card="plant:巴豆";

struct BeamAim {double x,y,score;};

std::optional<BeamAim> laser_aim(const View& view,double eye_x,double eye_y,int facing,bool focus){
    std::optional<BeamAim> best;
    const auto consider=[&](double x,double y,double priority,bool durable){
        const double dx=wrap_delta(eye_x,x,view.width),dy=y-eye_y;
        const double distance=std::hypot(dx,dy)/view.tile;
        if(distance<.1||distance>19.7||dx*facing<.18*distance*view.tile)return;
        double length=durable?19.7:std::clamp(distance+.45,8.2,19.7);
        if(dy!=0.){
            const double room=dy>0.?view.height-.1-eye_y:eye_y;
            length=std::min(length,room*distance/std::abs(dy));
        }
        if(length<std::max(8.05,distance))return;
        const double scale=length/distance;
        const double score=priority+(durable?.09*length:.12*(20.-length));
        if(!best||score>best->score)best=BeamAim{pmod(eye_x+dx*scale,view.width),eye_y+dy*scale,score};
    };
    for(const auto& unit:view.units){
        if(unit.side!=Seat::zombie||unit.hp<=0.||!unit.mobile)continue;
        const bool shield=unit.card_id=="zombie:盾卫僵尸";
        const bool durable=unit.max_hp>=500.||unit.card_id=="zombie:掷弹兵僵尸";
        const double missing=focus?std::clamp((unit.max_hp-unit.hp)/400.,0.,2.):0.;
        const double priority=shield?.35:durable?5.+missing:2.+missing;
        const double center=std::clamp(unit.h*.40,.2*view.tile,2.5*view.tile);
        consider(unit.x,unit.y-center,priority,durable);
    }
    for(const auto& foe:view.players){
        if((foe.seat=="zombie"||foe.seat=="zombie2")&&!foe.absent&&foe.hp>0.)
            consider(foe.x,foe.y-.55*view.tile,.8,false);
    }
    return best;
}
}

void Plant19::aim_laser(const View& view,Services& services){
    const auto* me=view.player("plant");
    if(!me||!me->in_deck(laser_card)||view.time<next_laser_check)return;
    next_laser_check=view.time+.55;
    for(const auto& bean:view.units){
        if(bean.side!=Seat::plant||bean.card_id!=laser_card||!bean.awake||bean.hp<=0.)continue;
        if(bean.seat.value_or("plant")!=me->seat)continue;
        const auto state=services.laser(bean.id);
        if(!state)continue;
        const auto aim=laser_aim(view,state->eye_x,state->eye_y,state->facing,me->has_secret("secret:聚能"));
        const Args select{{"target",bean.id},{"x",state->eye_x},{"y",state->eye_y}};
        if(state->firing){
            if(view.time<next_laser_adjust)continue;
            if(aim&&std::hypot(wrap_delta(state->target_x,aim->x,view.width),state->target_y-aim->y)<1.25*view.tile)continue;
            if(!send_("laser",select).empty())continue;
            log["laser:stop"]+=1;
        }
        if(!aim||!send_("laser",select).empty())continue;
        if(send_("laser",{{"x",aim->x},{"y",aim->y}}).empty()){
            next_laser_adjust=view.time+3.;
            log["laser:start"]+=1;
        }else{
            send_("laser_cancel");
            log["laser:rejected"]+=1;
        }
        break;
    }
}

bool Plant19::place_laser(Ctx& c){
    if(!c.me.in_deck(laser_card)||!c.ready(laser_card,0.)||
       std::any_of(c.own.begin(),c.own.end(),[&c](const Unit* unit){return unit->card_id==laser_card&&unit->seat.value_or("plant")==c.me.seat;}))return false;
    struct Candidate {Spot spot;int facing;double value;};
    std::vector<Candidate> candidates;
    for(const auto& spot:spots_near(c,c.me.x,c.me.y,24)){
        if(std::abs(wrap_delta(c.me.x,spot.x,c.width))>4.5*c.tile||std::abs(spot.y-c.me.y)>2.5*c.tile)continue;
        for(const int facing:{-1,1}){
            const double eye_x=(std::floor(spot.x/c.tile)+(facing<0?17.:31.)/48.)*c.tile;
            const double eye_y=(std::floor(spot.y/c.tile)+20.5/48.)*c.tile;
            const auto aim=laser_aim(c.b,eye_x,eye_y,facing,c.has_secret("secret:聚能"));
            if(!aim)continue;
            double risk=0.;
            for(const auto* enemy:c.enemy)if(enemy->mobile&&!enemy->flying)
                risk+=std::max(0.,1.-dist(c,spot.x,spot.y,enemy->x,enemy->y)/(4*c.tile));
            const double value=aim->score-1.8*risk-.08*dist(c,spot.x,spot.y,c.me.x,c.me.y)/c.tile;
            if(value>1.)candidates.push_back({spot,facing,value});
        }
    }
    std::stable_sort(candidates.begin(),candidates.end(),[](const auto& a,const auto& b){return a.value>b.value;});
    for(size_t i=0;i<std::min<size_t>(4,candidates.size());++i){
        const auto& candidate=candidates[i];
        if(deploy_(c,laser_card,candidate.spot.x,candidate.spot.y,{},candidate.facing).empty())return true;
    }
    return false;
}

bool Plant19::place_croton(Ctx& c){
    if(!c.me.in_deck(croton_card)||!c.ready(croton_card,0.))return false;
    struct Bait {Spot spot;int facing;double value;};
    std::optional<Bait> best;
    for(const auto* enemy:c.enemy){
        if(!enemy->mobile||enemy->flying||enemy->behavior!="bite"||
           !in_view(c.me.x,c.me.y,enemy->x,enemy->y,c.width))continue;
        const int facing=enemy->facing<0.?-1:1;
        const double lead=pmod(enemy->x+facing*1.3*c.tile,c.width);
        auto spots=spots_near(c,lead,enemy->y,5);
        for(const auto& spot:spots){
            const double ahead=facing*wrap_delta(enemy->x,spot.x,c.width)/c.tile;
            if(ahead<.45||ahead>2.7||std::abs(spot.y-enemy->y)>.8*c.tile)continue;
            if(!c.services.preview(croton_card,spot.x,spot.y,{},false).empty())continue;
            double value=2.-std::abs(ahead-1.3)-std::abs(spot.y-enemy->y)/c.tile;
            for(const auto* follower:c.enemy){
                const double gap=-facing*wrap_delta(enemy->x,follower->x,c.width)/c.tile;
                if(follower->mobile&&gap>0.&&gap<6.&&std::abs(follower->y-enemy->y)<c.tile)value+=.7;
            }
            if(!best||value>best->value)best=Bait{spot,-facing,value};
        }
    }
    return best&&deploy_(c,croton_card,best->spot.x,best->spot.y,{},best->facing).empty();
}
