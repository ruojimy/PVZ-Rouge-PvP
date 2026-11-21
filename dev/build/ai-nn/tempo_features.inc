    std::vector<int> troop_ticks, grave_ticks;
    bool tracks_tempo() const {
        return !switch_policy.is_null() && switch_policy.value("troop_tempo", false);
    }
    void append_tempo(std::vector<double>& x, double now) const {
        if (!tracks_tempo()) return;
        const int tick = static_cast<int>(std::llround(now * 30.));
        for (const auto* ticks : {&troop_ticks, &grave_ticks}) {
            const int age = ticks->empty() ? 1800 : std::min(1800, tick - ticks->back());
            x.push_back(age / 1800.);
            for (int span : {450, 1800}) {
                const auto start = std::lower_bound(ticks->begin(), ticks->end(), tick - span);
                x.push_back(std::tanh((ticks->end() - start) / 4.));
            }
        }
    }
