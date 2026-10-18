import { expect, test } from "@playwright/test";
import { loginAsAdmin } from "./helpers";

/**
 * Cost dashboard (A10): the "log a cost event" form was added alongside
 * the sampling/contacts fixes in the same hardening pass. Confirms the
 * form actually persists a cost event and the total-spend figure
 * increases by the logged amount, rather than just rendering. Compares
 * before/after numerically (not string equality) since total spend
 * accumulates across every cost event ever logged, including from other
 * runs against a database that isn't reset between suite runs.
 */
test("recording a cost lists it with what it was for and increases the total spend", async ({ page }) => {
  await loginAsAdmin(page);
  await page.goto("/admin/cost");

  const totalCard = page.locator("text=Total spend").locator("..");
  const parseTotal = async () => {
    const text = await totalCard.innerText();
    return Number(text.replace(/[^0-9.]/g, ""));
  };

  const before = await parseTotal();

  // The form says what the money was for (2026-10-18); the entry then appears in the "All costs" table.
  const form = page.getByRole("heading", { name: "Record a cost" }).locator("..");
  const what = `E2E bus fare ${Date.now()}`;
  await form.getByLabel("Category").selectOption("TRANSPORT");
  await form.getByLabel("What it was for").fill(what);
  await form.getByLabel("Paid to (optional)").fill("Harare Bus Co");
  await form.getByLabel("Amount (USD)").fill("12.34");
  await form.getByRole("button", { name: "Record cost" }).click();

  await expect(page.getByRole("cell", { name: what })).toBeVisible();
  await expect(async () => {
    const after = await parseTotal();
    expect(after).toBeCloseTo(before + 12.34, 2);
  }).toPass({ timeout: 5000 });
});
