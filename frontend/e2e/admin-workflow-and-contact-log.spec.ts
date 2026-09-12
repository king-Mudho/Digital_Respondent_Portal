import { expect, test } from "@playwright/test";
import { loginAsAdmin } from "./helpers";

/**
 * Case detail page (A04) hardening-pass coverage: the workflow-transition
 * buttons and the "log a contact attempt" form added when
 * SampleCaseSerializer's read-only-field gap and ContactEventSerializer's
 * sample_case-required gap were fixed (backend/tests/
 * test_sample_case_api_integrity.py, test_contact_event_api.py).
 *
 * Waits on the actual network responses (page.waitForResponse) rather than
 * on text appearing in the DOM -- both mutation buttons' own labels/options
 * already contain the target text before the click (e.g. the "→ S07"
 * button's own label contains "S07", and the channel <select> already has
 * a WHATSAPP <option>), so a naive "wait for this text to appear" assertion
 * would pass immediately regardless of whether the request even completed.
 * An earlier version of this spec had exactly that bug and could report
 * success while the transition had actually failed server-side.
 */
test("advancing workflow status and logging a contact attempt both work from the case detail page", async ({
  page,
}) => {
  await loginAsAdmin(page);
  const sampleId = process.env.E2E_WORKFLOW_TRANSITION_SAMPLE_ID!;

  await page.goto(`/admin/sample/${sampleId}`);

  // Click whichever next-transition button the state machine currently
  // offers -- the frontend mirrors sampling.services.WORKFLOW_TRANSITIONS
  // but never invents its own options, so there is always at least one
  // unless the case is already in a terminal state from a prior run.
  const transitionButton = page.getByRole("button", { name: /^→ S\d{2}$/ }).first();
  await expect(transitionButton).toBeVisible();
  const nextStatus = (await transitionButton.textContent())!.replace("→ ", "").trim();

  // Skips any intermediate redirect hop (e.g. a trailing-slash redirect)
  // that also matches the URL substring -- otherwise waitForResponse can
  // resolve on that 3xx hop instead of the actual final response.
  const isFinalResponse = (resp: import("@playwright/test").Response) => resp.status() < 300 || resp.status() >= 400;
  const [transitionResponse] = await Promise.all([
    page.waitForResponse(
      (resp) => resp.url().includes("/transition") && resp.request().method() === "POST" && isFinalResponse(resp),
    ),
    transitionButton.click(),
  ]);
  expect(transitionResponse.status(), "workflow transition should be accepted, not rejected").toBe(200);
  const updatedCase = await transitionResponse.json();
  expect(updatedCase.workflow_status).toBe(nextStatus);

  // The status shown in the case header (a dedicated <dd>, not the
  // transition buttons themselves) reflects the new value.
  const statusValue = page.locator("dt", { hasText: "Status" }).locator("xpath=following-sibling::dd[1]");
  await expect(statusValue).toHaveText(nextStatus);

  // Log a contact attempt over WhatsApp -- the one channel this suite
  // otherwise never exercises through the UI, since the WhatsApp Business
  // Platform integration itself is blocked on Meta template approval (see
  // pi-blocked-items.spec.ts) and has no messaging UI yet. This at least
  // confirms the channel option exists and round-trips correctly end to end.
  //
  // Scoped via :has(option[value='FACE_TO_FACE']) rather than the first
  // <select> on the page -- the "Invitations" panel (added when the
  // send-invitation gap was closed) has its own channel <select> earlier
  // in the DOM with a different option set (no FACE_TO_FACE/PHONE), so a
  // positional ".first()" here would silently select the wrong dropdown.
  const contactChannelSelect = page.locator("select:has(option[value='FACE_TO_FACE'])");
  await contactChannelSelect.selectOption("WHATSAPP");
  const noteText = `E2E: WhatsApp contact attempt logged via admin UI (${Date.now()}).`;
  await page.getByPlaceholder("Notes (optional)").fill(noteText);

  const [contactEventResponse] = await Promise.all([
    page.waitForResponse(
      (resp) => resp.url().includes("/events") && resp.request().method() === "POST" && isFinalResponse(resp),
    ),
    page.getByRole("button", { name: "Log contact attempt" }).click(),
  ]);
  expect(contactEventResponse.status(), "logging a contact attempt should succeed, not 400").toBe(201);
  const contactEvent = await contactEventResponse.json();
  expect(contactEvent.channel).toBe("WHATSAPP");

  // Scoped to this specific timeline <li> (filtering the *listitem*, not
  // the whole <ul> -- filtering the list only tests whether the list
  // contains matching text anywhere, which is trivially true once any
  // entry matches, so a naive list-level filter here would still search
  // every entry's WHATSAPP span, not just this one).
  const timelineEntry = page.getByRole("listitem").filter({ hasText: noteText });
  await expect(timelineEntry.getByText("WHATSAPP", { exact: true })).toBeVisible();
  await expect(timelineEntry.getByText(noteText)).toBeVisible();
});
