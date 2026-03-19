"""
braille_translator.py
─────────────────────
Wraps the `louis` Python bindings (liblouis) to convert plain text to Braille.

Supported tables:
  Grade 1 (uncontracted) — en-ueb-g1.ctb   (default)
  Grade 2 (contracted)   — en-ueb-g2.ctb

Usage:
    from braille_translator import BrailleTranslator, BrailleGrade

    tr = BrailleTranslator()
    result = tr.translate("Hello, world!")
    print(result.braille)          # Braille unicode string (⠠⠓⠑⠇⠇⠕…)
    print(result.back_translation) # Sanity-check round-trip text
    print(result.confidence)       # 1.0 if round-trip matches, 0.0 otherwise
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────
# Try to import louis; fall back gracefully so
# the module can be imported even when liblouis
# is not yet installed (useful for IDE tooling).
# ──────────────────────────────────────────────
try:
    import louis  # type: ignore

    _LOUIS_AVAILABLE = True
except ImportError:  # pragma: no cover
    louis = None  # type: ignore
    _LOUIS_AVAILABLE = False
    logger.warning(
        "liblouis Python bindings not found. "
        "Install with: brew install liblouis && pip install louis\n"
        "BrailleTranslator will return placeholder output until installed."
    )


# ──────────────────────────────────────────────
# Constants
# ──────────────────────────────────────────────

class BrailleGrade(str, Enum):
    """Braille grade / contraction level."""
    GRADE_1 = "grade1"  # Uncontracted (default per PRD)
    GRADE_2 = "grade2"  # Contracted


# Map grade → liblouis table filename(s).
# liblouis resolves these from its system table directory.
# UEB = Unified English Braille.
TABLES: dict[BrailleGrade, list[str]] = {
    BrailleGrade.GRADE_1: ["en-ueb-g1.ctb"],
    BrailleGrade.GRADE_2: ["en-ueb-g2.ctb"],
}

# Fallback: ASCII Braille dot-pattern lookup for when liblouis is missing.
_ASCII_BRAILLE_MAP: dict[str, str] = {
    "a": "⠁", "b": "⠃", "c": "⠉", "d": "⠙", "e": "⠑",
    "f": "⠋", "g": "⠛", "h": "⠓", "i": "⠊", "j": "⠚",
    "k": "⠅", "l": "⠇", "m": "⠍", "n": "⠝", "o": "⠕",
    "p": "⠏", "q": "⠟", "r": "⠗", "s": "⠎", "t": "⠞",
    "u": "⠥", "v": "⠧", "w": "⠺", "x": "⠭", "y": "⠽",
    "z": "⠵", " ": "⠀",
    "1": "⠂⠁", "2": "⠂⠃", "3": "⠂⠉", "4": "⠂⠙", "5": "⠂⠑",
    "6": "⠂⠋", "7": "⠂⠛", "8": "⠂⠓", "9": "⠂⠊", "0": "⠂⠚",
    ",": "⠂", ".": "⠲", "!": "⠖", "?": "⠦", ";": "⠆",
    ":": "⠒", "'": "⠄", "-": "⠤", "/": "⠌",
}


# ──────────────────────────────────────────────
# Result dataclass
# ──────────────────────────────────────────────

@dataclass
class TranslationResult:
    """Holds all output from a single translation call."""

    original_text: str
    """The normalized text that was fed to the translator."""

    braille: str
    """Braille unicode string output."""

    grade: BrailleGrade
    """The grade used for translation."""

    back_translation: str = ""
    """Round-trip translation for confidence scoring."""

    confidence: float = 1.0
    """
    Simple confidence score based on round-trip fidelity.
    1.0 = perfect match after case-fold; 0.0 = no match.
    Real STT confidence is passed in separately by the agent.
    """

    used_fallback: bool = False
    """True if liblouis was unavailable and the fallback ASCII map was used."""

    pipeline_meta: dict = field(default_factory=dict)
    """Timing / debug data for each pipeline stage."""


# ──────────────────────────────────────────────
# Translator class
# ──────────────────────────────────────────────

class BrailleTranslator:
    """
    Thread-safe (no mutable state beyond config) Braille translator.

    Parameters
    ----------
    default_grade:
        Which Braille grade to use when none is supplied per-call.
        Defaults to Grade 1 (uncontracted) per PRD.
    """

    def __init__(self, default_grade: BrailleGrade = BrailleGrade.GRADE_1) -> None:
        self.default_grade = default_grade
        self._available = _LOUIS_AVAILABLE

        if not self._available:
            logger.warning("Using ASCII-Braille fallback (liblouis not installed).")

    # ── public API ─────────────────────────────

    def translate(
        self,
        text: str,
        grade: Optional[BrailleGrade] = None,
    ) -> TranslationResult:
        """
        Translate *text* → Braille.

        Parameters
        ----------
        text:
            Pre-normalized plain text (run through normalizer.py first).
        grade:
            Override the default grade for this call.

        Returns
        -------
        TranslationResult
        """
        grade = grade or self.default_grade

        if not text.strip():
            return TranslationResult(
                original_text=text,
                braille="",
                grade=grade,
                back_translation="",
                confidence=1.0,
            )

        if self._available:
            return self._translate_liblouis(text, grade)
        else:
            return self._translate_fallback(text, grade)

    def translate_incremental(
        self,
        tokens: list[str],
        grade: Optional[BrailleGrade] = None,
    ) -> list[TranslationResult]:
        """
        Translate a list of word/phrase tokens individually.
        Useful for streaming progressive Braille output as STT
        produces interim transcripts.

        Returns a list of TranslationResult, one per token.
        """
        return [self.translate(tok, grade) for tok in tokens if tok.strip()]

    def is_available(self) -> bool:
        """True if liblouis is installed and usable."""
        return self._available

    # ── private helpers ─────────────────────────

    def _translate_liblouis(self, text: str, grade: BrailleGrade) -> TranslationResult:
        """Use the real liblouis library."""
        tables = TABLES[grade]
        try:
            # louis.translate returns a tuple: (braille_str, …)
            braille = louis.translateString(tables, text)

            # Round-trip back-translation for confidence scoring.
            try:
                back = louis.backTranslateString(tables, braille)
            except Exception:
                back = ""

            confidence = _compute_confidence(text, back)

            return TranslationResult(
                original_text=text,
                braille=braille,
                grade=grade,
                back_translation=back,
                confidence=confidence,
                used_fallback=False,
            )

        except Exception as exc:
            logger.error("liblouis translation failed: %s — falling back.", exc)
            return self._translate_fallback(text, grade)

    def _translate_fallback(self, text: str, grade: BrailleGrade) -> TranslationResult:
        """Simple character-by-character ASCII-Braille map (no liblouis needed)."""
        braille = "".join(
            _ASCII_BRAILLE_MAP.get(ch, "⠿")  # ⠿ = unknown character indicator
            for ch in text.lower()
        )
        return TranslationResult(
            original_text=text,
            braille=braille,
            grade=grade,
            back_translation="",
            confidence=0.5,   # Always flag as uncertain for liblouis-less output
            used_fallback=True,
        )


# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────

def _compute_confidence(original: str, back_translation: str) -> float:
    """
    Simple round-trip confidence: compare lowercased, whitespace-normalised
    versions of the original and back-translated strings.

    Returns a float in [0.0, 1.0].
    """
    if not back_translation:
        return 0.8  # Translation succeeded but back-translation unavailable; still ok

    def clean(s: str) -> str:
        return re.sub(r"\s+", " ", s.strip().lower())

    orig_clean = clean(original)
    back_clean = clean(back_translation)

    if orig_clean == back_clean:
        return 1.0

    # Character-level overlap as partial credit.
    total = max(len(orig_clean), len(back_clean), 1)
    matches = sum(a == b for a, b in zip(orig_clean, back_clean))
    return round(matches / total, 3)


# ──────────────────────────────────────────────
# Module-level convenience singleton
# ──────────────────────────────────────────────

_default_translator: Optional[BrailleTranslator] = None


def get_translator(grade: BrailleGrade = BrailleGrade.GRADE_1) -> BrailleTranslator:
    """Return a module-level singleton translator (lazy-initialised)."""
    global _default_translator
    if _default_translator is None:
        _default_translator = BrailleTranslator(default_grade=grade)
    return _default_translator
