# SPDX-License-Identifier: MIT
"""Frame layout, checksums and keyed obfuscation.

Wire format (all big-endian)::

    HEADER  6 bytes : magic 0x57 | version | scheme_index | flags | payload_len(u16)
    PAYLOAD n bytes
    CRC32   4 bytes : zlib.crc32 over HEADER || PAYLOAD

Insertion channels carry ``HEADER || PAYLOAD || CRC32`` as one unit (keystream
label ``F``).  Substitution channels cannot know the payload length before
decoding, so they are split in two:

    phase A : HEADER || CRC32(HEADER)                 -> 80 bits, keystream ``A``
    phase B : PAYLOAD || CRC32(PAYLOAD)               -> (n+4)*8 bits, keystream ``B``

``--key`` applies a SHA-256 derived keystream (CTR-style) over the framed bytes,
leaving only the magic and version bytes in clear text.  That is *obfuscation, not
encryption*: it stops casual reading and binds the mark to a secret, but anyone who
recovers the key reads the payload.  Keeping those two prefix bytes clear lets a
defender prove that a keyed frame exists (and that it needs a key), while a wrong
key fails loudly on the CRC instead of silently yielding garbage.
"""

from __future__ import annotations

import hashlib
import struct
import zlib

MAGIC = 0x57  # 'W'
VERSION = 1
FLAG_KEYED = 0x01

HEADER_FMT = ">BBBBH"
HEADER_SIZE = struct.calcsize(HEADER_FMT)  # 6
CRC_SIZE = 4
HEADER_PHASE_BYTES = HEADER_SIZE + CRC_SIZE  # 10
HEADER_PHASE_BITS = HEADER_PHASE_BYTES * 8  # 80
# magic + version stay in clear text so a scanner can prove a frame is present
# (and that it is keyed) without the secret.
CLEAR_PREFIX = 2


class GlyphMarkFrameError(Exception):
    exit_code = 4


class FrameError(GlyphMarkFrameError):
    """Raised when a frame cannot be parsed."""


class BadMagicError(FrameError):
    def __init__(self) -> None:
        super().__init__("no GlyphMark frame at this position (bad magic byte)")


class ChecksumError(FrameError):
    def __init__(self) -> None:
        super().__init__("frame CRC mismatch — payload corrupted, or wrong --key")


class SchemeMismatchError(FrameError):
    def __init__(self, expected: str, found: int) -> None:
        super().__init__(f"frame was written with scheme index {found}, not '{expected}'")


class KeyRequiredError(FrameError):
    exit_code = 4

    def __init__(self, payload_len: int = 0) -> None:
        # The length field itself is key-obfuscated, so it is deliberately not quoted here.
        super().__init__(
            "a keyed GlyphMark frame is present but no key was supplied — "
            "pass --key / the 'key' field"
        )
        self.payload_len = payload_len


def header_bytes(payload_len: int, scheme_index: int, keyed: bool) -> bytes:
    flags = FLAG_KEYED if keyed else 0x00
    return struct.pack(HEADER_FMT, MAGIC, VERSION, scheme_index, flags, payload_len)


def parse_header(raw: bytes) -> dict:
    if len(raw) < HEADER_SIZE:
        raise FrameError("truncated header")
    magic, version, scheme_index, flags, payload_len = struct.unpack(HEADER_FMT, raw[:HEADER_SIZE])
    if magic != MAGIC:
        raise BadMagicError()
    if version != VERSION:
        raise FrameError(f"unsupported frame version {version}")
    return {
        "version": version,
        "scheme_index": scheme_index,
        "keyed": bool(flags & FLAG_KEYED),
        "payload_len": payload_len,
    }


def crc32(data: bytes) -> bytes:
    return struct.pack(">I", zlib.crc32(data) & 0xFFFFFFFF)


def check_crc(data: bytes, trailer: bytes) -> bool:
    if len(trailer) < CRC_SIZE:
        return False
    return (zlib.crc32(data) & 0xFFFFFFFF) == struct.unpack(">I", trailer[:CRC_SIZE])[0]


# --------------------------------------------------------------------------- #
# Keyed keystream
# --------------------------------------------------------------------------- #


def root_key(secret: str) -> bytes:
    return hashlib.sha256(b"glyphmark/v1|" + secret.encode("utf-8")).digest()


def _phase_key(secret: str, label: str) -> bytes:
    return hashlib.sha256(root_key(secret) + b"|" + label.encode("ascii")).digest()


def keystream(secret: str | None, label: str, length: int) -> bytes:
    """Deterministic byte stream from a secret (SHA-256 in counter mode)."""
    if secret is None or length <= 0:
        return b"\x00" * length
    key = _phase_key(secret, label)
    out = bytearray()
    counter = 0
    while len(out) < length:
        out += hashlib.sha256(key + struct.pack(">I", counter)).digest()
        counter += 1
    return bytes(out[:length])


def apply_keystream(data: bytes, secret: str | None, label: str) -> bytes:
    stream = keystream(secret, label, len(data))
    return bytes(a ^ b for a, b in zip(data, stream, strict=True))


def protect(data: bytes, secret: str | None, label: str) -> bytes:
    """Key-obfuscate a framed unit while leaving the magic/version bytes in clear."""
    if not secret:
        return data
    head, body = data[:CLEAR_PREFIX], data[CLEAR_PREFIX:]
    return head + apply_keystream(body, secret, label)


def open_candidates(data: bytes, secret: str | None, label: str) -> list[bytes]:
    """Blobs to try when decoding: keyed reconstruction first (if a key exists), then clear."""
    out: list[bytes] = []
    if secret:
        head, body = data[:CLEAR_PREFIX], data[CLEAR_PREFIX:]
        out.append(head + apply_keystream(body, secret, label))
    out.append(data)
    return out
