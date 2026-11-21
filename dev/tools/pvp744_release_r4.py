"""Stage and verify the November 19 feedback build. Run each release phase separately."""
import argparse
import os
from pathlib import Path
import shutil
import zipfile

import pvp744_release_r3 as release

root = release.ROOT
release.OUT = root / 'test_results/pvp744/r4-feedback-20261119'
release.STAGE = root / 'dist/PvZ-PvP-Native-20261119-pvp744-r4'
release.VERSION = '1.6.0.74.4-typed.20261119-r4'
release.REV = 'pvp744-r4'
release.PREVIOUS_REV = 'pvp744-r3'
release.CODE = 1119004
release.NATIVE_RUN = 'pvp744-r4-final-20261119'
release.APK_DIR = root / 'dist/apk-pvp744-r4-20261119'
release.EXTRA_AUDITS = [('pvp744_r4_audit', 'r4')]
release.helpers.VERSION, release.helpers.OUT, release.helpers.STAGE = release.VERSION, release.OUT, release.STAGE

def backup():
    previous = release.read(root / 'dist/latest-native-release.json')
    assert previous['revision'] == release.PREVIOUS_REV
    dest = Path(previous['target']).parent
    folder = root / 'backup-latest'
    launchers = [root / '启动PvP.cmd', dest / 'launch_pvp.cmd']
    assert release.sha(dest / 'PvZPvPNative.exe') == previous['exe_sha256']
    before = dict(previous=previous, users=release.users(), launchers={str(p): release.sha(p) for p in launchers})
    release.dump(release.OUT / 'before.json', before)
    rows = []
    for name, path_key, hash_key in [('previous-release.zip','pc_zip','pc_zip_sha256'),
                                    ('previous-source.zip','developer_package','developer_sha256'),
                                    ('previous-android.apk','apk','apk_sha256')]:
        original, target = Path(previous[path_key]), folder/name
        staging = folder/(name+'.next')
        shutil.copy2(original, staging)
        digest = release.sha(staging)
        assert digest == previous[hash_key]
        rows.append(dict(file=str(target), revision=previous['revision'], sha256=digest, original_file=str(original)))
    state = folder / 'release-state-before.zip'
    with zipfile.ZipFile(folder/(state.name+'.next'), 'w', zipfile.ZIP_DEFLATED) as z:
        for p in launchers+[dest/'extract/data/__init__.json',root/'dist/latest-native-release.json']:
            z.write(p,p.relative_to(root).as_posix())
    with zipfile.ZipFile(folder/(state.name+'.next')) as z:
        assert z.testzip() is None
    rows.append(dict(file=str(state), revision=previous['revision'], sha256=release.sha(folder/(state.name+'.next'))))
    for row in rows:
        target = Path(row['file'])
        os.replace(folder/(target.name+'.next'), target)
    state.with_suffix('.zip.sha256').write_text(rows[-1]['sha256']+'  '+state.name+'\n','utf8')
    release.dump(folder/'manifest.json', rows)
    release.prepare()

if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('phase',choices=['backup','stage','smoke','apk','packages','promote'])
    phase = p.parse_args().phase
    if phase == 'backup':
        backup()
    else:
        getattr(release,phase)()

