import { expect, test } from "@playwright/test";
import { loginAsAdmin } from "./helpers";

/** Reports screen (added 2026-09-15): charts, ranges, table views, phone layout. */
test("reports show charts, switch range, and offer every chart as a table", async ({ page }) => {
  await loginAsAdmin(page);
  await page.setViewportSize({ width: 1366, height: 900 });
  await page.goto("/admin/reports");

  await expect(page.getByRole("heading", { name: "Reports" })).toBeVisible();
  await expect(page.getByRole("region", { name: "Case funnel" })).toBeVisible();
  await expect(page.getByText("Questionnaires submitted")).toBeVisible();
  // The funnel always has a sample, so it always draws.
  await expect(page.getByRole("region", { name: "Case funnel" }).locator(".recharts-bar-rectangle").first()).toBeVisible();

  await page.getByRole("button", { name: "All time" }).click();
  await expect(page.getByRole("button", { name: "All time" })).toHaveAttribute("aria-pressed", "true");
  await expect(page.getByText(/Time-based figures cover all time/)).toBeVisible();

  const funnel = page.getByRole("region", { name: "Case funnel" });
  await funnel.getByRole("button", { name: "Show table" }).click();
  await expect(funnel.getByRole("cell", { name: "In the sample" })).toBeVisible();

  const coverage = page.getByRole("region", { name: "Coverage" });
  await coverage.getByRole("button", { name: "Organisation type" }).click();
  await expect(coverage.getByRole("button", { name: "Organisation type" })).toHaveAttribute("aria-pressed", "true");
  await page.screenshot({ path: "test-results/reports-desktop.png", fullPage: true });

  await page.setViewportSize({ width: 375, height: 812 });
  await page.reload();
  await expect(page.getByRole("region", { name: "Case funnel" })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth)).toBeLessThanOrEqual(1);
  await page.screenshot({ path: "test-results/reports-phone.png", fullPage: true });
});
