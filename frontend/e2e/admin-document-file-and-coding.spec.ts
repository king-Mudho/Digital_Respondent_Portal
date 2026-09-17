import { expect, test } from "@playwright/test";
import { backendBaseURL, getAdminAccessToken, loginAsAdmin } from "./helpers";

/**
 * docs/14_DOCUMENTARY_EVIDENCE_MODULE.md: document analysis is done on the
 * platform, not by hand -- the source file lives on the document record
 * (uploaded once, downloadable by anyone with document access), and coding
 * happens in KoboToolbox's Document Analysis Tool via a link that's
 * prefilled with the record's DOC-ID and details, so a Documentary RA
 * never retypes them.
 */
test("a document's source file can be uploaded, and the coding link is prefilled", async ({ page, request }) => {
  const backend = backendBaseURL();
  const access = await getAdminAccessToken(request, backend);

  const createResponse = await request.post(`${backend}/api/v1/documents/`, {
    headers: { Authorization: `Bearer ${access}` },
    data: {
      title: "E2E Platform Screenshot Source",
      author_or_speaker: "E2E Test Platform",
      document_type: "PLATFORM",
    },
  });
  expect(createResponse.status()).toBe(201);
  const doc = await createResponse.json();

  await loginAsAdmin(page);
  await page.goto(`/admin/documents/${doc.id}`);

  // No file yet.
  await expect(page.getByText("No file uploaded yet.")).toBeVisible();

  // Upload a source file through the real multipart proxy path.
  await page.setInputFiles('input[type="file"]', {
    name: "source.pdf",
    mimeType: "application/pdf",
    buffer: Buffer.from("%PDF-1.4 e2e test file"),
  });
  await expect(page.getByRole("link", { name: /source\.pdf/ })).toBeVisible();
  await expect(page.getByText(/uploaded/)).toBeVisible();

  // The download link goes through the same proxy and returns the file.
  const downloadResponse = await request.get(`${backend}/api/v1/documents/${doc.id}/file/`, {
    headers: { Authorization: `Bearer ${access}` },
  });
  expect(downloadResponse.status()).toBe(200);
  expect((await downloadResponse.body()).toString()).toContain("e2e test file");

  // The coding link is prefilled with this record's DOC-ID and details --
  // set via KOBO_DOCUMENTS_FORM_URL in CI (.github/workflows/ci.yml).
  const codingLink = page.getByRole("link", { name: "Code this document" });
  await expect(codingLink).toBeVisible();
  const href = await codingLink.getAttribute("href");
  expect(decodeURIComponent(href!)).toContain(`d[section_a/DOC_ID]=${doc.document_id}`);
  expect(decodeURIComponent(href!)).toContain("d[section_a/org_author]=E2E Test Platform");
});

test("an unsupported file is refused with a clear message, and the field is ready for another try", async ({
  page,
  request,
}) => {
  const backend = backendBaseURL();
  const access = await getAdminAccessToken(request, backend);

  const createResponse = await request.post(`${backend}/api/v1/documents/`, {
    headers: { Authorization: `Bearer ${access}` },
    data: { title: "E2E Rejected Upload Source", document_type: "PLATFORM" },
  });
  const doc = await createResponse.json();

  await loginAsAdmin(page);
  await page.goto(`/admin/documents/${doc.id}`);

  const fileInput = page.locator('input[type="file"]');
  await fileInput.setInputFiles({
    name: "malware.exe",
    mimeType: "application/x-msdownload",
    buffer: Buffer.from("not really an executable"),
  });
  await expect(page.getByText(/aren.t accepted/)).toBeVisible();
  await expect(page.getByText("No file uploaded yet.")).toBeVisible(); // nothing was saved

  // The field must be cleared, not just visually reset: a browser only
  // fires "change" when the selected file differs from what's already
  // there, so a stale value would silently swallow a retry of the exact
  // same path (e.g. after renaming/converting the same file).
  await expect(fileInput).toHaveValue("");

  // A valid file straight after the rejection still works.
  await fileInput.setInputFiles({
    name: "retry.pdf",
    mimeType: "application/pdf",
    buffer: Buffer.from("%PDF-1.4 retry after rejection"),
  });
  await expect(page.getByRole("link", { name: "retry.pdf" })).toBeVisible();
});
