"""Run private production-library scenes for a released physical phone guest.

One room join is sufficient; the native Driver owns map, decks, units and timing.
Optional WLAN pinning is per-socket, never a system route/proxy modification.
The host is headless: its presentation rate is NOT desktop display acceptance.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import threading
import time

import psutil

ROOT = Path(__file__).resolve().parents[1]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out', required=True)
    p.add_argument('--endpoint', required=True, help='authorized relay IPv4:port')
    p.add_argument('--bind-ip', help='physical adapter address; requires --interface')
    p.add_argument('--interface', type=int)
    p.add_argument('--plan', help='JSON list: scenario, units, seconds; max four scenes')
    p.add_argument('--seconds', type=float, default=30)
    p.add_argument('--adb')
    p.add_argument('--serial')
    a = p.parse_args()
    if bool(a.bind_ip) != bool(a.interface): p.error('bind-ip and interface must be paired')
    if bool(a.adb) != bool(a.serial): p.error('adb and serial must be paired')
    if a.interface and os.name != 'nt': p.error('interface pinning is Windows only')
    host, port_text = a.endpoint.rsplit(':', 1)
    socket.inet_aton(host)
    port = int(port_text)
    scenes = json.loads(Path(a.plan).read_text('utf-8-sig')) if a.plan else [
        dict(scenario=n, units=u, seconds=a.seconds)
        for n, u in [('ordinary', 20), ('mixed', 120), ('barrage', 240), ('grabber', 120)]]
    if not isinstance(scenes, list) or not 1 <= len(scenes) <= 4: p.error('one to four scenes required')
    for scene in scenes:
        if (scene['scenario'] not in ('ordinary', 'mixed', 'barrage', 'grabber') or
                not 1 <= scene['units'] <= 300 or not 1 <= scene['seconds'] <= 90):
            p.error('unsupported scene or bound exceeded')
    out = Path(a.out).resolve()
    out.mkdir(parents=True, exist_ok=False)
    exe = ROOT / 'build/app-typed72-v2/Release/pvp743_device_network_fixture.exe'
    env = {k: v for k, v in os.environ.items() if k.lower() not in ('http_proxy', 'https_proxy', 'all_proxy')}
    env.update(NO_PROXY='*', no_proxy='*', PVP_USERDATA=str(out / 'userdata'),
               SDL_VIDEODRIVER='dummy', SDL_AUDIODRIVER='dummy')
    stop = threading.Event()
    records, sockets, workers = [], [], []
    listener = socket.socket()
    listener.bind(('127.0.0.1', 0)); listener.listen(8); listener.settimeout(1)

    def save(name, value):
        (out / name).write_text(json.dumps(value, indent=2, ensure_ascii=False), 'utf8')

    def bridge(client):
        upstream = socket.socket()
        sockets.extend((client, upstream))
        try:
            upstream.settimeout(8)
            if a.interface:
                upstream.setsockopt(socket.IPPROTO_IP, 31, socket.htonl(a.interface))
                upstream.bind((a.bind_ip, 0))
            upstream.connect((host, port)); upstream.settimeout(None)
            for sock in (client, upstream):
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 65536)
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 65536)
                sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            row = dict(local=list(upstream.getsockname()), interface=a.interface, sent=0, received=0)
            records.append(row)

            def pump(src, dst, key):
                try:
                    while not stop.is_set():
                        data = src.recv(65536)
                        if not data: break
                        dst.sendall(data); row[key] += len(data)
                except OSError: pass
                finally:
                    try: dst.shutdown(socket.SHUT_WR)
                    except OSError: pass
            thread = threading.Thread(target=pump, args=(client, upstream, 'sent'), daemon=True)
            thread.start(); pump(upstream, client, 'received'); thread.join(timeout=2)
        except OSError as exc:
            records.append(dict(error=str(exc)))
        finally:
            client.close(); upstream.close()

    def accept():
        while not stop.is_set():
            try: client, _ = listener.accept()
            except socket.timeout: continue
            except OSError: break
            thread = threading.Thread(target=bridge, args=(client,), daemon=True)
            workers.append(thread); thread.start()

    acceptor = threading.Thread(target=accept, daemon=True); acceptor.start()
    config = dict(mode='relay', endpoint='127.0.0.1:' + str(listener.getsockname()[1]), scenes=scenes)
    save('config.json', config)
    save('provenance.json', dict(exe=str(exe), exe_sha256=hashlib.sha256(exe.read_bytes()).hexdigest(),
        fixture_sha256=hashlib.sha256((ROOT/'src/uitools/pvp743_device_network_fixture.cpp').read_bytes()).hexdigest(),
        scope='Private cloud scene driver, headless production-library host, released physical phone guest; loopback WLAN bridge adds a hop.'))
    captured, last_events, ready_printed = set(), None, False
    started = time.monotonic()
    deadline = started + 300 + sum(s['seconds'] + 20 for s in scenes)
    process = None
    try:
        with (out / 'host.log').open('wb') as log:
            process = subprocess.Popen([str(exe), str(out/'config.json'), str(out)], cwd=ROOT,
                env=env, stdout=log, stderr=subprocess.STDOUT, creationflags=0x08000000)
            ps = psutil.Process(process.pid)
            ps.cpu_affinity(ps.cpu_affinity()[-2:]); ps.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
            save('process.json', dict(pid=process.pid, affinity=ps.cpu_affinity()))
            while process.poll() is None:
                if time.monotonic() > deadline: raise TimeoutError('bounded fixture deadline')
                if (out/'ready.json').exists() and not ready_printed:
                    print((out/'ready.json').read_text(), flush=True); ready_printed=True
                try: events = json.loads((out/'events.json').read_text())
                except (FileNotFoundError, json.JSONDecodeError): events = []
                if events != last_events:
                    if events: print(events[-1], flush=True)
                    last_events=events
                for event in events:
                    if (a.serial and event['event']=='scene_started' and event['index'] not in captured
                            and time.monotonic()-started > event['elapsed']+8):
                        # Read-only screenshot; scene creation uses the native API, not taps.
                        r = subprocess.run([a.adb,'-s',a.serial,'exec-out','screencap','-p'],
                                           capture_output=True,env=env,timeout=15)
                        if r.returncode==0:
                            (out/('phone-scene-'+str(event['index'])+'.png')).write_bytes(r.stdout)
                            captured.add(event['index'])
                save('tunnel.json', records)
                time.sleep(1)
            print('host exit', process.returncode, flush=True)
    finally:
        if process is not None and process.poll() is None:
            process.terminate()
            try: process.wait(timeout=10)
            except subprocess.TimeoutExpired: process.kill(); process.wait(timeout=10)
        stop.set(); listener.close()
        for sock in sockets:
            try: sock.shutdown(socket.SHUT_RDWR)
            except OSError: pass
            sock.close()
        acceptor.join(timeout=2)
        for worker in workers: worker.join(timeout=2)
        save('tunnel.json', records)
        save('cleanup.json', dict(host_exited=process is not None and process.poll() is not None,
                                 listener_closed=listener.fileno()==-1,
                                 live_bridge_threads=sum(w.is_alive() for w in workers)))
    return process.returncode


if __name__ == '__main__':
    raise SystemExit(main())
