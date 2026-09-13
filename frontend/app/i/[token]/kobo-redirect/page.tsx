"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { StudyHeader } from "@/components/respondent/StudyHeader";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { getKoboRedirectUrl } from "@/lib/api/respondent";
import { respondentErrorMessage } from "@/lib/api/respondentErrors";
import { PARTICIPANT_INFORMATION_SHEET_VERSION } from "@/lib/constants/participantInformation";
import { useRespondentFlow } from "@/lib/store/respondentFlow";

export default function KoboRedirectPage() {
  const params = useParams<{ token: string }>();
  const router = useRouter();
  const token = useRespondentFlow((s) => s.token) || params.token;
  const roleCategory = useRespondentFlow((s) => s.roleCategory);
  const [formUrl, setFormUrl] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let cancelled = false;
    setError(null);
    getKoboRedirectUrl({
      token,
      administrationMode: "01",
      respondentRoleCategory: roleCategory,
      consentVersion: PARTICIPANT_INFORMATION_SHEET_VERSION,
    })
      .then((res) => {
        if (cancelled) return;
        setFormUrl(res.kobo_form_url);
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        // The raw backend message used to be shown verbatim -- fine for
        // "consent_required", unhelpful for a throttle or a 500.
        setError(respondentErrorMessage(err));
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, roleCategory, attempt]);

  const retry = useCallback(() => setAttempt((n) => n + 1), []);

  return (
    <main className="min-h-screen flex flex-col">
      <StudyHeader />
      <section className="flex-1 flex items-center justify-center px-6 py-16">
        <Card className="max-w-md w-full text-center space-y-4">
          {error ? (
            <>
              <p className="text-danger">{error}</p>
              {/* Dead end otherwise: the questionnaire never opens and
                  there is nothing on the page to press. */}
              <Button className="w-full" onClick={retry}>
                Try again
              </Button>
              <button
                type="button"
                onClick={() => router.push(`/i/${params.token}/choice`)}
                className="w-full text-sm text-text-muted underline min-h-11"
              >
                Ask a researcher to help me instead
              </button>
            </>
          ) : formUrl ? (
            <>
              <p className="text-text-muted">
                Thank you. You&apos;re ready to begin the questionnaire.
              </p>
              <Button className="w-full" onClick={() => window.open(formUrl, "_self")}>
                Start the questionnaire
              </Button>
            </>
          ) : (
            <p className="text-text-muted">Preparing your questionnaire…</p>
          )}
        </Card>
      </section>
    </main>
  );
}
