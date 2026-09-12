import { expect, test } from "@playwright/test";
import { backendBaseURL, getAdminAccessToken, loginAsAdmin } from "./helpers";

/**
 * KII detail page (A07) hardening-pass coverage. Two things fixed/added in
 * this pass:
 *  - participation_consent_decision/recording_consent_decision were added
 *    to KIIRecordSerializer so the page can show whether consent was
 *    already captured (previously a click gave no feedback at all).
 *  - independently confirms the pre-existing separate-consent guard
 *    (mark_completed() refuses a recording without its own recording
 *    consent, AGENTS.md ground rule 6) still works through a real browser
 *    click, not just a backend unit test.
 * Creates its own KII record via the API so this doesn't depend on any
 * other spec having created one first.
 */
test("KII completion with a recording is blocked until recording consent is recorded, and the UI reflects it", async ({
  page,
  request,
}) => {
  const backend = backendBaseURL();
  const access = await getAdminAccessToken(request, backend);
  const authHeader = { Authorization: `Bearer ${access}` };

  const createResponse = await request.post(`${backend}/api/v1/kii/`, {
    headers: authHeader,
    data: {
      stakeholder_category: "REGULATOR",
      participant_name: "E2E Playwright KII Subject",
      participant_role: "Policy Officer",
      preferred_mode: "PHONE",
    },
  });
  expect(createResponse.status()).toBe(201);
  const kii = await createResponse.json();

  const scheduleResponse = await request.post(`${backend}/api/v1/kii/${kii.id}/status/`, {
    headers: authHeader,
    data: { status: "SCHEDULED" },
  });
  expect(scheduleResponse.status()).toBe(200);

  await loginAsAdmin(page);
  await page.goto(`/admin/kii/${kii.id}`);

  await expect(page.getByText("Status: SCHEDULED")).toBeVisible();
  await expect(page.getByText("Not recorded")).toHaveCount(2);

  // Attempting completion with a recording, before recording consent is
  // given, must be rejected -- not just hidden by a disabled button.
  await page.getByLabel("Recording made (requires separate recording consent)").check();
  await page.getByRole("button", { name: "COMPLETED" }).click();
  await expect(page.getByText("Recording consent was not given for this KII.")).toBeVisible();
  await expect(page.getByText("Status: SCHEDULED")).toBeVisible();

  // Record recording consent, then the same completion succeeds.
  await page.getByRole("button", { name: "Record recording consent" }).click();
  await expect(page.getByText("GIVEN")).toBeVisible();

  await page.getByLabel("Recording made (requires separate recording consent)").check();
  await page.getByRole("button", { name: "COMPLETED" }).click();
  await expect(page.getByText("Status: COMPLETED")).toBeVisible();

  const finalState = await (
    await request.get(`${backend}/api/v1/kii/${kii.id}/`, { headers: authHeader })
  ).json();
  expect(finalState.status).toBe("COMPLETED");
  expect(finalState.recording_consent_decision).toBe("GIVEN");
  expect(finalState.participation_consent_decision).toBeNull();
});
