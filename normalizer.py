"""
normalizer.py
─────────────
Pre-processes raw STT transcript text before it is fed to liblouis.

liblouis expects clean, lightly-formatted text. Raw STT output can contain
run-together filler words, inconsistent spacing, spoken punctuation (e.g.
"dot" instead of "."), and informal contractions that we want to normalise
before handing off to the Braille translator.

Usage:
    from normalizer import Normalizer

    n = Normalizer()
    clean = n.normalize("umm so like  Hello World   !!!")
    # → "Hello World!"
"""

from __future__ import annotations

import logging
import re
import unicodedata
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# Configuration dataclass
# ──────────────────────────────────────────────

@dataclass
class NormalizerConfig:
    """Tunable parameters for the Normalizer."""

    strip_filler_words: bool = True
    """Remove common spoken fillers (umm, uh, like, you know, etc.)."""

    expand_spoken_punctuation: bool = True
    """
    Convert spoken punctuation phrases to symbols:
      "period"        → "."
      "comma"         → ","
      "question mark" → "?"
      "exclamation"   → "!"
      etc.
    """

    normalize_contractions: bool = True
    """
    Expand spoken contractions to their full forms.
    Helps liblouis produce consistent Braille output.
      "don't" → "do not"  (Grade 1 mode only; Grade 2 handles contractions natively)
    """

    max_length: int = 5000
    """Hard limit on input text length (chars). Longer inputs are truncated."""

    preserve_numbers: bool = True
    """
    Keep digit strings intact so liblouis can apply Braille numeric indicators.
    If False, numbers are humanised ("3" → "three") before translation.
    """


# ──────────────────────────────────────────────
# Default filler word list
# ──────────────────────────────────────────────

_FILLERS: list[str] = [
    r"\bumm+\b",
    r"\buhh*\b",
    r"\buh\b",
    r"\bhmm+\b",
    r"\blike\b",
    r"\byou know\b",
    r"\bso\b(?=\s)",   # "so " at word boundary but not inside words
    r"\bkind of\b",
    r"\bsort of\b",
    r"\bbasically\b",
    r"\bactually\b",
    r"\bright\b(?=\s+\b(?:so|and|but)\b)",  # "right so" / "right and"
    r"\bi mean\b",
    r"\bwell\b(?=\s)",
]

_FILLER_PATTERN = re.compile(
    "|".join(_FILLERS),
    flags=re.IGNORECASE,
)


# ──────────────────────────────────────────────
# Spoken punctuation → symbol
# ──────────────────────────────────────────────

_SPOKEN_PUNCT: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\bperiod\b", re.I),              "."),
    (re.compile(r"\bfull stop\b", re.I),           "."),
    (re.compile(r"\bcomma\b", re.I),               ","),
    (re.compile(r"\bquestion mark\b", re.I),        "?"),
    (re.compile(r"\bexclamation(?: mark|point)?\b", re.I), "!"),
    (re.compile(r"\bcolon\b", re.I),               ":"),
    (re.compile(r"\bsemicolon\b", re.I),           ";"),
    (re.compile(r"\bdash\b", re.I),                "—"),
    (re.compile(r"\bhyphen\b", re.I),              "-"),
    (re.compile(r"\bellipsis\b", re.I),            "…"),
    (re.compile(r"\bnew line\b", re.I),            "\n"),
    (re.compile(r"\bnew paragraph\b", re.I),       "\n\n"),
    (re.compile(r"\bopen (?:paren(?:thesis)?|bracket)\b", re.I), "("),
    (re.compile(r"\bclose (?:paren(?:thesis)?|bracket)\b", re.I), ")"),
    (re.compile(r"\bopen quote\b", re.I),          "\u201c"),  # "
    (re.compile(r"\bclose quote\b", re.I),         "\u201d"),  # "
]


# ──────────────────────────────────────────────
# Contraction expansion (Grade 1 / plain text)
# ──────────────────────────────────────────────

_CONTRACTIONS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\bcan't\b", re.I),       "cannot"),
    (re.compile(r"\bwon't\b", re.I),       "will not"),
    (re.compile(r"\bdon't\b", re.I),       "do not"),
    (re.compile(r"\bdidn't\b", re.I),      "did not"),
    (re.compile(r"\bdoesn't\b", re.I),     "does not"),
    (re.compile(r"\bisn't\b", re.I),       "is not"),
    (re.compile(r"\baren't\b", re.I),      "are not"),
    (re.compile(r"\bwasn't\b", re.I),      "was not"),
    (re.compile(r"\bweren't\b", re.I),     "were not"),
    (re.compile(r"\bshouldn't\b", re.I),   "should not"),
    (re.compile(r"\bwouldn't\b", re.I),    "would not"),
    (re.compile(r"\bcouldn't\b", re.I),    "could not"),
    (re.compile(r"\bhaven't\b", re.I),     "have not"),
    (re.compile(r"\bhasn't\b", re.I),      "has not"),
    (re.compile(r"\bhadn't\b", re.I),      "had not"),
    (re.compile(r"\bI'm\b", re.I),         "I am"),
    (re.compile(r"\bI've\b", re.I),        "I have"),
    (re.compile(r"\bI'll\b", re.I),        "I will"),
    (re.compile(r"\bI'd\b", re.I),         "I would"),
    (re.compile(r"\bthey're\b", re.I),     "they are"),
    (re.compile(r"\bthey've\b", re.I),     "they have"),
    (re.compile(r"\bthey'll\b", re.I),     "they will"),
    (re.compile(r"\bwe're\b", re.I),       "we are"),
    (re.compile(r"\bwe've\b", re.I),       "we have"),
    (re.compile(r"\bwe'll\b", re.I),       "we will"),
    (re.compile(r"\byou're\b", re.I),      "you are"),
    (re.compile(r"\byou've\b", re.I),      "you have"),
    (re.compile(r"\byou'll\b", re.I),      "you will"),
    (re.compile(r"\bhe's\b", re.I),        "he is"),
    (re.compile(r"\bshe's\b", re.I),       "she is"),
    (re.compile(r"\bit's\b", re.I),        "it is"),
    (re.compile(r"\bthat's\b", re.I),      "that is"),
    (re.compile(r"\bthere's\b", re.I),     "there is"),
    (re.compile(r"\bwhat's\b", re.I),      "what is"),
    (re.compile(r"\bwho's\b", re.I),       "who is"),
    (re.compile(r"\blet's\b", re.I),       "let us"),
]


# ──────────────────────────────────────────────
# Result dataclass
# ──────────────────────────────────────────────

@dataclass
class NormalizationResult:
    """Output of a normalization pass."""

    original: str
    """The raw STT text before any processing."""

    normalized: str
    """Cleaned text ready for liblouis."""

    changes: list[str]
    """Human-readable log of transformations applied (for debugging)."""

    was_truncated: bool = False
    """True if input exceeded max_length and was cut off."""


# ──────────────────────────────────────────────
# Normalizer class
# ──────────────────────────────────────────────

class Normalizer:
    """
    Stateless text normalizer for the Braille agent pipeline.

    All transformations are configurable via NormalizerConfig.
    """

    def __init__(self, config: Optional[NormalizerConfig] = None) -> None:
        self.config = config or NormalizerConfig()

    def normalize(self, text: str) -> NormalizationResult:
        """
        Run the full normalization pipeline on *text*.

        Pipeline steps (in order):
          1. Unicode normalisation (NFC)
          2. Length guard / truncation
          3. Expand spoken punctuation  (if enabled)
          4. Expand contractions        (if enabled)
          5. Strip filler words         (if enabled)
          6. Collapse whitespace
          7. Strip leading/trailing whitespace

        Returns NormalizationResult.
        """
        changes: list[str] = []
        cfg = self.config

        # ── 1. Unicode NFC ─────────────────────
        text_nfc = unicodedata.normalize("NFC", text)
        if text_nfc != text:
            changes.append("unicode_nfc")
        text = text_nfc

        # ── 2. Length guard ────────────────────
        truncated = False
        if len(text) > cfg.max_length:
            text = text[: cfg.max_length]
            truncated = True
            changes.append(f"truncated_to_{cfg.max_length}_chars")

        # ── 3. Spoken punctuation ──────────────
        if cfg.expand_spoken_punctuation:
            text, n = _apply_patterns(text, _SPOKEN_PUNCT)
            if n:
                changes.append(f"spoken_punct_expanded({n})")

        # ── 4. Contraction expansion ───────────
        if cfg.normalize_contractions:
            text, n = _apply_patterns(text, _CONTRACTIONS)
            if n:
                changes.append(f"contractions_expanded({n})")

        # ── 5. Filler words ────────────────────
        if cfg.strip_filler_words:
            new_text = _FILLER_PATTERN.sub("", text)
            if new_text != text:
                changes.append("fillers_removed")
            text = new_text

        # ── 6. Collapse whitespace ─────────────
        text = re.sub(r"[ \t]+", " ", text)          # horizontal whitespace
        text = re.sub(r"\n{3,}", "\n\n", text)        # max 2 blank lines
        text = re.sub(r" +([.,!?;:])", r"\1", text)   # spaces before punct

        # ── 7. Strip edges ─────────────────────
        text = text.strip()

        return NormalizationResult(
            original=unicodedata.normalize("NFC", text) if not text else text,
            normalized=text,
            changes=changes,
            was_truncated=truncated,
        )

    def normalize_text(self, text: str) -> str:
        """Convenience wrapper — returns just the normalized string."""
        return self.normalize(text).normalized


# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────

def _apply_patterns(
    text: str,
    patterns: list[tuple[re.Pattern, str]],
) -> tuple[str, int]:
    """
    Apply a list of (pattern, replacement) pairs to *text*.

    Returns (new_text, number_of_substitutions_made).
    """
    total = 0
    for pattern, replacement in patterns:
        new_text, count = pattern.subn(replacement, text)
        text = new_text
        total += count
    return text, total


# ──────────────────────────────────────────────
# Module-level singleton
# ──────────────────────────────────────────────

_default_normalizer: Optional[Normalizer] = None


def get_normalizer(config: Optional[NormalizerConfig] = None) -> Normalizer:
    """Return a module-level singleton normalizer (lazy-initialised)."""
    global _default_normalizer
    if _default_normalizer is None:
        _default_normalizer = Normalizer(config=config)
    return _default_normalizer
