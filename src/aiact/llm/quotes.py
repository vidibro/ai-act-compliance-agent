"""Checking that a model's quote is a quote.

Both layers ask the model for an `evidence_quote`: the span of the source text that drove its
answer. Both then put that span in front of a human as the auditable part of a finding — the one
piece a reviewer can check without re-running anything.

Nothing made that span true. A model asked to copy will sometimes paraphrase, tidy, stitch two
passages together, or write the sentence the document *should* have contained. The result reads as
verbatim evidence and matches nothing, which is worse than no quote at all: it invites a reviewer to
confirm a finding against text that does not exist. On a PASS that is a clearance built on invented
evidence, the most expensive error this tool can make.

So a quote is checked against the source it claims to come from, and dropped when it is not there.
The ANSWER stands. That is a measured choice, not a soft one: on the Layer 1 dev split the model
invented nothing in 98 substantive answers, and every quote this check rejected was a citation-
formatting slip attached to a CORRECT answer. Escalating a bad quote to an abstention would have
discarded right answers to catch nothing — a gate whose only positives are false ones.

The match is deliberately forgiving about FORM and strict about CONTENT. Whitespace, letter case and
typographic punctuation are normalised away: a model that reflows a line break or straightens a
curly apostrophe has still copied the passage, and discarding real evidence over a dash helps
nobody. What no amount of normalising survives is different words, or a span assembled from places
the source never joined — which is the whole point.

An ELLIPSIS is honoured for the same reason, and it is not a loosening. Quoting the two ends of a
sentence and marking the cut is ordinary citation practice; models do it constantly, and on the
Layer 1 dev split every quote this check first rejected was a marked elision of real text rather
than an invention. What the marker buys is a claim the reader can still check: each fragment must
appear, and they must appear IN ORDER. An UNMARKED join stays a failure — the difference between
"A ... B" and "A B" is the difference between showing a reader that something was cut and letting
them believe the source runs the two together, which is how true fragments manufacture a false
claim.
"""

from __future__ import annotations

import re

# Typographic variants a model routinely swaps when copying. Folding them prevents a real quote from
# being thrown away over a dash.
_TYPOGRAPHY = str.maketrans(
    {
        "‘": "'",
        "’": "'",
        "“": '"',
        "”": '"',
        "–": "-",
        "—": "-",
        " ": " ",
    }
)

# Quote marks the model wraps its own answer in. Stripped from the ends before matching, since they
# are packaging rather than part of the span.
_WRAPPERS = "\"'“”‘’ \t\n"

# The cut a model marks when it quotes around something: "..." or a single ellipsis character.
_ELLIPSIS = re.compile(r"\s*(?:\.{3,}|…)\s*")


def _flatten(text: str) -> str:
    return " ".join(text.translate(_TYPOGRAPHY).split()).casefold()


def verbatim(quote: object, source: str) -> str | None:
    """`quote` if every part of it really is in `source`, in the order given; otherwise None.

    One span unless the model marked a cut with an ellipsis, in which case each fragment either
    side must appear and the later ones must appear LATER — searching from where the previous
    fragment ended, never from the top. Without that, "B ... A" would pass on a source that says
    "A ... B", and a reversal can invert what a passage means.

    Takes `object` rather than `str` because it arrives from parsed JSON, where the model may have
    sent null, a number, or a list. Anything that is not usable text is simply not a quote.
    """
    if not isinstance(quote, str):
        return None
    cleaned = quote.strip(_WRAPPERS)
    if not cleaned:
        return None
    fragments = [f for f in (p.strip(_WRAPPERS) for p in _ELLIPSIS.split(cleaned)) if f]
    if not fragments:
        return None

    flat_source = _flatten(source)
    at = 0
    for fragment in fragments:
        flat = _flatten(fragment)
        found = flat_source.find(flat, at)
        if found < 0:
            return None
        at = found + len(flat)
    return cleaned
