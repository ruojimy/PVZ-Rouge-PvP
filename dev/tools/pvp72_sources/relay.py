"""Outbound relay adapters; the Direct game transport remains authoritative.

The host uses a private loopback bridge. The guest injects an already paired
socket through ClientTransport._connect. Constructors never wait on the WAN.
"""
import json
import os
from pathlib import Path
import queue
import select
import socket
import struct
import sys
import threading
import time

from .network import ServerTransport, ClientTransport, _Connection, parse_endpoint

RELAY_VERSION = 1
DEFAULT_RELAY_PORT = 24562
ALPHABET = '0123456789ABCDEFGHJKMNPQRSTVWXYZ'


class RelayError(OSError):
    pass


def normalize_code(code):
    if not isinstance(code, str):
        raise ValueError('房间码格式不正确')
    code = code.strip().upper().replace('-', '').replace(' ', '')
    if len(code) != 10 or any(c not in ALPHABET for c in code):
        raise ValueError('云端房间码应为 10 位字母或数字')
    return code


def configured_endpoint():
    value = os.environ.get('PVP_RELAY_ENDPOINT')
    if value:
        try:
            parse_endpoint(value, DEFAULT_RELAY_PORT)
            return value.strip()
        except ValueError:
            return ''
    candidates = [Path.cwd() / 'relay.json']
    executable = getattr(sys, 'executable', None)
    if executable:
        candidates.insert(0, Path(executable).resolve().parent / 'relay.json')
    # Android's original-game handoff changes cwd to its art directory. The
    # relay config stays at the APK application root beside pvp/, independent
    # of the menu that launches this room. The next parent is the source root
    # in the desktop modkit/pvp layout.
    candidates.extend(parent / 'relay.json' for parent in list(Path(__file__).resolve().parents)[1:3])
    for path in candidates:
        if path.is_file():
            try:
                value = json.loads(path.read_text(encoding='utf-8-sig'))['endpoint']
                parse_endpoint(value, DEFAULT_RELAY_PORT)
                return value
            except (OSError, ValueError, KeyError, TypeError):
                return ''
    return ''


def send_control(sock, value):
    data = json.dumps(dict(value, relay_protocol=RELAY_VERSION), separators=(',', ':')).encode('utf8')
    if len(data) > 2048:
        raise RelayError('invalid_preamble')
    sock.sendall(struct.pack('!I', len(data)) + data)


def receive_control(sock, stop, timeout=6., max_bytes=2048):
    deadline = time.monotonic() + timeout
    def exact(size):
        data = bytearray()
        while len(data) < size:
            if stop.is_set():
                raise RelayError('cancelled')
            if time.monotonic() >= deadline:
                raise RelayError('relay_timeout')
            readable, _, _ = select.select([sock], [], [], .05)
            if readable:
                chunk = sock.recv(size-len(data))
                if not chunk:
                    raise RelayError('relay_unreachable')
                data.extend(chunk)
        return bytes(data)
    size = struct.unpack('!I', exact(4))[0]
    if not 0 < size <= max_bytes:
        raise RelayError('invalid_preamble')
    try:
        value = json.loads(exact(size).decode('utf8'))
    except (ValueError, UnicodeError):
        raise RelayError('invalid_preamble')
    if not isinstance(value, dict) or value.get('relay_protocol') != RELAY_VERSION:
        raise RelayError('relay_protocol_mismatch')
    if value.get('status') == 'error':
        raise RelayError(str(value.get('code', 'relay_unreachable'))[:64])
    return value


def paired(sock, stop):
    while True:
        response = receive_control(sock, stop)
        if response.get('status') == 'paired':
            return
        if response.get('status') != 'waiting':
            raise RelayError('invalid_preamble')


class RelayClientTransport(ClientTransport):
    def __init__(self, endpoint, *, room_code, **options):
        self.relay_code = normalize_code(room_code)
        self.relay_secret = None
        self._relay_spectator=options.get('spectator',False)
        self._take_seat_on_connect=False
        super().__init__(endpoint, DEFAULT_RELAY_PORT, room_code=self.relay_code, **options)

    def _connect(self, remaining=None):
        conn = super()._connect(remaining)
        try:
            conn.sock.settimeout(self.connect_timeout)
            send_control(conn.sock, dict(action='spectate' if self._relay_spectator else 'join', code=self.relay_code, secret=self.relay_secret,
                                         player_lanes=True))
            try:response = receive_control(conn.sock, self._stop)
            except RelayError as exc:
                # A spectating host can have two remote players. Reuse an
                # independent legacy relay lane; Room still admits only two
                # actual player seats and rejects an otherwise full room.
                if str(exc)!='room_full' or self._relay_spectator or self.relay_secret:raise
                conn.sock.close();conn=super()._connect(remaining)
                conn.sock.settimeout(self.connect_timeout)
                self._relay_spectator=True
                self.spectator=True;self._take_seat_on_connect=True
                send_control(conn.sock,dict(action='spectate',code=self.relay_code))
                response=receive_control(conn.sock,self._stop)
            if response.get('status') != 'joined' or not isinstance(response.get('secret'), str):
                raise RelayError('invalid_preamble')
            if response.get('player_lane') is True:
                self._relay_spectator=True
                self.spectator=True
                self._take_seat_on_connect=True
            self.relay_secret = response['secret']
            paired(conn.sock, self._stop)
            conn.sock.setblocking(False)
            return _Connection(conn.sock, self.max_frame_bytes)
        except (OSError, ValueError) as exc:
            conn.sock.close()
            if not self._ever_connected or (isinstance(exc,RelayError) and str(exc)=='spectators_disabled'):
                self._terminal_rejection = True
                self._emit('error', code=str(exc) if isinstance(exc, RelayError) else 'relay_unreachable')
            raise


class RelayHostTransport:
    def __init__(self, endpoint, *, identity=None, public=False, name='', in_use=None, **options):
        self.endpoint = parse_endpoint(endpoint, DEFAULT_RELAY_PORT)
        self.code = None
        self.secret = None
        self.spectators_supported=False
        self.room_roles_supported=False
        self._room_policy=None
        self.public, self.name = public, name
        # ``in_use`` reports a room that is actually being played but holds no
        # remote socket: a running match, or seats an AI teammate occupies.
        # The relay only sees a host lane waiting for a guest, so it reclaims
        # such a room after its waiting timeout; that must never end the match.
        self._in_use = in_use if callable(in_use) else (lambda: bool(in_use))
        self._stop = threading.Event()
        self._events = queue.Queue(maxsize=128)
        self._remote = None
        self._reset_guest = threading.Event()
        self.inner = ServerTransport('127.0.0.1', 0, identity=identity, **options)
        self._spectator_policy=threading.Event()
        self._spectator_remotes={}
        self._spectator_threads=[threading.Thread(target=self._watch_run,args=(index,),
                                 name='PvP-relay-watch-%d'%index,daemon=True)
                                 for index in range(self.inner.max_spectators)]
        self._policy_thread=threading.Thread(target=self._policy_run,name='PvP-relay-watch-policy',daemon=True)
        self._thread = threading.Thread(target=self._run, name='PvP-relay-host', daemon=True)
        self._thread.start()
        for thread in self._spectator_threads+[self._policy_thread]:thread.start()

    def __getattr__(self, name):
        return getattr(self.inner, name)

    def emit(self, kind, **values):
        try:
            self._events.put_nowait(dict(values, type=kind))
        except queue.Full:
            self._stop.set()

    def poll(self, limit=100):
        result = []
        while len(result) < limit:
            try:
                result.append(self._events.get_nowait())
            except queue.Empty:
                break
        result.extend(e for e in self.inner.poll(limit) if e['type'] != 'listening')
        return result

    def close(self):
        self._stop.set()
        for remote in list(self._spectator_remotes.copy().values()):
            try:remote.shutdown(socket.SHUT_RDWR)
            except OSError:pass
        self.inner.close()
        self._thread.join(.2)

    def set_allow_spectators(self,enabled):
        self.inner.set_allow_spectators(enabled)
        self._spectator_policy.set()

    def set_room_policy(self,available_seats,spectator_count):
        policy=dict(available_seats=max(0,min(4,int(available_seats))),
                    spectator_count=max(0,min(5,int(spectator_count))),
                    allow_spectators=self.inner.allow_spectators)
        if policy!=self._room_policy:
            self._room_policy=policy;self._spectator_policy.set()

    def set_peer_role(self,peer_id,spectator):
        error=self.inner.set_peer_role(peer_id,spectator)
        if not error:self._spectator_policy.set()
        return error

    def _relay_watch_enabled(self):
        # The cloud tunnels are byte-only and do not assign game authority.
        # Keep a promoted player's original lane available, including reconnect;
        # the inner server continues enforcing the host's spectator gate.
        return self.inner.allow_spectators or bool(self._room_policy and self._room_policy['available_seats']) or any(s.get('relay_spectator') and not s.get('spectator')
                                                 for s in self.inner._sessions.copy().values())

    def _policy_run(self):
        while not self._stop.wait(.1):
            if not self.code or not self.spectators_supported or not self._spectator_policy.is_set():continue
            enabled=self._relay_watch_enabled()
            policy=dict(self._room_policy) if self._room_policy else None
            try:
                with socket.create_connection(self.endpoint,timeout=2.) as remote:
                    send_control(remote,dict(action='configure_spectators',code=self.code,
                                             secret=self.secret,enabled=enabled,
                                             room_policy=policy if self.room_roles_supported else None))
                    receive_control(remote,self._stop)
                if self._relay_watch_enabled()==enabled and policy==self._room_policy:self._spectator_policy.clear()
            except (OSError,ValueError):
                if not self._stop.wait(1.):self._spectator_policy.set()

    def _watch_run(self,index):
        retry=.5
        while not self._stop.is_set():
            if not self.code or not self.spectators_supported or not self._relay_watch_enabled():
                self._stop.wait(.1);continue
            remote=local=None
            try:
                remote=socket.create_connection(self.endpoint,timeout=3.)
                self._spectator_remotes[index]=remote
                remote.setsockopt(socket.IPPROTO_TCP,socket.TCP_NODELAY,1)
                send_control(remote,dict(action='watch_host',code=self.code,secret=self.secret,lane=index))
                if receive_control(remote,self._stop).get('status')!='watch_ready':raise RelayError('invalid_preamble')
                paired(remote,self._stop)
                local=socket.create_connection(('127.0.0.1',self.inner.port),timeout=2.)
                local.setsockopt(socket.IPPROTO_TCP,socket.TCP_NODELAY,1)
                self.bridge(remote,local)
                retry=.5
            except (OSError,ValueError):retry=min(8.,retry*2)
            finally:
                self._spectator_remotes.pop(index,None)
                for sock in (remote,local):
                    if sock:sock.close()
            self._stop.wait(retry)

    def release_peer(self, peer_id):
        session=next((s for s in self.inner._sessions.copy().values() if s['peer_id']==peer_id),None)
        spectator=self.inner._peer_channels.get(peer_id,bool(session and session.get('relay_spectator'))) or str(peer_id).startswith('spectator-')
        removed = self.inner.release_peer(peer_id)
        self.inner._peer_channels.pop(peer_id,None)
        self._spectator_policy.set()
        if spectator:return removed
        if not removed and any(not s.get('spectator') for s in self.inner._sessions.copy().values()):
            return False
        # The cloud reservation is independent of the inner game session.
        # Restart even if the bridge has already re-entered its waiting state.
        self._reset_guest.set()
        remote = self._remote
        if remote is not None:
            try:
                remote.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
        return True

    def _sessions_connected(self):
        return any(s.get('connection') is not None for s in self.inner._sessions.copy().values())

    def _room_in_use(self):
        """A networked seat/audience, or a local room that is really being played.

        Co-op against an AI teammate keeps no remote session at all, which is
        why the relay's 10-minute guest wait used to expire a room mid-match.
        """
        return self._sessions_connected() or bool(self._in_use())

    def _run(self):
        deadline = None
        try:
            while self.inner.address is None and not self._stop.wait(.01):
                if self.inner.state == 'closed':
                    return
            while not self._stop.is_set():
                remote = local = None
                try:
                    remote = socket.create_connection(self.endpoint, timeout=4.)
                    self._remote = remote
                    remote.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                    remote.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
                    send_control(remote, dict(action='resume_host' if self.code else 'create', code=self.code, secret=self.secret,
                                              public=self.public, name=self.name, build=self.inner.identity.get('build', ''),
                                              allow_spectators=self._relay_watch_enabled(),
                                              reset_guest=self._reset_guest.is_set() or not any(not s.get('relay_spectator') for s in self.inner._sessions.copy().values())))
                    response = receive_control(remote, self._stop)
                    if response.get('status') != 'registered' or not isinstance(response.get('secret'), str):
                        raise RelayError('invalid_preamble')
                    self.code = normalize_code(response.get('code'))
                    self.secret = response['secret']
                    self.spectators_supported=response.get('spectators_supported') is True
                    self.room_roles_supported=response.get('room_roles_supported') is True
                    self._spectator_policy.set()
                    self._reset_guest.clear()
                    self.inner.room_code = self.code
                    self.emit('relay_ready', room_code=self.code)
                    deadline = None
                    paired(remote, self._stop)
                    local = socket.create_connection(('127.0.0.1', self.inner.port), timeout=2.)
                    local.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                    self.bridge(remote, local)
                except (OSError, ValueError) as exc:
                    if self._stop.is_set():
                        break
                    code = str(exc) if isinstance(exc, RelayError) else 'relay_unreachable'
                    if self._room_in_use():
                        # The room is being played (player report 10-16: a co-op
                        # match with an AI teammate was told "云端房间已过期" and
                        # thrown back to the menu). A reclaimed reservation may
                        # only cost the room code: keep it inside the server's
                        # resume window, then silently reserve a new room.
                        if code in ('room_not_found', 'resume_rejected') or (
                                code == 'room_expired' and deadline is not None
                                and time.monotonic() >= deadline):
                            self.code = None
                            self.secret = None
                            self.inner.room_code = ''
                            self.emit('relay_reclaimed')
                            deadline = None
                        elif code == 'room_expired':
                            deadline = deadline or time.monotonic() + 20.
                        self._stop.wait(.5)
                        continue
                    # Nothing is playing yet: this is still a waiting room, so a
                    # lost reservation is reported exactly as before.
                    # The relay ends a main lane that waited 10 minutes for its
                    # guest with room_expired, even while a seated player or
                    # audience plays through a watch lane. That room is alive:
                    # re-register within the resume window instead of closing.
                    expired_in_use = code == 'room_expired' and self.code and self._sessions_connected()
                    if not self.code or (code in ('room_not_found', 'room_expired', 'resume_rejected')
                                         and not expired_in_use):
                        self.emit('error', code=code, relay_terminal=True)
                        break
                    deadline = deadline or time.monotonic() + 20.
                    if time.monotonic() >= deadline:
                        self.emit('error', code='reconnect_expired', relay_terminal=True)
                        break
                finally:
                    self._remote = None
                    for sock in (local, remote):
                        if sock:
                            sock.close()
                self._stop.wait(.5)
        finally:
            self._stop.set()

    def bridge(self, remote, local):
        sockets = [remote, local]
        for sock in sockets:
            sock.setblocking(False)
            # Propagate pressure across both the loopback and cloud segments.
            # The byte bridge below already caps each application queue at 64KiB.
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 65536)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 65536)
        pending = {remote: bytearray(), local: bytearray()}
        last_progress = time.monotonic()
        while not self._stop.is_set():
            # Keep each direction at <=64 KiB, including the next recv. A
            # room with three remote players must not multiply 256 KiB queues.
            readers = [sock for sock in sockets if len(pending[local if sock is remote else remote]) < 65536]
            writers = [sock for sock in sockets if pending[sock]]
            readable, writable, errors = select.select(readers, writers, sockets, .05)
            if errors or time.monotonic()-last_progress > 15:
                raise RelayError('relay_timeout')
            for sock in writable:
                try:
                    count = sock.send(pending[sock])
                    if not count:
                        return
                    del pending[sock][:count]
                    last_progress = time.monotonic()
                except BlockingIOError:
                    pass
            for sock in readable:
                try:
                    target = local if sock is remote else remote
                    chunk = sock.recv(min(16384, 65536 - len(pending[target])))
                    if not chunk:
                        return
                    pending[target].extend(chunk)
                    last_progress = time.monotonic()
                except BlockingIOError:
                    pass


class LobbyQuery:
    """One bounded, cancellable background listing. No I/O from UI polling."""
    def __init__(self, endpoint):
        self.endpoint = parse_endpoint(endpoint, DEFAULT_RELAY_PORT)
        self.stop = threading.Event()
        self.results = queue.Queue(maxsize=1)
        self.thread = threading.Thread(target=self.run, name='PvP-relay-lobby', daemon=True)
        self.thread.start()

    def run(self):
        try:
            with socket.create_connection(self.endpoint, timeout=4.) as sock:
                send_control(sock, dict(action='list'))
                reply = receive_control(sock, self.stop, max_bytes=65536)
                if reply.get('status') != 'rooms' or not isinstance(reply.get('rooms'), list) or len(reply['rooms']) > 200:
                    raise RelayError('invalid_preamble')
                rooms = []
                for room in reply['rooms']:
                    if not isinstance(room, dict) or not isinstance(room.get('name'), str) or not isinstance(room.get('build'), str):
                        raise RelayError('invalid_preamble')
                    rooms.append(dict(code=normalize_code(room.get('code')), name=room['name'][:24], build=room['build'][:48], joinable=room.get('joinable') is True,
                                      allow_spectators=room.get('allow_spectators') is True,
                                      spectator_count=max(0,min(5,room.get('spectator_count',0))) if type(room.get('spectator_count',0)) is int else 0))
                self.results.put_nowait(dict(rooms=rooms))
        except (OSError, ValueError) as exc:
            self.results.put_nowait(dict(error=str(exc) if isinstance(exc, RelayError) else 'relay_unreachable'))

    def poll(self):
        try:
            return self.results.get_nowait()
        except queue.Empty:
            return None

    def close(self):
        self.stop.set()
