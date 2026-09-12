import { expect, test } from "@playwright/test";
import { backendBaseURL, getAdminAccessToken, loginAsAdmin } from "./helpers";

/**
 * Reserve activation (A09): docs/09_IDENTIFIER_AND_SAMPLING_CONTROL.md --
 * activation always requires one of five authorised reasons plus an
 * evidence note, and must be audited. Uses
 * E2E_ACTIVATION_RESERVE_SAMPLE_ID, a case dedicated to this spec (seeded
 * fresh and reset to LOCKED on every seed_drp_dev run) so activating it
 * can never make reserve-lock.spec.ts flaky by leaving the shared
 * E2E_RESERVE_SAMPLE_ID case ACTIVATED.
 */
test("activating a locked reserve case requires a reason and note, and is audited", async ({ page, request }) => {
  const sampleId = process.env.E2E_ACTIVATION_RESERVE_SAMPLE_ID!;
  await loginAsAdmin(page);
  await page.goto("/admin/reserve");

  // Scoped to the Card element itself (.rounded-lg is Card's own wrapper
  // class, components/ui/card.tsx) rather than any ancestor div, since the
  // /admin/reserve queue can legitimately show more than one locked case
  // at once (e.g. reserve-lock.spec.ts's own dedicated fixture) and a
  // looser locator would match buttons across all of them.
  const card = page.locator(".rounded-lg", { hasText: sampleId }).first();
  await expect(card).toBeVisible();

  // The button is disabled until both a reason and a note are provided --
  // no free-text "other" escape hatch, and no activation without evidence.
  const activateButton = card.getByRole("button", { name: "Activate this reserve" });
  await expect(activateButton).toBeDisabled();

  await card.locator("select").selectOption("NONRESPONSE_EXHAUSTED");
  await expect(activateButton).toBeDisabled();
  await card.getByPlaceholder("Evidence note (required)").fill("E2E Playwright: nonresponse sequence exhausted.");
  await expect(activateButton).toBeEnabled();

  await activateButton.click();
  await expect(page.getByText(sampleId, { exact: false })).toHaveCount(0);

  const backend = backendBaseURL();
  const access = await getAdminAccessToken(request, backend);
  const caseDetail = await (
    await request.get(`${backend}/api/v1/sample-cases/${sampleId}/`, { headers: { Authorization: `Bearer ${access}` } })
  ).json();
  expect(caseDetail.status).toBe("ACTIVATED");
  expect(caseDetail.activation_reason).toBe("NONRESPONSE_EXHAUSTED");
  // Correct audit attribution for this exact action is already covered at
  // the API level by backend/tests/test_audit.py -- this spec's job is the
  // UI contract (reason+note required, case disappears from the locked
  // queue, activation actually lands).
});
