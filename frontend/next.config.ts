import type { NextConfig } from "next";

// No PWA / service worker here -- unlike ABI's 10-12 minute in-app assessment,
// this portal's respondent surface is a short consent/eligibility/routing
// flow, and the actual questionnaire capture happens inside Kobo's own
// client. See docs/04_TECH_STACK.md "What NOT to add".
const nextConfig: NextConfig = {
  reactStrictMode: true,
  // Standalone output bundles only the production-necessary files/deps into
  // .next/standalone -- meaningfully smaller footprint on the shared VPS
  // (see the sibling ABI project's docs/PRODUCTION_ARCHITECTURE.md).
  output: "standalone",
};

export default nextConfig;
