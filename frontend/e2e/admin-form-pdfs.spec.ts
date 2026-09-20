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
  await expect(page.getByRole("heading", { name: "Completed forms" })).toBeVisible();

  // Not connected, or connected to something that isn't a usable form (CI's
  // placeholder asset and token): the screen must explain it either way.
  const notConnected = page.getByText(/isn't connected to KoboToolbox yet|wasn't found in KoboToolbox|KoboToolbox refused|KoboToolbox couldn't be reached|KoboToolbox answered HTTP/);
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

test("the PI downloads a form's full data workbook and all its PDFs intact", async ({ page }) => {
  await loginAsAdmin(page);
  await page.goto("/admin/export");
  const card = page.getByRole("main");
  await expect(card.getByRole("link", { name: "Excel workbook" }).first()).toBeVisible();

  const probe = await page.request.get("/api/proxy/kobo/forms/questionnaire/export/xlsx/");
  test.skip(probe.status() !== 200, `No usable KoboToolbox form in this environment (HTTP ${probe.status()}).`);

  const read = async (linkName: string) => {
    const [file] = await Promise.all([page.waitForEvent("download"), card.getByRole("link", { name: linkName }).first().click()]);
    const chunks: Buffer[] = [];
    for await (const chunk of await file.createReadStream()) chunks.push(chunk as Buffer);
    return { name: file.suggestedFilename(), bytes: Buffer.concat(chunks) };
  };

  const workbook = await read("Excel workbook");
  expect(workbook.name).toMatch(/^questionnaire-data-.+\.xlsx$/);
  expect(workbook.bytes.subarray(0, 2).toString("latin1")).toBe("PK"); // a real zip container, not re-encoded text

  const zip = await read("All completed forms (PDF ZIP)");
  expect(zip.name).toMatch(/^questionnaire-completed-forms-.+\.zip$/);
  expect(zip.bytes.subarray(0, 2).toString("latin1")).toBe("PK");
  expect(zip.bytes.includes(Buffer.from("manifest.csv"))).toBe(true);
});
