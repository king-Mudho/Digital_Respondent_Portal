import { expect, test } from "@playwright/test";
import { backendBaseURL, getAdminAccessToken, loginAsAdmin } from "./helpers";

/**
 * Document detail page (A08): docs/14_DOCUMENTARY_EVIDENCE_MODULE.md's
 * provenance rule -- a document cannot be marked INCLUDED before its
 * authenticity has been assessed.
 *
 * The gate is checked at both layers, deliberately. The UI now disables
 * "Include" while the document is UNVERIFIED (the end-to-end audit pass:
 * don't offer a control that can only fail), so the earlier version of
 * this test -- which clicked Include and waited for the server's error --
 * can no longer click it. The server-side gate is therefore asserted
 * directly against the API, which is the guarantee that actually matters;
 * the disabled button is asserted separately as the UI half.
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

  // The real gate: the API refuses INCLUDED regardless of what any client
  // does, so a caller bypassing the UI entirely still cannot get past it.
  const refused = await request.post(`${backend}/api/v1/documents/${doc.id}/qa-status/`, {
    headers: { Authorization: `Bearer ${access}` },
    data: { qa_status: "INCLUDED" },
  });
  expect(refused.status()).toBe(400);
  expect(JSON.stringify(await refused.json())).toMatch(/authenticity has been assessed/i);

  await loginAsAdmin(page);
  await page.goto(`/admin/documents/${doc.id}`);

  await expect(page.getByText("Authenticity: UNVERIFIED")).toBeVisible();
  await expect(page.getByText("Cannot be included until authenticity is assessed.")).toBeVisible();
  await expect(page.getByRole("button", { name: "Include" })).toBeDisabled();
  await expect(page.getByText("QA status: PENDING")).toBeVisible();

  await page.getByRole("button", { name: "Mark verified" }).click();
  await expect(page.getByText("Authenticity: VERIFIED")).toBeVisible();
  await expect(page.getByText("Cannot be included until authenticity is assessed.")).toHaveCount(0);

  await expect(page.getByRole("button", { name: "Include" })).toBeEnabled();
  await page.getByRole("button", { name: "Include" }).click();
  await expect(page.getByText("QA status: INCLUDED")).toBeVisible();
});
