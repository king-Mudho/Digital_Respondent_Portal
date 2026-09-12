import { expect, test } from "@playwright/test";
import { backendBaseURL, getAdminAccessToken, loginAsAdmin } from "./helpers";

/**
 * Document detail page (A08): docs/14_DOCUMENTARY_EVIDENCE_MODULE.md's
 * provenance rule -- a document cannot be marked INCLUDED before its
 * authenticity has been assessed. Confirms the gate is enforced by the
 * backend (a 400 from the API), not only hidden behind a disabled button,
 * then confirms it actually opens up once verified.
 */
test("a document cannot be included until its authenticity is assessed", async ({ page, request }) => {
  const backend = backendBaseURL();
  const access = await getAdminAccessToken(request, backend);

  const createResponse = await request.post(`${backend}/api/v1/documents/`, {
    headers: { Authorization: `Bearer ${access}` },
    data: {
      title: "E2E Playwright Policy Brief",
      document_type: "OFFICIAL",
      evidence_extract: "E2E test evidence extract.",
    },
  });
  expect(createResponse.status()).toBe(201);
  const doc = await createResponse.json();
  expect(doc.authenticity_assessment).toBe("UNVERIFIED");

  await loginAsAdmin(page);
  await page.goto(`/admin/documents/${doc.id}`);

  await expect(page.getByText("Authenticity: UNVERIFIED")).toBeVisible();
  await expect(page.getByText("Cannot be included until authenticity is assessed.")).toBeVisible();

  await page.getByRole("button", { name: "Include" }).click();
  await expect(page.getByText(/authenticity has been assessed/i)).toBeVisible();
  await expect(page.getByText("QA status: PENDING")).toBeVisible();

  await page.getByRole("button", { name: "Mark verified" }).click();
  await expect(page.getByText("Authenticity: VERIFIED")).toBeVisible();
  await expect(page.getByText("Cannot be included until authenticity is assessed.")).toHaveCount(0);

  await page.getByRole("button", { name: "Include" }).click();
  await expect(page.getByText("QA status: INCLUDED")).toBeVisible();
});
