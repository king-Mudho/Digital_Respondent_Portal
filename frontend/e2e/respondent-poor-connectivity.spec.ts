import { expect, test } from "@playwright/test";
import { backendBaseURL, issueTokenOnFreshCase } from "./helpers";

/**
 * docs/28 go-live checklist: "Mobile pages work on typical Android screens
 * and poor/variable connectivity." Nothing exercised the second half until
 * 2026-09-14. A low-end Android profile: 360x740 screen, 4x slower CPU, and a
 * slow 3G-like link (400 ms latency, ~400 kbit/s).
 *
 * Run against the dev server, whose unminified bundles are several times
 * larger than production's -- so this is a harsher test than the real site.
 */

const ANDROID = { width: 360, height: 740 };

test.describe.configure({ timeout: 240_000 });

test("the respondent journey completes on a slow 3G phone", async ({ page, request }) => {
  const { token } = await issueTokenOnFreshCase(request, backendBaseURL(), "Slow network");

  const cdp = await page.context().newCDPSession(page);
  await cdp.send("Network.enable");
  await cdp.send("Network.emulateNetworkConditions", {
    offline: false, latency: 400, downloadThroughput: 50_000, uploadThroughput: 50_000,
  });
  await cdp.send("Emulation.setCPUThrottlingRate", { rate: 4 });
  await page.setViewportSize(ANDROID);

  const step = { timeout: 60_000 };
  const started = Date.now();

  await page.goto(`/i/${token}`, step);
  await page.getByRole("button", { name: "Yes, that's correct" }).click(step);
  await page.getByLabel("Your full name").fill("Tendai Moyo", step);
  await page.getByLabel("Which best describes your role?").selectOption("CEO_MD");
  await page.getByRole("button", { name: "Continue" }).click();
  await page.getByRole("button", { name: "Continue to consent" }).click(step);
  await page.getByRole("button", { name: "I agree to take part" }).click(step);
  await page.getByText("Complete it myself now").click(step);
  await expect(page.getByRole("heading").first()).toBeVisible(step);
  // With KoboToolbox connected: the questionnaire button. Without: the
  // assisted-completion message. Either is a completed hand-off.
  await expect(
    page.getByRole("button", { name: "Start the questionnaire" }).or(page.getByText(/questionnaire isn't open yet/)),
  ).toBeVisible(step);

  // Nothing forced sideways scrolling on the narrow screen at any point we landed on.
  expect(await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1)).toBe(false);
  console.log(`slow-3G journey: ${Math.round((Date.now() - started) / 1000)} s`);
});

test("a slow tap is not submitted twice", async ({ page, request }) => {
  const { token } = await issueTokenOnFreshCase(request, backendBaseURL(), "Slow tap");
  await page.setViewportSize(ANDROID);

  await page.goto(`/i/${token}`);
  await page.getByRole("button", { name: "Yes, that's correct" }).click();
  await page.getByLabel("Your full name").fill("Tendai Moyo");
  await page.getByLabel("Which best describes your role?").selectOption("CEO_MD");

  let calls = 0;
  await page.route("**/api/v1/eligibility/", async (route) => {
    calls += 1;
    await new Promise((resolve) => setTimeout(resolve, 2500));
    await route.continue();
  });

  const cont = page.getByRole("button", { name: "Continue", exact: true });
  await cont.click();
  // While the answer is on its way the button is locked, so an impatient
  // second tap on a slow link cannot record the respondent twice.
  const pending = page.getByRole("button", { name: "Checking…" });
  await expect(pending).toBeDisabled();
  await pending.click({ force: true, timeout: 1000 }).catch(() => {});
  await page.getByRole("button", { name: "Continue to consent" }).waitFor({ timeout: 20_000 });
  expect(calls).toBe(1);
});
