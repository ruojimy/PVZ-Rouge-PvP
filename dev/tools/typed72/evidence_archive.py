"""Seal completed typed72 JSONL evidence and read raw/archived streams uniformly.

This module never scans live runs or changes summary/pinned files. The verifier
must obtain a same-process completion proof after subprocess.run has returned
and every actual/expected stream has closed, then explicitly archive that proof:

    proof = completion_proof(out, producer=run,
                             closed_streams=(actual, expected))
    result = archive_completed_run(proof)

Compression is streamed to a private temporary object and independently read
back. A checksummed sidecar is atomically published before any raw deletion.
On Windows, raw files are opened through handles denying other writers/renames;
deletion uses those same verified handles, never a freshly resolved pathname.
All precommit exceptions retain every raw file. Per-file deletion failures are
returned as retained entries; earlier successful removals remain fully archived.
Non-Windows hosts can publish archives with remove_raw=False; raw removal there
is deliberately unavailable without equivalent mandatory writer exclusion.

open_evidence/evidence_exists/evidence_sha256 understand raw files, new sidecars,
and the prior disk-cleanup-20261105 SQLite index in immutable read-only mode.
No builtins, pathlib methods or subprocess functions are monkey-patched.

Win32 sharing: https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-createfilew
Handle deletion: https://learn.microsoft.com/en-us/windows/win32/api/winbase/ns-winbase-file_disposition_info
Python 3.8+, standard library only. Importing this module performs no I/O.
"""

from contextlib import ExitStack, contextmanager
from dataclasses import dataclass
import ctypes
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import sqlite3
import stat
import subprocess
import tempfile
import threading
import time
import weakref

try:
    from . import evidence_store as store_module
except ImportError:
    import evidence_store as store_module


ROOT = Path(__file__).resolve().parents[2]
RESULTS_ROOT = ROOT / 'test_results'
LEGACY_INDEX = RESULTS_ROOT / 'disk-cleanup-20261105/restore-index.sqlite3'
MANIFEST_NAME = 'evidence-files.v1.json'
FORMAT = 'typed72-jsonl-evidence-v1'
_ALLOWED_NAMES = frozenset(('actual.jsonl', 'expected.jsonl'))
_CHUNK = 1024 * 1024
_PROOFS = weakref.WeakKeyDictionary()
_PROOF_LOCK = threading.Lock()
_VERIFIED_GZIP = set()
_VERIFIED_GZIP_LOCK = threading.Lock()


class EvidenceArchiveError(RuntimeError):
    """The operation cannot preserve the original evidence contract."""


@dataclass(frozen=True)
class RawSnapshot:
    name: str
    sha256: str
    size_bytes: int
    identity: tuple


@dataclass(frozen=True, eq=False)
class CompletionProof:
    run_root: Path
    results_root: Path
    process_id: int
    producer_exit_code: int
    summary_sha256: str
    snapshots: tuple

    def __reduce_ex__(self, protocol):
        raise TypeError('Completion proofs cannot be transferred between processes')


@dataclass(frozen=True)
class ArchiveResult:
    manifest_path: Path
    removed: tuple
    retained: tuple
    errors: tuple
    original_bytes: int


@dataclass(frozen=True)
class ArchivedFile:
    raw_path: Path
    object_path: Path
    raw_sha256: str
    raw_size: int
    gzip_sha256: str
    gzip_size: int
    provenance: Path


def _sha_size(stream):
    digest = hashlib.sha256()
    size = 0
    for chunk in iter(lambda: stream.read(_CHUNK), b''):
        digest.update(chunk)
        size += len(chunk)
    return digest.hexdigest(), size


def _file_sha_size(path):
    with Path(path).open('rb') as stream:
        return _sha_size(stream)


def _identity(info):
    return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns


def _valid_sha(value):
    if not isinstance(value, str) or len(value) != 64 or any(c not in '0123456789abcdef' for c in value):
        raise EvidenceArchiveError('Malformed evidence SHA-256')
    return value


def _canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')


def _bounded(path, root, must_exist=True, directory=False):
    root = Path(root).absolute()
    path = Path(os.path.abspath(str(path)))
    try:
        path.relative_to(root)
    except ValueError:
        raise EvidenceArchiveError('Evidence path escaped its approved root: ' + str(path))
    cursor = path
    while True:
        try:
            info = cursor.lstat()
        except FileNotFoundError:
            if cursor != root and not must_exist:
                pass
            else:
                raise
        else:
            if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400:
                raise EvidenceArchiveError('Evidence reparse point refused: ' + str(cursor))
            if cursor == path:
                required = stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode)
                if not required:
                    raise EvidenceArchiveError('Unexpected evidence file type: ' + str(path))
        if cursor == root:
            break
        cursor = cursor.parent
    if must_exist and path.resolve() != path:
        raise EvidenceArchiveError('Resolved evidence path differs from its approved path')
    return path


class _LockedRaw:
    """Read a stable raw file, optionally retaining native DELETE access."""
    def __init__(self, path, delete_access=False):
        self.path = path
        self.delete_access = delete_access
        self.stream = None

    def __enter__(self):
        if os.name == 'nt':
            import msvcrt
            kernel = ctypes.WinDLL('kernel32', use_last_error=True)
            kernel.CreateFileW.argtypes = (ctypes.c_wchar_p, ctypes.c_uint32, ctypes.c_uint32,
                                          ctypes.c_void_p, ctypes.c_uint32, ctypes.c_uint32,
                                          ctypes.c_void_p)
            kernel.CreateFileW.restype = ctypes.c_void_p
            kernel.CloseHandle.argtypes = (ctypes.c_void_p,)
            kernel.CloseHandle.restype = ctypes.c_int
            access = 0x80000000 | (0x00010000 if self.delete_access else 0)
            # FILE_SHARE_READ only: writers and renames are excluded until close.
            handle = kernel.CreateFileW(str(self.path), access, 1, None, 3,
                                        0x08000000 | 0x00200000, None)
            if handle == ctypes.c_void_p(-1).value:
                raise ctypes.WinError(ctypes.get_last_error())
            try:
                descriptor = msvcrt.open_osfhandle(handle, os.O_RDONLY | os.O_BINARY)
            except BaseException:
                kernel.CloseHandle(handle)
                raise
            try:
                self.stream = os.fdopen(descriptor, 'rb')
            except BaseException:
                os.close(descriptor)
                raise
        else:
            if self.delete_access:
                raise EvidenceArchiveError('Raw removal requires mandatory Windows writer exclusion')
            self.stream = self.path.open('rb')
        return self

    def snapshot(self):
        self.stream.seek(0)
        before = os.fstat(self.stream.fileno())
        digest, size = _sha_size(self.stream)
        if (_identity(before) != _identity(os.fstat(self.stream.fileno()))
                or _identity(before) != _identity(self.path.stat()) or size != before.st_size):
            raise EvidenceArchiveError('Raw evidence changed while hashing: ' + str(self.path))
        return RawSnapshot(self.path.name, digest, size, _identity(before))

    def assert_identity(self, snapshot):
        if (_identity(os.fstat(self.stream.fileno())) != snapshot.identity
                or _identity(self.path.stat()) != snapshot.identity):
            raise EvidenceArchiveError('Raw evidence identity changed after completion proof')

    def delete_verified_handle(self):
        if os.name != 'nt' or not self.delete_access:
            raise EvidenceArchiveError('No exclusive native deletion capability')
        import msvcrt
        class Disposition(ctypes.Structure):
            _fields_ = [('DeleteFile', ctypes.c_ubyte)]
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.SetFileInformationByHandle.argtypes = (ctypes.c_void_p, ctypes.c_int,
                                                      ctypes.c_void_p, ctypes.c_uint32)
        kernel.SetFileInformationByHandle.restype = ctypes.c_int
        flag = Disposition(1)
        handle = msvcrt.get_osfhandle(self.stream.fileno())
        if not kernel.SetFileInformationByHandle(handle, 4, ctypes.byref(flag), ctypes.sizeof(flag)):
            raise ctypes.WinError(ctypes.get_last_error())
        # No pathname deletion or further file operations after setting disposition.
        self.stream.close()

    def __exit__(self, *args):
        if self.stream is not None:
            self.stream.close()


def completion_proof(out, *, producer, closed_streams, names=('actual.jsonl', 'expected.jsonl'),
                     summary_sha256=None, results_root=RESULTS_ROOT):
    """Issue a nontransferable proof from this verifier's completed producer/IO."""
    results_root = Path(results_root).resolve(strict=True)
    out = _bounded(Path(out).absolute(), results_root, directory=True)
    names = tuple(names)
    if not names or len(set(names)) != len(names) or any(name not in _ALLOWED_NAMES for name in names):
        raise EvidenceArchiveError('Only explicit actual/expected JSONL streams can be sealed')
    if not isinstance(producer, subprocess.CompletedProcess) or type(producer.returncode) is not int:
        raise EvidenceArchiveError('A returned subprocess.CompletedProcess is required')
    if not isinstance(producer.args, (tuple, list)):
        raise EvidenceArchiveError('Producer arguments must identify this evidence directory')
    producer_paths = set()
    for arg in producer.args:
        if isinstance(arg, (str, bytes, os.PathLike)):
            try:
                producer_paths.add(Path(os.fsdecode(arg)).absolute())
            except (ValueError, TypeError):
                pass
    if not any(out / name in producer_paths for name in ('inputs.jsonl',) + names):
        raise EvidenceArchiveError('Completed producer does not name this run directory')
    streams = tuple(closed_streams)
    covered = set()
    for stream in streams:
        if not isinstance(stream, io.IOBase) or not stream.closed:
            raise EvidenceArchiveError('Every supplied evidence stream must already be closed')
        if not isinstance(stream.name, (str, bytes, os.PathLike)):
            raise EvidenceArchiveError('Closed stream must retain a filesystem name')
        stream_path = Path(os.path.abspath(os.fsdecode(stream.name)))
        if stream_path.parent != out or stream_path.name not in names:
            raise EvidenceArchiveError('Closed stream belongs to another run or file')
        covered.add(stream_path.name)
    if covered != set(names):
        raise EvidenceArchiveError('Closed-stream proof must cover every selected JSONL file')
    summary = _bounded(out / 'summary.json', results_root)
    with _LockedRaw(summary) as guard:
        summary_snapshot = guard.snapshot()
        guard.stream.seek(0)
        summary_data = json.load(guard.stream)
    if not isinstance(summary_data, dict):
        raise EvidenceArchiveError('Completed summary must be a JSON object')
    if ('process_exit_code' in summary_data
            and summary_data['process_exit_code'] != producer.returncode):
        raise EvidenceArchiveError('Producer exit code differs from the completed summary')
    if summary_sha256 is not None and _valid_sha(summary_sha256) != summary_snapshot.sha256:
        raise EvidenceArchiveError('Completed summary differs from the supplied SHA')
    snapshots = []
    for name in names:
        path = _bounded(out / name, results_root)
        with _LockedRaw(path) as guard:
            snapshots.append(guard.snapshot())
    metadata = {'summary.json': summary_snapshot.sha256}
    pinned = out / 'pinned.json'
    if pinned.exists():
        _bounded(pinned, results_root)
        with _LockedRaw(pinned) as guard:
            metadata['pinned.json'] = guard.snapshot().sha256
    proof = CompletionProof(out, results_root, os.getpid(), producer.returncode,
                            summary_snapshot.sha256, tuple(snapshots))
    with _PROOF_LOCK:
        _PROOFS[proof] = dict(pid=os.getpid(), state='ready', streams=streams,
                              snapshots=tuple(snapshots), metadata=metadata,
                              root=out, results_root=results_root)
    return proof


class EvidenceArchive:
    def __init__(self, store_root=None, results_root=RESULTS_ROOT, legacy_indices=None):
        self.store = store_module.EvidenceStore(store_root)
        self.results_root = Path(results_root).resolve()
        self.compressed = self.store.objects / 'jsonl-gzip-v1'
        self.legacy_indices = tuple(Path(p).absolute() for p in
                                   ((LEGACY_INDEX,) if legacy_indices is None else legacy_indices))

    def _verify_gzip(self, path, raw_sha, raw_size):
        with gzip.open(str(path), 'rb') as stream:
            digest, size = _sha_size(stream)
        if digest != raw_sha or size != raw_size:
            raise EvidenceArchiveError('Decompressed evidence SHA/size mismatch: ' + str(path))
        return _file_sha_size(path)

    def _compress(self, guard, snapshot):
        descriptor, name = tempfile.mkstemp(prefix='.jsonl-evidence-', suffix='.tmp',
                                             dir=str(self.store.incoming))
        temporary = Path(name)
        try:
            guard.stream.seek(0)
            digest = hashlib.sha256()
            count = 0
            with os.fdopen(descriptor, 'wb') as target:
                with gzip.GzipFile(filename='', mode='wb', fileobj=target, compresslevel=1, mtime=0) as encoded:
                    for chunk in iter(lambda: guard.stream.read(_CHUNK), b''):
                        encoded.write(chunk)
                        digest.update(chunk)
                        count += len(chunk)
                target.flush()
                os.fsync(target.fileno())
            guard.assert_identity(snapshot)
            if digest.hexdigest() != snapshot.sha256 or count != snapshot.size_bytes:
                raise EvidenceArchiveError('Raw stream differs from its completion proof')
            self._verify_gzip(temporary, snapshot.sha256, snapshot.size_bytes)
            _bounded(self.store.objects, self.store.root, directory=True)
            # Publishers can reach a fresh store together. mkdir(exist_ok=True)
            # handles that race; the following boundary check still rejects a
            # file or reparse point installed at this path.
            self.compressed.mkdir(exist_ok=True)
            _bounded(self.compressed, self.store.root, directory=True)
            bucket = self.compressed / snapshot.sha256[:2]
            bucket.mkdir(exist_ok=True)
            _bounded(bucket, self.store.root, directory=True)
            target = bucket / (snapshot.sha256 + '.gz')
            with self.store._publication_lock():
                if os.path.lexists(str(target)):
                    _bounded(target, self.store.root)
                    compressed_sha, compressed_size = self._verify_gzip(target, snapshot.sha256, snapshot.size_bytes)
                else:
                    self.store._publish_no_replace(temporary, target)
                    _bounded(target, self.store.root)
                    compressed_sha, compressed_size = self._verify_gzip(target, snapshot.sha256, snapshot.size_bytes)
                store_module._protect(target, 0o444)
            return dict(raw_sha256=snapshot.sha256, raw_bytes=snapshot.size_bytes,
                        gzip_sha256=compressed_sha, gzip_bytes=compressed_size,
                        object=target.relative_to(self.store.root).as_posix())
        finally:
            store_module._remove_private_temp(temporary)

    def _read_manifest(self, path):
        _bounded(path, self.results_root)
        envelope = json.loads(path.read_text(encoding='utf-8'))
        if not isinstance(envelope, dict) or envelope.get('format') != FORMAT:
            raise EvidenceArchiveError('Unrecognized evidence archive manifest')
        payload = envelope.get('payload')
        if not isinstance(payload, dict) or hashlib.sha256(_canonical(payload)).hexdigest() != envelope.get('payload_sha256'):
            raise EvidenceArchiveError('Evidence archive manifest checksum mismatch')
        if payload.get('schema') != 1 or not isinstance(payload.get('files'), dict):
            raise EvidenceArchiveError('Malformed evidence archive payload')
        if any(name not in _ALLOWED_NAMES for name in payload['files']):
            raise EvidenceArchiveError('Manifest contains an unsupported raw filename')
        _valid_sha(payload.get('summary_sha256'))
        if type(payload.get('producer_exit_code')) is not int:
            raise EvidenceArchiveError('Malformed producer completion metadata')
        if Path(payload.get('store_root', '')).resolve() != self.store.root:
            raise EvidenceArchiveError('Manifest points outside the configured evidence store')
        return payload

    def _write_manifest(self, proof, records):
        target = proof.run_root / MANIFEST_NAME
        with self.store._publication_lock():
            if os.path.lexists(str(target)):
                payload = self._read_manifest(target)
                if (payload.get('summary_sha256') != proof.summary_sha256
                        or payload.get('producer_exit_code') != proof.producer_exit_code):
                    raise EvidenceArchiveError('Refusing to rewrite a prior run archive')
            else:
                payload = dict(schema=1, store_root=str(self.store.root),
                               summary_sha256=proof.summary_sha256,
                               producer_exit_code=proof.producer_exit_code, files={})
            for name, record in records.items():
                existing = payload['files'].get(name)
                if existing is not None and existing != record:
                    raise EvidenceArchiveError('Existing archive record differs: ' + name)
                payload['files'][name] = record
            envelope = dict(format=FORMAT, payload=payload,
                            payload_sha256=hashlib.sha256(_canonical(payload)).hexdigest())
            descriptor, name = tempfile.mkstemp(prefix='.evidence-manifest-', suffix='.tmp', dir=str(proof.run_root))
            temporary = Path(name)
            try:
                with os.fdopen(descriptor, 'wb') as stream:
                    stream.write(_canonical(envelope) + b'\n')
                    stream.flush()
                    os.fsync(stream.fileno())
                _bounded(target, self.results_root, must_exist=False)
                os.replace(str(temporary), str(target))
                if self._read_manifest(target) != payload:
                    raise EvidenceArchiveError('Published archive manifest differs from its verified payload')
            finally:
                store_module._remove_private_temp(temporary)
        return target

    def archive_completed_run(self, proof, *, remove_raw=True):
        with _PROOF_LOCK:
            record = _PROOFS.get(proof)
            if (record is None or record['pid'] != os.getpid() or proof.process_id != os.getpid()
                    or record['state'] != 'ready'):
                raise EvidenceArchiveError('Fresh same-process completion proof required')
            if proof.results_root != self.results_root or record['root'] != proof.run_root:
                raise EvidenceArchiveError('Completion proof belongs to another approved root')
            if proof.snapshots != record['snapshots'] or not all(s.closed for s in record['streams']):
                raise EvidenceArchiveError('Completion proof or closed-stream state changed')
            if remove_raw and os.name != 'nt':
                raise EvidenceArchiveError('Use remove_raw=False without native writer exclusion')
            record['state'] = 'claimed'
        committed = False
        try:
            _bounded(proof.run_root, self.results_root, directory=True)
            self.store._prepare()
            records = {}
            removed, retained, errors = [], [], []
            with ExitStack() as stack:
                metadata_guards = []
                for name, expected in record['metadata'].items():
                    path = _bounded(proof.run_root / name, self.results_root)
                    guard = stack.enter_context(_LockedRaw(path))
                    if guard.snapshot().sha256 != expected:
                        raise EvidenceArchiveError('Original metadata changed after completion proof: ' + name)
                    metadata_guards.append(guard)
                guards = []
                # Open and revalidate EVERY source before creating/deleting any raw path.
                for snapshot in proof.snapshots:
                    path = _bounded(proof.run_root / snapshot.name, self.results_root)
                    guard = stack.enter_context(_LockedRaw(path, delete_access=remove_raw))
                    if guard.snapshot() != snapshot:
                        raise EvidenceArchiveError('Raw evidence changed after completion proof: ' + snapshot.name)
                    guards.append((guard, snapshot))
                for guard, snapshot in guards:
                    records[snapshot.name] = self._compress(guard, snapshot)
                manifest = self._write_manifest(proof, records)
                for guard, snapshot in guards:
                    _bounded(guard.path, self.results_root)
                    guard.assert_identity(snapshot)
                with _PROOF_LOCK:
                    record['state'] = 'consumed'
                committed = True
                # All fallible archive/metadata work is complete before removal.
                # Deletion failures retain that original and are explicit results.
                for guard, snapshot in guards:
                    if not remove_raw:
                        retained.append(snapshot.name)
                        continue
                    try:
                        guard.delete_verified_handle()
                        removed.append(snapshot.name)
                    except OSError as error:
                        retained.append(snapshot.name)
                        errors.append((snapshot.name, repr(error)))
            return ArchiveResult(manifest, tuple(removed), tuple(retained), tuple(errors),
                                 sum(snapshot.size_bytes for snapshot in proof.snapshots))
        finally:
            if not committed:
                with _PROOF_LOCK:
                    record['state'] = 'ready'

    def _descriptor(self, raw_path, record, provenance, object_root=None):
        if not isinstance(record, dict):
            raise EvidenceArchiveError('Malformed archived stream record')
        raw_sha = _valid_sha(record.get('raw_sha256'))
        gzip_sha = _valid_sha(record.get('gzip_sha256'))
        raw_size, gzip_size = record.get('raw_bytes'), record.get('gzip_bytes')
        if type(raw_size) is not int or raw_size < 0 or type(gzip_size) is not int or gzip_size < 0:
            raise EvidenceArchiveError('Malformed archived stream byte count')
        if not isinstance(record.get('object'), str):
            raise EvidenceArchiveError('Malformed archived object path')
        relative = Path(record['object'])
        if relative.is_absolute() or '..' in relative.parts or not relative.parts:
            raise EvidenceArchiveError('Archived object path is not bounded')
        root = self.store.root if object_root is None else object_root
        obj = _bounded(root / relative, root)
        if obj.name != raw_sha + '.gz':
            raise EvidenceArchiveError('Object filename differs from its raw SHA')
        return ArchivedFile(raw_path, obj, raw_sha, raw_size, gzip_sha, gzip_size, provenance)

    def _legacy_descriptor(self, raw_path):
        try:
            key = raw_path.relative_to(ROOT).as_posix()
        except ValueError:
            return None
        for index in self.legacy_indices:
            if not index.exists():
                continue
            _bounded(index, index.parent)
            # immutable=1 forbids journal/WAL creation and mutation of old evidence.
            uri = index.as_uri() + '?mode=ro&immutable=1'
            database = sqlite3.connect(uri, uri=True)
            try:
                row = database.execute('''SELECT f.sha,f.size,b.archive_path,b.compressed_sha,b.compressed_size
                    FROM files f JOIN blobs b ON f.sha=b.sha WHERE f.path=? AND f.deleted=1''', (key,)).fetchone()
            finally:
                database.close()
            if row is not None:
                sha, size, obj, compressed_sha, compressed_size = row
                return self._descriptor(raw_path, dict(raw_sha256=sha, raw_bytes=size, object=obj,
                                        gzip_sha256=compressed_sha, gzip_bytes=compressed_size), index, index.parent)
        return None

    def describe(self, path):
        path = _bounded(Path(path).absolute(), self.results_root, must_exist=False)
        manifest = path.parent / MANIFEST_NAME
        if os.path.lexists(str(manifest)):
            payload = self._read_manifest(manifest)
            record = payload['files'].get(path.name)
            if record is not None:
                return self._descriptor(path, record, manifest)
        return self._legacy_descriptor(path)

    def open_evidence(self, path, mode='r', encoding='utf-8', errors=None, newline=None):
        if mode not in ('r', 'rt', 'rb'):
            raise ValueError('open_evidence is read-only; writers must use their original raw paths')
        path = _bounded(Path(path).absolute(), self.results_root, must_exist=False)
        if path.exists():
            return path.open(mode, **({} if mode == 'rb' else dict(encoding=encoding, errors=errors, newline=newline)))
        archived = self.describe(path)
        if archived is None:
            raise FileNotFoundError(str(path))
        if _file_sha_size(archived.object_path) != (archived.gzip_sha256, archived.gzip_size):
            raise EvidenceArchiveError('Compressed evidence SHA/size mismatch: ' + str(archived.object_path))
        cache_key = (archived.gzip_sha256, archived.gzip_size, archived.raw_sha256, archived.raw_size)
        with _VERIFIED_GZIP_LOCK:
            verified = cache_key in _VERIFIED_GZIP
        if not verified:
            with gzip.open(str(archived.object_path), 'rb') as check:
                if _sha_size(check) != (archived.raw_sha256, archived.raw_size):
                    raise EvidenceArchiveError('Archived original SHA/size mismatch')
            with _VERIFIED_GZIP_LOCK:
                if len(_VERIFIED_GZIP) >= 1024:
                    _VERIFIED_GZIP.clear()
                _VERIFIED_GZIP.add(cache_key)
        if mode == 'rb':
            return gzip.open(str(archived.object_path), 'rb')
        return gzip.open(str(archived.object_path), 'rt', encoding=encoding, errors=errors, newline=newline)

    def evidence_exists(self, path):
        path = _bounded(Path(path).absolute(), self.results_root, must_exist=False)
        return path.exists() or self.describe(path) is not None

    def evidence_sha256(self, path):
        with self.open_evidence(path, 'rb') as stream:
            return _sha_size(stream)[0]


def archive_completed_run(proof, *, store_root=None, remove_raw=True):
    return EvidenceArchive(store_root, results_root=proof.results_root).archive_completed_run(proof, remove_raw=remove_raw)


def open_evidence(path, mode='r', encoding='utf-8', errors=None, newline=None, *, store_root=None,
                  results_root=RESULTS_ROOT, legacy_indices=None):
    return EvidenceArchive(store_root, results_root, legacy_indices).open_evidence(path, mode, encoding, errors, newline)


def evidence_exists(path, *, store_root=None, results_root=RESULTS_ROOT, legacy_indices=None):
    return EvidenceArchive(store_root, results_root, legacy_indices).evidence_exists(path)


def evidence_sha256(path, *, store_root=None, results_root=RESULTS_ROOT, legacy_indices=None):
    return EvidenceArchive(store_root, results_root, legacy_indices).evidence_sha256(path)


def finish_verification(out, *, producer, closed_streams, behavior_passed,
                        store_root=None, results_root=RESULTS_ROOT):
    """Shared verifier epilogue; preserve its already-written behavior report.

    Call explicitly after all JSONL with blocks and summary.json publication.
    Storage results get their own archive-status.json. A storage failure returns
    exit 2 even when the unchanged behavior report is PASS; behavior failure
    remains exit 1 when its complete raw evidence was successfully archived.
    """
    out = _bounded(Path(out).absolute(), Path(results_root).resolve(), directory=True)
    try:
        summary_path = _bounded(out / 'summary.json', Path(results_root).resolve())
        preserved_report = json.loads(summary_path.read_text(encoding='utf-8'))
        if type(behavior_passed) is not bool or preserved_report.get('passed') is not behavior_passed:
            raise EvidenceArchiveError('Verifier exit status differs from its immutable behavior report')
        proof = completion_proof(out, producer=producer, closed_streams=closed_streams,
                                 results_root=results_root)
        archived = EvidenceArchive(store_root, results_root).archive_completed_run(proof)
        status = dict(passed=not archived.errors, manifest=str(archived.manifest_path),
                      removed=list(archived.removed), retained=list(archived.retained),
                      errors=list(archived.errors), original_bytes=archived.original_bytes)
    except Exception as error:
        status = dict(passed=False, error=repr(error))
    target = _bounded(out / 'archive-status.json', Path(results_root).resolve(), must_exist=False)
    target.write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(dict(evidence_archive=status), ensure_ascii=False), flush=True)
    return (0 if behavior_passed else 1) if status['passed'] else 2
