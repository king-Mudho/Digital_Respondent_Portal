"""The ABI expert content-validation questionnaire, Round 1 (instrument version 1.0, 6 November 2026), as data.

One definition for both the KoboToolbox XLSForm (deploy/kobo/build_expert_form.py) and the portal: the field the
portal prefills with the Expert ID, and the 16 indicators in eight domains. The wording is the PI's, from
"ABI_16_Indicator_Expert_Validation_Questionnaire_Final_Draft-2.docx"; Section F (researcher-only analysis rules) is
not part of the form. The portal collects the ratings; it never computes an ABI score for anyone (AGENTS.md rule 3).
"""

FORM_TITLE = "ABI Expert Content-Validation Questionnaire — Round 1"
FORM_ID = "abi_expert_validation_r1"
FORM_VERSION = "1.0 (2026-11-06)"
INFORMATION_SHEET_VERSION = "expert-r1-v1.0"

# The group and field the portal prefills (?d[part_a/EXPERT_ID]=E01) and the form sync matches back to the expert.
GROUP = "part_a"
EXPERT_ID_FIELD = "EXPERT_ID"
EXPERT_ID_PATH = f"{GROUP}/{EXPERT_ID_FIELD}"

# Shown in the form and on the portal's information page (filled in 8 Nov 2026 from the study's clearance letters:
# the CUT Research Ethics Clearance Letter of 24 August 2026, the Ministry of Agriculture, Mechanisation and Water
# Resources Development clearance J/122 of 23 September 2026, and the confirmation of PhD supervision of 20 August
# 2026). The supervision letter gives no personal email or phone for the supervisor and asks that contact go through
# Chinhoyi University of Technology channels, so the Graduate Business School's contact is given.
#
# Three words differ from the PI's draft, because "approved" may not appear anywhere a participant reads it (AGENTS.md
# rule 2): "the approved ethics protocol" -> "the ethics protocol for this study"; "the approved information sheet" ->
# "the study's information sheet"; "[INSERT APPROVED CONTACT]" -> the supervisor's details. For PI sign-off.
ETHICS_LINE = (
    "Ethics clearance: Chinhoyi University of Technology Research Ethics Clearance, 24 August 2026 — Chairperson, "
    "University Research Committee (Research Ethics): Dr M. C. Mwando, gbs@cut.ac.zw, +263 6721 29447. "
    "Ministry of Agriculture, Mechanisation and Water Resources Development clearance: Ref J/122, 23 September 2026.\n"
    "Research contact: Happyson Saina, 0773943709, abffst.research@gmail.com.\n"
    "Supervisor: Dr L. Chikazhe, PhD Research Supervisor, Graduate Business School, Chinhoyi University of Technology "
    "(contact through the Graduate Business School: gbs@cut.ac.zw, +263 6721 29447)."
)

INFORMATION = [
    ("Purpose", "This exercise assesses the relevance, clarity and practical observability of 16 candidate indicators "
     "across eight domains of agribusiness bankability. Bankability is provisionally defined as the organisational "
     "capability to attract, appropriately use and sustain finance consistent with operational cash flows, risk controls "
     "and credible market commitments. The exercise evaluates proposed measures; it does not assess your institution or "
     "any particular borrower."),
    ("Time and format", "Estimated 15–20 minutes. You may skip any question and stop at any time without penalty. A "
     "brief optional second round may request reassessment of revised items. There is no compensation proposed. "
     "Participation is voluntary."),
    ("Privacy", "Use the assigned Expert ID rather than your name on the rating form. Responses will be reported in "
     "aggregate; any attributed quotation requires separate explicit permission. Access to identifiable "
     "contact/consent records will be restricted to the authorised research team. Retention and withdrawal deadlines "
     "must follow the ethics protocol for this study."),
]

CONSENT_STATEMENTS = [
    ("CONSENT_AGE", "I am at least 18 years old and have read the information above."),
    ("CONSENT_ANALYSIS", "I voluntarily consent to anonymous analysis of my ratings and comments for research and publication."),
    ("CONSENT_WITHDRAW", "I understand I may omit questions or withdraw according to the study's information sheet."),
]

RATING_INSTRUCTIONS = (
    "Rate each indicator independently on THREE separate four-point scales. Ratings of 3 or 4 for RELEVANCE will be "
    "used to calculate item-level content validity (I-CVI). Clarity and observability are analysed separately; do not "
    "treat them as relevance. If unable to judge, choose U and explain briefly. Please assess whether the indicator is "
    "suitable, not whether a particular firm currently meets it."
)
SCALES = {
    "relevance": ("R", "Relevance", ["Not relevant", "Somewhat relevant", "Quite relevant", "Highly relevant"]),
    "clarity": ("C", "Clarity", ["Unclear", "Major revision needed", "Clear with minor revision", "Very clear"]),
    "observability": ("O", "Observability", ["Not verifiable in practice", "Difficult to verify", "Generally verifiable",
                                             "Routinely verifiable"]),
}
UNABLE = ("U", "U — Unable to judge")

DOMAINS = [
    ("D1", "Financial planning and financing-source suitability",
     "Ability to plan financing needs and select suitable funding sources.", [
         ("ABI01", "Documented financing strategy", "A dated financing plan links the intended use of funds, amounts, "
          "timing and anticipated repayment to operating requirements."),
         ("ABI02", "Financing-source fit and diversification", "The firm evaluates alternative sources for suitability "
          "of cost, tenor, currency, conditions and availability; diversification is not assumed to be universally optimal."),
     ]),
    ("D2", "Capital cost and repayment-cycle management",
     "Ability to assess affordability and match financing obligations with cash generation.", [
         ("ABI03", "Cash-flow and debt-service stress testing", "The firm models debt service under plausible changes in "
          "sales, input prices, yield, payment delays and interest/currency conditions."),
         ("ABI04", "Repayment and cash-conversion alignment", "The firm evaluates whether financing maturity and "
          "repayment dates align with production, inventory, receivables and cash-conversion cycles."),
     ]),
    ("D3", "Risk governance and disclosure",
     "Ability to identify, monitor, disclose and control material enterprise risks.", [
         ("ABI05", "Documented risk management controls", "The firm maintains assigned controls for material financial, "
          "operational, contractual and compliance risks."),
         ("ABI06", "Timely and reliable management reporting", "Management periodically reviews reconciled financial and "
          "operational performance information for decisions and lender disclosure."),
     ]),
    ("D4", "Digital records and information integrity",
     "Ability to produce accurate, retrievable and auditable transaction and operational data.", [
         ("ABI07", "Reconciled transaction records", "Sales, purchases, cash/bank transactions and receivables are "
          "recorded, reconciled and retrievable, whether digital or paper-based."),
         ("ABI08", "Inventory and production traceability", "The firm can trace material inventory, production or "
          "service flows through reliable records appropriate to its value chain."),
     ]),
    ("D5", "Contract and market coordination",
     "Ability to establish and perform credible buyer and supplier commitments.", [
         ("ABI09", "Verifiable market commitments", "Buyer orders, off-take arrangements or other demand evidence "
          "identify counterparties, quantities, terms and verification mechanisms."),
         ("ABI10", "Contract execution and settlement monitoring", "The firm documents delivery, quality compliance, "
          "invoicing, payment and dispute resolution against commitments."),
     ]),
    ("D6", "Climate and biological/operational resilience",
     "Ability to manage material agricultural and environmental shocks.", [
         ("ABI11", "Documented contingency and adaptation planning", "The firm has context-appropriate plans for climate, "
          "biological, supply or infrastructure disruptions."),
         ("ABI12", "Monitored production and loss controls", "The firm measures relevant yield, mortality, spoilage, "
          "downtime or other value-chain-specific risk indicators and responds to deviations."),
     ]),
    ("D7", "Collateral-substitution readiness",
     "Ability to document assets or claims that could support alternative security arrangements.", [
         ("ABI13", "Verifiable movable-asset documentation", "The firm maintains records of eligible equipment, "
          "livestock, inventory or other movable assets, including ownership and encumbrances where relevant."),
         ("ABI14", "Verifiable receivables or stored-commodity claims", "The firm can substantiate qualifying "
          "receivables, warehouse receipts or inventory claims and relevant counterparty rights."),
     ]),
    ("D8", "Financial and operational performance evidence",
     "Ability to demonstrate a reliable operating record without using credit approval itself as an ABI input.", [
         ("ABI15", "Consistent historical financial records", "The firm maintains comparable, reconcilable financial "
          "statements or management accounts over an appropriate period."),
         ("ABI16", "Documented operating fulfilment history", "The firm records fulfilment of orders, quality "
          "requirements and operational commitments across relevant periods."),
     ]),
]

# Section B profile choices, as on the paper form.
EXPERIENCE = [("y5_9", "5–9 years"), ("y10_19", "10–19 years"), ("y20_plus", "20+ years"), ("other", "Other")]
EXPERTISE = [("ag_banking", "Agricultural banking/credit"), ("agribusiness_ops", "Agribusiness operations"),
             ("ag_economics", "Agricultural economics"), ("research_measurement", "Research measurement/statistics"),
             ("policy_food_systems", "Policy/food systems"), ("other", "Other")]
INSTITUTION = [("bank_dfi", "Bank/DFI"), ("agribusiness", "Agribusiness"), ("university_research", "University/research"),
               ("government_regulator", "Government/regulator"), ("ngo_development", "NGO/development partner"),
               ("other", "Other")]

# Section E, in order: (name, question, kind, follow-up name, follow-up label, when the follow-up shows)
OVERALL = [
    ("E1", "Are all eight domains needed?", "yes_no_unsure", "E1_DETAIL", "If no, identify any to remove/merge", "no"),
    ("E2", "Which critical bankability capability is missing?", "text", None, None, None),
    ("E3", "Which indicators overlap or could unfairly penalise smaller firms?", "text", None, None, None),
    ("E4", "Is the distinction between firm capabilities and actual loan outcomes clear?", "yes_no", "E4_DETAIL",
     "Suggested correction", "no"),
    ("E5", "Should equal domain weights be the starting point for the pilot?", "yes_no_unsure", "E5_RATIONALE",
     "Rationale", None),
    ("E6", "Should any domain be a non-compensatory minimum condition?", "yes_no", "E6_DETAIL", "Which and why?", "yes"),
    ("E7", "Which evidence types should be required for a credible ABI assessment?", "text", None, None, None),
    ("E8", "Other comments or suggested Zimbabwe-specific adaptations", "text", None, None, None),
]


def indicators():
    """[(domain_code, indicator_id, title, definition)] in questionnaire order."""
    return [(d, i, t, text) for d, _, _, items in DOMAINS for i, t, text in items]


def all_text() -> str:
    """Every word the expert sees on the form, for the forbidden-words check (AGENTS.md rule 2)."""
    parts = [FORM_TITLE, ETHICS_LINE, RATING_INSTRUCTIONS, *(t for _, t in INFORMATION), *(t for _, t in CONSENT_STATEMENTS)]
    for _, title, definition, items in DOMAINS:
        parts += [title, definition, *(f"{t} {text}" for _, t, text in items)]
    parts += [label for _, (_, _, labels) in SCALES.items() for label in labels]
    parts += [q for _, q, *_ in OVERALL] + [lab for *_, lab, _ in OVERALL if lab]
    parts += [lab for _, lab in EXPERIENCE + EXPERTISE + INSTITUTION]
    return " ".join(parts)
