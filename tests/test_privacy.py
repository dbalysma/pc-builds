import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
from privacy import mask  # noqa: E402


class MaskTests(unittest.TestCase):
    def m(self, text):
        return mask(text, user="dylanx", host="DBPC")

    def test_user_and_host(self):
        self.assertEqual(self.m("dylanx@DBPC:~/Documents$"), "<user>@<host>:~/Documents$")

    def test_home_paths(self):
        self.assertEqual(self.m("/home/someone/x.py"), "/home/<user>/x.py")
        self.assertEqual(self.m(r"C:\Users\Someone\x"), r"C:\Users\<user>\x")

    def test_network_identifiers(self):
        out = self.m("eth0 aa:bb:cc:dd:ee:ff 192.168.1.20 fe80::1ff:fe23:4567:890a")
        self.assertNotIn("aa:bb", out)
        self.assertNotIn("192.168", out)
        self.assertNotIn("fe80", out)

    def test_compressed_and_mapped_ipv6_masked_whole(self):
        for addr in ("::ffff:c000:280", "2001:db8::abcd:1234", "::ffff:192.0.2.128", "fe80::1%enp5s0",
                     "2001:0db8:0000:0000:0000:ff00:0042:8329"):
            with self.subTest(addr=addr):
                self.assertEqual(self.m(f"from {addr}, ok"), "from <ip6>, ok")
        self.assertEqual(self.m("[fe80::1ff:fe23:4567:890a]:22"), "[<ip6>]:22")
        self.assertEqual(self.m("fe80::1: link"), "<ip6>: link")

    def test_ipv6_ending_like_a_mac_is_masked_whole(self):
        self.assertEqual(self.m("peer 2001:db8:aa:bb:cc:dd:ee:ff up"), "peer <ip6> up")
        self.assertEqual(self.m("dev aa:bb:cc:dd:ee:ff up"), "dev <mac> up")

    # Every address type in every common context: start/end of text, brackets, quotes, a label such as
    # "addr:", and sentence punctuation after it. The same grid runs against the public audit.
    ADDRESSES = ["10.1.2.3", "192.168.1.20", "2001:db8::1", "2001:db8::abcd:1234", "::ffff:c000:280",
                 "::ffff:192.0.2.128", "fe80::1ff:fe23:4567:890a", "2001:db8:aa:bb:cc:dd:ee:ff",
                 "2001:0db8:0000:0000:0000:ff00:0042:8329", "aa:bb:cc:dd:ee:ff",
                 "2001:db8:1:2:3:4:5::", "::2:3:4:5:6:7:8"]
    PREFIXES = ["", "via ", "(", "[", "=", "addr:", '"', "'", "`", "<"]
    SUFFIXES = ["", " up", ".", ",", ";", ":", ")", "]", "!", "?", '"', "'", "`", "/64", ">"]

    def test_addresses_masked_in_every_context(self):
        for addr in self.ADDRESSES:
            for pre in self.PREFIXES:
                for suf in self.SUFFIXES:
                    text = f"{pre}{addr}{suf}"
                    with self.subTest(text=text):
                        self.assertNotIn(addr, self.m(text))

    def test_random_ipv6_shapes_found_and_masked(self):
        # Seeded, so the test is deterministic. Zero runs of every length at every position exercise
        # every compression shape; exploded, IPv4-mapped and zoned forms are mixed in.
        import ipaddress
        import random
        from privacy import find_ipv6
        rng = random.Random(20261030)
        for i in range(300):
            groups = [rng.randrange(1, 0x10000) for _ in range(8)]
            start, length = rng.randrange(8), rng.randrange(0, 8)
            for j in range(start, min(8, start + length)):
                groups[j] = 0
            addr = ipaddress.IPv6Address(":".join(f"{g:x}" for g in groups))
            form = [str(addr), addr.exploded, f"::ffff:{rng.randrange(1, 224)}.0.2.{rng.randrange(1, 255)}",
                    f"{addr}%eth{i % 3}"][i % 4]
            if form.split("%")[0] in ("::", "::1"):
                continue
            pre, suf = rng.choice(self.PREFIXES), rng.choice(self.SUFFIXES)
            text = f"{pre}{form}{suf}"
            with self.subTest(text=text):
                self.assertNotIn(form.split("%")[0], self.m(text))
                self.assertTrue(find_ipv6(text), text)

    def test_non_addresses_kept(self):
        line = "21:14:03 PCI:0000:01:00 0000:01:00.0 std::vector Foo::Bar ::1 ::"
        self.assertEqual(self.m(line), line)

    def test_loopback_kept(self):
        self.assertIn("127.0.0.1", self.m("listening on 127.0.0.1"))

    def test_clock_times_and_versions_kept(self):
        line = "2026-10-29T21:14:03+0000 kernel 6.8.0-45 driver 570.86.16"
        self.assertEqual(self.m(line), line)

    def test_urls_emails_uuids_serials(self):
        out = self.m("https://example.com/a?b=c me@example.com "
                     "123e4567-e89b-12d3-a456-426614174000 GPU-1a2b3c4d-0000 Serial Number: XYZ123")
        for leaked in ("example.com", "123e4567", "1a2b3c4d", "XYZ123"):
            self.assertNotIn(leaked, out)

    def test_sudo_masks_the_real_user(self):
        import os
        import privacy
        old = os.environ.get("SUDO_USER")
        os.environ["SUDO_USER"] = "realperson"
        try:
            self.assertEqual(privacy._identity()[0], "realperson")
            self.assertIn("<user>", privacy.mask("Session 2 of user realperson", host="zzz"))
        finally:
            if old is None:
                os.environ.pop("SUDO_USER", None)
            else:
                os.environ["SUDO_USER"] = old

    def test_short_names_not_replaced(self):
        self.assertEqual(mask("an id", user="an", host="id"), "an id")


if __name__ == "__main__":
    unittest.main()
