"""Schedule the already frozen fits and evaluations after all native collection groups finish."""
import time
import psutil
from overnight_common import read, write, sha
from coverage_guard import OUT, run

def main():
    while len(list((OUT/'train').glob('*/ready.json')))<32:
        if not any('coverage_study.py' in ' '.join(p.info['cmdline'] or []) and (p.info['cmdline'] or [''])[-1]=='collect' for p in psutil.process_iter(['cmdline']) if p.info['cmdline']):
            raise RuntimeError('Collection ended before all groups completed')
        time.sleep(5)
    for stage,entry in [('fit','coverage_study.py'),('fit','coverage_controls.py'),('validation','coverage_study.py'),('evaluate','coverage_controls.py'),('test','coverage_study.py')]:
        write(OUT/'phase.json',dict(stage=stage,entry=entry))
        run(stage,entry)
    write(OUT/'phase.json',dict(stage='completed'))
if __name__=='__main__':
    main()
