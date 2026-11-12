"""compare_match.py with PvP73 tools: V reference/cold export built from current sources
(build/pvp73-tools) and the production typed gate (build/app-typed72-v2 typed72_match_gate)."""
import sys
from pathlib import Path
ROOT=Path(r'C:\Users\xiech\Downloads\PVZ_rougePvP_native')
sys.path.insert(0,str(ROOT/'build/typed72-match-v1'))
import compare_match as c
c.EXPORT=ROOT/'build/pvp73-tools/build/Release/cold73_export.exe'
c.RECORD=ROOT/'build/pvp73-tools/build/Release/ref73_record.exe'
c.MATCH=ROOT/'build/app-typed72-v2/Release/typed72_match_gate.exe'
if __name__=='__main__':c.main()
