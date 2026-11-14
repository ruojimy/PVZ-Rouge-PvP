# Cooperative host retained-allocation attribution

Completed 2026-11-14. The isolated sampler ran the R5 real two-process Application/Room/TCP/Windows rendering scenario for 125 battle wall seconds, with the same copied cooperative day-8 rail run and cold hero-HP fixture. Both processes exited 0. No production file, shared library, frozen package, original R5 driver, or original R5 evidence was replaced. This is memory diagnosis, not performance acceptance or full regression.

## Measurement

`../coop-rail-live-stack-driver-r1/build-manifest.json` records the exact sources, current five production static-library hashes, executable and PDB hashes. MAP checks show global allocation entry points come from the explicit isolated `alloc_live.obj`, and the archive's original allocator is absent. The fixed sampler uses independent per-thread 1/128 admission, tracks live sampled allocations until their frees, and captures Windows stack frames. All six dumps report zero dropped samples and zero ungrouped samples. The standalone 100,000-allocation/free/reuse/epoch test passed: estimated 127,939,840 bytes versus exact 128,021,776 bytes at its checkpoint. Rare large allocations can make the gameplay sample estimate diverge more than this synthetic check; exact totals remain authoritative.

| Role/checkpoint | Exact requested live bytes | Estimated sampled live bytes | Alias-art sampled live bytes | Alias-art estimated live bytes | `aliases64` records |
|---|---:|---:|---:|---:|---:|
| Host 30.031 s | 241,407,128 | 284,037,504 | 10,648 | 1,362,944 | 7,330 |
| Host 60.156 s | 258,898,422 | 299,709,824 | 119,224 | 15,260,672 | 82,580 |
| Host 120.235 s | 295,020,496 | 332,103,040 | 336,072 | 43,017,216 | 232,830 |
| Guest 30.375 s | 53,483,637 | 50,014,208 | 0 | 0 | no simulation |
| Guest 60.422 s | 54,945,455 | 51,496,960 | 0 | 0 | no simulation |
| Guest 120.500 s | 57,202,001 | 53,891,072 | 0 | 0 | no simulation |

Between the first and last checkpoint the host's exact requested-live growth was **34.01 MiB/min**; all sampled stacks estimate **30.49 MiB/min**. The alias-art stack family alone estimates a retained increase of **41,654,272 bytes** over this interval. The guest's exact growth was **2.36 MiB/min** and has no alias-art allocations. Native record projections remain zero; `no_trace` and `release_fixtures` are both true. Tick/controller/phase observation arrays are zero. Thus neither the earlier `tick_events` suspicion nor a general missing-GC assertion explains the measured main growth.

## Concrete allocation/retention path

The six dominant positive-delta stack variants are JSON string construction and JSON array `push_back` below the same call chain:

```
ContentZombiesProbe::alias_art
MatchProbe::alias_art
ContentZombies::art_gate / ContentZombies::gate
MatchProbe::zombie_gate
ZombieActions::run
ZombiePhase::mobile_actions / ZombiePhase::run
NativeTick::run
RoomScheduler::step
TypedSession::step
```

The actual generated production composition retains this fixture observer:

- `src/sim/typed72_app/composition/probes/content_zombies64_probe.cpp:9` owns `aliases64 = J::array()`.
- The same file's `alias_art`, lines 27–28, unconditionally executes `aliases64.push_back({source,target})`.
- `src/sim/typed72_app/composition/probes/content_zombies_probe.cpp:51` delegates there.
- `src/sim/typed72_app/composition/frame_layer.inc:159–161` calls the inherited observer and the actual `canvas.alias` display operation.

The array grows by approximately 2,500 records per battle second after the initial wave arrives. Its caller is an active simulation step, so a paused host stops producing those entries while its renderer and networking can continue. The guest renders projected state and does not run that host-side simulation callback. This explains both the pause/resume and host/guest differences at the observed allocation sites. The presentation alias must remain; only diagnostic history retention should be removed or disabled using the project's owning-source/generator mechanism. This child made no production fix.

## Evidence and limits

`host-live-alloc-30.json`, `host-live-alloc-60.json`, and `host-live-alloc-120.json` contain unscaled live bytes/blocks, cohort ages, addresses, RVAs, symbol names and source lines where available. Matching guest files provide the control. `live-stack-summary.json` contains grouped 30→120 deltas. `host-memory.jsonl` contains the independent exact allocator totals and Session fixture-retention lengths. `launch.json` records successful exit codes and the original executable SHA.

Sampler raw storage is 60 MiB per process and a dump temporarily uses 16.5 MiB; neither enters requested C++ payload totals. DbgHelp loaded a large PDB and added roughly 600 MiB of process-private memory at the first dump, so this diagnostic's RSS/private values must not be compared directly with normal gameplay. Dumps cost 1.079/0.438/0.296 seconds on the host and 1.000/0.266/0.188 seconds on the guest. These pauses perturb timing; the test is not an FPS measurement. Remaining small input-journal/display allocations and longer-run behavior still require independent post-fix measurement. The sampler itself proves live allocation attribution, not the complete absence of every other leak.
