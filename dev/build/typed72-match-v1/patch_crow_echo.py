"""pvp61_content.crow_echo (pvp61_content.py:307-322) emits crow_echo(source, scarecrow, entity) after the
echo child is spawned. The most-derived chain fixture threw ("echo event outside gate/finish fixture")."""
from pathlib import Path
p=Path(__file__).with_name('match_probe.cpp');t=p.read_text(encoding='utf8')
if 'void crow_echo_event(' in t:raise SystemExit('already patched')
a='    void poison_damage(const Field<std::string>& entity,double amount,int level)override{\n'
assert t.count(a)==1
t=t.replace(a,'''    void crow_echo_event(const std::string& source,const Field<std::string>& scarecrow,const std::string& child)override{
        log_event({{"event","crow_echo"},{"source",source},{"scarecrow",scarecrow.present()&&!scarecrow.is_null()?J(scarecrow.get()):J(nullptr)},{"entity",child}});
    }
'''+a)
p.write_text(t,encoding='utf8');print('ok')
