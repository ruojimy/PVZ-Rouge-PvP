"""Prepare verified plain research inputs after cloning/downloading compressed data."""
import argparse
import gzip
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument('--training', action='store_true')
args = ap.parse_args()
here = Path(__file__).resolve().parent
root = here.parents[1]
plain = here / 'corpus-pvp743-r2-plain'
if not (plain / 'index.json').is_file():
    subprocess.run([sys.executable, str(here / 'materialize_corpus.py'),
                    str(here / 'corpus-pvp743-r2'), str(plain)], check=True)
if args.training:
    evidence = root / 'test_results/ai-nn-local-20261114'
    target = evidence / 'dataset.jsonl'
    if not target.exists():
        temp = target.with_suffix('.jsonl.partial')
        with gzip.open(target.with_suffix('.jsonl.gz'), 'rb') as src, temp.open('wb') as dst:
            shutil.copyfileobj(src, dst)
        expected = json.loads((evidence / 'dataset.provenance.json').read_text('utf-8'))['dataset_sha256']
        with temp.open('rb') as stream:
            actual = hashlib.file_digest(stream, 'sha256').hexdigest()
        if actual != expected:
            raise SystemExit('Dataset hash mismatch; partial file retained for diagnosis')
        temp.rename(target)
print('Research inputs ready')
