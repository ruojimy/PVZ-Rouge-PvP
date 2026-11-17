"""Run native transport stress through one explicitly bounded slow TCP lane."""
from pathlib import Path
import argparse,asyncio,json,os,socket,time
async def run(args):
    output=Path(args.output).resolve();output.parent.mkdir(parents=True,exist_ok=True)
    assert not output.exists(),'Preserve existing load-test evidence'
    env=dict(os.environ,SDL_VIDEODRIVER='dummy',SDL_AUDIODRIVER='dummy',PVP_USERDATA=str(output.parent/(output.stem+'-userdata')))
    counters={'downstream_bytes':0,'upstream_bytes':0,'configured_bytes_per_second':args.rate,'initial_one_way_delay_ms':30}
    tasks=set()
    with output.with_suffix('.log').open('wb') as log:
        process=await asyncio.create_subprocess_exec(str(Path(args.exe).resolve()),str(output),str(Path(args.payload).resolve()),str(args.seconds),stdout=log,stderr=asyncio.subprocess.STDOUT,env=env)
        portfile=Path(str(output)+'.server-port');deadline=time.monotonic()+20
        while not portfile.exists():
            if process.returncode is not None:raise RuntimeError('Native server exited before listening')
            if time.monotonic()>deadline:process.kill();raise TimeoutError('Native listener setup')
            await asyncio.sleep(.02)
        port=int(portfile.read_text().strip())
        async def lane(reader,writer):
            task=asyncio.current_task();tasks.add(task)
            remote=None
            try:
                upstream,remote=await asyncio.open_connection('127.0.0.1',port,limit=16384)
                for target in (writer,remote):
                    target.transport.set_write_buffer_limits(high=16384,low=4096)
                    raw=target.get_extra_info('socket');raw.setsockopt(socket.SOL_SOCKET,socket.SO_RCVBUF,16384);raw.setsockopt(socket.SOL_SOCKET,socket.SO_SNDBUF,16384)
                async def forward(source,target,key,rate):
                    await asyncio.sleep(.03);due=time.monotonic()
                    while True:
                        chunk=await source.read(8192)
                        if not chunk:break
                        if rate:
                            due=max(due,time.monotonic())+len(chunk)/rate
                            await asyncio.sleep(max(0,due-time.monotonic()))
                        target.write(chunk);await target.drain();counters[key]+=len(chunk)
                await asyncio.gather(forward(reader,remote,'upstream_bytes',0),forward(upstream,writer,'downstream_bytes',args.rate))
            except (ConnectionError,OSError,asyncio.CancelledError):pass
            finally:
                writer.close()
                if remote:remote.close()
                tasks.discard(task)
        proxy=await asyncio.start_server(lane,'127.0.0.1',0,limit=16384)
        Path(str(output)+'.proxy-port').write_text(str(proxy.sockets[0].getsockname()[1]))
        started=time.monotonic()
        try:code=await asyncio.wait_for(process.wait(),args.seconds+50)
        except asyncio.TimeoutError:process.kill();await process.wait();raise
        finally:
            proxy.close();await proxy.wait_closed()
            for task in list(tasks):task.cancel()
            if tasks:await asyncio.gather(*list(tasks),return_exceptions=True)
        counters.update(wall_seconds=time.monotonic()-started,native_exit_code=code)
        output.with_suffix('.proxy.json').write_text(json.dumps(counters,indent=2),encoding='utf8')
        print(json.dumps(counters),flush=True)
        if code:print(output.read_text('utf8') if output.exists() else output.with_suffix('.log').read_text('utf8',errors='replace')[-4000:]);raise SystemExit(code)
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('exe');parser.add_argument('payload');parser.add_argument('output');parser.add_argument('--seconds',type=int,default=20);parser.add_argument('--rate',type=int,default=131072)
    asyncio.run(run(parser.parse_args()))
