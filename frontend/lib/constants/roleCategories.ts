/**
 * Mirrors apps/contacts/models.py RoleCategory exactly -- the fixed list
 * that determines eligibility (docs/10_INVITATION_AND_CONSENT.md). Keep in
 * sync with the backend; a mismatch would silently misclassify eligibility.
 */
export const ROLE_CATEGORIES: { value: string; label: string }[] = [
  { value: "OWNER_FOUNDER", label: "Owner / Founder" },
  { value: "CEO_MD", label: "CEO / Managing Director" },
  { value: "FINANCE_CREDIT_RISK", label: "Finance / Credit / Risk" },
  { value: "OPERATIONS", label: "Operations" },
  { value: "STRATEGY_BD", label: "Strategy / Business Development" },
  { value: "SUPPLY_CHAIN_COMMERCIAL", label: "Supply Chain / Commercial" },
  { value: "OTHER_SENIOR_MANAGER", label: "Other senior manager" },
];

export const NONE_OF_THESE = "NONE_OF_THESE";
