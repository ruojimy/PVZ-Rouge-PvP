#include "sim/typed/coverage_grid.h"
#include "sim/typed/moving_point_grid.h"
#include "sim/typed/legal_destination_field.h"
#include <nlohmann/json.hpp>
#include <algorithm>
#include <chrono>
#include <fstream>
#include <iostream>
#include <random>
#include <set>
#include <tuple>
using namespace pvz::typed72;using J=nlohmann::json;
using Clock=std::chrono::steady_clock;
void require(bool b,const char* text){if(!b)throw std::runtime_error(text);}
bool segment_box(Point a,Point b,CoverageBox box){
 double lo=0.,hi=1.;const auto axis=[&](double p,double d,double left,double right){if(d==0.)return p>=left&&p<=right;double x=(left-p)/d,y=(right-p)/d;if(x>y)std::swap(x,y);lo=std::max(lo,x);hi=std::min(hi,y);return lo<=hi;};
 return axis(a.x,b.x-a.x,box.left,box.right)&&axis(a.y,b.y-a.y,box.top,box.bottom);
}
std::optional<Cell> reference_destination(const std::vector<std::vector<uint8_t>>& solid,Cell requested){
 std::optional<std::tuple<int64_t,int,int64_t>> best;Cell result{};const int64_t cols=solid.front().size();
 for(size_t y=0;y<solid.size();++y)for(size_t x=0;x<solid[y].size();++x)if(!solid[y][x]){const auto dx=std::abs(int64_t(x)-requested.x);const auto key=std::tuple{std::abs(int64_t(y)-requested.y)+std::min(dx,cols-dx),int(y),int64_t(x)};if(!best||key<*best){best=key;result={int(y),int64_t(x)};}}
 return best?std::optional<Cell>{result}:std::optional<Cell>{};
}
int main(int argc,char**argv){
 if(argc<2)return 2;J checks=J::array();int failed=0;
 const auto test=[&](const char* name,auto fn){J row={{"name",name}};try{row["evidence"]=fn();row["passed"]=true;}catch(const std::exception&e){row["passed"]=false;row["error"]=e.what();++failed;}checks.push_back(row);std::cout<<row.dump()<<std::endl;};
 test("coverage_points_segments_wrap_large_bodies_and_dedup",[]()->J{
  std::mt19937 rng(741);std::uniform_real_distribution<double> unit(0.,1.);const double width=1031.;CoverageGrid grid;grid.reset(37.,width,31,240);std::vector<CoverageBox> boxes;
  for(size_t i=0;i<240;++i){const double x=(unit(rng)*4.-2.)*width,y=(unit(rng)*3.-1.)*700.,w=1.+unit(rng)*200.,h=1.+unit(rng)*350.;boxes.push_back({x,y,x+w,y+h});grid.cover(i,boxes.back());}grid.finish();
  uint64_t exact_pairs=0;for(int q=0;q<1800;++q){Point a{(unit(rng)*4.-1.5)*width,(unit(rng)*3.-1.)*700.},b{(unit(rng)*4.-1.5)*width,(unit(rng)*3.-1.)*700.};if(q%3==0)b=a;if(q%11==0){a={0.,0.};b={width*40.,31.*37.};}
   const auto ids=grid.segment(a,b);require(std::adjacent_find(ids.begin(),ids.end())==ids.end(),"multi-cell duplicate candidate");
   for(size_t i=0;i<boxes.size();++i){bool hit=false;for(int k=-8;k<=48&&!hit;++k){auto box=boxes[i];box.left+=k*width;box.right+=k*width;hit=segment_box(a,b,box);}if(hit){++exact_pairs;require(std::binary_search(ids.begin(),ids.end(),i),"swept/large/wrapped target missing from grid");}}
  }
  return {{"queries",grid.queries},{"oracle_intersections",exact_pairs},{"unique_candidates",grid.unique_candidates},{"storage_bytes",grid.storage_bytes()},{"occupied_cells",grid.occupied_cells()}};
 });
 test("coverage_rebuild_removes_dead_or_moved_ids_and_dense_dedup",[]()->J{
  CoverageGrid grid;grid.reset(48,3456,24,1000);for(size_t i=0;i<1000;++i)grid.cover(i,{120,600,144,864});grid.finish();require(grid.segment({0,700},{3400,700}).size()==1000,"dense candidate loss or duplication");
  grid.reset(48,3456,24,3);grid.cover(1,{1000,1000,1200,1100});grid.finish();require(grid.point({130,700}).empty(),"stale grid occupancy");const auto next=grid.point({1100,1050});require(next.size()==1&&next.front()==1,"moved actor not reindexed");return {{"dense_units",1000},{"stale_ids",0},{"builds",grid.builds}};
 });
 test("incremental_point_buckets_preserve_moved_ids_and_wrapped_queries",[]()->J{
  MovingPointGrid grid;const double width=1031.;grid.reset(37.,width,1000);std::mt19937 rng(744);std::vector<Point> points;
  for(size_t i=0;i<1000;++i){points.push_back({double(rng()%4000)-2000.,double(rng()%1500)-500.});grid.move(i,points.back());}
  uint64_t checked=0;
  for(int q=0;q<1200;++q){for(int m=0;m<10;++m){const auto i=rng()%points.size();points[i]={double(rng()%4000)-2000.,double(rng()%1500)-500.};grid.move(i,points[i]);}
   const double x=double(rng()%4000)-2000.,y=double(rng()%1500)-500.,radius=double(rng()%1200);const CoverageBox box{x-radius,y-radius,x+radius,y+radius};const auto ids=grid.rectangle(box);
   require(std::adjacent_find(ids.begin(),ids.end())==ids.end(),"dynamic query duplicated an actor");
   for(size_t i=0;i<points.size();++i){const auto p=points[i];if(p.y<box.top||p.y>box.bottom)continue;bool inside=false;for(int k=-8;k<=8;++k)if(p.x+k*width>=box.left&&p.x+k*width<=box.right)inside=true;
    if(inside){++checked;require(std::binary_search(ids.begin(),ids.end(),i),"moved point missing from spatial route");}}
  }
  grid.reset(48.,width,2);grid.move(1,{900,900});const auto empty=grid.rectangle({0,0,10,10});require(empty.empty(),"reset retained a stale moving point");
  return {{"queries",1200},{"moves",13000},{"oracle_matches",checked},{"cell_changes",grid.cell_changes}};
 });
 test("voronoi_projection_matches_old_manhattan_and_ties",[]()->J{
  std::mt19937 rng(742);uint64_t queries=0,rebuilds=0;for(int m=0;m<60;++m){const int rows=1+int(rng()%24),cols=1+int(rng()%43);std::vector<std::vector<uint8_t>> map(rows,std::vector<uint8_t>(cols));for(auto& row:map)for(auto& c:row)c=uint8_t(rng()%4!=0);LegalDestinationField field;
   for(int pass=0;pass<2;++pass){for(int y=0;y<rows;++y)for(int x=0;x<cols;++x){const auto a=reference_destination(map,{y,x}),b=field.query(map,{y,x});require(a==b,"Voronoi label/distance tie differs from old scan");++queries;}map[size_t(rng()%rows)][size_t(rng()%cols)]^=1;}
   require(field.rebuilds==2,"dynamic passability edit was not rebuilt");rebuilds+=field.rebuilds;
  }return {{"maps",60},{"exact_queries",queries},{"rebuilds",rebuilds}};
 });
 test("shared_destination_cpu_and_rebuild_evidence",[]()->J{
  std::vector<std::vector<uint8_t>> map(24,std::vector<uint8_t>(72));for(int y=0;y<24;++y)for(int x=0;x<72;++x)map[y][x]=uint8_t(x%17==0||(y%5==0&&x%3));
  std::mt19937 rng(743);std::vector<Cell> requests;for(int i=0;i<20000;++i)requests.push_back({int(rng()%24),int64_t(rng()%72)});
  uint64_t before_hash=0,after_hash=0;const auto start=Clock::now();for(auto q:requests){const auto p=reference_destination(map,q);before_hash=before_hash*33+uint64_t(p->y*72+p->x);}const auto middle=Clock::now();LegalDestinationField field;for(auto q:requests){const auto p=field.query(map,q);after_hash=after_hash*33+uint64_t(p->y*72+p->x);}const auto end=Clock::now();require(before_hash==after_hash,"destination benchmark changed choices");
  return {{"requests",requests.size()},{"old_ms",std::chrono::duration<double,std::milli>(middle-start).count()},{"shared_ms",std::chrono::duration<double,std::milli>(end-middle).count()},{"rebuilds",field.rebuilds},{"reuses",field.reused},{"checksum",after_hash},{"scope","Legal rally-cell projection CPU loop, not rendered FPS or a replacement for native movement fields"}};
 });
 std::ofstream(argv[1],std::ios::binary)<<J{{"passed",failed==0},{"failures",failed},{"checks",checks}}.dump(2);return failed?1:0;
}
