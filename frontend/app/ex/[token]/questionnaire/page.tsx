"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { StudyHeader } from "@/components/respondent/StudyHeader";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { getExpertQuestionnaireUrl } from "@/lib/api/expertRespondent";
import { respondentErrorMessage } from "@/lib/api/respondentErrors";

/** Opens the KoboToolbox questionnaire with the expert's ID filled in; the server gives the link only after consent. */
export default function ExpertQuestionnairePage() {
  const params = useParams<{ token: string }>();
  const [formUrl, setFormUrl] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let cancelled = false;
    setError(null);
    getExpertQuestionnaireUrl(params.token)
      .then((res) => !cancelled && setFormUrl(res.kobo_form_url))
      .catch((err: unknown) => !cancelled && setError(respondentErrorMessage(err)));
    return () => {
      cancelled = true;
    };
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
              <Button className="w-full" onClick={retry}>Try again</Button>
            </>
          ) : formUrl ? (
            <>
              <p className="text-text-muted">
                Thank you. The questionnaire takes about 15–20 minutes: 16 indicators, each rated for relevance, clarity
                and observability. Your Expert ID is already filled in.
              </p>
              <Button className="w-full" onClick={() => window.open(formUrl, "_self")}>Open the questionnaire</Button>
            </>
          ) : (
            <p className="text-text-muted">Preparing the questionnaire…</p>
          )}
        </Card>
      </section>
    </main>
  );
}
