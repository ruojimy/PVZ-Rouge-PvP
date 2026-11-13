"""Isolated, offscreen application differential and timing; never opens the user's match."""
import argparse,hashlib,json,os,shutil,subprocess,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
FLAGS=['PVP742_FRAME','PVP742_RECIPE_KEY','PVP742_WALL_CLOCK','PVP742_LAZY_CANVAS','PVP742_INPUT_REFRESH','PVP742_TARGETING']
def main():
 p=argparse.ArgumentParser();p.add_argument('--out',required=True);p.add_argument('--ticks',type=int,default=180);p.add_argument('--profile',action='store_true');p.add_argument('--verify',action='store_true');args=p.parse_args()
 out=Path(args.out).resolve();out.mkdir(parents=True,exist_ok=False);exe=ROOT/'build/app-typed72-v2/Release/PvZPvPNative.exe';exe_sha=hashlib.sha256(exe.read_bytes()).hexdigest();rows=[]
 for scene,units in [('ordinary',20),('mixed',120),('barrage',240),('grabber',120)]:
  pair=[]
  for enabled in (False,True):
   d=out/(scene+('-current' if enabled else '-reference'));d.mkdir()
   cfg=dict(scenario=scene,units=units,durable_units=True,unit_hp=1e8,warmup_room_ticks=30,measure_room_ticks=args.ticks,warmup_seconds=1,seconds=max(1,args.ticks/30),world_quality='native',display_filter='pixel',display_budget=False,optimized=True,detail=False,prime_tentacles=scene=='grabber',function_profile=args.profile,engine_options={k:enabled for k in FLAGS})
   config=d/'config.json';config.write_text(json.dumps(cfg),encoding='utf8')
   env=dict(os.environ,SDL_VIDEODRIVER='dummy',SDL_AUDIODRIVER='dummy',PVP_USERDATA=str(d/'userdata'),PVP741_PRESSURE='0',PVP742_ALLOCATOR='1' if enabled else '0')
   env.update({k:'1' if enabled else '0' for k in FLAGS})
   env.pop('PVP741_PROFILE',None);env.pop('PVP742_VERIFY_FRAME',None)
   if args.verify and enabled:env['PVP742_VERIFY_FRAME']='1'
   if args.profile:env['PVP741_PROFILE']='1'
   started=time.time()
   with (d/'stdout.log').open('wb') as stdout,(d/'stderr.log').open('wb') as stderr:
    r=subprocess.run([str(exe),'--diagnostic',str(config)],cwd=str(ROOT),env=env,stdout=stdout,stderr=stderr,timeout=900,creationflags=0x08000000)
   logs=(d/'stdout.log').read_text('utf8',errors='replace')+(d/'stderr.log').read_text('utf8',errors='replace')
   if r.returncode:raise RuntimeError(logs[-4000:])
   source=Path([s.split('PVP72_DIAGNOSTIC_COMPLETE',1)[1].strip() for s in logs.splitlines() if 'PVP72_DIAGNOSTIC_COMPLETE' in s][-1]);shutil.copyfile(source,d/'report.json');shutil.copyfile(source.with_suffix('.png'),d/'frame.png')
   j=json.loads(source.read_text('utf8'));assert j['completed']
   assert bool(j['backend_audit']['frame_descriptions'])==enabled,'frame projection branch switch was not effective'
   assert j['native72']['small_allocator']['legacy'] != enabled,'allocator startup switch was not effective'
   for v in j['backend_audit']['dynamic_v_work'].values():assert v['boxes']==v['calls']==0,'dynamic V in typed hot loop'
   pair.append(j);row=dict(scene=scene,current=enabled,wall_seconds=time.time()-started,state=j['final_state_sha256'],rng=j['final_rng_sha256'],canvas=j['final_canvas_sha256'],fps=j['presentation']['frames_per_second'],frames=j['frames'],presentation=j['presentation'],phases=j.get('phases'),backend_audit=j['backend_audit'],native72=j['native72'])
   for field in ('frame_phases_cpu_ms','frame_phases_ms','native_phases_ms','runtime','ui_caches','simulation_wall_ratio','simulated_seconds','wall_seconds','scheduling'):row[field]=j.get(field)
   rows.append(row);print({k:v for k,v in row.items() if k in ('scene','current','wall_seconds','fps','frames')},flush=True)
  for field in ('final_state','final_native_entities','final_rng_sha256'):assert pair[0][field]==pair[1][field],scene+' '+field+' differs'
  (out/'summary.json').write_text(json.dumps(dict(passed=True,exe_sha256=exe_sha,room_ticks=args.ticks,profile=args.profile,verify=args.verify,scope='SDL dummy offscreen application; includes simulation, publication and software drawing. Fixed logical ticks; full combat state/native frame/RNG equality. Whole application canvas HUD timing is reported separately.',runs=rows),ensure_ascii=False,indent=2),encoding='utf8')
 return 0
if __name__=='__main__':raise SystemExit(main())
