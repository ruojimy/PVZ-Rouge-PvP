"""Immutable, content-addressed storage for ordinary typed72 frozen file paths.

Replace copy2(source, destination) with freeze_file(source, destination,
expected_sha256=pinned[str(source)]). This module never writes pinned/summary
files and never hard-links mutable source/build files. Every new snapshot first
passes through a separate, streamed, fsynced and SHA-verified temporary file.

Objects live in a NEW store, separate from disk-cleanup-20261105 archives:
  test_results/typed72-evidence-store-v1/objects/<sha[:2]>/<sha>[.rN]
Frozen paths hard-link those read-only objects on the same volume. Independent
replicas prevent NTFS's link limit from turning thousands of runs into copies.
Cross-volume or unsupported hard links use verified, atomically published copies.
All workers publishing into one store share its OS publication lock. Frozen
files must be treated as immutable; copy a frozen file before editing it.

Existing destinations are accepted only when their bytes already match. A
closure failure may leave earlier complete, validated frozen files as evidence;
private temporary files are cleaned, and partial public files are never exposed.
Source timestamps/modes are not propagated onto existing shared objects.

Windows hard-link limits: https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-createhardlinkw
Atomic Windows rename: https://docs.python.org/3/library/os.html#os.rename
Python 3.8+, standard library only; importing this module creates no files.
"""

from contextlib import contextmanager
from dataclasses import dataclass
import errno
import hashlib
import os
from pathlib import Path
import stat
import tempfile
import threading
import time


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_STORE_ROOT = ROOT / 'test_results' / 'typed72-evidence-store-v1'
_CHUNK = 1024 * 1024
_THREAD_LOCKS = {}
_THREAD_LOCKS_GUARD = threading.Lock()
_FALLBACK_ERRNOS = {errno.EXDEV, errno.EPERM, errno.EACCES, errno.EMLINK,
                    errno.ENOSYS, errno.ENOTSUP, errno.EOPNOTSUPP}
_FALLBACK_WINERRORS = {1, 17, 50, 1142, 1314}


class EvidenceStoreError(RuntimeError):
    """The evidence could not be frozen without losing its integrity."""


@dataclass(frozen=True)
class FrozenFile:
    source: Path
    destination: Path
    sha256: str
    size_bytes: int
    object_path: Path
    method: str


def _hash_size(path):
    digest = hashlib.sha256()
    size = 0
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(_CHUNK), b''):
            digest.update(chunk)
            size += len(chunk)
    return digest.hexdigest(), size


def sha256_file(path):
    return _hash_size(path)[0]


def _identity(info):
    return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns


def _same_file(left, right):
    try:
        return os.path.samefile(str(left), str(right))
    except FileNotFoundError:
        return False


def _fallback_allowed(error):
    return error.errno in _FALLBACK_ERRNOS or getattr(error, 'winerror', None) in _FALLBACK_WINERRORS


def _at_link_limit(error):
    return error.errno == errno.EMLINK or getattr(error, 'winerror', None) == 1142


def _remove_private_temp(path):
    # Only paths returned by our mkstemp calls reach this function. No recursion.
    if path is not None:
        try:
            Path(path).unlink()
        except FileNotFoundError:
            pass


def _verify(path, digest, size, mutable_source=None):
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400:
        raise EvidenceStoreError('Evidence must be a regular non-reparse file: ' + str(path))
    if mutable_source is not None and _same_file(path, mutable_source):
        raise EvidenceStoreError('Evidence aliases the mutable source: ' + str(path))
    actual_digest, actual_size = _hash_size(path)
    if actual_digest != digest or actual_size != size:
        raise EvidenceStoreError('Existing evidence SHA/size mismatch: ' + str(path))


def _protect(path, source_mode):
    # Preserve useful read/execute permissions while denying ordinary writes.
    current_mode = stat.S_IMODE(path.stat().st_mode)
    os.chmod(str(path), (current_mode | source_mode) & 0o555)


def _verify_storage_directory(path):
    info = path.lstat()
    if not stat.S_ISDIR(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400:
        raise EvidenceStoreError('Store directory must not be a reparse point: ' + str(path))


class EvidenceStore:
    def __init__(self, store_root=None, max_links=900, lock_timeout=30.0):
        if not 2 <= max_links <= 1000:
            raise ValueError('max_links must be between 2 and 1000')
        if lock_timeout <= 0:
            raise ValueError('lock_timeout must be positive')
        self.root = Path(DEFAULT_STORE_ROOT if store_root is None else store_root).resolve()
        self.objects = self.root / 'objects'
        self.incoming = self.root / '.incoming'
        self.max_links = max_links
        self.lock_timeout = lock_timeout
        key = os.path.normcase(str(self.root))
        with _THREAD_LOCKS_GUARD:
            self._thread_lock = _THREAD_LOCKS.setdefault(key, threading.RLock())

    def _prepare(self):
        self.objects.mkdir(parents=True, exist_ok=True)
        self.incoming.mkdir(parents=True, exist_ok=True)
        _verify_storage_directory(self.root)
        _verify_storage_directory(self.objects)
        _verify_storage_directory(self.incoming)

    @contextmanager
    def _publication_lock(self):
        # OS locks are released even when a worker crashes; no stale lock-directory
        # removal heuristics can race a live publisher. The one-byte file remains.
        with self._thread_lock:
            with (self.root / '.publish.lock').open('a+b') as lock:
                if os.fstat(lock.fileno()).st_size == 0:
                    lock.write(b'\0')
                    lock.flush()
                deadline = time.monotonic() + self.lock_timeout
                while True:
                    try:
                        lock.seek(0)
                        if os.name == 'nt':
                            import msvcrt
                            msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
                        else:
                            import fcntl
                            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                        break
                    except OSError:
                        if time.monotonic() >= deadline:
                            raise EvidenceStoreError('Evidence publication lock timed out: ' + str(self.root))
                        time.sleep(0.01)
                try:
                    yield
                finally:
                    lock.seek(0)
                    if os.name == 'nt':
                        msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
                    else:
                        fcntl.flock(lock.fileno(), fcntl.LOCK_UN)

    def _snapshot(self, source, directory, expected=None):
        descriptor, name = tempfile.mkstemp(prefix='.pvp72-evidence-', suffix='.tmp', dir=str(directory))
        temporary = Path(name)
        try:
            digest = hashlib.sha256()
            count = 0
            with os.fdopen(descriptor, 'wb') as target, source.open('rb') as original:
                before = os.fstat(original.fileno())
                if not stat.S_ISREG(before.st_mode):
                    raise EvidenceStoreError('Source is not a regular file: ' + str(source))
                for chunk in iter(lambda: original.read(_CHUNK), b''):
                    target.write(chunk)
                    digest.update(chunk)
                    count += len(chunk)
                if (_identity(before) != _identity(os.fstat(original.fileno()))
                        or _identity(before) != _identity(source.stat())):
                    raise EvidenceStoreError('Source changed while freezing: ' + str(source))
                target.flush()
                os.fsync(target.fileno())
            value = digest.hexdigest()
            if expected is not None and value != expected:
                raise EvidenceStoreError('Source SHA differs from pinned SHA: ' + str(source))
            if count != before.st_size or _hash_size(temporary) != (value, count):
                raise EvidenceStoreError('Temporary snapshot SHA/size mismatch: ' + str(source))
            if _same_file(source, temporary):
                raise EvidenceStoreError('Temporary snapshot aliases source')
            return temporary, value, count, stat.S_IMODE(before.st_mode)
        except BaseException:
            _remove_private_temp(temporary)
            raise

    def _publish_no_replace(self, temporary, destination):
        """Publish complete bytes while holding the shared publication lock."""
        try:
            os.link(str(temporary), str(destination))
        except FileExistsError:
            return False
        except OSError as error:
            if not _fallback_allowed(error):
                raise
            # Temp and destination are on the same volume. Windows rename is
            # atomic and refuses an existing target. POSIX fallback is protected
            # against all publishers in this store by the shared OS lock.
            if os.path.lexists(str(destination)):
                return False
            try:
                os.rename(str(temporary), str(destination))
            except FileExistsError:
                return False
        # Unlink while still writable and holding the lock. Making the shared
        # object read-only first would also make this private hard link read-only.
        _remove_private_temp(temporary)
        return True

    def _hardlink(self, source, destination):
        os.link(str(source), str(destination))

    def _copy_fallback(self, obj, destination, digest, size, mode, mutable_source):
        temporary, copied_digest, copied_size, unused_mode = self._snapshot(obj, destination.parent, digest)
        try:
            if copied_digest != digest or copied_size != size:
                raise EvidenceStoreError('Fallback copy differs from verified object')
            with self._publication_lock():
                created = self._publish_no_replace(temporary, destination)
                if not created:
                    _verify(destination, digest, size, mutable_source)
                    return 'existing'
                _protect(destination, mode)
            return 'copy'
        finally:
            _remove_private_temp(temporary)

    def freeze_file(self, source, destination, expected_sha256=None):
        source = Path(source).resolve(strict=True)
        destination = Path(os.path.abspath(str(destination)))
        if expected_sha256 is not None:
            expected_sha256 = str(expected_sha256).lower()
            if len(expected_sha256) != 64 or any(c not in '0123456789abcdef' for c in expected_sha256):
                raise ValueError('expected_sha256 must contain exactly 64 hexadecimal digits')
        if source == destination or _same_file(source, destination):
            raise EvidenceStoreError('Frozen destination must not alias the mutable source')
        self._prepare()
        temporary, digest, size, mode = self._snapshot(source, self.incoming, expected_sha256)
        try:
            destination.parent.mkdir(parents=True, exist_ok=True)
            bucket = self.objects / digest[:2]
            bucket.mkdir(exist_ok=True)
            _verify_storage_directory(bucket)
            replica = 0
            previous_object = None
            fallback = False
            with self._publication_lock():
                while True:
                    obj = bucket / (digest + ('.r%d' % replica if replica else ''))
                    if os.path.lexists(str(obj)):
                        _verify(obj, digest, size, source)
                    else:
                        if temporary is None or not temporary.exists():
                            # Link-count rollover copies verified CAS bytes into
                            # a fresh independent inode, never into a source link.
                            temporary, unused_digest, unused_size, unused_mode = self._snapshot(
                                previous_object, self.incoming, digest)
                        if not self._publish_no_replace(temporary, obj):
                            _verify(obj, digest, size, source)
                    _protect(obj, mode)
                    previous_object = obj
                    if os.path.lexists(str(destination)):
                        _verify(destination, digest, size, source)
                        method = 'existing'
                        break
                    if obj.stat().st_nlink >= self.max_links:
                        replica += 1
                        continue
                    try:
                        self._hardlink(obj, destination)
                        method = 'hardlink'
                        break
                    except FileExistsError:
                        _verify(destination, digest, size, source)
                        method = 'existing'
                        break
                    except OSError as error:
                        if _at_link_limit(error):
                            if obj.stat().st_nlink > 1:
                                replica += 1
                                continue
                            # A fresh inode also failing cannot be repaired by
                            # unbounded replica creation; take the copy path.
                            fallback = True
                            break
                        if not _fallback_allowed(error):
                            raise
                        fallback = True
                        break
            if fallback:
                method = self._copy_fallback(obj, destination, digest, size, mode, source)
            return FrozenFile(source, destination, digest, size, obj, method)
        finally:
            _remove_private_temp(temporary)

    def freeze_closure(self, paths, frozen_root, source_root=ROOT, pinned=None):
        """Freeze a source closure using existing ROOT/reference/name mapping.

        Returns the normal {absolute_source_path: sha256} pinned mapping without
        writing or modifying any metadata. Pass existing pinned to detect races
        between the verifier's pinning pass and its freezing pass.
        """
        source_root = Path(source_root).resolve()
        frozen_root = Path(frozen_root).resolve()
        planned = []
        destinations = {}
        for value in paths:
            source = Path(value).resolve(strict=True)
            try:
                relative = source.relative_to(source_root)
            except ValueError:
                relative = Path('reference') / source.name
            destination = frozen_root / relative
            key = os.path.normcase(str(destination))
            if key in destinations and destinations[key] != source:
                raise EvidenceStoreError('Ambiguous frozen reference basename: ' + str(relative))
            destinations[key] = source
            expected = None if pinned is None else pinned[str(source)]
            planned.append((source, destination, expected))
        result = {}
        for source, destination, expected in planned:
            frozen = self.freeze_file(source, destination, expected)
            result[str(source)] = frozen.sha256
        return result


def freeze_file(source, destination, expected_sha256=None, store_root=None):
    return EvidenceStore(store_root).freeze_file(source, destination, expected_sha256)


def freeze_closure(paths, frozen_root, source_root=ROOT, pinned=None, store_root=None):
    return EvidenceStore(store_root).freeze_closure(paths, frozen_root, source_root, pinned)


freeze_sources = freeze_closure
