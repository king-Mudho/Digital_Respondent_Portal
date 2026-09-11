export default function HomePage() {
  return (
    <main className="min-h-screen flex flex-col">
      <header className="bg-header text-white px-6 py-4">
        <p className="text-xs uppercase tracking-wide text-white/70">
          Chinhoyi University of Technology
        </p>
        <h1 className="font-semibold text-lg">ABF-FST Digital Respondent Portal</h1>
      </header>

      <section className="flex-1 flex flex-col items-center justify-center gap-6 px-6 py-16 text-center max-w-2xl mx-auto">
        <h2 className="text-2xl font-semibold text-text">
          Developing and Validating the Agribusiness Bankability Framework for
          Food Systems Transformation through Novel Financing Models in
          Zimbabwe
        </h2>
        <p className="text-text-muted">
          This portal supports data collection for a doctoral research study.
          It is accessible only to organisations invited to participate, by a
          personal invitation link. There is no public entry point.
        </p>
        <p className="text-text-muted text-sm">
          Principal Researcher: Happyson Saina, Doctor of Strategic Management
          candidate, Chinhoyi University of Technology. Supervisors: Dr L.
          Chikazhe, Dr J. Kanyepe.
        </p>
        <p className="text-sm text-text-muted border-t border-border pt-4">
          <strong>Research study</strong>: Your participation and responses
          are used for research purposes only. No score, rating, or financing
          decision is generated or shown to you as part of this process.
        </p>
      </section>

      <footer className="text-center text-xs text-text-muted py-6">
        Have an invitation code? Follow the link you were sent, or contact the
        research team using the details in your invitation.
      </footer>
    </main>
  );
}
