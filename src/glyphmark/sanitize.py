"""Defense side: staged sanitizer that destroys every channel this toolkit writes.

Stages run in a fixed order (cheap structural strips first, normalization, then
aggressive opt-in passes).  Each stage reports how many code points it removed or
rewrote, so a pipeline can *prove* that a payload did not survive.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass

from .analysis import (
    BIDI,
    CONFUSABLE_ALTS,
    DEFAULT_IGNORABLE_RANGES,
    FILLERS,
    INVISIBLE_OPS,
    ZERO_WIDTH,
    is_tag,
    is_vs,
    script_of,
)


@dataclass(frozen=True)
class Stage:
    id: str
    label: str
    description: str
    kills: tuple[str, ...] = ()
    default: bool = True
    fn: object = None      # callable(str) -> tuple[str, int]


@dataclass
class StageResult:
    id: str
    label: str
    removed: int
    before_len: int
    after_len: int
    changed: bool

    def to_dict(self) -> dict:
        return {
            "id": self.id, "label": self.label, "removed": self.removed,
            "before_len": self.before_len, "after_len": self.after_len,
            "changed": self.changed,
        }


def _drop_chars(text: str, predicate) -> tuple[str, int]:
    out = []
    removed = 0
    for ch in text:
        if predicate(ch):
            removed += 1
        else:
            out.append(ch)
    return "".join(out), removed


def strip_controls(text: str) -> tuple[str, int]:
    return _drop_chars(
        text, lambda ch: unicodedata.category(ch) == "Cc" and ord(ch) not in (0x09, 0x0A, 0x0D)
    )


def strip_zero_width(text: str) -> tuple[str, int]:
    dead = set(ZERO_WIDTH) | set(INVISIBLE_OPS)
    return _drop_chars(text, lambda ch: ord(ch) in dead)


def strip_bidi(text: str) -> tuple[str, int]:
    return _drop_chars(text, lambda ch: ord(ch) in set(BIDI))


def strip_tags(text: str) -> tuple[str, int]:
    return _drop_chars(text, lambda ch: is_tag(ord(ch)))


def strip_variation_selectors(text: str) -> tuple[str, int]:
    return _drop_chars(text, lambda ch: is_vs(ord(ch)))


def strip_fillers(text: str) -> tuple[str, int]:
    return _drop_chars(text, lambda ch: ord(ch) in set(FILLERS))


def strip_combining(text: str) -> tuple[str, int]:
    return _drop_chars(text, lambda ch: unicodedata.category(ch) == "Mn")


def strip_format(text: str) -> tuple[str, int]:
    return _drop_chars(text, lambda ch: unicodedata.category(ch) == "Cf")


def strip_default_ignorable(text: str) -> tuple[str, int]:
    return _drop_chars(
        text,
        lambda ch: any(a <= ord(ch) <= b for a, b in DEFAULT_IGNORABLE_RANGES),
    )


def confusables_to_ascii(text: str) -> tuple[str, int]:
    out, changed = [], 0
    for ch in text:
        base = CONFUSABLE_ALTS.get(ord(ch))
        if base:
            out.append(base)
            changed += 1
        else:
            out.append(ch)
    return "".join(out), changed


def fullwidth_fold(text: str) -> tuple[str, int]:
    out, changed = [], 0
    for ch in text:
        cp = ord(ch)
        if 0xFF01 <= cp <= 0xFF5E:
            out.append(chr(cp - 0xFEE0))
            changed += 1
        elif cp == 0x3000:
            out.append(" ")
            changed += 1
        else:
            out.append(ch)
    return "".join(out), changed


def punct_fold(text: str) -> tuple[str, int]:
    table = {0x2010: "-", 0x02BC: "'", 0x201F: '"', 0x2217: "*", 0x223C: "~",
             0x2024: ".", 0x2018: "'", 0x2019: "'", 0x201C: '"', 0x201D: '"',
             0x2011: "-", 0x2012: "-", 0x2013: "-", 0x2014: "-", 0x2212: "-"}
    out, changed = [], 0
    for ch in text:
        repl = table.get(ord(ch))
        if repl:
            out.append(repl)
            changed += 1
        else:
            out.append(ch)
    return "".join(out), changed


def collapse_spaces(text: str) -> tuple[str, int]:
    """Normalise every blank to U+0020. U+180E (used as a zero-width 'space' in the
    space-alphabet channel) is dropped rather than widened into a real space."""
    out, changed = [], 0
    for ch in text:
        cp = ord(ch)
        if cp == 0x180E:
            changed += 1
            continue
        if cp == 0x20 or unicodedata.category(ch) in ("Zs", "Zl", "Zp"):
            if cp != 0x20:
                changed += 1
            out.append(" ")
        else:
            out.append(ch)
    return "".join(out), changed


def nfkc(text: str) -> tuple[str, int]:
    norm = unicodedata.normalize("NFKC", text)
    changed = sum(1 for a, b in zip(text, norm, strict=False) if a != b) + abs(len(text) - len(norm))
    return norm, changed


def ascii_transcode(text: str) -> tuple[str, int]:
    kept = text.encode("ascii", errors="ignore").decode("ascii")
    return kept, len(text) - len(kept)


def script_allowlist(text: str, allowed: frozenset[str] = frozenset({"Latin", "Common"})
                     ) -> tuple[str, int]:
    return _drop_chars(text, lambda ch: ch.isalpha() and script_of(ord(ch)) not in allowed)


STAGES: list[Stage] = [
    Stage("strip_controls", "Remove C0/C1 control codes",
          "Drops every category-Cc character except tab/newline/CR. Kills the ASCII-only "
          "nibble channel.", ("ascii-ctrl",), True, strip_controls),
    Stage("strip_zero_width", "Remove zero-widths & invisible operators",
          "U+200B-U+200D, U+2060-U+2064, U+FEFF, U+180E, soft hyphen.",
          ("zw-binary", "zw-octal", "omni16"), True, strip_zero_width),
    Stage("strip_bidi", "Remove bidi controls",
          "LRM/RLM, LRE/RLE/PDF/LRO/RLO and the 2066-2069 isolates.",
          ("bidi", "omni16"), True, strip_bidi),
    Stage("strip_tags", "Remove Plane 14 tag block",
          "U+E0000-U+E0FFF. The highest-value single rule for LLM input hygiene.",
          ("tags",), True, strip_tags),
    Stage("strip_variation_selectors", "Remove variation selectors",
          "U+FE00-U+FE0F and U+E0100-U+E01EF (1 byte per anchor channel).",
          ("vs-bytes",), True, strip_variation_selectors),
    Stage("strip_fillers", "Remove Hangul fillers",
          "U+3164 / U+FFA0 — letters, not Cf, so category strippers miss them.",
          ("fillers", "omni16"), True, strip_fillers),
    Stage("strip_combining", "Remove combining marks",
          "Category Mn. Warning: this also removes legitimate diacritics, so disable it "
          "for multilingual corpora.", ("combining",), True, strip_combining),
    Stage("strip_format", "Remove all category-Cf controls",
          "Catch-all for format characters that the named lists above did not cover.",
          ("omni16",), True, strip_format),
    Stage("strip_default_ignorable", "Remove default-ignorable ranges",
          "Everything in a Unicode default-ignorable range, plus annotation & interlinear "
          "marks.", (), True, strip_default_ignorable),
    Stage("confusables_to_ascii", "Fold confusables to ASCII",
          "UTS #39 style: map Cyrillic/Greek/Armenian look-alikes and punctuation twins "
          "back to their ASCII prototype.", ("homoglyph", "punct"), True,
          confusables_to_ascii),
    Stage("fullwidth_fold", "Fold fullwidth/compatibility forms",
          "U+FF01-U+FF5E to ASCII, ideographic space to space.", ("fullwidth",), True,
          fullwidth_fold),
    Stage("punct_fold", "Normalize punctuation twins",
          "Dashes, curly quotes, modifier apostrophes, operator asterisk/tilde to ASCII.",
          ("punct",), True, punct_fold),
    Stage("collapse_spaces", "Collapse whitespace variants",
          "Every Zs/nbsp/ideographic variant becomes a plain U+0020; the Mongolian vowel "
          "separator used as a zero-width blank is dropped.", ("spaces",), True,
          collapse_spaces),
    Stage("nfkc", "NFKC normalize",
          "The single highest-value defense: compatibility forms, selectors on odd bases "
          "and many space variants all collapse.",
          ("fullwidth", "combining", "vs-bytes", "spaces"), True, nfkc),
    Stage("script_allowlist", "Keep Latin+Common letters only",
          "Aggressive: rejects any letter outside the allowed script set. Use for "
          "ASCII-ish intake (usernames, domains, identifiers).",
          ("homoglyph", "fillers"), False, script_allowlist),
    Stage("ascii_transcode", "Force 7-bit ASCII",
          "Aggressive last resort: drops every non-ASCII code point. Destroys all Unicode "
          "channels and any legitimate non-Latin text.",
          tuple(s for s in ("zw-binary", "zw-octal", "omni16", "tags", "vs-bytes", "bidi",
                            "fillers", "homoglyph", "fullwidth", "punct", "spaces",
                            "combining")),
          False, ascii_transcode),
]

_BY_ID = {s.id: s for s in STAGES}
DEFAULT_PIPELINE = [s.id for s in STAGES if s.default]


def sanitize(text: str, stages: list[str] | None = None) -> dict:
    """Run the pipeline and return clean text + per-stage accounting."""
    ids = DEFAULT_PIPELINE if stages is None else list(stages)
    unknown = [s for s in ids if s not in _BY_ID]
    if unknown:
        raise KeyError(f"unknown sanitize stage(s): {', '.join(unknown)}. "
                       f"available: {', '.join(_BY_ID)}")
    # keep the caller's order but preserve the canonical relative order of known stages
    order = {s.id: i for i, s in enumerate(STAGES)}
    ids = sorted(set(ids), key=lambda s: order[s])

    current = text
    results: list[StageResult] = []
    for sid in ids:
        stage = _BY_ID[sid]
        before = len(current)
        current, removed = stage.fn(current)  # type: ignore[operator]
        results.append(StageResult(sid, stage.label, removed, before, len(current),
                                   removed > 0 or before != len(current)))
    killed = sorted({k for sid in ids for k in _BY_ID[sid].kills})
    return {
        "text": current,
        "stages": [r.to_dict() for r in results],
        "removed_total": sum(r.removed for r in results),
        "codepoints_before": len(text),
        "codepoints_after": len(current),
        "identical": current == text,
        "channels_targeted": killed,
    }


def stage_docs() -> list[dict]:
    return [
        {
            "id": s.id, "label": s.label, "description": s.description,
            "kills": list(s.kills), "default": s.default,
        }
        for s in STAGES
    ]
