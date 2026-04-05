"""
tests/test_translator.py
────────────────────────
Unit tests for braille_translator.py and normalizer.py.

Run with:
    cd "/Users/ved/Documents/Epics_Dicated Note Printer/Voice_Assistant"
    source venv/bin/activate
    python -m pytest tests/ -v
"""

from normalizer import Normalizer, NormalizerConfig, NormalizationResult
from braille_translator import BrailleTranslator, BrailleGrade, TranslationResult
import sys
import os

# ── Make sure project root is on the path ──────────────────────────────────────
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ==============================================================================
# BrailleTranslator tests
# ==============================================================================

class TestBrailleTranslator:
    """Tests for BrailleTranslator — run against either liblouis or the fallback."""

    def setup_method(self):
        self.tr = BrailleTranslator(default_grade=BrailleGrade.GRADE_1)

    # ── Basic return types ─────────────────────────────────────────────────────

    def test_translate_returns_result_object(self):
        result = self.tr.translate("hello")
        assert isinstance(result, TranslationResult)

    def test_translate_empty_string(self):
        result = self.tr.translate("")
        assert result.braille == ""
        assert result.confidence == 1.0

    def test_translate_whitespace_only(self):
        result = self.tr.translate("   ")
        assert result.braille == ""

    # ── Output content ─────────────────────────────────────────────────────────

    def test_translate_produces_nonempty_braille(self):
        result = self.tr.translate("hello")
        assert len(result.braille) > 0

    def test_translate_preserves_grade(self):
        r1 = self.tr.translate("hello", grade=BrailleGrade.GRADE_1)
        r2 = self.tr.translate("hello", grade=BrailleGrade.GRADE_2)
        assert r1.grade == BrailleGrade.GRADE_1
        assert r2.grade == BrailleGrade.GRADE_2

    def test_translate_single_letter_a(self):
        result = self.tr.translate("a")
        # Braille for 'a' in the fallback map or liblouis should be ⠁
        assert "⠁" in result.braille or result.used_fallback

    def test_translate_alphabet(self):
        for ch in "abcdefghijklmnopqrstuvwxyz":
            result = self.tr.translate(ch)
            assert len(result.braille) > 0, f"Empty output for '{ch}'"

    def test_translate_number(self):
        result = self.tr.translate("123")
        assert len(result.braille) > 0

    def test_translate_sentence(self):
        result = self.tr.translate("The quick brown fox")
        assert len(result.braille) > 0

    def test_translate_punctuation(self):
        for punct in [".", ",", "!", "?"]:
            result = self.tr.translate(punct)
            assert len(result.braille) > 0, f"Empty output for '{punct}'"

    # ── Confidence ─────────────────────────────────────────────────────────────

    def test_confidence_is_float_in_range(self):
        result = self.tr.translate("hello world")
        assert 0.0 <= result.confidence <= 1.0

    # ── Incremental ────────────────────────────────────────────────────────────

    def test_translate_incremental_returns_list(self):
        results = self.tr.translate_incremental(["hello", "world"])
        assert isinstance(results, list)
        assert len(results) == 2
        assert all(isinstance(r, TranslationResult) for r in results)

    def test_translate_incremental_skips_empty_tokens(self):
        results = self.tr.translate_incremental(["hello", "", "  ", "world"])
        assert len(results) == 2

    # ── availability ───────────────────────────────────────────────────────────

    def test_is_available_returns_bool(self):
        assert isinstance(self.tr.is_available(), bool)


# ==============================================================================
# Normalizer tests
# ==============================================================================

class TestNormalizer:
    """Tests for Normalizer — not dependent on liblouis."""

    def setup_method(self):
        self.n = Normalizer()

    def test_normalize_returns_result_object(self):
        r = self.n.normalize("hello")
        assert isinstance(r, NormalizationResult)

    def test_normalize_plain_text_unchanged(self):
        r = self.n.normalize("Hello world")
        assert r.normalized == "Hello world"

    def test_normalize_collapses_whitespace(self):
        r = self.n.normalize("Hello  World")
        assert r.normalized == "Hello World"

    def test_normalize_strips_edges(self):
        r = self.n.normalize("  hello  ")
        assert r.normalized == "hello"

    def test_normalize_fillers_removed(self):
        r = self.n.normalize("umm hello uh world")
        assert "umm" not in r.normalized
        assert "uh" not in r.normalized

    def test_normalize_spoken_period(self):
        r = self.n.normalize("hello period")
        assert "." in r.normalized
        assert "period" not in r.normalized

    def test_normalize_spoken_comma(self):
        r = self.n.normalize("apples comma oranges")
        assert "," in r.normalized

    def test_normalize_spoken_question_mark(self):
        r = self.n.normalize("how are you question mark")
        assert "?" in r.normalized

    def test_normalize_spoken_exclamation(self):
        r = self.n.normalize("wow exclamation mark")
        assert "!" in r.normalized

    def test_normalize_contraction_dont(self):
        r = self.n.normalize("I don't know")
        assert "do not" in r.normalized

    def test_normalize_contraction_cant(self):
        r = self.n.normalize("I can't do it")
        assert "cannot" in r.normalized

    def test_normalize_contraction_wont(self):
        r = self.n.normalize("I won't go")
        assert "will not" in r.normalized

    def test_normalize_contraction_its(self):
        r = self.n.normalize("it's raining")
        assert "it is" in r.normalized.lower()

    def test_normalize_truncation(self):
        long_text = "a" * 6000
        cfg = NormalizerConfig(max_length=5000)
        n = Normalizer(config=cfg)
        r = n.normalize(long_text)
        assert len(r.normalized) <= 5000
        assert r.was_truncated is True

    def test_normalize_no_truncation_short(self):
        r = self.n.normalize("short text")
        assert r.was_truncated is False

    def test_normalize_changes_list(self):
        r = self.n.normalize("umm hello uh world period")
        assert isinstance(r.changes, list)

    def test_normalize_empty_string(self):
        r = self.n.normalize("")
        assert r.normalized == ""

    def test_normalize_text_convenience(self):
        result = self.n.normalize_text("hello period")
        assert isinstance(result, str)
        assert "." in result

    def test_normalize_unicode_nfc(self):
        # NFC normalisation should not break plain ASCII
        r = self.n.normalize("caf\u00e9")  # café
        assert r.normalized == "café"

    def test_filler_disabled(self):
        cfg = NormalizerConfig(strip_filler_words=False)
        n = Normalizer(config=cfg)
        r = n.normalize("umm hello")
        assert "umm" in r.normalized

    def test_spoken_punct_disabled(self):
        cfg = NormalizerConfig(expand_spoken_punctuation=False)
        n = Normalizer(config=cfg)
        r = n.normalize("hello period")
        assert "period" in r.normalized

    def test_contractions_disabled(self):
        cfg = NormalizerConfig(normalize_contractions=False)
        n = Normalizer(config=cfg)
        r = n.normalize("I can't do it")
        assert "can't" in r.normalized


# ==============================================================================
# Integration: normalizer → translator
# ==============================================================================

class TestPipeline:
    """Sanity-check the normalizer → translator chain."""

    def setup_method(self):
        self.normalizer = Normalizer()
        self.translator = BrailleTranslator()

    def test_pipeline_hello_world(self):
        text = "umm hello period world"
        normalized = self.normalizer.normalize_text(text)
        result = self.translator.translate(normalized)
        assert len(result.braille) > 0

    def test_pipeline_produces_no_exception(self):
        sentences = [
            "The quick brown fox jumps over the lazy dog period",
            "can't stop won't stop",
            "1 2 3 go",
            "umm uh like you know",
            "",
        ]
        for s in sentences:
            normalized = self.normalizer.normalize_text(s)
            # Should never raise
            result = self.translator.translate(normalized)
            assert result is not None
