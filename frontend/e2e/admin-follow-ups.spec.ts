import { execFileSync } from "node:child_process";
import { existsSync } from "node:fs";
import path from "node:path";
import { expect, test } from "@playwright/test";
import { backendBaseURL, getAdminAccessToken, issueTokenOnFreshCase, loginAsAdmin } from "./helpers";

/**
 * Sending invitations and reminders by hand until the WhatsApp Business
 * Platform is connected (added 2026-09-14). Before this, a due reminder was
 * written as a FAILED row no screen showed, so no reminder could ever reach a
 * respondent, and cases were marked Nonresponse on the calendar alone.
 */

const PHONE = { width: 375, height: 812 };
const BACKEND_DIR = path.resolve(__dirname, "../../backend");
// CI has no virtualenv and names its interpreter in E2E_PYTHON, as global-setup uses.
const PYTHON =
  process.env.E2E_PYTHON ?? [".venv/Scripts/python.exe", ".venv/bin/python"].map((p) => path.join(BACKEND_DIR, p)).find(existsSync);

/** Backdates a case's invitation and gives it a respondent with a number --
 * there is no API for moving time, and none should exist. */
function makeReminderDue(sampleId: string, days: number) {
  execFileSync(PYTHON!, ["manage.py", "shell", "-c", `
from datetime import timedelta
from django.utils import timezone
from apps.contacts.models import Respondent
from apps.sampling.models import SampleCase
case = SampleCase.objects.get(sample_id="${sampleId}")
Respondent.objects.create(sample_case=case, full_name="Follow-up Tester", is_eligible=True, whatsapp_number="0771234567")
token = case.invitation_tokens.order_by("-issued_at").first()
token.issued_at = timezone.now() - timedelta(days=${days})
token.save(update_fields=["issued_at"])
`], { cwd: BACKEND_DIR, env: { ...process.env, DJANGO_SETTINGS_MODULE: "config.settings.dev" }, stdio: "pipe" });
}

async function verifiedCaseWithInvitation(request: Parameters<typeof issueTokenOnFreshCase>[0], label: string) {
  const backend = backendBaseURL();
  const auth = { Authorization: `Bearer ${await getAdminAccessToken(request, backend)}` };
  const { sampleId } = await issueTokenOnFreshCase(request, backend, label);
  for (const status of ["S01", "S02", "S03"]) {
    const r = await request.post(`${backend}/api/v1/sample-cases/${sampleId}/transition/`, {
      headers: auth, data: { workflow_status: status },
    });
    expect(r.status()).toBe(200);
  }
  // Re-issue now that the case is verified, so it moves to S05 and enters the sequence.
  await request.post(`${backend}/api/v1/invitations/`, {
    headers: auth, data: { sample_id: sampleId, channel: "WHATSAPP", invitation_wave: 1 },
  });
  return sampleId;
}

test("a due reminder is sent from Follow-ups and leaves the queue", async ({ page, request }) => {
  test.skip(!PYTHON, "Needs the local backend virtualenv to backdate an invitation.");
  const sampleId = await verifiedCaseWithInvitation(request, "Follow-up");
  makeReminderDue(sampleId, 2);

  await loginAsAdmin(page);
  await page.setViewportSize(PHONE);
  await page.goto("/admin/follow-ups");

  const card = page.getByRole("article", { name: `Follow-up for ${sampleId}` });
  await expect(card.getByText("Day 2 reminder")).toBeVisible();
  const wa = card.getByRole("link", { name: "Open in WhatsApp" });
  await expect(wa).toHaveAttribute("href", /^https:\/\/wa\.me\/263771234567\?text=Hello/);
  expect(await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1)).toBe(false);
  await page.screenshot({ path: "test-results/follow-ups-phone.png", fullPage: true });

  await card.getByRole("button", { name: "Mark as sent" }).click();
  await expect(page.getByRole("link", { name: sampleId, exact: true })).toHaveCount(0);
});

test("a new invitation can be sent through WhatsApp with the link and code", async ({ page, request }) => {
  const backend = backendBaseURL();
  const auth = { Authorization: `Bearer ${await getAdminAccessToken(request, backend)}` };
  const org = await (await request.post(`${backend}/api/v1/organisations/`, {
    headers: auth,
    data: { name: `E2E WhatsApp invite ${Date.now()}`, entity_type: "Cooperative", province: "HARARE",
      district: "Harare", actor_family: "PRODUCER_PRIMARY", value_chain: "Horticulture", size_class: "SME" },
  })).json();
  const { sample_id: sampleId } = await (await request.post(`${backend}/api/v1/sample-cases/`, {
    headers: auth, data: { organisation: org.id, sample_type: "MAIN" },
  })).json();

  await loginAsAdmin(page);
  await page.goto(`/admin/sample/${sampleId}`);
  // Not yet verified: the RA is told what inviting now does and doesn't do.
  await expect(page.getByText("This case hasn't reached S03")).toBeVisible();

  await page.getByRole("button", { name: "Send invitation" }).click();
  const wa = page.getByRole("link", { name: "Send via WhatsApp" });
  await expect(wa).toBeVisible();
  const href = decodeURIComponent((await wa.getAttribute("href")) ?? "");
  expect(href).toMatch(/^https:\/\/wa\.me\/\?text=Hello\. You are invited/);
  expect(href).toMatch(/\/i\/[A-Za-z0-9_-]{20,}/);
  expect(href).toMatch(/quote code \S+\.$/);
});

test("the coordinator's bulk verification control asks before moving anything", async ({ page, request }) => {
  const backend = backendBaseURL();
  const auth = { Authorization: `Bearer ${await getAdminAccessToken(request, backend)}` };
  const before = (await (await request.get(`${backend}/api/v1/sample-cases/?sample_type=MAIN&workflow_status=S00`, { headers: auth })).json()).count;

  await loginAsAdmin(page);
  await page.goto("/admin/sample");
  await expect(page.getByText("Move cases through verification")).toBeVisible();
  const button = page.getByRole("button", { name: new RegExp(`^Move all ${before}$`) });
  await expect(button).toBeVisible();

  page.once("dialog", (dialog) => dialog.dismiss());
  await button.click();

  const after = (await (await request.get(`${backend}/api/v1/sample-cases/?sample_type=MAIN&workflow_status=S00`, { headers: auth })).json()).count;
  expect(after).toBe(before);
});
