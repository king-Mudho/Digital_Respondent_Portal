import { expect, test } from "@playwright/test";
import { backendBaseURL, issueTokenOnFreshCase, loginAsAdmin } from "./helpers";

/**
 * Recording a respondent's contact details on the case page (added
 * 2026-09-14). Before, staff could not add or correct a phone number at all.
 */
test("a person and their WhatsApp number can be added and corrected on a phone", async ({ page, request }) => {
  const { sampleId } = await issueTokenOnFreshCase(request, backendBaseURL(), "Contacts");

  await loginAsAdmin(page);
  await page.setViewportSize({ width: 375, height: 812 });
  await page.goto(`/admin/sample/${sampleId}`);

  const panel = page.getByRole("region", { name: "Respondents and contact details" });
  await expect(panel.getByText("No one recorded for this case yet.")).toBeVisible();

  await panel.getByRole("button", { name: "Add a person" }).click();
  await panel.getByLabel("Full name").fill("Rudo Chari");
  await panel.getByLabel("Phone").fill("0772 000 111");
  await panel.getByLabel("Role").selectOption("CEO_MD");
  await panel.getByRole("button", { name: "Save person" }).click();
  await expect(panel.getByText("Phone 0772 000 111")).toBeVisible();
  await expect(panel.getByText("Not yet screened")).toBeVisible();

  await panel.getByRole("button", { name: "Edit" }).click();
  await panel.getByLabel("WhatsApp number").fill("0772000111");
  await panel.getByLabel("Eligibility").selectOption("yes");
  await panel.getByRole("button", { name: "Save changes" }).click();
  await expect(panel.getByText(/WhatsApp 0772000111/)).toBeVisible();
  await expect(panel.getByText(/Eligible \(checked by /)).toBeVisible();

  expect(await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1)).toBe(false);
});
