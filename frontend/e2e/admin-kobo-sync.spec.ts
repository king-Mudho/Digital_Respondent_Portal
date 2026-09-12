import { expect, test } from "@playwright/test";
import { loginAsAdmin } from "./helpers";

/**
 * QA queue (A06) "KoboToolbox sync" panel -- added in this hardening pass
 * alongside apps.kobo.client.KoboClient's pagination fix and reconcile()'s
 * graceful-failure handling (backend/tests/test_kobo.py).
 *
 * This environment has no real Kobo asset provisioned (KOBO_ASSET_UID is a
 * placeholder / empty in dev, staging and CI alike -- see
 * docs/11_KOBOTOOLBOX_INTEGRATION.md "Implementation status"), which is
 * exactly the PI-blocked state this test documents: a real KoboToolbox
 * production account and asset are the PI's responsibility to provision
 * (docs/28_DEFINITION_OF_DONE.md), not something this suite can fake.
 * What IS this suite's job is confirming the app never crashes or hangs
 * when Kobo is unreachable/unconfigured -- it must show a clear failure
 * message and leave the page usable, which is what got fixed this pass
 * (previously an uncaught exception surfaced as a raw 500).
 */
test("Kobo sync panel degrades gracefully when no real Kobo asset is configured", async ({ page }) => {
  await loginAsAdmin(page);
  await page.goto("/admin/qa");

  await expect(page.getByText("KoboToolbox sync")).toBeVisible();
  await page.getByRole("button", { name: "Sync now" }).click();

  // Never hangs forever, never crashes the page -- resolves to either a
  // successful run (if this environment is ever pointed at a real test
  // asset) or a clearly surfaced failure message (the expected outcome
  // today, with no KOBO_ASSET_UID configured).
  await expect(page.getByRole("button", { name: "Sync now" })).toBeVisible({ timeout: 15000 });
  const pageText = await page.locator("main").innerText();
  expect(pageText).toMatch(/Last sync failed|pulled.*new.*updated/);

  // The rest of the page must still be fully usable after a failed sync --
  // this is the actual regression this pass fixed (a raw 500 used to
  // propagate out of the manual-trigger endpoint).
  await expect(page.getByText("QUAN QA Queue")).toBeVisible();
});
