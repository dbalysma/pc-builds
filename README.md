# PC builds and diagnostics

PC builds, upgrades and diagnostics by Dylan Balysma (BEng Electromechanical Engineering, MSc
Robotics & AI). This repository documents real builds with evidence captured on the machines
themselves, and is the technical foundation for a PC build, upgrade and diagnostics service.

> **Status: work in progress.** The first build's installed hardware is verified and its October freeze is
> diagnosed; stability tests are next. A result appears here only after it has been captured on the machine;
> nothing is estimated or copied from spec sheets.

## Timeline

Each date comes from a dated record: order and delivery emails, dated photos, the machine's own logs, or this
repository's history.

| Date | What happened | Evidence |
|---|---|---|
| 7–12 Mar 2026 | Workstation parts ordered; the last core part, the graphics card, delivered on 12 March | Order and delivery records |
| 16 Mar 2026 | HYTE Y70 workstation build complete by this date | Dated photo of the finished build |
| Aug 2026 | Workstation used to train, evaluate and demo the MSc project [violence-detection-camera](https://github.com/dbalysma/violence-detection-camera) | Dated photos and recordings; that project's results |
| 29 Oct 2026 | Desktop froze; machine restarted by hand | The machine's system journal |
| 30 Oct 2026 | Read-only diagnostic tools built and tested | Development history (private repository) |
| Nov 2026 | First documented client job: a memory upgrade and clean ([case study 001](case-studies/001-hp-victus-15l-memory-upgrade.md)) | Job record (private); case study |
| 5 Nov 2026 | Service workflow templates added. Workstation hardware verified on the machine, the freeze diagnosed, and an out-of-memory helper enabled ([Y70 page](builds/hyte-y70-workstation.md)) | Development history (private repository); captures from the machine |

## Builds

| Build | Purpose | Status |
|---|---|---|
| [HYTE Y70 ML workstation](builds/hyte-y70-workstation.md) (March 2026) | Training, evaluation and live-demo machine for the MSc project [violence-detection-camera](https://github.com/dbalysma/violence-detection-camera) | Installed hardware verified; 29 Oct freeze diagnosed and out-of-memory helper enabled; stability tests next |

## Case studies

Customer work, published anonymously and only with the customer's consent.

| Case study | Work | Status |
|---|---|---|
| [001: HP Victus 15L memory upgrade](case-studies/001-hp-victus-15l-memory-upgrade.md) | Single 16GB module replaced with a matched 32GB pair, internal clean, HP UEFI diagnostics | Job completed November 2026; published with the customer's consent |

## How evidence works here

- **Purchased is not the same as installed.** Parts lists from order records are labelled
  *purchased*. Only specifications captured on the running machine are labelled *installed*.
- **Every published number has a capture behind it**, with the date, OS, driver and settings,
  and the exact command so it can be repeated.
- **A passed test is evidence for that run.** It is not a guarantee of long-term stability.
- **Raw evidence stays private.** Logs and inventories are collected outside this repository,
  reviewed, and only sanitised measurements and methods are committed.

## Service workflow

Every build, upgrade, repair and diagnostics job follows the same steps, from enquiry to handover:
intake, job sheet, pre-service checks, service, QA sign-off, handover, and a consent-and-anonymisation
gate before any case study. The blank templates and the rules behind them are in
[services/](services/README.md). Filled-in copies, quotes and customer details stay in the private
client record, never in this repository.

## Tools

All tools are read-only Python 3 scripts with no dependencies beyond the standard library. They
write to `~/db-pc-builds-evidence/`, outside the repository.

| Tool | What it does |
|---|---|
| `tools/collect_inventory.py` | Records what is installed and running: CPU, board and BIOS, memory modules and their configured speed (`--dmidecode`, asks for sudo once), GPU and driver, drives, OS and desktop session, displays, temperatures and memory-pressure settings. Named fields only: no serial numbers, UUIDs, MAC or IP addresses, hostname or username. |
| `tools/collect_freeze_logs.py` | For diagnosing a freeze on Linux. `--list` (optionally `--date YYYY-MM-DD`) shows the boots the journal holds. `--boot N` extracts that boot: how it ended, the gap to the next boot, error counts per program, warnings from the final 10 minutes, lines matching memory, GPU/compositor, hardware, kernel, storage and thermal problems, and the final lines before the journal stops. Identifiers are masked; the output is still private. |
| `tools/audit_public.py` | Runs in CI on every change. Fails if a committed file contains prices, contact details, order or tracking numbers, serial numbers, UUIDs, network addresses, home paths, AI session links, image metadata, or a file type that isn't allowed. A safety net behind the collectors' allowlists, not a guarantee. |

## Running the Phase 1 checks (Kubuntu)

Everything here only reads. Nothing changes a setting or puts the machine under load.

```bash
git clone https://github.com/dbalysma/pc-builds.git && cd pc-builds

# 1. Check the tools on this machine. The integration tests also run both collectors and
#    confirm that the hostname, username and network/device identifiers don't appear in the output.
python3 -m unittest discover -s tests

# 2. Find the boot that froze, then extract it.
python3 tools/collect_freeze_logs.py --list --date 2026-10-29
python3 tools/collect_freeze_logs.py --boot <index>

# 3. Record what is installed and running (asks for the sudo password once, for memory modules).
python3 tools/collect_inventory.py --dmidecode
```

Then read the files in `~/db-pc-builds-evidence/` before sharing them. They are private evidence and
are never committed here.

The freeze extract shows:
- how the boot ended: a **confirmed** orderly shutdown (power-off or reboot messages after journald's last
  start), **unclear** (journald stopped but nothing corroborates a shutdown), **no** shutdown messages (as
  after a forced power-off or hard hang), or **unknown** if the system journal wasn't readable;
- when the next boot started, relative to the last log entry;
- error counts per program;
- every warning from the final 10 minutes;
- lines matching memory pressure, GPU and compositor, hardware error, kernel hang, storage and thermal patterns;
- the final 80 lines.

Read the gap together with how long you waited before holding the power button. A gap close to that wait
means logging stopped when the screen froze: a hard hang, pointing at the kernel, driver or hardware. A gap of
only seconds means the kernel kept logging until power-off: more likely a desktop or memory-pressure stall.

## Privacy

This repository never contains customer names or details, quotes, prices, costs or margins, order
or tracking numbers, addresses, serial numbers, or photo location data. Customer work, if it is
ever shown, appears only as an anonymised case study with the customer's consent.

## Authorship

The builds, hardware work and testing are Dylan's own. AI tools (Claude, ChatGPT, Codex) helped
write the scripts and documentation; Dylan reviews and approves every change. Commit messages
start with `[Dylan]`, `[Claude]` or `[ChatGPT]` to show the intended contributor.

This is the public showcase. Development, reviews and private evidence are kept in a separate private
repository, so this repository's commit history starts at publication. The dates in the timeline come from the
records listed there, not from commit dates.
