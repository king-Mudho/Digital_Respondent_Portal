import { expect, test } from "@playwright/test";
import { loginAsAdmin } from "./helpers";

/**
 * docs/22_TESTING_STRATEGY.md: "internal-role login -> every dashboard
 * renders without exposing any individual organisation/respondent name."
 */
const DASHBOARD_PATHS = [
  "/admin/dashboard",
  "/admin/dashboard/sampling",
  "/admin/dashboard/contact",
  "/admin/dashboard/kii-documents",
  "/admin/cost",
];

const IDENTIFYING_STRINGS = ["E2E Test Farming Trust", "E2E Locked Reserve Trust", "E2E Respondent", "E2E Test Respondent"];

test("every aggregate dashboard renders without an organisation or respondent name", async ({ page }) => {
  await loginAsAdmin(page);

  for (const path of DASHBOARD_PATHS) {
    await page.goto(path);
    await expect(page.getByText("Loading…")).toHaveCount(0, { timeout: 10000 });

    const bodyText = await page.locator("main").innerText();
    for (const identifying of IDENTIFYING_STRINGS) {
      expect(bodyText, `${path} leaked "${identifying}"`).not.toContain(identifying);
    }
  }
});
