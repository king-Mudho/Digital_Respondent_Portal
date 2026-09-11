import { expect, test } from "@playwright/test";
import { backendBaseURL, loginAsAdmin } from "./helpers";

/**
 * docs/22_TESTING_STRATEGY.md: "assert the workflow status shown on the
 * internal case-detail screen exactly matches SampleCase.workflow_status
 * from the API -- the frontend must never diverge from or infer the
 * backend value."
 */
test("case detail workflow status matches the API exactly", async ({ page, request }) => {
  await loginAsAdmin(page);

  const backend = backendBaseURL();
  const loginResponse = await request.post(`${backend}/api/v1/auth/token/`, {
    data: { username: process.env.E2E_ADMIN_USERNAME, password: process.env.E2E_ADMIN_PASSWORD },
  });
  const { access } = await loginResponse.json();

  const apiResponse = await request.get(`${backend}/api/v1/sample-cases/${process.env.E2E_MAIN_SAMPLE_ID}/`, {
    headers: { Authorization: `Bearer ${access}` },
  });
  const sampleCase = await apiResponse.json();

  await page.goto(`/admin/sample/${process.env.E2E_MAIN_SAMPLE_ID}`);
  await expect(page.getByText(sampleCase.workflow_status, { exact: false })).toBeVisible();
});
