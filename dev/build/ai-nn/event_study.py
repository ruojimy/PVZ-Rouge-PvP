"""Family-independent action selection on changes in public native match state."""
import re
import shutil
import sys
from pathlib import Path

import numpy as np
from advantage_study import OUT as LAST,ROOT,R,H,BUILD,EXPORT,PARENT,STRONG,PROGRAM,OLD_Z,PLANTS,deck,fixed,inputs_ok,read,sha,cmd
from position_build import replace_once

OUT=ROOT/'event'
CORPUS=OUT/'plain'
NATIVE=OUT/'native/Release/position_match.exe'
START=OUT/'models/event-start.json'
PROBE=OUT/'probe-native/Release/position_match.exe'
LIVE=OUT/'live-native/Release/position_match.exe'

def setup():
    inputs_ok()
    for p in (OUT,OUT/'temp',OUT/'models'):p.mkdir(exist_ok=True)
    fixed(OUT/'plan.json',dict(parent=sha(PARENT),plant=sha(STRONG),position=sha(OLD_Z),native=sha(PROGRAM),
        data='8 train and 6 validation home openings; two sealed cohorts of 12, six night each. Exclude historical seeds and exact per-seat decks from test.',
        train='Freeze strong plant-1p, O and r22. Sample native event choices on training openings, including older development starts. Roll out alternatives with unique immediate command identities and reuse the native default trajectory. Fit shared state-action residuals, compare strengths on validation for old win retention, worst rival and net. Freeze event zombie then train plant with r22 anchor.',
        test='Compare singleseat substitutions with previous z16 and plant-1p on both cohorts versus r22, H and B. Group by old zero-trigger, preserve original wins, examine timing, extend loss to timeout to 1200. Stable requires retained original wins, positive in both cohorts, no negative opponent per cohort, positive pooled opening-bootstrap lower bound and no joint slowdown credit.'))

def prepare():
    setup()
    if (OUT/'splits.json').exists():
        assert sha(CORPUS/'index.json')==read(OUT/'splits.json')['corpus'];return
    paths=[*(R/s for s in read(ROOT/'splits.json')['past_indexes']),ROOT/'plain/index.json',ROOT/'confirm/plain/index.json',LAST/'plain/index.json']
    known=[set(),set()];seeds=set()
    for p in paths:
        for r in read(p)['entries']:
            if r.get('map')=='家院' and 'decks' in r:
                seeds.add(r['seed'])
                for names,d in zip(known,deck(r)):names.add(d)
    pool=[];rng=np.random.default_rng(816701)
    for n in range(24):
        path=OUT/f'draft-{n}.json'
        if not path.exists():cmd(EXPORT/'deck73_corpus.exe',path,3,16,2370000+10000*n,71401+127*n)
        pool.extend(r for r in read(path) if r.get('map')=='家院' and r['seed'] not in seeds and not r.get('error') and not r.get('invalid'))
        for _ in range(60):
            used=[set(x) for x in known];held=[]
            for j in range(24):
                valid=[r for r in pool if bool(r['night'])==bool(j%2) and all(d not in k for d,k in zip(deck(r),used))]
                if not valid:break
                row=valid[rng.integers(len(valid))];held.append(row)
                for k,d in zip(used,deck(row)):k.add(d)
            if len(held)==24:break
        if len(held)<24:continue
        banned=[{deck(r)[j] for r in held} for j in range(2)]
        dev=[]
        for j in range(14):
            valid=[r for r in pool if bool(r['night'])==bool(j%2) and all(d not in k for d,k in zip(deck(r),banned))]
            if not valid:break
            row=valid[rng.integers(len(valid))];dev.append(row)
            for k,d in zip(banned,deck(row)):k.add(d)
        if len(dev)==14:break
    assert len(held)==24 and len(dev)==14
    cases=dev+held
    assert len({r['seed'] for r in cases})==len(cases)
    for j in range(2):
        assert len({deck(r)[j] for r in cases})==len(cases)
        assert not {deck(r)[j] for r in held}&known[j]
    fixed(OUT/'scenarios.json',cases)
    cmd(sys.executable,H/'export_corpus.py',OUT/'scenarios.json',OUT/'corpus',3,EXPORT/'cold73_export.exe')
    cmd(sys.executable,H/'materialize_corpus.py',OUT/'corpus',CORPUS)
    rows=read(CORPUS/'index.json')['entries'];assert [(r['seed'],deck(r)) for r in rows]==[(r['seed'],deck(r)) for r in cases]
    ids=[r['id'] for r in rows]
    fixed(OUT/'splits.json',dict(train=ids[:8],val=ids[8:14],a=ids[14:26],b=ids[26:],corpus=sha(CORPUS/'index.json'),
        exclusions=list(map(len,known)),historical_indexes=[str(p.relative_to(R)) for p in paths]))

def frozen_build(name,binary,source):
    path=OUT/name
    if not path.exists():return False
    receipt=read(path)
    assert sha(binary)==receipt['binary']
    assert all(sha(source/n)==v for n,v in receipt['sources'].items())
    assert all(sha(BUILD/'Release'/n)==v for n,v in receipt['libraries'].items())
    return True

def build():
    old=LAST/'native-src';dest=OUT/'native-src';dest.mkdir(exist_ok=True)
    rng=np.random.default_rng(336711)
    fixed(START,dict(format='pvz-event-actions-1',sim_fingerprint=read(PARENT)['sim_fingerprint'],legacy=read(PARENT),
        position_parent=sha(OLD_Z),event_hidden=rng.normal(0,.25,(8,24)).tolist(),event_bias=[0.]*8,event_head=[0.]*8,scale=0.))
    if frozen_build('build.json',NATIVE,dest):return
    receipt=read(LAST/'build.json')
    assert all(sha(old/n)==s for n,s in receipt['sources'].items())
    for p in old.iterdir():
        if p.is_file():shutil.copyfile(p,dest/p.name)
    shutil.copyfile(H/'event_policy.inc',dest/'event_policy.inc')
    p=dest/'option_control.inc';s=p.read_text('utf8')
    s=replace_once(s,'inline void configure_options','inline void load_event(const ainn::J&);\ninline void configure_options')
    s=replace_once(s,'if(option_policy.at("format")','''if(option_policy.at("format")=="pvz-event-actions-1"){
        load_event(option_policy);
        auto legacy=option_policy.at("legacy");option_policy=std::move(legacy);
    }
    if(option_policy.at("format")''')
    s=replace_once(s,'    static OptionState observe','public:\n    static OptionState observe')
    p.write_text(s,'utf8')
    p=dest/'position_head.h';s=p.read_text('utf8')
    s=replace_once(s,'class Tactics {','#include "event_policy.inc"\nclass Tactics {\n    EventChoices event_choices;')
    s=replace_once(s,'bool at_order=v.time','const int mask=event_enabled?event_choices.changes(v,service):0;\n        bool at_order=mask || v.time')
    s=replace_once(s,'if(at_order||flag_due){','''if(event_enabled&&!mask&&!arrived&&!target_card.empty()&&v.time<move_until)at_order=false;
        if(at_order||flag_due){''')
    s=replace_once(s,'options.apply(list,b,service);','''if(event_enabled){
                    event_choices.choose(list,b,service,hint,mask,jump_at);
                    target_card.clear();move_until=0.;
                }else options.apply(list,b,service);''')
    s=replace_once(s,'if(!options.traveling() &&','if(!event_enabled && !options.traveling() &&')
    p.write_text(s,'utf8')
    p=dest/'position_match.cpp';s=p.read_text('utf8')
    s=replace_once(s,'if(kind=="rally"||kind=="deploy")commands.push_back(event);',
        'if(kind=="rally"||kind=="deploy"||(position_ai::event_enabled && kind=="move" && event.at("tick")==position_ai::event_log_tick))commands.push_back(event);')
    p.write_text(s,'utf8')
    cmake=re.search('^CMAKE_COMMAND:INTERNAL=(.+)$',(BUILD/'CMakeCache.txt').read_text('utf8'),re.M).group(1)
    cmd(cmake,'-S',dest,'-B',OUT/'native','-G','Visual Studio 17 2022','-A','x64')
    cmd(cmake,'--build',OUT/'native','--config','Release','--parallel',2)
    shutil.copyfile(BUILD/'Release/SDL2.dll',NATIVE.parent/'SDL2.dll')
    fixed(OUT/'build.json',dict(binary=sha(NATIVE),sources={p.name:sha(p) for p in dest.iterdir()},libraries=receipt['libraries']))

def build_probes():
    src=OUT/'native-src';dest=OUT/'probe-src';dest.mkdir(exist_ok=True)
    if frozen_build('probe-build.json',PROBE,dest):return
    receipt=read(OUT/'build.json')
    for name,digest in receipt['sources'].items():
        assert sha(src/name)==digest;shutil.copyfile(src/name,dest/name)
    p=dest/'event_policy.inc';s=p.read_text('utf8')
    s=replace_once(s,'double next_probe=0.;','double next_probe=0.;std::array<double,4> next_reason{};')
    s=replace_once(s,'const bool probe=mask && (b.v.time>=next_probe||fork);','''bool fresh_reason=false;
        for(int i=0;i<4;++i)if((mask&(1<<i))&&b.v.time>=next_reason[i]){
            fresh_reason=true;next_reason[i]=b.v.time+18.;
        }
        const bool probe=mask && (fresh_reason||b.v.time>=next_probe||fork);''')
    start=s.index('            const auto& first_action=');end=s.index('\n        }\n        const size_t chosen=',start)
    s=s[:start]+'''            add([](const Action& a){return a.kind==spawn;});
            const Action* ref=nullptr;
            for(size_t i:picks)if(ranked[i].action.kind==spawn){ref=&ranked[i].action;break;}
            if(ref){
                add([&](const Action& a){return a.kind==spawn&&a.card!=ref->card&&a.source==ref->source;});
                add([&](const Action& a){return a.kind==spawn&&a.source!=ref->source&&a.card==ref->card;});
            }
            add([&](const Action& a){return a.kind==approach&&b.direction*b.dx(b.me.x,a.x)>1.25;});
            add([](const Action& a){return a.kind==wait;});
            while(picks.size()<6&&add([](const Action&){return true;})){}'''+s[end:]
    p.write_text(s,'utf8')
    p=dest/'position_match.cpp';p.write_text(replace_once(p.read_text('utf8'),'o.forced_option>3','o.forced_option>5'),'utf8')
    cmake=re.search('^CMAKE_COMMAND:INTERNAL=(.+)$',(BUILD/'CMakeCache.txt').read_text('utf8'),re.M).group(1)
    cmd(cmake,'-S',dest,'-B',OUT/'probe-native','-G','Visual Studio 17 2022','-A','x64')
    cmd(cmake,'--build',OUT/'probe-native','--config','Release','--parallel',2)
    shutil.copyfile(BUILD/'Release/SDL2.dll',PROBE.parent/'SDL2.dll')
    fixed(OUT/'probe-build.json',dict(binary=sha(PROBE),sources={p.name:sha(p) for p in dest.iterdir()},libraries=receipt['libraries']))

def build_live():
    src=OUT/'probe-src';dest=OUT/'live-src';dest.mkdir(exist_ok=True)
    if frozen_build('live-build.json',LIVE,dest):return
    receipt=read(OUT/'probe-build.json')
    for name,digest in receipt['sources'].items():
        assert sha(src/name)==digest;shutil.copyfile(src/name,dest/name)
    p=dest/'event_policy.inc';s=p.read_text('utf8')
    s=replace_once(s,'class EventChoices {','''inline std::function<std::optional<double>(const std::string&,double,double,const std::optional<std::string>&,bool,bool)> native_price;
class EventChoices {
    std::map<std::string,double> prices;
    std::size_t last_units=0;double last_resource=-1.;''')
    s=replace_once(s,'    int changes(','''    double price(const std::string& key,double fallback) const {
        auto it=prices.find(key);return it==prices.end()?fallback:it->second;
    }
    int changes(''')
    s=replace_once(s,'        for(const auto& k:me.deck)', '''        std::size_t units=0;
        for(const auto& u:v.units)if(u.hp>0.)units^=std::hash<std::string>{}(u.id);
        const bool refresh=first||last_resource!=me.resource||last_units!=units;
        last_resource=me.resource;last_units=units;
        for(const auto& k:me.deck)''')
    s=replace_once(s,'            if(me.resource>=c.cost)affordable.insert(k);','''            if(refresh){
                std::optional<double> quote;
                if(native_price){
                    if(c.behavior=="grave")quote=native_price(k,me.x,me.y,{},true,false);
                    else for(const auto& u:v.units)if(graves.count(u.id)){
                        quote=native_price(k,u.x,u.y-24.,u.id,true,false);if(quote)break;
                    }
                }
                prices[k]=quote.value_or(c.cost);
            }
            if(me.resource>=price(k,c.cost))affordable.insert(k);''')
    s=replace_once(s,'        return service.preview(a.card,a.x,a.y,src,false).empty();',
        '''        if(native_price && a.kind!=approach)return native_price(a.card,a.x,a.y,src,false,true).has_value();
        return service.preview(a.card,a.x,a.y,src,false).empty();''')
    p.write_text(s,'utf8')
    p=dest/'position_head.h';s=p.read_text('utf8')
    s=replace_once(s,'if(card.cost>me.resource','const double cost=event_enabled?event_choices.price(key,card.cost):card.cost;\n                    if(cost>me.resource')
    s=replace_once(s,'key,grave,card.cost,hp','key,grave,cost,hp');p.write_text(s,'utf8')
    p=dest/'tactical_session.cpp';s=p.read_text('utf8')
    s=replace_once(s,'AiServices(TypedSession& s,Seat owner,const ai::View& v):s_(s),owner_(owner),view_(v){}',
        '''AiServices(TypedSession& s,Seat owner,const ai::View& v):s_(s),owner_(owner),view_(v){}
        std::optional<double> quote(const std::string& key,double x,double y,const std::optional<std::string>& grave,bool unbounded,bool actual){
            std::optional<double> price;
            inspect(key,x,y,grave,unbounded,actual,&price);
            return price;
        }''')
    s=replace_once(s,'bool unbounded)override{\n            auto& m=*s_.match_;',
        '''bool unbounded)override{
            return inspect(key,x,y,grave,unbounded,false,nullptr);
        }
        std::string inspect(const std::string& key,double x,double y,const std::optional<std::string>& grave,bool unbounded,bool actual,std::optional<double>* price){
            auto& m=*s_.match_;''')
    s=replace_once(s,'            m.deployment.ranked=false;','            if(!actual)m.deployment.ranked=false;')
    s=replace_once(s,'if(r.error.empty()&&!r.plan)return "no placement";','''if(r.error.empty()&&!r.plan)return "no placement";
            if(price&&r.error.empty()&&r.plan)*price=r.plan->charge;''')
    s=replace_once(s,'if(tactical){slot->send={};tactics_.step(view,*field_,services,suggestions,send);}',
        '''if(tactical){
            slot->send={};
            if(position_ai::event_enabled)position_ai::native_price=[&](const std::string& key,double x,double y,const std::optional<std::string>& grave,bool unbounded,bool actual){
                return services.quote(key,x,y,grave,unbounded,actual);};
            tactics_.step(view,*field_,services,suggestions,send);
            position_ai::native_price={};
        }''');p.write_text(s,'utf8')
    cmake=re.search('^CMAKE_COMMAND:INTERNAL=(.+)$',(BUILD/'CMakeCache.txt').read_text('utf8'),re.M).group(1)
    cmd(cmake,'-S',dest,'-B',OUT/'live-native','-G','Visual Studio 17 2022','-A','x64')
    cmd(cmake,'--build',OUT/'live-native','--config','Release','--parallel',2)
    shutil.copyfile(BUILD/'Release/SDL2.dll',LIVE.parent/'SDL2.dll')
    fixed(OUT/'live-build.json',dict(binary=sha(LIVE),sources={p.name:sha(p) for p in dest.iterdir()},libraries=receipt['libraries']))

def run(stage):
    setup()
    if stage=='prepare':prepare()
    elif stage=='build':build()
    elif stage=='probe-build':build_probes()
    elif stage=='live-build':build_live()
    elif stage in ('gate-test','price-test'):
        quoted=stage=='price-test'
        dest=OUT/('live-gate-src' if quoted else 'gate-src');dest.mkdir(exist_ok=True)
        header=OUT/('live-src' if quoted else 'native-src')
        test_source=H/'event_gate_test.cpp'
        if quoted:
            text=test_source.read_text('utf8')
            marker='    std::cout<<"11/11'
            text=replace_once(text,marker,'''    cards.item.behavior="grave";
    double current_price=17.;
    native_price=[&](const auto&,double,double,const auto&,bool unbounded,bool actual)->std::optional<double>{
        if(!unbounded||actual)throw std::runtime_error("invalid price inquiry");
        return current_price;};
    EventChoices quoted;
    v.players[0].resource=9.;if(quoted.changes(v,cards)!=16)throw std::runtime_error("init quote");
    v.players[0].resource=10.;if(quoted.changes(v,cards)!=0)throw std::runtime_error("base cost false positive");
    v.players[0].resource=17.;if(quoted.changes(v,cards)!=8)throw std::runtime_error("effective price crossing");
    current_price=21.;v.players[0].resource=18.;if(quoted.changes(v,cards)!=0)throw std::runtime_error("price increased");
    v.players[0].resource=21.;if(quoted.changes(v,cards)!=8)throw std::runtime_error("new effective crossing");
    native_price={};
    std::cout<<"5/5 native quote checks; ";
'''+marker)
            test_source=dest/'event_price_test.cpp';test_source.write_text(text,'utf8')
        contents=(OUT/'native-src/CMakeLists.txt').read_text('utf8')
        contents=replace_once(contents,'position_match.cpp tactical_session.cpp',f'"{test_source.as_posix()}"')
        contents=replace_once(contents,'target_include_directories(position_match PRIVATE',
            f'target_include_directories(position_match PRIVATE "{header.as_posix()}"')
        (dest/'CMakeLists.txt').write_text(contents,'utf8')
        cmake=re.search('^CMAKE_COMMAND:INTERNAL=(.+)$',(BUILD/'CMakeCache.txt').read_text('utf8'),re.M).group(1)
        cmd(cmake,'-S',dest,'-B',OUT/stage,'-G','Visual Studio 17 2022','-A','x64')
        cmd(cmake,'--build',OUT/stage,'--config','Release','--parallel',1)
        cmd(OUT/stage/'Release/position_match.exe')
        fixed(OUT/(stage+'.json'),dict(assertions=16 if quoted else 11,header=sha(header/'event_policy.inc'),test=sha(test_source)))
    else:
        from event_fit import run_stage
        run_stage(stage)
