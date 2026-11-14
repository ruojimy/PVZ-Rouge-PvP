# R6 cooperative host memory comparison after alias-history elision

The real two-process Application/Room/TCP/Windows-render scenario completed its requested 300-second battle interval on 2026-11-14. Both processes exited 0; neither the per-process 2 GiB private-byte guard nor the 4 GiB available-physical guard fired. There were no allocation failures. This test used the original production allocator, not the stack-sampling allocator, and did not initialize DbgHelp/PDB symbols. It is therefore comparable to the original ordinary-allocator R5 and is not contaminated by the sampler's roughly 600 MiB symbol-loading cost.

`../coop-rail-api-memory-driver-r6/driver-manifest.json` records the executable SHA-256 (`b441368bdba5efedd1dd7664c31ab59912c406d4d194e715c27e8aea0a59654b`), all five current static-library hashes, allocator MAP ownership and input SHA. The API driver is byte-identical to R5. The diagnostic include only adds read-only fixture-retention output. The same original day-8 rail cooperative run was copied from R4, exactly as R5 originally initialized; the guest has no initial `coop_run.json` in either test. Both use the cold `Room.rules.hero_hp` fixture, no profiling, no pauses, no raw native g/avatars, and no native-record projections.

## Exact measurements

All memory values below are MiB. The two late OLS fits use each run's actual samples from battle wall time ≥120 seconds through its final sample. R5 host ends at 300.203 seconds; R6 host ends at 299.328 seconds because its peer reaches the shared deadline and closes first. R6 guest's last sample is 300.203 seconds. This is a completed 300-second two-process run, not 300.000 seconds of independently synchronized samples per process.

| Host metric | R5 first→last | R6 first→last | R5 late OLS MiB/min | R6 late OLS MiB/min |
|---|---:|---:|---:|---:|
| Process private bytes | 585.35→848.15 | 584.79→649.86 | 50.3537 | 5.6058 |
| C++ requested live payload | 237.44→379.40 | 237.45→248.85 | 33.0799 | 4.3982 |
| SDL owned surface bytes | 161.11→209.48 | 161.11→209.49 | 1.3038 | 1.3154 |

The host requested-live growth rate fell **86.70%**, and its process-private growth rate fell **88.87%** in the late interval. The SDL surface path has essentially the same natural resource-warming trend; the fix did not remove drawing work or change the image budget.

| Guest metric | R5 first→last | R6 first→last | R5 late OLS MiB/min | R6 late OLS MiB/min |
|---|---:|---:|---:|---:|
| Process private bytes | 204.03→276.43 | 203.57→276.13 | 3.6681 | 3.6967 |
| C++ requested live payload | 48.74→60.46 | 48.80→60.46 | 2.0138 | 2.0039 |
| SDL owned surface bytes | 12.65→60.22 | 12.92→59.74 | 1.1785 | 1.3189 |

The guest changes little, consistent with the removed observer being on the host's active simulation path. Full machine-readable values and 0/30/120/180-second fit windows are in `r5-comparison.json`.

## Mechanism and execution evidence

The prior sampled run found `ContentZombiesProbe::alias_art` retaining JSON records in `aliases64`: 7,330 records at 30 seconds and 232,830 at 120 seconds. That run attributed an estimated 41,654,272-byte retained increase to this stack family. R6 records **`aliases64 == 0` at every sample**, with `no_trace == true` and `release_fixtures == true`. All other diagnostic tick/controller/phase/cost/draw arrays observed here also stay empty. The production presentation `canvas.alias` operation was preserved by the owning generator fix; independent equivalence evidence is retained separately at `../alias-retention-r1/`.

The R6 host's retained gameplay counters evolve as follows:

| Counter | First | Last | Maximum |
|---|---:|---:|---:|
| `aliases64` | 0 | 0 | 0 |
| `match_log` | 91 | 20,559 | 20,559 |
| `runtime_events` | 0 | 5,521 | 5,521 |
| `room_events` | 0 | 2 | 2 |
| Native objects | 0 | 17 | 17 |
| Atlas entries | 3,015 | 3,018 | 3,018 |
| Current frame commands | 2 | 35 | 39 |

Both R5 and R6 reach a maximum of 17 visible units. R6 host native-record projections remain zero for the whole run. Public game time progresses from 1.8333 to 300.1333 seconds on the host and 1.7333 to 300.9667 on the guest; exact native tick counts were not exported by this driver and are not inferred from those public time values. The ordinary workload continues to advance and render, so the improvement is not a paused or empty-simulation result.

## Residual growth and scope

R6 still has approximately **4.40 MiB/min of host requested-live growth** and **2.00 MiB/min on the guest** in this five-minute window. This result does **not** establish a completely flat heap or absence of another retention path. The host keeps gameplay/input history (`match_log`, `runtime_events`) while both sides warm rendering resources. The roughly 2.4 MiB/min host-minus-guest gap is compatible with additional host journal retention, but lengths alone do not prove byte attribution. These histories were not deleted or bounded because they may implement existing event/replay/diagnostic contracts.

A new post-fix sampled-live-stack run at 30/60/120 seconds would be a useful next diagnostic to distinguish that business history from remaining V/cache retention. No extra run was started as part of this report. This scenario covers the real day-8 rail cooperative input and at most 17 units, not the previous unreplicated 8 GiB incident, hours-long play, every dense planting arrangement, physical Android performance, or full game regression. Raw logs, copied userdata and connection-token files remain local evidence.
