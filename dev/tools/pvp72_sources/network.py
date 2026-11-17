"""Bounded JSON/TCP transport for the PvP host-authoritative application.

Python 3.8, standard library only. Network I/O and name resolution run on the
worker. ``send`` queues data and signals a nonblocking local wakeup socket;
``poll`` and constructors do no socket I/O. The application owns game validation,
snapshots, roles, and disconnect outcomes; transport messages grant no authority.

``ServerTransport('::', 24561, identity={...})`` starts a background listener.
``ClientTransport('[::1]:24561', identity={...})`` starts a background connector.
``poll()`` returns event dictionaries, including connected/message/disconnected.
``send(peer_id, payload)`` sends a JSON object; the client also accepts
``send(payload)``. It returns False if disconnected or backpressured and raises
ValueError for an invalid payload. Payloads are copied before queuing.

The client automatically attempts a bounded reconnect after an established
connection is lost. Every successful connection requires an application-level
full authoritative snapshot: transport does not replay missed game messages.
Keep session_id/token from connected events in memory, never in public logs.
The room code is admission control, not encryption; TCP is not authenticated
against an on-path attacker. No firewall or router configuration is changed.
"""

# Load the idna codec before any transport thread exists. getaddrinfo encodes
# host names with it lazily; the first lookup racing between the network thread
# and the UI thread (create(): ServerTransport + local_endpoints) can cache the
# codec as missing for the whole process (CPython bpo-29288) -> every later
# "LookupError: unknown encoding: idna".
import encodings.idna  # noqa: F401
import errno
import hmac
import json
import math
import queue
import secrets
import select
import socket
import struct
import threading
import time



PROTOCOL_VERSION = 1
DEFAULT_PORT = 24561
MAX_FRAME_BYTES = 1024 * 1024
_HEADER = struct.Struct('!I')
LATENCY_KINDS = ('latency_probe', 'latency_echo')


def supersedes_snapshot(event, previous):
    """Only adjacent independent states in the same stream may be replaced."""
    payload = event.get('payload', {})
    old = previous.get('payload', {})
    return (event.get('type') == previous.get('type') == 'message'
            and event.get('peer_id') == previous.get('peer_id')
            and payload.get('type') == old.get('type') == 'room_snapshot'
            and old.get('map_included') is False
            and payload.get('snapshot_stream') is not None
            and payload.get('snapshot_stream') == old.get('snapshot_stream'))


def valid_latency_payload(payload):
    """Diagnostics may carry only a bounded, opaque nonce (never credentials)."""
    if not isinstance(payload, dict) or len(payload) != 2 or set(payload) != {'type', 'nonce'}:
        return False
    nonce = payload['nonce']
    return (payload['type'] in LATENCY_KINDS and isinstance(nonce, str) and
            len(nonce) == 16 and all(ch in '0123456789abcdef' for ch in nonce))


def allow_latency_payload(conn, payload, now):
    """Limit optional diagnostics before they enter the application queue."""
    if not valid_latency_payload(payload):
        return False
    previous = getattr(conn, 'latency_rate_at', now)
    tokens = min(4., getattr(conn, 'latency_tokens', 4.) + max(0., now - previous) * 2.)
    conn.latency_rate_at = now
    if tokens < 1.:
        conn.latency_tokens = tokens
        return False
    conn.latency_tokens = tokens - 1.
    return True


class ProtocolError(ValueError):
    pass


def parse_endpoint(endpoint, port=DEFAULT_PORT):
    """Return (host, port); IPv6 with an explicit port requires brackets."""
    if not isinstance(endpoint, str):
        raise ValueError('address must be text')
    value = endpoint.strip()
    if not value or any(ch.isspace() for ch in value) or any(ch in value for ch in '/\\'):
        raise ValueError('invalid address; use hostname:port or [IPv6]:port')
    if value.startswith('['):
        end = value.find(']')
        if end < 0:
            raise ValueError('IPv6 address is missing ]')
        host, suffix = value[1:end], value[end + 1:]
        if suffix:
            if not suffix.startswith(':') or not suffix[1:].isdigit():
                raise ValueError('invalid port after IPv6 address')
            port = int(suffix[1:])
        try:
            socket.inet_pton(socket.AF_INET6, host.split('%', 1)[0])
        except OSError:
            raise ValueError('invalid IPv6 address')
    elif value.count(':') == 1:
        host, port_text = value.rsplit(':', 1)
        if not port_text.isdigit():
            raise ValueError('port must be a number')
        port = int(port_text)
    else:
        host = value
        if ':' in host:
            try:
                socket.inet_pton(socket.AF_INET6, host.split('%', 1)[0])
            except OSError:
                raise ValueError('invalid IPv6 address; use [IPv6]:port')
    if not host or '[' in host or ']' in host:
        raise ValueError('invalid host')
    if isinstance(port, bool) or not isinstance(port, int) or not 1 <= port <= 65535:
        raise ValueError('port must be between 1 and 65535')
    return host, port


def _identity(value):
    result = {'protocol': PROTOCOL_VERSION, 'build': 'development', 'rules_hash': ''}
    if value is not None:
        if not isinstance(value, dict):
            raise ValueError('identity must be a JSON object')
        result.update(value)
    if result.get('protocol') != PROTOCOL_VERSION:
        raise ValueError('unsupported local protocol')
    for key, item in result.items():
        if not isinstance(key, str) or not isinstance(item, (str, int)) or isinstance(item, bool):
            raise ValueError('identity values must be strings or integers')
    if len(json.dumps(result)) > 8192:
        raise ValueError('identity too large')
    return result


def _reject_constant(value):
    raise ProtocolError('non-finite JSON number')


def _finite_float(value):
    result = float(value)
    if not math.isfinite(result):
        raise ProtocolError('non-finite JSON number')
    return result


def _decode(data):
    try:
        value = json.loads(data.decode('utf-8'), parse_constant=_reject_constant,
                           parse_float=_finite_float)
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise ProtocolError('invalid JSON: ' + type(exc).__name__)
    if not isinstance(value, dict):
        raise ProtocolError('frame must contain a JSON object')
    return value


def encode_frame(message, max_frame_bytes=MAX_FRAME_BYTES):
    """Encode a bounded JSON object. Exported for protocol diagnostics/tests."""
    if not isinstance(message, dict):
        raise ValueError('message must be a JSON object')
    try:
        raw = json.dumps(message, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode('utf-8')
    except (TypeError, ValueError, UnicodeError, RecursionError) as exc:
        raise ValueError('message is not finite JSON: ' + type(exc).__name__)
    if not 0 < len(raw) <= max_frame_bytes:
        raise ValueError('message exceeds frame limit')
    return _HEADER.pack(len(raw)) + raw


class FrameDecoder:
    """Incremental decoder handling fragmented headers and coalesced frames."""
    def __init__(self, max_frame_bytes=MAX_FRAME_BYTES):
        self.max_frame_bytes = max_frame_bytes
        self.buffer = bytearray()

    def feed(self, data):
        # Callers read at most 64 KiB each time. Reject an unreasonable feed
        # before retaining it, even if its advertised header is incomplete.
        if len(data) > self.max_frame_bytes + 65540:
            raise ProtocolError('input chunk exceeds limit')
        self.buffer.extend(data)
        messages = []
        offset = 0
        while len(self.buffer) - offset >= 4:
            size = _HEADER.unpack_from(self.buffer, offset)[0]
            if size == 0 or size > self.max_frame_bytes:
                raise ProtocolError('invalid frame length')
            if len(self.buffer) - offset < size + 4:
                break
            messages.append(_decode(self.buffer[offset + 4:offset + 4 + size]))
            offset += size + 4
        if offset:
            del self.buffer[:offset]
        if len(self.buffer) > self.max_frame_bytes + 4:
            raise ProtocolError('receive buffer exceeds limit')
        return messages


class _Connection:
    def __init__(self, sock, max_frame_bytes):
        self.sock = sock
        self.decoder = FrameDecoder(max_frame_bytes)
        self.output = bytearray()
        self.created = self.last_received = self.last_ping = time.monotonic()
        self.ready = False
        self.close_reason = None
        self.peer_id = None
        self.session = None
        self.rate_start = self.created
        self.rate_count = 0


class _BaseTransport:
    def _init_base(self, identity, room_code, max_frame_bytes, heartbeat_interval,
                   idle_timeout, handshake_timeout, reconnect_timeout):
        self.identity = _identity(identity)
        if not isinstance(room_code, str) or len(room_code.encode('utf-8')) > 256:
            raise ValueError('room code must be text of at most 256 UTF-8 bytes')
        if not 1024 <= max_frame_bytes <= 16 * 1024 * 1024:
            raise ValueError('frame limit must be between 1 KiB and 16 MiB')
        for value in (heartbeat_interval, idle_timeout, handshake_timeout, reconnect_timeout):
            if not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
                raise ValueError('timeouts must be positive finite numbers')
        if idle_timeout <= heartbeat_interval:
            raise ValueError('idle timeout must exceed heartbeat interval')
        self.room_code = room_code
        self.max_frame_bytes = max_frame_bytes
        self.heartbeat_interval = heartbeat_interval
        self.idle_timeout = idle_timeout
        self.handshake_timeout = handshake_timeout
        self.reconnect_timeout = reconnect_timeout
        self.state = 'starting'
        self._events = queue.Queue(maxsize=4096)
        self._commands = queue.Queue(maxsize=256)
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._event_lock = threading.Lock()
        self._event_bytes = 0
        self._ready_peers = set()
        self._generations = {}
        self._thread = None
        self._queued_bytes = 0
        self._peer_queued_bytes = {}
        self._snapshot_commands = {}
        self._wake_lock = threading.Lock()
        self._wake_reader = self._wake_writer = None
        self._wake_pending = False
        self._metrics = dict(received_bytes=0,sent_bytes=0,receive_block_peak=0,
            decoder_retained_peak=0,socket_output_peak=0,command_bytes_peak=0,
            event_bytes_peak=0,command_items_peak=0,event_items_peak=0,
            control_items_peak=0,control_overflows=0,coalesced_snapshots=0,
            coalesced_outgoing_snapshots=0,deferred_output_commands=0)

    def statistics(self):
        with self._lock:
            value=dict(self._metrics,queued_command_bytes=self._queued_bytes,peer_command_bytes=dict(self._peer_queued_bytes),
                       command_items=self._commands.qsize())
        with self._event_lock:
            value.update(event_bytes=self._event_bytes,event_items=self._events.qsize())
        value.update(available=True,scope='This process application transport; excludes public relay process RSS/buffers',
            max_frame_bytes=self.max_frame_bytes,command_bytes_limit=self.max_frame_bytes*4,
            event_bytes_limit=self.max_frame_bytes*8,command_item_limit=256,event_item_limit=4096,
            socket_output_limit_per_connection=self.max_frame_bytes*4,
            control_item_limit_per_queue=256,receive_block_limit=65536)
        return value

    def _open_wakeup(self):
        # Windows select accepts sockets, not pipe/event descriptors. Create
        # this on the owner thread, keeping constructors free of socket I/O.
        reader, writer = socket.socketpair()
        reader.setblocking(False); writer.setblocking(False)
        with self._wake_lock:
            self._wake_reader, self._wake_writer = reader, writer

    def _notify(self):
        with self._wake_lock:
            if self._wake_writer is None or self._wake_pending:
                return
            try:
                self._wake_writer.send(b'\0')
                self._wake_pending = True
            except (BlockingIOError, OSError):
                pass

    def _drain_wakeup(self, readable):
        with self._wake_lock:
            if self._wake_reader not in readable:
                return
            readable.remove(self._wake_reader)
            try:
                while self._wake_reader.recv(1024):
                    pass
            except (BlockingIOError, OSError):
                pass
            self._wake_pending = False

    def _close_wakeup(self):
        with self._wake_lock:
            for sock in (self._wake_reader, self._wake_writer):
                if sock is not None:
                    sock.close()
            self._wake_reader = self._wake_writer = None
            self._wake_pending = False

    def _emit(self, kind, **fields):
        event = dict(fields, type=kind)
        size = len(json.dumps(event, ensure_ascii=True, separators=(',', ':')))
        with self._event_lock:
            # Sequence validation happens before _emit. Coalesce here, before
            # a stalled renderer retains dozens of compressed battle states.
            # All event queue access is serialized by _event_lock; Queue's
            # mutex also protects its tail while replacing an existing item.
            with self._events.mutex:
                if self._events.queue and supersedes_snapshot(event, self._events.queue[-1][0]):
                    old_size = self._events.queue[-1][1]
                    if self._event_bytes - old_size + size <= self.max_frame_bytes * 8:
                        self._events.queue[-1] = (event, size)
                        self._event_bytes += size - old_size
                        self._metrics['coalesced_snapshots']+=1
                        self._metrics['event_bytes_peak']=max(self._metrics['event_bytes_peak'],self._event_bytes)
                        # Queue.qsize() acquires the non-reentrant mutex we
                        # already hold here. Read its protected deque directly.
                        self._metrics['event_items_peak']=max(self._metrics['event_items_peak'],len(self._events.queue))
                        return
            if self._events.full() or self._event_bytes + size > self.max_frame_bytes * 8:
                # A stalled UI may not retain gigabytes of full snapshots.
                # Discard pending state and stop, rather than losing one input
                # silently while pretending the connection is still healthy.
                while not self._events.empty():
                    self._events.get_nowait()
                error = {'type': 'error', 'code': 'event_queue_full',
                         'detail': 'application did not consume network events'}
                self._events.put_nowait((error, 128))
                self._event_bytes = 128
                self._stop.set()
            else:
                self._events.put_nowait((event, size))
                self._event_bytes += size
            self._metrics['event_bytes_peak']=max(self._metrics['event_bytes_peak'],self._event_bytes)
            self._metrics['event_items_peak']=max(self._metrics['event_items_peak'],self._events.qsize())

    def poll(self, limit=100):
        if not isinstance(limit, int) or isinstance(limit, bool) or limit < 1:
            raise ValueError('poll limit must be a positive integer')
        events = []
        for _ in range(min(limit, 4096)):
            with self._event_lock:
                try:
                    event, size = self._events.get_nowait()
                except queue.Empty:
                    break
                self._event_bytes -= size
                events.append(event)
        return events

    def generation(self, peer_id):
        with self._lock:
            return self._generations.get(peer_id, 0)

    def send(self, peer_id, payload=None, *, generation=None):
        if payload is None and isinstance(peer_id, dict) and isinstance(self, ClientTransport):
            payload, peer_id = peer_id, 'server'
        if not isinstance(peer_id, str) or not isinstance(payload, dict):
            raise ValueError('send expects a peer ID and JSON object')
        # Freeze caller-owned data. Reserve space for the sequence envelope.
        frame = encode_frame(payload, self.max_frame_bytes - 128)
        raw = frame[4:]
        # Only unsent snapshots from the same stream can supersede each other.
        # Freeze stream identity too; caller mutation must not alter admission.
        stream = None
        if payload.get('type') == 'room_snapshot' and payload.get('snapshot_stream') is not None:
            stream = json.dumps(payload['snapshot_stream'], ensure_ascii=True, separators=(',', ':'))
        map_included = bool(payload.get('map_included'))
        with self._lock:
            if self._stop.is_set() or peer_id not in self._ready_peers:
                return False
            if generation is not None and generation != self._generations.get(peer_id, 0):
                return False
            previous = self._snapshot_commands.get(peer_id)
            replace = stream is not None and previous is not None and previous[1] == stream and not previous[2]
            delta = len(raw) - (len(previous[0]) if replace else 0)
            if self._queued_bytes + delta > self.max_frame_bytes * 4:
                return False
            if replace:
                previous[0], previous[2] = raw, map_included
                self._metrics['coalesced_outgoing_snapshots'] += 1
            else:
                entry = [raw, stream, map_included]
                try:
                    self._commands.put_nowait((peer_id, entry, self._generations.get(peer_id, 0)))
                except queue.Full:
                    return False
                if stream is None:
                    self._snapshot_commands.pop(peer_id, None)
                else:
                    self._snapshot_commands[peer_id] = entry
            self._queued_bytes += delta
            self._peer_queued_bytes[peer_id] = self._peer_queued_bytes.get(peer_id, 0) + delta
            self._metrics['command_bytes_peak']=max(self._metrics['command_bytes_peak'],self._queued_bytes)
            self._metrics['command_items_peak']=max(self._metrics['command_items_peak'],self._commands.qsize())
        self._notify()
        return True

    def close(self):
        """Cancel connection/listen/reconnect without blocking on network I/O."""
        self._stop.set()
        self._notify()
        with self._lock:
            self._ready_peers.clear()
            self._snapshot_commands.clear()
        if self._thread is not None and self._thread is not threading.current_thread():
            self._thread.join(0.2)

    def _ready(self, peer_id, value):
        with self._lock:
            if (peer_id in self._ready_peers) != bool(value):
                self._generations[peer_id] = self._generations.get(peer_id, 0) + 1
                self._snapshot_commands.pop(peer_id, None)
            if value:
                self._ready_peers.add(peer_id)
            else:
                self._ready_peers.discard(peer_id)

    def _queue(self, conn, value):
        frame = encode_frame(value, self.max_frame_bytes)
        if len(conn.output) + len(frame) > self.max_frame_bytes * 4:
            raise ProtocolError('send buffer full')
        conn.output.extend(frame)
        self._metrics['socket_output_peak']=max(self._metrics['socket_output_peak'],len(conn.output))

    def _read(self, conn):
        data = conn.sock.recv(65536)
        if not data:
            raise EOFError('peer closed connection')
        self._metrics['received_bytes']+=len(data)
        self._metrics['receive_block_peak']=max(self._metrics['receive_block_peak'],len(data))
        for message in conn.decoder.feed(data):
            if conn.close_reason:
                break
            now = time.monotonic()
            if now - conn.rate_start >= 1:
                conn.rate_start, conn.rate_count = now, 0
            conn.rate_count += 1
            if conn.rate_count > 1200:
                raise ProtocolError('message rate limit exceeded')
            conn.last_received = now
            self._handle_frame(conn, message)
        self._metrics['decoder_retained_peak']=max(self._metrics['decoder_retained_peak'],len(conn.decoder.buffer))

    def _write(self, conn):
        if conn.output:
            sent = conn.sock.send(conn.output)
            if sent == 0:
                raise EOFError('socket write returned zero')
            del conn.output[:sent]
            self._metrics['sent_bytes']+=sent

    def _heartbeat(self, conn, now):
        if now - conn.last_received > (self.idle_timeout if conn.ready else self.handshake_timeout):
            raise TimeoutError('idle_timeout' if conn.ready else 'handshake_timeout')
        if conn.ready and now - conn.last_ping >= self.heartbeat_interval:
            self._queue(conn, {'type': 'ping'})
            conn.last_ping = now

    def _control(self, conn, message):
        kind = message.get('type')
        if kind == 'ping':
            self._queue(conn, {'type': 'pong'})
            return True
        return kind == 'pong'

    def _pop_commands(self):
        # Leave a blocked peer's next frame replaceable until its current frame
        # has left the application socket buffer. Sequence numbers are assigned
        # only after this yield; no framed bytes or sequence gaps are discarded.
        # Each initially queued item is examined once, so a blocked peer cannot
        # spin or prevent unrelated peers from being serviced.
        selected_peers = set()
        for _ in range(min(64, self._commands.qsize())):
            with self._lock:
                try:
                    peer_id, entry, generation = self._commands.get_nowait()
                except queue.Empty:
                    break
                connections = getattr(self, '_connections', None)
                if (generation == self._generations.get(peer_id, 0) and connections is not None and
                        (peer_id in selected_peers or
                         any(getattr(conn, 'ready', False) and conn.peer_id == peer_id and conn.output for conn in connections.values()))):
                    self._commands.put_nowait((peer_id, entry, generation))
                    self._metrics['deferred_output_commands'] += 1
                    continue
                raw = entry[0]
                if self._snapshot_commands.get(peer_id) is entry:
                    self._snapshot_commands.pop(peer_id, None)
                self._queued_bytes -= len(raw)
                remaining = self._peer_queued_bytes.get(peer_id, 0) - len(raw)
                if remaining > 0:
                    self._peer_queued_bytes[peer_id] = remaining
                else:
                    self._peer_queued_bytes.pop(peer_id, None)
                valid = generation == self._generations.get(peer_id, 0)
                if valid and connections is not None:
                    # The native translator can materialize an iterator before
                    # its consumer runs. Reserve one frame per peer in this
                    # batch instead of depending on the consumer updating output.
                    selected_peers.add(peer_id)
            if not valid:
                continue
            yield peer_id, _decode(raw)

    def _discard_commands(self):
        while True:
            try:
                peer_id, entry, _ = self._commands.get_nowait()
            except queue.Empty:
                break
            with self._lock:
                raw = entry[0]
                if self._snapshot_commands.get(peer_id) is entry:
                    self._snapshot_commands.pop(peer_id, None)
                self._queued_bytes -= len(raw)
                remaining = self._peer_queued_bytes.get(peer_id, 0) - len(raw)
                if remaining > 0:
                    self._peer_queued_bytes[peer_id] = remaining
                else:
                    self._peer_queued_bytes.pop(peer_id, None)

    def _data(self, conn, message, peer_id, last_sequence, emit=True):
        if message.get('type') != 'data' or not isinstance(message.get('payload'), dict):
            raise ProtocolError('expected data frame')
        sequence = message.get('seq')
        if isinstance(sequence, bool) or not isinstance(sequence, int) or not 1 <= sequence < 2 ** 53:
            raise ProtocolError('invalid sequence')
        if sequence <= last_sequence:
            return last_sequence  # duplicates cannot become repeated game inputs
        if sequence != last_sequence + 1:
            raise ProtocolError('sequence gap; authoritative resync required')
        payload = message['payload']
        if payload.get('type') in LATENCY_KINDS:
            emit = emit and allow_latency_payload(conn, payload, time.monotonic())
        if emit:self._emit('message', peer_id=peer_id, payload=payload, sequence=sequence)
        return sequence

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


class ServerTransport(_BaseTransport):
    def __init__(self, host='::', port=DEFAULT_PORT, *, identity=None, room_code='',
                 max_peers=1, max_frame_bytes=MAX_FRAME_BYTES, heartbeat_interval=2.0,
                 idle_timeout=8.0, handshake_timeout=5.0, reconnect_timeout=20.0,
                 allow_spectators=True, max_spectators=4):
        self._init_base(identity, room_code, max_frame_bytes, heartbeat_interval,
                        idle_timeout, handshake_timeout, reconnect_timeout)
        if not isinstance(host, str) or not host:
            raise ValueError('listen host must be text')
        if isinstance(port, bool) or not isinstance(port, int) or not 0 <= port <= 65535:
            raise ValueError('listen port must be between 0 and 65535')
        if isinstance(max_peers, bool) or not isinstance(max_peers, int) or not 1 <= max_peers <= 8:
            raise ValueError('max_peers must be between 1 and 8')
        if type(allow_spectators) is not bool or type(max_spectators) is not int or not 1<=max_spectators<=4:
            raise ValueError('invalid spectator policy')
        self.allow_spectators, self.max_spectators = allow_spectators, max_spectators
        self._spectator_pending = {}
        self._spectator_full_pending = set()
        self._peer_roles = {}
        self._peer_channels = {}
        self._spectator_policy = threading.Event()
        self.host, self.port, self.max_peers = host, port, max_peers
        self.address = None
        self._listener = None
        self._connections = {}
        self._sessions = {}
        self._releases = queue.Queue(maxsize=256)
        self._role_changes = queue.Queue(maxsize=256)
        self._rejections = queue.Queue(maxsize=256)
        self._thread = threading.Thread(target=self._run, name='PvP-server', daemon=True)
        self._thread.start()

    def pending_bytes(self, peer_id):
        """Bytes already queued toward one peer and not yet taken by its socket.

        Read from the game thread: copying the dict values is atomic under the
        GIL, and a stale length only delays one snapshot by a frame.
        """
        with self._lock:
            total = self._peer_queued_bytes.get(peer_id, 0)
            total += len(self._spectator_pending.get(peer_id, b''))
        for conn in list(self._connections.values()):
            if getattr(conn, 'peer_id', None) == peer_id:
                total += len(conn.output)
        return total

    def set_max_peers(self, count):
        """PvP66: a 2v2 room admits three remote players."""
        if isinstance(count, bool) or not isinstance(count, int) or not 1 <= count <= 8:
            raise ValueError('max_peers must be between 1 and 8')
        self.max_peers = count

    def set_allow_spectators(self, enabled):
        if type(enabled) is not bool:raise ValueError('spectator policy must be boolean')
        self.allow_spectators=enabled
        self._spectator_policy.set()
        self._notify()

    def send_spectator(self, peer_id, payload, full_snapshot=False):
        """Replace a spectator's pending snapshot without using the player queue."""
        raw=encode_frame(payload,self.max_frame_bytes-128)[4:]
        with self._lock:
            if self._stop.is_set() or peer_id not in self._ready_peers:return False
            if not self._peer_roles.get(peer_id):return False
            # A full terrain snapshot is a prerequisite for later deltas. Do
            # not let a slow writer replace that prerequisite with a delta.
            if peer_id in self._spectator_full_pending and not full_snapshot:return False
            self._spectator_pending[peer_id]=raw
            if full_snapshot:self._spectator_full_pending.add(peer_id)
        self._notify()
        return True

    def set_peer_role(self,peer_id,spectator):
        """Apply an already-authorized room seat change on the socket thread."""
        if type(spectator) is not bool:return 'invalid_role'
        done=threading.Event();result=[]
        if not self._queue_control(self._role_changes,(peer_id,spectator,done,result)):return 'control_queue_full'
        return result[0] if done.wait(1.) and result else 'not_connected'

    def reject_peer(self,peer_id,message):
        """Flush a terminal application error before releasing an admitted peer."""
        return self._queue_control(self._rejections,(peer_id,str(message)[:512]))

    def _queue_control(self,target,value):
        try:target.put_nowait(value)
        except queue.Full:
            self._metrics['control_overflows']+=1
            self._emit('error',code='control_queue_full',detail='Connection control queue exceeded its bounded capacity')
            self._stop.set();self._notify()
            return False  # explicit terminal failure, never a silently lost transaction
        self._metrics['control_items_peak']=max(self._metrics['control_items_peak'],target.qsize())
        self._notify()
        return True

    def _pop_commands(self):
        yield from super()._pop_commands()
        pending = {}
        with self._lock:
            for peer_id, raw in list(self._spectator_pending.items()):
                if any(getattr(conn, 'ready', False) and conn.peer_id == peer_id and conn.output for conn in self._connections.values()):
                    continue
                pending[peer_id] = raw
                self._spectator_pending.pop(peer_id, None)
                self._spectator_full_pending.discard(peer_id)
        for peer_id,raw in pending.items():yield peer_id,_decode(raw)

    def release_peer(self, peer_id):
        """Revoke a departed player's reservation on the network owner thread."""
        done = threading.Event()
        result = []
        if not self._queue_control(self._releases,(peer_id,done,result)):return False
        # Audience departure must not wait on the transport thread during a
        # battle render/update. Its independent reservation can clear later.
        if self._peer_roles.get(peer_id,False):return True
        return done.wait(1.) and bool(result and result[0])

    def _release_pending(self):
        while True:
            try:peer_id,message=self._rejections.get_nowait()
            except queue.Empty:break
            for sid,session in list(self._sessions.items()):
                if session['peer_id']!=peer_id:continue
                self._sessions.pop(sid,None);self._peer_roles.pop(peer_id,None)
                conn=session['connection']
                if conn is not None:
                    seq=session['out_seq']+1;session['out_seq']=seq
                    self._queue(conn,dict(type='data',seq=seq,payload=dict(type='error',message=message,terminal=True)))
                    conn.close_reason='peer_left'
        while True:
            try:peer_id,spectator,done,result=self._role_changes.get_nowait()
            except queue.Empty:break
            session=next((s for s in self._sessions.values() if s['peer_id']==peer_id),None)
            error=''
            if session is None or session['connection'] is None:error='not_connected'
            elif spectator and not self.allow_spectators:error='spectators_disabled'
            elif sum(s['peer_id']!=peer_id and s.get('spectator',False)==spectator for s in self._sessions.values()) >= (self.max_spectators if spectator else self.max_peers):error='room_full'
            else:
                session['spectator']=spectator;session['role_changed']=True
                self._peer_roles[peer_id]=spectator
                with self._lock:
                    self._spectator_pending.pop(peer_id,None)
                    self._spectator_full_pending.discard(peer_id)
                self._queue(session['connection'],dict(type='role_changed',spectator=spectator))
            result.append(error);done.set()
        if self._spectator_policy.is_set():
            self._spectator_policy.clear()
            if not self.allow_spectators:
                for sid,session in list(self._sessions.items()):
                    if session.get('spectator'):
                        self._sessions.pop(sid,None)
                        self._peer_roles.pop(session['peer_id'],None)
                        if session['connection'] is not None:
                            self._disconnect(session['connection'],'spectators_disabled')
        while True:
            try:
                peer_id, done, result = self._releases.get_nowait()
            except queue.Empty:
                return
            removed = False
            for session_id, session in list(self._sessions.items()):
                if session['peer_id'] != peer_id:
                    continue
                del self._sessions[session_id]
                self._peer_roles.pop(peer_id,None)
                removed = True
                if session['connection'] is not None:
                    self._disconnect(session['connection'], 'peer_left')
            result.append(removed)
            self._peer_channels.pop(peer_id,None)
            done.set()

    def _reject(self, conn, code, detail):
        self._queue(conn, {'type': 'reject', 'code': code, 'detail': detail})
        conn.close_reason = code

    def _handle_frame(self, conn, message):
        if not conn.ready:
            if message.get('type') != 'hello':
                raise ProtocolError('first frame must be hello')
            remote_identity = message.get('identity')
            if message.get('protocol') != PROTOCOL_VERSION:
                return self._reject(conn, 'protocol_mismatch', 'transport protocol differs')
            if remote_identity != self.identity:
                keys = sorted(set(self.identity) | set(remote_identity if isinstance(remote_identity, dict) else {}))
                mismatch = [key for key in keys if not isinstance(remote_identity, dict) or remote_identity.get(key) != self.identity.get(key)]
                return self._reject(conn, 'identity_mismatch', 'incompatible fields: ' + ', '.join(mismatch))
            code = message.get('room_code', '')
            if not isinstance(code, str) or not hmac.compare_digest(code.encode('utf-8'), self.room_code.encode('utf-8')):
                return self._reject(conn, 'room_code_invalid', 'room code differs')
            session_id, token = message.get('session_id'), message.get('token')
            spectator = message.get('spectator',False)
            request_player=message.get('request_player',False)
            if type(spectator) is not bool:return self._reject(conn,'invalid_role','invalid spectator role')
            if type(request_player) is not bool:return self._reject(conn,'invalid_role','invalid seat request')
            if spectator and not self.allow_spectators and not session_id and not request_player:
                return self._reject(conn,'spectators_disabled','host disabled spectators')
            resumed = bool(session_id)
            if resumed:
                session = self._sessions.get(session_id) if isinstance(session_id, str) else None
                if (session is None or not isinstance(token, str)
                        or not hmac.compare_digest(token.encode('utf-8'), session['token'].encode('utf-8'))
                        or (session['expires'] is not None and time.monotonic() > session['expires'])):
                    return self._reject(conn, 'session_invalid', 'session expired or token differs')
                if session['connection'] is not None:
                    return self._reject(conn, 'session_in_use', 'session is already connected')
                if session.get('spectator',False)!=spectator and not (session.get('role_changed') and session.get('initial_spectator')==spectator):
                    return self._reject(conn,'session_invalid','session role differs')
                spectator=session.get('spectator',False)
                if spectator and not self.allow_spectators:return self._reject(conn,'spectators_disabled','host disabled spectators')
            else:
                if request_player and sum(not s.get('spectator',False) for s in self._sessions.values())>=self.max_peers:
                    return self._reject(conn,'room_full','player seats are full or reserved for reconnect')
                count=sum(s.get('spectator',False)==spectator for s in self._sessions.values())
                if count >= (self.max_spectators if spectator else self.max_peers):
                    return self._reject(conn, 'room_full', 'room is full or reserved for reconnect')
                session_id = secrets.token_urlsafe(18)
                session = {'peer_id': ('spectator-' if spectator else 'peer-') + secrets.token_hex(6), 'session_id': session_id,
                           'token': secrets.token_urlsafe(32), 'in_seq': 0, 'out_seq': 0,
                           'connection': None, 'expires': None, 'spectator':spectator,
                           'initial_spectator':spectator,
                           'relay_spectator':message.get('relay_spectator') is True}
                self._sessions[session_id] = session
            conn.session = session
            conn.peer_id, conn.ready = session['peer_id'], True
            self._peer_roles[conn.peer_id]=spectator
            self._peer_channels[conn.peer_id]=session.get('relay_spectator',False)
            session['connection'], session['expires'] = conn, None
            self._queue(conn, {'type': 'welcome', 'protocol': PROTOCOL_VERSION,
                              'identity': self.identity, 'peer_id': conn.peer_id,
                              'session_id': session_id, 'token': session['token'],
                              'receive_sequence': session['in_seq'], 'server_sequence': session['out_seq'],
                              'resumed': resumed,'spectator':spectator})
            self._ready(conn.peer_id, True)
            self._emit('reconnected' if resumed else 'connected', peer_id=conn.peer_id,
                       session_id=session_id, resumed=resumed, require_full_snapshot=True,spectator=spectator,request_player=request_player)
            return
        if not self._control(conn, message):
            spectator=conn.session.get('spectator',False)
            payload=message.get('payload')
            allowed=(not spectator or (isinstance(payload,dict) and payload.get('type') in
                     ('request_full_snapshot','leave','result_received','role_change') + LATENCY_KINDS and conn.rate_count<=8))
            if spectator and allowed and payload.get('type')=='request_full_snapshot':
                now=time.monotonic()
                allowed=now-getattr(conn,'last_snapshot_request',0.)>=1.
                if allowed:conn.last_snapshot_request=now
            # Even a modified spectator client cannot forward game commands,
            # replay requests or a flood into the authoritative application.
            conn.session['in_seq'] = self._data(conn, message, conn.peer_id, conn.session['in_seq'],emit=allowed)

    def _disconnect(self, conn, reason, detail=''):
        if conn.sock not in self._connections:
            return
        self._connections.pop(conn.sock, None)
        try:
            conn.sock.close()
        except OSError:
            pass
        if conn.ready:
            self._ready(conn.peer_id, False)
            conn.session['connection'] = None
            conn.session['expires'] = time.monotonic() + self.reconnect_timeout
            self._emit('disconnected', peer_id=conn.peer_id, reason=reason,
                       detail=detail, reconnect_seconds=self.reconnect_timeout,
                       clear_continuous_input=not conn.session.get('spectator',False),
                       spectator=conn.session.get('spectator',False))
            with self._lock:
                self._spectator_pending.pop(conn.peer_id,None)
                self._spectator_full_pending.discard(conn.peer_id)
        elif reason not in ('room_full', 'room_code_invalid', 'identity_mismatch', 'protocol_mismatch',
                            'session_invalid', 'session_in_use', 'local_close','spectators_disabled','invalid_role'):
            self._emit('error', code=reason, detail=detail, peer_id=None)

    def _run(self):
        try:
            self._open_wakeup()
            candidates = socket.getaddrinfo(self.host, self.port, socket.AF_UNSPEC,
                                            socket.SOCK_STREAM, 0, socket.AI_PASSIVE)
            last_error = None
            for family, socktype, proto, _, address in candidates:
                listener = socket.socket(family, socktype, proto)
                try:
                    if hasattr(socket, 'SO_EXCLUSIVEADDRUSE'):
                        listener.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
                    else:
                        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                    if family == socket.AF_INET6:
                        try:
                            listener.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 0)
                        except OSError:
                            pass
                    listener.bind(address)
                    listener.listen(8)
                    listener.setblocking(False)
                    self._listener = listener
                    break
                except OSError as exc:
                    last_error = exc
                    listener.close()
            if self._listener is None:
                raise last_error or OSError('no listen address')
            self.address = self._listener.getsockname()
            self.port = self.address[1]
            self.state = 'listening'
            self._emit('listening', address=self.address, port=self.port,
                       wildcard=self.address[0] in ('::', '0.0.0.0'))
            while not self._stop.is_set():
                now = time.monotonic()
                self._release_pending()
                for session_id, session in list(self._sessions.items()):
                    if session['expires'] is not None and now > session['expires']:
                        del self._sessions[session_id]
                        self._peer_roles.pop(session['peer_id'],None)
                        self._emit('session_expired', peer_id=session['peer_id'])
                for peer_id, payload in self._pop_commands():
                    conn = next((item for item in self._connections.values()
                                 if item.ready and item.peer_id == peer_id), None)
                    if conn is None:
                        self._emit('send_dropped', peer_id=peer_id, reason='disconnected')
                        continue
                    try:
                        sequence = conn.session['out_seq'] + 1
                        self._queue(conn, {'type': 'data', 'seq': sequence, 'payload': payload})
                        conn.session['out_seq'] = sequence
                    except (ValueError, OSError) as exc:
                        self._disconnect(conn, 'backpressure', str(exc))
                readers = [self._listener, self._wake_reader] + list(self._connections)
                writers = [conn.sock for conn in self._connections.values() if conn.output]
                readable, writable, exceptional = select.select(readers, writers, list(self._connections), 0.02)
                self._drain_wakeup(readable)
                if self._listener in readable:
                    sock, _ = self._listener.accept()
                    sock.setblocking(False)
                    sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                    # Bound kernel queues too, so application backpressure is
                    # not hidden behind multi-megabyte TCP autotuning buffers.
                    sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 65536)
                    sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 65536)
                    if len(self._connections) >= self.max_peers + self.max_spectators + 4:
                        sock.close()
                    else:
                        self._connections[sock] = _Connection(sock, self.max_frame_bytes)
                    readable.remove(self._listener)
                for sock in set(readable + writable + exceptional):
                    conn = self._connections.get(sock)
                    if conn is None:
                        continue
                    try:
                        if sock in exceptional:
                            raise OSError('socket exception')
                        if sock in readable:
                            self._read(conn)
                        if sock in writable:
                            self._write(conn)
                        if conn.close_reason and not conn.output:
                            self._disconnect(conn, conn.close_reason)
                    except BlockingIOError:
                        pass
                    except (OSError, EOFError, ValueError) as exc:
                        self._disconnect(conn, 'protocol_error' if isinstance(exc, ValueError) else 'connection_lost', str(exc))
                for conn in list(self._connections.values()):
                    try:
                        self._heartbeat(conn, time.monotonic())
                    except (TimeoutError, ValueError) as exc:
                        self._disconnect(conn, str(exc))
        except Exception as exc:
            self._emit('error', code='listen_failed' if self._listener is None else 'transport_error',
                       detail=type(exc).__name__ + ': ' + str(exc))
        finally:
            for conn in list(self._connections.values()):
                self._disconnect(conn, 'local_close')
            if self._listener is not None:
                self._listener.close()
            self._stop.set()
            self._close_wakeup()
            self.state = 'closed'
            self._emit('closed', reason='local_close')


class ClientTransport(_BaseTransport):
    def __init__(self, endpoint, port=DEFAULT_PORT, *, identity=None, room_code='',
                 session_id=None, token=None, max_frame_bytes=MAX_FRAME_BYTES,
                 heartbeat_interval=2.0, idle_timeout=8.0, handshake_timeout=5.0,
                 reconnect_timeout=20.0, connect_timeout=5.0, reconnect_delay=0.5,
                 spectator=False):
        self._init_base(identity, room_code, max_frame_bytes, heartbeat_interval,
                        idle_timeout, handshake_timeout, reconnect_timeout)
        self.host, self.port = parse_endpoint(endpoint, port)
        if type(spectator) is not bool:raise ValueError('spectator must be boolean')
        self.spectator=spectator
        for value in (connect_timeout, reconnect_delay):
            if not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
                raise ValueError('connect/retry timeouts must be positive finite numbers')
        if bool(session_id) != bool(token) or (session_id is not None and not isinstance(session_id, str)) or (token is not None and not isinstance(token, str)):
            raise ValueError('session ID and token must both be supplied as text')
        self.session_id, self.token = session_id, token
        self.peer_id = None
        self.connect_timeout, self.reconnect_delay = connect_timeout, reconnect_delay
        self._conn = None
        self._in_seq = self._out_seq = 0
        self._ever_connected = False
        self._terminal_rejection = False
        self._thread = threading.Thread(target=self._run, name='PvP-client', daemon=True)
        self._thread.start()

    def _connect(self, remaining=None):
        self.state = 'reconnecting' if self._ever_connected else 'connecting'
        self._emit(self.state)
        deadline = time.monotonic() + min(self.connect_timeout, remaining if remaining is not None else self.connect_timeout)
        addresses = socket.getaddrinfo(self.host, self.port, socket.AF_UNSPEC, socket.SOCK_STREAM)
        last_error = None
        pending_codes = {0, errno.EINPROGRESS, errno.EWOULDBLOCK, errno.EALREADY,
                         10035, 10036, 10037}
        for family, kind, proto, _, address in addresses:
            sock = socket.socket(family, kind, proto)
            sock.setblocking(False)
            try:
                result = sock.connect_ex(address)
                if result not in pending_codes:
                    raise OSError(result, 'connection refused or address unreachable')
                while not self._stop.is_set() and time.monotonic() < deadline:
                    readable, writable, exceptional = select.select([self._wake_reader], [sock], [sock], 0.02)
                    self._drain_wakeup(readable)
                    if writable or exceptional:
                        error = sock.getsockopt(socket.SOL_SOCKET, socket.SO_ERROR)
                        if error:
                            raise OSError(error, 'connection refused or address unreachable')
                        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                        sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 65536)
                        sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 65536)
                        return _Connection(sock, self.max_frame_bytes)
                raise TimeoutError('connect_timeout')
            except (OSError, TimeoutError) as exc:
                sock.close()
                last_error = exc
                if self._stop.is_set() or time.monotonic() >= deadline:
                    break
        raise last_error or OSError('no connection address')

    def _handle_frame(self, conn, message):
        if not conn.ready:
            if message.get('type') == 'reject':
                self._terminal_rejection = True
                code = message.get('code')
                allowed = {'protocol_mismatch', 'identity_mismatch', 'room_code_invalid',
                           'session_invalid', 'session_in_use', 'room_full','spectators_disabled','invalid_role'}
                if code not in allowed:
                    code = 'handshake_rejected'
                self._emit('error', code=code, detail=str(message.get('detail', ''))[:512])
                raise ProtocolError('handshake_rejected')
            if message.get('type') != 'welcome' or message.get('protocol') != PROTOCOL_VERSION or message.get('identity') != self.identity:
                raise ProtocolError('invalid welcome or incompatible identity')
            for key in ('peer_id', 'session_id', 'token'):
                if not isinstance(message.get(key), str) or not 1 <= len(message[key]) <= 256:
                    raise ProtocolError('invalid welcome credentials')
            for key in ('receive_sequence', 'server_sequence'):
                value = message.get(key)
                if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value < 2 ** 53:
                    raise ProtocolError('invalid welcome sequence')
            if not isinstance(message.get('resumed'), bool):
                raise ProtocolError('invalid reconnect state')
            if message.get('spectator',False)!=self.spectator and not message['resumed']:
                raise ProtocolError('server assigned an unexpected role')
            self.spectator=message.get('spectator',False)
            self.session_id, self.token, self.peer_id = message['session_id'], message['token'], message['peer_id']
            self._out_seq, self._in_seq = message['receive_sequence'], message['server_sequence']
            conn.ready = True
            self._ever_connected = True
            self.state = 'connected'
            self._ready('server', True)
            self._emit('reconnected' if message['resumed'] else 'connected', peer_id='server',
                       assigned_peer_id=self.peer_id, session_id=self.session_id, token=self.token,
                       resumed=message['resumed'], require_full_snapshot=True,spectator=self.spectator)
            return
        if message.get('type')=='role_changed':
            if type(message.get('spectator')) is not bool:raise ProtocolError('invalid role change')
            self.spectator=message['spectator']
            self._emit('role_changed',peer_id='server',spectator=self.spectator)
            return
        if not self._control(conn, message):
            self._in_seq = self._data(conn, message, 'server', self._in_seq)

    def _run_connection(self, conn):
        self.state = 'handshaking'
        self._emit('handshaking')
        self._queue(conn, {'type': 'hello', 'protocol': PROTOCOL_VERSION,
                          'identity': self.identity, 'room_code': self.room_code,
                          'session_id': self.session_id, 'token': self.token,
                          'spectator':True if getattr(self,'_relay_spectator',False) else self.spectator,
                          'relay_spectator':getattr(self,'_relay_spectator',False),
                          'request_player':getattr(self,'_take_seat_on_connect',False)})
        while not self._stop.is_set():
            for _, payload in self._pop_commands():
                if not conn.ready:
                    self._emit('send_dropped', peer_id='server', reason='resync_required')
                    continue
                sequence = self._out_seq + 1
                self._queue(conn, {'type': 'data', 'seq': sequence, 'payload': payload})
                self._out_seq = sequence
            readable, writable, exceptional = select.select([conn.sock, self._wake_reader], [conn.sock] if conn.output else [], [conn.sock], 0.02)
            self._drain_wakeup(readable)
            try:
                if exceptional:
                    raise OSError('socket exception')
                if readable:
                    self._read(conn)
                if writable:
                    self._write(conn)
            except BlockingIOError:
                pass
            self._heartbeat(conn, time.monotonic())

    def _run(self):
        reconnect_deadline = None
        try:
            self._open_wakeup()
            while not self._stop.is_set():
                was_connected = False
                try:
                    remaining = None if reconnect_deadline is None else reconnect_deadline - time.monotonic()
                    if remaining is not None and remaining <= 0:
                        break
                    self._conn = self._connect(remaining)
                    self._run_connection(self._conn)
                except (OSError, EOFError, ValueError) as exc:
                    was_connected = self._conn is not None and self._conn.ready
                    if not self._stop.is_set() and not self._terminal_rejection:
                        if was_connected:
                            reason = 'protocol_error' if isinstance(exc, ValueError) else ('idle_timeout' if isinstance(exc, TimeoutError) else 'connection_lost')
                            self._emit('disconnected', peer_id='server', reason=reason,
                                       detail=str(exc), clear_continuous_input=True,
                                       reconnect_seconds=self.reconnect_timeout)
                        elif not self._ever_connected:
                            code = ('address_resolution_failed' if isinstance(exc, socket.gaierror)
                                    else 'connect_timeout' if isinstance(exc, TimeoutError)
                                    else 'protocol_error' if isinstance(exc, ValueError)
                                    else 'connection_failed')
                            self._emit('error', code=code, detail=str(exc))
                finally:
                    self._ready('server', False)
                    if self._conn is not None:
                        self._conn.sock.close()
                        self._conn = None
                    # Input intentions made before a disconnect are stale. A
                    # reconnect emits require_full_snapshot and never replays.
                    self._discard_commands()
                if self._stop.is_set() or self._terminal_rejection or not self._ever_connected:
                    break
                if was_connected or reconnect_deadline is None:
                    reconnect_deadline = time.monotonic() + self.reconnect_timeout
                if time.monotonic() >= reconnect_deadline:
                    break
                self._stop.wait(min(self.reconnect_delay, max(0, reconnect_deadline - time.monotonic())))
            if reconnect_deadline is not None and not self._stop.is_set() and not self._terminal_rejection:
                self._emit('error', code='reconnect_expired', detail='reconnect window elapsed')
        except Exception as exc:
            self._emit('error', code='transport_error', detail=type(exc).__name__ + ': ' + str(exc))
        finally:
            self._ready('server', False)
            self._stop.set()
            self._close_wakeup()
            self.state = 'closed'
            self._emit('closed', reason='cancelled' if not self._terminal_rejection else 'rejected')
