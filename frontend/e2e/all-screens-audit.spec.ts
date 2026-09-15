import { expect, test, type Page } from "@playwright/test";
import { backendBaseURL, getAdminAccessToken, issueTokenOnFreshCase } from "./helpers";

/**
 * Every screen, as every role, on desktop and on a phone (added 2026-09-15).
 *
 * For each role the nav is taken from the server (GET /auth/me/), so a new
 * screen is audited automatically. A screen fails if it:
 *   - gets a 5xx from the API (except the deliberate 503 "not connected" states),
 *   - gets a 403 from its own data (the nav offered something the API refuses),
 *   - throws in the browser, or shows a generic failure message,
 *   - never finishes loading, or scrolls sideways at 375px.
 */

const PASSWORD = process.env.E2E_ADMIN_PASSWORD!;
const ROLES = [
  "e2e_admin", "e2e_field_coordinator", "e2e_contact_ra", "e2e_quan_qa_ra", "e2e_kii_ra",
  "e2e_documentary_ra", "e2e_analyst", "e2e_supervisor_readonly",
];
// Handled "not set up here" states, which the screens explain rather than fail on.
// CI points at a placeholder KoboToolbox form and token, so the form-not-found
// and token-refused answers are expected there too.
const EXPECTED_ERROR_CODES = new Set([
  "kobo_not_configured", "kobo_form_not_found", "kobo_auth_failed", "email_not_configured", "questionnaire_unavailable",
]);

async function signIn(page: Page, username: string) {
  await page.goto("/admin/login");
  await page.getByLabel("Username").fill(username);
  await page.getByLabel("Password").fill(PASSWORD);
  await page.getByRole("button", { name: "Sign in" }).click();
  await page.waitForURL(/\/admin\/(?!login)/);
}

for (const username of ROLES) {
  test(`every screen works for ${username}`, async ({ page, request }) => {
    test.setTimeout(240_000);
    if (username === "e2e_contact_ra") {
      // A Contact RA only opens cases assigned to it; give it one so its case page is audited too.
      const backend = backendBaseURL();
      const auth = { Authorization: `Bearer ${await getAdminAccessToken(request, backend)}` };
      const { sampleId } = await issueTokenOnFreshCase(request, backend, "Audit contact RA");
      const ras = await (await request.get(`${backend}/api/v1/auth/contact-ras/`, { headers: auth })).json();
      const ra = (Array.isArray(ras) ? ras : ras.results).find((u: { username: string }) => u.username === username);
      await request.patch(`${backend}/api/v1/sample-cases/${sampleId}/`, { headers: auth, data: { assigned_ra: ra.id } });
    }
    const problems: string[] = [];
    let current = "";

    page.on("pageerror", (err) => problems.push(`${current}: uncaught ${err.message}`));
    page.on("response", async (response) => {
      const screen = current; // before any await: the page may move on meanwhile
      const url = response.url();
      if (!url.includes("/api/proxy/")) return;
      const status = response.status();
      if (status < 400 || status === 401) return;
      let code = "";
      try {
        code = (await response.json())?.error?.code ?? "";
      } catch {
        // The body is discarded once the page navigates away. A GET can be
        // asked again to learn which error it was.
        if (response.request().method() === "GET") {
          code = await page.request.get(url).then((r) => r.json()).then((b) => b?.error?.code ?? "", () => "");
        }
      }
      if (EXPECTED_ERROR_CODES.has(code)) return;
      if (status >= 500 || status === 403) problems.push(`${screen}: HTTP ${status} ${code} ${url.split("/api/proxy")[1]}`);
    });

    await signIn(page, username);
    const me = await (await page.request.get("/api/proxy/auth/me/")).json();
    const paths: string[] = me.screens.map((s: { path: string }) => s.path);
    expect(paths.length).toBeGreaterThan(0);

    // Detail screens reached from the registers, for roles that hold them.
    const detail = async (listPath: string, toPath: (row: Record<string, unknown>) => string) => {
      const response = await page.request.get(`/api/proxy${listPath}`);
      if (!response.ok()) return;
      const body = await response.json();
      const row = (Array.isArray(body) ? body : body.results ?? [])[0];
      if (row) paths.push(toPath(row));
    };
    if (paths.includes("/admin/sample")) await detail("/sample-cases/?sample_type=MAIN", (r) => `/admin/sample/${r.sample_id}`);
    if (paths.includes("/admin/kii")) await detail("/kii/", (r) => `/admin/kii/${r.id}`);
    if (paths.includes("/admin/documents")) await detail("/documents/", (r) => `/admin/documents/${r.id}`);

    for (const viewport of [{ width: 1366, height: 900 }, { width: 375, height: 812 }]) {
      await page.setViewportSize(viewport);
      for (const path of [...paths, "/admin/account"]) {
        current = `${path} @${viewport.width}`;
        await page.goto(path);
        await expect(page.locator("main")).toBeVisible();
        // Settled: no "Loading…" left after the data calls finish.
        await page.waitForLoadState("networkidle");
        await expect(page.getByText(/^Loading…$/)).toHaveCount(0, { timeout: 15_000 }).catch(() =>
          problems.push(`${current}: still loading after 15s`),
        );
        if (await page.getByText(/Something went wrong|isn't part of your role/).count()) {
          problems.push(`${current}: shows an error state`);
        }
        if (viewport.width === 375) {
          const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
          if (overflow > 1) problems.push(`${current}: page scrolls sideways by ${overflow}px`);
        }
      }
    }

    expect(problems, problems.join("\n")).toEqual([]);
  });
}
