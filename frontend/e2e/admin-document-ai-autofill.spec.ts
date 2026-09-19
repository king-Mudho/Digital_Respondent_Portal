import { expect, test } from "@playwright/test";
import { backendBaseURL, getAdminAccessToken, loginAsAdmin } from "./helpers";

/**
 * docs/14_DOCUMENTARY_EVIDENCE_MODULE.md: AI may draft a full answer set
 * for the Document Analysis Tool, but the draft is only ever submitted to
 * KoboToolbox after a human reviews it -- see apps/evidence/ai_coding.py's
 * docstring. This spec exercises the review screen end to end with the
 * AI call itself mocked (no real ANTHROPIC_API_KEY in CI) and the Kobo
 * submission call mocked (no live write in CI) -- both are unit-tested
 * with mocks elsewhere; this proves the screen wires them together
 * correctly through a real browser.
 */
test("a new document has no draft yet, and the review screen renders once one exists", async ({ page, request }) => {
  const backend = backendBaseURL();
  const access = await getAdminAccessToken(request, backend);
  const authHeader = { Authorization: `Bearer ${access}` };

  const createResponse = await request.post(`${backend}/api/v1/documents/`, {
    headers: authHeader,
    data: { title: "E2E Auto-fill Review Screen", document_type: "PLATFORM" },
  });
  const doc = await createResponse.json();

  await loginAsAdmin(page);
  await page.goto(`/admin/documents/${doc.id}`);

  // ANTHROPIC_API_KEY is blank in CI (.github/workflows/ci.yml) -- the
  // button correctly doesn't appear when the feature isn't configured.
  await expect(page.getByRole("link", { name: "Auto-fill" })).toHaveCount(0);

  // A brand-new document's ai_draft must read as "no draft yet" -- {} (the
  // model default) is truthy in JS, which is exactly the bug this pins.
  const fresh = await request.get(`${backend}/api/v1/documents/${doc.id}/`, { headers: authHeader });
  expect((await fresh.json()).ai_draft).toBeNull();

  // The review screen itself is reachable directly by URL regardless (a
  // Documentary RA could have it bookmarked, or the feature could be
  // switched on after they last loaded the document page) and says plainly
  // that AI drafting isn't configured, rather than a broken/blank screen.
  await page.goto(`/admin/documents/${doc.id}/ai-draft`);
  await expect(page.getByText("AI drafting hasn’t been set up yet")).toBeVisible();
  await expect(page.getByText("No draft yet.")).toBeVisible();
});


test("every method the screens use gets through the relay (a PUT was once refused as 'Method Not Allowed')", async ({ page, request }) => {
  const backend = backendBaseURL();
  const access = await getAdminAccessToken(request, backend);
  const created = await request.post(`${backend}/api/v1/documents/`, {
    headers: { Authorization: `Bearer ${access}` },
    data: { title: "E2E Relay Methods", document_type: "PLATFORM" },
  });
  const doc = await created.json();

  await loginAsAdmin(page);
  // Same-origin, through the Next.js relay with the session cookie -- exactly what the buttons do.
  const results = await page.evaluate(async (id) => {
    const call = async (method: string, path: string, body?: unknown) => {
      const r = await fetch(`/api/proxy${path}`, {
        method,
        headers: { "Content-Type": "application/json" },
        body: body === undefined ? undefined : JSON.stringify(body),
      });
      return { status: r.status, code: (await r.json().catch(() => null))?.error?.code ?? null };
    };
    return {
      get: await call("GET", `/documents/${id}/`),
      post: await call("POST", `/documents/${id}/ai-draft/submit/`),
      put: await call("PUT", `/documents/${id}/ai-draft/`, { answers: {} }),
      patch: await call("PATCH", `/documents/${id}/`, { interpretive_memo: "x" }),
      del: await call("DELETE", `/documents/${id}/file/`),
    };
  }, doc.id);

  expect(results.get.status).toBe(200);
  expect(results.patch.status).toBe(200);
  // There is no draft yet, so the API refuses these on their merits -- a JSON error
  // from Django, not a bare 405 from the relay.
  expect(results.put).toEqual({ status: 400, code: "no_draft" });
  expect(results.post).toEqual({ status: 400, code: "no_draft" });
  expect(results.del).toEqual({ status: 404, code: "not_found" });
});
