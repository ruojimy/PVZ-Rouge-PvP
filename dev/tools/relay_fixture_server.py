"""Out-of-process REAL Python relay for native client tests (decision 11-02: relay server stays Python).

    python relay_fixture_server.py <relay_server.py> '<options json>'

Loads the unmodified relay_server.py, starts RelayServer(port=0, **options) on its own asyncio loop and
serves a line-based JSON control channel on stdin/stdout. Only observation and the coarse operations the
client-facing tests perform are exposed (config writes, room listing, aborting a host lane, dropping the
registry, snapshot, connection buffer limits). The three unchanged async server fixtures are selected from verified original
ASTs. Other server method replacements and module mocks remain unsupported.
"""
import asyncio
import importlib.util
import json
import sys
import threading
from pathlib import Path


def main():
    path, options = sys.argv[1], json.loads(sys.argv[2])
    spec = importlib.util.spec_from_file_location('pvp_relay_server_fixture', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    helper_path=Path(__file__).with_name('relay_async_fixture.py')
    helper_spec=importlib.util.spec_from_file_location('pvp_original_relay_async_fixture',str(helper_path))
    fixtures=importlib.util.module_from_spec(helper_spec);helper_spec.loader.exec_module(fixtures)
    server = module.RelayServer(port=0, **options)
    loop.run_until_complete(server.start())
    out = sys.stdout
    lock = threading.Lock()

    def reply(value):
        with lock:
            out.write(json.dumps(value, ensure_ascii=True) + "\n")
            out.flush()

    def room_view(room):
        return dict(host=bool(room.host), guest=bool(room.guest), public=room.public, active=room.active,
                    allow_spectators=room.allow_spectators,
                    spectator_lanes={str(k): dict(guest=lane.guest is not None) for k, lane in room.spectator_lanes.items()})

    def run(cmd):
        op = cmd.get("op")
        if op == "fixture_install":
            name,function=fixtures.load(server,cmd)
            if name!='legacy_send':raise ValueError('Only the original legacy send fixture can be installed')
            server.send=function;return None
        if op == "config_set":
            server.config[cmd["key"]] = cmd["value"]; return None
        if op == "config_get":
            return server.config[cmd["key"]]
        if op == "rooms":
            return {code: room_view(r) for code, r in server.rooms.items()}
        if op == "abort_host":
            room = server.rooms.get(cmd["code"])
            if room and room.host: room.host[1].transport.abort()
            return None
        if op == "clear_rooms":
            server.rooms.clear(); return None
        if op == "snapshot":
            return server.snapshot()
        if op == "connections":
            return [dict(limits=list(w.transport.get_write_buffer_limits()),
                         max_size=getattr(w.transport, "max_size", None)) for w in list(server.connections)]
        if op == "batch":   # the writes one test callback made, applied in ONE loop callback like the original
            for sub in cmd["ops"]: run(sub)
            return None
        raise ValueError("unknown op %r" % op)

    def handle(cmd):
        if cmd.get('op')=='fixture_call':
            async def inspect_original_fixture():
                try:
                    name,function=fixtures.load(server,cmd)
                    if name!='inspect':raise ValueError('Only the original transport inspection fixture can be awaited')
                    reply(dict(ok=True,value=await function()))
                except Exception as error:reply(dict(ok=False,error='%s: %s'%(type(error).__name__,error)))
            asyncio.ensure_future(inspect_original_fixture());return
        if cmd.get("op") == "close":
            async def shut():
                await server.close()
                reply(dict(ok=True)); loop.stop()
            asyncio.ensure_future(shut()); return
        try:
            reply(dict(ok=True, value=run(cmd)))
        except Exception as e:  # reported to the native test as an error, never swallowed
            reply(dict(ok=False, error="%s: %s" % (type(e).__name__, e)))

    def reader():
        for line in sys.stdin:
            line = line.strip()
            if line:
                loop.call_soon_threadsafe(handle, json.loads(line))
        loop.call_soon_threadsafe(loop.stop)   # parent went away

    threading.Thread(target=reader, daemon=True).start()
    reply(dict(ready=True, port=server.port))
    loop.run_forever()


if __name__ == "__main__":
    main()
