"""Archive generated regression evidence and rotate reproducible suite fixtures."""

import contextlib
import ctypes
import functools
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import tempfile
import time
import zipfile


FIXTURE_RECEIPT = "scratch-paths.json"
ARTIFACTS = "scratch-artifacts.zip"
MANAGED_PREFIX = "managed-"


def managed_scratch_root(scratch_root, workspace):
    name = hashlib.sha256(os.fsencode(os.path.normcase(str(workspace.resolve())))).hexdigest()[:16]
    return scratch_root / (MANAGED_PREFIX + name)


@contextlib.contextmanager
def retention_lock(root):
    # The lock file stays in place so competing processes always lock the same inode.
    with (root / ".retention.lock").open("a+b") as handle:
        if os.name == "nt":
            import msvcrt
            import errno

            while True:
                handle.seek(0)
                try:
                    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                    break
                except OSError as error:
                    if error.errno not in (errno.EACCES, errno.EDEADLK):
                        raise
                    time.sleep(0.1)
        else:
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        yield


@contextlib.contextmanager
def fixture_access(fixture_root):
    """Keep a completed shared fixture available while a separate gate uses it."""
    root = fixture_root.parent.parent
    if root.name.startswith(MANAGED_PREFIX) and fixture_root.parent.name.startswith("suite-"):
        with retention_lock(root):
            if not fixture_root.is_dir():
                raise FileNotFoundError("This regression fixture has been retired: " + str(fixture_root))
            yield
    else:
        yield


def is_reparse(path):
    info = path.lstat()
    return stat.S_ISLNK(info.st_mode) or bool(
        getattr(info, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    )


def suite_scratch_path(root, name):
    if Path(name).name != name or not name.startswith("suite-") or not root.name.startswith(MANAGED_PREFIX):
        raise ValueError("Unexpected regression scratch name: " + name)
    path = root / name
    if root.resolve() != root or path.resolve() != path or (path.exists() and is_reparse(path)):
        raise ValueError("Regression scratch resolves outside its managed location: " + str(path))
    return path


def fixture_entry(parts):
    if parts[0] == "fixture-root":
        return "/".join(parts[1:])
    if len(parts) >= 4 and parts[0] == "module-fixtures" and parts[2] == "fixture-root":
        return "/".join(parts[3:])
    return None


def save_generated_artifacts(out, scratch, fixtures, file_sha):
    archive = out / ARTIFACTS
    archive_id = os.fsencode(str(scratch))
    if archive.exists():
        with zipfile.ZipFile(archive) as saved:
            if saved.comment != archive_id or saved.testzip() is not None:
                raise ValueError("Regression scratch archive failed verification: " + str(archive))
        return

    base = scratch / "fixture-root"
    verified_inputs = {}
    for rel, entry in fixtures.items():
        path = base / rel
        if path.is_file() and not is_reparse(path) and file_sha(path) == entry["sha256"]:
            verified_inputs[rel] = path.stat()

    def raise_walk_error(error):
        raise error

    with tempfile.NamedTemporaryFile(dir=out, suffix=".scratch.zip.part", delete=False) as handle:
        temporary = Path(handle.name)
    try:
        with zipfile.ZipFile(temporary, "w", zipfile.ZIP_DEFLATED, compresslevel=1) as saved:
            saved.comment = archive_id
            for folder, dirs, files in os.walk(scratch, onerror=raise_walk_error):
                folder = Path(folder)
                for name in dirs + files:
                    path = folder / name
                    if is_reparse(path):
                        raise ValueError("Unexpected link inside regression scratch: " + str(path))
                for name in files:
                    path = folder / name
                    relative = path.relative_to(scratch)
                    key = fixture_entry(relative.parts)
                    stock = verified_inputs.get(key)
                    if stock is not None and stock.st_ino and os.path.samestat(path.stat(), stock):
                        continue
                    if key in fixtures and file_sha(path) == fixtures[key]["sha256"]:
                        continue
                    saved.write(path, relative.as_posix())
        with zipfile.ZipFile(temporary) as saved:
            bad = saved.testzip()
            if bad is not None:
                raise ValueError("Failed to verify scratch artifact: " + bad)
        os.replace(temporary, archive)
    finally:
        if temporary.exists():
            temporary.unlink()


@functools.lru_cache(maxsize=1)
def windows_disposition_api():
    from ctypes import wintypes

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateFileW.argtypes = (
        wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p,
        wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE,
    )
    kernel.CreateFileW.restype = wintypes.HANDLE
    kernel.SetFileInformationByHandle.argtypes = (
        wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD,
    )
    kernel.SetFileInformationByHandle.restype = wintypes.BOOL
    kernel.CloseHandle.argtypes = (wintypes.HANDLE,)
    return kernel


def remove_readonly_file(function, path, exc):
    if os.name != "nt" or function is not os.unlink or not isinstance(exc[1], PermissionError):
        raise exc[1]
    # FileDispositionInfoEx unlinks readonly files without changing attributes
    # of other hard links, including the retained base fixture.
    kernel = windows_disposition_api()
    path = os.path.abspath(path)
    if not path.startswith("\\\\?\\"):
        path = "\\\\?\\UNC\\" + path[2:] if path.startswith("\\\\") else "\\\\?\\" + path
    handle = kernel.CreateFileW(path, 0x10000, 7, None, 3, 0x200000, None)
    if handle == ctypes.c_void_p(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        flags = ctypes.c_ulong(0x1 | 0x2 | 0x10)
        if not kernel.SetFileInformationByHandle(handle, 21, ctypes.byref(flags), ctypes.sizeof(flags)):
            raise ctypes.WinError(ctypes.get_last_error())
    finally:
        kernel.CloseHandle(handle)


def finalize_scratch(out, scratch, scope, fixtures, file_sha):
    """Retain the latest completed base per scope. Active runs have no receipt."""
    root = scratch.parent
    if suite_scratch_path(root, scratch.name) != scratch:
        raise ValueError("Unexpected regression scratch path: " + str(scratch))
    save_generated_artifacts(out, scratch, fixtures, file_sha)
    with retention_lock(root):
        # Only the base is needed for a follow-up bytecode gate. The archived
        # worker outputs preserve their original paths inside the archive.
        for name in ("module-fixtures", "tmp"):
            target = scratch / name
            if target.exists():
                if target.resolve() != target or is_reparse(target):
                    raise ValueError("Unexpected regression scratch component: " + str(target))
                shutil.rmtree(target, onerror=remove_readonly_file)

        marker = root / (scratch.name + ".completed.json")
        pending = marker.with_suffix(".part")
        pending.write_text(json.dumps({
            "out": str(out), "scope": scope, "completed_ns": time.time_ns(),
        }), encoding="utf-8")
        os.replace(pending, marker)
        completed = []
        for receipt in root.glob("suite-*.completed.json"):
            if is_reparse(receipt):
                continue
            data = json.loads(receipt.read_text(encoding="utf-8"))
            if data["scope"] == scope:
                completed.append((data["completed_ns"], receipt, data["out"]))

        retired = []
        for _, receipt, previous_out in sorted(completed, reverse=True)[1:]:
            previous = suite_scratch_path(root, receipt.name[:-len(".completed.json")])
            output = Path(previous_out)
            registration = json.loads((output / FIXTURE_RECEIPT).read_text(encoding="utf-8"))
            with zipfile.ZipFile(output / ARTIFACTS) as saved:
                valid_archive = saved.comment == os.fsencode(str(previous)) and saved.testzip() is None
            if not valid_archive or registration["run_scratch"] != str(previous):
                raise ValueError("Cannot verify ownership of old regression scratch: " + str(previous))
            if previous.exists():
                shutil.rmtree(previous, onerror=remove_readonly_file)
            receipt.unlink()
            retired.append(str(previous))
    return {"artifacts": str(out / ARTIFACTS), "retained_fixture": str(scratch / "fixture-root"), "retired": retired}
