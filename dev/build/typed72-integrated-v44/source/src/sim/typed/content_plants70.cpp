#include "sim/typed/content_plants70.h"
#include "sim/typed/projectile_rules.h"
#include "core/pymath.h"
#include "core/function_profile.h"
#include "sim/typed/spatial_mode.h"
#include <algorithm>
namespace pvz::typed72 {
namespace {
constexpr double pi=0x1.921fb54442d18p+1;
bool yes(const Field<bool>& value){return value.present()&&!value.is_null()&&value.get();}
bool named(const Field<std::string>& value,std::string_view name){return value.present()&&!value.is_null()&&value.get()==name;}
bool local_occupancy(){static const bool enabled=[]{const char* p=std::getenv("PVP742_TARGETING");return !p||*p!='0';}();return enabled&&spatial741_enabled();}
bool same_optional(const Field<std::string>& a,const Field<std::string>& b) {
    const bool av=a.present()&&!a.is_null(),bv=b.present()&&!b.is_null();return av==bv&&(!av||a.get()==b.get());
}
}
bool ContentPlants70::alive(const ContentTarget& target)const {
    if(const auto* p=std::get_if<PlantRef>(&target))return (*p)->hp.or_missing(0.)>0.&&!(*p)->dead.present()&&!(*p)->ash.present();
    const auto& t=std::get<CombatTarget>(target);const auto& body=t.is_hero()?static_cast<const ZombieRecordFields&>(world_.heroes.cached_proxy(t.hero)):
        static_cast<const ZombieRecordFields&>(t.unit->body);
    return body.hp>0.&&!body.dead.present()&&!body.ash.present();
}
bool ContentPlants70::is_head(const PlantRef& plant){return named(plant->source.content,"抓人草触手");}
double ContentPlants70::plant_rate(const PlantRef& plant) {
    if(plant->sleep.present()||plant->hp.or_missing(0.)<=0.||plant->dead.present()||plant->ash.present())return 0.;
    return 1./std::max(.01,plant->aura_factor.or_missing(1.));
}
double ContentPlants70::factor(const PlantRef& p){return p->ice.or_missing(0.)>1000.||p->butter.or_missing(0.)>0.||p->stun.or_missing(0.)>0.?0.:p->ice.or_missing(0.)>0.?.5:1.;}
bool ContentPlants70::seat_has(const PlantRef& plant,std::string_view name)const {
    const auto seat=plant->source.seat.value_or(plant->source.owner.present()?parse_seat(plant->source.owner.get()):Seat::zombie);
    const auto& secrets=world_.heroes.players.at(seat_index(seat)).value().secrets;return std::find(secrets.begin(),secrets.end(),name)!=secrets.end();
}
std::optional<ContentTarget> ContentPlants70::registered(const Field<std::string>& key)const {
    if(!key.present()||key.is_null())return {};
    const auto object=world_.native_objects.get(key.get());if(!object)return {};
    if(const auto* p=std::get_if<PlantRef>(&*object))return *p;return CombatTarget::zombie(std::get<ZombieRef>(*object));
}
bool ContentPlants70::configure(PlantRef plant,std::string_view name,double hp) {
    if(name!="水盆"&&name!="抓人草"&&name!="冰冻生菜")return false;
    auto& p=*plant;p.source.content.set(std::string(name));p.content70.clock.set(0.);
    p.kind=name;p.hp.set(hp);p.max_hp.set(hp);p.content_state.maximum_hp.set(hp);p.shoot_cd.set(1e9);p.sleep.erase();p.one_shot.erase();
    if(name=="水盆") {
        auto& cell=world_.terrain.native_at(p.cell.y,p.cell.x);auto saved=std::make_shared<TerrainCell>(cell);saved->plant.erase();p.content70.basin_terrain.set(saved);
        const auto id=p.source.id.get();const auto found=std::find_if(basins.begin(),basins.end(),[&](const auto& item){return item.first==id;});
        if(found==basins.end())basins.emplace_back(id,plant);else found->second=plant;
        cell.block.set("水");cell.basin.set(id);services_.sync_terrain();
    }else if(name=="抓人草"){p.content70.heads.set({});spawn_head(plant);}
    else {p.one_shot.set(true);try_lettuce(plant);}return true;
}
std::vector<PlantRef> ContentPlants70::heads(const PlantRef& root)const {
    std::vector<PlantRef> result;for(const auto& plant:*world_.plant_roster)
        if(same_optional(plant->content70.parent,root->source.id)&&alive(plant))result.push_back(plant);return result;
}
void ContentPlants70::plant_tick(PlantRef plant) {
    if(named(plant->source.content,"冰冻生菜")){if(alive(plant)&&!plant->sleep.present())try_lettuce(plant);return;}
    if(!named(plant->source.content,"抓人草")||!alive(plant))return;
    const auto children=heads(plant);
    if(plant->sleep.present()){for(const auto& head:children)if(!head->sleep.present())head->sleep.set(0.);}
    else if(yes(plant->content70.was_asleep)){for(const auto& head:children)head->sleep.erase();}
    else if(std::any_of(children.begin(),children.end(),[](const auto& head){return head->sleep.present();})) {
        plant->sleep.set(0.);for(const auto& head:children)if(!head->sleep.present())head->sleep.set(0.);
    }
    plant->content70.was_asleep.set(plant->sleep.present());const size_t limit=seat_has(plant,"secret:触手")?3:1;
    if(children.size()<limit){plant->content70.clock.get()+=plant_rate(plant);if(plant->content70.clock.get()>=10000.&&spawn_head(plant))plant->content70.clock.get()-=10000.;}
    else plant->content70.clock.set(0.);update_heads(plant,children);
}
PlantRef ContentPlants70::spawn_head(PlantRef root) {
    if(world_.native_objects.size()>=700)return {};const auto point=targets_.point(root);const auto cell_index=root->cell;
    const auto cell=world_.terrain.at(cell_index.y,cell_index.x);if(!cell)throw std::out_of_range("tentacle root terrain");
    const bool had=cell->plant.present();const auto head=services_.spawn_tentacle_native(cell_index,root->facing);
    if(!had)cell->plant.erase();if(!head)return {};
    std::set<int> used;for(const auto& existing:heads(root))used.insert(existing->content70.head_color.or_missing(0));
    int color=0;for(int i=0;i<3;++i)if(!used.contains(i)){color=i;break;}
    services_.register_tentacle(head,root->source.id);head->kind="抓人草触手";head->hp.set(54.);head->max_hp.set(54.);head->content_state.maximum_hp.set(54.);head->shoot_cd.set(1e9);
    head->source.content.set("抓人草触手");auto& state=head->content70;state.parent=root->source.id;
    state.head_clock.set(0.);state.head_phase.set("idle");state.head_age.set(0.);state.head_hits.set({});
    head->head_point.set(point);state.head_color.set(color);state.head_aim.set({root->facing,0.});head->sleep.erase();
    if(root->source.seat)head->source.seat=root->source.seat;anchor_head_cached(head);
    services_.plant70_event({Plant70Event::Kind::tentacle_spawn,root->source.id,head->source.id,{},{},{}});return head;
}
std::vector<ContentTarget> ContentPlants70::head_targets(const PlantRef& plant,std::optional<size_t> limit) {
    PVP_PROFILE_SCOPE("ContentPlants70::head_targets");
    struct Candidate {double rank;std::string id;ContentTarget target;size_t ordinal;};std::vector<Candidate> found;
    const auto point=targets_.point(plant);const double radius=16.*world_.runtime.tile;
    for(const auto& target:queries_.enemies_in_box(source_ref(plant),{point.x-radius,point.y-radius,point.x+radius,point.y+radius})) {
        ++queries_.range_exact_tests;
        if(!alive(target))continue;const auto p=targets_.point(target);const double dx=wrap_delta(point.x,p.x,world_.world_width.get()),dy=p.y-point.y,distance=std::hypot(dx,dy);
        if(distance>16.*world_.runtime.tile||(distance!=0.&&dx*plant->facing/distance<std::cos(80.*pi/180.)))continue;
        double hp=0.;if(const auto* body=std::get_if<CombatTarget>(&target))hp=body->is_hero()?world_.heroes.cached_proxy(body->hero).hp*10.:body->unit->body.hp;
        found.push_back({-hp,world_.heroes.source_id(queries_.source(target)),target,found.size()});
    }
    const auto less=[](const Candidate& a,const Candidate& b){return a.rank<b.rank||(a.rank==b.rank&&(a.id<b.id||(a.id==b.id&&a.ordinal<b.ordinal)));};
    const auto keep=std::min(found.size(),limit.value_or(found.size()));
    if(keep<found.size()){std::partial_sort(found.begin(),found.begin()+keep,found.end(),less);found.resize(keep);}else std::stable_sort(found.begin(),found.end(),less);
    std::vector<ContentTarget> result;for(const auto& item:found)result.push_back(item.target);return result;
}
Point ContentPlants70::head_rest(const PlantRef& root,const PlantRef& head) {
    const auto base=targets_.point(root);const double tile=world_.runtime.tile;auto target=registered(head->content70.head_target);
    if(!target)for(const auto& candidate:queries_.enemies(source_ref(root)))if(named(head->content70.head_target,world_.heroes.source_id(queries_.source(candidate)))){target=candidate;break;}
    if(target&&alive(*target)) {
        const auto point=targets_.point(*target);double dx=wrap_delta(base.x,point.x,world_.world_width.get()),dy=point.y-base.y;
        const double distance=std::hypot(dx,dy);if(distance>16.*tile){const double scale=16.*tile/distance;dx*=scale;dy*=scale;}
        return {base.x+dx*.65,base.y+dy*.65};
    }
    const int lane=head->content70.head_color.or_missing(0)-1;return {base.x+root->facing*tile*(1.7+.15*std::abs(lane)),base.y-tile*(.35+.3*lane)};
}
void ContentPlants70::update_heads(const PlantRef& root,std::vector<PlantRef> children) {
    struct MovedHeads {ContentQueries& queries;const std::vector<PlantRef>& heads;~MovedHeads(){for(const auto& h:heads)queries.moved(h);}} moved_heads{queries_,children};
    // At most H heads can use H distinct targets, including those already
    // reserved by active heads. The first H entries of the old full ordering
    // therefore suffice, with exactly the same HP/ID/roster tie rules.
    const bool local=spatial741_enabled();const bool idle=std::any_of(children.begin(),children.end(),[](const auto& h){return h->content70.head_phase.get()=="idle";});
    const auto targets=!local||idle?head_targets(root,local?std::optional<size_t>{children.size()}:std::nullopt):std::vector<ContentTarget>{};std::set<std::optional<std::string>> used;
    for(const auto& head:children)if(head->content70.head_phase.get()!="idle") {
        const auto& id=head->content70.head_target;used.insert(id.present()&&!id.is_null()?std::optional<std::string>(id.get()):std::nullopt);
    }
    const auto base=targets_.point(root);const double rate=plant_rate(root),width=world_.world_width.get();
    std::stable_sort(children.begin(),children.end(),[](const auto& a,const auto& b){return a->source.id.get()<b->source.id.get();});
    for(const auto& head:children) {
        auto& state=head->content70;const double speed=head->sleep.present()?0.:rate*factor(head);state.head_clock.set(std::min(500.,state.head_clock.get()+speed));
        if(state.head_phase.get()=="idle") {
            std::optional<ContentTarget> choice=targets.empty()?std::nullopt:std::optional<ContentTarget>(targets.front());
            for(const auto& t:targets)if(!used.contains(world_.heroes.source_id(queries_.source(t)))){choice=t;break;}
            if(choice) {
                const auto id=world_.heroes.source_id(queries_.source(*choice));used.insert(id);state.head_target.set(id);
                const auto p=targets_.point(*choice);const double x=wrap_delta(base.x,p.x,width),y=p.y-base.y,length=std::hypot(x,y);if(length!=0.)state.head_aim.set({x/length,y/length});
            }
            if(choice&&state.head_clock.get()>=500.) {
                const auto p=targets_.point(*choice);state.head_phase.set("retract");state.head_age.set(0.);state.head_hits.set({});state.head_goal.set({base.x+wrap_delta(base.x,p.x,width),p.y});
                state.head_start=head->head_point;state.head_clock.get()-=500.;
            }
        }
        const auto phase=state.head_phase.get();state.head_age.get()+=speed;const auto old=head->head_point.get();const double age=state.head_age.get();Point point;
        if(phase=="idle") {const auto rest=head_rest(root,head);const double f=std::min(1.,speed/40.);point={old.x+wrap_delta(old.x,rest.x,width)*f,old.y+(rest.y-old.y)*f};}
        else if(phase=="retract") {
            const double f=std::min(1.,age/50.);const auto start=state.head_start.get(),rest=head_rest(root,head);point={start.x+wrap_delta(start.x,rest.x,width)*f,start.y+(rest.y-start.y)*f};
            if(f>=1.){const auto goal=state.head_goal.get();const double x=wrap_delta(point.x,goal.x,width),y=goal.y-point.y,length=std::hypot(x,y);if(length!=0.)state.head_aim.set({x/length,y/length});state.head_phase.set("dash");state.head_age.set(0.);state.head_start.set(point);}
        }else if(phase=="dash") {
            const double f=std::min(1.,age/50.);const auto start=state.head_start.get(),goal=state.head_goal.get();point={start.x+wrap_delta(start.x,goal.x,width)*f,start.y+(goal.y-start.y)*f};
            if(speed!=0.)head_hit(root,head,old,point);if(f>=1.){state.head_phase.set("return");state.head_age.set(0.);state.head_start.set(point);}
        }else {
            const double f=std::min(1.,age/100.);const auto start=state.head_start.get(),rest=head_rest(root,head);point={start.x+wrap_delta(start.x,rest.x,width)*f,start.y+(rest.y-start.y)*f};
            if(f>=1.){state.head_phase.set("idle");state.head_age.set(0.);}
        }
        head->head_point.set({py::mod(point.x,width),point.y});head->facing=root->facing;anchor_head_cached(head);
    }
}
void ContentPlants70::head_hit(const PlantRef& root,const PlantRef& head,Point start,Point end) {
    const double dx=wrap_delta(start.x,end.x,world_.world_width.get()),dy=end.y-start.y;
    for(const auto& target:queries_.enemies_in_box(source_ref(root),{std::min(start.x,start.x+dx),std::min(start.y,end.y),std::max(start.x,start.x+dx),std::max(start.y,end.y)})) {
        ++queries_.range_exact_tests;
        const auto id=world_.heroes.source_id(queries_.source(target));auto& hits=head->content70.head_hits;
        if(std::find(hits.get().begin(),hits.get().end(),id)!=hits.get().end()||!alive(target)||!targets_.contact(target,start,{dx,dy}))continue;
        hits.get().push_back(id);const auto* body=std::get_if<CombatTarget>(&target);const bool hero=body&&body->is_hero();
        targets_.damage(source_ref(root),target,hero?4.:16.,root->facing,true,HeroHit::tentacle);
        queries_.invalidate();
        const double direction=dx>=0.?1.:-1.;if(hero)world_.heroes.cached_proxy(body->hero).position->vx+=direction*world_.runtime.plk*400.;
        else if(body) {const auto found=std::find(world_.targets->begin(),world_.targets->end(),*body);if(found!=world_.targets->end())services_.tentacle_knock(size_t(found-world_.targets->begin()),direction*world_.runtime.plk*400.);}
        services_.plant70_event({Plant70Event::Kind::tentacle_hit,root->source.id,head->source.id,Field<std::string>(id),{}, {}});
    }
}
std::vector<PlantRef>& ContentPlants70::occupancy_bucket(Cell cell)const {
    if(cell.y<0||cell.y>=occupancy_rows_||cell.x<0||cell.x>=occupancy_cols_)return occupancy_outside_;
    return occupancy_buckets_[size_t(cell.y)*occupancy_cols_+size_t(cell.x)];
}
void ContentPlants70::prepare_occupancy(bool force)const {
    const auto& roster=*world_.plant_roster;const int rows=world_.terrain.rows(),cols=world_.terrain.cols();
    if(!force&&occupancy_tick_==world_.heroes.tick&&occupancy_revision_==world_.plant_roster_revision&&
       occupancy_roster_==world_.plant_roster.get()&&occupancy_data_==roster.data()&&occupancy_count_==roster.size()&&occupancy_rows_==rows&&occupancy_cols_==cols)return;
    PVP_PROFILE_SCOPE("ContentPlants70::prepare_occupancy");occupancy_tick_=-1;++occupancy_work_.rebuilds;occupancy_work_.indexed_plants+=roster.size();
    if(rows!=occupancy_rows_||cols!=occupancy_cols_){occupancy_buckets_.clear();occupancy_buckets_.resize(size_t(rows)*size_t(cols));occupancy_rows_=rows;occupancy_cols_=cols;}
    else for(auto& bucket:occupancy_buckets_)bucket.clear();
    occupancy_outside_.clear();occupancy_cells_.clear();
    // Keep dead/asleep/non-head records too. The original alive/exclude/type
    // predicates are re-evaluated at query time, never cached as occupancy.
    for(const auto& plant:roster){occupancy_bucket(plant->cell).push_back(plant);occupancy_cells_[plant.get()]=plant->cell;}
    occupancy_roster_=world_.plant_roster.get();occupancy_data_=roster.data();occupancy_count_=roster.size();occupancy_revision_=world_.plant_roster_revision;occupancy_tick_=world_.heroes.tick;
}
bool ContentPlants70::plant_in_cached(Cell cell,const PlantRef& exclude,bool non_head)const {
    ++occupancy_work_.queries;occupancy_work_.full_scan_candidates+=world_.plant_roster->size();
    const auto& candidates=local_occupancy()?occupancy_bucket(cell):*world_.plant_roster;
    for(const auto& p:candidates){++occupancy_work_.candidates;if(p!=exclude&&alive(p)&&(!non_head||!is_head(p))&&p->cell==cell)return true;}return false;
}
bool ContentPlants70::plant_in(Cell cell,const PlantRef& exclude)const {
    PVP_PROFILE_SCOPE("ContentPlants70::plant_in");
    // Public white-box calls may edit a record's raw Cell without a lifecycle
    // hook. Internal movement uses the maintained table; public calls refresh.
    if(local_occupancy())prepare_occupancy(true);
    return plant_in_cached(cell,exclude);
}
void ContentPlants70::anchor_head(const PlantRef& head) {
    if(local_occupancy())prepare_occupancy(true);
    anchor_head_cached(head);
}
void ContentPlants70::anchor_head_cached(const PlantRef& head) {
    PVP_PROFILE_SCOPE("ContentPlants70::anchor_head");
    const auto point=head->head_point.get();const double tile=world_.runtime.tile;
    const Cell cell{std::min(world_.terrain.rows()-2,std::max(0,int(std::floor(point.y/tile)))),world_.terrain.wrap(int64_t(std::floor(point.x/tile)))};
    const bool indexed=local_occupancy();if(indexed){
        prepare_occupancy();const auto old=occupancy_cells_.find(head.get());
        if(old!=occupancy_cells_.end()&&old->second!=head->cell)prepare_occupancy(true);
    }
    if(head->cell!=cell){
        if(!plant_in_cached(head->cell,head))world_.terrain.native_at(head->cell.y,head->cell.x).plant.erase();
        if(indexed){
            auto& before=occupancy_bucket(head->cell);auto& after=occupancy_bucket(cell);
            const auto occurrences=size_t(std::count(before.begin(),before.end(),head));
            if(&before!=&after&&occurrences){after.reserve(after.size()+occurrences);std::erase(before,head);after.insert(after.end(),occurrences,head);}
            if(const auto old=occupancy_cells_.find(head.get());old!=occupancy_cells_.end())old->second=cell;
        }
        head->cell=cell;
    }
    world_.terrain.native_at(cell.y,cell.x).plant.set(true);head_cells.emplace(cell.y,cell.x);
}
WaterCells ContentPlants70::head_only_cells()const {
    PVP_PROFILE_SCOPE("ContentPlants70::head_only_cells");
    // Publication is also the fixture boundary. A single O(P) refresh handles
    // direct same-tick cell/list edits while avoiding the old H full scans.
    if(local_occupancy())prepare_occupancy(true);
    WaterCells result;for(const auto& head:*world_.plant_roster)if(is_head(head)&&alive(head)&&!plant_in_cached(head->cell,{},true))result.emplace(head->cell.y,head->cell.x);return result;
}
void ContentPlants70::restore_marks() {
    if(local_occupancy())prepare_occupancy();
    for(const auto [row,col]:head_cells){auto& cell=world_.terrain.native_at(row,col);if(!cell.plant.present()&&plant_in_cached({row,col}))cell.plant.set(true);}head_cells.clear();
}
void ContentPlants70::before_tick() {
    const auto captured=basins;for(const auto& [id,plant]:captured)if(!alive(plant)||std::find(world_.plant_roster->begin(),world_.plant_roster->end(),plant)==world_.plant_roster->end()) {
        remove_basin(plant);std::erase_if(basins,[&,id=id](const auto& item){return item.first==id;});
    }
    if(!head_cells.empty())restore_marks();const auto plants=world_.plant_roster;
    for(size_t i=0;i<plants->size();++i) {
        const auto head=plants->at(i);if(!is_head(head))continue;const auto parent=registered(head->content70.parent);
        if((!parent||!alive(*parent))&&!yes(head->content70.head_gone)) {
            head->content70.head_gone.set(true);if(alive(head)){head->hp.set(0.);head->dead.set(DeathMarker(0.));
                if(parent)if(const auto* root=std::get_if<PlantRef>(&*parent);root&&yes((*root)->crushed))head->content70.head_crushed.set(double(world_.heroes.tick));}
        }else if(alive(head))anchor_head_cached(head);
    }
}
void ContentPlants70::remove_basin(const PlantRef& plant) {
    if(yes(plant->content70.basin_removed))return;plant->content70.basin_removed.set(true);auto& cell=world_.terrain.native_at(plant->cell.y,plant->cell.x);
    if(!same_optional(cell.basin,plant->source.id))return;
    for(const auto& other:*world_.plant_roster) {
        if(other==plant||!alive(other)||is_head(other)||other->cell!=plant->cell)continue;
        const auto& card=other->protection.card;
        if(other->kind=="睡莲"||(card.present()&&!card.is_null()&&std::find(aquatic_cards_.begin(),aquatic_cards_.end(),card.get())!=aquatic_cards_.end()))other->hp.set(0.);
    }
    const bool occupied=std::any_of(world_.plant_roster->begin(),world_.plant_roster->end(),[&](const auto& other){return other!=plant&&alive(other)&&!is_head(other)&&other->cell==plant->cell;});
    cell=*plant->content70.basin_terrain.get();if(occupied)cell.plant.set(true);services_.sync_terrain();
}
WaterCells ContentPlants70::water_component(Cell start)const {
    WaterCells seen;std::vector<Cell> todo{{start.y,world_.terrain.wrap(start.x)}};
    while(!todo.empty()) {
        const auto cell=todo.back();todo.pop_back();const auto key=std::pair{cell.y,cell.x};
        if(seen.contains(key)||!world_.terrain.valid_row(cell.y)||!named(world_.terrain.native_at(cell.y,cell.x).block,"水"))continue;
        seen.insert(key);todo.push_back({cell.y-1,cell.x});todo.push_back({cell.y+1,cell.x});todo.push_back({cell.y,world_.terrain.wrap(cell.x-1)});todo.push_back({cell.y,world_.terrain.wrap(cell.x+1)});
    }return seen;
}
bool ContentPlants70::target_in_water(const CombatTarget& target,const WaterCells& water)const {
    const auto position=target.is_hero()?*world_.heroes.cached_proxy(target.hero).position:target.unit->body.motion.get();const double tile=world_.runtime.tile;
    const auto col=world_.terrain.wrap(int64_t(std::floor(position.x/tile)));const double top=position.y-tile*(target.is_hero()?2.:target.unit->body.size.or_missing(2.));
    for(int row=std::max(0,int(std::floor(top/tile))),end=std::min(world_.terrain.rows(),int(std::floor((position.y-.001)/tile))+1);row<end;++row)if(water.contains({row,col}))return true;return false;
}
void ContentPlants70::try_lettuce(const PlantRef& plant) {
    if(yes(plant->effect_done)||!alive(plant))return;const auto water=water_component(plant->cell);std::vector<CombatTarget> hits;
    for(const auto& target:queries_.enemies(source_ref(plant)))if(const auto* t=std::get_if<CombatTarget>(&target);t&&alive(target)) {
        if(!water.empty()){if(target_in_water(*t,water))hits.push_back(*t);}
        else {const auto a=targets_.point(plant),b=targets_.point(target);if(std::abs(wrap_delta(a.x,b.x,world_.world_width.get()))<world_.runtime.tile*.6&&std::abs(a.y-b.y)<world_.runtime.tile*1.4){hits.push_back(*t);break;}}
    }
    if(!water.empty())for(const auto seat:seats_for(world_.mode))if(team_of(seat)==Seat::plant) {
        auto& hero=world_.heroes.hero(seat);world_.heroes.proxy(seat);
        if(hero.frame.hp.or_missing(0.)>0.&&target_in_water(CombatTarget::player(seat),water))hero.cold_until.set(std::max(hero.cold_until.or_missing(0.),double(world_.heroes.tick)+1500.));
    }
    if(water.empty()&&hits.empty())return;
    for(const auto& target:hits){HeroContext context(world_.heroes,{Seat::zombie,Seat::plant,CombatPhase::status,source_ref(plant),{}});frost_.freeze(target,2250.);}
    plant->hp.set(0.);plant->dead.set(DeathMarker(0.));plant->effect_done.set(true);flashes.push_back({world_.heroes.tick,water,targets_.point(plant)});
    Plant70Event event{Plant70Event::Kind::lettuce_freeze,plant->source.id,{},{},water,{}};
    for(const auto& target:hits)event.targets.push_back(world_.heroes.source_id(queries_.source(target)));services_.plant70_event(event);
}
} // namespace pvz::typed72
