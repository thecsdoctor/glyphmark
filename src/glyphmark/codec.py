"""High level encode / extract API — the single source of truth for CLI and web."""

from __future__ import annotations

from dataclasses import dataclass, field

from . import frames
from .bitstreams import digits_to_bytes, to_symbols
from .schemes import (
    FAMILY_INSERT,
    FAMILY_SUBSTITUTE,
    SCHEMES,
    Scheme,
    get_scheme,
    select_positions,
)

MAX_PAYLOAD = 0xFFFF
PLACEMENTS = ("spread", "interleave", "suffix", "prefix")


class GlyphMarkError(Exception):
    exit_code = 1


class CapacityError(GlyphMarkError):
    exit_code = 5


class NoPayloadError(GlyphMarkError):
    exit_code = 3


@dataclass
class EncodeResult:
    text: str
    scheme_id: str
    payload_len: int
    bits_used: int
    units_used: int
    carrier_units: int
    capacity_bytes: int
    placement: str
    keyed: bool
    verified: bool = False
    cover_len: int = 0

    def to_dict(self) -> dict:
        return {
            "text": self.text,
            "scheme": self.scheme_id,
            "payload_len": self.payload_len,
            "bits_used": self.bits_used,
            "units_used": self.units_used,
            "carrier_units": self.carrier_units,
            "capacity_bytes": self.capacity_bytes,
            "utilization": round(self.units_used / max(1, self.carrier_units), 4),
            "placement": self.placement,
            "keyed": self.keyed,
            "verified": self.verified,
            "cover_len": self.cover_len,
        }


@dataclass
class DecodeResult:
    payload: bytes
    scheme_id: str
    keyed: bool
    bits_read: int
    units_used: int
    carrier_units: int
    attempts: list[dict] = field(default_factory=list)

    @property
    def text(self) -> str:
        return self.payload.decode("utf-8", errors="replace")

    def to_dict(self) -> dict:
        printable = self.payload.decode("utf-8", errors="strict") if _is_utf8(self.payload) else None
        return {
            "payload_text": printable,
            "payload_hex": self.payload.hex(),
            "payload_base64": _b64(self.payload),
            "payload_len": len(self.payload),
            "scheme": self.scheme_id,
            "keyed": self.keyed,
            "bits_read": self.bits_read,
            "units_used": self.units_used,
            "carrier_units": self.carrier_units,
            "attempts": self.attempts,
        }


def _is_utf8(data: bytes) -> bool:
    try:
        data.decode("utf-8")
    except UnicodeDecodeError:
        return False
    return True


def _b64(data: bytes) -> str:
    import base64

    return base64.b64encode(data).decode("ascii")


def _seed(key: str | None) -> str:
    return f"glyphmark/v1|{key}" if key else "glyphmark/v1|unkeyed"


# --------------------------------------------------------------------------- #
# Insertion family
# --------------------------------------------------------------------------- #

def _insert_positions(text: str, scheme: Scheme, count: int, placement: str) -> list[int]:
    """Return the carrier index each symbol should be glued after (>= 0 = after char i).

    Positions are non-decreasing in symbol order so that a left-to-right scan on
    the decode side reproduces the digit order.
    """
    if scheme.anchor_required:
        taken = scheme.symbol_to_digit
        anchors = [i for i, ch in enumerate(text) if ch not in taken]
        if not anchors:
            raise CapacityError("cover text has no anchor character to attach to")
    else:
        anchors = list(range(len(text)))
    n = len(anchors)
    out: list[int] = []
    for j in range(count):
        if placement == "interleave":
            out.append(anchors[min(j, n - 1)])
        elif placement == "spread":
            out.append(anchors[min(int((j + 1) * n / (count + 1)), n - 1)])
        elif placement == "prefix":
            out.append(-1)
        else:  # suffix
            out.append(n - 1)
    return out


def _apply_insertion(text: str, symbols: list[str], positions: list[int]) -> str:
    buckets: dict[int, list[str]] = {}
    for pos, sym in zip(positions, symbols, strict=True):
        buckets.setdefault(pos, []).append(sym)
    out: list[str] = []
    out.extend(buckets.pop(-1, []))
    for i, ch in enumerate(text):
        out.append(ch)
        out.extend(buckets.pop(i, []))
    for rest in buckets.values():  # defensive; normally empty
        out.extend(rest)
    return "".join(out)


def _extract_symbols(text: str, scheme: Scheme) -> list[int]:
    table = scheme.symbol_to_digit
    return [table[ch] for ch in text if ch in table]


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #

def encode(
    cover: str,
    payload: bytes,
    scheme_id: str,
    key: str | None = None,
    placement: str = "spread",
    verify: bool = True,
) -> EncodeResult:
    if not cover:
        raise CapacityError("cover text is empty — nothing to carry the mark")
    if placement not in PLACEMENTS:
        raise GlyphMarkError(f"placement must be one of {', '.join(PLACEMENTS)}")
    if len(payload) > MAX_PAYLOAD:
        raise CapacityError(
            f"payload is {len(payload)} bytes; the u16 length field caps it at {MAX_PAYLOAD}"
        )
    scheme = get_scheme(scheme_id)
    keyed = bool(key)
    header = frames.header_bytes(len(payload), scheme.index, keyed)

    if scheme.family == FAMILY_INSERT:
        result = _encode_insert(scheme, cover, payload, header, key, keyed, placement)
    elif scheme.family == FAMILY_SUBSTITUTE:
        result = _encode_substitute(scheme, cover, payload, header, key, keyed)
    else:  # pragma: no cover
        raise GlyphMarkError(f"unhandled family {scheme.family}")

    if verify:
        try:
            back = decode(result.text, key=key, scheme_id=scheme.id)
            result.verified = back.payload == payload
        except GlyphMarkError:
            result.verified = False
        if not result.verified:
            raise GlyphMarkError("internal error: round-trip self-check failed")
    return result


def _encode_insert(scheme, cover, payload, header, key, keyed, placement) -> EncodeResult:
    frame = header + payload + frames.crc32(header + payload)
    blob = frames.protect(frame, key, "F")
    digits = to_symbols(blob, scheme.bits_per_unit)
    symbols = [scheme.symbols[d] for d in digits]
    positions = _insert_positions(cover, scheme, len(symbols), placement)
    text = _apply_insertion(cover, symbols, positions)
    carrier = len(scheme.slots(cover))
    bits = len(digits) * scheme.bits_per_unit
    return EncodeResult(
        text=text, scheme_id=scheme.id, payload_len=len(payload), bits_used=bits,
        units_used=len(digits), carrier_units=carrier,
        capacity_bytes=scheme.capacity_payload_bytes(
            cover, frames.HEADER_SIZE * 8, frames.CRC_SIZE * 8
        ),
        placement=placement, keyed=keyed, cover_len=len(cover),
    )


def _encode_substitute(scheme, cover, payload, header, key, keyed) -> EncodeResult:
    carriers = scheme.slots(cover)
    total = len(carriers)
    if total == 0:
        raise CapacityError(
            f"cover text has no carrier character for scheme '{scheme.id}' "
            f"({scheme.carrier})"
        )
    seed = _seed(key)

    need_a = scheme.digits_for_bytes(frames.HEADER_PHASE_BYTES)
    need_b = scheme.digits_for_bytes(len(payload) + frames.CRC_SIZE)
    if need_a + need_b > total:
        raise CapacityError(
            f"'{scheme.id}' needs {need_a + need_b} carrier units "
            f"({(need_a + need_b) * scheme.bits_per_unit} bits) but this cover text offers "
            f"{total} ({scheme.carrier}). Use a longer cover or a denser channel."
        )

    # phase A: header + its own CRC, at keyed spread positions
    frame_a = header + frames.crc32(header)
    digits_a = to_symbols(frames.protect(frame_a, key, "A"), scheme.bits_per_unit)
    pos_a = select_positions(total, len(digits_a), seed)
    text = scheme.write_symbols(cover, [carriers[p] for p in pos_a], digits_a)

    # phase B: payload + CRC, at the remaining spread positions
    body = payload + frames.crc32(payload)
    digits_b = to_symbols(frames.apply_keystream(body, key if keyed else None, "B"),
                          scheme.bits_per_unit)
    pos_b = select_positions(total, len(digits_b), seed, exclude=set(pos_a))
    text = scheme.write_symbols(text, [carriers[p] for p in pos_b], digits_b)

    units = len(digits_a) + len(digits_b)
    return EncodeResult(
        text=text, scheme_id=scheme.id, payload_len=len(payload),
        bits_used=units * scheme.bits_per_unit, units_used=units, carrier_units=total,
        capacity_bytes=scheme.capacity_payload_bytes(
            cover, frames.HEADER_PHASE_BITS, frames.CRC_SIZE * 8
        ),
        placement="spread(keyed)", keyed=keyed, cover_len=len(cover),
    )


# --------------------------------------------------------------------------- #
# Decoding
# --------------------------------------------------------------------------- #

def decode(text: str, key: str | None = None, scheme_id: str = "auto") -> DecodeResult:
    if scheme_id != "auto":
        return _decode_with(text, get_scheme(scheme_id), key)
    attempts: list[dict] = []
    keyed_suspect = False
    key_needed: frames.KeyRequiredError | None = None
    for scheme in SCHEMES:
        try:
            result = _decode_with(text, scheme, key, auto=True)
            result.attempts = attempts
            return result
        except frames.KeyRequiredError as exc:
            key_needed = exc
            attempts.append({"scheme": scheme.id, "error": str(exc)})
        except (GlyphMarkError, frames.FrameError) as exc:
            if isinstance(exc, frames.ChecksumError):
                keyed_suspect = True
            attempts.append({"scheme": scheme.id, "error": str(exc)})
    if key_needed:
        raise key_needed
    if keyed_suspect:
        raise frames.ChecksumError()
    raise NoPayloadError(
        "no GlyphMark frame recovered. The text may be normalized/stripped, the payload may "
        "have been written with a different scheme, or --key is wrong."
    )


def _decode_with(text: str, scheme: Scheme, key: str | None, auto: bool = False) -> DecodeResult:
    if scheme.family == FAMILY_INSERT:
        return _decode_insert(text, scheme, key, auto)
    return _decode_substitute(text, scheme, key, auto)


def _frame_from(raw: bytes, key: str | None, label: str) -> tuple[dict, bytes]:
    """Parse ``HEADER||PAYLOAD||CRC32`` (single-phase insertion layout)."""
    last: Exception = frames.BadMagicError()
    for blob in frames.open_candidates(raw, key, label):
        try:
            info = frames.parse_header(blob)
            if info["keyed"] and not key:
                raise frames.KeyRequiredError(info["payload_len"])
            total = frames.HEADER_SIZE + info["payload_len"] + frames.CRC_SIZE
            if len(blob) < total:
                raise frames.ChecksumError()
            body = blob[: frames.HEADER_SIZE + info["payload_len"]]
            if not frames.check_crc(body, blob[frames.HEADER_SIZE + info["payload_len"]:]):
                raise frames.ChecksumError()
            return info, blob[frames.HEADER_SIZE: frames.HEADER_SIZE + info["payload_len"]]
        except frames.FrameError as exc:
            last = exc
    raise last


def _decode_insert(text: str, scheme: Scheme, key: str | None, auto: bool) -> DecodeResult:
    digits = _extract_symbols(text, scheme)
    carrier = len(scheme.slots(text))
    if not digits:
        raise NoPayloadError(f"scheme '{scheme.id}': no symbols present in this text")
    raw = digits_to_bytes(digits, scheme.bits_per_unit)
    if len(raw) < frames.HEADER_SIZE:
        raise NoPayloadError(
            f"scheme '{scheme.id}': {len(digits)} symbols found, shorter than a frame header"
        )
    info, payload = _frame_from(raw, key, "F")
    _check_index(info, scheme, auto)
    return DecodeResult(
        payload=payload, scheme_id=scheme.id, keyed=key is not None,
        bits_read=len(digits) * scheme.bits_per_unit, units_used=len(digits),
        carrier_units=carrier,
    )


def _decode_substitute(text: str, scheme: Scheme, key: str | None, auto: bool) -> DecodeResult:
    carriers = scheme.slots(text)
    total = len(carriers)
    need_a = scheme.digits_for_bytes(frames.HEADER_PHASE_BYTES)
    if total < need_a:
        raise NoPayloadError(
            f"scheme '{scheme.id}': only {total} carrier characters — too few to hold a "
            f"{need_a}-unit header"
        )
    seed = _seed(key)

    pos_a = select_positions(total, need_a, seed)
    raw_a = digits_to_bytes(scheme.read_symbols(text, [carriers[p] for p in pos_a]),
                            scheme.bits_per_unit)
    info, _ = _parse_phase_a(raw_a, key)
    _check_index(info, scheme, auto)

    need_b = scheme.digits_for_bytes(info["payload_len"] + frames.CRC_SIZE)
    pos_b = select_positions(total, need_b, seed, exclude=set(pos_a))
    raw_b = digits_to_bytes(scheme.read_symbols(text, [carriers[p] for p in pos_b]),
                            scheme.bits_per_unit)
    stream = frames.apply_keystream(raw_b, key, "B") if key else raw_b
    payload = stream[:info["payload_len"]]
    if not frames.check_crc(payload, stream[info["payload_len"]:]):
        raise frames.ChecksumError()
    return DecodeResult(
        payload=payload, scheme_id=scheme.id, keyed=key is not None,
        bits_read=(need_a + need_b) * scheme.bits_per_unit,
        units_used=need_a + len(pos_b), carrier_units=total,
    )


def _parse_phase_a(raw: bytes, key: str | None) -> tuple[dict, bytes]:
    last: Exception = frames.BadMagicError()
    for blob in frames.open_candidates(raw, key, "A"):
        try:
            info = frames.parse_header(blob)
            if info["keyed"] and not key:
                raise frames.KeyRequiredError(info["payload_len"])
            if not frames.check_crc(blob[:frames.HEADER_SIZE], blob[frames.HEADER_SIZE:]):
                raise frames.ChecksumError()
            return info, blob
        except frames.FrameError as exc:
            last = exc
    raise last


def _check_index(info: dict, scheme: Scheme, auto: bool) -> None:
    if auto and info["scheme_index"] != scheme.index:
        raise frames.SchemeMismatchError(scheme.id, info["scheme_index"])


def roundtrip_ok(scheme_id: str, key: str | None = None) -> dict:
    """Self-test a channel with an auto-sized carrier — used by ``glyphmark verify``."""
    scheme = get_scheme(scheme_id)
    payload = b"GLYPHMARK-SELFTEST-0123456789"
    cover = sample_carrier(scheme, len(payload))
    try:
        enc = encode(cover, payload, scheme_id, key=key)
        dec = decode(enc.text, key=key, scheme_id=scheme_id)
        ok = dec.payload == payload
        return {
            "scheme": scheme_id, "ok": ok, "bits_used": enc.bits_used,
            "carrier_units": enc.carrier_units, "capacity_bytes": enc.capacity_bytes,
            "cover_len": len(cover), "error": None if ok else "payload mismatch",
        }
    except (GlyphMarkError, frames.FrameError) as exc:
        return {
            "scheme": scheme_id, "ok": False, "bits_used": 0, "carrier_units": 0,
            "capacity_bytes": 0, "cover_len": len(cover),
            "error": f"{type(exc).__name__}: {exc}",
        }


_SENTENCE = ("GlyphMark self test the quick brown fox jumps over the lazy dog while "
             "reviewing unicode provenance channels 0123456789 ")
_PUNCT_SENTENCE = "a-b.c'd*e~f, g-h.i'j*k~l, m-n.o'p*q~r, "


def sample_carrier(scheme: Scheme, payload_len: int, max_reps: int = 400) -> str:
    """Build a cover text with enough carrier units for ``payload_len`` bytes."""
    base = _PUNCT_SENTENCE if scheme.id == "punct" else _SENTENCE
    header_bits = (frames.HEADER_PHASE_BITS if scheme.family == FAMILY_SUBSTITUTE
                   else frames.HEADER_SIZE * 8)
    text = base * 4
    for _ in range(max_reps):
        if scheme.capacity_payload_bytes(text, header_bits, frames.CRC_SIZE * 8) >= payload_len:
            return text
        text += base
    return text  # last resort; encode() will raise CapacityError with a clear message

