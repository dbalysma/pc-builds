"""Run both collectors for real on a Linux machine (the CI runner is Ubuntu) and check that
their output contains no hostname, username or network/device identifiers."""

import contextlib
import getpass
import io
import json
import platform
import re
import shutil
import socket
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import audit_public  # noqa: E402
import collect_freeze_logs  # noqa: E402
import collect_inventory  # noqa: E402

LEAK_RULES = {name for name, _ in audit_public.RULES} - {"private evidence file", "price or amount",
                                                          "UK postcode", "order, tracking or invoice number"}


def leaks(text: str) -> list[str]:
    found = [name for name, pattern in audit_public.RULES if name in LEAK_RULES and pattern.search(text)]
    for value in (socket.gethostname(), getpass.getuser()):
        if value and len(value) >= 3 and re.search(rf"(?<![\w-]){re.escape(value)}(?![\w-])", text):
            found.append(f"identity value {value!r}")
    return found


@unittest.skipUnless(platform.system() == "Linux", "Linux only")
class InventoryIntegration(unittest.TestCase):
    def test_runs_and_leaks_nothing(self):
        with tempfile.TemporaryDirectory() as d, contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(collect_inventory.main(["--out", d]), 0)
            files = sorted(Path(d).iterdir())
            self.assertEqual([f.suffix for f in files], [".json", ".md"])
            report = json.loads(files[0].read_text())
            for section in ("cpu", "board", "gpu", "storage", "os", "displays", "memory_pressure"):
                self.assertIn(section, report)
            for f in files:
                self.assertEqual(leaks(f.read_text()), [], f.name)


@unittest.skipUnless(platform.system() == "Linux" and shutil.which("journalctl"), "needs journalctl")
class FreezeLogIntegration(unittest.TestCase):
    def test_list_and_extract_current_boot(self):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            self.assertEqual(collect_freeze_logs.main(["--list"]), 0)
        self.assertIn("index | first entry", buf.getvalue())
        with tempfile.TemporaryDirectory() as d, contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(collect_freeze_logs.main(["--boot", "0", "--out", d]), 0)
            text = next(Path(d).iterdir()).read_text()
            self.assertTrue(text.startswith("> PRIVATE EVIDENCE") or "No journal entries" in text)
            self.assertEqual(leaks(text), [])


if __name__ == "__main__":
    unittest.main()
