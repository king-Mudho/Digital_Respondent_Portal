import { test } from "@playwright/test";

/**
 * Explicit, visible record of what this suite deliberately does NOT and
 * cannot cover, per docs/28_DEFINITION_OF_DONE.md's go-live blockers. These
 * are intentionally `test.skip` (not simply absent) so they show up in
 * every Playwright run's report -- a missing test is invisible; a skipped
 * test with a reason is a standing, visible reminder of exactly what is
 * still blocked and why, until the underlying PI/external action happens.
 */

test("WhatsApp Business Platform messaging integration", () => {
  test.skip(
    true,
    "No WhatsApp Business Platform account or Meta-approved message template exists yet " +
      "(docs/27_AGENT_EXECUTION_PLAN.md, docs/28_DEFINITION_OF_DONE.md). apps/messaging has no " +
      "views or URLs at all -- there is no built feature to test, only the WHATSAPP enum value " +
      "already exercised as a plain dropdown option in admin-workflow-and-contact-log.spec.ts " +
      "(ContactChannel) and the respondent choice/appointment screens (AppointmentMode). Writing " +
      "an E2E test against a WhatsApp send/receive flow here would either mock the entire " +
      "integration (testing nothing real) or require live Meta credentials this environment does " +
      "not have. Add real coverage once a Meta-approved account and template exist and the " +
      "messaging app is actually implemented against them.",
  );
});

// POTRAZ / Data Protection Officer determination -- resolved 2026-09-12, see
// docs/18_DATA_PRIVACY_AND_COMPLIANCE.md. No longer a go-live blocker, so the
// standing skip that tracked it has been removed.
