#pragma once
namespace pvz::typed72 {
// Native death keys distinguish a boolean mark from an animation clock.
class DeathMarker {
public:
    DeathMarker()=default;
    explicit DeathMarker(double n):number_(n){}
    explicit DeathMarker(bool flag):number_(flag?1.:0.),boolean_(true){}
    double number()const{return number_;}
    bool boolean_encoding()const{return boolean_;}
    void advance(double amount){number_+=amount;boolean_=false;}
private:
    double number_=0.;bool boolean_=false;
};
} // namespace pvz::typed72
