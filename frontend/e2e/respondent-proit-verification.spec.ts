import { expect, test, type APIRequestContext, type Page } from "@playwright/test";
import { backendBaseURL, getAdminAccessToken, issueTokenOnFreshCase } from "./helpers";

/**
 * The PROIT verification screen, with real fields, on a phone.
 *
 * No test rendered this screen with fields until 2026-09-14: respondent
 * PROIT is gated by PROIT_ENABLED_FOR_RESPONDENTS, which is on in production
 * and was off everywhere tests ran, so the verify step always self-skipped.
 * The first manual pass at 375px immediately found all 24 choice buttons at
 * 30px -- under the 44px minimum every other respondent control uses -- on
 * the screen straight after consent.
 *
 * Where the flag is off (CI, a default dev checkout) this skips with that
 * reason rather than passing without having looked at anything.
 */

const PHONE = { width: 375, height: 812 };

async function seedLockedProfile(request: APIRequestContext, backend: string, sampleId: string) {
  const access = await getAdminAccessToken(request, backend);
  const auth = { Authorization: `Bearer ${access}` };

  const caseId = (await (await request.get(`${backend}/api/v1/sample-cases/${sampleId}/`, { headers: auth })).json()).id;
  const profile = await (await request.post(`${backend}/api/v1/proit/pre-profiles/`, {
    headers: auth, data: { sample_case: caseId },
  })).json();

  for (const [fieldId, value] of [["year_established", "2011"], ["hq_district", "Harare"]]) {
    const field = await (await request.post(`${backend}/api/v1/proit/pre-profiles/${profile.id}/fields/`, {
      headers: auth, data: { field_id: fieldId, preliminary_documentary_value: value },
    })).json();
    const evidence = await request.post(`${backend}/api/v1/proit/fields/${field.id}/evidence/`, {
      headers: auth,
      data: { source_title: "Companies register extract", source_confidence: "HIGH", source_authority: "TIER_1_STATUTORY" },
    });
    expect(evidence.status()).toBe(201);
  }

  const lock = await request.post(`${backend}/api/v1/proit/pre-profiles/${profile.id}/lock/`, { headers: auth });
  expect(lock.status()).toBe(200);
  return { profileId: profile.id as number, auth };
}

async function reachVerify(page: Page, token: string) {
  await page.goto(`/i/${token}`);
  await page.getByRole("button", { name: "Yes, that's correct" }).click();
  await page.getByLabel("Your full name").fill("Tendai Moyo");
  await page.getByLabel("Which best describes your role?").selectOption("CEO_MD");
  await page.getByRole("button", { name: "Continue" }).click();
  await page.getByRole("button", { name: "Continue to consent" }).click();
  await page.getByRole("button", { name: "I agree to take part" }).click();
  await page.waitForURL(/\/verify$/);
}

test("PROIT verification works and is usable on a phone", async ({ page, request }) => {
  const backend = backendBaseURL();
  const { token, sampleId } = await issueTokenOnFreshCase(request, backend, "PROIT Verify");
  const { profileId, auth } = await seedLockedProfile(request, backend, sampleId);

  const shown = await (await request.get(`${backend}/api/v1/proit/respondent-profile/?t=${encodeURIComponent(token)}`)).json();
  test.skip(shown === null, "PROIT_ENABLED_FOR_RESPONDENTS is off in this environment, so the verify screen self-skips.");

  await page.setViewportSize(PHONE);
  await reachVerify(page, token);

  const choices = page.locator("main button[aria-pressed]");
  await expect(choices).toHaveCount(12); // 2 facts x 6 answers

  // Tap targets: every choice at least 44px tall.
  const heights = await choices.evaluateAll((els) => els.map((e) => e.getBoundingClientRect().height));
  expect(Math.min(...heights)).toBeGreaterThanOrEqual(44);

  // Nothing forces the page to scroll sideways at 375px.
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1);
  expect(overflow).toBe(false);

  // Facts appear in the order the researcher added them. Locking rewrites
  // every field row, and before PreProfileField had a Meta ordering that
  // was enough for Postgres to hand them back swapped.
  const groups = page.locator("main [role=group]");
  await expect(groups).toHaveCount(2);
  expect(await groups.evaluateAll((els) => els.map((e) => e.getAttribute("aria-label")))).toEqual([
    "Is this correct: Year established?",
    "Is this correct: HQ district?",
  ]);
  await page.getByRole("group", { name: "Is this correct: Year established?" }).getByRole("button", { name: "Yes, correct" }).click();
  await page.getByRole("group", { name: "Is this correct: HQ district?" }).getByRole("button", { name: "No — correct it" }).click();

  // A correction left empty would record nothing distinguishable from "no answer".
  const cont = page.getByRole("button", { name: "Continue", exact: true });
  await expect(cont).toBeDisabled();
  await page.getByPlaceholder("What should it say instead?").fill("Mutare");
  await expect(cont).toBeEnabled();
  await cont.click();
  await page.waitForURL(/\/choice$/);

  // The three values stay separate: the correction is stored as the
  // respondent's own answer and the documentary value is untouched.
  const fields = (await (await request.get(`${backend}/api/v1/proit/pre-profiles/${profileId}/`, { headers: auth })).json()).fields;
  const district = fields.find((f: { field_id: string }) => f.field_id === "hq_district");
  expect(district.verification_status).toBe("NO_CORRECT_VALUE_PROVIDED");
  expect(district.respondent_value).toBe("Mutare");
  expect(district.preliminary_documentary_value).toBe("Harare");
});

test("the referral screen is not a dead end if the wrong role was picked", async ({ page, request }) => {
  const { token } = await issueTokenOnFreshCase(request, backendBaseURL(), "Wrong Role");
  await page.setViewportSize(PHONE);

  await page.goto(`/i/${token}`);
  await page.getByRole("button", { name: "Yes, that's correct" }).click();
  await page.getByLabel("Your full name").fill("Rudo Chikwava");
  await page.getByLabel("Which best describes your role?").selectOption("NONE_OF_THESE");
  await page.getByRole("button", { name: "Continue" }).click();
  await expect(page.getByText("Thank you for your time")).toBeVisible();

  await page.getByRole("button", { name: "I chose the wrong role — go back" }).click();
  // The earlier choice is cleared so the second one is deliberate.
  await expect(page.getByLabel("Which best describes your role?")).toHaveValue("");
  await page.getByLabel("Which best describes your role?").selectOption("OPERATIONS");
  await page.getByRole("button", { name: "Continue" }).click();
  await page.waitForURL(/\/information$/);
});
