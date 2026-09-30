"""Report scope notes that carry a norm, keyed by the id a `scope_note` norm names.

A scope note is the only thing a report prints for a system whose obligations this product does
not check. A norm that binds a supported operator only for such a system reaches the reader here,
so the note must state that norm's enacted text; `norm_traceability` checks it does.
"""

from __future__ import annotations

SECTION_B = "AIA-SCOPE-NOTE-SECTION-B"

# A Section B system is high-risk and owes no Chapter III. Both halves have to be said, or the
# empty findings list reads as a clean bill of health rather than a scope limit.
SCOPE_NOTES: dict[str, str] = {
    SECTION_B: (
        "High-risk under Art. 6(1), but Chapter III was NOT checked: this system is a safety "
        "component of a product covered by Annex I Section B ({products}). Under "
        "Art. 2(2) only Art. 6(1), Art. 60a and Arts. 102-112 of this Regulation apply to such a "
        "system, plus Arts. 57 to 59 on sandboxes where the high-risk requirements have been "
        "integrated into that sectoral legislation — the requirements of Art. 9-15 and the "
        "provider obligations of Art. 16 onward do not. Its safety duties come from that sectoral "
        "legislation instead, which is outside this tool's scope. ART. 60a IS THE ONE THAT STILL "
        "BITES HERE: if this system is tested in real world conditions, the Member State "
        "framework allowing that must under "
        "Art. 60a(5)(b) ensure compliance with Art. 60(2), (3), (4)(d) to (j) and (5) to (9). "
        "Those conditions reach the provider through national law rather than through this "
        "Regulation, so no obligation for them is listed above — confirm them separately. "
        'Art. 60a(6) adds: "The real-world testing shall comply with the applicable provisions '
        'laid down in the Union harmonisation legislation listed in Section B of Annex I."'
    ),
}


def section_b_note(products: list[str]) -> str:
    return SCOPE_NOTES[SECTION_B].format(products=", ".join(products))
