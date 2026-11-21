"""Shared helpers for 2026-11-20 diagnosis runs; reuses the frozen day-league profile read-only."""
import os,json,gzip
from pathlib import Path
R=Path(__file__).resolve().parents[2]
DAY=R/'test_results/ai-nn-home-options-20261118/ranked-day-league-20261120'
os.environ.setdefault('PVZ_RANKED_PROFILE',str(DAY/'profile.json'))
OUT=R/'test_results/ai-nn-home-options-20261118/ranked-diagnose-20261120'
import ranked_day_league as day
from option_games import play
def fixture_dir(case):
    tag,uid=case.split('/');return Path(day.fixtures()['sources'][tag]['path']),uid
def game(case,plant,zombie,storage,limit=600):
    from dataclasses import replace
    corpus,uid=fixture_dir(case)
    (storage/'temp').mkdir(parents=True,exist_ok=True)
    g=day.combat_game(corpus,uid,plant,zombie,storage)
    return replace(g,limit=limit) if limit!=600 else g
def trace(g):
    play(g)
    with gzip.open(g.path(),'rt',encoding='utf8') as f:
        head=json.loads(f.readline());tail=json.loads(f.readline())
    return head,tail
