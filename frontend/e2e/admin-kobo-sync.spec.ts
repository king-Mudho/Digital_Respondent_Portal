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
  const syncButton = page.getByRole("button", { name: "Sync now" });
  await expect(syncButton).toBeVisible();

  // Wait for the status to settle before deciding which state we're in.
  // isVisible() is instantaneous, so checking it straight away raced the
  // status request and took the wrong branch.
  const settled = page.getByText(/KoboToolbox is not connected yet|Last synced|No reconciliation run yet|Last sync failed/);
  await expect(settled.first()).toBeVisible();

  if (await page.getByText("KoboToolbox is not connected yet").isVisible()) {
    // No asset ID/API token here (dev, CI, and production until the PI
    // connects the form). Since 2026-09-14 that reads as a state, not as a
    // failed sync, and there is nothing to press.
    await expect(syncButton).toBeDisabled();
    await expect(page.getByText(/Last sync failed/)).toHaveCount(0);
  } else {
    // A connected (test) asset: a manual sync must resolve to a result or a
    // clearly surfaced failure, never hang or crash the page.
    await syncButton.click();
    // The button reads "Syncing…" while the run is in flight, and a request to
    // an unusable asset can take up to the client's 30s timeout. Checking the
    // "Sync now" button straight away passed before the click had registered.
    await expect(page.getByText(/Last sync failed|pulled.*new.*updated/)).toBeVisible({ timeout: 45_000 });
    await expect(syncButton).toBeEnabled();
  }

  // The rest of the page must still be fully usable after a failed sync --
  // this is the actual regression this pass fixed (a raw 500 used to
  // propagate out of the manual-trigger endpoint).
  await expect(page.getByText("QUAN QA Queue")).toBeVisible();
});
