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

/**
 * A token on a brand-new organisation and sample case of its own.
 *
 * The shared seed case (E2E_MAIN_SAMPLE_ID) accumulates state across runs:
 * consent and eligibility both attach to the SampleCase, so by the second
 * run it already has GIVEN consent and eligible respondents on it. Any
 * spec asserting that a gate *refuses* something must start from a case
 * with no such history, or it silently tests nothing.
 */
export async function issueTokenOnFreshCase(
  request: APIRequestContext,
  baseURL: string,
  label: string,
): Promise<{ token: string; sampleId: string }> {
  const access = await getAdminAccessToken(request, baseURL);
  const auth = { Authorization: `Bearer ${access}` };

  const org = await request.post(`${baseURL}/api/v1/organisations/`, {
    headers: auth,
    data: {
      name: `E2E ${label} ${Date.now()}`,
      entity_type: "Cooperative",
      province: "HARARE",
      district: "Harare",
      actor_family: "PRODUCER_PRIMARY",
      value_chain: "Horticulture",
      size_class: "SME",
    },
  });
  const created = await request.post(`${baseURL}/api/v1/sample-cases/`, {
    headers: auth,
    data: { organisation: (await org.json()).id, sample_type: "MAIN" },
  });
  const { sample_id: sampleId } = await created.json();

  const invited = await request.post(`${baseURL}/api/v1/invitations/`, {
    headers: auth,
    data: { sample_id: sampleId, channel: "WHATSAPP", invitation_wave: 1 },
  });
  return { token: (await invited.json()).raw_token, sampleId };
}

/** A raw JWT access token for the seeded e2e_admin, for specs that need to
 * create fixture data directly against the Django API (KII records,
 * documents, appointments, ...) before driving the admin UI against them. */
export async function getAdminAccessToken(request: APIRequestContext, baseURL: string): Promise<string> {
  const response = await request.post(`${baseURL}/api/v1/auth/token/`, {
    data: { username: process.env.E2E_ADMIN_USERNAME, password: process.env.E2E_ADMIN_PASSWORD },
  });
  const { access } = await response.json();
  return access;
}
