import { Page, APIRequestContext } from "@playwright/test";

export async function loginAsAdmin(page: Page) {
  await page.goto("/admin/login");
  await page.getByLabel("Username").fill(process.env.E2E_ADMIN_USERNAME!);
  await page.getByLabel("Password").fill(process.env.E2E_ADMIN_PASSWORD!);
  await page.getByRole("button", { name: "Sign in" }).click();
  await page.waitForURL("**/admin/dashboard");
}

/** Issues a fresh invitation token for the seeded MAIN sample case via the
 * internal API, so each spec gets a clean, un-consumed token rather than
 * racing other specs over the single global-setup token. */
export async function issueFreshToken(request: APIRequestContext, baseURL: string): Promise<string> {
  const loginResponse = await request.post(`${baseURL}/api/v1/auth/token/`, {
    data: { username: process.env.E2E_ADMIN_USERNAME, password: process.env.E2E_ADMIN_PASSWORD },
  });
  const { access } = await loginResponse.json();

  const response = await request.post(`${baseURL}/api/v1/invitations/`, {
    headers: { Authorization: `Bearer ${access}` },
    data: { sample_id: process.env.E2E_MAIN_SAMPLE_ID, channel: "WHATSAPP", invitation_wave: 1 },
  });
  const body = await response.json();
  return body.raw_token;
}

export function backendBaseURL(): string {
  return process.env.E2E_BACKEND_URL ?? "http://localhost:8000";
}
