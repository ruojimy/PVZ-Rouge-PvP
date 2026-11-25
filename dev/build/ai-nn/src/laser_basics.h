#pragma once

#include "deploy_model.h"

namespace laser_research {
using deploy_research::J;
using deploy_research::Session;
using deploy_research::View;
using deploy_research::dx;
using deploy_research::wrapped;
using pvz::typed72::Seat;
constexpr const char* Card = "plant:激光豆";

struct Point { double x, y; };
struct Aim { Point target; double score; };

inline std::optional<Aim> select_target(const View& view, Point eye, int facing) {
    const double tile = view.tile;
    std::optional<Aim> best;
    const auto consider = [&](Point unit, double weight, bool reach) {
        const auto hx = dx(unit.x, eye.x, view.width), hy = unit.y - eye.y;
        const auto cells = std::hypot(hx, hy) / tile;
        if (cells < 0.1 || cells > 19.7 || hx * facing < .19 * cells * tile) return;
        const double length = reach ? 19.7 : std::clamp(cells + .55, 8.3, 19.7);
        const double scale = length / cells;
        const Point endpoint{wrapped(eye.x + hx * scale, view.width), eye.y + hy * scale};
        if (endpoint.y < 0. || endpoint.y >= view.height) return;
        // The longer beam buys encounter time against durable or dangerous arrivals.
        // Short lines retain the higher base damage when the same weak target is in reach.
        const auto score = weight + (reach ? .1 * cells : .15 * (20. - length));
        if (!best || score > best->score) best = Aim{endpoint, score};
    };
    for (const auto& unit : view.units) {
        if (unit.side != Seat::zombie || unit.hp <= 0.) continue;
        const bool shield = unit.card_id == "zombie:盾卫僵尸";
        const bool heavy = unit.max_hp >= 500. || unit.card_id == "zombie:掷弹兵僵尸";
        const auto vertical = std::max(.18 * tile, std::min(unit.h * .38, tile));
        const double weight = shield ? .5 : heavy ? 5. : 2.;
        consider({unit.x, unit.y - vertical}, weight, heavy);
    }
    if (const auto* foe = view.player("zombie"); foe && !foe->absent && foe->hp > 0.)
        consider({foe->x, foe->y - .5 * tile}, 1.5, true);
    return best;
}

class Controller {
public:
    // Call on a normal AI tick, before the r22 action loop. All commands go through
    // the same room admission as the match. No resource, aim, or unit is injected.
    template<class Send>
    void step(Session& session, double time, Send send) {
        if (time < next_) return;
        next_ = time + .7;
        const auto view = session.ai_control_view(Seat::plant);
        const auto* me = view.player("plant");
        const auto* foe = view.player("zombie");
        if (!me || !foe || !me->in_deck(Card)) return;
        const auto tile = view.tile;
        bool own_bean = false;
        for (const auto& bean : view.units) {
            if (bean.side != Seat::plant || bean.card_id != Card || bean.hp <= 0.) continue;
            own_bean = true;
            if (!bean.awake) continue;
            const int facing = bean.facing < 0. ? -1 : 1;
            const Point eye{bean.x, bean.y};
            auto aim = select_target(view, eye, facing);
            auto it = firing_.find(bean.id);
            if (it != firing_.end()) {
                if (aim && time - it->second.t < 2.8) continue;
                if (!aim && time - it->second.t < 3.5) continue;
                if (aim && time - it->second.t < 7.
                    && std::hypot(dx(aim->target.x, it->second.point.x, view.width),
                                  aim->target.y - it->second.point.y) <= tile) continue;
                if (select(bean.id, eye, send)) {
                    ++stops_;
                    firing_.erase(it);
                }
                // A click can stop a beam or arm an idle bean. Cancel any
                // selected aim here, then reacquire on the next control tick.
                send("laser_cancel", J::object());
                continue;
            }
            if (!select(bean.id, eye, send)) continue;
            const auto player = session.players().at("plant");
            if (!player.contains("laser_aim")) continue;
            const auto& marker = player.at("laser_aim");
            aim = select_target(view, {marker.at("x").get<double>(), marker.at("y").get<double>()},
                                marker.at("facing").get<int>());
            if (!aim) {
                send("laser_cancel", J::object());
                continue;
            }
            const auto error = send("laser", J{{"x", aim->target.x}, {"y", aim->target.y}});
            if (error.empty()) {
                ++fired_;
                firing_[bean.id] = {aim->target, time};
            } else {
                ++rejected_;
                ++errors_[error];
                send("laser_cancel", J::object());
            }
            return;
        }
        if (own_bean || me->resource < 200. || time < next_plant_ || time < me->cooldown(Card, 0.)) return;
        next_plant_ = time + 2.;
        std::optional<J> best;
        double value = -1.;
        for (const int step : {0, -1, 1, -2, 2, -3, 3, -4, 4}) {
            const auto x = wrapped(me->x + step * tile, view.width);
            for (const int level : {0, -1, 1, -2, 2}) {
                const double y = me->y + (level - .5) * tile;
                const auto admission = session.placement("plant", Card, x, y, nullptr, nullptr);
                if (!admission.at(1).is_object()) continue;
                const auto& placement = admission.at(1);
                if (!placement.contains("col")) continue;
                for (const int direction : {-1, 1}) {
                    const Point eye{(placement.at("col").get<double>() + (direction < 0 ? 17. : 31.) / 48.) * tile,
                                    (placement.at("row").get<double>() + 20.5 / 48.) * tile};
                    const auto aim = select_target(view, eye, direction);
                    if (!aim) continue;
                    double risk = 0.;
                    for (const auto& u : view.units)
                        if (u.side == Seat::zombie && u.hp > 0. &&
                            std::hypot(dx(u.x, eye.x, view.width), u.y - eye.y) < 5. * tile) risk += 1.2;
                    const auto score = aim->score - risk - .05 * (std::abs(step) + std::abs(level));
                    if (score > value) {
                        value = score;
                        best = J{{"card", Card}, {"x", x}, {"y", y}, {"facing", direction}};
                    }
                }
            }
        }
        if (!best) return;
        const auto error = send("deploy", *best);
        if (error.empty()) ++planted_;
        else ++errors_[error];
    }

    J counts() const { return {{"planted", planted_}, {"starts", fired_}, {"retargets", stops_},
                               {"rejected_aims", rejected_}, {"errors", errors_}}; }

private:
    template<class Send>
    static bool select(const std::string& id, Point eye, Send send) {
        return send("laser", J{{"target", id}, {"x", eye.x}, {"y", eye.y}}).empty();
    }
    struct Beam { Point point; double t; };
    std::map<std::string, Beam> firing_;
    std::map<std::string, int> errors_;
    double next_ = 0., next_plant_ = 0.;
    int planted_ = 0, fired_ = 0, stops_ = 0, rejected_ = 0;
};
}
