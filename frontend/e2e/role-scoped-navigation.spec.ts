import { expect, test, type Page } from "@playwright/test";

/**
 * Role-scoped navigation (backend/api/navigation.py, served by
 * GET /api/v1/auth/me/). Before this, every role saw all 14 nav links and
 * every role was sent to /admin/dashboard on sign-in -- which four of the
 * eight roles are refused.
 *
 * The accounts below are created by `manage.py seed_drp_dev`, one per
 * role, all sharing the E2E admin password.
 */

const PASSWORD = process.env.E2E_ADMIN_PASSWORD!;

async function signIn(page: Page, username: string) {
  await page.goto("/admin/login");
  await page.getByLabel("Username").fill(username);
  await page.getByLabel("Password").fill(PASSWORD);
  await page.getByRole("button", { name: "Sign in" }).click();
  await page.waitForURL(/\/admin\/(?!login)/);
}

/** The nav bar's own links, excluding the account/sign-out header row. */
async function navLabels(page: Page): Promise<string[]> {
  await expect(page.locator("nav a").first()).toBeVisible();
  const labels = await page.locator("nav a").allInnerTexts();
  return labels.filter((l) => l !== "Change password").map((l) => l.trim());
}

const EXPECTED: Array<{
  username: string;
  landing: string;
  nav: string[];
  refused: string;
}> = [
  {
    username: "e2e_contact_ra",
    landing: "/admin/sample",
    nav: ["Main-400 Register", "Appointments"],
    refused: "/admin/audit",
  },
  {
    username: "e2e_quan_qa_ra",
    landing: "/admin/dashboard/qa",
    nav: ["QA Dashboard", "QA Queue"],
    refused: "/admin/kii",
  },
  {
    username: "e2e_kii_ra",
    landing: "/admin/dashboard/kii-documents",
    nav: ["KII/Doc Dashboard", "KII Register"],
    // The over-grant this pass fixed: IsQAOrAdmin let a KII RA edit
    // documents and take QA decisions.
    refused: "/admin/documents",
  },
  {
    username: "e2e_documentary_ra",
    landing: "/admin/dashboard/kii-documents",
    nav: ["KII/Doc Dashboard", "Documents"],
    refused: "/admin/qa",
  },
];

for (const role of EXPECTED) {
  test(`${role.username} sees only its own modules`, async ({ page }) => {
    await signIn(page, role.username);

    // Lands on a screen it can actually open, not the shared dashboard.
    await expect(page).toHaveURL(new RegExp(`${role.landing}$`));
    expect(await navLabels(page)).toEqual(role.nav);

    // A screen outside the role renders the explicit card, not a page
    // whose every fetch 403s.
    await page.goto(role.refused);
    await expect(page.getByText("This screen isn't part of your role")).toBeVisible();
  });
}

test("the PI sees every module", async ({ page }) => {
  await signIn(page, process.env.E2E_ADMIN_USERNAME!);

  await expect(page).toHaveURL(/\/admin\/dashboard$/);
  const labels = await navLabels(page);

  expect(labels).toContain("Audit Log");
  expect(labels).toContain("Export");
  expect(labels).toContain("Reserve Activation");
  expect(labels.length).toBe(15);
});

test("a read-only role sees no write controls on a mixed screen", async ({ page }) => {
  await signIn(page, "e2e_supervisor_readonly");

  await page.goto("/admin/qa");
  await expect(page.getByRole("heading", { name: "QUAN QA Queue" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Sync now" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Accept" })).toHaveCount(0);

  await page.goto("/admin/cost");
  await expect(page.getByRole("heading", { name: "Cost Dashboard" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Log cost" })).toHaveCount(0);

  // Audit Log and Export are PI/Analyst territory, not the Supervisor's.
  expect(await navLabels(page)).not.toContain("Audit Log");
});
