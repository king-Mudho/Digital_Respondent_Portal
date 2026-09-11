import { expect, test } from "@playwright/test";
import { backendBaseURL, issueFreshToken } from "./helpers";

/**
 * docs/22_TESTING_STRATEGY.md: "eligibility gate fails -> referral path
 * shown, questionnaire never reachable."
 */
test("ineligible respondent sees referral, never reaches consent or Kobo", async ({ page, request }) => {
  const token = await issueFreshToken(request, backendBaseURL());

  await page.goto(`/i/${token}/eligibility`);
  await page.getByLabel("Your full name").fill("Front Desk Receptionist");
  await page.getByLabel("Which best describes your role?").selectOption("NONE_OF_THESE");
  await page.getByRole("button", { name: "Continue" }).click();

  await expect(page.getByText("Thank you for your time")).toBeVisible();
  // Never redirected onward to information/consent/Kobo.
  await expect(page).toHaveURL(new RegExp(`/i/${token}/eligibility$`));
});
