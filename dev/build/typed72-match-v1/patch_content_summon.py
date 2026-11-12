"""native_content.NativeContent.summon emits content_summon(source, entity, card, owner) for every
controller summon (pirate parrots, imp cannon, ...). Only the PvP56 dancer path was logged; the
NativeSummons callback content_summoned still filled the fixture list (long_cards_z3)."""
from pathlib import Path
p=Path(__file__).with_name('match_probe.cpp');t=p.read_text(encoding='utf8')
if 'void content_summoned(' in t:raise SystemExit('already patched')
a='    void cart_expired(const Field<std::string>& entity,const Field<std::string>& card,double seconds)override{\n'
assert t.count(a)==1
t=t.replace(a,'''    void content_summoned(const Field<std::string>& source,const std::string& entity,const std::string& card,Seat owner)override{
        log_event({{"event","content_summon"},{"source",opt_text(source)},{"entity",entity},{"card",card},{"owner",seat_name(owner)}});
    }
'''+a)
p.write_text(t,encoding='utf8');print('ok')
