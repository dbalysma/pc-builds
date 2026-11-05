# Case study 001: HP Victus 15L memory upgrade and clean

November 2026 · Job DBPC-2026-001 · Published anonymously with the customer's consent, which is recorded in the
private client record.

**Result:** a gaming and streaming PC running on a single 16GB memory module now has a matched 32GB pair and a
clean cooling system, and passed HP's extensive memory test twice (31.2 GB tested each time).

## The machine

| Component | Detail | Source |
|---|---|---|
| Model | HP Victus 15L Gaming Desktop TG02-0035na (product number 8C1D7EA) | HP BIOS system information |
| Motherboard | HP Erica8, board ID 89D8 | HP BIOS system information |
| CPU | AMD Ryzen 5 5600G | HP BIOS system information |
| BIOS | F.20 | HP BIOS system information |
| GPU | NVIDIA GeForce RTX 3050 8GB (OEM) | Customer's system details, card seen on inspection |
| Power supply | HP 350W | PSU label |
| Storage | Kioxia NVMe SSD | Drive label |
| OS | Windows 11 Home | Customer's system details |

## What the customer needed

The customer livestreams in two ways: PC games played on this machine, and PS5 gameplay brought in
through a capture card. He multistreams with OBS and wanted more memory ahead of GTA 6.

Moving to a matched 32GB pair was the agreed first step. No before-and-after performance measurements
were taken, so this write-up does not claim memory was the only bottleneck.

## What I found

- **One memory module, not two.** The BIOS reported 16 GB. Inside, a single 16GB DDR4 module sat in
  one of the two slots, so memory was running single-channel. (Single-channel follows from one module
  in two slots; it was not read out in software.) Planning had assumed two 8GB modules until the case
  was opened.
- **Heavy dust** on the CPU cooler fan and heatsink, the rear exhaust fan, the graphics card and the
  front intake mesh.
- **A 350W power supply.** Enough for the RTX 3050, but it limits future graphics card choices.

## Choosing the memory

The first kit the customer shortlisted, a Gigastone Game Pro (CL16, 1.35V), reaches 3200 only
through an XMP profile. [HP Community guidance for this board](https://h30434.www3.hp.com/t5/Desktop-Hardware-and-Upgrade-Questions/Ram-upgrade/m-p/9240059)
is to use CL22, 1.2V memory and avoid XMP kits. The Crucial Pro CP2K16G4DFRA32A (2×16GB DDR4-3200,
CL22, 1.2V) meets that and was chosen instead. The customer bought the kit.

Its DDR4-3200 rating is the kit's specification: a standard (JEDEC) speed at CL22 and 1.2V, so it needs no
XMP profile to reach it. That is what the kit is rated for, not what this machine was measured running:
the speed the HP actually configured was not read out (see *What these results don't show*).

## What was done

1. Recorded the starting configuration in the BIOS (16 GB) before opening the case.
2. Removed the original module.
3. Cleaned the CPU cooler and heatsink, rear fan, graphics card, front mesh and case interior.
4. Installed the matched pair, one module in each slot.
5. Reinstalled the graphics card and reassembled the case.

Every check ran in the BIOS and HP's UEFI diagnostics, outside Windows.

## Results

| Check | Tool | Result |
|---|---|---|
| Installed memory | HP BIOS system information | 32 GB (was 16 GB) |
| Processor check | HP PC Hardware Diagnostics UEFI | Passed |
| Extensive memory test, pass 1 | HP PC Hardware Diagnostics UEFI | Passed, 31.2 GB tested. Started 3 Nov 2026, 12:06 |
| Extensive memory test, pass 2 | HP PC Hardware Diagnostics UEFI | Passed, 31.2 GB tested. Started 3 Nov 2026, 17:17 |

HP PC Hardware Diagnostics UEFI was version 10. Both runs are listed as Passed in its on-screen test
log, which also gives their start times; each result screen was photographed. The first pass took at
most 5 hours 11 minutes, since the second started after it finished; HP's on-screen estimate had been
about 9.5 hours.

The test covers 31.2 of the 32 GB. The rest is reserved by the system before the test runs, which is
normal; the exact split was not measured.

**What these results don't show:**
- A passed test is evidence for that run. It is not a guarantee of long-term stability.
- Memory speed and channel mode were not read in Windows (Task Manager, CPU-Z), and temperatures under
  load were not measured. With two clean passes and the customer streaming on the machine, these were
  left out. They are the first checks to run if problems appear.
- Dual-channel operation is expected with a matched pair in both slots, but was not read out in software.

## Customer feedback

After collection, the customer posted publicly that the PC now multistreams with no lag. That is the
customer's report of real use, not a measurement.

## Recommendations given (none carried out)

- **Graphics card:** the 350W power supply, the case's room for dual-fan cards only, and the 5600G's
  PCIe 3.0 link all limit upgrades. Power needs depend on the card, so check each one's power draw and
  connectors against the 350W unit before buying; a card that needs more would also need a
  higher-wattage HP power supply. A newer card would add AV1 stream encoding.
- **BIOS:** F.20 dates from 2023. Check HP for a newer release at the next service.
- **Cleaning:** every 6 to 12 months, given the dust found.
- **If crashes or freezes appear:** rerun the extensive memory test, then test each module on its own.

## Lessons for the service

1. **Check the OEM board's requirements, not generic compatibility.** The first kit shortlisted
   depended on XMP, which this board's guidance rules out.
2. **Inspect what is installed before planning.** The module count was wrong until the case was open.
3. **Measure before naming a bottleneck.** Memory was the agreed first step for a PC that games,
   captures and streams at once. Before-and-after measurements would show what it changed; next time,
   take them.
4. **Run diagnostics outside Windows where possible.** BIOS and UEFI checks need no customer password.

## Evidence

Held privately and not published here: before and after photos, video of the work, and the HP result
screens. Photos may be added later with serial labels blurred and image metadata stripped.
