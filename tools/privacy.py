"""Masking helpers shared by the collectors.

The collectors output allowlisted fields only. Masking is a second line of defence for
free-text values (model names, log lines). It is not a substitute for the allowlist.
"""

from __future__ import annotations

import getpass
import ipaddress
import os
import re
import socket

MAC = re.compile(r"\b(?:[0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}\b")
# Boundaries: an address may be followed by sentence punctuation (a trailing "." is allowed unless a digit
# follows it, as in a longer version string), and preceded by a label such as "addr:".
IPV4 = re.compile(r"(?<![\d.])(?:\d{1,3}\.){3}\d{1,3}(?!\d|\.\d)")
# IPv6: rather than describe every valid shape in a pattern (full, compressed anywhere, IPv4-mapped,
# zoned), take each maximal run of hex digits, colons and dots that holds at least two colons, and let
# the ipaddress module decide. Clock times (21:14:03), PCI addresses (0000:01:00.0), MAC addresses and
# C++ names (Foo::a::b, blocked by the "::" lookbehind) are not valid addresses and are left alone.
IPV6_TOKEN = re.compile(
    r"(?<![\w.%])(?<!::)[0-9A-Fa-f:.]*:[0-9A-Fa-f:.]*:[0-9A-Fa-f:.]*(?:%[\w-]+(?:\.[\w-]+)*)?(?!\w)"
)
IPV6_KEEP = {"::", "::1"}  # unspecified and loopback addresses identify nobody


def _ipv6_prefix(token: str) -> str | None:
    """The longest prefix of token that is a valid IPv6 address (zone allowed), trimming trailing
    sentence punctuation ('.' or ':') one character at a time, so an address that itself ends in
    '::' keeps it ('1:2:3:4:5:6:7::' followed by ':' or '.'). None if there is no such prefix."""
    candidate = token
    while candidate:
        address = candidate.split("%", 1)[0]
        if address.count(":") >= 2:
            try:
                ipaddress.IPv6Address(address)
                return candidate
            except ValueError:
                pass
        if candidate[-1] not in ".:":
            return None
        candidate = candidate[:-1]
    return None


def find_ipv6(text: str) -> list[str]:
    """Real IPv6 addresses in text, other than :: and ::1."""
    found = []
    for m in IPV6_TOKEN.finditer(text or ""):
        addr = _ipv6_prefix(m.group(0))
        if addr and addr.split("%", 1)[0] not in IPV6_KEEP:
            found.append(addr)
    return found


def _mask_ipv6(m: re.Match) -> str:
    token = m.group(0)
    addr = _ipv6_prefix(token)
    if not addr or addr.split("%", 1)[0] in IPV6_KEEP:
        return token
    return "<ip6>" + token[len(addr):]


EMAIL = re.compile(r"\b[\w.+-]+@[\w-]+(?:\.[\w-]+)+\b")
URL = re.compile(r"\b(?:https?|wss?|file)://\S+", re.IGNORECASE)
UUID = re.compile(r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b")
GPU_UUID = re.compile(r"\bGPU-[0-9a-fA-F-]{8,}\b")
HOME_LINUX = re.compile(r"/home/[^/\s:'\"]+")
HOME_WINDOWS = re.compile(r"[A-Za-z]:\\Users\\[^\\\s:'\"]+", re.IGNORECASE)
SERIAL_FIELD = re.compile(r"(serial\s*(?:number|no\.?)?\s*[:=]\s*)\S+", re.IGNORECASE)


def _identity() -> tuple[str, str]:
    """The real user's name, even under sudo (where getuser() would return root), and the hostname."""
    user = os.environ.get("SUDO_USER", "")
    if not user:
        try:
            user = getpass.getuser()
        except Exception:  # pragma: no cover - depends on the environment
            user = os.environ.get("USER", "")
    host = socket.gethostname() or ""
    return user, host


def mask(text: str, user: str | None = None, host: str | None = None) -> str:
    """Return text with personal and network identifiers replaced by placeholders."""
    if not text:
        return text
    if user is None or host is None:
        default_user, default_host = _identity()
        user = default_user if user is None else user
        host = default_host if host is None else host
    out = URL.sub("<url>", text)
    out = EMAIL.sub("<email>", out)
    out = HOME_LINUX.sub("/home/<user>", out)
    out = HOME_WINDOWS.sub(r"C:\\Users\\<user>", out)
    out = GPU_UUID.sub("GPU-<uuid>", out)
    out = UUID.sub("<uuid>", out)
    # IPv6 first: an address ending in six two-digit groups (2001:db8:aa:bb:cc:dd:ee:ff) would
    # otherwise lose its tail to the MAC rule and leave the prefix behind; and before IPv4, so
    # IPv4-mapped addresses are masked whole. A bare MAC is not a valid IPv6 address, so the MAC
    # rule still catches it.
    out = IPV6_TOKEN.sub(_mask_ipv6, out)
    out = MAC.sub("<mac>", out)
    out = IPV4.sub(lambda m: m.group(0) if m.group(0) in ("127.0.0.1", "0.0.0.0") else "<ip>", out)
    out = SERIAL_FIELD.sub(r"\1<serial>", out)
    # Names last, so a hostname inside an already-masked token is not touched twice.
    for value, placeholder in ((host, "<host>"), (user, "<user>")):
        if value and len(value) >= 3:
            out = re.sub(rf"(?<![\w-]){re.escape(value)}(?![\w-])", placeholder, out)
    return out


PRIVATE_BANNER = "PRIVATE EVIDENCE: review before sharing. Never commit this file to db-pc-builds."
