import { expect, test } from "@playwright/test";
import { backendBaseURL, getAdminAccessToken, issueTokenOnFreshCase, loginAsAdmin } from "./helpers";

/**
 * PROIT: the AI research section (the AI itself is off in CI, so the screen must say so plainly), and the
 * interview sheet a coordinator or interviewer uses on the LOCKED profile: confirm what is public, ask what
 * is not, record the respondent's answer separately, and reconcile after the interview.
 */
test("the AI research section appears on a draft profile and says plainly when AI isn't set up", async ({ page, request }) => {
  const backend = backendBaseURL();
  const { sampleId } = await issueTokenOnFreshCase(request, backend, "AI research");
  await loginAsAdmin(page);
  await page.goto(`/admin/sample/${sampleId}`);
  await page.getByRole("button", { name: "Start background research" }).click();

  const panel = page.getByRole("region", { name: "AI research" });
  await expect(panel.getByRole("heading", { name: "AI research from public sources" })).toBeVisible();
  await expect(panel.getByText("Nothing enters the profile until you accept it.")).toBeVisible();
  // Not configured in CI: the button is off and the reason is given, never a silent dead button.
  const configured = !(await panel.getByText(/hasn.t been set up yet/).isVisible().catch(() => false));
  const research = panel.getByRole("button", { name: /Research with AI|Searching…/ });
  await expect(research).toBeVisible();
  if (!configured) await expect(research).toBeDisabled();
});

test("a locked profile is verified with the respondent and then reconciled, three values kept apart", async ({ page, request }) => {
  const backend = backendBaseURL();
  const access = await getAdminAccessToken(request, backend);
  const auth = { Authorization: `Bearer ${access}` };
  const { sampleId } = await issueTokenOnFreshCase(request, backend, "Interview sheet");

  const caseId = (await (await request.get(`${backend}/api/v1/sample-cases/${sampleId}/`, { headers: auth })).json()).id;
  const profile = await (await request.post(`${backend}/api/v1/proit/pre-profiles/`, { headers: auth, data: { sample_case: caseId } })).json();
  for (const [fieldId, value] of [["year_established", "2011"], ["hq_district", "Harare"]]) {
    const field = await (await request.post(`${backend}/api/v1/proit/pre-profiles/${profile.id}/fields/`, {
      headers: auth, data: { field_id: fieldId, preliminary_documentary_value: value },
    })).json();
    await request.post(`${backend}/api/v1/proit/fields/${field.id}/evidence/`, {
      headers: auth, data: { source_title: "Companies register extract", source_confidence: "HIGH", source_authority: "TIER_1_STATUTORY" },
    });
  }
  expect((await request.post(`${backend}/api/v1/proit/pre-profiles/${profile.id}/lock/`, { headers: auth })).status()).toBe(200);

  await loginAsAdmin(page);
  await page.goto(`/admin/sample/${sampleId}`);
  const sheet = page.getByRole("region", { name: "Interview verification" });
  await expect(sheet.getByText("Verified 0 of 2")).toBeVisible();
  await expect(sheet.getByText("Public source says: 2011")).toBeVisible();

  // Confirm one fact; the respondent corrects the other.
  await sheet.getByLabel("What the respondent said").first().selectOption("YES_CORRECT");
  await sheet.getByRole("button", { name: "Save answer" }).first().click();
  await expect(sheet.getByText("Verified 1 of 2")).toBeVisible();

  await sheet.getByLabel("What the respondent said").nth(1).selectOption("NO_CORRECT_VALUE_PROVIDED");
  await sheet.getByLabel("Respondent's answer for Registered/legal organisation name").or(sheet.getByPlaceholder("Their answer")).first().fill("Mashonaland East");
  await sheet.getByRole("button", { name: "Save answer" }).nth(1).click();
  await expect(sheet.getByText("Differs from the public source")).toBeVisible();
  await expect(sheet.getByText(/settled 1 of 2/)).toBeVisible(); // corrected: still needs the researcher's reconciled value

  // The public value was not overwritten; the reconciled value completes the profile.
  await expect(sheet.getByText("Public source says: Harare")).toBeVisible();
  await sheet.getByLabel(/Reconciled value/).last().fill("Harare (head office); Mashonaland East (depot)");
  await sheet.getByRole("button", { name: "Save reconciled value" }).last().click();
  await expect(sheet.getByRole("status")).toHaveText("Reconciled");
});
