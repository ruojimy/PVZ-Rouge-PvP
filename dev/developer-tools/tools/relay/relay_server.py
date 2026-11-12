"""PvP byte relay. Python 3.8+, standard library; never imports game code.

Control frames are length-prefixed JSON (maximum 2048 bytes). After paired,
only bounded game frames are forwarded, unchanged. No payload/token logging.
"""
import argparse
import asyncio
import collections
import contextlib
import hmac
import json
import logging
import os
import secrets
import signal
import struct
import time

VERSION = 1
MAX_CONTROL = 2048
MAX_FRAME = 1024 * 1024
STREAM_CHUNK = 16384
WRITE_HIGH = 32768
WRITE_LOW = 8192
ALPHABET = '0123456789ABCDEFGHJKMNPQRSTVWXYZ'


class RelayError(Exception):
    pass


def frame(value):
    data = json.dumps(value, separators=(',', ':'), allow_nan=False).encode('utf8')
    return struct.pack('!I', len(data)) + data


class Room:
    def __init__(self, code):
        self.code = code
        self.secret = secrets.token_urlsafe(32)
        self.guest_secret = None
        self.host = self.guest = None
        self.pair = asyncio.Event()
        self.done = asyncio.Event()
        self.expires = time.monotonic() + 20
        self.active = False
        self.bytes = 0
        self.public = False
        self.name = ''
        self.build = ''
        self.allow_spectators = False
        self.spectator_lanes = {}
        self.room_policy = None


class RelayServer:
    def __init__(self, **options):
        defaults = dict(host='127.0.0.1', port=24562, max_rooms=200,
                        max_connections=512, max_per_ip=24, creates_per_minute=12,
                        attempts_per_minute=120, handshake_timeout=5.,
                        idle_timeout=15., waiting_timeout=600., resume_timeout=20.,
                        drain_timeout=5., stats_interval=30.)
        unknown = set(options) - set(defaults)
        if unknown:
            raise ValueError('unknown options: ' + ', '.join(sorted(unknown)))
        defaults.update(options)
        for key, value in defaults.items():
            if key not in ('host', 'port') and (isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 < value < 1e9):
                raise ValueError('invalid option: ' + key)
        self.config = defaults
        self.rooms = {}
        self.connections = set()
        self.readers = {}
        self.tasks = set()
        self.per_ip = collections.Counter()
        self.rates = collections.OrderedDict()
        self.stats = collections.Counter()
        self.listener = None
        self.sweeper = None
        self.started = time.monotonic()

    async def start(self):
        self.listener = await asyncio.start_server(self.handle, self.config['host'], self.config['port'], limit=STREAM_CHUNK)
        self.port = self.listener.sockets[0].getsockname()[1]
        self.sweeper = asyncio.create_task(self.sweep())
        return self

    def snapshot(self):
        # Linux RSS includes all Python buffers, not just the relay's counters.
        # Other platforms report unavailable rather than a misleading zero.
        rss = None
        try:
            with open('/proc/self/statm', encoding='ascii') as source:
                rss = int(source.read().split()[1]) * os.sysconf('SC_PAGE_SIZE')
        except (OSError, ValueError, IndexError, AttributeError):
            pass
        return dict(self.stats, rooms=len(self.rooms), active_rooms=sum(r.active for r in self.rooms.values()),
                    connections=len(self.connections), rss_bytes=rss,
                    relay_revision='pvp67-network1',
                    read_buffer_bytes=sum(len(reader._buffer) for reader in self.readers.values()),
                    write_buffer_bytes=sum(w.transport.get_write_buffer_size() for w in self.connections),
                    stream_chunk_bytes=STREAM_CHUNK, write_high_bytes=WRITE_HIGH,
                    uptime_seconds=round(time.monotonic() - self.started, 2))

    async def sweep(self):
        next_log = time.monotonic() + self.config['stats_interval']
        while True:
            await asyncio.sleep(.25)
            now = time.monotonic()
            for code, room in list(self.rooms.items()):
                if room.host is None and now >= room.expires:
                    self.close_spectators(room)
                    del self.rooms[code]
                    self.stats['expired'] += 1
            # Rate-limit state is bounded both by time and count.
            for key, entry in list(self.rates.items()):
                if now - entry[0] > 60:
                    self.rates.pop(key, None)
            if now >= next_log:
                logging.info('stats %s', json.dumps(self.snapshot(), sort_keys=True))
                next_log = now + self.config['stats_interval']

    def rate(self, ip, action, limit):
        key = (ip, action)
        now = time.monotonic()
        start, count = self.rates.get(key, (now, 0))
        if now - start >= 60:
            start, count = now, 0
        if key not in self.rates and len(self.rates) >= 8192:
            raise RelayError('rate_limited')
        self.rates[key] = (start, count + 1)
        if count >= limit:
            raise RelayError('rate_limited')

    async def send(self, writer, value):
        writer.write(frame(dict(value, relay_protocol=VERSION)))
        await asyncio.wait_for(writer.drain(), self.config['drain_timeout'])

    async def control(self, reader):
        async def read():
            size = struct.unpack('!I', await reader.readexactly(4))[0]
            if not 0 < size <= MAX_CONTROL:
                raise RelayError('invalid_preamble')
            try:
                data = json.loads((await reader.readexactly(size)).decode('utf8'))
            except (ValueError, UnicodeError, RecursionError):
                raise RelayError('invalid_preamble')
            if not isinstance(data, dict):
                raise RelayError('invalid_preamble')
            if type(data.get('relay_protocol')) is not int or data['relay_protocol'] != VERSION:
                raise RelayError('relay_protocol_mismatch')
            return data
        return await asyncio.wait_for(read(), self.config['handshake_timeout'])

    @staticmethod
    def authenticated(value, expected):
        return (isinstance(value, str) and isinstance(expected, str) and value.isascii()
                and hmac.compare_digest(value.encode('ascii'), expected.encode('ascii')))

    def lookup(self, data):
        code = data.get('code')
        if not isinstance(code, str) or len(code) != 10 or any(c not in ALPHABET for c in code):
            raise RelayError('room_code_invalid')
        room = self.rooms.get(code)
        if room is None:
            raise RelayError('room_not_found')
        if room.host is None and time.monotonic() >= room.expires:
            raise RelayError('room_expired')
        return room

    async def handle(self, reader, writer):
        task = asyncio.current_task()
        self.tasks.add(task)
        ip = writer.get_extra_info('peername')[0]
        admitted = False
        raw = False
        preamble_read = False
        try:
            if len(self.connections) >= self.config['max_connections'] or self.per_ip[ip] >= self.config['max_per_ip']:
                raise RelayError('connection_limit')
            admitted = True
            self.connections.add(writer)
            self.readers[writer] = reader
            self.per_ip[ip] += 1
            # CPython's Linux selector transport otherwise recv()s up to
            # 256 KiB even with a 16 KiB StreamReader limit. Set its supported
            # chunk attribute before pairing, so pause_reading can bound the
            # next game read. This attribute is selector-specific; other
            # event loops retain their own read policy and Reader limits.
            if hasattr(writer.transport, 'max_size'):
                writer.transport.max_size = STREAM_CHUNK
            writer.transport.set_write_buffer_limits(high=WRITE_HIGH, low=WRITE_LOW)
            sock = writer.get_extra_info('socket')
            import socket
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            self.rate(ip, 'attempt', self.config['attempts_per_minute'])
            data = await self.control(reader)
            preamble_read = True
            action = data.get('action')
            player_lane = False
            if action == 'join':
                room = self.lookup(data)
                occupied = room.guest is not None or (room.guest_secret is not None and
                    not self.authenticated(data.get('secret'), room.guest_secret))
                if data.get('player_lanes') is True and occupied and room.room_policy is not None and room.room_policy['available_seats'] > 0:
                    # Extra 2v2 players use independent byte pipes. Their
                    # hello requests a player seat from the authoritative host.
                    action = 'spectate'
                    player_lane = True
            if action == 'health':
                # Public health does not expose room codes, IPs or credentials.
                await self.send(writer, dict(status='ok', **self.snapshot()))
            elif action == 'list':
                rooms = [dict(code=r.code, name=r.name, build=r.build,
                              joinable=(r.room_policy['available_seats']>0 if r.room_policy is not None else r.guest is None and r.guest_secret is None),
                              allow_spectators=(r.room_policy['allow_spectators'] if r.room_policy is not None else r.allow_spectators),
                              spectator_count=(r.room_policy['spectator_count'] if r.room_policy is not None else sum(lane.guest is not None for lane in r.spectator_lanes.values())))
                         for r in self.rooms.values() if r.public and r.host is not None]
                await self.send(writer, dict(status='rooms', rooms=rooms[:200], truncated=len(rooms)>200))
            elif action in ('create', 'resume_host'):
                if action == 'create':
                    if type(data.get('public', False)) is not bool or type(data.get('allow_spectators',False)) is not bool or not isinstance(data.get('name', ''), str) or not isinstance(data.get('build', ''), str):
                        raise RelayError('invalid_preamble')
                    self.rate(ip, 'create', self.config['creates_per_minute'])
                    if len(self.rooms) >= self.config['max_rooms']:
                        raise RelayError('server_full')
                    for _ in range(32):
                        code = ''.join(secrets.choice(ALPHABET) for _ in range(10))
                        if code not in self.rooms:
                            break
                    else:
                        raise RelayError('server_busy')
                    room = Room(code)
                    room.public = data.get('public', False)
                    room.name = ''.join(c for c in data.get('name', '') if c.isprintable())[:24] or 'PVZ PvP'
                    room.build = data.get('build', '')[:48]
                    room.allow_spectators = data.get('allow_spectators',False)
                    self.rooms[code] = room
                    self.stats['created'] += 1
                else:
                    room = self.lookup(data)
                    if not self.authenticated(data.get('secret'), room.secret):
                        raise RelayError('resume_rejected')
                    if room.host is not None:
                        raise RelayError('host_in_use')
                    if type(data.get('allow_spectators',room.allow_spectators)) is not bool:
                        raise RelayError('invalid_preamble')
                    room.allow_spectators=data.get('allow_spectators',room.allow_spectators)
                    if not room.allow_spectators:self.close_spectators(room)
                    if data.get('reset_guest') is True:
                        room.guest_secret = None
                room.host = (reader, writer)
                room.pair.clear()
                room.done.clear()
                try:
                    await self.send(writer, dict(status='registered', code=room.code, secret=room.secret,
                                                 spectators_supported=True,room_roles_supported=True))
                    await self.wait_pair(room)
                    raw = True  # No outer error frames may enter the game stream.
                    await self.forward(room)
                finally:
                    room.active = False
                    room.host = None
                    if room.guest:
                        room.guest[1].close()
                    room.guest = None
                    room.expires = time.monotonic() + self.config['resume_timeout']
                    room.done.set()
            elif action == 'configure_spectators':
                room=self.lookup(data)
                if not self.authenticated(data.get('secret'),room.secret):raise RelayError('resume_rejected')
                if type(data.get('enabled')) is not bool:raise RelayError('invalid_preamble')
                policy=data.get('room_policy')
                if policy is not None:
                    if (not isinstance(policy,dict) or type(policy.get('available_seats')) is not int or not 0<=policy['available_seats']<=4
                            or type(policy.get('spectator_count')) is not int or not 0<=policy['spectator_count']<=5
                            or type(policy.get('allow_spectators')) is not bool):raise RelayError('invalid_preamble')
                    room.room_policy={k:policy[k] for k in ('available_seats','spectator_count','allow_spectators')}
                room.allow_spectators=data['enabled']
                if not room.allow_spectators:self.close_spectators(room)
                await self.send(writer,dict(status='configured'))
            elif action == 'watch_host':
                room=self.lookup(data)
                if not self.authenticated(data.get('secret'),room.secret):raise RelayError('resume_rejected')
                if not room.allow_spectators:raise RelayError('spectators_disabled')
                index=data.get('lane')
                if type(index) is not int or not 0<=index<4:raise RelayError('invalid_preamble')
                lane=room.spectator_lanes.get(index)
                if lane is not None and lane.host is not None:raise RelayError('host_in_use')
                lane=Room(room.code)
                room.spectator_lanes[index]=lane
                lane.host=(reader,writer)
                try:
                    await self.send(writer,dict(status='watch_ready'))
                    await self.wait_pair(lane)
                    raw=True
                    await self.forward(lane,spectator=True)
                finally:
                    lane.active=False;lane.host=None
                    if lane.guest:lane.guest[1].close()
                    lane.guest=None;lane.done.set()
            elif action == 'spectate':
                room=self.lookup(data)
                if room.host is None:raise RelayError('host_offline')
                if not room.allow_spectators:raise RelayError('spectators_disabled')
                # Every audience member has a separate byte pipe. There is no
                # writer, input or drain shared with the playing guest.
                deadline=time.monotonic()+min(4.,self.config['handshake_timeout'])
                lane=None
                while lane is None:
                    lane=next((item for item in room.spectator_lanes.values()
                               if item.host is not None and item.guest is None),None)
                    if lane is not None:break
                    if not room.allow_spectators:raise RelayError('spectators_disabled')
                    if time.monotonic()>=deadline:raise RelayError('spectators_full')
                    await asyncio.sleep(.025)
                lane.guest=(reader,writer)
                try:
                    response=dict(status='joined',secret=secrets.token_urlsafe(32))
                    if player_lane:response['player_lane']=True
                    await self.send(writer,response)
                    lane.pair.set();raw=True
                    await lane.done.wait()
                finally:
                    if lane.guest and lane.guest[1] is writer:
                        lane.guest=None
                        if lane.host:lane.host[1].close()
            elif action == 'join':
                room = self.lookup(data)
                if room.host is None:
                    raise RelayError('host_offline')
                if room.guest is not None:
                    raise RelayError('room_full')
                if room.guest_secret is not None and not self.authenticated(data.get('secret'), room.guest_secret):
                    raise RelayError('room_full')
                room.guest_secret = room.guest_secret or secrets.token_urlsafe(32)
                # Reserve before the first await: concurrent join cannot replace it.
                room.guest = (reader, writer)
                try:
                    await self.send(writer, dict(status='joined', secret=room.guest_secret))
                    room.pair.set()
                    raw = True
                    await room.done.wait()
                finally:
                    if room.guest and room.guest[1] is writer:
                        room.guest = None
                        if room.host:
                            room.host[1].close()
            else:
                raise RelayError('invalid_preamble')
        except RelayError as exc:
            self.stats['rejected'] += 1
            if not raw:
                if not preamble_read:
                    # Consume a bounded already-sent preamble before FIN. Closing
                    # with unread input can turn a useful rejection into TCP RST.
                    with contextlib.suppress(Exception):
                        await asyncio.wait_for(reader.read(MAX_CONTROL+4), .05)
                with contextlib.suppress(Exception):
                    await self.send(writer, dict(status='error', code=str(exc)))
        except (OSError, EOFError, asyncio.IncompleteReadError, asyncio.TimeoutError, ConnectionError):
            self.stats['disconnects'] += 1
        finally:
            writer.close()
            with contextlib.suppress(Exception):
                await asyncio.wait_for(writer.wait_closed(), 1)
            if admitted:
                self.connections.discard(writer)
                self.readers.pop(writer, None)
                self.per_ip[ip] -= 1
                if not self.per_ip[ip]:
                    del self.per_ip[ip]
            self.tasks.discard(task)

    @staticmethod
    def close_spectators(room):
        for lane in list(room.spectator_lanes.values()):
            if lane.host:lane.host[1].close()
            if lane.guest:lane.guest[1].close()
            lane.done.set()

    async def wait_pair(self, room):
        reader, writer = room.host
        eof = asyncio.create_task(reader.read(1))
        paired = asyncio.create_task(room.pair.wait())
        deadline = time.monotonic() + self.config['waiting_timeout']
        try:
            while True:
                done, _ = await asyncio.wait((eof, paired), timeout=min(2., max(.01, deadline-time.monotonic())), return_when=asyncio.FIRST_COMPLETED)
                if eof in done:
                    raise RelayError('host_left')
                if paired in done:
                    return
                if time.monotonic() >= deadline:
                    # A seated player or audience on a watch lane keeps the
                    # room in use; only an idle room expires.
                    if any(lane.active for lane in room.spectator_lanes.values()):
                        deadline = time.monotonic() + self.config['waiting_timeout']
                    else:
                        raise RelayError('room_expired')
                await self.send(writer, dict(status='waiting'))
        finally:
            eof.cancel()
            paired.cancel()
            await asyncio.gather(eof, paired, return_exceptions=True)

    async def forward(self, room, spectator=False):
        host, guest = room.host, room.guest
        if guest is None:
            return
        await self.send(host[1], dict(status='paired'))
        await self.send(guest[1], dict(status='paired'))
        room.active = True
        self.stats['paired'] += 1

        async def pipe(source, target, spectator_source=False):
            first=True
            while True:
                try:
                    header = await asyncio.wait_for(source.readexactly(4), self.config['idle_timeout'])
                except asyncio.IncompleteReadError as exc:
                    if exc.partial:
                        raise RelayError('truncated_frame')
                    if target.can_write_eof():
                        target.write_eof()
                    return
                size = struct.unpack('!I', header)[0]
                if not 0 < size <= MAX_FRAME:
                    raise RelayError('invalid_game_frame')
                if spectator_source and first:
                    # Bind the read-only role before the stream reaches the
                    # host. The inner transport binds it to the session token.
                    if size>16384:raise RelayError('invalid_game_frame')
                    raw=await asyncio.wait_for(source.readexactly(size),self.config['idle_timeout'])
                    try:hello=json.loads(raw.decode('utf8'))
                    except (ValueError,UnicodeError):raise RelayError('invalid_game_frame')
                    if not isinstance(hello,dict) or hello.get('type')!='hello' or hello.get('spectator') is not True:
                        raise RelayError('invalid_spectator_role')
                    target.write(header+raw)
                    await asyncio.wait_for(target.drain(),self.config['drain_timeout'])
                    self.stats['bytes_in']+=size+4;self.stats['bytes_out']+=size+4;room.bytes+=size+4
                    first=False
                    continue
                first=False
                target.write(header)
                # A full frame has an absolute deadline, not a reset per byte.
                deadline = time.monotonic() + self.config['idle_timeout']
                self.stats['bytes_in'] += 4
                self.stats['bytes_out'] += 4
                room.bytes += 4
                while size:
                    chunk = await asyncio.wait_for(source.readexactly(min(size, STREAM_CHUNK)), max(.001, deadline-time.monotonic()))
                    size -= len(chunk)
                    target.write(chunk)
                    self.stats['max_write_buffer'] = max(self.stats['max_write_buffer'], target.transport.get_write_buffer_size())
                    await asyncio.wait_for(target.drain(), self.config['drain_timeout'])
                    self.stats['bytes_in'] += len(chunk)
                    self.stats['bytes_out'] += len(chunk)
                    room.bytes += len(chunk)

        tasks = [asyncio.create_task(pipe(host[0], guest[1])), asyncio.create_task(pipe(guest[0], host[1],spectator))]
        try:
            done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            for task in done:
                task.result()
            if pending:
                await asyncio.wait_for(asyncio.gather(*pending), 2.)
        finally:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)

    async def close(self):
        if self.listener:
            self.listener.close()
            await self.listener.wait_closed()
        if self.sweeper:
            self.sweeper.cancel()
            await asyncio.gather(self.sweeper, return_exceptions=True)
        for writer in list(self.connections):
            writer.close()
        for task in list(self.tasks):
            task.cancel()
        await asyncio.gather(*list(self.tasks), return_exceptions=True)
        self.rooms.clear()


async def main(config):
    server = await RelayServer(**config).start()
    logging.info('relay ready port=%s protocol=%s', server.port, VERSION)
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        with contextlib.suppress(NotImplementedError):
            loop.add_signal_handler(sig, stop.set)
    try:
        await stop.wait()
    finally:
        await server.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', required=True)
    args = parser.parse_args()
    with open(args.config, encoding='utf8') as source:
        config = json.load(source)
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    asyncio.run(main(config))
