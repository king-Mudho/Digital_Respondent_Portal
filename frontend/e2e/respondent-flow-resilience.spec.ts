import { expect, test } from "@playwright/test";
import {
  backendBaseURL,
  getAdminAccessToken,
  issueFreshToken,
  issueTokenOnFreshCase,
} from "./helpers";

/**
 * Respondent-flow audit pass. The happy path was already covered by
 * happy-path.spec.ts; these are the failure and branch cases that were
 * broken, and which a respondent hits alone with no support channel open.
 *
 * Every step used to wrap its submit in try/finally with no catch, so any
 * failed request left the button re-enabled and the page unchanged --
 * indistinguishable from a dead button.
 */

test("a failed step tells the respondent something went wrong instead of doing nothing", async ({
  page,
  request,
}) => {
  const token = await issueFreshToken(request, backendBaseURL());
  await page.goto(`/i/${token}`);
  await page.getByRole("button", { name: /Yes, that/ }).click();

  // Make the eligibility call fail the way a dropped connection would.
  await page.route("**/api/v1/eligibility/", (route) => route.abort("failed"));

  await page.getByLabel("Your full name").fill("Tendai Chirwa");
  await page.getByLabel("Which best describes your role?").selectOption("CEO_MD");
  await page.getByRole("button", { name: "Continue" }).click();

  await expect(page.getByText(/Something went wrong on our side/)).toBeVisible();
  // And the respondent can still retry rather than being stranded.
  await expect(page.getByRole("button", { name: "Continue" })).toBeEnabled();
});

test("a revoked invitation is explained in the respondent's own terms", async ({ page, request }) => {
  const backend = backendBaseURL();
  const access = await getAdminAccessToken(request, backend);

  // Issue it here rather than via issueFreshToken, which doesn't return the
  // token's id -- and the invitation list is paginated, so searching it for
  // "the GENERATED one" misses on a case that has accumulated many tokens.
  const invited = await request.post(`${backend}/api/v1/invitations/`, {
    headers: { Authorization: `Bearer ${access}` },
    data: { sample_id: process.env.E2E_MAIN_SAMPLE_ID, channel: "WHATSAPP", invitation_wave: 1 },
  });
  const { token_id: tokenId, raw_token: token } = await invited.json();

  const revoked = await request.post(`${backend}/api/v1/invitations/${tokenId}/revoke/`, {
    headers: { Authorization: `Bearer ${access}` },
    data: { reason: "E2E revocation" },
  });
  expect(revoked.ok()).toBeTruthy();

  await page.goto(`/i/${token}`);

  await expect(page.getByText("Invitation not valid")).toBeVisible();
  await expect(page.getByText(/revoked|no longer active/i).first()).toBeVisible();
});

test("an appointment cannot be requested in the past", async ({ page, request }) => {
  const backend = backendBaseURL();
  const token = await issueFreshToken(request, backend);

  await page.goto(`/i/${token}`);
  await page.getByRole("button", { name: /Yes, that/ }).click();
  await page.getByLabel("Your full name").fill("Tendai Chirwa");
  await page.getByLabel("Which best describes your role?").selectOption("CEO_MD");
  await page.getByRole("button", { name: "Continue" }).click();
  await page.getByRole("button", { name: "Continue to consent" }).click();
  await page.getByRole("button", { name: "I agree to take part" }).click();
  await page.getByRole("button", { name: /Have a researcher call me/ }).click();

  const picker = page.locator("input[type=datetime-local]");
  await expect(picker).toHaveAttribute("min", /\d{4}-\d{2}-\d{2}T\d{2}:\d{2}/);

  // A picker that ignores `min` (several mobile browsers) must still be caught.
  await picker.evaluate((el: HTMLInputElement) => el.removeAttribute("min"));
  await picker.fill("2020-01-01T09:00");
  await page.getByRole("button", { name: "Request this time" }).click();

  await expect(page.getByText("Please choose a time in the future.")).toBeVisible();
  await expect(page).toHaveURL(/\/appointment$/);

  // The server refuses it independently of the browser.
  const refused = await request.post(`${backend}/api/v1/appointments/`, {
    data: { token, scheduled_for: "2020-01-01T09:00:00Z", mode: "PHONE" },
  });
  expect(refused.status()).toBe(400);
  expect(JSON.stringify(await refused.json())).toMatch(/cannot be requested in the past/);
});

test("someone who booked a call is not told they have finished", async ({ page, request }) => {
  const token = await issueFreshToken(request, backendBaseURL());

  await page.goto(`/i/${token}`);
  await page.getByRole("button", { name: /Yes, that/ }).click();
  await page.getByLabel("Your full name").fill("Tendai Chirwa");
  await page.getByLabel("Which best describes your role?").selectOption("CEO_MD");
  await page.getByRole("button", { name: "Continue" }).click();
  await page.getByRole("button", { name: "Continue to consent" }).click();
  await page.getByRole("button", { name: "I agree to take part" }).click();
  await page.getByRole("button", { name: /Have a researcher call me/ }).click();

  await page.locator("input[type=datetime-local]").fill("2026-11-20T14:30");
  await page.getByRole("button", { name: "Request this time" }).click();

  // Both routes end on /done, but they do not mean the same thing: this
  // respondent still has an interview ahead of them.
  await expect(page).toHaveURL(/\/done\?requested=call$/);
  await expect(page.getByText("Your request has been sent")).toBeVisible();
  await expect(page.getByText(/A researcher will be in touch/)).toBeVisible();
  await expect(page.getByText(/thank you for your time and participation/i)).toHaveCount(0);
});

test("an appointment cannot be requested before consent is given", async ({ request }) => {
  const backend = backendBaseURL();
  // Its own case: consent attaches to the SampleCase, and the shared seed
  // case has been consented by earlier runs.
  const { token } = await issueTokenOnFreshCase(request, backend, "Appointment Consent Gate");

  // Straight to the appointment endpoint, skipping the consent screen --
  // it is AllowAny and takes only a valid token, so the frontend's routing
  // is not what keeps this closed (PI decision, Sep 2026).
  const refused = await request.post(`${backend}/api/v1/appointments/`, {
    data: { token, scheduled_for: "2026-12-05T10:00:00Z", mode: "PHONE" },
  });

  expect(refused.status()).toBe(403);
  expect((await refused.json()).error.code).toBe("consent_required");

  // And it opens up once consent is actually recorded.
  await request.post(`${backend}/api/v1/consent/`, {
    data: {
      token,
      consent_type: "PARTICIPATION",
      decision: "GIVEN",
      information_sheet_version: "v1.0",
      method: "WEB_CLICKTHROUGH",
    },
  });
  const allowed = await request.post(`${backend}/api/v1/appointments/`, {
    data: { token, scheduled_for: "2026-12-05T10:00:00Z", mode: "PHONE" },
  });
  expect(allowed.status()).toBe(201);
});

test("an ineligible respondent cannot reach the questionnaire even by bypassing the UI", async ({
  request,
}) => {
  const backend = backendBaseURL();
  // A case of its own, so a previous run's eligible respondent can't mask
  // the gate (the shared seed case accumulates them).
  const { token } = await issueTokenOnFreshCase(request, backend, "Eligibility Gate");

  // Skip the eligibility screen entirely and consent directly -- the
  // consent endpoint is AllowAny and takes only a valid token.
  const consent = await request.post(`${backend}/api/v1/consent/`, {
    data: {
      token,
      consent_type: "PARTICIPATION",
      decision: "GIVEN",
      information_sheet_version: "v1.0",
      method: "WEB_CLICKTHROUGH",
    },
  });
  expect(consent.status()).toBe(200);

  const redirect = await request.get(`${backend}/api/v1/kobo/redirect-url/?t=${encodeURIComponent(token)}`);

  expect(redirect.status()).toBe(403);
  expect((await redirect.json()).error.code).toBe("eligibility_required");
});
