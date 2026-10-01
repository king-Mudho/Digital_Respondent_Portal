"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { StudyHeader } from "@/components/respondent/StudyHeader";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { getKIIKoboRedirectUrl } from "@/lib/api/kiiRespondent";
import { respondentErrorMessage } from "@/lib/api/respondentErrors";

export default function KIIKoboRedirectPage() {
  const params = useParams<{ token: string }>();
  const [formUrl, setFormUrl] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let cancelled = false;
    setError(null);
    getKIIKoboRedirectUrl(params.token)
      .then((res) => {
        if (cancelled) return;
        setFormUrl(res.kobo_form_url);
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setError(respondentErrorMessage(err));
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [params.token, attempt]);

  const retry = useCallback(() => setAttempt((n) => n + 1), []);

  return (
    <main className="min-h-screen flex flex-col">
      <StudyHeader />
      <section className="flex-1 flex items-center justify-center px-6 py-16">
        <Card className="max-w-md w-full text-center space-y-4">
          {error ? (
            <>
              <p className="text-danger">{error}</p>
              <Button className="w-full" onClick={retry}>
                Try again
              </Button>
            </>
          ) : formUrl ? (
            <>
              <p className="text-text-muted">
                Thank you. You&apos;re ready to begin the interview, in your own time.
              </p>
              <Button className="w-full" onClick={() => window.open(formUrl, "_self")}>
                Start the interview
              </Button>
            </>
          ) : (
            <p className="text-text-muted">Preparing the interview form…</p>
          )}
        </Card>
      </section>
    </main>
  );
}
