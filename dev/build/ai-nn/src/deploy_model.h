#pragma once

#include "plan_codec.h"
#include "sim/typed72_app/cold_file.h"
#include "sim/typed72_app/session.h"
#include <algorithm>
#include <array>
#include <cmath>
#include <fstream>
#include <optional>
#include <set>
#include <tuple>

namespace deploy_research {

using J = nlohmann::json;
using pvz::typed72::Seat;
using pvz::typed72app::Session;
using pvz::typed72app::ai::View;
constexpr std::size_t FeatureCount = 24;
using Features = std::array<double, FeatureCount>;

struct Choice {
    J command;
    Features features;
};

inline double scale(double x, double unit) {
    return std::clamp(x / unit, -4., 4.);
}

inline double dx(double x, double from, double width) {
    return width > 0. ? std::remainder(x - from, width) : x - from;
}

inline double wrapped(double x, double width) {
    if (width <= 0.) return x;
    const auto w = std::fmod(x, width);
    return w < 0. ? w + width : w;
}

inline Features features(const View& view, const std::string& side, const J& command, const J& plan) {
    const auto& me = *view.player(side);
    const auto& foe = *view.player(side == "plant" ? "zombie" : "plant");
    const auto x = plan.at("x").get<double>(), y = plan.at("y").get<double>();
    const auto tile = std::max(1., view.tile), width = std::max(1., view.width);
    const std::string key = command.at("card");
    double own_near = 0., enemy_near = 0., same_near = 0., enemy_air = 0., own_graves = 0.;
    double nearest = 12. * tile, grave_dx = 0., grave_dy = 0.;
    for (const auto& u : view.units) {
        if (u.hp <= 0.) continue;
        const double hx = dx(u.x, x, width), hy = u.y - y;
        const bool close = std::abs(hx) <= 5. * tile && std::abs(hy) <= 3. * tile;
        if (command.contains("grave") && command["grave"].is_string()
            && u.id == command["grave"].get_ref<const std::string&>()) {
            grave_dx = hx;
            grave_dy = hy;
        }
        if (u.side == view.team) {
            own_near += close;
            own_graves += close && u.behavior == "grave";
            same_near += close && key == u.card_id;
        } else {
            enemy_near += close;
            enemy_air += close && u.flying;
            nearest = std::min(nearest, std::abs(hx) + std::abs(hy));
        }
    }
    const auto card = plan.at("card");
    const std::string behavior = card.value("behavior", std::string{});
    const bool producer = card.value("producer", J(false)) == J(true) || behavior == "grave";
    return {
        scale(view.time, 300.), scale(me.resource, 250.), me.hp / std::max(1., me.max_hp),
        foe.hp / std::max(1., foe.max_hp), scale(dx(x, me.x, width), 5. * tile),
        scale(y - me.y, 3. * tile), scale(dx(x, foe.x, width), 5. * tile),
        scale(y - foe.y, 3. * tile), y / std::max(1., view.height), scale(plan.value("charge", 0.), 150.),
        double(producer), double(behavior == "grave"), scale(own_near, 5.), scale(enemy_near, 5.),
        scale(own_graves, 3.), scale(same_near, 3.), scale(enemy_air, 3.), scale(nearest, 6. * tile),
        scale(grave_dx, 5. * tile), scale(grave_dy, 3. * tile),
        double(command.contains("grave") && command["grave"].is_string()), double(view.deathmatch),
        double(view.map_night), double(behavior == "wall"),
    };
}

inline std::vector<Choice> alternatives(Session& session, Seat seat, const std::string& side, const J& original) {
    std::vector<Choice> choices;
    const auto view = session.ai_control_view(seat);
    if (!view.player(side) || !view.player(side == "plant" ? "zombie" : "plant")) return choices;
    const auto x = original.at("x").get<double>(), y = original.at("y").get<double>();
    const J source = original.value("grave", J(nullptr));
    const auto card = original.at("card").get<std::string>();
    const auto copy = original.value("copy", J(nullptr));
    std::set<std::tuple<double,double,std::string>> seen;
    const auto add = [&](double cx, double cy, const J& grave) {
        const auto admission = session.placement(side, card, cx, cy, grave, copy);
        if (!(admission.at(0).is_null() || admission.at(0) == "") || !admission.at(1).is_object()) return;
        const auto& plan = admission.at(1);
        if (!seen.emplace(plan.at("x").get<double>(), plan.at("y").get<double>(), grave.dump()).second) return;
        J command = original;
        command["x"] = ainn::game_number(cx);
        command["y"] = ainn::game_number(cy);
        if (original.contains("grave") || !grave.is_null()) command["grave"] = grave;
        const auto v = features(view, side, command, plan);
        choices.push_back({std::move(command), v});
    };
    add(x, y, source);
    if (choices.empty()) return choices;
    for (const int offset : {-2, -1, 1, 2}) add(wrapped(x + offset * view.tile, view.width), y, source);
    for (const int offset : {-1, 1}) add(x, y + offset * view.tile, source);
    if (source.is_string() && side == "zombie") {
        std::vector<const pvz::typed72app::ai::Unit*> graves;
        for (const auto& u : view.units)
            if (u.side == seat && u.hp > 0. && u.behavior == "grave" && u.id != source.get_ref<const std::string&>())
                graves.push_back(&u);
        std::sort(graves.begin(), graves.end(), [&](const auto* a, const auto* b) {
            return std::make_pair(std::abs(dx(a->x, x, view.width)), a->id)
                 < std::make_pair(std::abs(dx(b->x, x, view.width)), b->id);
        });
        for (std::size_t i = 0; i < std::min<std::size_t>(3, graves.size()); ++i)
            add(x, y, J(graves[i]->id));
    }
    return choices;
}

struct Ranker {
    std::vector<Features> hidden;
    std::vector<double> bias, output;
    double intercept = 0.;

    explicit Ranker(const J& data)
        : hidden(data.at("hidden").get<std::vector<Features>>()),
          bias(data.at("bias").get<std::vector<double>>()),
          output(data.at("output").get<std::vector<double>>()),
          intercept(data.at("intercept").get<double>()) {
        if (hidden.empty() || hidden.size() != bias.size() || bias.size() != output.size())
            throw std::runtime_error("Invalid deploy checkpoint shape");
    }

    double score(const Features& x) const {
        double total = intercept;
        for (std::size_t i = 0; i < hidden.size(); ++i) {
            double h = bias[i];
            for (std::size_t k = 0; k < x.size(); ++k) h += hidden[i][k] * x[k];
            total += output[i] * std::max(0., h);
        }
        return total;
    }
};

class DeployPolicy {
public:
    DeployPolicy(const std::string& trace, const std::string& model, std::string side, double margin)
        : side_(std::move(side)), margin_(margin) {
        if (!trace.empty()) {
            trace_.open(trace, std::ios::binary);
            if (!trace_) throw std::runtime_error("Cannot open deploy trace");
        }
        if (!model.empty()) {
            const auto bytes = pvz::typed72app::read_file_maybe_gz(model);
            const auto root = J::parse(bytes);
            if (root.at("format") != "pvz77-deploy-rank-1" || root.at("features") != FeatureCount)
                throw std::runtime_error("Deploy checkpoint uses a different feature format");
            ranker_.emplace(root.at("sides").at(side_));
            ainn::Sha256 digest;
            digest.update(bytes);
            sha_ = digest.hex();
        }
    }

    J metadata() const {
        return ranker_ ? J{{"seat", side_}, {"margin", margin_}, {"sha256", sha_}} : J(nullptr);
    }

    J counts() const {
        return {{"choice_groups", groups_}, {"swaps", swaps_}, {"fallbacks", fallbacks_}};
    }

    template<class Send>
    std::string dispatch(Session& session, Seat seat, const std::string& side, const J& command, Send send) {
        const bool controlled = ranker_ && side == side_;
        if ((!trace_.is_open() && !controlled) || command.at("type") != "deploy")
            return send(command, false);
        const auto choices = alternatives(session, seat, side, command);
        if (choices.size() < 2) return send(command, false);
        ++groups_;
        std::size_t selected = 0;
        if (controlled) {
            auto score = ranker_->score(choices[0].features) + margin_;
            for (std::size_t i = 1; i < choices.size(); ++i) {
                const auto next = ranker_->score(choices[i].features);
                if (next > score) { score = next; selected = i; }
            }
        }
        auto error = send(selected ? choices[selected].command : command, false);
        if (selected) {
            if (error.empty()) ++swaps_;
            else {
                ++fallbacks_;
                selected = 0;
                error = send(command, true);
            }
        }
        if (trace_.is_open() && error.empty()) {
            J inputs = J::array();
            for (const auto& candidate : choices) inputs.push_back(candidate.features);
            trace_ << J{{"side", side}, {"tick", session.tick()}, {"card", command.at("card")},
                       {"label", 0}, {"executed", selected}, {"features", std::move(inputs)}}.dump() << '\n';
            if (!trace_) throw std::runtime_error("Deploy trace write failed");
        }
        return error;
    }

private:
    std::ofstream trace_;
    std::optional<Ranker> ranker_;
    std::string side_, sha_;
    double margin_;
    std::uint64_t groups_ = 0, swaps_ = 0, fallbacks_ = 0;
};

} // namespace deploy_research
