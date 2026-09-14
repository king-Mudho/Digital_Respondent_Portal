import { expect, test } from "@playwright/test";
import { loginAsAdmin } from "./helpers";

/**
 * Completed-form PDFs (added 2026-09-14). Runs fully only when the backend
 * can reach a KoboToolbox API with at least one questionnaire submission;
 * otherwise it checks the screen explains why nothing is listed.
 *
 * The download assertion guards the /api/proxy fix: the relay read every
 * response as text, which re-encoded PDF bytes and corrupted every download.
 */
test("a completed questionnaire downloads as an intact PDF", async ({ page }) => {
  await loginAsAdmin(page);
  await page.goto("/admin/submissions");
  await expect(page.getByRole("heading", { name: "Completed form PDFs" })).toBeVisible();

  const notConnected = page.getByText(/isn't connected to KoboToolbox yet/);
  const download = page.getByRole("button", { name: "Download PDF" }).first();
  await expect(notConnected.or(download).or(page.getByText("No submissions yet."))).toBeVisible();
  test.skip(!(await download.isVisible()), "No KoboToolbox submissions reachable from this environment.");

  const [file] = await Promise.all([page.waitForEvent("download"), download.click()]);
  expect(file.suggestedFilename()).toMatch(/^questionnaire-.+\.pdf$/);
  const stream = await file.createReadStream();
  const chunks: Buffer[] = [];
  for await (const chunk of stream) chunks.push(chunk as Buffer);
  const bytes = Buffer.concat(chunks);

  expect(bytes.subarray(0, 5).toString("latin1")).toBe("%PDF-");
  expect(bytes.subarray(-6).toString("latin1")).toContain("%%EOF");
  // Binary content survived: a text round-trip turns every byte above 0x7F into
  // the three-byte replacement character EF BF BD.
  expect(bytes.includes(Buffer.from([0xef, 0xbf, 0xbd]))).toBe(false);
});
