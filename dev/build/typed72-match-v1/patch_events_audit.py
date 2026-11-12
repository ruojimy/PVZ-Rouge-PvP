"""Event callbacks whose most-derived match-chain definition only filled a fixture list:
  cart_lifecycle.py:38      _emit('cart_expired', entity, card, seconds)
  pvp56_plants.py:153       _emit('asparagus_sweep', source, angle, facing)
  pvp66_secrets.py:204      _emit('lantern_burn', entity, targets)
  native_gravebuster.py:75,155,171 via on_event=self._emit (native_battle.py:224):
      grave_consume_started / grave_consumed / grave_consume_cancelled(source_entity, target, native_tick[, reason])
The bridge's on_consume is not wired in the source, so grave_consumed(unit, plant) stays a no-op."""
from pathlib import Path
p=Path(__file__).with_name('match_probe.cpp');t=p.read_text(encoding='utf8')
if 'void cart_expired(' in t:raise SystemExit('already patched')
a='    void crow_echo_event(const std::string& source,const Field<std::string>& scarecrow,const std::string& child)override{\n'
assert t.count(a)==1
t=t.replace(a,'''    static J opt_text(const Field<std::string>& f){return f.present()&&!f.is_null()?J(f.get()):J(nullptr);}
    void cart_expired(const Field<std::string>& entity,const Field<std::string>& card,double seconds)override{
        log_event({{"event","cart_expired"},{"entity",opt_text(entity)},{"card",opt_text(card)},{"seconds",seconds}});
    }
    void flying_sweep(const FlyingSweepEvent& e)override{
        log_event({{"event","asparagus_sweep"},{"source",opt_text(e.source)},{"angle",e.angle},{"facing",e.facing}});
    }
    void lantern_burn(const Field<std::string>& id,size_t hits)override{
        log_event({{"event","lantern_burn"},{"entity",opt_text(id)},{"targets",hits}});
    }
    void grave_consumed(const ZombieRef&,const PlantRef&)override{}
    void grave_event(GraveBindingEvent e)override{
        static const char* names[]={"grave_consume_started","grave_consumed","grave_consume_cancelled"};
        J row{{"event",names[size_t(e.kind)]},{"source_entity",opt_text(e.source_id)},{"target",e.target_id},{"native_tick",e.native_tick}};
        if(e.reason==GraveBindingReason::plant_unavailable)row["reason"]="plant_unavailable";
        else if(e.reason==GraveBindingReason::target_unavailable)row["reason"]="target_unavailable";
        log_event(row);
    }
'''+a)
p.write_text(t,encoding='utf8');print('ok')
