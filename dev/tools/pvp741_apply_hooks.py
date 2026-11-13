# -*- coding: utf-8 -*-
"""Reapply/verify reviewed shared native hooks after UI regeneration."""
from pathlib import Path
import argparse,json
ROOT=Path(__file__).resolve().parents[1]
def main():
 p=argparse.ArgumentParser();p.add_argument('--check',action='store_true');args=p.parse_args()
 patches=json.loads((ROOT/'tools/pvp741_hooks.json').read_text('utf8'));missing=[]
 for patch in patches:
  path=ROOT/patch['file'];text=path.read_text('utf8')
  if patch['after'] in text:continue
  if args.check:missing.append(patch['file']);continue
  if text.count(patch['before'])!=1:raise RuntimeError('Ambiguous/stale PvP74.1 hook anchor: '+patch['file'])
  path.write_text(text.replace(patch['before'],patch['after'],1),'utf8')
 if missing:raise SystemExit('Stale PvP74.1 hooks: '+', '.join(missing))
 print('PvP74.1 shared hooks: '+('checked' if args.check else 'applied'))
if __name__=='__main__':main()
