"""Sandbox duties, powers and protections retain their own actors and triggers."""

import pytest

from aiact.norm_loader import load_normative_coverage


def _texts(expression) -> list[str]:
    """The enacted words of a condition expression, leaf by leaf in order."""
    texts: list[str] = []
    for operand in expression.operands:
        texts += _texts(operand) if hasattr(operand, "operands") else [operand.text]
    return texts


@pytest.fixture(scope="module")
def norms():
    return {
        norm.norm_id.removeprefix("AIA-NORM-A057-"): norm
        for norm in load_normative_coverage().norm_inventory.norms
        if norm.norm_id.startswith("AIA-NORM-A057-")
    }


def test_establishment_powers_are_not_cooperation_or_access_duties(norms):
    for prefix, actor in (
        ("P3-EDPS", "european_data_protection_supervisor"),
        ("P3A-AI-OFFICE", "ai_office"),
    ):
        power = norms[f"{prefix}-SANDBOX"]
        substitution = norms[f"{prefix}-AUTHORITY-REFERENCES"]
        assert power.kind.value == "power"
        assert substitution.kind.value == "legal_consequence"
        assert power.actors[0].actor_ref == substitution.actors[0].actor_ref == actor
        assert "this Chapter" in substitution.action
        assert substitution.conditions
    power = norms["P3A-AI-OFFICE-SANDBOX"]
    assert "Article 75(1)" in power.action
    assert "Member States' competence to establish and supervise" in power.action
    assert power.qualifier_spans == ["AIA-TEXT-A057-P006"]
    assert not power.mandatory_content
    for suffix in ("COOPERATE-WITH-AUTHORITIES", "PRIORITY-ACCESS"):
        duty = norms[f"P3A-{suffix}"]
        assert duty.kind.value == "obligation"
        assert duty.actors[0].actor_ref == "ai_office"
        assert _texts(duty.conditions) == [
            "The AI Office may establish an AI regulatory sandbox at Union level for AI systems "
            "covered by Article 75(1)"
        ]
    assert "other Union-law compliance" in norms["P3A-COOPERATE-WITH-AUTHORITIES"].action
    assert "SMEs, including start-ups, and SMCs" in norms["P3A-PRIORITY-ACCESS"].action


def test_resources_cooperation_permission_and_savings_have_distinct_effects(norms):
    resources = norms["P4-RESOURCE-AND-AUTHORITY-COORDINATION"]
    assert resources.actors[0].actor_ref == "member_state"
    assert "paragraph 1 and 2" in resources.action
    assert "effective and timely" in resources.action
    assert not resources.mandatory_content
    cooperation = norms["P4-AUTHORITY-COOPERATION"]
    involvement = norms["P4-INVOLVE-ECOSYSTEM-ACTORS"]
    assert cooperation.kind.value == "obligation"
    assert involvement.kind.value == "permission"
    assert cooperation.actors[0].actor_ref == "national_competent_authority"
    assert involvement.actors == cooperation.actors
    assert cooperation.conditions == involvement.conditions
    assert _texts(cooperation.conditions) == ["Where appropriate"]
    assert norms["P4-PRESERVE-OTHER-SANDBOXES"].kind.value == "legal_consequence"
    other = norms["P4-INTER-SANDBOX-COOPERATION"]
    assert other.actors[0].actor_ref == "member_state"
    assert "other Union or national-law sandboxes" in other.action


def test_real_world_testing_is_optional_and_its_plan_only_applies_conditionally(norms):
    lifecycle = norms["P5-CONTROLLED-SANDBOX-LIFECYCLE"]
    assert len(lifecycle.mandatory_content) == 4
    assert "development, training, testing and validation" in lifecycle.mandatory_content[0]
    assert "before placing on the market or putting into service" in lifecycle.mandatory_content[1]
    assert "providers or prospective providers" in lifecycle.mandatory_content[2]
    assert lifecycle.mandatory_content[3] == "appropriate safeguards"
    testing = norms["P5-SUPERVISED-REAL-WORLD-TESTING"]
    assert testing.kind.value == "permission"
    assert "supervised" in testing.action
    plan = norms["P5-INCORPORATE-TESTING-PLAN"]
    assert plan.kind.value == "obligation"
    assert _texts(plan.conditions) == ["Where applicable"]


def test_written_proof_is_requested_but_exit_report_is_not(norms):
    proof = norms["P7-SANDBOX-EVIDENCE-PACKAGE"]
    report = norms["P7-EXIT-REPORT"]
    assert _texts(proof.conditions) == [
        "Upon request of the provider or prospective provider of the AI system"
    ]
    assert "successfully carried out" in proof.action
    assert not report.conditions
    assert report.mandatory_content == [
        "activities carried out in the sandbox",
        "related results",
        "learning outcomes",
    ]
    assert not proof.mandatory_content
    assert proof.primary_spans == report.primary_spans == ["AIA-TEXT-A057-P011"]
    use = norms["P7-EVIDENTIARY-USE"]
    assert use.kind.value == "permission"
    assert use.actors[0].actor_ref == "provider"
    assert "conformity assessment or relevant market surveillance" in use.action
    for suffix, actor, category in (
        ("SURVEILLANCE", "market_surveillance_authority", "public_authority"),
        ("NOTIFIED-BODY", "notified_body", "notified_or_conformity_body"),
    ):
        duty = norms[f"P7-{suffix}-EVIDENCE-CONSIDERATION"]
        assert duty.kind.value == "obligation"
        assert duty.actors[0].actor_ref == actor
        assert duty.actors[0].category.value == category
        assert "positively into account" in duty.action
        assert "reasonably accelerating" in duty.action


def test_report_access_consideration_and_public_release_do_not_share_one_gate(norms):
    access = norms["P8-EXIT-REPORT-ACCESS"]
    consideration = norms["P8-CONSIDER-EXIT-REPORTS"]
    publication = norms["P8-PUBLIC-EXIT-REPORT"]
    assert access.kind.value == "permission"
    assert consideration.kind.value == "obligation"
    assert publication.kind.value == "permission"
    assert access.actors == consideration.actors
    assert [actor.actor_ref for actor in access.actors] == ["commission", "board"]
    assert _texts(access.conditions) == [
        "Subject to the confidentiality provisions in Article 78",
        "with the agreement of the provider or prospective provider",
    ]
    assert _texts(consideration.conditions) == [*_texts(access.conditions), "as appropriate"]
    assert _texts(publication.conditions) == [
        "If both the provider or prospective provider and the national competent authority "
        "explicitly agree",
        "Subject to the confidentiality provisions in Article 78",
    ]
    assert "single information platform" in publication.action


def test_mitigation_does_not_make_suspension_mandatory_or_gate_all_supervision(norms):
    preservation = norms["P11-PRESERVE-SUPERVISORY-POWERS"]
    assert preservation.kind.value == "legal_consequence"
    assert "regional and local" in preservation.action
    mitigation = norms["P11-SUPERVISORY-MITIGATION-WORKFLOW"]
    suspension = norms["P11-SUSPEND-TESTING-OR-PARTICIPATION"]
    notification = norms["P11-NOTIFY-SUSPENSION"]
    discretion = norms["P11-LAWFUL-SUPERVISORY-DISCRETION"]
    assert mitigation.kind.value == "obligation"
    assert "significant risks" in _texts(mitigation.conditions)[0]
    assert "suspend" not in mitigation.action
    assert suspension.kind.value == "power"
    assert _texts(suspension.conditions)[-1] == "if no effective mitigation is possible"
    assert "temporarily or permanently" in suspension.action
    assert "testing or participation" in suspension.action
    assert notification.kind.value == "obligation"
    # Notifying follows the same trigger as the suspension it reports.
    assert notification.conditions == suspension.conditions
    assert "AI Office" in notification.action
    assert discretion.kind.value == "obligation"
    assert not discretion.conditions
    assert "within relevant law" in discretion.action
    assert "specific sandbox project" in discretion.action
    assert "supporting AI innovation" in discretion.action


def test_liability_and_two_no_fine_protections_preserve_different_conditions(norms):
    liability = norms["P12-LIABILITY-AND-FINE-SAFE-HARBOUR"]
    ai_act = norms["P12-AI-ACT-NO-FINE-PROTECTION"]
    other_law = norms["P12-OTHER-LAW-NO-FINE-PROTECTION"]
    assert all(n.kind.value == "legal_consequence" for n in (liability, ai_act, other_law))
    assert [actor.actor_ref for actor in liability.actors] == ["provider", "prospective_provider"]
    assert "third-party damage resulting from sandbox experimentation" in liability.action
    assert not any("guidance" in text for text in _texts(liability.conditions))
    # The pinned text specifically says prospective providers for the AI Act safe harbour.
    assert ai_act.actors[0].actor_ref == "prospective_provider"
    assert _texts(ai_act.conditions) == [
        "provided that the prospective providers observe the specific plan and the terms and "
        "conditions for their participation and follow in good faith the guidance given by the "
        "national competent authority"
    ]
    assert "infringements of this Regulation" in ai_act.action
    assert _texts(other_law.conditions) == [
        "Providers and prospective providers participating in the AI regulatory sandbox",
        "Where other competent authorities responsible for other Union and national law were "
        "actively involved in the supervision of the AI system in the sandbox and provided "
        "guidance for compliance",
    ]
    assert "other Union or national law" in other_law.action


def test_board_coordination_is_required_but_joint_sandbox_support_is_optional(norms):
    duty = norms["P14-COORDINATE-SANDBOX-ACTIVITIES"]
    support = norms["P14-SUPPORT-JOINT-SANDBOXES"]
    assert duty.kind.value == "obligation"
    assert support.kind.value == "permission"
    assert duty.actors == support.actors
    assert "Board" in duty.action
    assert "as appropriate" in duty.conditions[0]
    assert "respective competences" in duty.conditions[0]
    assert "including across sectors" in support.action
    assert "exchange related best practices" in support.action


def test_notification_support_requests_and_public_list_belong_to_the_right_actors(norms):
    notice = norms["P15-NOTIFY-AND-LIST-SANDBOXES"]
    support = norms["P15-REQUEST-SUPPORT"]
    listing = norms["P15-PUBLIC-SANDBOX-LIST"]
    assert notice.kind.value == listing.kind.value == "obligation"
    assert support.kind.value == "permission"
    assert notice.actors == support.actors
    assert notice.actors[0].actor_ref == "national_competent_authority"
    assert "AI Office and the Board" in notice.action
    assert "AI Office and the Board" in support.action
    assert listing.actors[0].actor_ref == "ai_office"
    assert listing.actors[0].category.value == "union_institution_or_body"
    assert "publish and keep current" in listing.action
    assert "planned and existing" in listing.action


def test_reporting_lifecycle_publication_and_commission_use_are_separate(norms):
    annual = norms["P16-SANDBOX-REPORTING"]
    publication = norms["P16-PUBLISH-ANNUAL-REPORTS"]
    consideration = norms["P16-COMMISSION-REPORT-CONSIDERATION"]
    assert "from one year after sandbox establishment" in annual.action
    assert "every year thereafter until termination" in annual.action
    assert "final report" in annual.action
    assert "AI Office and the Board" in annual.action
    assert len(annual.mandatory_content) == 8
    assert annual.mandatory_content[:5] == [
        "implementation progress and results",
        "best practices",
        "incidents",
        "lessons learnt",
        "recommendations on sandbox setup",
    ]
    assert "application and possible revision" in annual.mandatory_content[5]
    assert "delegated and implementing acts" in annual.mandatory_content[5]
    assert "where relevant" in annual.mandatory_content[6]
    assert "other Union law supervised" in annual.mandatory_content[6]
    assert annual.mandatory_content[7] == "submit a final report when the sandbox terminates"
    assert publication.actors == annual.actors
    assert annual.actors[0].actor_ref == "national_competent_authority"
    assert "annual sandbox reports or abstracts" in publication.action
    assert "online" in publication.action
    assert consideration.actors[0].actor_ref == "commission"
    assert consideration.conditions == ["where appropriate"]
    assert "annual sandbox reports" in consideration.action


def test_information_interface_does_not_swallow_conditional_coordination(norms):
    interface = norms["P17-SINGLE-INFORMATION-INTERFACE"]
    coordination = norms["P17-PROACTIVE-AUTHORITY-COORDINATION"]
    assert "Article 62(1)(c)" in interface.action
    assert len(interface.mandatory_content) == 4
    assert "non-binding" in interface.mandatory_content[3]
    assert "products, services and business models" in interface.mandatory_content[3]
    assert not interface.conditions
    assert coordination.actors == interface.actors
    assert coordination.actors[0].actor_ref == "commission"
    assert coordination.conditions == ["where relevant"]
    assert "proactively coordinate with national competent authorities" == coordination.action


def test_corrections_remain_proposed_and_do_not_invent_runtime_coverage(norms):
    assert len(norms) == 49
    # The one operator route, using sandbox documentation as evidence, is reported beside the
    # conformity-assessment rules; every other Article 57 norm binds an authority.
    evidence = norms["P7-EVIDENTIARY-USE"]
    assert evidence.implementation_mode.value == "report_only"
    assert evidence.review.verified_by
    for norm in norms.values():
        assert norm.primary_spans[0].startswith("AIA-TEXT-A057-")
        if norm is evidence:
            continue
        assert norm.review.status.value == "proposed"
        assert norm.implementation_mode.value == "none_required"
        assert not norm.implementation_refs
        assert norm.product_scope.value in {"outside_supported_actor", "no_product_action"}
