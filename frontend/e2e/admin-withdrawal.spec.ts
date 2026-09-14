import { expect, test } from "@playwright/test";
import { backendBaseURL, issueTokenOnFreshCase, loginAsAdmin } from "./helpers";

/**
 * docs/28 go-live checklist: "Withdrawal and consent-revocation procedures
 * are operationally testable." Until 2026-09-14 there was no way for staff
 * to record a withdrawal at all.
 */
test("a coordinator records a withdrawal and the participant's link stops working", async ({ page, request }) => {
  const { token, sampleId } = await issueTokenOnFreshCase(request, backendBaseURL(), "Withdrawal");

  await loginAsAdmin(page);
  await page.goto(`/admin/sample/${sampleId}`);
  const panel = page.locator("div", { has: page.getByRole("heading", { name: "Record a withdrawal" }) }).last();
  await expect(panel.getByRole("button", { name: "Record withdrawal" })).toBeDisabled();

  await panel.getByLabel("Reason or their words").fill("Called the study line and asked to withdraw.");
  page.once("dialog", (dialog) => dialog.accept());
  await panel.getByRole("button", { name: "Record withdrawal" }).click();
  await expect(panel.getByText(/Withdrawal recorded\. 1 invitation\(s\) revoked/)).toBeVisible();

  await page.goto(`/i/${token}`);
  await expect(page.getByText("Invitation not valid")).toBeVisible();
});
