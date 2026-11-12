#pragma once
#include <cstdint>
#include <cmath>
#include <memory>
namespace pvz::typed72 {
struct Point { double x = 0, y = 0; };
struct Motion { double x = 0, y = 0, vx = 0, vy = 0; };
// 按时归位, shared by zombie entries and attracted entities.
inline double timed_coordinate(double start,double end,double duration,double elapsed){
    if(elapsed<=0.)return start;
    if(elapsed>=duration)return end;
    const double delta=end-start,acceleration=4.*delta/(duration*duration),vmax=acceleration*duration/2.;
    const double half=std::floor(duration/2.);
    if(elapsed<half)return start+vmax/2.*elapsed;
    const double t=elapsed-half,v=vmax-acceleration*t;
    return start+(delta/2.+(v+vmax)/2.*t);
}
// A native position list is independently retainable. Assigning a new list
// must not redirect callbacks/iterators that already captured the old list.
// Ordinary physics mutates get(); a native dictionary assignment uses replace.
class MotionRecord {
public:
    MotionRecord():value_(std::make_shared<Motion>()){}
    explicit MotionRecord(Motion value):value_(std::make_shared<Motion>(value)){}
    Motion& get()noexcept{return *value_;}
    const Motion& get()const noexcept{return *value_;}
    std::shared_ptr<Motion> retain()const noexcept{return value_;}
    void replace(Motion value){value_=std::make_shared<Motion>(value);}
    MotionRecord& operator=(Motion value){replace(value);return *this;}
private:
    std::shared_ptr<Motion> value_;
};
struct Cell { int y = 0; int64_t x = 0; friend bool operator==(const Cell&, const Cell&) = default; };
} // namespace pvz::typed72
