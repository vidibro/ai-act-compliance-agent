"""Sandbox duties, powers and protections retain their own actors and triggers."""

import pytest

from aiact.norm_loader import load_normative_coverage


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
        assert power.subjects[0].subject_ref == substitution.subjects[0].subject_ref == actor
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
        assert duty.subjects[0].subject_ref == "ai_office"
        assert duty.conditions == ["the AI Office establishes the sandbox under paragraph 3a"]
    assert "other Union-law compliance" in norms["P3A-COOPERATE-WITH-AUTHORITIES"].action
    assert "SMEs, including start-ups, and SMCs" in norms["P3A-PRIORITY-ACCESS"].action


def test_resources_cooperation_permission_and_savings_have_distinct_effects(norms):
    resources = norms["P4-RESOURCE-AND-AUTHORITY-COORDINATION"]
    assert resources.subjects[0].subject_ref == "member_state"
    assert "paragraph 1 and 2" in resources.action
    assert "effective and timely" in resources.action
    assert not resources.mandatory_content
    cooperation = norms["P4-AUTHORITY-COOPERATION"]
    involvement = norms["P4-INVOLVE-ECOSYSTEM-ACTORS"]
    assert cooperation.kind.value == "obligation"
    assert involvement.kind.value == "permission"
    assert cooperation.subjects[0].subject_ref == "national_competent_authority"
    assert involvement.subjects == cooperation.subjects
    assert cooperation.conditions == involvement.conditions == ["where appropriate"]
    assert norms["P4-PRESERVE-OTHER-SANDBOXES"].kind.value == "legal_consequence"
    other = norms["P4-INTER-SANDBOX-COOPERATION"]
    assert other.subjects[0].subject_ref == "member_state"
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
    assert plan.conditions == [
        "where the Articles 60 and 60a real-world testing plan is applicable"
    ]


def test_written_proof_is_requested_but_exit_report_is_not(norms):
    proof = norms["P7-SANDBOX-EVIDENCE-PACKAGE"]
    report = norms["P7-EXIT-REPORT"]
    assert proof.conditions == [
        "the provider or prospective provider of the AI system requests written proof"
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
    assert use.subjects[0].subject_ref == "provider"
    assert "conformity assessment or relevant market surveillance" in use.action
    for suffix, actor, category in (
        ("SURVEILLANCE", "market_surveillance_authority", "public_authority"),
        ("NOTIFIED-BODY", "notified_body", "notified_or_conformity_body"),
    ):
        duty = norms[f"P7-{suffix}-EVIDENCE-CONSIDERATION"]
        assert duty.kind.value == "obligation"
        assert duty.subjects[0].subject_ref == actor
        assert duty.subjects[0].category.value == category
        assert "positively into account" in duty.action
        assert "reasonably accelerating" in duty.action


def test_report_access_consideration_and_public_release_do_not_share_one_gate(norms):
    access = norms["P8-EXIT-REPORT-ACCESS"]
    consideration = norms["P8-CONSIDER-EXIT-REPORTS"]
    publication = norms["P8-PUBLIC-EXIT-REPORT"]
    assert access.kind.value == "permission"
    assert consideration.kind.value == "obligation"
    assert publication.kind.value == "permission"
    assert access.subjects == consideration.subjects
    assert access.subjects[0].subject_ref == "commission_and_board"
    assert access.conditions == [
        "Article 78 confidentiality provisions are observed",
        "the provider or prospective provider agrees to access",
    ]
    assert consideration.conditions == [
        *access.conditions,
        "where appropriate when exercising tasks under this Regulation",
    ]
    assert publication.conditions == [
        "the provider or prospective provider explicitly agrees to public release",
        "the national competent authority explicitly agrees to public release",
        "Article 78 confidentiality provisions are observed",
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
    assert "significant risks" in mitigation.conditions[0]
    assert "suspend" not in mitigation.action
    assert suspension.kind.value == "power"
    assert suspension.conditions[-1] == "no effective mitigation is possible"
    assert "temporarily or permanently" in suspension.action
    assert "testing or participation" in suspension.action
    assert notification.kind.value == "obligation"
    assert notification.conditions == [
        "a decision temporarily or permanently suspending testing or sandbox participation "
        "has been taken"
    ]
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
    assert liability.subjects[0].subject_ref == "provider_or_prospective_provider"
    assert "third-party damage resulting from sandbox experimentation" in liability.action
    assert not any("guidance" in condition for condition in liability.conditions)
    # The pinned text specifically says prospective providers for the AI Act safe harbour.
    assert ai_act.subjects[0].subject_ref == "prospective_provider"
    assert ai_act.conditions == [
        "the prospective provider observes the specific sandbox plan",
        "the prospective provider observes the terms and conditions of participation",
        "the prospective provider follows national competent authority guidance in good faith",
    ]
    assert "infringements of this Regulation" in ai_act.action
    assert other_law.conditions == [
        "the provider or prospective provider participates in the sandbox",
        "competent authorities responsible for the other law were actively involved in "
        "supervision of the AI system in the sandbox",
        "those competent authorities provided guidance for compliance with that law",
    ]
    assert "other Union or national law" in other_law.action


def test_board_coordination_is_required_but_joint_sandbox_support_is_optional(norms):
    duty = norms["P14-COORDINATE-SANDBOX-ACTIVITIES"]
    support = norms["P14-SUPPORT-JOINT-SANDBOXES"]
    assert duty.kind.value == "obligation"
    assert support.kind.value == "permission"
    assert duty.subjects == support.subjects
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
    assert notice.subjects == support.subjects
    assert notice.subjects[0].subject_ref == "national_competent_authority"
    assert "AI Office and the Board" in notice.action
    assert "AI Office and the Board" in support.action
    assert listing.subjects[0].subject_ref == "ai_office"
    assert listing.subjects[0].category.value == "union_institution_or_body"
    assert "publish and keep current" in listing.action
    assert "planned and existing" in listing.action


def test_reporting_stages_publication_and_commission_use_are_separate(norms):
    annual = norms["P16-SANDBOX-REPORTING"]
    final = norms["P16-FINAL-SANDBOX-REPORT"]
    publication = norms["P16-PUBLISH-ANNUAL-REPORTS"]
    consideration = norms["P16-COMMISSION-REPORT-CONSIDERATION"]
    assert "from one year after sandbox establishment" in annual.action
    assert "every year thereafter until termination" in annual.action
    assert "final sandbox report" in final.action
    assert "AI Office and the Board" in annual.action
    assert "AI Office and the Board" in final.action
    assert annual.mandatory_content == final.mandatory_content
    assert len(annual.mandatory_content) == 7
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
    assert publication.subjects == annual.subjects == final.subjects
    assert annual.subjects[0].subject_ref == "national_competent_authority"
    assert "annual sandbox reports or abstracts" in publication.action
    assert "online" in publication.action
    assert consideration.subjects[0].subject_ref == "commission"
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
    assert coordination.subjects == interface.subjects
    assert coordination.subjects[0].subject_ref == "commission"
    assert coordination.conditions == ["where relevant"]
    assert "proactively coordinate with national competent authorities" == coordination.action


def test_corrections_remain_proposed_and_do_not_invent_runtime_coverage(norms):
    assert len(norms) == 50
    for norm in norms.values():
        assert norm.review.status.value == "proposed"
        assert norm.implementation_mode.value == "none_required"
        assert not norm.implementation_refs
        assert norm.product_scope.value in {"outside_supported_actor", "no_product_action"}
        assert norm.primary_spans[0].startswith("AIA-TEXT-A057-")
