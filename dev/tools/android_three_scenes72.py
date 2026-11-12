"""Prepared for post-package device testing; never guesses a serial or port.

Uses the signed production APK's explicit diagnostic intent. Player userdata
is neither replaced nor edited. No pairing, installation or proxy changes.
"""
import argparse,base64,json,re,subprocess,time
from pathlib import Path
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--adb',required=True);ap.add_argument('--serial',required=True);ap.add_argument('--server-port',type=int,default=5037)
    ap.add_argument('--package',default='org.pvzrouge.pvzpvpnative');ap.add_argument('--out',required=True);ap.add_argument('--rounds',type=int,default=3)
    ap.add_argument('--render-stats',action='store_true',help='Enable diagnostic counters; use separate runs for timing')
    args=ap.parse_args();out=Path(args.out).resolve();out.mkdir(parents=True,exist_ok=False)
    if args.rounds<1 or not 1<=args.server_port<=65535:raise ValueError('Invalid rounds or ADB server port')
    if not re.fullmatch(r'[A-Za-z0-9_.]+',args.package):raise ValueError('Invalid package name')
    adb=[args.adb,'-P',str(args.server_port),'-s',args.serial]
    def command(*a,check=True):
        result=subprocess.run(adb+list(a),stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=40)
        if check and result.returncode:raise RuntimeError(result.stdout.decode('utf8',errors='replace'))
        return result.stdout.decode('utf8',errors='replace').strip()
    command('get-state')
    (out/'device.txt').write_text(command('shell','getprop'),encoding='utf8')
    (out/'package-before.txt').write_text(command('shell','dumpsys','package',args.package),encoding='utf8')
    for round_no in range(args.rounds):
        for scene,units in [('ordinary',20),('mixed',60),('barrage',120)]:
            label='r%d-%s%d'%(round_no,scene,units);case=out/label;case.mkdir()
            config={'scenario':scene,'units':units,'warmup_seconds':5,'seconds':30,'world_quality':'native','display_filter':'pixel','optimized':True,'detail':False}
            encoded=base64.b64encode(json.dumps(config).encode()).decode()
            command('shell','am','force-stop',args.package)
            previous=command('shell','ls','-1','/sdcard/Android/data/'+args.package+'/files/reports',check=False).splitlines()
            launch=['shell','am','start','-W','-n',args.package+'/org.pvzrouge.pvzpvpnative.PvPActivity','--es','pvp72_diagnostic_b64',encoded]
            if args.render_stats:launch+=['--ez','pvp72_render_stats','true']
            command(*launch)
            started=time.monotonic();report=None
            while time.monotonic()-started<180:
                paths=command('shell','ls','-1','/sdcard/Android/data/'+args.package+'/files/reports',check=False).splitlines()
                fresh=[p for p in paths if p not in previous and p.endswith('.json') and not p.endswith('.live.json')]
                for name in fresh:
                    remote='/sdcard/Android/data/'+args.package+'/files/reports/'+name
                    raw=command('shell','cat',remote,check=False)
                    try:value=json.loads(raw)
                    except ValueError:continue
                    # The probe first writes completed=true; the native entry
                    # then adds native72 metadata. Wait for that final report.
                    if value.get('completed') and '.72' in value.get('native72',{}).get('build',''):
                        command('pull',remote,str(case/'report.json'));report=value;break
                if report:break
                time.sleep(2)
            (case/'battery.txt').write_text(command('shell','dumpsys','battery'),encoding='utf8')
            if not report:raise RuntimeError('No completed production diagnostic report: '+label)
            if report.get('native72',{}).get('build','').find('.72')<0:raise RuntimeError('Report is not a 72 candidate')
            if args.render_stats and not report['native72'].get('render_stats_enabled'):raise RuntimeError('Requested render counters are unavailable')
            print('COMPLETE',label,flush=True)
    (out/'package-after.txt').write_text(command('shell','dumpsys','package',args.package),encoding='utf8')
if __name__=='__main__':main()
