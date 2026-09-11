/**
 * Legitimacy-first header shown on every respondent-facing screen
 * (docs/21_UI_UX_GUIDELINES.md): study title, CUT affiliation, no hint of a
 * provisional score, no commercial/fintech branding pattern.
 */
export function StudyHeader() {
  return (
    <header className="bg-header text-white px-6 py-4">
      <p className="text-xs uppercase tracking-wide text-white/70">
        Chinhoyi University of Technology — Research Study
      </p>
      <h1 className="font-semibold">ABF-FST Digital Respondent Portal</h1>
    </header>
  );
}
