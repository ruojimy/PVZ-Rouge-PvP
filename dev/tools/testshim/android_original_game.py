# Native AST subset: actual original asset-root and persistent-save helpers.
import os
import shutil
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[2]

def asset_root():
    """Directory holding 图片/音乐/音效, which the original body opens relatively.

    The packaged PC game runs with the game directory as cwd; in the APK those
    three folders sit one level down, so the handoff chdirs there first.
    """
    for candidate in (APP_DIR / "PVZ-Rouge-v1.4.8", APP_DIR):
        if (candidate / "图片").is_dir() and (candidate / "音效").is_dir():
            return candidate
    return APP_DIR

ORIGINAL_SAVES = ("pvzrouge.json", "pvzrougeb.json")

def persistent_home():
    """Keep the original modes' saves across launches and APK updates.

    The original body saves to ``os.path.expanduser('~')`` (``pvzrouge.json``
    and its backup ``pvzrougeb.json``). python-for-android gives the process no
    usable HOME: ``~`` stayed literal and resolved under ``files/app``, the code
    directory p4a replaces on every update, so progress never lasted. HOME now
    points beside the PvP records; a save found at the old place is copied
    once, never overwriting one already kept.
    """
    folder = os.environ.get("PVP_USERDATA")
    if not folder:
        from modkit.android.platform_android import user_data_dir
        folder = user_data_dir()
    home = Path(folder) / "original_home"
    home.mkdir(parents=True, exist_ok=True)
    previous = [Path(os.path.expanduser("~")), Path.cwd() / "~", asset_root() / "~", APP_DIR / "~"]
    for name in ORIGINAL_SAVES:
        target = home / name
        if target.exists():
            continue
        old = next((path / name for path in previous if (path / name).is_file()), None)
        if old is not None:
            shutil.copy2(str(old), str(target))
    os.environ["HOME"] = str(home)
    return home

