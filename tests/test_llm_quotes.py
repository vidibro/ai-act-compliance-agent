"""`verbatim` — the one check standing between a citation and a plausible sentence.

Both layers ask a model to copy the span that drove its answer, and a model asked to copy will
sometimes write instead. The failure is quiet by construction: an invented quote reads exactly like
a real one, and the reviewer it misleads is the person the tool exists to help.

The two halves of this file are the two ways the check can be wrong, and they pull against each
other. Rejecting a real quote over a reflowed line break throws away evidence we have; accepting a
paraphrase because it is "close" is the whole failure being guarded against. So: forgiving about
form, unforgiving about words.
"""

from aiact.llm import verbatim

SOURCE = (
    "## Human oversight\n\n"
    "A panel of two managers reviews every recommendation before it reaches the candidate.\n\n"
    "Reviewers may override the score — the system's output is advisory.\n"
)


# --- forgiving about form -----------------------------------------------------------------------
def test_an_exact_span_is_kept():
    quote = "A panel of two managers reviews every recommendation"
    assert verbatim(quote, SOURCE) == quote


def test_a_reflowed_quote_survives():
    """Models rewrap text. The words are the evidence; the line breaks are not."""
    assert verbatim("A panel of two managers\n   reviews every recommendation", SOURCE) is not None


def test_a_recased_quote_survives():
    """A model that capitalises a mid-sentence fragment has still copied the passage."""
    assert verbatim("Reviewers May Override The Score", SOURCE) is not None


def test_typographic_punctuation_is_folded():
    """Curly quotes and dashes drift in both directions between a document and a model reply. A
    real quote must not be thrown away over a dash."""
    assert verbatim("Reviewers may override the score -- ", SOURCE) is None  # different words
    assert verbatim("override the score — the system's output", SOURCE) is not None
    assert verbatim("override the score - the system's output", SOURCE) is not None


def test_wrapping_quote_marks_are_stripped():
    """The model quoting its own quote is packaging, not content."""
    assert verbatim('"A panel of two managers"', SOURCE) == "A panel of two managers"


# --- unforgiving about words --------------------------------------------------------------------
def test_a_paraphrase_is_dropped():
    """The exact failure this exists for: fluent, on-topic, and not in the document. Nothing about
    it looks wrong to a reader who does not go back to the source."""
    assert verbatim("Two managers review each recommendation", SOURCE) is None


def test_an_invented_span_is_dropped():
    assert verbatim("Accuracy was measured at 94% on a held-out set.", SOURCE) is None


def test_an_unmarked_stitch_is_dropped():
    """Two real halves the source never joined, presented as though it did. Stitching manufactures
    a claim out of true parts — here, one panel that overrides, from two separate sentences."""
    assert verbatim("A panel of two managers may override the score", SOURCE) is None


def test_a_marked_elision_is_kept():
    """The same two halves WITH the cut marked. Ordinary citation practice, and the reader can
    still check both ends — which is the whole difference from the stitch above."""
    assert verbatim("A panel of two managers ... override the score", SOURCE) is not None
    assert verbatim("A panel of two managers … override the score", SOURCE) is not None


def test_an_elision_may_not_reorder_the_source():
    """Fragments are searched forward from where the last one ended, so an elision cannot quietly
    reverse two passages. Order carries meaning: what follows what is part of what a text says."""
    assert verbatim("override the score ... A panel of two managers", SOURCE) is None


def test_an_elided_fragment_still_has_to_be_real():
    """The marker licenses a CUT, not an insertion. One real end and one invented one is still an
    invented quote."""
    assert verbatim("A panel of two managers ... escalate to the hiring committee", SOURCE) is None


# --- non-answers --------------------------------------------------------------------------------
def test_a_non_string_is_not_a_quote():
    """Straight off parsed JSON, so null, a number or a list are all reachable."""
    for value in (None, 42, ["a panel of two managers"], {}):
        assert verbatim(value, SOURCE) is None


def test_an_empty_or_blank_quote_is_dropped():
    """`"" in anything` is True — the one input that would sail through a naive substring check."""
    assert verbatim("", SOURCE) is None
    assert verbatim("   \n  ", SOURCE) is None
    assert verbatim('""', SOURCE) is None
