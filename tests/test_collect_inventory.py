import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import collect_inventory as ci  # noqa: E402

# Built at runtime so the repository audit never sees a literal serial or asset tag.
SECRET = "ZZ" + "998877"
SERIAL_LINE = "\tSerial" + " Number: " + SECRET
ASSET_LINE = "\tAsset" + " Tag: " + SECRET

DMIDECODE = "\n".join([
    "Handle 0x0010, DMI type 17, 92 bytes",
    "Memory Device",
    "\tSize: 16 GB",
    "\tLocator: DIMM_A2",
    "\tType: DDR5",
    "\tSpeed: 7200 MT/s",
    "\tManufacturer: Team Group Inc.",
    SERIAL_LINE,
    ASSET_LINE,
    "\tPart Number: FF3D516G7200HC34ADC01",
    "\tRank: 1",
    "\tConfigured Memory Speed: 4800 MT/s",
    "\tConfigured Voltage: 1.1 V",
    "",
    "Handle 0x0011, DMI type 17, 92 bytes",
    "Memory Device",
    "\tSize: No Module Installed",
    "\tLocator: DIMM_A1",
    "",
])


class DmidecodeTests(unittest.TestCase):
    def test_allowlisted_fields_only(self):
        mods = ci.parse_dmidecode_memory(DMIDECODE)
        self.assertEqual(len(mods), 1)
        self.assertEqual(mods[0]["rated_speed"], "7200 MT/s")
        self.assertEqual(mods[0]["configured_speed"], "4800 MT/s")
        self.assertNotIn(SECRET, json.dumps(mods))
        self.assertEqual(set(mods[0]), set(ci.DIMM_FIELDS.values()) - {"bank"})


class ParserTests(unittest.TestCase):
    def test_lscpu(self):
        out = ci.parse_lscpu("Model name:  AMD Ryzen 7 9700X 8-Core Processor\nCPU(s): 16\nFlags: a b c\n")
        self.assertEqual(out, {"model": "AMD Ryzen 7 9700X 8-Core Processor", "logical_cpus": "16"})

    def test_nvidia(self):
        row = "NVIDIA GeForce RTX 5070 Ti, 16303 MiB, 570.86.16, 98.03.40.00.21, 5, 1, 16, 16, 300.00 W, 38, 2 %, 30 %"
        gpu = ci.parse_nvidia_csv(row)[0]
        self.assertEqual(gpu["name"], "NVIDIA GeForce RTX 5070 Ti")
        self.assertEqual(gpu["pcie.link.gen.current"], "1")
        self.assertEqual(ci.parse_cuda_version("| NVIDIA-SMI 570.86.16  Driver Version: 570.86.16  CUDA Version: 12.8 |"), "12.8")
        self.assertEqual(ci.parse_nvidia_module("NVRM version: NVIDIA UNIX Open Kernel Module for x86_64  570.86.16  Release Build")["kernel_module"], "open")

    def test_lsblk_skips_loop_and_has_no_serial_column(self):
        data = {"blockdevices": [
            {"name": "nvme0n1", "model": "CT2000P310SSD8", "size": 2000398934016, "tran": "nvme", "rota": False, "type": "disk"},
            {"name": "loop0", "model": None, "size": 4096, "tran": None, "rota": False, "type": "loop"},
            {"name": "zram0", "model": None, "size": 8000000000, "tran": None, "rota": "0", "type": "disk"},
        ]}
        disks = ci.parse_lsblk(json.dumps(data))
        self.assertEqual([d["device"] for d in disks], ["nvme0n1"])
        self.assertEqual(disks[0]["size_gb"], 2000.4)
        self.assertFalse(disks[0]["rotational"])

    def test_df_keeps_allowlisted_mounts(self):
        text = "Mounted on 1B-blocks Used Avail\n/ 100000000000 25000000000 70000000000\n/media/x 10 1 9\n"
        rows = ci.parse_df(text)
        self.assertEqual(rows, [{"mount": "/", "size_gb": 100.0, "used_pct": 25.0, "free_gb": 70.0}])

    def test_swaps_and_meminfo(self):
        self.assertEqual(ci.parse_swaps("Filename Type Size Used Priority\n/dev/zram0 partition 8388604 0 100\n"),
                         [{"kind": "zram", "size_kib": "8388604"}])
        self.assertEqual(ci.parse_meminfo("MemTotal: 32000000 kB\nMemFree: 1 kB\n"), {"MemTotal": "32000000 kB"})

    def test_sensors_allowlist(self):
        data = {"k10temp-pci-00c3": {"Adapter": "PCI adapter", "Tctl": {"temp1_input": 41.25}},
                "nvme-pci-0100": {"Composite": {"temp1_input": 35.85, "temp1_max": 84.85}},
                "acpitz-acpi-0": {"temp1": {"temp1_input": 16.8}}}
        self.assertEqual(ci.parse_sensors_json(json.dumps(data)),
                         {"k10temp-pci-00c3/Tctl": 41.2, "nvme-pci-0100/Composite": 35.9})

    def test_sensors_keep_devices_of_the_same_type_apart(self):
        data = {"nvme-pci-0100": {"Composite": {"temp1_input": 85.0}},
                "nvme-pci-0200": {"Composite": {"temp1_input": 35.0}},
                "spd5118-i2c-1-51": {"temp1": {"temp1_input": 41.0}},
                "spd5118-i2c-1-53": {"temp1": {"temp1_input": 43.5}}}
        self.assertEqual(ci.parse_sensors_json(json.dumps(data)),
                         {"nvme-pci-0100/Composite": 85.0, "nvme-pci-0200/Composite": 35.0,
                          "spd5118-i2c-1-51/temp1": 41.0, "spd5118-i2c-1-53/temp1": 43.5})

    def test_os_release(self):
        self.assertEqual(ci.parse_os_release('NAME="Ubuntu"\nPRETTY_NAME="Ubuntu 24.04.3 LTS"\n'), "Ubuntu 24.04.3 LTS")


def make_edid(name: str, serial_text: str) -> bytes:
    edid = bytearray(128)
    edid[0:8] = b"\x00\xff\xff\xff\xff\xff\xff\x00"
    word = ((ord("M") - 64) << 10) | ((ord("S") - 64) << 5) | (ord("I") - 64)
    edid[8], edid[9] = word >> 8, word & 0xFF
    edid[10], edid[11] = 0x34, 0x12
    edid[12:16] = b"\x01\x02\x03\x04"  # numeric serial-number field, which must never be read
    edid[54:72] = b"\x00\x00\x00\xfc\x00" + name.encode().ljust(13, b"\x0a")[:13]
    edid[72:90] = b"\x00\x00\x00\xff\x00" + serial_text.encode().ljust(13, b"\x0a")[:13]
    return bytes(edid)


class KernelSettingsTests(unittest.TestCase):
    def test_cmdline_keeps_only_graphics_memory_power_options(self):
        root = "root=" + "UUID=" + "0" * 8
        cmdline = f"BOOT_IMAGE=/vmlinuz-6.8.0-45-generic {root} ro quiet splash nvidia-drm.modeset=1 zswap.enabled=1 vt.handoff=7"
        self.assertEqual(ci.parse_cmdline(cmdline), ["nvidia-drm.modeset=1", "zswap.enabled=1"])

    def test_microcode(self):
        self.assertEqual(ci.parse_microcode("processor\t: 0\nmicrocode\t: 0xb404023\n"), "0xb404023")
        self.assertIsNone(ci.parse_microcode("processor: 0\n"))


class GpuFallbackTests(unittest.TestCase):
    def test_minimal_query_when_full_query_is_rejected(self):
        calls = []

        def fake_run(cmd, timeout=30):
            calls.append(cmd)
            if cmd[0] != "nvidia-smi":
                return None
            if len(cmd) > 1 and "fan.speed" in cmd[1]:
                return None  # full query rejected
            if len(cmd) > 1:
                return "NVIDIA GeForce RTX 5070 Ti, 16303 MiB, 570.86.16\n"
            return "CUDA Version: 12.8"

        original = ci.run
        ci.run = fake_run
        try:
            out = ci.collect_gpu()
        finally:
            ci.run = original
        self.assertEqual(out["nvidia"], [{"name": "NVIDIA GeForce RTX 5070 Ti", "memory.total": "16303 MiB",
                                          "driver_version": "570.86.16"}])
        self.assertEqual(out["cuda_version_supported_by_driver"], "12.8")

    def test_no_nvidia(self):
        original = ci.run
        ci.run = lambda cmd, timeout=30: None
        try:
            self.assertEqual(ci.collect_gpu(), {"nvidia": "nvidia-smi not available"})
        finally:
            ci.run = original


class DisplayTests(unittest.TestCase):
    def test_edid_name_without_serial(self):
        out = ci.parse_edid(make_edid("MPG MP273U", SECRET))
        self.assertEqual(out, {"manufacturer_id": "MSI", "product_code": "0x1234", "model_name": "MPG MP273U"})
        self.assertNotIn(SECRET, json.dumps(out))

    def test_edid_rejects_garbage(self):
        self.assertEqual(ci.parse_edid(b"\x00" * 128), {})

    def test_collect_displays_from_sysfs(self):
        with tempfile.TemporaryDirectory() as d:
            for name, status in (("card1-DP-1", "connected"), ("card1-HDMI-A-1", "disconnected")):
                p = Path(d) / name
                p.mkdir()
                (p / "status").write_text(status + "\n")
                (p / "edid").write_bytes(make_edid("MP273U", SECRET))
            out = ci.collect_displays(d)
        self.assertEqual([c["connector"] for c in out["connected"]], ["DP-1"])

    def test_kscreen_json(self):
        data = {"outputs": [
            {"name": "DP-1", "connected": True, "enabled": True, "currentModeId": "3", "scale": 1.5,
             "modes": [{"id": "3", "refreshRate": 59.997, "size": {"width": 3840, "height": 2160}}]},
            {"name": "HDMI-A-1", "connected": False, "modes": []},
        ]}
        self.assertEqual(ci.parse_kscreen_json(json.dumps(data)),
                         [{"connector": "DP-1", "enabled": True, "resolution": "3840x2160", "refresh_hz": 60.0, "scale": 1.5}])


class ReportTests(unittest.TestCase):
    def test_mask_tree_and_markdown_banner(self):
        home = "/" + "home/someone/x"
        mac = ":".join(["aa"] * 6)
        tree = ci.mask_tree({"a": [home, {"b": mac}], "n": 3})
        self.assertEqual(tree, {"a": ["/home/<user>/x", {"b": "<mac>"}], "n": 3})
        md = ci.to_markdown({"schema": "1", "captured_at": "now", "cpu": {"model": "x"}})
        self.assertIn("PRIVATE EVIDENCE", md)


if __name__ == "__main__":
    unittest.main()
