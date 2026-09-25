"""Watermark channel registry.

A *scheme* is a bidirectional mapping between bit groups and a set of Unicode /
ASCII code points, plus the rule for how those code points attach to a carrier
text.  Two families exist:

``insert``      invisible symbols are *inserted* at character boundaries
                (zero-widths, Plane-14 tags, variation selectors, bidi marks ...)

``substitute``  an existing visible character is swapped for a visually
                equivalent look-alike (Cyrillic/Greek homoglyphs, fullwidth
                forms, space variants, punctuation twins ...)

Every scheme carries honest operational metadata: payload density, visual
stealth, cross-platform survival, and the detection / sanitization vector that
kills it.  The same metadata drives the CLI tables and the web UI.
"""

from __future__ import annotations

import hashlib
import random
import unicodedata
from dataclasses import dataclass, field

FAMILY_INSERT = "insert"
FAMILY_SUBSTITUTE = "substitute"

SPACE_CHARS = {0x20, 0xA0, 0x1680, 0x2000, 0x2001, 0x2002, 0x2003, 0x2004, 0x2005,
               0x2006, 0x2007, 0x2008, 0x2009, 0x200A, 0x202F, 0x205F, 0x3000}


def _cps(*codes: int) -> str:
    return "".join(chr(c) for c in codes)


def _run(start: int, end: int) -> str:
    return "".join(chr(c) for c in range(start, end + 1))


# --------------------------------------------------------------------------- #
# Alphabets (radix is always an exact power of two -> loss-free bit groups)
# --------------------------------------------------------------------------- #

ZW_BINARY = _cps(0x200B, 0x200C)
ZW_OCTAL = _cps(0x200B, 0x200C, 0x200D, 0x2060, 0x2061, 0x2062, 0x2063, 0x2064)
OMNI_16 = _cps(0x200B, 0x200C, 0x200D, 0x2060, 0x2061, 0x2062, 0x2063, 0x2064,
               0xFEFF, 0x180E, 0x3164, 0xFFA0, 0x200E, 0x200F, 0x061C, 0x2066)
TAG_64 = _run(0xE0020, 0xE005F)          # mirrors ASCII 0x20-0x5F
VS_256 = _run(0xFE00, 0xFE0F) + _run(0xE0100, 0xE01EF)   # exactly 256 selectors
BIDI_4 = _cps(0x200E, 0x200F, 0x2066, 0x2069)
FILLER_2 = _cps(0x3164, 0xFFA0)
COMBINING_16 = _run(0x0300, 0x030F)
SPACE_16 = _cps(0x0020, 0x00A0, 0x1680, 0x2002, 0x2003, 0x2004, 0x2005, 0x2006,
                0x2007, 0x2008, 0x2009, 0x200A, 0x202F, 0x205F, 0x3000, 0x180E)
CTRL_16 = _cps(0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x0E,
               0x0F, 0x10, 0x11, 0x12, 0x13, 0x14, 0x15, 0x16)

# --------------------------------------------------------------------------- #
# Substitution tables: (base char, look-alike char). bit 0 = base, bit 1 = alt.
# --------------------------------------------------------------------------- #

HOMOGLYPH_PAIRS: list[tuple[str, str]] = [
    ("a", "а"), ("c", "с"), ("e", "е"), ("o", "ο"), ("p", "р"),
    ("x", "х"), ("i", "і"), ("j", "ј"), ("s", "ѕ"), ("k", "к"),
    ("y", "у"), ("l", "ӏ"), ("d", "ԁ"),
    ("A", "А"), ("B", "В"), ("C", "С"), ("E", "Е"), ("H", "Н"),
    ("K", "К"), ("M", "М"), ("O", "Ο"), ("P", "Р"), ("S", "Ѕ"),
    ("T", "Т"), ("X", "Х"), ("Y", "У"),
]

FULLWIDTH_PAIRS: list[tuple[str, str]] = [(chr(c), chr(c + 0xFEE0)) for c in range(0x21, 0x7F)]

PUNCT_PAIRS: list[tuple[str, str]] = [
    ("-", "‐"),   # HYPHEN
    ("'", "ʼ"),   # MODIFIER LETTER APOSTROPHE
    ('"', '"'),   # DOUBLE PRIME QUOTATION MARK
    ("*", "∗"),   # ASTERISK OPERATOR
    ("~", "∼"),   # TILDE OPERATOR
    (".", "․"),   # ONE DOT LEADER
]

SPACE_PAIRS: list[tuple[str, str]] = [(" ", ch) for ch in SPACE_16[1:]]

# Multi-alternative channels: one carrier, radix-1 look-alikes. The space channel
# is the only one with a 16-way alphabet (15 blanks + plain space = 4 bits/gap).
SPACE_ALTS = {" ": tuple(SPACE_16[1:])}


@dataclass(frozen=True)
class Scheme:
    id: str
    index: int
    label: str
    family: str
    blurb: str
    bits_per_unit: int
    alphabet: str = ""
    pairs: tuple[tuple[str, str], ...] = ()
    alts: dict[str, tuple[str, ...]] = field(default_factory=dict)
    anchor_required: bool = False
    carrier: str = ""
    stealth: int = 3
    survival: int = 3
    ascii_only: bool = False
    detection: str = ""
    killed_by: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()

    # ---- derived ---------------------------------------------------------- #
    @property
    def radix(self) -> int:
        return 1 << self.bits_per_unit

    @property
    def symbols(self) -> str:
        """Code points actually used (alphabet truncated to the radix)."""
        if self.family == FAMILY_INSERT:
            return self.alphabet[: self.radix]
        return "01"

    @property
    def alternatives(self) -> dict[str, tuple[str, ...]]:
        """base character -> the radix-1 look-alikes that encode digits 1..n."""
        if self.alts:
            return self.alts
        return {b: (a,) for b, a in self.pairs}

    @property
    def alt_index(self) -> dict[str, int]:
        """look-alike character -> its digit value (1..radix-1)."""
        out: dict[str, int] = {}
        for options in self.alternatives.values():
            for i, alt in enumerate(options, start=1):
                out[alt] = i
        return out

    @property
    def symbol_to_digit(self) -> dict[str, int]:
        return {ch: i for i, ch in enumerate(self.symbols)}

    @property
    def base_to_alt(self) -> dict[str, str]:
        return {b: a for b, a in self.pairs}

    @property
    def alt_to_base(self) -> dict[str, str]:
        return {a: b for b, a in self.pairs}

    @property
    def alt_to_base_full(self) -> dict[str, str]:
        return {a: b for b, options in self.alternatives.items() for a in options}

    @property
    def density_bytes_per_unit(self) -> float:
        return self.bits_per_unit / 8.0

    def unit_rows(self) -> list[dict]:
        """Reference table of the characters this scheme drives."""
        rows: list[dict] = []
        if self.family == FAMILY_INSERT:
            for digit, ch in enumerate(self.symbols):
                rows.append({
                    "digit": digit,
                    "bit_value": format(digit, f"0{self.bits_per_unit}b"),
                    "char": ch,
                    "codepoint": f"U+{ord(ch):04X}",
                    "category": unicodedata.category(ch),
                    "name": unicodedata.name(ch, "<unassigned code point>"),
                    "utf8": " ".join(f"{b:02X}" for b in ch.encode("utf-8")),
                    "render": render_hint(ch),
                })
        else:
            for base, options in self.alternatives.items():
                for i, alt in enumerate(options, start=1):
                    rows.append({
                        "digit": i,
                        "bit_value": format(i, f"0{self.bits_per_unit}b") + " (0 = base)",
                        "char": alt,
                        "codepoint": f"U+{ord(alt):04X}",
                        "category": unicodedata.category(alt),
                        "name": unicodedata.name(alt, "<unassigned code point>"),
                        "utf8": " ".join(f"{b:02X}" for b in alt.encode("utf-8")),
                        "render": f"{base}  →  {alt}",
                        "base": base,
                    })
        return rows

    # ---- carrier arithmetic ---------------------------------------------- #
    def slots(self, text: str) -> list[int]:
        """Indices in ``text`` able to host one watermark unit."""
        if self.family == FAMILY_INSERT:
            symbols = self.symbol_to_digit
            if self.anchor_required:
                return [i for i, ch in enumerate(text) if ch not in symbols]
            return list(range(len(text) + 1))
        usable = set(self.alternatives) | set(self.alt_index)
        return [i for i, ch in enumerate(text) if ch in usable]

    def capacity_bits(self, text: str) -> int:
        return len(self.slots(text)) * self.bits_per_unit

    def capacity_payload_bytes(self, text: str, header_bits: int, crc_bits: int) -> int:
        """Max payload bytes this cover text can carry under this scheme."""
        bits = self.capacity_bits(text) - header_bits - crc_bits
        return max(0, bits // 8)

    # ---- substitution read/write (digit-based, radix = 1 + n look-alikes) -- #
    def write_symbols(self, text: str, positions: list[int], digits: list[int]) -> str:
        """Write digit values at the given *text* indices."""
        alts = self.alternatives
        out = list(text)
        for pos, digit in zip(positions, digits, strict=True):
            ch = out[pos]
            base = ch if ch in alts else self.alt_to_base_full.get(ch)
            if base is None:  # pragma: no cover - guarded by slots()
                continue
            out[pos] = base if digit == 0 else alts[base][digit - 1]
        return "".join(out)

    def read_symbols(self, text: str, positions: list[int]) -> list[int]:
        index = self.alt_index
        return [index.get(text[pos], 0) for pos in positions]

    def digits_for_bytes(self, nbytes: int) -> int:
        """How many carrier units are needed to carry ``nbytes``."""
        return -(-nbytes * 8 // self.bits_per_unit)

    def to_dict(self, with_chars: bool = True) -> dict:
        data = {
            "id": self.id,
            "index": self.index,
            "label": self.label,
            "family": self.family,
            "blurb": self.blurb,
            "bits_per_unit": self.bits_per_unit,
            "radix": self.radix,
            "density_bytes_per_unit": self.density_bytes_per_unit,
            "carrier": self.carrier,
            "anchor_required": self.anchor_required,
            "stealth": self.stealth,
            "survival": self.survival,
            "ascii_only": self.ascii_only,
            "detection": self.detection,
            "killed_by": list(self.killed_by),
            "notes": list(self.notes),
            "tags": list(self.tags),
            "n_symbols": self.radix if self.family == FAMILY_INSERT else 2,
        }
        if with_chars:
            data["characters"] = self.unit_rows()
        return data


def render_hint(ch: str) -> str:
    cp = ord(ch)
    cat = unicodedata.category(ch)
    if 0xE0000 <= cp <= 0xE007F:
        return "invisible (renderer-suppressed tag)"
    if 0xFE00 <= cp <= 0xFE0F or 0xE0100 <= cp <= 0xE01EF:
        return "invisible after a base character"
    if cp in (0x3164, 0xFFA0):
        return "blank in Latin text (but it is a letter)"
    if cat == "Cf":
        return "invisible format control"
    if cat == "Cc":
        return "non-printing control (caret notation in terminals)"
    if unicodedata.combining(ch):
        return "attaches to the previous character"
    if cp in SPACE_CHARS or cat == "Zs":
        return "blank — width differs from U+0020"
    return "visible glyph"


_DEFS: list[dict] = [
    dict(
        id="zw-binary",
        label="Zero-width binary (ZWSP/ZWNJ)",
        family=FAMILY_INSERT,
        blurb="The classic 1-bit channel: ZWSP = 0, ZWNJ = 1. Maximum tool "
              "compatibility, minimum density.",
        bits_per_unit=1,
        alphabet=ZW_BINARY,
        carrier="one insertion point per character",
        stealth=5, survival=3,
        detection="regex [\\u200B-\\u200D] or a category=='Cf' sweep; NFKC does not "
                  "remove it, explicit stripping does",
        killed_by=("strip_zero_width", "strip_format"),
        notes=("Nearly every 'clean text' library already knows these two code points.",),
        tags=("invisible", "simple", "interop"),
    ),
    dict(
        id="zw-octal",
        label="Zero-width octal (8 invisible ops)",
        family=FAMILY_INSERT,
        blurb="3 bits per inserted char: ZWSP/ZWNJ/ZWJ/WJ plus the four invisible "
              "mathematical operators U+2061..U+2064.",
        bits_per_unit=3,
        alphabet=ZW_OCTAL,
        carrier="one insertion point per character",
        stealth=5, survival=3,
        detection="naive filters strip U+200B-200D only, so U+2061-2064 often survive; "
                  "a full Cf sweep removes all eight",
        killed_by=("strip_zero_width", "strip_format"),
        notes="The invisible math operators are the most commonly missed part of a sanitizer.",
        tags=("invisible", "math-ink"),
    ),
    dict(
        id="omni16",
        label="Omni-invisible base-16",
        family=FAMILY_INSERT,
        blurb="Zero-widths + invisible operators + BOM + Mongolian vowel separator + "
              "Hangul fillers + bidi marks in one 16-symbol radix: 4 bits per char.",
        bits_per_unit=4,
        alphabet=OMNI_16,
        carrier="one insertion point per character",
        stealth=4, survival=4,
        detection="maximal code-point spread — only a block allow-list catches all of it",
        killed_by=("strip_zero_width", "strip_format", "strip_bidi", "strip_fillers"),
        notes=("U+3164 / U+FFA0 are category Lo (letters), so category-based 'strip Cf' "
               "filters walk past them.",
               "Unpaired bidi isolates can glitch glyph ordering inside RTL text."),
        tags=("invisible", "mixed-channel", "bidi"),
    ),
    dict(
        id="tags",
        label="Unicode Tags block (Plane 14)",
        family=FAMILY_INSERT,
        blurb="U+E0020..U+E005F mirror ASCII 0x20..0x5F and are suppressed by renderers. "
              "6 bits per char — the channel LLM tokenizers read back as text.",
        bits_per_unit=6,
        alphabet=TAG_64,
        carrier="one insertion point per character",
        stealth=5, survival=2,
        detection="range filter U+E0000-E007F; UTF-8 sniff F3 A0 80 80 .. F3 A0 81 BF",
        killed_by=("strip_tags",),
        notes=("Rejected by strict XML/JSON parsers and some DB collations.",
               "Social platforms strip Plane 14 on ingestion; raw paste buffers keep it.",
               "This is the block behind hidden-instruction injection research."),
        tags=("invisible", "high-capacity", "llm-relevant"),
    ),
    dict(
        id="vs-bytes",
        label="Variation selectors (1 byte per anchor)",
        family=FAMILY_INSERT,
        blurb="VS1-VS16 + VS17-VS256 = exactly 256 selectors, i.e. one whole hidden byte "
              "clamped onto each anchor character.",
        bits_per_unit=8,
        alphabet=VS_256,
        anchor_required=True,
        carrier="one anchor character per payload byte",
        stealth=4, survival=3,
        detection="combining/selector sweep (Mn/Me categories) or NFKC, which drops "
                  "selectors sitting on non-emoji bases",
        killed_by=("strip_variation_selectors", "strip_combining"),
        notes=("Highest density per character in Unicode.",
               "Some fonts show a dotted box for selectors on unusual base characters."),
        tags=("invisible", "high-capacity", "anchor-bound"),
    ),
    dict(
        id="bidi",
        label="Bidirectional marks (base-4)",
        family=FAMILY_INSERT,
        blurb="LRM/RLM plus first/last bidi isolates: 2 bits per char, invisible in "
              "left-to-right prose.",
        bits_per_unit=2,
        alphabet=BIDI_4,
        carrier="one insertion point per character",
        stealth=3, survival=3,
        detection="any bidi control in an all-LTR document is itself the signal — "
                  "grep U+202A-U+202E and U+2066-U+2069",
        killed_by=("strip_bidi", "strip_format"),
        notes=("Mismatched overrides visibly reverse neighbouring glyphs — the classic tell.",),
        tags=("invisible", "bidi", "flagged-by-owasp"),
    ),
    dict(
        id="fillers",
        label="Hangul fillers (Cf-stripper blind spot)",
        family=FAMILY_INSERT,
        blurb="U+3164 / U+FFA0 render as nothing in Latin text yet are *letters* (Lo), so "
              "category-based Cf filters miss them entirely.",
        bits_per_unit=1,
        alphabet=FILLER_2,
        carrier="one insertion point per character",
        stealth=4, survival=4,
        detection="block allow-list, or a mixed-script check that rejects Hangul letters "
                  "inside Latin words",
        killed_by=("strip_fillers", "script_allowlist"),
        notes=("Useful fallback channel to pair with a homoglyph watermark.",),
        tags=("invisible", "letters", "blind-spot"),
    ),
    dict(
        id="homoglyph",
        label="Cross-script homoglyphs",
        family=FAMILY_SUBSTITUTE,
        blurb="Latin letters swapped for Cyrillic/Greek/Armenian look-alikes. Nothing "
              "invisible is added, so almost no sanitizer catches it.",
        bits_per_unit=1,
        pairs=HOMOGLYPH_PAIRS,
        carrier="each letter that has a confusable counterpart",
        stealth=4, survival=5,
        detection="UTS #39 skeleton normalization + mixed-script profile; "
                  "NFKC does NOT collapse these",
        killed_by=("confusables_to_ascii", "script_allowlist"),
        notes=("Survives copy-paste, JSON, SQL and social platforms.",
               "Breaks exact matching / search / case-folding — which is also why "
               "homograph phishing works."),
        tags=("visible-substitution", "most-robust", "uts39"),
    ),
    dict(
        id="fullwidth",
        label="Fullwidth look-alikes",
        family=FAMILY_SUBSTITUTE,
        blurb="ASCII 0x21-0x7E replaced by its U+FF01-FF5E twin: identical in most mono "
              "UIs, and NFKC is the only reliable killer.",
        bits_per_unit=1,
        pairs=FULLWIDTH_PAIRS,
        carrier="any printable ASCII character",
        stealth=3, survival=3,
        detection="one NFKC pass collapses the entire compatibility block",
        killed_by=("nfkc", "fullwidth_fold"),
        notes="Every printable character is a slot, so capacity is excellent — but the "
              "glyph advance changes in proportional fonts.",
        tags=("visible-substitution", "compat-chars"),
    ),
    dict(
        id="punct",
        label="Punctuation twins",
        family=FAMILY_SUBSTITUTE,
        blurb="Hyphen, apostrophe, quote, asterisk, tilde and period replaced by "
              "near-identical typographic twins.",
        bits_per_unit=1,
        pairs=PUNCT_PAIRS,
        carrier="each occurrence of a mappable punctuation character",
        stealth=3, survival=4,
        detection="typographic normalization (curly → straight quotes); NFKC partially works",
        killed_by=("punct_fold", "nfkc"),
        notes=("Low capacity in prose; good enough to sign code blocks and config dumps.",),
        tags=("visible-substitution", "low-capacity"),
    ),
    dict(
        id="spaces",
        label="Space alphabet (4 bits per gap)",
        family=FAMILY_SUBSTITUTE,
        blurb="Each word-gap space becomes one of 15 look-alike blanks: NBSP, en/em/thin/"
              "hair, NNBSP, ideographic, Ogham, Mongolian vowel separator.",
        bits_per_unit=4,
        pairs=SPACE_PAIRS,
        alts=SPACE_ALTS,
        carrier="each space in the cover text",
        stealth=2, survival=2,
        detection="HTML unescape and whitespace collapsing, textwrap, trim(); NFKC folds "
                  "several width variants",
        killed_by=("collapse_spaces", "nfkc"),
        notes=("Word-wrap and editor auto-format destroy this channel — keep payloads tiny "
               "or use pre-formatted text."),
        tags=("whitespace", "fragile"),
    ),
    dict(
        id="ascii-ctrl",
        label="ASCII C0 control nibbles",
        family=FAMILY_INSERT,
        blurb="For pipelines forced to 7-bit ASCII: 16 non-rendering C0 codes carry "
              "nibbles (4 bits each). Invisible in GUIs, obvious in terminals.",
        bits_per_unit=4,
        alphabet=CTRL_16,
        carrier="one insertion point per character",
        stealth=2, survival=2,
        ascii_only=True,
        detection="xxd / cat -A caret notation (^A ^B); any isprintable() sweep",
        killed_by=("strip_controls", "ascii_transcode"),
        notes=("The only family that survives an ISO-8859-1 / US-ASCII transcode.",
               "Terminals, compilers and web forms strip or escape it aggressively."),
        tags=("ascii-only", "terminal-visible"),
    ),
    dict(
        id="combining",
        label="Combining marks (stress test)",
        family=FAMILY_INSERT,
        blurb="16 combining diacritics clamped onto anchor characters. A channel in "
              "principle, but far from invisible in most fonts.",
        bits_per_unit=4,
        alphabet=COMBINING_16,
        anchor_required=True,
        carrier="one anchor character per 4 bits",
        stealth=1, survival=2,
        detection="any NFC/NFKC pass composes or reorders them; regex [\\u0300-\\u036F]",
        killed_by=("strip_combining", "nfkc"),
        notes=("Bundled as a stress-test channel: it demonstrates why normalization is the "
               "single highest-value defense."),
        tags=("combining", "low-stealth"),
    ),
]


def _build() -> list[Scheme]:
    out: list[Scheme] = []
    for i, spec in enumerate(_DEFS):
        data = dict(spec)
        data["index"] = i
        data["pairs"] = tuple(tuple(p) for p in data.get("pairs", ()))
        for key in ("killed_by", "notes", "tags"):
            data[key] = tuple(data.get(key, ()))
        scheme = Scheme(**data)
        n_alts = max((len(v) for v in scheme.alternatives.values()), default=1)
        if scheme.family == FAMILY_SUBSTITUTE and 1 + n_alts != scheme.radix:
            raise ValueError(
                f"scheme '{data['id']}': {n_alts} look-alikes needs radix {1 + n_alts}, "
                f"declared radix is {scheme.radix} ({scheme.bits_per_unit} bits)"
            )
        out.append(scheme)
    return out


SCHEMES: list[Scheme] = _build()
_BY_ID: dict[str, Scheme] = {s.id: s for s in SCHEMES}


def scheme_ids() -> list[str]:
    return [s.id for s in SCHEMES]


def get_scheme(scheme_id: str) -> Scheme:
    try:
        return _BY_ID[scheme_id]
    except KeyError:
        raise KeyError(
            f"unknown scheme '{scheme_id}'. available: {', '.join(scheme_ids())}"
        ) from None


# --------------------------------------------------------------------------- #
# Deterministic position spreading (substitution channels)
# --------------------------------------------------------------------------- #

def select_positions(total: int, need: int, seed: str,
                     exclude: set[int] | None = None) -> list[int]:
    """Pick ``need`` carrier indices, evenly spread with keyed jitter.

    Stable across processes (SHA-256 derived RNG, never ``hash()``), so a decoder
    that knows the bit budget recomputes exactly the same indices.
    """
    if need <= 0:
        return []
    excluded = tuple(sorted(exclude or ()))
    pool = [i for i in range(total) if i not in (exclude or set())]
    if need > len(pool):
        raise ValueError(f"carrier too small: need {need} slots, only {len(pool)} available")
    material = f"{seed}|{total}|{need}|{excluded}".encode()
    rng = random.Random(int.from_bytes(hashlib.sha256(material).digest()[:16], "big"))
    step = len(pool) / need
    chosen: set[int] = set()
    for j in range(need):
        lo = min(int(j * step), len(pool) - 1)
        hi = min(max(lo + 1, int((j + 1) * step)), len(pool))
        chosen.add(pool[rng.randint(lo, hi - 1)])
    if len(chosen) < need:  # deterministic backfill on bucket collisions
        for idx in pool:
            if len(chosen) >= need:
                break
            chosen.add(idx)
    return sorted(chosen)


def all_reference_rows() -> list[dict]:
    """Deduplicated character reference across every scheme (Character Lab)."""
    table: dict[int, dict] = {}
    for scheme in SCHEMES:
        for row in scheme.unit_rows():
            cp = int(row["codepoint"].split("+")[1], 16)
            entry = table.setdefault(cp, {**row, "schemes": []})
            if scheme.id not in entry["schemes"]:
                entry["schemes"].append(scheme.id)
    return [table[cp] for cp in sorted(table)]
