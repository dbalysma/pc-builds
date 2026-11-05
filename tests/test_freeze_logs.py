import datetime as dt
import json
import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import collect_freeze_logs as fl  # noqa: E402


def usec(y, mo, d, h, mi):
    return int(dt.datetime(y, mo, d, h, mi).astimezone().timestamp() * 1e6)


class BootListTests(unittest.TestCase):
    def test_json_boots_and_date_filter(self):
        data = [
            {"index": -2, "boot_id": "a" * 32, "first_entry": usec(2026, 10, 28, 9, 0), "last_entry": usec(2026, 10, 29, 1, 0)},
            {"index": -1, "boot_id": "b" * 32, "first_entry": usec(2026, 10, 29, 10, 0), "last_entry": usec(2026, 10, 29, 23, 40)},
            {"index": 0, "boot_id": "c" * 32, "first_entry": usec(2026, 10, 30, 8, 0), "last_entry": usec(2026, 10, 30, 9, 0)},
        ]
        boots = fl.parse_boots_json(json.dumps(data))
        table = fl.format_boots(boots, dt.date(2026, 10, 29))
        self.assertIn("\n-2 |", table)
        self.assertIn("\n-1 |", table)
        self.assertNotIn("\n0 |", table)
        self.assertNotIn("a" * 32, table)

    def test_text_fallback(self):
        text = ("IDX BOOT ID                          FIRST ENTRY                 LAST ENTRY\n"
                " -1 " + "b" * 32 + " Thu 2026-10-29 10:00:01 GMT Thu 2026-10-29 23:40:12 GMT\n"
                "  0 " + "c" * 32 + " Fri 2026-10-30 08:00:00 GMT Fri 2026-10-30 09:00:00 GMT\n")
        boots = fl.parse_boots_text(text)
        self.assertEqual([b["index"] for b in boots], [-1, 0])
        self.assertEqual(boots[0]["last"], dt.datetime(2026, 10, 29, 23, 40, 12))

    def test_single_boot_warns_about_persistence(self):
        boots = [{"index": 0, "first": dt.datetime(2026, 10, 30, 8), "last": dt.datetime(2026, 10, 30, 9)}]
        self.assertIn("not be persistent", fl.format_boots(boots))


class ExtractTests(unittest.TestCase):
    LINES = [
        "2026-10-29T23:39:01+00:00 DBPC kernel: NVRM: Xid (PCI:0000:01:00): 79, GPU has fallen off the bus.",
        "2026-10-29T23:39:02+00:00 DBPC kernel: Out of memory: Killed process 4242 (code)",
        "2026-10-29T23:39:03+00:00 DBPC plasmashell[1200]: qml: binding loop detected",
        "2026-10-29T23:39:04+00:00 DBPC kwin_wayland[900]: kwin_wayland_drm: atomic commit failed",
        "2026-10-29T23:39:05+00:00 DBPC kernel: watchdog: BUG: soft lockup - CPU#3 stuck for 22s!",
        "2026-10-29T23:39:06+00:00 DBPC kernel: mce: [Hardware Error]: Machine check events logged",
    ]

    def test_categories(self):
        hits = fl.categorise(self.LINES)
        self.assertEqual(len(hits["gpu and compositor"]), 2)
        self.assertEqual(len(hits["memory pressure"]), 1)
        self.assertEqual(len(hits["kernel hangs and crashes"]), 1)
        self.assertEqual(len(hits["hardware errors"]), 1)
        self.assertFalse(any("binding loop" in l for v in hits.values() for l in v))

    def test_benign_boot_messages_not_matched(self):
        benign = ["2026-10-29T10:00:00+00:00 DBPC kernel: NMI watchdog: Perf NMI watchdog permanently disabled",
                  "2026-10-29T10:00:00+00:00 DBPC kernel: thermal_sys: Registered thermal governor 'step_wise'"]
        hits = fl.categorise(benign)
        self.assertEqual(sum(len(v) for v in hits.values()), 0, hits)

    def test_browser_gpu_process_crash_matched(self):
        line = "2026-10-29T23:38:00+00:00 DBPC code[5000]: GPU process exited unexpectedly: exit_code=139"
        self.assertEqual(len(fl.categorise([line])["gpu and compositor"]), 1)

    def test_final_window(self):
        lines = ["2026-10-29T23:20:00+00:00 DBPC a: early",
                 "2026-10-29T23:31:00+00:00 DBPC a: inside",
                 "continuation without a timestamp",
                 "2026-10-29T23:40:00+00:00 DBPC a: last"]
        self.assertEqual(fl.final_window(lines, 10), lines[1:2] + lines[3:])
        self.assertEqual(fl.final_window(["no timestamps here"]), [])

    def test_final_window_anchored_to_boot_end(self):
        warnings = ["2026-10-29T10:00:00+00:00 DBPC a: morning warning",
                    "2026-10-29T23:35:00+00:00 DBPC a: late warning"]
        end = fl.last_time(["2026-10-29T23:40:00+00:00 DBPC b: final entry of the boot"])
        self.assertEqual(fl.final_window(warnings, 10, end=end), warnings[1:])
        self.assertEqual(fl.final_window(warnings[:1], 10, end=end), [])

    def test_next_boot_gap(self):
        boots = [{"index": -1, "first": dt.datetime(2026, 10, 29, 10), "last": dt.datetime(2026, 10, 29, 23, 40)},
                 {"index": 0, "first": dt.datetime(2026, 10, 29, 23, 43, 30), "last": dt.datetime(2026, 10, 30, 9)}]
        self.assertIn("0:03:30 after", fl.next_boot_gap(boots, -1))
        self.assertIsNone(fl.next_boot_gap(boots, 0))

    def test_kernel_visibility(self):
        self.assertTrue(fl.kernel_visible(self.LINES))
        user_only = ["2026-10-29T23:39:03+00:00 DBPC plasmashell[1200]: qml: binding loop detected"]
        self.assertFalse(fl.kernel_visible(user_only))
        self.assertIn("sudo python3 tools/collect_freeze_logs.py --boot -1", fl.NO_KERNEL_WARNING.format(boot=-1))

    POWER_OFF = "2026-10-29T23:50:00+00:00 DBPC systemd[1]: Reached target System Power Off."
    STOPPED = "2026-10-29T23:50:01+00:00 DBPC systemd-journald[300]: Journal stopped"
    STARTED = "2026-10-29T23:50:02+00:00 DBPC systemd-journald[900]: Journal started"

    def test_shutdown_status(self):
        self.assertEqual(fl.shutdown_status(self.LINES), "none")
        self.assertEqual(fl.shutdown_status(self.LINES + [self.POWER_OFF, self.STOPPED]), "confirmed")
        self.assertEqual(fl.shutdown_status(self.LINES + [self.STOPPED]), "journal-stopped-only")
        self.assertTrue(fl.clean_shutdown(self.LINES + [self.POWER_OFF]))
        self.assertFalse(fl.clean_shutdown(self.LINES + [self.STOPPED]))

    def test_late_restart_in_a_short_tail_is_not_a_clean_shutdown(self):
        # ChatGPT's reproduction on db-workspace #13: stop, restart, then a hang, all within five lines.
        lines = ["2026-10-29T15:00:00+00:00 DBPC systemd-journald[300]: Journal stopped",
                 "2026-10-29T15:00:01+00:00 DBPC systemd-journald[900]: Journal started",
                 "2026-10-29T15:00:05+00:00 DBPC kernel: watchdog: BUG: soft lockup - CPU#3 stuck for 22s!"]
        self.assertFalse(fl.clean_shutdown(lines))
        self.assertEqual(fl.shutdown_status(lines), "none")
        self.assertEqual(fl.shutdown_status(self.LINES + [self.POWER_OFF, self.STARTED]), "none")

    def test_shutdown_unknown_without_kernel_messages(self):
        user_only = ["2026-10-29T23:39:03+00:00 DBPC plasmashell[1200]: qml: binding loop detected", self.STOPPED]
        self.assertEqual(fl.shutdown_status(user_only), "unknown")

    def test_journal_restart_is_not_a_clean_shutdown(self):
        restart_then_hang = [
            "2026-10-29T15:00:00+00:00 DBPC systemd-journald[300]: Journal stopped",
            "2026-10-29T15:00:01+00:00 DBPC systemd-journald[900]: Journal started",
        ] + [f"2026-10-29T23:{m:02d}:00+00:00 DBPC app[1]: normal work" for m in range(30)]
        self.assertFalse(fl.clean_shutdown(restart_then_hang))

    def test_shutdown_marker_before_a_restart_does_not_count(self):
        lines = ["2026-10-29T15:00:00+00:00 DBPC systemd[1]: Reached target System Power Off.",
                 "2026-10-29T15:00:05+00:00 DBPC systemd-journald[900]: Journal started",
                 "2026-10-29T23:40:00+00:00 DBPC app[1]: normal work"]
        self.assertFalse(fl.clean_shutdown(lines))

    def test_masks_the_source_journals_names(self):
        raw = ["2026-10-29T10:00:00+00:00 OTHERPC systemd-logind[700]: New session 2 of user alicex.",
               "2026-10-29T10:00:01+00:00 OTHERPC kwin_wayland[900]: started for alicex on OTHERPC",
               "2026-10-29T10:00:02+00:00 OTHERPC systemd[1]: Started session for user root."]
        hosts, users = fl.journal_identities(raw)
        self.assertEqual((hosts, users), ({"OTHERPC"}, {"alicex"}))
        old = os.environ.get("SUDO_USER")
        os.environ["SUDO_USER"] = "localperson"  # make the local identity independent of who runs the tests
        try:
            masker = fl.make_masker(raw)
            out = [masker(l) for l in raw]
        finally:
            if old is None:
                os.environ.pop("SUDO_USER", None)
            else:
                os.environ["SUDO_USER"] = old
        self.assertTrue(all(" <host> " in l for l in out))
        self.assertFalse(any("OTHERPC" in l or "alicex" in l for l in out), out)
        self.assertIn("user root", out[2])

    def test_trim(self):
        lines = [str(i) for i in range(100)]
        out = fl.trim(lines, 10)
        self.assertEqual(out[:5], ["0", "1", "2", "3", "4"])
        self.assertEqual(out[-5:], ["95", "96", "97", "98", "99"])
        self.assertIn("90 lines omitted", out[5])

    def test_error_counts(self):
        text = "\n".join(json.dumps(e) for e in [
            {"SYSLOG_IDENTIFIER": "kernel"}, {"SYSLOG_IDENTIFIER": "kernel"}, {"_COMM": "kwin_wayland"}, "not json"])
        self.assertEqual(fl.error_counts(text).most_common(), [("kernel", 2), ("kwin_wayland", 1)])


if __name__ == "__main__":
    unittest.main()
