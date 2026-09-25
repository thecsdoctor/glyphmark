# SPDX-License-Identifier: MIT
"""Bit packing helpers.

All watermark symbols use radixes that are exact powers of two, so a symbol is a
fixed-width bit group and no lossy big-integer base conversion is required.
"""

from __future__ import annotations


def pack_bits(bits: list[int]) -> bytes:
    """Pack a list of 0/1 ints (MSB first) into bytes, zero-padding the tail."""
    out = bytearray()
    for i in range(0, len(bits), 8):
        byte = 0
        for bit in bits[i : i + 8]:
            byte = (byte << 1) | bit
        out.append(byte)
    return bytes(out)


def unpack_bytes(data: bytes) -> list[int]:
    """Expand bytes into a MSB-first bit list."""
    bits: list[int] = []
    for byte in data:
        for shift in range(7, -1, -1):
            bits.append((byte >> shift) & 1)
    return bits


def to_symbols(data: bytes, bits_per_symbol: int) -> list[int]:
    """Convert payload bytes into fixed-width digit values in ``[0, 2**bps)``."""
    bits = unpack_bytes(data)
    pad = (-len(bits)) % bits_per_symbol
    bits += [0] * pad
    out = []
    for i in range(0, len(bits), bits_per_symbol):
        value = 0
        for bit in bits[i : i + bits_per_symbol]:
            value = (value << 1) | bit
        out.append(value)
    return out


def digits_to_bytes(digits: list[int], bits_per_symbol: int) -> bytes:
    """Inverse of :func:`to_symbols`; trailing partial groups are dropped."""
    bits: list[int] = []
    for digit in digits:
        for shift in range(bits_per_symbol - 1, -1, -1):
            bits.append((digit >> shift) & 1)
    usable = (len(bits) // 8) * 8
    return pack_bits(bits[:usable])
