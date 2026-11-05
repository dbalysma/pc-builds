import struct
import sys
import tempfile
import unittest
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import audit_public as ap  # noqa: E402


def png(extra_chunks=()):
    def chunk(ctype, data):
        return struct.pack(">I", len(data)) + ctype + data + struct.pack(">I", zlib.crc32(ctype + data))
    ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    body = chunk(b"IHDR", ihdr)
    for ctype, data in extra_chunks:
        body += chunk(ctype, data)
    body += chunk(b"IDAT", zlib.compress(b"\x00\x00\x00\x00")) + chunk(b"IEND", b"")
    return b"\x89PNG\r\n\x1a\n" + body


def jpeg(segments=()):
    out = b"\xff\xd8"
    for marker, payload in segments:
        out += bytes([0xFF, marker]) + struct.pack(">H", len(payload) + 2) + payload
    return out + b"\xff\xda\x00\x02" + b"\x00" * 8 + b"\xff\xd9"


class AuditTests(unittest.TestCase):
    def audit_text(self, text, name="notes.md"):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / name
            p.write_text(text)
            return ap.audit_file(p, name)

    def test_clean_text_passes(self):
        clean = ("# Y70 workstation\nRyzen 7 9700X, 32 GB DDR5-7200, M2 2TB NVMe, driver 570.86.16, "
                 "vBIOS 98.03.40.00.21, at 21:14:03 on 2026-10-29. Run: python3 tools/x.py \"$1\".\n")
        self.assertEqual(self.audit_text(clean), [])

    def test_each_rule_fires(self):
        cases = {
            "price or amount": ["Total £199.99", "about 250 GBP", "$1200", "$9.99"],
            "e-mail address": ["contact me@example.com"],
            "UK phone number": ["call 07700 900123", "+44 7700 900123", "Call 020 7946 0958 or +44 20 7946 0958",
                                "+44 (0)20 7946 0958", "(020) 7946 0958", "01632 960 123", "0113 496 0000",
                                "0800 123 4567", "+447700900123", "07700-900-123"],
            "UK postcode": ["E3 4AB", "SW1A 1AA"],
            "order, tracking or invoice number": ["Order #ABC12345", "tracking number: 1Z999AA10123456784"],
            "serial number": ["Serial Number: ABC123"],
            "UUID": ["123e4567-e89b-12d3-a456-426614174000", "GPU-1a2b3c4d-aaaa"],
            "MAC address": ["aa:bb:cc:dd:ee:ff"],
            "IP address": ["host at 192.168.1.20"],
            "IPv6 address": ["from 2001:db8::abcd:1234", "mapped ::ffff:c000:280"],
            "home-directory path": ["/home/dylan/x", r"C:\Users\Dylan\x"],
            "AI session link": ["https://claude.ai/code/session_abc", "https://chatgpt.com/c/abc"],
            "private evidence file": ["> PRIVATE EVIDENCE: review before sharing. Never commit"],
        }
        for rule, samples in cases.items():
            for sample in samples:
                with self.subTest(rule=rule, sample=sample):
                    problems = self.audit_text(sample + "\n")
                    self.assertTrue(any(rule in p for p in problems), problems)

    def test_addresses_flagged_in_every_context(self):
        from test_privacy import MaskTests
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "notes.md"
            for addr in MaskTests.ADDRESSES:
                for pre in MaskTests.PREFIXES:
                    for suf in MaskTests.SUFFIXES:
                        text = f"The remote endpoint was {pre}{addr}{suf}"
                        path.write_text(text + "\n")
                        with self.subTest(text=text):
                            self.assertTrue(ap.audit_file(path, "notes.md"), text)

    def test_phone_lookalikes_pass(self):
        for text in ("2026-10-30 21:14:03", "driver 570.86.16", "0 1 2 3 4 5 6 7 8 9", "000 000 0000",
                     "hash 01234567890abcdef", "16303 MiB", "boot 0 at 0:03:30", "seed 42, 284 videos, 1013 s"):
            with self.subTest(text=text):
                self.assertEqual(ap.uk_phone_numbers(text), [])

    def test_masked_placeholders_pass(self):
        self.assertEqual(self.audit_text("/home/<user>/x Serial Number: <serial> 127.0.0.1 0.0.0.0\n"), [])

    def test_blocked_and_unknown_types(self):
        with tempfile.TemporaryDirectory() as d:
            for name in ("clip.mov", "raw.log", "thing.bin"):
                (Path(d) / name).write_bytes(b"x")
            self.assertIn("not allowed", ap.audit_file(Path(d) / "clip.mov", "clip.mov")[0])
            self.assertIn("not allowed", ap.audit_file(Path(d) / "raw.log", "raw.log")[0])
            self.assertIn("unrecognised", ap.audit_file(Path(d) / "thing.bin", "thing.bin")[0])

    def test_size_limit(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "big.csv"
            p.write_bytes(b"a\n" * (ap.MAX_BYTES // 2 + 1))
            self.assertTrue(any("5 MB" in x for x in ap.audit_file(p, "big.csv")))

    def test_images(self):
        self.assertEqual(ap.png_metadata(png()), [])
        self.assertEqual(ap.png_metadata(png([(b"tEXt", b"Comment\x00hi")])), ["PNG tEXt chunk"])
        self.assertEqual(ap.png_metadata(png([(b"eXIf", b"MM\x00*")])), ["PNG eXIf chunk"])
        self.assertEqual(ap.jpeg_metadata(jpeg([(0xE0, b"JFIF\x00\x01\x01")])), [])
        self.assertEqual(ap.jpeg_metadata(jpeg([(0xE1, b"Exif\x00\x00MM")])), ["EXIF (APP1)"])
        self.assertEqual(ap.jpeg_metadata(jpeg([(0xE1, b"http://ns.adobe.com/xap/1.0/\x00<x/>")])), ["XMP"])
        self.assertEqual(ap.jpeg_metadata(jpeg([(0xFE, b"hello")])), ["JPEG comment"])

    def test_image_files(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "ok.png").write_bytes(png())
            (Path(d) / "gps.jpg").write_bytes(jpeg([(0xE1, b"Exif\x00\x00MM")]))
            self.assertEqual(ap.audit_file(Path(d) / "ok.png", "ok.png"), [])
            self.assertIn("EXIF", ap.audit_file(Path(d) / "gps.jpg", "gps.jpg")[0])

    def test_symlink_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "t.md").write_text("x")
            (Path(d) / "l.md").symlink_to(Path(d) / "t.md")
            self.assertIn("symlinks", ap.audit_file(Path(d) / "l.md", "l.md")[0])


if __name__ == "__main__":
    unittest.main()
