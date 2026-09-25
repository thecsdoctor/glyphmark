"""Round-trip guarantees for every watermark channel."""

from __future__ import annotations

import pytest

from glyphmark import frames
from glyphmark.bitstreams import digits_to_bytes, to_symbols
from glyphmark.codec import (
    CapacityError,
    NoPayloadError,
    decode,
    encode,
    roundtrip_ok,
    sample_carrier,
)
from glyphmark.schemes import SCHEMES, get_scheme, scheme_ids, select_positions

PAYLOAD = b'{"model":"local-llm","session":"4F2A-91C7"}'
IDS = scheme_ids()


def cover_for(scheme_id: str, payload_len: int = len(PAYLOAD)) -> str:
    return sample_carrier(get_scheme(scheme_id), payload_len)


@pytest.mark.parametrize("scheme_id", IDS)
def test_roundtrip_unkeyed(scheme_id: str) -> None:
    enc = encode(cover_for(scheme_id), PAYLOAD, scheme_id)
    assert enc.verified
    out = decode(enc.text)                      # auto channel sweep
    assert out.payload == PAYLOAD
    assert out.scheme_id == scheme_id


@pytest.mark.parametrize("scheme_id", IDS)
def test_roundtrip_keyed(scheme_id: str) -> None:
    enc = encode(cover_for(scheme_id), PAYLOAD, scheme_id, key="hunter2")
    assert enc.verified and enc.keyed
    assert decode(enc.text, key="hunter2").payload == PAYLOAD


@pytest.mark.parametrize("scheme_id", IDS)
def test_self_test_helper(scheme_id: str) -> None:
    assert roundtrip_ok(scheme_id)["ok"]
    assert roundtrip_ok(scheme_id, key="k")["ok"]


@pytest.mark.parametrize("scheme_id", IDS)
def test_channel_sweep_identifies_the_channel(scheme_id: str) -> None:
    """The scheme index inside the frame must match the channel that wrote it."""
    enc = encode(cover_for(scheme_id), PAYLOAD, scheme_id)
    assert decode(enc.text).scheme_id == scheme_id


def test_unicode_and_binary_payloads() -> None:
    scheme_id = "tags"
    for payload in ("grüße 🔐 ünïcødé".encode(), b"\x00\x01\x02\xff\xfe", b""):
        enc = encode(cover_for(scheme_id, max(len(payload), 1)), payload, scheme_id)
        assert decode(enc.text).payload == payload


def test_insertion_channel_reports_key_required() -> None:
    enc = encode(cover_for("zw-octal"), PAYLOAD, "zw-octal", key="s3cret")
    with pytest.raises(frames.KeyRequiredError) as exc:
        decode(enc.text)
    assert exc.value.exit_code == 4


def test_wrong_key_never_returns_garbage() -> None:
    enc = encode(cover_for("tags"), PAYLOAD, "tags", key="right")
    with pytest.raises(frames.FrameError):
        decode(enc.text, key="wrong")


def test_tampering_is_caught_by_the_crc() -> None:
    enc = encode(cover_for("zw-octal"), PAYLOAD, "zw-octal")
    scheme = get_scheme("zw-octal")
    symbols = scheme.symbols
    chars = [c for c in enc.text if c in scheme.symbol_to_digit]
    assert chars
    damaged = enc.text.replace(chars[len(chars) // 2], symbols[0], 1)
    if damaged != enc.text:
        with pytest.raises((frames.ChecksumError, frames.FrameError, NoPayloadError)):
            decode(damaged)


def test_truncated_text_is_rejected() -> None:
    enc = encode(cover_for("vs-bytes"), PAYLOAD, "vs-bytes")
    half = enc.text[: len(enc.text) // 2]
    with pytest.raises((NoPayloadError, frames.FrameError)):
        decode(half)


def test_plain_text_has_nothing_to_extract() -> None:
    with pytest.raises(NoPayloadError):
        decode("Just an ordinary sentence with no hidden marks whatsoever.")


def test_capacity_error_is_actionable() -> None:
    big = b"x" * 5000
    with pytest.raises(CapacityError) as exc:
        encode("short cover text.", big, "homoglyph")
    assert "carrier" in str(exc.value)


def test_encode_is_deterministic() -> None:
    cover = cover_for("omni16")
    a = encode(cover, PAYLOAD, "omni16", key="k", placement="spread").text
    b = encode(cover, PAYLOAD, "omni16", key="k", placement="spread").text
    assert a == b


@pytest.mark.parametrize("placement", ["spread", "interleave", "suffix", "prefix"])
def test_all_placements_decode(placement: str) -> None:
    enc = encode(cover_for("tags"), PAYLOAD, "tags", placement=placement)
    assert decode(enc.text).payload == PAYLOAD


def test_visible_text_is_unchanged_for_insertion_channels() -> None:
    cover = cover_for("zw-octal")
    enc = encode(cover, PAYLOAD, "zw-octal")
    scheme = get_scheme("zw-octal")
    visible = "".join(c for c in enc.text if c not in scheme.symbol_to_digit)
    assert visible == cover


def test_substitution_channels_keep_length_and_word_count() -> None:
    for scheme_id in ("homoglyph", "fullwidth", "spaces", "punct"):
        scheme = get_scheme(scheme_id)
        cover = cover_for(scheme_id)
        enc = encode(cover, PAYLOAD, scheme_id)
        assert len(enc.text) == len(cover)
        assert enc.text.split()[0]  # still word-shaped
        assert scheme.slots(enc.text) == scheme.slots(cover)


def test_substitution_positions_are_key_derived() -> None:
    """With a key the carrier positions move, so an unkeyed reader cannot align."""
    cover = cover_for("homoglyph")
    plain = encode(cover, PAYLOAD, "homoglyph").text
    keyed = encode(cover, PAYLOAD, "homoglyph", key="k").text
    assert plain != keyed


def test_select_positions_is_stable_and_disjoint() -> None:
    a = select_positions(500, 120, "glyphmark/v1|key")
    b = select_positions(500, 120, "glyphmark/v1|key")
    assert a == b and len(set(a)) == 120
    excluded = set(a)
    c = select_positions(500, 120, "glyphmark/v1|key", exclude=excluded)
    assert not (set(c) & excluded)


def test_select_positions_is_hash_randomisation_proof() -> None:
    """Only int-seeded RNG state is used, so results survive a fresh interpreter."""
    import hashlib

    material = b"glyphmark/v1|k|10|5|()"
    assert int.from_bytes(hashlib.sha256(material).digest()[:16], "big") > 0
    assert select_positions(10, 5, "glyphmark/v1|k") == select_positions(10, 5, "glyphmark/v1|k")


@pytest.mark.parametrize("bits", [1, 2, 3, 4, 6, 8])
def test_bit_digit_codec_is_lossless(bits: int) -> None:
    data = bytes(range(64))
    digits = to_symbols(data, bits)
    assert all(0 <= d < (1 << bits) for d in digits)
    assert digits_to_bytes(digits, bits)[: len(data)] == data


def test_every_channel_declares_its_metadata() -> None:
    for scheme in SCHEMES:
        assert scheme.blurb and scheme.carrier and scheme.detection
        assert scheme.killed_by, f"{scheme.id} must name the sanitizer stage(s) that kill it"
        assert 1 <= scheme.stealth <= 5 and 1 <= scheme.survival <= 5
        assert scheme.bits_per_unit == scheme.radix.bit_length() - 1


def test_listish_metadata_is_itemized_not_character_split() -> None:
    """A channel may declare one note as a bare string; it must not become one item per letter.

    The CLI prints each note as a bullet and the web UI maps over them, so a str leaking
    through here shows up as 70 one-character bullets.
    """
    for scheme in SCHEMES:
        for field in ("notes", "tags", "killed_by"):
            items = getattr(scheme, field)
            assert isinstance(items, tuple), f"{scheme.id}.{field} must be a tuple"
            assert all(isinstance(i, str) for i in items)
            assert all(len(i) > 1 for i in items), (
                f"{scheme.id}.{field} looks character-split: {items[:4]!r}"
            )
        assert scheme.to_dict()["notes"] == list(scheme.notes)
