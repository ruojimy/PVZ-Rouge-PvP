"""Launch the installed experimental APK's isolated live-touch scene."""
import argparse
from datetime import datetime
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--adb',default='C:/Users/xiech/android-sdk/platform-tools/adb.exe')
    p.add_argument('--serial')
    p.add_argument('--arm',choices=['metadata','stateview'],default='metadata')
    a=p.parse_args()
    serial=a.serial
    if not serial:
        lines=subprocess.check_output([a.adb,'devices'],text=True,timeout=15).splitlines()[1:]
        online=[line.split()[0] for line in lines if len(line.split())>=2 and line.split()[1]=='device']
        if len(online)!=1:raise SystemExit('Expected one online ADB device; connect the phone or supply --serial.')
        serial=online[0]
    package=subprocess.check_output([a.adb,'-s',serial,'shell','dumpsys','package',
        'org.pvzrouge.pvzpvpnative'],text=True,encoding='utf8',errors='replace',timeout=15)
    match=re.search(r'^\s*versionName=(\S+)',package,re.M)
    supported={'1.6.0.74.3-typed.20261114-metadata-c1':1114084,
               '1.6.0.74.3-typed.20261114-r4':1114085}
    if not match or match.group(1) not in supported:raise SystemExit('Install the metadata candidate or r4 release first.')
    installed_name=match.group(1);code=supported[installed_name]
    out=ROOT/'test_results/pvp744'/('android-manual-'+datetime.now().strftime('%Y%m%d-%H%M%S'))
    out.mkdir(exist_ok=False)
    cfg=dict(name='live-touch-'+a.arm,scenario='grabber',units=120,seconds=180,
      interactive_input=True,audit_userdata=True,engine_options=dict(PVP744_PACING=True,
      PVP744_STEP_BUDGET_MS=8,PVP744_VIEW_REUSE=True,PVP744_LOCAL_FRAME=True,
      PVP744_STATE_VIEW=True,PVP744_METADATA_VIEW=a.arm=='metadata'))
    plan=out/'plan.json';plan.write_text(json.dumps([cfg],indent=2),'utf8')
    print('Live touch enabled for 180 seconds; isolated test data and normal cooldowns.',flush=True)
    subprocess.run([sys.executable,'-X','utf8',str(ROOT/'tools/pvp743_android_scenes.py'),
      '--adb',a.adb,'--serial',serial,'--plan',str(plan),'--out',str(out/'run'),
      '--build','1.6.0.74.3-typed.20261114','--installed-name',installed_name,
      '--code',str(code)],cwd=ROOT,check=True)

if __name__=='__main__':main()
