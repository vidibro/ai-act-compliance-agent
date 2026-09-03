# Normative coverage granularity audit

**Snapshot:** `2026-07-27`; **audit date:** 2026-09-02; **reviewer:** codex.
**Source baseline:** `0951522` (confirmed Annex IV checklist and segmentation).
**Status:** candidate triage and populated-content-list pass completed; corrections and the rest
of the unflagged-source audit remain open.

## Boundary and method

The scanner visits all 133 documents and all 1,471 segments, including approved segments. It
flags internal enumerations and multiple modal signals linked to at most one norm. Full text of
each flagged segment and its linked norm actions, subjects, kinds, content, conditions and
exceptions were compared against the [atomicity contract](NORMATIVE-COVERAGE-SCOPE.md#atomicity-rules).
This is a pinned-source comparison, not verification of the latest external legislation.

The original space-delimited exploratory scan found 84 candidates before the Annex IV split,
82 afterwards. Word-boundary/whitespace-aware matching adds six previously missed candidates,
giving **88 baseline candidates**. This change is detector sensitivity, not six newly discovered norms.
The focused comparison recommends **46 splits, eight expansions and 34 retentions**, plus four
additional qualifier corrections outside the detector. These are segment-level decisions, not
counts of new norms; one split may require several records.

A second pass compared all 146 populated norm content lists against their linked source. The
[content audit register](NORMATIVE-COVERAGE-CONTENT-AUDIT.md) records 19 additional split proposals,
12 expansions, 38 references to existing decisions and 77 records with no additional focused
finding. Those are norm-level rows, not an extension of the 88-segment denominator. Examples include
independently triggered notifications, optional Board powers summarised as duties, and consent
information missing the no-detriment/no-justification safeguards.

Reproduce the live read-only candidate list, source hashes and full scan denominator (after the
corrections below, 45 candidates remain; a disappearing signal is not independent norm approval):

```sh
uv run python scripts/audit_norm_granularity.py --act-version 2026-07-27
```

No scanner result approves a segment or norm. The decisions below are proposed correction
directions, not user verification and not changes to enacted text. `retain` means no split is
recommended for the focused granularity question, not that all legal fields or implementations
have been independently approved. A compound action summary alone does not establish atomicity.

- `split`: actor, action, trigger, recipient, deadline, or legal effect varies independently.
- `expand`: the existing decomposition can remain, but concrete qualifiers/content need explicit
  representation or tests; source-span retention alone is insufficient.
- `retain`: repeated signals describe one decision, its content, or an associated qualification.

The scanner is not a completeness gate: unnumbered content, inline enumerations, implicit norms,
single-modal lists already divided into separate segments, and errors in multi-norm segments may
be unflagged. All unflagged source remains subject to the independent norm-review phase. The
additional source-linked checks below demonstrate why regex-only sign-off would be unsafe.

## Candidate decisions, in source order

IDs resolve in the versioned `text-review/articles/` and `text-review/annexes/` shards. Norm IDs
for each row are listed by the scanner and in the segment's `norm_ids`.

| Segment | Decision | Rationale / required change |
|---|---|---|
| AIA-TEXT-A006-P006 | retain | Assessment being required is the factual premise of one classification exclusion, not a second duty. |
| AIA-TEXT-A027-P001 | retain | One FRIA action with six content groups and the qualifying-deployer/excluded-area gate represented. |
| AIA-TEXT-A031-P001 | retain | One eligibility package expressly enumerates establishment and legal personality. |
| AIA-TEXT-A031-P005 | split | Separate direct system involvement, party representation and the general conflict prohibition; consultancy qualifies the latter. |
| AIA-TEXT-A031-P006 | split | Independent operation and the duty to document/implement impartiality structures are separately assessable actions. |
| AIA-TEXT-A031-P007 | split | Body procedures and staff secrecy have different duty-holders and different disclosure exceptions; current `exceptions` is empty. |
| AIA-TEXT-A031-P011 | split | Competence to evaluate outsourced work differs from permanent availability of multidisciplinary staff. |
| AIA-TEXT-A031-P012 | split | Article 38 coordination and participation/representation/currency in standardisation are independent obligations. |
| AIA-TEXT-A043-P1 | expand | Four norms and four mandatory-route conditions preserve the list structure. Explicitly retain Annex III point 1 scope and the special-authority exception to free notified-body choice. |
| AIA-TEXT-A048-P003 | retain | One marking obligation with its nature-dependent alternative location explicitly retained in the action. |
| AIA-TEXT-A050-P1 | expand | Keep the disclosure norm and exceptions; spell out the reasonably well-informed, observant and circumspect person/context test rather than just “obvious interaction”. |
| AIA-TEXT-A050-P2 | expand | Marking/detectability and solution qualities are represented, but content limitations, implementation costs and acknowledged state of the art are not explicit in the checklist. |
| AIA-TEXT-A050-P6 | retain | One cumulative-operation savings proposition for the listed other duties. |
| AIA-TEXT-A057-P005 | split | Optional sandbox-establishment power, statutory reference substitution and subsequent cooperation/access duties are different effects and stages. |
| AIA-TEXT-A057-P007 | split | Member State resource duties, authority cooperation/participation permission, preservation of other sandboxes and inter-sandbox coordination must not share one duty-holder/action. |
| AIA-TEXT-A057-P008 | split | Controlled sandbox operation, permission for supervised real-world testing and conditional incorporation of testing plans have different applicability. |
| AIA-TEXT-A057-P012 | split | Access is an authorisation, not a duty to access; considering reports is a duty, and public release has a separate two-party consent gate. |
| AIA-TEXT-A057-P020 | split | Preserve existing powers; distinguish mitigation, conditional suspension power, notification duty and lawful exercise of supervisory discretion. Current action turns suspension power into a duty. |
| AIA-TEXT-A057-P021 | split | Liability survives independently of the AI Act no-fine protection and the other-law no-fine protection, whose conditions differ. |
| AIA-TEXT-A057-P024 | split | Authorities notify and may request support; the AI Office publishes/updates the list. Different actors and legal effects. |
| AIA-TEXT-A057-P025 | split | Separate annual/final reporting stages, online publication and Commission consideration. The last duty is currently attributed to the national authority. |
| AIA-TEXT-A057-P026 | split | Providing the interface and proactively coordinating where relevant are distinct actions with different applicability. |
| AIA-TEXT-A058-P001 | retain | One implementing-act obligation whose four common-principle content groups are enumerated. |
| AIA-TEXT-A058-P018 | split | Agreeing safeguards with participants and conditional cooperation with other authorities have different recipients. |
| AIA-TEXT-A060-P002 | retain | One implementing-act action with the Article 98(2) adoption procedure as its qualifier. |
| AIA-TEXT-A060-P019 | split | Member States confer powers; surveillance authorities use them. One combined subject loses the bilateral allocation. |
| AIA-TEXT-A060-P020 | split | Article 73 reporting, immediate mitigation, conditional suspension/termination and recall on termination do not always share a trigger or deadline. |
| AIA-TEXT-A060A-P005 | retain | One framework-content requirement with four structured content groups. |
| AIA-TEXT-A060A-P010 | split | Sectoral compliance duty and the limitation on sectoral requirements obstructing Article 60a are different legal effects. |
| AIA-TEXT-A061-P007 | split | Documenting/dating consent and supplying a copy to a subject/representative are distinct actions and recipients, despite all three being listed. |
| AIA-TEXT-A065-P008 | retain | One two-thirds-majority adoption action with five explicit rules-of-procedure content groups. |
| AIA-TEXT-A067-P002 | retain | Three dimensions qualify one balanced forum-membership requirement. |
| AIA-TEXT-A067-P006 | split | Adopting rules, electing co-chairs and the term/renewal limit are independently meaningful. |
| AIA-TEXT-A067-P010 | split | Preparing an annual report and making it public are separately assessable actions. |
| AIA-TEXT-A068-P001 | retain | One panel-establishment implementing act with an adoption-procedure qualifier. |
| AIA-TEXT-A068-P002 | retain | One expert-selection requirement with three explicit eligibility conditions. |
| AIA-TEXT-A068-P006 | retain | Needs, consultation and gender/geographic balance qualify one panel-composition decision. |
| AIA-TEXT-A070-P001 | split | State designation, authority independence, member conduct and conditional organisational flexibility bind different actors or have different effects. |
| AIA-TEXT-A070-P003 | split | State resourcing, authority staffing and annual State reassessment differ in duty-holder and timing. |
| AIA-TEXT-A071-P001 | split | Database operation, expert consultation on initial specifications and Board consultation on updates have distinct stages/recipients. |
| AIA-TEXT-A071-P004 | split | Article 49 public access and Article 60 restricted/consented access apply to different datasets; preserve the restricted sections and the source's “should” wording. |
| AIA-TEXT-A071-P005 | retain | Necessity limit and required registrant details are represented as one database-content constraint. |
| AIA-TEXT-A072-P002 | retain | One lifetime monitoring function with explicit collection/analysis, relevant interaction analysis and the sensitive-operational-data exclusion. |
| AIA-TEXT-A073-P007 | split | Incident investigation/risk assessment and corrective action have separately verifiable outcomes; a single checklist must not substitute for action-level mapping. |
| AIA-TEXT-A073-P008 | split | General investigation cooperation and the prohibition on evidence-affecting alteration before notification have different conditions and legal effects. |
| AIA-TEXT-A073-P010 | split | Seven-day measures and the separate imported notification procedure need separate action mapping. |
| AIA-TEXT-A073-P012 | retain | One medical-device incident-reporting rule with restricted incident scope and designated recipient. |
| AIA-TEXT-A074-P004 | split | Competition-information reporting and prohibited-practice reporting have different contents and recipients. |
| AIA-TEXT-A074-P007 | retain | Exclusion of the Act procedure and replacement by equivalent sectoral procedure form one substitution. |
| AIA-TEXT-A074-P012 | split | State designation of eligible authorities differs from the non-interference constraint on surveillance activities affecting judicial authorities. |
| AIA-TEXT-A074-P015 | split | Authorities/Commission have a joint-activity power; the AI Office owes coordination support. Current obligation label conflates them. |
| AIA-TEXT-A075-P008 | retain | One competence rule states both role branches and the narrower same-undertaking deployer gate. |
| AIA-TEXT-A075-P015 | split | Cooperation with the AI Office and notification of the Board/other authorities have different recipients and verification. |
| AIA-TEXT-A075-P016 | expand | Keep the qualified request power and three content groups; explicitly retain that the request must be duly reasoned. |
| AIA-TEXT-A075-P021 | split | Initial response has an undue-delay/four-month deadline; periodic updates and final outcome arise only when powers are exercised. |
| AIA-TEXT-A075C-P018 | expand | Preserve the effectiveness/proportionality rule, but explicitly represent income/turnover basis, reference year, daily calculation and decision-appointed start date. |
| AIA-TEXT-A075C-P021 | retain | One five-year limitation rule with ordinary and continuing/repeated-infringement start alternatives. |
| AIA-TEXT-A075C-P022 | retain | Period and final-decision start date form one enforcement-limitation rule. |
| AIA-TEXT-A075C-P023 | retain | One implementing-act content requirement for limitation and interruption rules. |
| AIA-TEXT-A075C-P024 | retain | Immediate effect qualifies the required no-grounds closure decision. |
| AIA-TEXT-A076-P002 | retain | Coordinated authority and article-reference substitutions apply together to Article 60a testing. |
| AIA-TEXT-A077-P003 | retain | Reciprocal assistance and necessary information exchange specify one cooperation relationship. |
| AIA-TEXT-A077-P004 | split | Initial identification/publication deadline, notification and continuing updates are distinct stages/recipients. |
| AIA-TEXT-A078-P008 | split | Consultation before security-sensitive disclosure does not override the separate exclusion of sensitive operational data from exchange. |
| AIA-TEXT-A078-P009 | split | Premises retention, immediate access/copy on request and security-clearance restriction have distinct triggers and duty-holder roles. |
| AIA-TEXT-A078-P010 | retain | One savings clause preserves the listed exchange/warning and criminal-law obligations. |
| AIA-TEXT-A079-P007 | split | Taking provisional measures and promptly notifying other institutions are separate actions. |
| AIA-TEXT-A079-P008 | expand | Retain one notification-content norm, but enumerate the detailed non-compliance grounds rather than the broad combined final content label. |
| AIA-TEXT-A079-P014 | split | Deemed justification and its alternative clocks must not swallow the separate preservation of operator procedural rights. |
| AIA-TEXT-A082-P003 | retain | Immediate notification and four explicit content groups describe one report. |
| AIA-TEXT-A082-P005 | split | Immediate communication to concerned States/operators and informing other States have different recipients; do not silently extend the first deadline to the second duty. |
| AIA-TEXT-A085-P002 | split | Considering complaints in surveillance and handling them under dedicated procedures are independently verifiable actions. |
| AIA-TEXT-A092-P008 | retain | One implementing-act obligation with its evaluation content and examination-procedure qualifier. |
| AIA-TEXT-A097-P003 | split | Revocation power, termination/effective-date consequences and preservation of existing acts are distinct legal effects; “prospective” omits the actual date alternatives. |
| AIA-TEXT-A097-P006 | split | Entry-into-force alternatives and extension at Parliament/Council initiative require separate explicit treatment; early joint non-objection and extension are absent from the action summary. |
| AIA-TEXT-A098-P001 | retain | Committee status qualifies the same assistance arrangement; no list is being hidden. |
| AIA-TEXT-A099-P002 | split | Initial penalty-rule notification and subsequent amendment notification have different triggers/deadlines. |
| AIA-TEXT-A099-P016 | retain | One fine-decision consideration requirement with ten structured factor groups. |
| AIA-TEXT-A100-P001 | retain | Fine power is conditioned on a seven-group decision checklist; this row does not approve the checklist's implementation. |
| AIA-TEXT-A100-P011 | split | Hearing the investigated body, limiting decision grounds and involving complainants have different protections and applicability. |
| AIA-TEXT-A100-P012 | split | General defence safeguards and qualified party entitlement to file access need distinct legal-effect/subject representation. |
| AIA-TEXT-A100-P013 | split | Allocation of revenue to the Union budget and protection of the fined body's operation are distinct consequences/constraints. |
| AIA-TEXT-A101-P006 | expand | Keep one fine-amount determination, but enumerate nature/gravity/duration, proportionality/appropriateness and Article 93(3)/Article 56 commitments explicitly. |
| AIA-TEXT-A101-P011 | retain | One implementing-act obligation with content and Article 98(2) adoption procedure. |
| AIA-TEXT-A113-C | retain | Two route/date norms already exist; both now explicitly exclude Article 6(5). |
| AIA-TEXT-ANNEX-VIII-A | expand | All 13 entries are retained exactly. Nevertheless item 13 is optional, item 12 contains a non-disclosure requirement, and some fields are conditional: they must not become 13 unconditional mandatory checks. |
| AIA-TEXT-ANNEX-VIII-B | retain | Nine concrete fields, including conditional representative information, are retained exactly; no heading-only collapse. |
| AIA-TEXT-ANNEX-VIII-C | retain | Five concrete fields are retained exactly, including the applicability qualifier for the data-protection impact assessment. |

## Additional source-linked checks beyond the detector

These findings are separate from the 88-segment denominator and must not be hidden by a clean
modal/list scan. Source references identify full norm records in `source-records/` and `norms/`.

| Norm / area | Finding | Required treatment |
|---|---|---|
| AIA-NORM-A003-D061-WIDESPREAD-INFRINGEMENT | The two broad conditions hide point (a)'s at-least-two-other-Member-States threshold and the three origin/establishment branches. | Keep the definition but explicitly encode the nested alternatives and thresholds. |
| AIA-NORM-A006-P3-INSIGNIFICANT-RISK-EXCEPTION | Four alternatives are combined into one condition string; the pattern-detection alternative compresses the proper-human-review qualification. | Preserve the no-significant-risk AND at-least-one-of-four structure, with each alternative and its qualification explicit. Do not flatten OR into four cumulative duties. |
| AIA-NORM-A041-P1-ADOPT-COMMON-SPECIFICATIONS | Point (a) has four alternatives; point (b) requires both no published reference AND no reference expected within a reasonable period. The current compressed wording is ambiguous. | Represent the conjunctions and alternatives explicitly, keeping one conditioned power. |
| AIA-NORM-A075-P1-COMPETENCE | “Subject to the enacted exclusions” hides all four point (a) exclusions; the norm links their source segments but does not enumerate them. | Explicitly list the Annex I, Annex III point 2, qualifying institutional-provider, and administration-of-justice exclusions, scoped to point (a), not point (b). |
| AIA-NORM-A059-P1-CONDITIONAL-FURTHER-PROCESSING | The chapeau says every condition applies, but (a)–(j) also have separate linked norms. | No heading-only omission established at the parent level. Audit the child norms and executable conjunction separately; do not duplicate them just to increase the parent's list length. |
| Annex V | All eight declaration-content items and their subdetails/qualifiers are present in the content list. | No Annex IV-style heading-only collapse found in this comparison. |
| Annex IX | All five registration-content items are present. | No heading-only content omission found; initial submission versus maintenance still needs runtime mapping. |
| Annex XI | Section 1 has 11 content entries; Section 2 has four concrete evaluation/testing/architecture entries. | Content groups are represented. Section 2 is still packed into one source line and should be split for review ergonomics; counts do not prove implementation. |
| Annex XII | Eleven lettered requirements and their subdetails are represented; the 13 qualifier spans also include two group introductions. | Do not misclassify 13 spans versus 11 content items as two missing requirements. |

## Correction and completion queue

1. Address `split` and `expand` rows in both audit registers in source order, preserving old norm identity/history when a
   proposition is replaced, and fixing subject/kind/conditions rather than merely multiplying IDs.
2. Apply the four additional qualifier findings in source order too; these start at Article 3.
3. Reassess source-segment approval only if its disposition or represented legal effect changes;
   never label a codex correction as independently verified by the user.
4. Edit only authored `segments/` and `source-records/`; regenerate derived artifacts. Give every
   correction a focused semantic regression assertion, not just a norm-count assertion.
5. Complete the remaining unflagged-source pass, including requirements not represented in any
   content list, implicit legal effects and cross-reference conditions. All 146 populated lists
   have received a focused source comparison, not independent norm approval. A full-corpus scan
   is not a full-corpus semantic audit.
6. Reconcile these findings before declaring extraction complete or compiling new runtime rules.

## Applied corrections

| Article | Applied change | Assurance |
|---|---|---|
| 3 | Expanded definition 61 into explicit alternative cross-border routes: two other Member States with three origin/establishment connections, OR concurrent common-feature infringement by the same operator in at least three Member States. | Nested-condition regression; norm remains proposed. |
| 6 | Explicit shared risk premise AND one of four alternatives, including proper human review; linked the profiling override as an exception. | Nested-condition and source-provenance regressions; norm remains proposed. |
| 31 | Split paragraphs 5, 6, 7, 11 and 12 by independent action/actor. Distinguished legal-disclosure and notifying-authority exceptions. Added six norms, retaining existing IDs for narrowed original duties. | Action, actor and exception regressions; all 19 Article 31 norms remain proposed. |
| 40 | Kept two deliverable groups; resource/energy reduction is explicitly an example within the reporting/documentation group, not a third mandatory deliverable. | Content-semantic regression; norm remains proposed. |
| 41 | Preserved the standardisation request AND one of four defects AND no published reference AND none expected within a reasonable period. | Nested-condition regression; the provision remains a power. |
| 43 | Explicit Annex III point 1 scope, alternative Annex VII triggers, and the Article 74(8)/(9) exception to provider choice of notified body. | Route/exception regression; no runtime rules changed. |
| 45 | Split event-based and request-only disclosures in paragraphs 1 and 2; the same source-linked issue in paragraph 3 was also split into negative-result and requested positive-result sharing. Event categories are explicit alternatives, not mandatory payload lists; paragraph 4 is unchanged. | Seven proposed norms instead of four; regression checks cover request triggers, recipients, all event categories and the narrower adverse QMS outcomes. |
| 46 | Split paragraph 2's refusal response into immediate stopping of use and immediate discarding of all results and outputs. The actor and refusal trigger are identical; urgent-use permission and the other paragraphs are unchanged. | Fourteen proposed norms instead of thirteen; regressions check both actions, timing, shared condition and actor, source links and separate permission. |
| 50 | Expanded paragraph 1's obvious-interaction exception to the reasonably well-informed, observant and circumspect person test, considering circumstances and context. Paragraph 2 now explicitly includes content specificities/limitations, implementation costs and generally acknowledged state of the art, including the possible reflection in technical standards. | Still eleven proposed norms; regressions preserve marking/detectability, existing exceptions, implementation links and user-approved source provenance. The three factors qualify technical-solution qualities, not exemptions from marking. |
| 57 | Split the nine flagged segments and the requested-proof/exit-report content finding by actor, trigger and legal effect. Establishment, access, testing, suspension and support remain powers/permissions rather than duties; report use, notification, publication and annual/final reporting are distinct. Retained the different liability and two no-fine conditions, including the pinned text's prospective-provider condition for the AI Act protection. Nearby source checks also separated EDPS reference substitution, provider evidence use from surveillance/notified-body consideration, and optional joint-sandbox support. P006 is now a normative qualifier preserving Member State competence, linked to the AI Office power. | Fifty proposed norms instead of twenty-two; twelve focused semantic regressions plus source-link, metric and audit reconciliation checks. Codex changed P006's disposition; no user verification or runtime coverage is claimed. |
| 58 | Split paragraph 4's agreement of testing terms/safeguards with participants from cooperation with other national competent authorities. Both retain the supervised real-world sandbox testing context; only cooperation has the additional where-appropriate condition. The two safeguards content groups still qualify one agreement duty. Paragraphs 1–3 are unchanged. | Six proposed norms instead of five; regression checks cover distinct recipients/actions, conditions, exact quotes, source linkage and unchanged review/runtime boundaries. |
| 59 | Expanded paragraph 1(a)'s five public-interest areas into an explicit alternative group under the shared substantial-public-interest purpose and enacted development actors. Preserved all health examples and environmental, energy, transport/infrastructure and public-service details without inventing cumulative checks. The parent permission still requires all ten lettered conditions, each linked to its child norm. | Still thirteen proposed norms; regression checks cover AND/OR structure, exact source details, parent/child links and unchanged source-review and implementation boundaries. The live inventory has 142 populated content lists, not 143. |
| 60 | Split paragraph 6 into Member State conferral and market surveillance authority use of the powers, and paragraph 7 into Article 73 reporting, immediate mitigation, the conditional suspension/termination duty and the prompt-recall procedure. Paragraph 4(h) separates informing participating deployers from the jointly concluded roles agreement; 4(i) separates Article 61 consent from the law-enforcement substitute's no-negative-effect and post-test deletion duties, which require both law-enforcement context AND that seeking consent would prevent testing. 4(c)'s three registration routes became mutually exclusive `any_of` gates with their exact Annex III scopes, identifiers and information sources, and its truncated quote now covers the whole point. A nearby source check also separated the subject's withdrawal right from the separate deletion request. | Thirty-two proposed norms instead of twenty-four; three focused semantic regressions plus metric and audit reconciliation. Implementation debt rises to 221 because five separated provider duties have no existing rule; the ledger's earlier count hid them inside two checklists. No user verification or runtime coverage is claimed. |
| 60a | Split paragraph 6's operator duty to comply with the Section B harmonisation provisions from the separate limitation preventing those requirements from obstructing Article 60a testing. A nearby source check also separated the unconditional duty to ensure close good-faith authority cooperation from the removal of practical obstacles, which applies only where that removal is necessary. Paragraph 5's framework-content requirement is unchanged. | Eleven proposed norms instead of nine; regressions cover the differing conditions, kinds, product scope and the retained framework content. Implementation debt is unchanged because both separated effects fall outside the supported reporting surface. |
| 61 | Split paragraph 2 into dating and documenting the informed consent and the separate duty to give a copy to the subjects of testing or their legal representative. Paragraph 1's five information items now carry their full enacted detail, including the right to refuse and to withdraw at any time without any resulting detriment and without having to provide any justification, and the action states that the information must be concise, clear, relevant and understandable. | Three proposed norms instead of two; regressions check both actions, the recipient, the information qualities, each content item against its source span and unchanged review status. Implementation debt rises to 222 for the separated copy duty. |
| 62 | Split both chapeau duties into their lettered actions: priority sandbox access and its non-preclusion rule for other eligible SMEs, tailored awareness and training, use of existing advice channels, the where-appropriate establishment of new ones, standardisation facilitation, Board-requested templates, the information platform, communication campaigns and procurement best-practice work. Paragraph 2's fee factors are unchanged. | Thirteen proposed norms instead of three; regressions cover each chapeau's child links, the differing conditions and the retained fee factors. Every addressee is outside the supported reporting surface, so implementation debt is unchanged. |
| 65 | Split paragraph 8's AI Office content list into providing the Board secretariat, convening meetings upon the Chair's request and preparing agendas aligned with the Board's tasks and rules of procedure. Only convening carries the request trigger. Paragraph 5's rules-of-procedure content is unchanged. | Sixteen proposed norms instead of fourteen; regressions cover the three actions, the single request trigger and the unchanged addressee scope. Implementation debt is unchanged. |
| 66 | Separated the chapeau duty to advise and assist the Commission and the Member States from the non-exhaustive list of things the Board may in particular do, and gave each lettered task its own power norm. Point (e)'s seven topics are now one non-exhaustive scope entry naming every enacted topic, not seven contents every opinion must carry. | Seventeen proposed norms instead of two; regressions cover the duty/power boundary, each lettered child link and the preserved topic detail. Every addressee is outside the supported reporting surface, so implementation debt is unchanged. |
| 67 | Split paragraph 6 into drawing up the rules of procedure, electing two co-chairs under the paragraph 2 criteria and the two-year renewable co-chair term; paragraph 7 into the required two annual meetings and the optional invitation of experts and stakeholders; and paragraph 10 into preparing the annual activity report and making it publicly available. Paragraph 2's balance requirement is unchanged. | Fourteen proposed norms instead of ten; regressions cover the three paragraph 6 effects, the duty/power split on meetings and the separate publication action. Implementation debt is unchanged. |
| 68 | Split the scientific panel's advice-and-support duty and its GPAI support task into their lettered and numbered actions, keeping the request trigger on market surveillance support, the Article 74(11) without-prejudice limit and the Article 90 qualification on alerts. The expert protections became four norms: impartiality and objectivity, confidentiality, the prohibition on seeking or taking instructions and the published declaration of interests; the AI Office's conflict-management duty was already separate. | Nineteen proposed norms instead of eight; regressions cover the child links, the request trigger, the typed prohibition and the separate AI Office duty. Implementation debt is unchanged. |
| 70 | Split paragraph 1 into the Member State designation duty, the authorities' independent and impartial exercise of powers, the prohibition on incompatible member action and the permission to consolidate tasks while those principles are observed. Paragraph 2 separates the Commission communication, the 2 August 2025 public contact information and the single-point-of-contact designation and notification. Paragraph 3 separates Member State resourcing, the authorities' permanently available expert personnel and the annual reassessment. | Eighteen proposed norms instead of eleven; regressions cover the duty-holders, the typed prohibition and permission, the deadline that belongs to one disclosure only and the seven expertise fields. Implementation debt is unchanged. |
| 71 | Split paragraph 1 into database set-up and maintenance, expert consultation when setting the functional specifications and Board consultation when updating them. Paragraph 4 now carries the Article 49 public-access duty with both excluded sections as exceptions, the enacted "should" for navigable machine-readable presentation as a separate non-duty consequence, and the Article 60 restriction with its provider-consent exception. Paragraph 6 separates controllership from operator support. Paragraph 5 is unchanged. | Thirteen proposed norms instead of eight; regressions cover the two consultation stages, both access regimes and their exceptions, the preserved "should" and the separate support duty. Implementation debt is unchanged. |
| 73 | Split paragraph 6 into the without-delay investigation with its risk assessment and the separate corrective action, and into the cooperation duty and the typed prohibition on evidence-affecting alteration before informing the competent authorities. Paragraph 8 separates the seven-day Article 19 measures from following the Regulation (EU) 2019/1020 notification procedures. Paragraph 10's medical-device rule is unchanged. | Sixteen proposed norms instead of thirteen; regressions cover the shared reporting trigger, the typed prohibition and the deadline that belongs only to the measures. The two new provider duties map to the existing Article 73 report-only obligation, so implementation debt is unchanged. |
| 74 | Split paragraph 2 into the competition-information report to the Commission and national competition authorities and the prohibited-practice report to the Commission, which keeps its own two content items. Paragraph 8 separates the Member State designation duty from the prohibition on surveillance activities affecting judicial independence, and paragraph 11 separates the joint-activity power of the authorities and the Commission from the AI Office's coordination-support duty. Paragraph 7's substitution is unchanged. | Seventeen proposed norms instead of fourteen; regressions cover the recipients, the typed prohibition and the power/duty boundary. Implementation debt is unchanged. |
| 75 | Split paragraph 2 into cooperation with the AI Office on compliance evaluations and the separate duty to inform the Board and the other market surveillance authorities, and paragraph 2a's reply into the four-month initial response and the conditional periodic updates on major developments and outcome. Paragraph 2a's request now records that it must be duly reasoned, and paragraph 1's competence enumerates the four point (a) exclusions instead of referring to "the enacted exclusions". | Twenty-seven proposed norms instead of twenty-five; regressions cover the shared suspicion trigger, the deadline that belongs only to the first reply, the duly-reasoned request and the four exclusions being scoped to point (a). Implementation debt is unchanged. |
| 75a | Split paragraph 3's information-request content into the three fields every request must state, the simple-request additions, the decision-request additions and the separate duty to send a copy to the operator's territorial market surveillance authority. The voluntary-reply correctness duty is unchanged. | Twenty-four proposed norms instead of twenty-one; regressions cover the branch conditions, both fine references, the judicial-review right and the copy being an action rather than a request field. Implementation debt is unchanged. |
| 75c | Expanded paragraph 5's penalty-payment rule and, in doing so, separated the unconditional effectiveness and proportionality requirement from the where-applicable 5 % ceiling. The ceiling now states the income or worldwide-turnover basis, the preceding financial year, the per-day rate and the decision-appointed start date. Paragraphs 6 to 9 are unchanged. | Nineteen proposed norms instead of eighteen; regressions cover the conditional ceiling and its four elements. Implementation debt is unchanged. |
| 77 | Split paragraph 2 into identifying the paragraph 1 authorities and publishing their list by 2 November 2024, notifying the list to the Commission and the other Member States, and keeping it up to date. The deadline no longer covers the later stages. Paragraph 3's cooperation relationship is unchanged. | Nine proposed norms instead of seven; regressions cover the deadline scope, the recipients and the continuing update duty. Implementation debt is unchanged. |
| 78 | Split paragraph 3's disclosure rule into the consultation requirement, with its two cumulative conditions, and the separate prohibition on exchanging sensitive operational data. Its second subparagraph became three norms: documentation remaining on the premises, the request-triggered immediate access or copy, and the prohibition limiting access to appropriately security-cleared market surveillance staff. Paragraph 1 now enumerates the five protected interests and records the Article 5 of Directive (EU) 2016/943 exception as a point (a) exception and an external dependency. Paragraph 4's savings clause is unchanged. | Eleven proposed norms instead of eight; regressions cover the conditions, the two typed prohibitions, the scoped trade-secret exception and the retained implementation links. Implementation debt is unchanged. |
| 79 | Split paragraph 5 into taking the provisional measures, conditioned on the operator's failure to act within the paragraph 2 period, and notifying the Commission and the other Member States without undue delay. Paragraph 6's notification now enumerates the five detail groups and the four non-compliance grounds separately. Paragraph 8 separates deemed justification, the preserved Article 18 procedural rights and the 30-day period for Article 5 non-compliance. | Seventeen proposed norms instead of fourteen; regressions cover the trigger, the deadline that belongs to the notification, the nine content entries and the three distinct consequences. Implementation debt is unchanged. |
| 82 | Split paragraph 5 into the immediate communication of the decision to the Member States concerned and the relevant operators and the separate duty to inform the other Member States, which the source does not put under the same immediacy requirement. Paragraph 3's report is unchanged. | Seven proposed norms instead of six; regressions cover the recipients and the deadline that belongs only to the first duty. Implementation debt is unchanged. |
| 85 | Split paragraph 2 into taking complaints into account when conducting market surveillance activities and handling them in line with the dedicated procedures the authorities established for them. | Three proposed norms instead of two; regressions cover both actions and the unchanged complaint entitlement. Implementation debt is unchanged. |
| 92 | Expanded paragraph 1's evaluation power into two explicit alternative purposes: assessing provider compliance where the Article 91 information is insufficient, and investigating Union-level systemic risks of general-purpose AI models with systemic risk, in particular following an Article 90(1), point (a) qualified alert. Board consultation remains a separate shared condition. Paragraph 8's implementing-act duty is unchanged. | Still fourteen proposed norms; regressions cover the AND/OR structure and both enacted limits. Implementation debt is unchanged. |
| 95 | Paragraph 2's five topics are now one non-exhaustive scope entry quoting each enacted example in full, and the action states that the list is not exhaustive and that applying the requirements stays voluntary. | Still four proposed norms; regressions cover the "such as, but not limited to" wording, all five examples and the voluntary framing. Implementation debt is unchanged. |
| 96 | Paragraph 1's seven guideline subjects are enumerated in full, and point (g)'s 1 August 2027 publication became its own norm so the deadline no longer applies to the whole guideline duty. | Six proposed norms instead of five; regressions cover the seven subjects and the deadline scope. Implementation debt is unchanged. |
| 97 | Split paragraph 3 into the revocation power, the decision's effect on the delegation with its day-after-publication or later-specified date, and the preservation of delegated acts already in force. Paragraph 6 now carries both entry-into-force alternatives, including early joint non-objection, and the separate power to extend the objection period by three months. | Eleven proposed norms instead of eight; regressions cover the three paragraph 3 effects, the alternative conditions and the extension power. Implementation debt is unchanged. |

The original 88-row ledger above remains a historical audit baseline. Article 31's five,
Article 57's nine, Article 58's one, Article 60's two, Article 60a's one, Article 61's one,
Article 67's two, Article 70's two, Article 71's two, Article 73's three, Article 74's
three and Article 75's two, Article 75c's one, Article 77's one, Article 78's two, Article 79's two, Article 82's one, Article 85's one and Article 97's two split candidate segments no longer
trigger the scanner, leaving 45 live signals. The current inventory has 1,477 proposed norms and 1,471 segments. Implementation debt rose from 216 to 222 records: six
separated provider duties in Articles 60 and 61 are in-scope propositions that no existing rule
covers, which the previous combined checklists concealed. Every other norm added since baseline
either addresses an actor outside the supported reporting roles, states a no-product-action
consequence, or maps to the report-only obligation that already carried its provision.
Source approvals have not been relabelled as norm approvals. The Article 57 mitigation proposition
preserves the supervisory requirement for adequate mitigation; it does not assign a new operational
product action or turn suspension into a duty. This actor interpretation remains subject to
independent norm review, as do the other corrections.
Next recorded correction: Article 99. Articles 47–49 and 51–56 have no open recorded correction
in these ledgers. The Article 50 corrections do not remove their heuristic scan signals; a signal
is not a finding or an approval status.

Committed separately on 2026-09-03: shared condition mechanism `62c3011`; Article 3 `9fd7c58`;
Article 6 `b31b780`; Article 31 `7282527`; Article 40 `856707c`; Article 41 `d8ec444`;
Article 43 `f7ec5e9`. Article-specific regression tests accompany their commits. The final combined
builder, extraction, loader, scanner and correction test run passed 75 tests; Ruff and builder
`--check` also passed. Three previously confirmed baseline mypy errors in the builder remain
outside this correction batch. These checks do not confer independent legal approval.
