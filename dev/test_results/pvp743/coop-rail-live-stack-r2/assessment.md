# Post-fix retained-allocation attribution, R2

The isolated diagnostic-only sampler was relinked against the final alias-history fix and ran the same real two-process cooperative day-8 rail input for 125 battle wall seconds. Both processes exited 0, all six 30/60/120-second dumps completed, no safety guard fired, and no sample was dropped or left ungrouped. The sampler CPP/include and API driver are byte-identical to R1; the linked production libraries and executable hash are recorded in `../coop-rail-live-stack-driver-r2/build-manifest.json`. The old R1 driver and evidence were preserved.

The allocator samples approximately 1/128 allocation calls and immediately removes freed samples. Tables below contain **net change in live sampled bytes**, followed by **sample change ×128 estimates**. The latter are estimates of call-path attribution, not exact per-function accounting or proven retaining-owner identities. Rare large allocations make the guest estimate particularly noisy. Original exact requested-live totals remain the authoritative process-wide observation. DbgHelp's large PDB-loading/private-memory overhead makes this diagnostic unsuitable for RSS/private performance comparisons; use ordinary-allocator R5/R6 for those.

## Host, 60.015→120.265 seconds

Exact requested-live payload increases **4,937,518 bytes**, or **4.6892 MiB/min**. The live sample estimates a net increase of **5,193,728 bytes**, or **4.9326 MiB/min**.

| Matched allocation call-path family | Net sampled bytes | Estimated net bytes (×128) |
|---|---:|---:|
| Renderer text/rendered/font size paths | +16,768 | +2,146,304 |
| `MatchProbe::input_record` | +9,312 | +1,191,936 |
| `MatchProbe::flush_journal` / `log_event` | +6,832 | +874,496 |
| Room snapshot / map `to_dict` deep copies | +6,496 | +831,488 |
| Typed snapshot / typed map / frame projection | +3,272 | +418,816 |
| Other paths | −136 | −17,408 |
| Other deep copies | −432 | −55,296 |
| Native recipe key / draw replay | −1,536 | −196,608 |
| Alias-art observer | 0 | 0 |

The input-record and gameplay-journal call paths jointly account for an estimated **2,066,432-byte** net increase in this interval. The remaining positive groups include display caches and currently retained snapshot/map data; they are not all gameplay history and are not all proven leaks.

## Guest, 60.000→120.125 seconds

Exact requested-live payload increases **2,265,537 bytes**, or **2.1561 MiB/min**. The sample estimates **1,270,784 bytes**, or **1.2094 MiB/min**. This estimate has a large error against the exact total, so its category values identify observed allocation sites rather than exact percentages.

| Matched allocation call-path family | Net sampled bytes | Estimated net bytes (×128) |
|---|---:|---:|
| Renderer text/rendered/font size paths | +17,904 | +2,291,712 |
| Native recipe key / draw replay | +3,488 | +446,464 |
| Other paths | +496 | +63,488 |
| JSON decoder / snapshot unpack | −11,960 | −1,530,880 |
| Alias-art observer | 0 | 0 |

The guest's JSON unpack allocation family has a negative net live sample change here despite some individual sub-stacks increasing. Merely seeing positive JSON/box allocation stacks does not establish an accumulating snapshot history.

## Evidence boundary

The removed alias observer has **zero allocation stack groups in both processes**, and the host's independent `fixture_retention.aliases64` is zero throughout. Native-record projections remain zero. The original dominant JSON alias history is therefore absent from this run.

Renderer text storage has explicit existing bounds in production `src/ui/gen/pm_rendering.cpp:190–191`: text images are limited to 2,048 entries / 16 MiB and text-size storage to 8,192 entries / 2 MiB of its configured accounting. These are configured cache budgets, not an assertion that all associated C++ metadata fits the same byte count. The recipe replay cache also has a 32 MiB byte budget and 512-entry eviction contract. Snapshot/map allocation paths coexist with stable cached map data and current/previous projected state; sampled function names alone cannot determine which owner holds every byte.

The ordinary R6 run independently measured 300 seconds with at most 17 units, zero alias records and zero allocation failures. Its host late requested-live slope fell from 33.0799 to 4.3982 MiB/min. Retained input/gameplay histories remain intentionally present because they have event/audit/export contracts. This diagnostic did not delete or cap those histories. It does not establish hours-long or cross-match limits for all business histories, complete heap flatness, absence of every possible cycle, or reproduction of the earlier reported 8 GiB incident. No additional game scenarios were started after this R2 run.

Detailed allocation frames, addresses, RVAs and symbol names are in the six `*-live-alloc-*.json` files. `live-stack-summary-60-120.json` contains individual stack deltas; `call-path-categories-60-120.json` contains the exact deterministic classification of those samples. The classification script is retained at `../coop-rail-live-stack-driver-r2/classify_delta.py`, so its call-path grouping is reviewable and reproducible.
