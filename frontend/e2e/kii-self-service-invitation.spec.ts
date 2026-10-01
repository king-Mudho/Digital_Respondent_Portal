import { expect, test } from "@playwright/test";
import { backendBaseURL, getAdminAccessToken, loginAsAdmin } from "./helpers";

/**
 * apps/kii self-service invitation (2026-10-01): a KII informant can now open a
 * personal link themselves -- WhatsApp/email, filled in alone, no interviewer present --
 * the same way a Main-400 respondent already can. This drives the whole path: an RA
 * issuing the link from the KII record page, through to the informant reaching the
 * KoboToolbox KII Guide with no participant-identifying data in the URL.
 */

test("a KII informant can open their own link, consent, and reach the KII Guide unsupervised", async ({
  page,
  request,
}) => {
  // Two full browser contexts and several admin round trips in one test --
  // the default 30s budget is tight for this path, especially on a dev
  // server compiling the /ki/[token]/* routes on first hit.
  test.setTimeout(60_000);

  const backend = backendBaseURL();
  const access = await getAdminAccessToken(request, backend);
  const auth = { Authorization: `Bearer ${access}` };

  // A fresh record of its own, not a shared fixture -- same reasoning as
  // issueTokenOnFreshCase: a gate test proves nothing against a record that
  // already carries consent or an open token from a previous run.
  const created = await request.post(`${backend}/api/v1/kii/`, {
    headers: auth,
    data: {
      stakeholder_category: "Financial institution representative",
      participant_name: `E2E Informant ${Date.now()}`,
      participant_role: "Head of SME Lending",
    },
  });
  const record = await created.json();

  await loginAsAdmin(page);
  await page.goto(`/admin/kii/${record.id}`);

  // No phone/WhatsApp/email yet -- the Invite panel can't send anywhere.
  await expect(page.getByText(/Needs a phone, WhatsApp number or email on file/)).toBeVisible();

  await page.getByLabel("WhatsApp number").fill("0771234567");
  await page.getByRole("button", { name: "Save details" }).click();
  await expect(page.getByText("Details saved.")).toBeVisible();

  await page.getByRole("button", { name: "Send link" }).click();
  const linkInput = page.getByLabel("Invitation link");
  await expect(linkInput).toBeVisible();
  const link = await linkInput.inputValue();
  expect(link).toContain("/ki/");

  // The informant opens the link on their own, in a separate context (no admin
  // session, no cookies) -- exactly how it arrives on their phone.
  const informantContext = await page.context().browser()!.newContext();
  const informantPage = await informantContext.newPage();
  await informantPage.goto(link);

  await informantPage.waitForURL(/\/ki\/.+\/information/);
  await expect(informantPage.getByRole("heading", { name: "Participant Information" })).toBeVisible();

  await informantPage.getByRole("button", { name: "Continue to consent" }).click();
  await informantPage.waitForURL(/\/ki\/.+\/consent/);
  await informantPage.getByRole("button", { name: "I agree to take part" }).click();

  await informantPage.waitForURL(/\/ki\/.+\/kobo-redirect/);
  const startButton = informantPage.getByRole("button", { name: "Start the interview" });
  await expect(startButton).toBeVisible();

  // Confirm the resolved link directly rather than following window.open(url, "_self")
  // off the portal onto KoboToolbox's own site -- same approach as the Main-400 kobo-
  // redirect checks elsewhere in this suite.
  const tokenFromUrl = new URL(informantPage.url()).pathname.split("/")[2];
  const redirectResp = await request.get(`${backend}/api/v1/kii-invitations/kobo-redirect-url/?t=${tokenFromUrl}`);
  const { kobo_form_url: koboFormUrl } = await redirectResp.json();
  expect(koboFormUrl).toContain(record.kii_id);
  expect(koboFormUrl).not.toContain(record.participant_name);

  await informantContext.close();

  // The admin page reflects what just happened: consent given, the token's
  // lifecycle advanced past CONSENTED, and the staff "Continue this interview"
  // link now available too.
  await page.reload();
  await expect(page.getByText("Participation: GIVEN")).toBeVisible();
  // exact: true -- a bare substring match also hits "NOT_STARTED" on the
  // Transcript/Coding cards elsewhere on this same page.
  await expect(page.getByText("STARTED", { exact: true })).toBeVisible();
});

test("a KII invitation link cannot reach the interview form before consent is given", async ({ page, request }) => {
  const backend = backendBaseURL();
  const access = await getAdminAccessToken(request, backend);
  const auth = { Authorization: `Bearer ${access}` };

  const created = await request.post(`${backend}/api/v1/kii/`, {
    headers: auth,
    data: {
      stakeholder_category: "Donor agency representative",
      participant_name: `E2E Informant No-Consent ${Date.now()}`,
      participant_role: "Programme Officer",
      whatsapp_number: "0779876543",
    },
  });
  const record = await created.json();

  const issued = await request.post(`${backend}/api/v1/kii-invitations/`, {
    headers: auth,
    data: { kii_id: record.kii_id, channel: "WHATSAPP" },
  });
  const { raw_token: rawToken } = await issued.json();

  const redirectResp = await request.get(`${backend}/api/v1/kii-invitations/kobo-redirect-url/?t=${rawToken}`);
  expect(redirectResp.status()).toBe(403);
  const body = await redirectResp.json();
  expect(body.error.code).toBe("consent_required");
});
