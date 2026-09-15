import { expect, test } from "@playwright/test";
import { backendBaseURL, issueTokenOnFreshCase, loginAsAdmin } from "./helpers";

/**
 * Reassigning Main cases in bulk from the register (added 2026-09-15): all
 * 400 started on one shared Contact RA account.
 */
test("the coordinator moves a chosen number of cases to a Contact RA, after confirming", async ({ page, request }) => {
  await issueTokenOnFreshCase(request, backendBaseURL(), "Bulk assign"); // at least one unassigned Harare case

  await loginAsAdmin(page);
  await page.goto("/admin/sample");
  const panel = page.getByRole("heading", { name: "Reassign cases" }).locator("xpath=ancestor::div[contains(@class,'rounded-lg')][1]");
  await expect(panel).toBeVisible();

  await panel.getByLabel("From").selectOption("unassigned");
  await panel.getByLabel("Province").selectOption("HARARE");
  await panel.getByLabel("How many").fill("1");
  await panel.getByLabel("To").selectOption({ label: "e2e_contact_ra" });
  const move = panel.getByRole("button", { name: "Move 1 case" });
  await expect(move).toBeEnabled();

  let asked = "";
  page.once("dialog", (dialog) => {
    asked = dialog.message();
    dialog.accept();
  });
  await move.click();
  await expect(panel.getByText("Moved 1 case to e2e_contact_ra.")).toBeVisible();
  expect(asked).toContain("Move 1 Main case to e2e_contact_ra?");
});
