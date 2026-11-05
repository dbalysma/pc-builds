# HYTE Y70 ML workstation

Built by Dylan in March 2026 (completed 16 March). It is the training, evaluation and live-demo machine for the
MSc project [violence-detection-camera](https://github.com/dbalysma/violence-detection-camera).

> **Status:** installed hardware captured on the running machine on 5 November 2026. The 29 October freeze is
> diagnosed from the logs below, and an out-of-memory helper is now running. Stability and load testing hasn't
> been done yet.

## Purchased and installed

*Purchased* comes from the order records. *Installed* is what the machine reported about itself on
5 November 2026, using [`tools/collect_inventory.py`](../tools/collect_inventory.py).

| Part | Purchased (March 2026) | Installed and running | Match |
|---|---|---|---|
| CPU | AMD Ryzen 7 9700X | AMD Ryzen 7 9700X, 8 cores / 16 threads | Yes |
| Motherboard | MSI MAG B850 Tomahawk Max WiFi | MSI MAG B850 Tomahawk Max WiFi, BIOS 2.A40 (June 2025) | Yes |
| Memory | TeamGroup T-Force Delta RGB 32 GB (2×16 GB) DDR5-7200 CL34 | 2×16 GB DDR5 (module part number UD5-7200), one per channel, **running at 5600 MT/s, 1.1 V** | Yes, but not at its rated speed (see below) |
| Graphics | Gigabyte GeForce RTX 5070 Ti Windforce OC SFF 16 GB | NVIDIA GeForce RTX 5070 Ti, 16 GB, PCIe 5.0 ×16, driver 580.178.04 (open kernel module) | Yes |
| Storage | Crucial P310 2 TB NVMe; Crucial P310 1 TB NVMe | Crucial P310 2 TB (Kubuntu); Crucial P310 1 TB (not used by Kubuntu) | Yes |
| Displays | HYTE Y70 Touch Infinite case screen; MSI PRO MP273U 27" 4K | Y70 screen at 3840×1100; two MSI MP273U at 3840×2160 | Yes (the second MP273U isn't in the March records) |
| Cooling, PSU, case, fans | MSI MAG CoreLiquid A15 360 mm; MSI MPG A850G 850 W; HYTE Y70 Touch Infinite; Lian Li UNI FAN SL-INF | Not readable from software | Not checked |

**Memory speed.** The kit is sold as DDR5-7200, but it runs at the standard 5600 MT/s because its EXPO profile
isn't switched on in the BIOS. That is the safe default, not a fault. Following the
[testing plan](#next), EXPO stays off until the baseline is reviewed and the system has passed stability tests.

**Software.** Kubuntu (Ubuntu 26.04.1 LTS), kernel 7.0.0-42 (the freeze below happened on 7.0.0-38), KDE Plasma
6.6.6 on Wayland. Swap is 16 GB of
zram (compressed swap held in RAM) plus a 0.5 GB swap file. At the time of the freeze, no out-of-memory helper
(`systemd-oomd` or `earlyoom`) was running. Dylan turned one on afterwards (see [Fix applied](#fix-applied)).

## The 29 October freeze

The desktop froze on 29 October 2026 at about 15:24, and the machine was restarted by holding the power button.

**What the logs show** (extracted with [`tools/collect_freeze_logs.py`](../tools/collect_freeze_logs.py)):

- The last two messages before the journal stops are both *"Under memory pressure, flushing caches"*, from
  `systemd-resolved` at 15:23:25 and `systemd-journald` at 15:24:17. There are no shutdown messages, and the
  next boot started at 15:28:19.
- At 15:21:57 a desktop app was flagged as unresponsive, and at 15:22:36 input processing was lagging.
- Over the boot (six days), there were no kernel crash, graphics driver error, machine-check (hardware) error,
  storage error or thermal message.
- No process was killed by the kernel's out-of-memory killer.

**What the memory records show** (the system's own `sysstat` samples, every 10 minutes):

| Time | RAM used | Available | Swap used | Pages swapped in/out per second | Major page faults per second |
|---|---|---|---|---|---|
| 13:10 | 86.4% | 5.7 GB | 9.1 GB (57%) | 42 / 0 | 42 |
| 14:20 | 90.3% | 4.4 GB | 9.5 GB (60%) | 17 / 62 | 17 |
| 15:00 | 86.6% | 5.5 GB | 9.2 GB (58%) | 115 / 26 | 131 |
| 15:10 | 87.4% | 5.3 GB | 9.2 GB (58%) | 121 / 134 | 131 |
| 15:20 | 89.1% | 4.6 GB | 9.6 GB (60%) | 26 / 197 | 40 |
| 15:28 | Restart | | | | |

Across the afternoon, RAM stayed 86–90% full, with about 9–10 GB in swap. Programs had committed about 130%
of RAM plus swap. In the 30 minutes before the freeze, swap-ins and major page faults rose to roughly ten times
their usual level, and swap-outs stayed high. The next sample, due at 15:30, never came.

**Conclusion.** The evidence points to a memory-pressure stall: memory and swap were near their limits for
hours, paging climbed in the last half hour, and the final log lines report memory pressure. Nothing points to
the hardware or the graphics driver. Not proven: the last sample is four minutes before the freeze, so the
final collapse itself wasn't recorded, and the samples don't show which programs held the memory.

**Since then.** The machine ran for six and a half days (29 October to 5 November) and was then restarted
normally. In that time the graphics driver logged one failed memory allocation (3 November), with no freeze.

## Fix applied

On 5 November 2026 Dylan installed and enabled `systemd-oomd` (Ubuntu package 259.9), so a runaway program is
closed instead of the whole desktop stalling. Checked the same day:

- The service is enabled and running.
- The user session is managed with `ManagedOOMMemoryPressure=kill` at a 50% pressure limit, so the worst
  offender in the desktop session is closed if memory pressure stays above that.
- Ubuntu's root-slice defaults are installed (`-.slice.d/10-oomd-root-slice-defaults.conf`), which add the
  swap-usage rule for the whole system.
- Not yet checked: `oomctl` couldn't reach the service straight after the install (a D-Bus activation
  timeout), so its live view of the monitored groups is still to be read after a restart.

Whether this prevents a repeat can only be shown over time, or by a controlled memory-pressure test.

## Next

1. Read `oomctl` after the next restart to confirm which groups are monitored.
2. Record temperatures at idle and under load. One reading at capture showed the CPU's control temperature
   (Tctl) at 79 °C while the core die read 40 °C at almost no load. A single reading isn't enough to judge.
3. Then, as planned: memory, CPU and GPU stability tests and storage benchmarks, each with its method and
   results recorded here. EXPO is considered only after those pass.

Raw logs and inventories stay private. Only the figures above are published.
