#!/usr/bin/env python3
"""Read-only extract of the system journal around a freeze, for diagnosis.

Step 1: list the boots the journal still holds, and find the one that froze:
  python3 tools/collect_freeze_logs.py --list
  python3 tools/collect_freeze_logs.py --list --date 2026-10-29

Step 2: extract from that boot, by its index from the list (for example -1 for the boot
before the current one):
  python3 tools/collect_freeze_logs.py --boot -1

The extract shows:
- how the boot ended (confirmed shutdown, unclear, none, or unknown);
- when the next boot began, relative to the last entry;
- how many error-level messages each program logged;
- every warning from the final 10 minutes;
- the lines that matter for the usual causes of a desktop freeze;
- the final lines before the journal stops.

The usual causes it looks for are memory exhaustion, GPU or compositor faults, hardware
error reports, kernel hangs, storage errors and thermal events.

It changes nothing and needs no sudo if your user can read the system journal (the
first Ubuntu user can). Usernames, hostnames, home paths, URLs, e-mail, IP and MAC
addresses are masked. The output is still PRIVATE evidence: review it before sharing,
and never commit it.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from privacy import PRIVATE_BANNER, mask  # noqa: E402

EVIDENCE_DIR = Path.home() / "db-pc-builds-evidence"

CATEGORIES: dict[str, re.Pattern] = {
    "memory pressure": re.compile(
        r"out of memory|oom[-_ ]?kill|oom_reaper|killed process|systemd-oomd|earlyoom|"
        r"page allocation failure|memory pressure|out of swap", re.I),
    "gpu and compositor": re.compile(
        r"NVRM|\bXid\b|nvidia-modeset|nvidia-drm|fallen off the bus|flip_done timed out|atomic commit|"
        r"amdgpu.*(error|fail|timeout|reset)|drm:.*(error|fail)|"
        r"(kwin|plasmashell).*(crash|fatal|abort|segfault|freez|frozen|context lost|reset|timed? ?out)|"
        r"GPU process (exited|crashed|isn't usable)|gpu_process_host", re.I),
    "hardware errors": re.compile(
        r"\bmce\b|machine check|hardware error|EDAC|PCIe Bus Error|\bAER\b|WHEA", re.I),
    "kernel hangs and crashes": re.compile(
        r"soft lockup|hard lockup|hung_task|blocked for more than|\bBUG:|Oops|"
        r"Call Trace|segfault|general protection|core dumped|dumped core", re.I),
    "storage": re.compile(
        r"I/O error|nvme.*(timeout|reset|error)|EXT4-fs error|btrfs.*error|Buffer I/O", re.I),
    "thermal": re.compile(
        r"temperature above threshold|critical temperature|thermal (trip|shutdown|throttl)|"
        r"clock throttled|throttling", re.I),
}

# Messages only a real shutdown produces.
SHUTDOWN_MARKERS = re.compile(
    r"Reached target .*(Power[- ]Off|Reboot|Shutdown|Halt)|System is (powering down|rebooting)|"
    r"systemd-shutdown|reboot: (Power down|Restarting)", re.I)
# journald also logs these when it restarts in the middle of a boot, so they count only at the very end.
JOURNAL_STOPPED = re.compile(r"Journal stopped", re.I)
JOURNAL_STARTED = re.compile(r"Journal started", re.I)
SYSTEM_USERS = {"root", "gdm", "sddm", "lightdm", "nobody", "systemd-coredump", "messagebus"}

PER_CATEGORY = 40
TAIL_LINES = 80
FINAL_MINUTES = 10
JOURNAL_DIR: Path | None = None  # set by --directory to read a copied journal instead


def journalctl(args: list[str], timeout: int = 180) -> str:
    env = dict(os.environ, LC_ALL="C", SYSTEMD_COLORS="0", SYSTEMD_PAGER="")
    where = ["--directory", str(JOURNAL_DIR)] if JOURNAL_DIR else []
    res = subprocess.run(["journalctl", "--no-pager", *where, *args], capture_output=True, text=True,
                         timeout=timeout, env=env)
    if res.returncode != 0:
        raise SystemExit(f"journalctl failed: {res.stderr.strip() or res.returncode}")
    return res.stdout


# ---------------------------------------------------------------- boots

def _from_usec(value) -> dt.datetime:
    return dt.datetime.fromtimestamp(int(value) / 1e6).astimezone()


def parse_boots_json(text: str) -> list[dict]:
    boots = []
    for b in json.loads(text):
        boots.append({
            "index": int(b["index"]),
            "first": _from_usec(b["first_entry"]),
            "last": _from_usec(b["last_entry"]),
        })
    return boots


BOOT_LINE = re.compile(
    r"^\s*(-?\d+)\s+[0-9a-f]{32}\s+\w{3}\s+(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) (\S+)\s*[—-]*\s*"
    r"\w{3}\s+(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) (\S+)")


def parse_boots_text(text: str) -> list[dict]:
    """Fallback for older journalctl without JSON output for --list-boots."""
    boots = []
    for line in text.splitlines():
        m = BOOT_LINE.match(line)
        if m:
            first = dt.datetime.strptime(m.group(2), "%Y-%m-%d %H:%M:%S")
            last = dt.datetime.strptime(m.group(4), "%Y-%m-%d %H:%M:%S")
            boots.append({"index": int(m.group(1)), "first": first, "last": last, "tz": m.group(3)})
    return boots


def list_boots() -> list[dict]:
    try:
        return parse_boots_json(journalctl(["--list-boots", "-o", "json"]))
    except (SystemExit, ValueError, KeyError):
        return parse_boots_text(journalctl(["--list-boots"]))


def overlaps(boot: dict, day: dt.date) -> bool:
    return boot["first"].date() <= day <= boot["last"].date()


def format_boots(boots: list[dict], day: dt.date | None = None) -> str:
    rows = ["index | first entry | last entry | length", "---|---|---|---"]
    for b in boots:
        if day and not overlaps(b, day):
            continue
        length = b["last"] - b["first"]
        rows.append(f"{b['index']} | {b['first']:%Y-%m-%d %H:%M:%S} | {b['last']:%Y-%m-%d %H:%M:%S} | {length}")
    if len(rows) == 2:
        rows.append("(no boots found" + (f" overlapping {day}" if day else "") + ")")
    if len(boots) <= 1:
        rows.append("")
        rows.append("Only one boot is stored: the journal may not be persistent, so logs from before the "
                    "last restart could be gone. Check that /var/log/journal exists.")
    return "\n".join(rows)


# ---------------------------------------------------------------- one boot

SHUTDOWN_STATUS = {
    "confirmed": "**yes**: power-off or reboot messages close the boot, and journald did not start again after them",
    "journal-stopped-only": "**unclear**: journald stopped at the very end, but there are no power-off or reboot "
                            "messages to confirm an orderly shutdown",
    "none": "**no**: the journal stops without shutdown messages, as after a forced power-off or a hard hang",
    "unknown": "**unknown**: the system journal was not readable, so system shutdown messages could not be checked",
}


def shutdown_status(lines: list[str]) -> str:
    """How the boot ended, judged only from what happened after journald last (re)started.

    confirmed            a system power-off/reboot marker appears after the last "Journal started"
    journal-stopped-only "Journal stopped" is among the final lines, with no later restart, but no
                         power-off/reboot marker corroborates it
    none                 neither
    unknown              no kernel messages are visible (permission-limited journal), so system
                         shutdown messages could not have been seen either
    """
    if not kernel_visible(lines):
        return "unknown"
    tail = lines[-400:]
    restarted = max((i for i, l in enumerate(tail) if JOURNAL_STARTED.search(l)), default=-1)
    after_restart = tail[restarted + 1:]
    if any(SHUTDOWN_MARKERS.search(l) for l in after_restart):
        return "confirmed"
    if any(JOURNAL_STOPPED.search(l) for l in after_restart[-5:]):
        return "journal-stopped-only"
    return "none"


def clean_shutdown(lines: list[str]) -> bool:
    """True only for a corroborated, orderly shutdown."""
    return shutdown_status(lines) == "confirmed"


def journal_identities(raw_lines: list[str]) -> tuple[set[str], set[str]]:
    """Hostnames and login names that appear in the journal itself, so a journal copied from
    another machine is masked with *its* names, not this machine's. In short-iso output the
    hostname is the second field; login names come from logind's "... of user NAME" messages."""
    hosts, users = set(), set()
    for line in raw_lines:
        parts = line.split(" ", 2)
        if len(parts) >= 2 and line_time(line):
            hosts.add(parts[1])
        users.update(m.group(1) for m in re.finditer(r"\b(?:of|for) user ([a-z_](?:[\w.-]*\w)?)", line, re.I))
    return hosts, {u for u in users if u.lower() not in SYSTEM_USERS}


def make_masker(raw_lines: list[str]):
    hosts, users = journal_identities(raw_lines)

    def masker(line: str) -> str:
        parts = line.split(" ", 2)
        if len(parts) == 3 and line_time(line) and parts[1] in hosts:
            line = f"{parts[0]} <host> {parts[2]}"
        out = mask(line)
        for value, placeholder in [(h, "<host>") for h in hosts] + [(u, "<user>") for u in users]:
            if value and len(value) >= 2 and not value.startswith("<"):
                out = re.sub(rf"(?<![\w-]){re.escape(value)}(?![\w-])", placeholder, out)
        return out

    return masker


def categorise(lines: list[str]) -> dict[str, list[str]]:
    hits: dict[str, list[str]] = {name: [] for name in CATEGORIES}
    for line in lines:
        for name, pattern in CATEGORIES.items():
            if pattern.search(line):
                hits[name].append(line)
    return hits


def trim(lines: list[str], n: int = PER_CATEGORY) -> list[str]:
    if len(lines) <= n:
        return lines
    half = n // 2
    return lines[:half] + [f"... {len(lines) - n} lines omitted ..."] + lines[-half:]


def error_counts(json_lines: str) -> Counter:
    counts: Counter = Counter()
    for line in json_lines.splitlines():
        try:
            entry = json.loads(line)
        except ValueError:
            continue
        if not isinstance(entry, dict):
            continue
        ident = entry.get("SYSLOG_IDENTIFIER") or entry.get("_COMM") or "unknown"
        counts[mask(str(ident))] += 1
    return counts


def line_time(line: str) -> dt.datetime | None:
    """Timestamp at the start of a short-iso journal line."""
    try:
        return dt.datetime.fromisoformat(line.split(" ", 1)[0])
    except ValueError:
        return None


def last_time(lines: list[str]) -> dt.datetime | None:
    return next((t for t in map(line_time, reversed(lines)) if t), None)


def final_window(lines: list[str], minutes: int = FINAL_MINUTES, end: dt.datetime | None = None) -> list[str]:
    """Lines from the `minutes` before `end`, which should be the boot's final entry (all
    messages, not only these lines). Defaults to the last timestamp in `lines`."""
    end = end or last_time(lines)
    if end is None:
        return []
    start = end - dt.timedelta(minutes=minutes)
    return [l for l in lines if (t := line_time(l)) and t >= start]


def next_boot_gap(boots: list[dict], boot: int) -> str | None:
    """How long after this boot's last entry the following boot began."""
    by_index = {b["index"]: b for b in boots}
    if boot in by_index and boot + 1 in by_index:
        gap = by_index[boot + 1]["first"] - by_index[boot]["last"]
        return f"{by_index[boot + 1]['first']:%Y-%m-%d %H:%M:%S} ({gap} after this boot's last entry)"
    return None


def kernel_visible(lines: list[str]) -> bool:
    """True if any kernel message is present. Without permission to read the system journal,
    journalctl quietly returns only the user's own session messages."""
    return any(" kernel: " in l or " kernel[" in l for l in lines)


NO_KERNEL_WARNING = (
    "**No kernel messages were readable for this boot,** so this extract is missing the system side. "
    "Your user is probably not allowed to read the system journal. Rerun with "
    "`sudo python3 tools/collect_freeze_logs.py --boot {boot} --out ~/db-pc-builds-evidence`, "
    "or add yourself to the `adm` group and log in again.")


def extract(boot: int, boots: list[dict] | None = None) -> str:
    raw = [l for l in journalctl([f"--boot={boot}", "-o", "short-iso"]).splitlines() if l and not l.startswith("-- ")]
    masker = make_masker(raw)
    lines = [masker(l) for l in raw]
    if not lines:
        return f"No journal entries for boot {boot}."
    errors = error_counts(journalctl([f"--boot={boot}", "-p", "3", "-o", "json",
                                      "--output-fields=SYSLOG_IDENTIFIER,_COMM"]))
    warnings = [masker(l) for l in journalctl([f"--boot={boot}", "-p", "4", "-o", "short-iso"]).splitlines()
                if l and not l.startswith("-- ")]
    hits = categorise(lines)
    gap = next_boot_gap(boots or [], boot)
    out = [f"> {PRIVATE_BANNER}", "", f"# Journal extract, boot {boot}", "",
           f"- First entry: `{lines[0][:25]}`",
           f"- Last entry: `{lines[-1][:25]}`",
           f"- Next boot started: {gap or 'not known (this is the latest boot, or the next is not stored)'}",
           f"- Lines in this boot: {len(lines)}",
           f"- Clean shutdown recorded: {SHUTDOWN_STATUS[shutdown_status(lines)]}",
           "",
           *([] if kernel_visible(lines) else [NO_KERNEL_WARNING.format(boot=boot), ""]),
           "How to read the gap: if the last entry is close to when the screen froze, logging stopped with the "
           "freeze (a hard hang points towards the kernel, driver or hardware). If entries continue well after the "
           "freeze began, the kernel was still running and the desktop or memory pressure is the likelier cause.",
           "", "## Error-level messages (priority 0-3) by program", ""]
    out += [f"- {ident}: {n}" for ident, n in errors.most_common(25)] or ["- none"]
    last = final_window(warnings, end=last_time(lines))
    out += ["", f"## Warnings and errors in the final {FINAL_MINUTES} minutes: {len(last)} lines", ""]
    if last:
        out += ["```"] + trim(last, 60) + ["```"]
    for name, found in hits.items():
        out += ["", f"## {name}: {len(found)} matching lines", ""]
        if found:
            out += ["```"] + trim(found) + ["```"]
    out += ["", f"## Last {TAIL_LINES} lines before the journal stops", "", "```"] + lines[-TAIL_LINES:] + ["```"]
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    global JOURNAL_DIR
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--list", action="store_true", help="list stored boots")
    ap.add_argument("--date", type=dt.date.fromisoformat, help="with --list: only boots overlapping YYYY-MM-DD")
    ap.add_argument("--boot", type=int, help="extract from this boot index (from --list)")
    ap.add_argument("--directory", type=Path, help="read a journal folder instead of the system journal")
    ap.add_argument("--out", type=Path, default=EVIDENCE_DIR, help="output folder (default: %(default)s)")
    args = ap.parse_args(argv)
    JOURNAL_DIR = args.directory
    boots = list_boots()
    if args.list or args.boot is None:
        print(format_boots(boots, args.date))
        if args.boot is None:
            print("\nNext: run with --boot <index> for the boot that froze "
                  "(usually the one whose last entry is just before the forced power-off).")
            return 0
    report = extract(args.boot, boots)
    args.out.mkdir(parents=True, exist_ok=True)
    path = args.out / f"freeze-boot{args.boot}-{dt.datetime.now():%Y%m%d-%H%M%S}.md"
    path.write_text(report + "\n")
    print(f"Wrote {path}. Review it before sharing; it may still contain window or file names.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
