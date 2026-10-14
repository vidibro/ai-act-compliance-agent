"""What each role means, for the page to show beside a role's name.

A role the Act defines gets its Article 3 definition, word for word from the stored text of the
pinned version. A role the report uses that Article 3 does not define gets a short summary of where
the Act sets it up, marked as a summary so a reader never takes it for enacted wording.
"""

from __future__ import annotations

import re
from functools import lru_cache

from pydantic import BaseModel

from aiact.config import get_settings
from aiact.policy_loader import articles_dir_for, provision_text
from aiact.schemas.enums import ActorRole

# A point of Article 3 opens a line: "(3) ‘provider’ means ...". Its sub-points, if any, follow on
# lines of their own until the next point.
_POINT = re.compile(r"^\s*\((\d+[a-z]?)\) ‘([^’]+)’", re.MULTILINE)
_NUMBER = re.compile(r"^\(\d+[a-z]?\)\s*")

# Roles the report uses that Article 3 does not define, with where the Act sets each one up.
_SUMMARIES: dict[str, tuple[str, str]] = {
    "initial_provider": (
        "Art. 25(2)",
        "The provider that first placed the AI system on the market or put it into service, where "
        "another party has since become its provider under Art. 25(1) — by putting its name on it, "
        "substantially modifying it, or changing its intended purpose. It must cooperate with the "
        "new provider.",
    ),
    "prospective_provider": (
        "Arts. 57 to 60",
        "A provider developing an AI system it has not yet placed on the market, who tests it in "
        "an AI regulatory sandbox or in real world conditions.",
    ),
    "sandbox_participant": (
        "Arts. 57 and 58",
        "A provider or prospective provider taking part in an AI regulatory sandbox under the "
        "supervision of a competent authority.",
    ),
    "product_manufacturer": (
        "Art. 25(3)",
        "The manufacturer of a product covered by the Union laws in Annex I, Section A, that "
        "places a high-risk AI system on the market or into service together with its product and "
        "under its own name or trademark. It is then treated as the system's provider.",
    ),
    "gpai_provider": (
        "Art. 3(3) and 3(63)",
        "A provider of a general-purpose AI model: whoever develops the model, or has it "
        "developed, and places it on the market under its own name or trademark.",
    ),
    "civil_protection_authority": (
        "Art. 46(2)",
        "A public authority responsible for civil protection. In a duly justified urgent situation "
        "it may put a high-risk AI system into service before it is authorised, and must request "
        "the authorisation without undue delay.",
    ),
    "judicial_authority": (
        "Art. 5(3)",
        "A court or other judicial body of a Member State, such as the one that authorises each "
        "use of real-time remote biometric identification for law enforcement.",
    ),
    "independent_administrative_authority": (
        "Art. 5(3)",
        "A Member State authority, independent of the one using the system, whose decision is "
        "binding — the alternative to a judicial authority for authorising real-time remote "
        "biometric identification.",
    ),
}


class RoleDefinition(BaseModel):
    citation: str
    """Where the meaning comes from, e.g. "Art. 3(3)"."""
    text: str
    defined: bool
    """True for the Act's own definition; False for a summary of where the Act sets the role up."""


def _article_3_points(text: str) -> dict[str, str]:
    """Each defined term of Article 3 and its full definition, sub-points included."""
    matches = list(_POINT.finditer(text))
    return {
        match.group(2): " ".join(
            line.strip()
            for line in text[match.start() : nxt.start() if nxt else len(text)].splitlines()
            if line.strip()
        )
        for match, nxt in zip(matches, [*matches[1:], None], strict=True)
    }


@lru_cache(maxsize=1)
def role_definitions() -> dict[str, RoleDefinition]:
    """Every role the report can tag a provision with that has a meaning to show."""
    text = provision_text(articles_dir_for(get_settings().act_version_date) / "article-003.md")
    points = _article_3_points(text)
    numbers = {term: m.group(1) for m in _POINT.finditer(text) if (term := m.group(2))}
    definitions: dict[str, RoleDefinition] = {}
    for role in ActorRole:
        term = role.value.replace("_", " ")
        if term in points:
            definitions[role.value] = RoleDefinition(
                citation=f"Art. 3({numbers[term]})",
                text=_NUMBER.sub("", points[term], count=1),  # the citation carries the number
                defined=True,
            )
        elif role.value in _SUMMARIES:
            citation, summary = _SUMMARIES[role.value]
            definitions[role.value] = RoleDefinition(citation=citation, text=summary, defined=False)
    return definitions
