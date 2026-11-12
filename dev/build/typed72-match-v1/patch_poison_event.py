"""native_status.py:65 b._emit('poison_damage', entity=obj.get('_pvp_id'), amount=amount, level=level):
the match used the fixture stub, so the typed poison tick never reached the event log (secrets_3)."""
from pathlib import Path
p=Path(__file__).with_name('match_probe.cpp');t=p.read_text(encoding='utf8')
if 'void poison_damage(' in t:raise SystemExit('already patched')
a='    void petrified_resource(double amount,Point point)override{'
assert t.count(a)==1
t=t.replace(a,'''    void poison_damage(const Field<std::string>& entity,double amount,int level)override{
        log_event({{"event","poison_damage"},{"entity",entity.present()&&!entity.is_null()?J(entity.get()):J(nullptr)},{"amount",amount},{"level",level}});
    }
'''+a)
p.write_text(t,encoding='utf8');print('ok')
