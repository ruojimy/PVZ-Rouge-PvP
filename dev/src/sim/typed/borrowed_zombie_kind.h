#pragma once
#include <optional>
#include <string>
#include <string_view>

namespace pvz::typed72 {
// A living unit exposes the single native kind string. A metadata copy has
// dict(source) semantics: capture the current string, without borrowing the
// old unit's lifetime or following its later transformations. Moves also
// materialize because CombatZombie/HeroProxy themselves are nonmovable.
class BorrowedZombieKind {
public:
    BorrowedZombieKind()=default;
    BorrowedZombieKind(const BorrowedZombieKind& other){capture(other);}
    BorrowedZombieKind(BorrowedZombieKind&& other){capture(other);}
    BorrowedZombieKind& operator=(const BorrowedZombieKind& other) {
        if(this!=&other)capture(other);return *this;
    }
    BorrowedZombieKind& operator=(BorrowedZombieKind&& other) {
        if(this!=&other)capture(other);return *this;
    }
    void bind(const std::string& kind){snapshot_.reset();borrowed_=&kind;}
    bool present()const noexcept{return borrowed_!=nullptr||snapshot_.has_value();}
    std::string_view get()const {
        if(borrowed_)return *borrowed_;
        return snapshot_?std::string_view(*snapshot_):std::string_view{};
    }
private:
    const std::string* borrowed_=nullptr;
    std::optional<std::string> snapshot_;
    void capture(const BorrowedZombieKind& other) {
        // Make the owning string before releasing any current snapshot. This
        // also keeps assignment correct when the incoming borrow aliases it.
        auto value=other.present()?std::optional<std::string>(other.get()):std::nullopt;
        borrowed_=nullptr;snapshot_=std::move(value);
    }
};
}
