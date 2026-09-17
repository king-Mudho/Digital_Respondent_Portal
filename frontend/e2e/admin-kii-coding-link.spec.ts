import { expect, test } from "@playwright/test";
import { backendBaseURL, getAdminAccessToken, loginAsAdmin } from "./helpers";

/**
 * docs/13_KII_MODULE.md: the KII Guide has the same "Code this document"-
 * style prefilled launch link as the Documentary Evidence module (built
 * the same day), but narrower -- a KIIRecord identifies a real person, so
 * the link is withheld entirely until participation consent is GIVEN, and
 * never carries participant_name/role/organisation in the URL.
 */
test("the KII interview link appears only after participation consent, and never carries participant identity", async ({
  page,
  request,
}) => {
  const backend = backendBaseURL();
  const access = await getAdminAccessToken(request, backend);
  const authHeader = { Authorization: `Bearer ${access}` };

  const createResponse = await request.post(`${backend}/api/v1/kii/`, {
    headers: authHeader,
    data: {
      stakeholder_category: "REGULATOR",
      participant_name: "E2E Coding Link Subject",
      participant_role: "Policy Officer",
      preferred_mode: "PHONE",
    },
  });
  expect(createResponse.status()).toBe(201);
  const kii = await createResponse.json();

  await loginAsAdmin(page);
  await page.goto(`/admin/kii/${kii.id}`);

  // Before consent: the form is configured (set via KOBO_KII_FORM_URL in
  // CI/.env), but the link is withheld and says why.
  await expect(page.getByText("Record participation consent first")).toBeVisible();
  await expect(page.getByRole("link", { name: "Continue this interview" })).toHaveCount(0);

  const isConsentResponse = (resp: import("@playwright/test").Response) =>
    resp.url().includes(`/kii/${kii.id}/consent`) && resp.request().method() === "POST" && resp.status() < 300;

  const [consentResponse] = await Promise.all([
    page.waitForResponse(isConsentResponse, { timeout: 15000 }),
    page.getByRole("button", { name: "Record participation consent" }).click(),
  ]);
  expect(consentResponse.status()).toBe(200);

  const codingLink = page.getByRole("link", { name: "Continue this interview" });
  await expect(codingLink).toBeVisible({ timeout: 15000 });
  const href = await codingLink.getAttribute("href");
  expect(decodeURIComponent(href!)).toContain(`d[part_a/KII_ID]=${kii.kii_id}`);
  // Never the participant's name or role -- only the system-generated ID.
  expect(decodeURIComponent(href!)).not.toContain("E2E Coding Link Subject");
  expect(decodeURIComponent(href!)).not.toContain("Policy Officer");
});
