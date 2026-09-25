"""Forensic side of the toolkit: character inspection and covert-channel detection.

``inspect_text``  -> per-code-point table (what is really in this string?)
``detect``        -> findings, risk score, and the sanitizer stages that remove them
"""

from __future__ import annotations

import unicodedata

from . import frames
from .codec import GlyphMarkError, decode
from .schemes import HOMOGLYPH_PAIRS, PUNCT_PAIRS, SCHEMES

# Code points that render as nothing (or near-nothing) but change the stream.
ZERO_WIDTH = {
    0x200B: "ZERO WIDTH SPACE", 0x200C: "ZERO WIDTH NON-JOINER",
    0x200D: "ZERO WIDTH JOINER", 0x2060: "WORD JOINER",
    0xFEFF: "ZERO WIDTH NO-BREAK SPACE / BOM", 0x180E: "MONGOLIAN VOWEL SEPARATOR",
    0x00AD: "SOFT HYPHEN",
}
INVISIBLE_OPS = {
    0x2061: "FUNCTION APPLICATION", 0x2062: "INVISIBLE TIMES",
    0x2063: "INVISIBLE SEPARATOR", 0x2064: "INVISIBLE PLUS",
}
BIDI = {
    0x200E: "LEFT-TO-RIGHT MARK", 0x200F: "RIGHT-TO-LEFT MARK", 0x061C: "ARABIC LETTER MARK",
    0x202A: "LRE", 0x202B: "RLE", 0x202C: "PDF", 0x202D: "LRO", 0x202E: "RLO",
    0x2066: "LRI", 0x2067: "RLI", 0x2068: "FSI", 0x2069: "PDI",
}
FILLERS = {0x3164: "HANGUL FILLER", 0xFFA0: "HALFWIDTH HANGUL FILLER"}
# Derived straight from the substitution tables so the detector can never drift
# out of sync with the encoder.
CONFUSABLE_ALTS: dict[int, str] = {
    ord(alt): base for base, alt in (*HOMOGLYPH_PAIRS, *PUNCT_PAIRS)
}
LATEX_SPACEISH = {0x00A0, 0x1680, 0x2000, 0x2001, 0x2002, 0x2003, 0x2004, 0x2005,
                  0x2006, 0x2007, 0x2008, 0x2009, 0x200A, 0x202F, 0x205F, 0x3000}
DEFAULT_IGNORABLE_RANGES = [
    (0x00AD, 0x00AD), (0x180E, 0x180E), (0x200B, 0x200F), (0x202A, 0x202E),
    (0x2060, 0x2069), (0xFEFF, 0xFEFF), (0xFFF9, 0xFFFB), (0x0600, 0x0605),
    (0x061C, 0x061C), (0x08E2, 0x08E2), (0x110BD, 0x110BD), (0x1BCA0, 0x1BCA3),
    (0xE0000, 0xE0FFF),
]

_SCRIPT_RANGES: list[tuple[int, int, str]] = [
    (0x0041, 0x005A, "Latin"), (0x0061, 0x007A, "Latin"),
    (0x00C0, 0x024F, "Latin"), (0x1E00, 0x1EFF, "Latin"),
    (0x0400, 0x04FF, "Cyrillic"), (0x0500, 0x052F, "Cyrillic"),
    (0x0370, 0x03FF, "Greek"), (0x0530, 0x058F, "Armenian"),
    (0x10A0, 0x10FF, "Georgian"), (0x0600, 0x06FF, "Arabic"),
    (0x0590, 0x05FF, "Hebrew"), (0x0900, 0x097F, "Devanagari"),
    (0x0E00, 0x0E7F, "Thai"), (0x3040, 0x30FF, "Kana"),
    (0x4E00, 0x9FFF, "Han"), (0xAC00, 0xD7AF, "Hangul"),
    (0x3130, 0x318F, "Hangul"), (0xFF66, 0xFF9F, "Kana"),
]


def script_of(cp: int) -> str:
    for start, end, name in _SCRIPT_RANGES:
        if start <= cp <= end:
            return name
    return "Common"


def is_vs(cp: int) -> bool:
    return 0xFE00 <= cp <= 0xFE0F or 0xE0100 <= cp <= 0xE01EF


def is_tag(cp: int) -> bool:
    return 0xE0000 <= cp <= 0xE007F


def is_fullwidth(cp: int) -> bool:
    return 0xFF01 <= cp <= 0xFF5E


def char_info(ch: str) -> dict:
    cp = ord(ch)
    cat = unicodedata.category(ch)
    flags: list[str] = []
    if cat == "Cc" and cp not in (0x09, 0x0A, 0x0D):
        flags.append("c0-control")
    if cp in ZERO_WIDTH:
        flags.append("zero-width")
    if cp in INVISIBLE_OPS:
        flags.append("invisible-operator")
    if cp in BIDI:
        flags.append("bidi-control")
    if cp in FILLERS:
        flags.append("hangul-filler")
    if is_vs(cp):
        flags.append("variation-selector")
    if is_tag(cp):
        flags.append("tag-block")
    if is_fullwidth(cp):
        flags.append("fullwidth-compat")
    if cp in CONFUSABLE_ALTS:
        flags.append("confusable")
    if cp in LATEX_SPACEISH and cp != 0x20:
        flags.append("space-variant")
    if cat == "Mn":
        flags.append("combining-mark")
    if any(a <= cp <= b for a, b in DEFAULT_IGNORABLE_RANGES):
        flags.append("default-ignorable")
    return {
        "index": 0,
        "char": ch,
        "display": _displayable(ch),
        "codepoint": f"U+{cp:04X}",
        "decimal": cp,
        "category": cat,
        "name": unicodedata.name(ch, "<unassigned>"),
        "script": script_of(cp),
        "utf8": " ".join(f"{b:02X}" for b in ch.encode("utf-8")),
        "flags": flags,
        "suspect": bool(flags),
    }


def _displayable(ch: str) -> str:
    if unicodedata.category(ch) in ("Cc", "Cf", "Zl", "Zp"):
        return "␢"
    return ch


def inspect_text(text: str, limit: int = 4000) -> dict:
    rows = []
    for i, ch in enumerate(text):
        if i >= limit:
            break
        row = char_info(ch)
        row["index"] = i
        rows.append(row)
    return {
        "codepoints": len(text),
        "utf8_bytes": len(text.encode("utf-8")),
        "utf16_units": len(text.encode("utf-16-le")) // 2,
        "visible_guess": sum(1 for r in rows if not r["suspect"]),
        "suspect_count": sum(1 for r in rows if r["suspect"]),
        "truncated": len(text) > limit,
        "rows": rows,
    }


# --------------------------------------------------------------------------- #
# Detection
# --------------------------------------------------------------------------- #

_FINDINGS: list[dict] = [
    dict(kind="c0_controls", severity="high", weight=18,
         title="Non-printable ASCII C0/C1 control characters",
         why="C0 codes are the classic ASCII stego nibble channel. Invisible in GUIs, "
             "shown as ^A/^B by cat -A.",
         stage="strip_controls"),
    dict(kind="zero_width", severity="high", weight=20,
         title="Zero-width / invisible format characters",
         why="ZWSP, ZWNJ, ZWJ, WORD JOINER, BOM, soft hyphen and the Mongolian vowel "
             "separator carry 1-4 bits per insertion.",
         stage="strip_zero_width"),
    dict(kind="invisible_operators", severity="high", weight=16,
         title="Invisible mathematical operators (U+2061-U+2064)",
         why="Frequently missing from 'strip zero width' regexes, so they are a favourite "
             "stego slot.",
         stage="strip_zero_width"),
    dict(kind="bidi_controls", severity="high", weight=20,
         title="Bidirectional override / isolate controls",
         why="Invisible in LTR prose and explicitly flagged by the OWASP LLM top-10 as a "
             "prompt-injection carrier.",
         stage="strip_bidi"),
    dict(kind="tags_block", severity="high", weight=25,
         title="Unicode Tags block (Plane 14, U+E0000-U+E007F)",
         why="Renderer-suppressed mirror of ASCII. Invisible to humans while tokenizers "
             "decode it back to text — the hidden-instruction injection primitive.",
         stage="strip_tags"),
    dict(kind="variation_selectors", severity="medium", weight=14,
         title="Variation selectors",
         why="256 selectors clamp onto a base character; up to one hidden byte per visible "
             "character.",
         stage="strip_variation_selectors"),
    dict(kind="confusables", severity="high", weight=22,
         title="Confusable cross-script homoglyphs",
         why="Cyrillic/Greek/Armenian look-alikes of Latin letters. The most "
             "sanitizer-resistant channel known; basis of homograph phishing.",
         stage="confusables_to_ascii"),
    dict(kind="script_mixing", severity="medium", weight=12,
         title="Mixed-script token (Latin + Cyrillic/Greek/…)",
         why="A single word that mixes incompatible scripts is the UTS #39 "
             "'Highly Restrictive' signal browsers use to force punycode.",
         stage="confusables_to_ascii"),
    dict(kind="fullwidth_forms", severity="low", weight=8,
         title="Fullwidth / compatibility look-alikes",
         why="U+FF01-U+FF5E twins of printable ASCII — a 1-bit channel NFKC removes in "
             "one pass.",
         stage="fullwidth_fold"),
    dict(kind="space_variants", severity="low", weight=8,
         title="Non-ASCII whitespace variants",
         why="NBSP / thin / ideographic spaces at word boundaries encode the 'space "
             "alphabet' channel.",
         stage="collapse_spaces"),
    dict(kind="hangul_fillers", severity="medium", weight=14,
         title="Hangul filler letters used as invisible ink",
         why="U+3164 / U+FFA0 are category Lo (letters) so category-based Cf strippers "
             "leave them behind.",
         stage="strip_fillers"),
    dict(kind="combining_marks", severity="low", weight=8,
         title="Combining marks on unexpected bases",
         why="Stacking U+0300-U+036F onto letters/spaces is a low-stealth but real "
             "channel.",
         stage="strip_combining"),
    dict(kind="default_ignorable", severity="medium", weight=12,
         title="Other default-ignorable code points",
         why="Anything in an ignorable range that is not already covered above is "
             "anomalous in ordinary prose.",
         stage="strip_format"),
]
_META = {f["kind"]: f for f in _FINDINGS}


def _classify(cp: int) -> str | None:
    if unicodedata.category(chr(cp)) == "Cc" and cp not in (0x09, 0x0A, 0x0D):
        return "c0_controls"
    if unicodedata.category(chr(cp)) == "Cc":
        return None
    if cp in ZERO_WIDTH:
        return "zero_width"
    if cp in INVISIBLE_OPS:
        return "invisible_operators"
    if cp in BIDI:
        return "bidi_controls"
    if is_tag(cp):
        return "tags_block"
    if is_vs(cp):
        return "variation_selectors"
    if cp in FILLERS:
        return "hangul_fillers"
    if cp in CONFUSABLE_ALTS:
        return "confusables"
    if is_fullwidth(cp):
        return "fullwidth_forms"
    if cp in LATEX_SPACEISH and cp != 0x20:
        return "space_variants"
    if unicodedata.category(chr(cp)) == "Mn":
        return "combining_marks"
    if any(a <= cp <= b for a, b in DEFAULT_IGNORABLE_RANGES):
        return "default_ignorable"
    return None


def _mixed_scripts(text: str) -> list[dict]:
    hits: list[dict] = []
    token: list[int] = []
    start = 0
    for idx, ch in enumerate(text + " "):
        cp = ord(ch)
        script = script_of(cp)
        if script in ("Common",) or unicodedata.category(ch) == "Mn":
            if token:
                hits.append(_token_report(token, start))
                token, start = [], 0
            continue
        if not token:
            start = idx
        token.append(cp)
    return [h for h in hits if h]


def _token_report(codes: list[int], start: int) -> dict | None:
    scripts = {script_of(c) for c in codes if script_of(c) != "Common"}
    # a Latin word with foreign letters in it is the interesting case
    if len(scripts) > 1 and "Latin" in scripts:
        confusable_in_token = sum(1 for c in codes if c in CONFUSABLE_ALTS)
        if confusable_in_token or scripts - {"Latin"} - {"Hangul"}:
            return {
                "offset": start,
                "text": "".join(chr(c) for c in codes)[:64],
                "scripts": sorted(scripts),
                "confusables": confusable_in_token,
            }
    return None


def _tag_mirror(text: str) -> str:
    out = []
    for ch in text:
        cp = ord(ch)
        if 0xE0020 <= cp <= 0xE007F:
            out.append(chr(cp - 0xE0000))
    return "".join(out)


def _frame_signatures(text: str) -> list[dict]:
    """Try to recover an unkeyed GlyphMark frame per channel — a positive signature."""
    hits = []
    for scheme in SCHEMES:
        try:
            result = decode(text, key=None, scheme_id=scheme.id)
        except frames.KeyRequiredError:
            hits.append({
                "scheme": scheme.id,
                "payload_preview": "(keyed frame — payload is unreadable without the key)",
                "payload_len": 0,
                "strength": "keyed frame present (magic + version bytes valid)",
            })
            continue
        except (GlyphMarkError, frames.FrameError):
            continue
        hits.append({
            "scheme": scheme.id,
            "payload_preview": result.text[:120],
            "payload_len": len(result.payload),
            "strength": "confirmed (magic + CRC32 valid)",
        })
    return hits


def detect(text: str, try_frames: bool = True) -> dict:
    counts: dict[str, list[int]] = {}
    samples: dict[str, list[dict]] = {}
    for i, ch in enumerate(text):
        kind = _classify(ord(ch))
        if not kind:
            continue
        counts.setdefault(kind, []).append(i)
        if len(samples.setdefault(kind, [])) < 12:
            info = char_info(ch)
            info["index"] = i
            samples[kind].append(info)

    findings: list[dict] = []
    for kind, positions in counts.items():
        meta = _META[kind]
        findings.append({
            "kind": kind,
            "title": meta["title"],
            "severity": meta["severity"],
            "count": len(positions),
            "offsets": positions[:40],
            "why": meta["why"],
            "remove_with": meta["stage"],
            "characters": [
                {"codepoint": s["codepoint"], "name": s["name"], "utf8": s["utf8"],
                 "category": s["category"], "at": s["index"]}
                for s in samples[kind]
            ],
        })

    mixed = _mixed_scripts(text)
    if mixed:
        meta = _META["script_mixing"]
        findings.append({
            "kind": "script_mixing", "title": meta["title"], "severity": meta["severity"],
            "count": len(mixed), "offsets": [m["offset"] for m in mixed[:40]],
            "why": meta["why"], "remove_with": meta["stage"], "tokens": mixed[:20],
        })

    nfkc = unicodedata.normalize("NFKC", text)
    drift = sum(1 for a, b in zip(text, nfkc, strict=False) if a != b) + abs(len(text) - len(nfkc))
    if drift:
        findings.append({
            "kind": "nfkc_drift", "title": "Text changes under NFKC normalization",
            "severity": "info", "count": drift, "offsets": [],
            "why": "Compatibility characters (fullwidth, ligatures, selectors, some spaces) "
                   "collapse under NFKC. Diffing raw vs normalized is the cheapest "
                   "stego tripwire there is.",
            "remove_with": "nfkc", "characters": [],
        })

    frames_hits = _frame_signatures(text) if try_frames else []
    for hit in frames_hits:
        findings.append({
            "kind": "frame_signature", "title": f"GlyphMark frame recovered via "
                                                f"'{hit['scheme']}'",
            "severity": "high", "count": hit["payload_len"], "offsets": [],
            "why": "A structured frame with a valid magic byte and CRC32 was recovered on "
                   "this channel — this is a positive identification, not a heuristic.",
            "remove_with": SCHEME_STAGE.get(hit["scheme"], "nfkc"),
            "characters": [],
            "payload_preview": hit["payload_preview"],
            "strength": hit["strength"],
        })

    findings.sort(key=lambda f: (-_severity_rank(f["severity"]), -f["count"]))
    score = 0
    for f in findings:
        score += _META.get(f["kind"], {"weight": 10})["weight"] * min(4, 1 + f["count"] // 8)
    if frames_hits:
        score += 40
    verdict = classify_score(score, bool(frames_hits), bool(findings))

    return {
        "risk_score": min(100, score),
        "verdict": verdict,
        "codepoints": len(text),
        "suspect_total": sum(len(v) for k, v in counts.items()),
        "findings": findings,
        "tag_block_mirror": _tag_mirror(text) or None,
        "nfkc_equal": text == nfkc,
        "frame_signatures": frames_hits,
        "recommendation": _recommendation(findings, verdict),
    }


SCHEME_STAGE = {
    "zw-binary": "strip_zero_width", "zw-octal": "strip_zero_width",
    "omni16": "strip_format", "tags": "strip_tags", "vs-bytes": "strip_variation_selectors",
    "bidi": "strip_bidi", "fillers": "strip_fillers", "homoglyph": "confusables_to_ascii",
    "fullwidth": "fullwidth_fold", "punct": "punct_fold", "spaces": "collapse_spaces",
    "ascii-ctrl": "strip_controls", "combining": "strip_combining",
}


def _severity_rank(sev: str) -> int:
    return {"high": 3, "medium": 2, "low": 1, "info": 0}[sev]


def classify_score(score: int, frames_found: bool, any_finding: bool) -> str:
    if frames_found:
        return "watermark-confirmed"
    if score >= 60:
        return "high-risk"
    if score >= 25:
        return "suspicious"
    if any_finding:
        return "minor-anomalies"
    return "clean"


def _recommendation(findings: list[dict], verdict: str) -> str:
    stages = sorted({f["remove_with"] for f in findings if f.get("remove_with")})
    if verdict == "clean":
        return "No covert-channel code points detected. Still normalize untrusted input " \
               "(NFKC) before it reaches a model or a template."
    return ("Run the sanitizer with these stages to neutralize everything found: "
            + ", ".join(stages) + ". For an intake pipeline use the full default pipeline.")
