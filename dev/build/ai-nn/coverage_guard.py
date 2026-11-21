"""Guarded launcher for the expanded paired-opponent training study."""
import os
import sys
import time
import shutil
import subprocess
from pathlib import Path
import psutil
from overnight_common import R, B as PREVIOUS, BUILD, write, read, kill_owned

OUT = R / 'test_results/ai-nn-coverage-20261118'
def size(root):
    return sum(item.stat().st_size for item in root.rglob('*') if item.is_file())

def run(stage, script='coverage_study.py'):
    OUT.mkdir(exist_ok=True)
    temp = OUT / 'temp'
    temp.mkdir(exist_ok=True)
    env = dict(os.environ, TMP=str(temp), TEMP=str(temp), OMP_NUM_THREADS='2', OPENBLAS_NUM_THREADS='1', PYTHONUTF8='1')
    previous = size(PREVIOUS) + size(BUILD)
    receipt = OUT / 'disk.json'
    peak = read(receipt)['new_peak'] if receipt.exists() else 0
    def guard():
        nonlocal peak
        try:
            used = size(OUT)
        except FileNotFoundError:
            return guard()
        peak = max(peak, used)
        free = shutil.disk_usage(OUT).free
        write(receipt, dict(new_bytes=used, new_peak=peak, prior_bytes=previous, free=free, combined_limit=4*2**30, free_floor=100*2**30))
        if previous + used >= 4*2**30-256*2**20 or free <= 100*2**30 or (OUT/'STOP').exists():
            raise RuntimeError('Storage guard or stop file')
    guard()
    with (OUT / (stage + '-' + str(time.time_ns()) + '.log')).open('wb') as log:
        job = subprocess.Popen([sys.executable,'-X','utf8','-u',Path(__file__).with_name(script),stage],cwd=R,env=env,stdout=log,stderr=subprocess.STDOUT,creationflags=0x08004000)
        try:
            while job.poll() is None:
                guard()
                time.sleep(2)
            guard()
            if job.returncode: raise RuntimeError('Stage failed: '+stage)
        except BaseException:
            kill_owned(job)
            raise
if __name__ == '__main__':
    run(sys.argv[1])
