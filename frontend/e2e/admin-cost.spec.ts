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
test("logging a cost event increases the total spend by the logged amount", async ({ page }) => {
  await loginAsAdmin(page);
  await page.goto("/admin/cost");

  const totalCard = page.locator("text=Total spend").locator("..");
  const parseTotal = async () => {
    const text = await totalCard.innerText();
    return Number(text.replace(/[^0-9.]/g, ""));
  };

  const before = await parseTotal();

  await page.locator("select").first().selectOption("TRANSPORT");
  await page.getByPlaceholder("Amount").fill("12.34");
  await page.getByRole("button", { name: "Log cost" }).click();

  await expect(page.getByRole("cell", { name: "TRANSPORT" })).toBeVisible();
  await expect(async () => {
    const after = await parseTotal();
    expect(after).toBeCloseTo(before + 12.34, 2);
  }).toPass({ timeout: 5000 });
});
