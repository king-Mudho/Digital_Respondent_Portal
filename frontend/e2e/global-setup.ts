import { execSync } from "child_process";
import path from "path";

/**
 * Seeds deterministic synthetic fixtures via the backend's seed_drp_dev
 * management command (never real Main-400 data -- docs/23_DEPLOYMENT_
 * ARCHITECTURE.md "test/synthetic cases only" rule) before the E2E suite
 * runs. Captures the printed sample_id/token pair for the specs to use.
 */
export default async function globalSetup() {
  const backendDir = path.resolve(__dirname, "../../backend");
  const pythonBin = process.platform === "win32" ? ".venv/Scripts/python.exe" : ".venv/bin/python";

  const output = execSync(`"${pythonBin}" manage.py seed_drp_dev`, {
    cwd: backendDir,
    encoding: "utf-8",
  });

  const mainSampleId = /main sample_id: (\S+)/.exec(output)?.[1];
  const reserveSampleId = /reserve sample_id \(LOCKED\): (\S+)/.exec(output)?.[1];
  const activationReserveSampleId = /activation reserve sample_id \(LOCKED\): (\S+)/.exec(output)?.[1];
  const workflowTransitionSampleId = /workflow transition test sample_id: (\S+)/.exec(output)?.[1];
  const rawToken = /raw invitation token: (\S+)/.exec(output)?.[1];

  if (!mainSampleId || !reserveSampleId || !activationReserveSampleId || !workflowTransitionSampleId || !rawToken) {
    throw new Error(`seed_drp_dev output did not match expected format:\n${output}`);
  }

  process.env.E2E_MAIN_SAMPLE_ID = mainSampleId;
  process.env.E2E_RESERVE_SAMPLE_ID = reserveSampleId;
  // A LOCKED reserve case dedicated to admin-reserve-activation.spec.ts --
  // kept separate from E2E_RESERVE_SAMPLE_ID above, which reserve-lock.spec.ts
  // asserts stays LOCKED for the whole suite run.
  process.env.E2E_ACTIVATION_RESERVE_SAMPLE_ID = activationReserveSampleId;
  // A main case reset to S03 on every seed run, dedicated to
  // admin-workflow-and-contact-log.spec.ts -- E2E_MAIN_SAMPLE_ID gets
  // auto-advanced by every issue_invitation() call from other specs and
  // would eventually run out of forward transitions.
  process.env.E2E_WORKFLOW_TRANSITION_SAMPLE_ID = workflowTransitionSampleId;
  process.env.E2E_RAW_TOKEN = rawToken;
  process.env.E2E_ADMIN_USERNAME = "e2e_admin";
  process.env.E2E_ADMIN_PASSWORD = "E2eDevPassword123!";

  await warmRoutes();
}

/**
 * Against `next dev`, each route compiles on its first request, which can
 * take longer than a test's 30s timeout. The first spec then fails waiting
 * for a redirect that is simply still compiling -- seen 2026-09-14 on
 * admin-appointments, which passed in 5.7s on a rerun. Requesting every page
 * once here moves that cost out of the tests. Against a production build
 * this is a few fast no-ops.
 */
async function warmRoutes() {
  const base = process.env.E2E_BASE_URL ?? "http://localhost:3000";
  const routes = [
    "/admin/login", "/admin", "/admin/account",
    "/admin/dashboard", "/admin/dashboard/sampling", "/admin/dashboard/contact",
    "/admin/dashboard/qa", "/admin/dashboard/kii-documents",
    "/admin/sample", "/admin/sample/warm", "/admin/organisations", "/admin/appointments", "/admin/follow-ups",
    "/admin/qa", "/admin/qa/exceptions", "/admin/kii", "/admin/kii/new", "/admin/kii/1",
    "/admin/documents", "/admin/documents/new", "/admin/documents/1",
    "/admin/reserve", "/admin/cost", "/admin/audit", "/admin/export", "/admin/proit/1",
    "/i/warm", "/i/warm/confirm", "/i/warm/eligibility", "/i/warm/information",
    "/i/warm/consent", "/i/warm/verify", "/i/warm/choice", "/i/warm/appointment",
    "/i/warm/kobo-redirect", "/i/warm/done",
  ];
  for (const route of routes) {
    try {
      await fetch(base + route, { signal: AbortSignal.timeout(120_000) });
    } catch {
      // A slow or failing warm-up is not a test failure; the specs will
      // report anything genuinely broken.
    }
  }
}
