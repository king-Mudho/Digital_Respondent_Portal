import { expect, test } from "@playwright/test";
import { backendBaseURL, getAdminAccessToken, issueTokenOnFreshCase, loginAsAdmin } from "./helpers";

/**
 * apps/clearance (2026-09-30): the letters proving this study is genuine and authorised, managed by the PI
 * and shown to a respondent on the information step of their own invitation link. A document must be
 * explicitly switched on before a respondent sees it, and never appears at all once switched off again.
 */

test("a clearance document is invisible to a respondent until switched on, then invisible again once switched off", async ({
  page,
  request,
}) => {
  const backend = backendBaseURL();
  const { token } = await issueTokenOnFreshCase(request, backend, "Clearance");
  const access = await getAdminAccessToken(request, backend);
  const auth = { Authorization: `Bearer ${access}` };

  await loginAsAdmin(page);
  await page.goto("/admin/clearance");

  const title = `E2E Ethics Clearance ${Date.now()}`;
  await page.getByPlaceholder("e.g. Research Ethics Clearance Letter").fill(title);
  await page.getByPlaceholder("e.g. Chinhoyi University of Technology").fill("Chinhoyi University of Technology");
  await page.getByPlaceholder("e.g. Annex 19, Form GRSD 17 SEBS/06/2025").fill("Annex 19, Form GRSD 17 SEBS/06/2025");
  await page.getByRole("button", { name: "Add document" }).click();

  // A bare `page.locator("div").filter({ hasText: title })` matches every ancestor div up to the page
  // root too (each "has" the title as descendant text), and neither .first() nor .last() reliably lands on
  // the one per-document row -- .py-3.space-y-2 is that row's own class pair, on no other element on the page.
  const rowFor = (heading: string) => page.locator("div.py-3.space-y-2").filter({ hasText: heading });

  const row = rowFor(title);
  await expect(row.getByText("No file uploaded yet")).toBeVisible();

  // Before it has a file, a respondent visiting the information step doesn't see THIS document -- scoped
  // rather than asserting the whole section is absent, since a past run of this same test may have left its
  // own document permanently public (the very rule proven later in this test), which would still show.
  await page.goto(`/i/${token}/information`);
  await expect(page.locator("li").filter({ hasText: title })).toHaveCount(0);

  // Upload the letter and switch it on.
  await page.goto("/admin/clearance");
  const rowAfterReload = rowFor(title);
  await rowAfterReload.locator('input[type="file"]').setInputFiles({
    name: "ethics-clearance.pdf",
    mimeType: "application/pdf",
    buffer: Buffer.from("%PDF-1.4 e2e clearance letter"),
  });
  await expect(rowAfterReload.getByText(/File: ethics-clearance\.pdf/)).toBeVisible();
  // The checkbox is controlled by query data, so it snaps back right after the native click until the
  // PATCH resolves and the refetch lands -- .check() sees that snap-back as "did not change its state" and
  // throws before the mutation settles. Click it and wait for the eventual checked state instead.
  const shownCheckbox = rowAfterReload.getByLabel("Shown to respondents");
  await shownCheckbox.click();
  await expect(shownCheckbox).toBeChecked();

  // Now the respondent sees it, with a working link to the actual letter. Every past run of this test
  // left behind its own permanently-public document (that's the very rule being proven below), all sharing
  // this same reference number, so scope to this run's own <li> rather than a page-wide text search.
  await page.goto(`/i/${token}/information`);
  await expect(page.getByText("How to verify this is a genuine study")).toBeVisible();
  const respondentItem = page.locator("li").filter({ hasText: title });
  await expect(respondentItem).toBeVisible();
  await expect(respondentItem.getByText("Annex 19, Form GRSD 17 SEBS/06/2025")).toBeVisible();

  // The link opens the PDF in a new tab, which the browser may hand straight to its download machinery
  // rather than firing an ordinary page "response" -- fetch the same href directly instead, which proves
  // the token-gated file endpoint actually serves the real bytes without depending on that browser behaviour.
  const fileHref = await respondentItem.getByRole("link", { name: "View letter" }).getAttribute("href");
  const fileResponse = await request.get(fileHref!);
  expect(fileResponse.status()).toBe(200);

  // Switch it off again -- it must disappear for the respondent immediately, not just for new documents.
  await page.goto("/admin/clearance");
  const hideCheckbox = rowFor(title).getByLabel("Shown to respondents");
  await hideCheckbox.click();
  await expect(hideCheckbox).not.toBeChecked();
  await page.goto(`/i/${token}/information`);
  // Scoped to this run's own document, not a page-wide check of the whole section -- a past run of this
  // same test left its own document permanently public (the very rule the next block proves), so the
  // section itself can legitimately still be showing for other documents.
  await expect(page.locator("li").filter({ hasText: title })).toHaveCount(0);

  // A document that was ever made public can't be deleted from the API, even after being hidden again --
  // the admin UI disables the button, but the server is the actual boundary.
  const list = await request.get(`${backend}/api/v1/clearance-documents/`, { headers: auth });
  const created = (await list.json()).results.find((d: { title: string }) => d.title === title);
  const deleteAttempt = await request.delete(`${backend}/api/v1/clearance-documents/${created.id}/`, { headers: auth });
  expect(deleteAttempt.status()).toBe(409);
});

