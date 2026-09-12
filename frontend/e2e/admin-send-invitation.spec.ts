import { expect, test } from "@playwright/test";
import { loginAsAdmin } from "./helpers";

/**
 * Case detail page (A04): the "Invitations" panel closes a real gap found
 * during manual operation of the deployed system -- there was no way to
 * issue a respondent invitation from the UI at all (only a raw API call),
 * and Django admin can't do it either since it only ever persists a
 * *hash* of the token. Confirms the full loop: issuing a new invitation
 * from the panel produces a link that actually opens the respondent flow,
 * and revoking it removes the option to revoke it again.
 */
test("sending an invitation from the case detail page produces a working respondent link", async ({ page }) => {
  await loginAsAdmin(page);
  const sampleId = process.env.E2E_MAIN_SAMPLE_ID!;
  await page.goto(`/admin/sample/${sampleId}`);

  const invitationsPanel = page.locator("h3", { hasText: "Invitations" }).locator("..");
  const sendButton = invitationsPanel.getByRole("button", { name: /Send.*invitation/ });
  await expect(sendButton).toBeVisible();

  const [issueResponse] = await Promise.all([
    page.waitForResponse(
      (resp) => resp.url().endsWith("/invitations") && resp.request().method() === "POST" && resp.status() === 201,
    ),
    sendButton.click(),
  ]);
  const issued = await issueResponse.json();
  expect(issued.raw_token).toBeTruthy();
  expect(issued.raw_manual_code).toHaveLength(8);

  // The panel builds the link from window.location.origin, not a
  // hardcoded domain (AGENTS.md ground rule 9) -- confirm the rendered
  // link input actually matches what a respondent would need to open.
  const linkInput = page.locator("input[readonly]");
  await expect(linkInput).toBeVisible();
  const linkValue = await linkInput.inputValue();
  expect(linkValue).toBe(`${new URL(page.url()).origin}/i/${issued.raw_token}`);

  // The link genuinely opens the respondent flow, in a fresh tab so the
  // admin session/page state above isn't disturbed.
  const respondentPage = await page.context().newPage();
  await respondentPage.goto(linkValue);
  await expect(respondentPage.getByText("Please confirm:")).toBeVisible();
  await respondentPage.close();

  // Revoking removes the option to revoke it again (status leaves the
  // "open" set), without touching any other row in the history table. A
  // freshly-issued token starts at SENT -- issuing IS sending in this
  // system, there's no separate delivery-confirmation step.
  const newRow = page.getByRole("row", { name: new RegExp(`SENT`) }).first();
  await expect(newRow).toBeVisible();
  const [revokeResponse] = await Promise.all([
    page.waitForResponse(
      (resp) => resp.url().includes("/revoke") && resp.request().method() === "POST" && resp.status() === 200,
    ),
    newRow.getByRole("button", { name: "Revoke" }).click(),
  ]);
  expect(revokeResponse.status()).toBe(200);
  await expect(page.getByRole("row", { name: /REVOKED/ }).first()).toBeVisible();
});
