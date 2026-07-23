"""Score a classification run against the Layer 1 answer key — on BOTH axes.

Two independent things are being judged, and merging them would hide the interesting one:

  RISK CLASS   — Art. 5 / Art. 6 cascade. prohibited / high_risk / not_high_risk / minimal.

  ART. 50      — the transparency obligation, which is a SEPARATE AXIS from the tier
                 (see ClassificationResult.transparency). A minimal-risk text generator can owe it
                 and a high-risk scorer can owe none, so it is never an input to the class and
                 must never be averaged into the class score either.
"""

from __future__ import annotations

from dataclasses import dataclass

from aiact.schemas.classification import ClassificationResult
from aiact.schemas.enums import RiskClass
from aiact.schemas.eval import ClassificationCase


@dataclass(frozen=True)
class CaseScore:
    """One case, judged on both axes."""

    case_id: str
    expected_class: RiskClass
    got_class: RiskClass
    expected_transparency: bool
    got_transparency: bool | None
    """None means the Art. 50 node produced no usable answer — an abstention, not a `false`."""

    @property
    def class_correct(self) -> bool:
        return self.expected_class == self.got_class

    @property
    def transparency_abstained(self) -> bool:
        return self.got_transparency is None

    @property
    def transparency_correct(self) -> bool:
        """An abstention is never correct — but see `transparency_abstained`, which is why it is
        reported apart from a wrong answer rather than lumped in with one."""
        return self.got_transparency is not None and (
            self.got_transparency == self.expected_transparency
        )


def score_case(case: ClassificationCase, result: ClassificationResult) -> CaseScore:
    answer = result.transparency
    # `value` is bool | None: None is an abstention here, NOT "no obligation". The Art. 50 question
    # is a bool question, so anything non-bool that reaches this point is treated as no answer.
    got = answer.value if answer is not None else None
    return CaseScore(
        case_id=case.case_id,
        expected_class=case.expected_risk_class,
        got_class=result.overall_risk_class,
        expected_transparency=case.expected_transparency_obligation,
        got_transparency=got if isinstance(got, bool) else None,
    )


@dataclass(frozen=True)
class RunScore:
    """Both axes over a whole run. Deliberately has no single combined accuracy property — an
    aggregate over two unrelated obligations is a number nobody can act on."""

    scores: list[CaseScore]

    @property
    def total(self) -> int:
        return len(self.scores)

    @property
    def class_correct(self) -> int:
        return sum(s.class_correct for s in self.scores)

    @property
    def transparency_correct(self) -> int:
        return sum(s.transparency_correct for s in self.scores)

    @property
    def transparency_abstained(self) -> int:
        return sum(s.transparency_abstained for s in self.scores)

    @property
    def transparency_false_positives(self) -> int:
        """Claimed an Art. 50 obligation where the answer key says none. Called out separately
        because over-triggering a transparency duty on everything is the failure mode that makes
        the node worthless while still scoring respectably — exactly what the smoke check saw."""
        return sum(
            s.got_transparency is True and s.expected_transparency is False for s in self.scores
        )

    @property
    def transparency_false_negatives(self) -> int:
        """Missed an Art. 50 obligation the answer key requires — the compliance-relevant miss."""
        return sum(
            s.got_transparency is False and s.expected_transparency is True for s in self.scores
        )

    def lines(self) -> list[str]:
        """Two axes, two lines, never one merged figure."""
        out = [
            f"risk-class accuracy : {self.class_correct}/{self.total}",
            f"art.50 accuracy     : {self.transparency_correct}/{self.total}"
            f"  (false-positive {self.transparency_false_positives},"
            f" false-negative {self.transparency_false_negatives},"
            f" abstained {self.transparency_abstained})",
        ]
        expected_any = sum(s.expected_transparency for s in self.scores)
        got_any = sum(s.got_transparency is True for s in self.scores)
        if expected_any and got_any == self.total:
            out.append(
                "  ! art.50 answered TRUE on every case — a node that always says yes scores "
                "whatever the base rate is and discriminates nothing. Treat as unmeasured."
            )
        return out


def score_run(pairs: list[tuple[ClassificationCase, ClassificationResult]]) -> RunScore:
    return RunScore([score_case(case, result) for case, result in pairs])
