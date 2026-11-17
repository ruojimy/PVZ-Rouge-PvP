"""Regenerate the owned transport and Application.publish_network only.

The other Application methods contain reviewed native lifecycle adaptations.
Do not replace the whole module when refreshing this network-owned method.
The manifest gate works on Windows and Android/WSL without the Python reference.
"""
from pathlib import Path
import argparse, hashlib, json, re, subprocess, sys, tempfile
ROOT=Path(__file__).resolve().parents[1]
MANIFEST=ROOT/'tools/pvp743_network_sources.json'
PATTERN=r'V C_Application::m_publish_network\(const Args& A\) \{.*?(?=\nV C_Application::)'
RELAY_PATTERN=r'V C_RelayHostTransport::m_bridge\(const Args& A\) \{.*?\n\}\n'
def digest(data):return hashlib.sha256(data).hexdigest()
def write_changed(path,data):
    if not path.exists() or path.read_bytes()!=data:path.write_bytes(data)
def records():
    files=['tools/pvp72_sources/network.py','tools/pvp72_sources/app.py','tools/pvp72_sources/relay.py','src/ui/gen/pm_network.cpp','src/ui/gen/pm_network.h']
    result={name:digest((ROOT/name).read_bytes()) for name in files}
    body=re.search(PATTERN,(ROOT/'src/ui/gen/pm_app.cpp').read_text('utf8'),re.S)
    if not body:raise RuntimeError('Missing publish_network body')
    result['src/ui/gen/pm_app.cpp::publish_network']=digest(body.group().encode('utf8'))
    bridge=re.search(RELAY_PATTERN,(ROOT/'src/ui/gen/pm_relay.cpp').read_text('utf8'),re.S)
    if not bridge:raise RuntimeError('Missing relay bridge body')
    result['src/ui/gen/pm_relay.cpp::bridge']=digest(bridge.group().encode('utf8'))
    return result
def main():
    p=argparse.ArgumentParser();p.add_argument('--check',action='store_true');args=p.parse_args()
    if args.check:
        if records()!=json.loads(MANIFEST.read_text('utf8')):raise SystemExit('Stale PvP74.3 network source manifest; run tools/pvp743_network_sources.py')
        print('PvP74.3 network source manifest: checked');return
    with tempfile.TemporaryDirectory(prefix='pvp743-network-') as folder:
        target=Path(folder)/'ui/gen'
        result=subprocess.run([sys.executable,str(ROOT/'tools/pvp2cpp.py'),str(target),'app','network','relay'],cwd=ROOT,capture_output=True,text=True,encoding='utf8')
        if result.returncode or 'total TODO 0' not in result.stdout:raise RuntimeError(result.stdout+'\n'+result.stderr)
        application=ROOT/'src/ui/gen/pm_app.cpp';old=application.read_text('utf8');new=(target/'pm_app.cpp').read_text('utf8')
        a=re.search(PATTERN,old,re.S);b=re.search(PATTERN,new,re.S)
        if not a or not b:raise RuntimeError('Missing generated publish_network')
        write_changed(application,(old[:a.start()]+b.group()+old[a.end():]).encode('utf8'))
        relay=ROOT/'src/ui/gen/pm_relay.cpp';old=relay.read_text('utf8');new=(target/'pm_relay.cpp').read_text('utf8')
        a=re.search(RELAY_PATTERN,old,re.S);b=re.search(RELAY_PATTERN,new,re.S)
        if not a or not b:raise RuntimeError('Missing generated relay bridge')
        write_changed(relay,(old[:a.start()]+b.group()+old[a.end():]).encode('utf8'))
        for suffix in ('cpp','h'):
            name='pm_network.'+suffix
            write_changed(ROOT/'src/ui/gen'/name,(target/name).read_bytes())
    subprocess.run([sys.executable,str(ROOT/'tools/pvp74_apply_hooks.py')],cwd=ROOT,check=True)
    subprocess.run([sys.executable,str(ROOT/'tools/pvp741_apply_hooks.py'),'--check'],cwd=ROOT,check=True)
    MANIFEST.write_text(json.dumps(records(),indent=2)+'\n',encoding='utf8')
    print('PvP74.3 network sources regenerated; other Application methods preserved')
if __name__=='__main__':main()
