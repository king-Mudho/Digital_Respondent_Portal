import { expect, test } from "@playwright/test";
import { backendBaseURL, issueFreshToken } from "./helpers";

/**
 * docs/22_TESTING_STRATEGY.md happy path: invitation validation ->
 * organisation confirmation -> eligibility -> consent -> participation
 * choice -> Kobo redirect. Scoped to what a browser can actually exercise:
 * the reconciliation/QA-queue/QA_PASSED tail of the documented happy path
 * is backend-only (no browser UI triggers a Kobo submission arriving) --
 * that portion is covered by tests/test_kobo.py and tests/test_qa.py on
 * the backend instead, not duplicated here as a fake browser step.
 */
test("respondent completes invitation through Kobo handoff", async ({ page, request }) => {
  const token = await issueFreshToken(request, backendBaseURL());

  await page.goto(`/i/${token}`);
  await page.waitForURL(`**/i/${token}/confirm`);
  await expect(page.getByText("Please confirm:")).toBeVisible();

  await page.getByRole("button", { name: "Yes, that's correct" }).click();
  await page.waitForURL(`**/i/${token}/eligibility`);

  await page.getByLabel("Your full name").fill("E2E Respondent");
  await page.getByLabel("Which best describes your role?").selectOption("CEO_MD");
  await page.getByRole("button", { name: "Continue" }).click();
  await page.waitForURL(`**/i/${token}/information`);

  await page.getByRole("button", { name: "Continue to consent" }).click();
  await page.waitForURL(`**/i/${token}/consent`);
  await expect(page.getByText(/No score, rating, or financing decision/)).toBeVisible();

  await page.getByRole("button", { name: "I agree to take part" }).click();
  await page.waitForURL(`**/i/${token}/choice`);

  await page.getByText("Complete it myself now").click();
  await page.waitForURL(`**/i/${token}/kobo-redirect`);
  await expect(page.getByRole("button", { name: "Start the questionnaire" })).toBeVisible({ timeout: 10000 });
});
