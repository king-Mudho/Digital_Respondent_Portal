import { expect, test } from "@playwright/test";
import { backendBaseURL, getAdminAccessToken, loginAsAdmin } from "./helpers";

/**
 * Registers show 20 rows by default and let the person choose 10, 20, 50, 100 or 200; the
 * choice is remembered. (Before, 20 was the only size and the register had no way to see more.)
 */
test("a register lets you choose how many rows to show, and remembers it", async ({ page, request }) => {
  const backend = backendBaseURL();
  const access = await getAdminAccessToken(request, backend);
  // Enough records for more than one page at 10 a page, wherever this runs.
  for (let n = 0; n < 22; n++) {
    await request.post(`${backend}/api/v1/documents/`, {
      headers: { Authorization: `Bearer ${access}` },
      data: { title: `E2E Paging ${Date.now()}-${n}`, document_type: "PLATFORM" },
    });
  }

  await loginAsAdmin(page);
  await page.goto("/admin/documents");
  const status = page.getByRole("status").filter({ hasText: /^Showing / });
  await expect(status).toContainText(/Showing 1 to 20 of \d+ documents/);

  const size = page.getByLabel("Rows per page");
  await expect(size.locator("option")).toHaveText(["10", "20", "50", "100", "200"]);

  const ten = page.waitForRequest((r) => r.url().includes("page_size=10"));
  await size.selectOption("10");
  await ten;
  await expect(status).toContainText(/Showing 1 to 10 of \d+ documents/);

  await page.getByRole("button", { name: "Page 2", exact: true }).click();
  await expect(status).toContainText(/Showing 11 to 20 of \d+ documents/);
  await expect(page.getByRole("button", { name: "Page 2", exact: true })).toHaveAttribute("aria-current", "page");

  // Changing the size goes back to the first page.
  await size.selectOption("50");
  await expect(status).toContainText(/Showing 1 to (50|\d+) of \d+ documents/);
  await expect(page.getByRole("button", { name: "Page 1", exact: true })).toHaveAttribute("aria-current", "page");

  // Remembered: another register, and a fresh load, both open at 50.
  await page.goto("/admin/kii");
  await expect(page.getByLabel("Rows per page")).toHaveValue("50");
  await page.reload();
  await expect(page.getByLabel("Rows per page")).toHaveValue("50");

  // First / last / previous / next
  await page.goto("/admin/documents");
  await page.getByLabel("Rows per page").selectOption("10");
  await page.getByRole("button", { name: "Last page" }).click();
  await expect(page.getByRole("button", { name: "Next page" })).toBeDisabled();
  await page.getByRole("button", { name: "First page" }).click();
  await expect(page.getByRole("button", { name: "Previous page" })).toBeDisabled();
});
