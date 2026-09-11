import { expect, test } from "@playwright/test";
import { backendBaseURL } from "./helpers";

/**
 * docs/22_TESTING_STRATEGY.md: "attempt to issue an invitation against a
 * locked Reserve case via the API and confirm it is rejected before any UI
 * path is even exercised." API-only by design -- no browser navigation.
 */
test("locked reserve case cannot receive an invitation via the API", async ({ request }) => {
  const backend = backendBaseURL();
  const loginResponse = await request.post(`${backend}/api/v1/auth/token/`, {
    data: { username: process.env.E2E_ADMIN_USERNAME, password: process.env.E2E_ADMIN_PASSWORD },
  });
  const { access } = await loginResponse.json();

  const response = await request.post(`${backend}/api/v1/invitations/`, {
    headers: { Authorization: `Bearer ${access}` },
    data: { sample_id: process.env.E2E_RESERVE_SAMPLE_ID, channel: "WHATSAPP", invitation_wave: 1 },
  });

  expect(response.status()).toBe(403);
  const body = await response.json();
  expect(body.error.code).toBe("not_invitable");
});
