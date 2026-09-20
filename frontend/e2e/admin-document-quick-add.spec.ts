import { expect, test } from "@playwright/test";
import { backendBaseURL, getAdminAccessToken, loginAsAdmin } from "./helpers";

/**
 * Quick add: upload a document and the AI fills in the record and drafts the form. CI has no
 * ANTHROPIC_API_KEY, so the AI part is refused with a plain message here; the AI itself is mocked in
 * the backend tests. What this proves is that the screen is reachable, asks for a file, refuses
 * cleanly, and that the record's details can be corrected by hand (where AI-filled details get checked).
 */
test("quick add asks for a file and says plainly when AI drafting isn't set up", async ({ page }) => {
  await loginAsAdmin(page);
  await page.goto("/admin/documents/new");
  const quick = page.getByRole("form", { name: "Quick add from a file" });
  await expect(quick.getByText("Fastest: upload the document")).toBeVisible();

  await quick.getByRole("button", { name: "Upload and auto-fill" }).click();
  await expect(quick.getByText("Choose the document to upload first.")).toBeVisible();

  await quick.getByLabel("Document file").setInputFiles({ name: "circular.pdf", mimeType: "application/pdf", buffer: Buffer.from("%PDF-1.4 x") });
  await quick.getByRole("button", { name: "Upload and auto-fill" }).click();
  await expect(quick.getByText(/hasn.t been set up/)).toBeVisible();
  await expect(page).toHaveURL(/\/admin\/documents\/new$/); // nothing was created, nowhere to be sent
});

test("a record's details can be corrected on its page", async ({ page, request }) => {
  const backend = backendBaseURL();
  const access = await getAdminAccessToken(request, backend);
  const created = await request.post(`${backend}/api/v1/documents/`, {
    headers: { Authorization: `Bearer ${access}` },
    data: { title: "E2E details before", document_type: "OFFICIAL" },
  });
  const doc = await created.json();

  await loginAsAdmin(page);
  await page.goto(`/admin/documents/${doc.id}`);
  await page.getByLabel("Title", { exact: true }).fill("E2E details after");
  await page.getByLabel("Author / speaker").fill("Ministry of Examples");
  await page.getByLabel("Publication or event date").fill("2026-03-12");
  await page.getByRole("button", { name: "Save details" }).click();
  await expect(page.getByText("Details saved.")).toBeVisible();

  await page.reload();
  await expect(page.getByLabel("Title", { exact: true })).toHaveValue("E2E details after");
  await expect(page.getByLabel("Author / speaker")).toHaveValue("Ministry of Examples");
  await expect(page.getByLabel("Publication or event date")).toHaveValue("2026-03-12");
});
