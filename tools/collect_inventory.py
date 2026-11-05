#!/usr/bin/env python3
"""Read-only, allowlisted hardware and software inventory for a Linux (Kubuntu) PC.

What it does
  Records what is *installed and running*, as opposed to what was purchased: CPU, board and
  BIOS, memory modules and their configured speed, GPU and driver, drives, OS and desktop
  session, displays, temperatures at the time of capture, and memory-pressure settings.

What it never does
  It changes nothing. It never records serial numbers, UUIDs, MAC or IP addresses, the
  hostname, the username or home-directory paths. Each section keeps named fields only.

Usage
  python3 tools/collect_inventory.py              # everything except memory modules
  python3 tools/collect_inventory.py --dmidecode  # also memory modules (asks for sudo once)

Output: ~/db-pc-builds-evidence/inventory-<timestamp>.json and .md, outside the repository.
Review both files before sharing them.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import platform
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from privacy import PRIVATE_BANNER, mask  # noqa: E402

TOOL_VERSION = "1"
EVIDENCE_DIR = Path.home() / "db-pc-builds-evidence"


def run(cmd: list[str], timeout: int = 30) -> str | None:
    """Run a read-only command; return stdout, or None if it is missing or fails."""
    env = dict(os.environ, LC_ALL="C")
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, env=env)
    except (FileNotFoundError, PermissionError, subprocess.TimeoutExpired):
        return None
    return res.stdout if res.returncode == 0 else None


def read(path: str | Path) -> str | None:
    try:
        return Path(path).read_text(errors="replace").strip()
    except OSError:
        return None


# ---------------------------------------------------------------- CPU, board, BIOS

LSCPU_FIELDS = {
    "Model name": "model",
    "Socket(s)": "sockets",
    "Core(s) per socket": "cores_per_socket",
    "Thread(s) per core": "threads_per_core",
    "CPU(s)": "logical_cpus",
    "CPU max MHz": "max_mhz",
    "CPU min MHz": "min_mhz",
}


def parse_lscpu(text: str) -> dict:
    out = {}
    for line in text.splitlines():
        key, sep, value = line.partition(":")
        if sep and key.strip() in LSCPU_FIELDS:
            out[LSCPU_FIELDS[key.strip()]] = value.strip()
    return out


DMI_FIELDS = ("board_vendor", "board_name", "bios_vendor", "bios_version", "bios_date")


def collect_board(dmi_dir: str = "/sys/class/dmi/id") -> dict:
    return {f: v for f in DMI_FIELDS if (v := read(Path(dmi_dir) / f))}


# ---------------------------------------------------------------- memory modules

DIMM_FIELDS = {
    "Locator": "slot",
    "Bank Locator": "bank",
    "Size": "size",
    "Type": "type",
    "Speed": "rated_speed",
    "Configured Memory Speed": "configured_speed",
    "Manufacturer": "manufacturer",
    "Part Number": "part_number",
    "Rank": "rank",
    "Configured Voltage": "configured_voltage",
}


def parse_dmidecode_memory(text: str) -> list[dict]:
    """Parse `dmidecode -t 17`. Serial numbers and asset tags are never read."""
    modules = []
    for block in re.split(r"\n\s*\n", text):
        if "Memory Device" not in block:
            continue
        mod = {}
        for line in block.splitlines():
            key, sep, value = line.strip().partition(":")
            if sep and key in DIMM_FIELDS:
                mod[DIMM_FIELDS[key]] = value.strip()
        if mod.get("size") and "No Module Installed" not in mod["size"]:
            modules.append(mod)
    return modules


def parse_meminfo(text: str) -> dict:
    out = {}
    for line in text.splitlines():
        key, _, value = line.partition(":")
        if key in ("MemTotal", "SwapTotal"):
            out[key] = value.strip()
    return out


def parse_swaps(text: str) -> list[dict]:
    rows = []
    for line in text.splitlines()[1:]:
        parts = line.split()
        if len(parts) >= 3:
            kind = "zram" if "zram" in parts[0] else parts[1]
            rows.append({"kind": kind, "size_kib": parts[2]})
    return rows


def collect_memory_pressure() -> dict:
    out = {}
    if (meminfo := read("/proc/meminfo")):
        out.update(parse_meminfo(meminfo))
    if (swaps := read("/proc/swaps")):
        out["swap_devices"] = parse_swaps(swaps)
    if (sw := read("/proc/sys/vm/swappiness")):
        out["vm_swappiness"] = sw
    for unit in ("systemd-oomd", "earlyoom"):
        state = run(["systemctl", "is-active", unit])
        out[f"{unit}_active"] = (state or "inactive or not installed").strip()
    return out


# ---------------------------------------------------------------- GPU

NVIDIA_QUERY = [
    "name", "memory.total", "driver_version", "vbios_version",
    "pcie.link.gen.max", "pcie.link.gen.current", "pcie.link.width.max", "pcie.link.width.current",
    "power.limit", "temperature.gpu", "utilization.gpu", "fan.speed",
]


def parse_nvidia_csv(text: str, fields: list[str] = NVIDIA_QUERY) -> list[dict]:
    gpus = []
    for line in text.strip().splitlines():
        values = [v.strip() for v in line.split(",")]
        if len(values) == len(fields):
            gpus.append(dict(zip(fields, values)))
    return gpus


def parse_cuda_version(text: str) -> str | None:
    m = re.search(r"CUDA Version:\s*([\d.]+)", text or "")
    return m.group(1) if m else None


def parse_nvidia_module(text: str) -> dict:
    first = (text or "").splitlines()[0] if text else ""
    m = re.search(r"(\d+\.\d+(?:\.\d+)?)", first)
    return {
        "kernel_module": "open" if "Open Kernel Module" in first else ("proprietary" if first else "unknown"),
        "module_version": m.group(1) if m else None,
    }


NVIDIA_MINIMAL = ["name", "memory.total", "driver_version"]
NVIDIA_PARAMS = ("/sys/module/nvidia_drm/parameters/modeset", "/sys/module/nvidia_drm/parameters/fbdev")


def collect_gpu() -> dict:
    out: dict = {}
    q = run(["nvidia-smi", f"--query-gpu={','.join(NVIDIA_QUERY)}", "--format=csv,noheader"])
    gpus = parse_nvidia_csv(q, NVIDIA_QUERY) if q else []
    if not gpus:  # an older or newer driver may reject one of the fields: fall back to the essentials
        q = run(["nvidia-smi", f"--query-gpu={','.join(NVIDIA_MINIMAL)}", "--format=csv,noheader"])
        gpus = parse_nvidia_csv(q, NVIDIA_MINIMAL) if q else []
    if gpus:
        out["nvidia"] = gpus
        out["nvidia_drm"] = {Path(p).name: v for p in NVIDIA_PARAMS if (v := read(p))}
        out["cuda_version_supported_by_driver"] = parse_cuda_version(run(["nvidia-smi"]) or "")
        out.update(parse_nvidia_module(read("/proc/driver/nvidia/version") or ""))
        out["note"] = "PCIe generation and clocks drop at idle to save power; read them under load."
    else:
        out["nvidia"] = "nvidia-smi not available"
    return out


# ---------------------------------------------------------------- kernel and firmware settings

KERNEL_PARAM_PREFIXES = ("nvidia", "nouveau", "amdgpu", "amd_", "iommu", "amd_iommu", "pcie_", "mem_",
                         "zswap", "transparent_hugepage", "split_lock", "nowatchdog", "acpi", "processor")


def parse_cmdline(text: str) -> list[str]:
    """Keep only graphics, memory and power options; drop root/UUID/path arguments."""
    return [t for t in (text or "").split() if t.split("=", 1)[0].startswith(KERNEL_PARAM_PREFIXES)]


def parse_microcode(text: str) -> str | None:
    m = re.search(r"^microcode\s*:\s*(\S+)", text or "", re.MULTILINE)
    return m.group(1) if m else None


def collect_kernel_settings() -> dict:
    return {
        "boot_options_of_interest": parse_cmdline(read("/proc/cmdline") or ""),
        "zswap_enabled": read("/sys/module/zswap/parameters/enabled"),
        "transparent_hugepage": read("/sys/kernel/mm/transparent_hugepage/enabled"),
        "cpu_microcode": parse_microcode(read("/proc/cpuinfo") or ""),
    }


# ---------------------------------------------------------------- storage

def parse_lsblk(text: str) -> list[dict]:
    disks = []
    for dev in json.loads(text).get("blockdevices", []):
        if dev.get("type") != "disk" or str(dev.get("name", "")).startswith(("loop", "zram", "ram")):
            continue
        size = int(dev.get("size") or 0)
        disks.append({
            "device": dev.get("name"),
            "model": (dev.get("model") or "").strip(),
            "size_gb": round(size / 1e9, 1),
            "transport": dev.get("tran"),
            "rotational": bool(int(dev.get("rota") or 0)) if str(dev.get("rota")) in ("0", "1", "True", "False") else dev.get("rota"),
        })
    return disks


DF_TARGETS = ("/", "/home", "/boot", "/boot/efi")


def parse_df(text: str) -> list[dict]:
    rows = []
    for line in text.splitlines()[1:]:
        parts = line.split()
        if len(parts) == 4 and parts[0] in DF_TARGETS:
            target, size, used, avail = parts
            size_i = int(size)
            rows.append({
                "mount": target,
                "size_gb": round(size_i / 1e9, 1),
                "used_pct": round(100 * int(used) / size_i, 1) if size_i else None,
                "free_gb": round(int(avail) / 1e9, 1),
            })
    return rows


def collect_storage() -> dict:
    out: dict = {}
    if (j := run(["lsblk", "-d", "-b", "-J", "-o", "NAME,MODEL,SIZE,TRAN,ROTA,TYPE"])):
        disks = parse_lsblk(j)
        for d in disks:
            if (fw := read(f"/sys/block/{d['device']}/device/firmware_rev")):
                d["firmware"] = fw
        out["disks"] = disks
    if (df := run(["df", "-B1", "--output=target,size,used,avail"])):
        out["filesystems"] = parse_df(df)
    return out


# ---------------------------------------------------------------- OS and session

def parse_os_release(text: str) -> str | None:
    m = re.search(r'^PRETTY_NAME="?([^"\n]+)"?', text or "", re.MULTILINE)
    return m.group(1) if m else None


def first_line(text: str | None) -> str | None:
    return text.strip().splitlines()[0] if text and text.strip() else None


def collect_os() -> dict:
    return {
        "distribution": parse_os_release(read("/etc/os-release") or ""),
        "kernel": platform.release(),
        "session_type": os.environ.get("XDG_SESSION_TYPE"),
        "desktop": os.environ.get("XDG_CURRENT_DESKTOP"),
        "plasma": first_line(run(["plasmashell", "--version"])),
        "kwin": first_line(run(["kwin_wayland", "--version"])) or first_line(run(["kwin_x11", "--version"])),
        "python": platform.python_version(),
    }


# ---------------------------------------------------------------- displays

def parse_edid(data: bytes) -> dict:
    """Manufacturer ID, product code and the monitor-name descriptor. The serial-number
    field (bytes 12-15) and the serial-number descriptor (0xFF) are never read."""
    if len(data) < 128 or data[:8] != b"\x00\xff\xff\xff\xff\xff\xff\x00":
        return {}
    word = (data[8] << 8) | data[9]
    vendor = "".join(chr(((word >> s) & 0x1F) + 64) for s in (10, 5, 0))
    product = data[10] | (data[11] << 8)
    name = None
    for off in (54, 72, 90, 108):
        block = data[off:off + 18]
        if block[:3] == b"\x00\x00\x00" and block[3] == 0xFC:
            name = block[5:18].split(b"\x0a")[0].decode("ascii", "replace").strip()
    out = {"manufacturer_id": vendor, "product_code": f"0x{product:04X}"}
    if name:
        out["model_name"] = name
    return out


def parse_kscreen_json(text: str) -> list[dict]:
    outputs = []
    for o in json.loads(text).get("outputs", []):
        if not o.get("connected"):
            continue
        mode = next((m for m in o.get("modes", []) if str(m.get("id")) == str(o.get("currentModeId"))), {})
        size = mode.get("size") or {}
        outputs.append({
            "connector": o.get("name"),
            "enabled": o.get("enabled"),
            "resolution": f"{size.get('width')}x{size.get('height')}" if size else None,
            "refresh_hz": round(float(mode["refreshRate"]), 2) if mode.get("refreshRate") else None,
            "scale": o.get("scale"),
        })
    return outputs


def collect_displays(drm_dir: str = "/sys/class/drm") -> dict:
    connected = []
    for status_file in sorted(Path(drm_dir).glob("card*-*/status")):
        conn = status_file.parent
        if read(status_file) != "connected":
            continue
        entry = {"connector": conn.name.split("-", 1)[1]}
        try:
            entry.update(parse_edid(Path(conn / "edid").read_bytes()))
        except OSError:
            pass
        connected.append(entry)
    out: dict = {"connected": connected}
    if (k := run(["kscreen-doctor", "-j"])):
        try:
            out["active_modes"] = parse_kscreen_json(k)
        except (ValueError, KeyError, TypeError):
            out["active_modes"] = "kscreen-doctor output not parsed"
    return out


# ---------------------------------------------------------------- temperatures

SENSOR_CHIPS = ("k10temp", "nvme", "amdgpu", "spd5118", "jc42")


def parse_sensors_json(text: str) -> dict:
    out = {}
    for chip, readings in json.loads(text).items():
        if not chip.startswith(SENSOR_CHIPS) or not isinstance(readings, dict):
            continue
        for label, values in readings.items():
            if not isinstance(values, dict):
                continue
            for key, value in values.items():
                if key.startswith("temp") and key.endswith("_input"):
                    # The full chip id (e.g. nvme-pci-0100) is a bus location, not a serial; keeping
                    # it stops two devices of the same type overwriting each other's reading.
                    out[f"{chip}/{label}"] = round(float(value), 1)
    return out


def collect_temperatures() -> dict:
    s = run(["sensors", "-j"])
    if not s:
        return {"sensors": "lm-sensors not available"}
    try:
        return parse_sensors_json(s)
    except ValueError:
        return {"sensors": "output not parsed"}


# ---------------------------------------------------------------- report

def collect(with_dmidecode: bool) -> dict:
    report = {
        "schema": TOOL_VERSION,
        "captured_at": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "cpu": parse_lscpu(run(["lscpu"]) or ""),
        "board": collect_board(),
        "memory_pressure": collect_memory_pressure(),
        "kernel_settings": collect_kernel_settings(),
        "gpu": collect_gpu(),
        "storage": collect_storage(),
        "os": collect_os(),
        "displays": collect_displays(),
        "temperatures_at_capture": collect_temperatures(),
        "load_at_capture": read("/proc/loadavg"),
    }
    if with_dmidecode:
        text = run(["sudo", "dmidecode", "-t", "17"], timeout=120)
        report["memory_modules"] = parse_dmidecode_memory(text) if text else "dmidecode failed or was declined"
    else:
        report["memory_modules"] = "skipped (run with --dmidecode)"
    return report


def mask_tree(value):
    if isinstance(value, str):
        return mask(value)
    if isinstance(value, list):
        return [mask_tree(v) for v in value]
    if isinstance(value, dict):
        return {k: mask_tree(v) for k, v in value.items()}
    return value


def to_markdown(report: dict) -> str:
    lines = [f"> {PRIVATE_BANNER}", "", f"# Inventory captured {report['captured_at']}", ""]
    for section, content in report.items():
        if section in ("schema", "captured_at"):
            continue
        lines.append(f"## {section}")
        lines.append("```json")
        lines.append(json.dumps(content, indent=2, ensure_ascii=False))
        lines.append("```")
        lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dmidecode", action="store_true", help="also read memory modules (needs sudo)")
    ap.add_argument("--out", type=Path, default=EVIDENCE_DIR, help="output folder (default: %(default)s)")
    args = ap.parse_args(argv)
    if platform.system() != "Linux":
        print("This collector is for Linux.", file=sys.stderr)
        return 2
    report = mask_tree(collect(args.dmidecode))
    args.out.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    (args.out / f"inventory-{stamp}.json").write_text(json.dumps({"notice": PRIVATE_BANNER, **report}, indent=2) + "\n")
    (args.out / f"inventory-{stamp}.md").write_text(to_markdown(report) + "\n")
    print(f"Wrote {args.out}/inventory-{stamp}.json and .md. Review them before sharing.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
