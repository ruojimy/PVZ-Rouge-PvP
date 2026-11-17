"""Mix production sound events and assemble the three native gameplay captures."""
from pathlib import Path
import argparse, hashlib, json, subprocess, wave
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
FF=ROOT/'视频制作工具与记忆/runtime/ffmpeg/ffmpeg.exe'
PROBE=FF.with_name('ffprobe.exe')

def run(args):
    return subprocess.run([str(x) for x in args],check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)

def finish(source:Path,output:Path):
    output.mkdir(parents=True,exist_ok=True)
    rate=48000
    cache={};reports=[];files=[]
    for key,title in [('eye','01_克苏鲁之眼'),('worm','02_世界吞噬者'),('skeleton','03_骷髅王')]:
        data=json.loads((source/f'{key}-events.json').read_text('utf-8'))
        pcm=np.zeros((data['seconds']*rate,2),dtype=np.float32)
        mixed=0
        for event in data['audio']:
            path=Path(event['file'])
            if path not in cache:
                raw=run([FF,'-v','error','-i',path,'-f','f32le','-acodec','pcm_f32le','-ar',rate,'-ac',2,'pipe:1']).stdout
                cache[path]=np.frombuffer(raw,dtype='<f4').reshape(-1,2).copy()
            wave_data=cache[path]
            start=round(event['time']*rate);length=min(len(wave_data),len(pcm)-start)
            if length<=0:continue
            pan=event['pan'];gain=event['gain']
            volumes=np.array([gain*(1-max(0,pan)*.65),gain*(1+min(0,pan)*.65)],dtype=np.float32)
            pcm[start:start+length]+=wave_data[:length]*volumes
            mixed+=1
        peak=float(np.max(np.abs(pcm)));normalization=min(1,.92/max(peak,1e-9));pcm*=normalization
        wav=source/f'{key}.wav'
        with wave.open(str(wav),'wb') as w:
            w.setnchannels(2);w.setsampwidth(2);w.setframerate(rate);w.writeframes(np.clip(pcm*32767,-32768,32767).astype('<i2').tobytes())
        dest=output/f'{title}.mp4'
        run([FF,'-v','error','-y','-i',source/f'{key}-silent.mp4','-i',wav,'-map','0:v:0','-map','1:a:0','-c:v','copy','-c:a','aac','-b:a','192k','-shortest','-movflags','+faststart',dest])
        files.append(dest)
        probe=json.loads(run([PROBE,'-v','error','-show_streams','-show_format','-of','json',dest]).stdout)
        assert len(probe['streams'])==2 and abs(float(probe['format']['duration'])-data['seconds'])<.1
        assert mixed>0 and peak>0
        run([FF,'-v','error','-i',dest,'-f','null','-'])
        reports.append({'name':title,'seconds':data['seconds'],'audio_events':mixed,'peak_before_normalization':peak,'audio_gain':normalization,'video':str(dest),'sha256':hashlib.sha256(dest.read_bytes()).hexdigest(),'probe':probe})
    concat=source/'concat.txt'
    concat.write_text(''.join("file '"+str(p).replace('\\','/')+"'\n" for p in files),encoding='utf-8')
    metadata=source/'chapters.ffmetadata'
    offset=0;chapters=[';FFMETADATA1','title=PvP744 Terraria 三 Boss 演示']
    for r in reports:
        chapters+=['[CHAPTER]','TIMEBASE=1/1000',f'START={offset*1000}',f'END={(offset+r["seconds"])*1000}',f'title={r["name"][3:]}']
        offset+=r['seconds']
    metadata.write_text('\n'.join(chapters)+'\n',encoding='utf-8')
    combined=output/'PvP744_Terraria三Boss演示.mp4'
    run([FF,'-v','error','-y','-f','concat','-safe','0','-i',concat,'-i',metadata,'-map','0:v','-map','0:a','-map_metadata','1','-map_chapters','1','-c','copy','-movflags','+faststart',combined])
    run([FF,'-v','error','-i',combined,'-f','null','-'])
    probe=json.loads(run([PROBE,'-v','error','-show_streams','-show_format','-of','json',combined]).stdout)
    report={'chapters':reports,'combined':str(combined),'combined_sha256':hashlib.sha256(combined.read_bytes()).hexdigest(),'probe':probe,'capture':'Native production simulation and renderer at fixed 30 fps, one room tick per video frame. Not a hardware-performance recording.','audio':'Production GameAudio spatial gain/pan and original files, placed at captured event times. No narration or added music.'}
    (output/'录制与验证.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'combined':str(combined),'seconds':probe['format']['duration'],'chapters':[{k:r[k] for k in ['name','seconds','audio_events']} for r in reports]},ensure_ascii=False))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('source',type=Path);p.add_argument('output',type=Path);a=p.parse_args();finish(a.source.resolve(),a.output.resolve())
